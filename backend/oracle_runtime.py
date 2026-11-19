"""Oracle runtime pool, revision-checked access store and bounded SQL dialect adapter.

Existing HTTP permissions and business rules remain in their original modules.
Only feedback and quota statements use the adapter; unknown DML is rejected.
"""
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime,timezone
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from threading import local
from threading import RLock

from fastapi import HTTPException

from oracle_connection import settings,configure_fetch
from oracle_mapping import build_rows, canonical, timestamp
from oracle_migration import insert_rows

_unit = local()
_access_cache = {'revision':None,'data':None}
_cache_lock = RLock()


@lru_cache(maxsize=1)
def pool():
    import oracledb
    return oracledb.create_pool(**settings(), min=1,max=6,increment=1,
        getmode=oracledb.POOL_GETMODE_TIMEDWAIT,wait_timeout=10000,tcp_connect_timeout=10)


@contextmanager
def transaction():
    active=getattr(_unit,'db',None)
    if active is not None:
        yield active
        return
    db=configure_fetch(pool().acquire())
    db.call_timeout=30000
    _unit.db=db
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        del _unit.db
        pool().release(db)


def text(value):
    return value.read() if hasattr(value,'read') else value


class AccessData(dict):
    def __init__(self,value,revision):
        super().__init__(value)
        self.revision=revision


def load_access():
    nested=getattr(_unit,'db',None) is not None
    with transaction() as db,db.cursor() as cursor:
        cursor.execute("SELECT revision FROM genai_harf_runtime_state WHERE state_id='access'")
        revision_row=cursor.fetchone()
        if revision_row is None:
            raise RuntimeError('Oracle has no imported runtime state. Complete migration before enabling it.')
        with _cache_lock:
            if not nested and _access_cache['revision']==revision_row[0]:
                return AccessData(deepcopy(_access_cache['data']),int(revision_row[0]))
        cursor.execute("SELECT access_json,revision FROM genai_harf_runtime_state WHERE state_id='access'")
        row=cursor.fetchone()
        if row is None:
            raise RuntimeError('Oracle has no imported runtime state. Complete migration before enabling it.')
        data=json.loads(text(row[0]))
        if not nested:
            with _cache_lock:
                _access_cache.update(revision=int(row[1]),data=deepcopy(data))
        return AccessData(data,int(row[1]))


ACCESS_TABLES=('genai_harf_channels','genai_harf_users','genai_harf_batches','genai_harf_copy_items','genai_harf_outputs','genai_harf_copy_versions',
               'genai_harf_approval_events','genai_harf_language_approvals','genai_harf_notifications','genai_harf_activity')
KEYS={'genai_harf_channels':('channel_id',),'genai_harf_users':('email',),'genai_harf_batches':('batch_id',),
      'genai_harf_copy_items':('batch_id','item_id'),'genai_harf_outputs':('batch_id','item_id','language_code'),
      'genai_harf_copy_versions':('batch_id','item_id','language_code','version_no'),
      'genai_harf_approval_events':('event_id',),'genai_harf_language_approvals':('batch_id','layer_no','language_code'),
      'genai_harf_notifications':('notification_id',),'genai_harf_activity':('activity_id',)}


def access_rows(data,baseline):
    return build_rows(dict(access=data,sqlite={},instructions=[],captured_at=baseline))


def sync_access_rows(db,previous,current,baseline):
    """Write only changed projections; retain stable IDs and historical timestamps."""
    old,new=access_rows(previous,baseline),access_rows(current,baseline)
    indexed=lambda table,rows:{tuple(r[k] for k in KEYS[table]):r for r in rows}
    changes={}
    for table in ACCESS_TABLES:
        before,after=indexed(table,old[table]),indexed(table,new[table])
        changes[table]=(before,after)
    # Delete removed children first. Updates use UPDATE, preserving FK parents.
    with db.cursor() as cursor:
        for table in reversed(ACCESS_TABLES):
            before,after=changes[table]
            for key in before.keys()-after.keys():
                where=' AND '.join(c+'=:'+str(i+1) for i,c in enumerate(KEYS[table]))
                cursor.execute('DELETE FROM '+table+' WHERE '+where,key)
    from oracle_mapping import CLOBS,TIMESTAMPS
    import oracledb
    with db.cursor() as cursor:
        for table in ACCESS_TABLES:
            before,after=changes[table]
            for key,record in after.items():
                if key not in before:
                    insert_rows(db,table,[record])
                elif canonical(record)!=canonical(before[key]):
                    values={c:v for c,v in record.items() if c not in KEYS[table]}
                    assignments=[c+'='+ ("TO_TIMESTAMP_TZ(:"+c+", 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')" if c in TIMESTAMPS else ':'+c) for c in values]
                    where=' AND '.join(c+'=:'+c for c in KEYS[table])
                    cursor.setinputsizes(**{c:oracledb.DB_TYPE_CLOB if c in CLOBS else None for c in record})
                    cursor.execute('UPDATE '+table+' SET '+','.join(assignments)+' WHERE '+where,record)


