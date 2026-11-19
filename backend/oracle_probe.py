"""Exercise real Oracle runtime SQL with fictional data, then roll it all back."""
from datetime import datetime,timezone
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from oracle_mapping import build_rows,canonical
from oracle_migration import TABLES,ROOT,lock_tables,insert_rows,compare_rows


def validate_runtime_sql(db,root=ROOT):
    from oracle_connection import configure_fetch
    from oracle_runtime import _unit,RepositoryConnection,load_access,save_access
    from oracle_instructions import OracleInstructionVersions
    from request_limits import RequestLimits
    if getattr(_unit,'db',None) is not None: raise ValueError('Run runtime SQL validation from the administration tool only.')
    configure_fetch(db)
    old_mode=os.environ.get('REWRITE_STORAGE_BACKEND')
    channel='oracle-check-'+uuid4().hex[:12]
    identity='probe-'+uuid4().hex
    now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
    user=dict(email='oracle-probe@example.invalid',name='Fictional database check',role='user',channel_id=channel)
    snapshot=dict(format_version=1,migration_id=identity,captured_at=now,source_files={},
        access=dict(channels=[dict(id=channel,name='Temporary SQL validation')],users=[user],activity=[],notifications=[],
            approval_batches=[dict(id=identity,channel_id=channel,title='Fictional test',status='draft',created_by_email=user['email'],
                created_by=user['name'],created_at=now,updated_at=now,items=[dict(id='item',source='Fictional source',
                    generated={'en':'English database check','ar':'نص عربي للاختبار فقط. '*4000})],events=[])]),
        instructions=[dict(channel_id=channel,module_id='CHANNEL_SYSTEM',file_name='01_SYSTEM_INSTRUCTIONS.md',
                           kind='system',content='Fictional SQL test rules.')],
        sqlite={'request-limits.sqlite3':{'channel_limits':[dict(channel=channel,monthly_limit=2)]}})
    try:
        lock_tables(db)
        with db.cursor() as cursor:
            for table in TABLES:
                cursor.execute('SELECT COUNT(*) FROM '+table)
                if cursor.fetchone()[0]: raise ValueError('Runtime SQL validation requires an empty application target; it will not modify existing data.')
            cursor.execute('SELECT COUNT(*) FROM genai_harf_runtime_state')
            if cursor.fetchone()[0]: raise ValueError('Runtime state already exists. This probe is only for pre-migration validation.')
        records=build_rows(snapshot)
        for table,rows in records.items(): insert_rows(db,table,rows)
        import oracledb
        with db.cursor() as cursor:
            cursor.setinputsizes(payload=oracledb.DB_TYPE_CLOB)
            cursor.execute("INSERT INTO genai_harf_migration_snapshots(migration_id,snapshot_sha256,snapshot_json,migration_status) VALUES(:id,:checksum,:payload,'imported')",
                           id=identity,checksum='0'*64,payload=canonical(snapshot))
            cursor.execute("INSERT INTO genai_harf_runtime_state(state_id,revision,migration_id,baseline_at,access_json) VALUES('access',1,:id,:baseline,:payload)",
                           id=identity,baseline=now,payload=canonical(snapshot['access']))
        compare_rows(db,records)
        _unit.db=db
        os.environ['REWRITE_STORAGE_BACKEND']='oracle'
        data=load_access(); data['users'][0]['name']='Updated fictional check'; save_access(data)
        if load_access()['users'][0]['name']!='Updated fictional check': raise ValueError('Oracle access write/read failed.')
        quota=RequestLimits(); quota.set_user(channel,user,2)
        reservation=quota.reserve(channel,user); quota.finish(reservation,True)
        if quota.summary(channel,[user],user)['mine']['used']!=1: raise ValueError('Oracle quota write/read failed.')
        feedback=RepositoryConnection('feedback')
        try:
            feedback.execute('BEGIN IMMEDIATE')
            feedback.execute('''INSERT INTO feedback(id,channel_id,workspace,user_email,user_name,fingerprint,rating,reason,snapshot,instruction_manifest,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(identity,channel,'rewrite',user['email'],user['name'],'1'*64,'down','Fictional reason',
                canonical({'task':'write','output_text':'نص عربي '*8000}),canonical({'files':[]}),now,now))
            row=feedback.execute("SELECT id,rating,reason,json_extract(snapshot,'$.task') AS task FROM feedback WHERE id=? ORDER BY updated_at DESC LIMIT 20 OFFSET ?",(identity,0)).fetchone()
            if not row or row['task']!='write': raise ValueError('Oracle feedback/JSON/pagination validation failed.')
            feedback.execute('UPDATE feedback SET status=?,admin_note=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=? AND updated_at=?',
                ('reviewed','Fictional review',user['email'],now,now,identity,now))
        finally: feedback.close()
        temporary=root/'tmp'
        temporary.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='oracle-sql-check-',dir=temporary) as directory:
            path=Path(directory)/'01_SYSTEM_INSTRUCTIONS.md'
            path.write_text('Fictional SQL test rules.',encoding='utf-8')
            repository=OracleInstructionVersions(path)
            result=repository.save(channel,'CHANNEL_SYSTEM',path,path,'Updated fictional test rules.',{'name':'SQL validation','role':'system'},1)
            if result['version']!=2 or repository.get(channel,'CHANNEL_SYSTEM',path,1)['content']!='Fictional SQL test rules.':
                raise ValueError('Oracle instruction version validation failed.')
            if len(repository.list(channel,'CHANNEL_SYSTEM',path)['versions'])!=2:
                raise ValueError('Oracle instruction history paging failed.')
    finally:
        if getattr(_unit,'db',None) is db: del _unit.db
        if old_mode is None: os.environ.pop('REWRITE_STORAGE_BACKEND',None)
        else: os.environ['REWRITE_STORAGE_BACKEND']=old_mode
        # No commit: no fictional user, copy, reservation or version survives.
        db.rollback()
    with db.cursor() as cursor:
        for table in (*TABLES,'genai_harf_runtime_state'):
            cursor.execute('SELECT COUNT(*) FROM '+table)
            if cursor.fetchone()[0]: raise ValueError('Temporary SQL probe did not roll back cleanly.')
        cursor.execute('SELECT COUNT(*) FROM genai_harf_migration_snapshots WHERE migration_id=:id',id=identity)
        if cursor.fetchone()[0]: raise ValueError('Temporary SQL probe snapshot did not roll back.')
