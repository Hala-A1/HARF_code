"""Export live Oracle data back into verified local stores before reverting."""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from dotenv import dotenv_values,set_key

from oracle_connection import CONFIG_FILE
from instruction_locations import instruction_relative_path, instruction_restore_path
from oracle_mapping import canonical,digest
from oracle_runtime import text

SCHEMAS={
 'instruction-versions.sqlite3':{'instruction_versions':'''channel_id TEXT NOT NULL,module_id TEXT NOT NULL,version INTEGER NOT NULL,
 content TEXT NOT NULL,checksum TEXT NOT NULL,created_at TEXT NOT NULL,actor_name TEXT NOT NULL,actor_email TEXT,actor_role TEXT NOT NULL,
 action TEXT NOT NULL,note TEXT NOT NULL,restored_from INTEGER,characters INTEGER NOT NULL,words INTEGER NOT NULL,lines INTEGER NOT NULL,
 PRIMARY KEY(channel_id,module_id,version)'''},
 'feedback.sqlite3':{'feedback':'''id TEXT PRIMARY KEY,channel_id TEXT NOT NULL,workspace TEXT NOT NULL,user_email TEXT NOT NULL,
 user_name TEXT NOT NULL,fingerprint TEXT NOT NULL,rating TEXT NOT NULL CHECK(rating IN ('up','down')),reason TEXT NOT NULL,
 snapshot TEXT NOT NULL,instruction_manifest TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'new',admin_note TEXT NOT NULL DEFAULT '',reviewed_by TEXT,reviewed_at TEXT,
 UNIQUE(user_email,channel_id,fingerprint)'''},
 'request-limits.sqlite3':{
 'channel_limits':'channel TEXT PRIMARY KEY,monthly_limit INTEGER NOT NULL CHECK(monthly_limit>=0)',
 'user_limits':'channel TEXT NOT NULL,principal TEXT NOT NULL,monthly_limit INTEGER NOT NULL CHECK(monthly_limit>=0),PRIMARY KEY(channel,principal)',
 'request_usage':'id TEXT PRIMARY KEY,channel TEXT NOT NULL,principal TEXT NOT NULL,month TEXT NOT NULL,state TEXT NOT NULL,expires REAL NOT NULL,created_at TEXT NOT NULL'},
}


def configure(mode,password=None):
    if mode not in {'local','oracle'}: raise ValueError('Invalid storage mode.')
    CONFIG_FILE.touch(exist_ok=True)
    set_key(str(CONFIG_FILE),'ORACLE_USER','REWRITE_APP')
    if not dotenv_values(CONFIG_FILE).get('ORACLE_DSN'):
        set_key(str(CONFIG_FILE),'ORACLE_DSN',os.getenv('ORACLE_DSN','localhost:1521/FREEPDB1'))
    if password is not None: set_key(str(CONFIG_FILE),'ORACLE_PASSWORD',password)
    set_key(str(CONFIG_FILE),'REWRITE_STORAGE_BACKEND',mode)
    os.environ['REWRITE_STORAGE_BACKEND']=mode
    if password is not None: os.environ['ORACLE_PASSWORD']=password


def dict_rows(db,sql):
    with db.cursor() as cursor:
        cursor.execute(sql)
        columns=[c[0].lower() for c in cursor.description]
        return [{c:text(v) for c,v in zip(columns,row)} for row in cursor]


def export_snapshot(db,readonly=True):
    from oracle_instructions import SELECT,as_row
    with db.cursor() as cursor:
        if readonly:
            db.rollback()
            cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute("SELECT r.access_json,s.snapshot_json,r.baseline_at FROM genai_harf_runtime_state r JOIN genai_harf_migration_snapshots s ON r.migration_id=s.migration_id WHERE r.state_id='access'")
        row=cursor.fetchone()
        if not row: raise ValueError('No imported runtime state is available to export.')
        access=json.loads(text(row[0]))
        original=json.loads(text(row[1]))
        baseline=row[2]
    from oracle_runtime import access_rows,ACCESS_TABLES
    from oracle_migration import compare_rows
    projections=access_rows(access,baseline)
    compare_rows(db,{table:projections[table] for table in ACCESS_TABLES})
    files={}
    for relative, content in original['source_files'].items():
        normalized=instruction_relative_path(relative)
        if normalized in files and files[normalized] != content:
            raise ValueError('Conflicting instruction paths in source snapshot.')
        files[normalized]=content
    instructions=[]
    for row in dict_rows(db,'SELECT channel_id,module_id,file_name,display_name,instruction_kind,is_active,content_md,metadata_json,checksum FROM genai_harf_instructions'):
        channel,name=row['channel_id'],row['file_name']
        if Path(name).name!=name or Path(channel).name!=channel or channel in {'.','..'}:
            raise ValueError('Invalid source instruction path in Oracle.')
        if hashlib.sha256(row['content_md'].encode('utf-8')).hexdigest()!=row['checksum']:
            raise ValueError('Instruction checksum mismatch in Oracle. Review direct database edits before recovery.')
        data=json.loads(row['metadata_json'])
        data.update(channel_id=channel,module_id=row['module_id'],file_name=name,display_name=row['display_name'],
                    kind=row['instruction_kind'],active=bool(row['is_active']),content=row['content_md'])
        instructions.append(data)
        path='instructions/channels/'+channel+'/'+name
        if path in files or row['is_active']: files[path]=row['content_md']
    with db.cursor() as cursor:
        cursor.execute(SELECT)
        history=[dict(as_row(v)) for v in cursor]
    feedback=dict_rows(db,'SELECT * FROM rw_feedback_legacy')
    for row in feedback:
        row['reason']=row['reason'] or ''; row['admin_note']=row['admin_note'] or ''
    limits={name:dict_rows(db,'SELECT * FROM rw_'+name+'_legacy') for name in ('channel_limits','user_limits','request_usage')}
    for row in limits['request_usage']: row['expires']=float(row['expires'])
    return dict(format_version=1,migration_id='oracle-export-'+uuid4().hex,
        captured_at=datetime.now(timezone.utc).isoformat(),access=access,instructions=instructions,source_files=files,
        sqlite={'instruction-versions.sqlite3':{'instruction_versions':history},'feedback.sqlite3':{'feedback':feedback},
                'request-limits.sqlite3':limits})