def save_access(data):
    expected=getattr(data,'revision',None)
    if expected is None:
        raise RuntimeError('Oracle access data must be loaded before it is saved.')
    import oracledb
    with transaction() as db,db.cursor() as cursor:
        cursor.execute("SELECT access_json,revision,baseline_at FROM genai_harf_runtime_state WHERE state_id='access' FOR UPDATE WAIT 10")
        raw,revision,baseline=cursor.fetchone()
        if revision!=expected:
            raise HTTPException(status_code=409,detail='Another change was saved at the same time. Refresh and retry; your existing data is safe.')
        previous=json.loads(text(raw))
        if canonical(previous)==canonical(data): return
        now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
        for collection,key in (('users','email'),('channels','id')):
            previous_records={row[key]:row for row in previous[collection]}
            for row in data[collection]:
                old=previous_records.get(row[key])
                if old is None or canonical(old)!=canonical(row):
                    row.setdefault('created_at',(old or {}).get('created_at') or (baseline if old else now))
                    if collection=='users': row['updated_at']=now
        sync_access_rows(db,previous,data,baseline)
        # New channels receive only their own starter files, within this transaction.
        old_ids={c['id'] for c in previous['channels']}
        for channel in data['channels']:
            if channel['id'] not in old_ids:
                seed_channel_instructions(db,channel['id'])
        cursor.setinputsizes(payload=oracledb.DB_TYPE_CLOB)
        cursor.execute("UPDATE genai_harf_runtime_state SET access_json=:payload,revision=revision+1,updated_at=SYSTIMESTAMP WHERE state_id='access'",payload=canonical(data))
    data.revision+=1


def seed_channel_instructions(db,channel):
    import access_control
    from oracle_instructions import append_version
    for module in ('CHANNEL_SYSTEM','CHANNEL_TEMPLATES','CHANNEL_USER_ADMIN_GUIDE'):
        file=access_control.CHANNEL_PROMPT_DIR/channel/access_control.INSTRUCTION_MODULES[module]['filename']
        if file.is_file():
            append_version(db,channel,module,file,file.read_text(encoding='utf-8'),
                {'name':'Channel creation','role':'system'},'baseline','Starter instructions for this channel.')


class Row(Mapping):
    def __init__(self,columns,values): self.data=dict(zip(columns,values))
    def __getitem__(self,key): return list(self.data.values())[key] if isinstance(key,int) else self.data[key]
    def __iter__(self): return iter(self.data)
    def __len__(self): return len(self.data)


class Result:
    def __init__(self,cursor,kind): self.cursor=cursor; self.kind=kind
    @property
    def rowcount(self): return self.cursor.rowcount
    def row(self,values):
        if values is None: return None
        columns=[c[0].lower() for c in self.cursor.description]
        converted=[]
        for c,v in zip(columns,values):
            v=text(v)
            if self.kind=='feedback' and c in {'reason','admin_note'} and v is None: v=''
            converted.append(v)
        return Row(columns,converted)
    def fetchone(self): return self.row(self.cursor.fetchone())
    def fetchall(self): return [self.row(v) for v in self.cursor.fetchall()]
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None: break
            yield row


TABLE_MAP={'feedback':'genai_harf_feedback','channel_limits':'genai_harf_channel_limits','user_limits':'genai_harf_user_limits','request_usage':'genai_harf_request_usage'}
READ_MAP={key:'rw_'+key+'_legacy' for key in TABLE_MAP}
COLUMN_MAP={'feedback':{'id':'feedback_id','workspace':'workspace_name','reason':'reason_text','snapshot':'snapshot_json','status':'review_status'},
            'quota':{'channel':'channel_id','principal':'principal_id','id':'request_id','month':'month_key','state':'request_state','expires':'expires_at'}}
INSERT_COLUMNS={'channel_limits':['channel','monthly_limit'],'user_limits':['channel','principal','monthly_limit'],
                'request_usage':['id','channel','principal','month','state','expires','created_at']}


def replace_identifiers(sql,mapping):
    return re.sub(r"'(?:''|[^'])*'|\b[A-Za-z_]\w*\b",lambda m:m[0] if m[0].startswith("'") else mapping.get(m[0].lower(),m[0]),sql)


def compile_statement(sql,parameters,kind):
    """Translate the repositories' small SQL surface, using bind variables throughout."""
    sql=' '.join(sql.split())
    parameters=list(parameters)
    selecting=sql.upper().startswith('SELECT ')
    allowed={'feedback'} if kind=='feedback' else {'channel_limits','user_limits','request_usage'}
    head=re.split(r' ON CONFLICT',sql,flags=re.I)[0]
    mentioned={name.lower() for name in re.findall(r'\b(?:FROM|INTO|UPDATE)\s+(\w+)',head,re.I)}
    if not mentioned or not mentioned<=allowed:
        raise ValueError('Unsupported Oracle repository statement.')
    fields=[]
    insert=re.match(r'INSERT(?: OR IGNORE)? INTO (\w+)(?:\s*\(([^)]+)\))? VALUES\s*\(([^)]+)\)',sql,re.I)
    if insert:
        fields=[c.strip() for c in insert[2].split(',')] if insert[2] else INSERT_COLUMNS[insert[1]]
    else:
        for match in re.finditer(r'\?',sql):
            left=sql[:match.start()]
            field=re.search(r'(\w+)\s*(?:<=|>=|<>|=|<|>)\s*$',left)
            fields.append(field[1].lower() if field else None)
    if len(fields)!=len(parameters): raise ValueError('Oracle parameter count mismatch.')
    binds={}
    types={}
    tokens=[]
    for n,(field,value) in enumerate(zip(fields,parameters)):
        key='p'+str(n)
        is_date=not selecting and field in {'created_at','updated_at','reviewed_at','expires'}
        binds[key]=timestamp(value) if is_date and value is not None else value
        tokens.append("TO_TIMESTAMP_TZ(:"+key+", 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')" if is_date else ':'+key)
        if not selecting and field in {'reason','snapshot','instruction_manifest','admin_note'}: types[key]='clob'
    if insert and ('ON CONFLICT' in sql.upper() or 'INSERT OR IGNORE' in sql.upper()):
        table=TABLE_MAP[insert[1]]
        names=[COLUMN_MAP[kind].get(c,c) for c in fields]
        keys=['channel_id']+(['principal_id'] if insert[1]=='user_limits' else [])
        sql='MERGE INTO '+table+' t USING (SELECT '+','.join(v+' AS '+c for c,v in zip(names,tokens))+' FROM dual) s ON ('+' AND '.join('t.'+c+'=s.'+c for c in keys)+') '
        if 'IGNORE' not in insert[0].upper() and 'INSERT OR IGNORE' not in insert[0].upper():
            sql+='WHEN MATCHED THEN UPDATE SET '+','.join('t.'+c+'=s.'+c for c in names if c not in keys)+' '
        sql+='WHEN NOT MATCHED THEN INSERT ('+','.join(names)+') VALUES ('+','.join('s.'+c for c in names)+')'
        return sql,binds,types
    # Replace only the original placeholders, before inserting SQL date format strings.
    it=iter(tokens)
    sql=re.sub(r'\?',lambda _:next(it),sql)
    if selecting:
        sql=replace_identifiers(sql,READ_MAP)
        sql=re.sub(r"json_extract\((\w+),'([^']+)'\)",r"JSON_VALUE(\1,'\2')",sql,flags=re.I)
        sql=re.sub(r"SUM\((\w+)='([^']+)'\)",r"SUM(CASE WHEN \1='\2' THEN 1 ELSE 0 END)",sql,flags=re.I)
        sql=re.sub(r'\bAS new\b','AS "new"',sql,flags=re.I)
        sql=re.sub(r'LIMIT (:\w+|\d+) OFFSET (:\w+|\d+)$',r'OFFSET \2 ROWS FETCH NEXT \1 ROWS ONLY',sql,flags=re.I)
    else:
        if not insert and not sql.upper().startswith(('UPDATE ','DELETE ')): raise ValueError('Unsupported Oracle DML.')
        sql=replace_identifiers(sql,{**TABLE_MAP,**COLUMN_MAP[kind]})
    return sql,binds,types