def recovery_fingerprint(snapshot):
    return digest(dict(access=snapshot['access'],source_files=snapshot['source_files'],
        sqlite={name:{table:sorted(records,key=canonical) for table,records in tables.items()}
                for name,tables in snapshot['sqlite'].items()}))


def materialize(snapshot,root):
    """Create a new backup-shaped artifact; never overwrite the running local stores."""
    destination=root/'backups/oracle'/snapshot['migration_id']
    destination.mkdir(parents=True,exist_ok=False)
    try:
        for relative,content in snapshot['source_files'].items():
            path=destination/relative
            instruction_relative_path(relative)  # Validate both historic and current layouts.
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Unexpected instruction file path in source snapshot.')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content,encoding='utf-8')
        (destination/'backend').mkdir(exist_ok=True)
        (destination/'backend/access-control.json').write_text(canonical(snapshot['access']),encoding='utf-8')
        for filename,tables in SCHEMAS.items():
            with closing(sqlite3.connect(destination/'backend'/filename)) as db:
                for table,definition in tables.items():
                    db.execute('CREATE TABLE '+table+' ('+definition+')')
                    records=snapshot['sqlite'].get(filename,{}).get(table,[])
                    for record in records:
                        columns=list(record)
                        # Columns originate from fixed Oracle projections, not executable user input.
                        allowed={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
                        if not set(columns)<=allowed: raise ValueError('Unknown export columns; update the migration schema before restoring.')
                        db.execute('INSERT INTO '+table+' ('+','.join('"'+c+'"' for c in columns)+') VALUES ('+','.join('?' for _ in columns)+')',list(record.values()))
                db.commit()
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Export integrity check failed.')
        (destination/'snapshot.json').write_text(canonical(snapshot),encoding='utf-8')
        manifest=dict(format_version=1,migration_id=snapshot['migration_id'],snapshot_sha256=digest(snapshot),
            files={str(p.relative_to(destination)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in destination.rglob('*') if p.is_file()})
        (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return destination
    except BaseException:
        (destination/'INCOMPLETE.txt').write_text('Export failed. Do not restore this directory.',encoding='utf-8')
        raise


def restore_local(directory,root):
    from instruction_versions import _atomic_write
    from oracle_migration import require_stopped,load_backup,create_backup,sqlite_rows
    require_stopped()
    snapshot=load_backup(directory)
    if not snapshot['migration_id'].startswith('oracle-export-'):
        raise ValueError('Use a fresh export-local artifact to preserve newer Oracle data.')
    # Preserve even the previous local stores before replacing them. This command is
    # not automatically called after connection failures and never destroys Oracle data.
    previous,_=create_backup(root)
    try:
        _atomic_write(root/'backend/access-control.json',canonical(snapshot['access']))
        for relative,content in snapshot['source_files'].items():
            path=instruction_restore_path(root, relative)
            _atomic_write(path,content)
        for filename in SCHEMAS:
            with closing(sqlite3.connect((Path(directory)/'backend'/filename).resolve().as_uri()+'?mode=ro',uri=True)) as source:
                with closing(sqlite3.connect(root/'backend'/filename,timeout=10)) as target:
                    source.backup(target)
        access=json.loads((root/'backend/access-control.json').read_text(encoding='utf-8'))
        if canonical(access)!=canonical(snapshot['access']): raise ValueError('Restored access data did not match the Oracle export.')
        for filename,tables in snapshot['sqlite'].items():
            expected={t:sorted(v,key=canonical) for t,v in tables.items()}
            if canonical(sqlite_rows(root/'backend'/filename))!=canonical(expected): raise ValueError('Restored database did not match: '+filename)
        for relative,content in snapshot['source_files'].items():
            if instruction_restore_path(root, relative).read_text(encoding='utf-8')!=content: raise ValueError('Restored instructions did not match.')
    except BaseException:
        raise ValueError('Local restore did not finish. Keep the backend stopped and Oracle selected. Previous local backup: '+str(previous)) from None
    configure('local')
    return previous