class RepositoryConnection:
    def __init__(self,kind):
        self.kind=kind
        self.borrowed=getattr(_unit,'db',None) is not None
        self.db=_unit.db if self.borrowed else configure_fetch(pool().acquire())
        self.db.call_timeout=30000
        self.cursors=[]
    def execute(self,sql,parameters=()):
        if sql.strip().upper()=='BEGIN IMMEDIATE':
            cursor=self.db.cursor(); self.cursors.append(cursor)
            cursor.execute('LOCK TABLE '+('genai_harf_feedback' if self.kind=='feedback' else 'genai_harf_channel_limits')+' IN EXCLUSIVE MODE WAIT 10')
            return Result(cursor,self.kind)
        compiled,binds,types=compile_statement(sql,parameters,self.kind)
        cursor=self.db.cursor(); self.cursors.append(cursor)
        if types:
            import oracledb
            cursor.setinputsizes(**{k:oracledb.DB_TYPE_CLOB for k in types})
        cursor.execute(compiled,binds)
        return Result(cursor,self.kind)
    def __enter__(self): return self
    def __exit__(self,kind,value,traceback):
        if kind: self.rollback()
        else: self.commit()
    def commit(self):
        if not self.borrowed: self.db.commit()
    def rollback(self):
        if not self.borrowed: self.db.rollback()
    def close(self):
        try:
            self.rollback()
            for cursor in self.cursors: cursor.close()
        finally:
            if not self.borrowed: pool().release(self.db)


def startup():
    with transaction() as db,db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM genai_harf_schema_versions WHERE version_id='003'")
        if cursor.fetchone()[0]!=1: raise RuntimeError('Install runtime schema 003 before enabling Oracle.')
        cursor.execute("SELECT COUNT(*) FROM genai_harf_runtime_state WHERE state_id='access'")
        if cursor.fetchone()[0]!=1: raise RuntimeError('Import and verify existing data before enabling Oracle.')
        cursor.execute('SELECT channel_id,module_id FROM genai_harf_instructions WHERE is_active=1')
        files=cursor.fetchall()
    for channel,module in files:
        cache_instruction(channel,module)


def cache_instruction(channel,module,path=None):
    """Oracle is authoritative; the Markdown file is the existing retrieval cache."""
    import access_control
    from instruction_versions import _atomic_write
    with transaction() as db,db.cursor() as cursor:
        cursor.execute('SELECT checksum,file_name FROM genai_harf_instructions WHERE channel_id=:channel AND module_id=:module',channel=channel,module=module)
        row=cursor.fetchone()
        if not row: return path
        checksum,name=row
        if Path(name).name!=name or not re.fullmatch(r'[a-z0-9-]+',channel): raise RuntimeError('Invalid instruction cache path.')
        target=Path(path) if path is not None else access_control.CHANNEL_PROMPT_DIR/channel/name
        root=access_control.CHANNEL_PROMPT_DIR.resolve()
        if not target.resolve().is_relative_to(root): raise RuntimeError('Instruction cache must stay inside the channel directory.')
        existing=hashlib.sha256(target.read_text(encoding='utf-8').encode('utf-8')).hexdigest() if target.exists() else None
        if existing!=checksum:
            cursor.execute('SELECT content_md FROM genai_harf_instructions WHERE channel_id=:channel AND module_id=:module',channel=channel,module=module)
            _atomic_write(target,text(cursor.fetchone()[0]))
        return target
