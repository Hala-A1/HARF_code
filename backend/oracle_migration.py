"""Backup, inspect, import, verify and undo an Oracle data import.

Run locally from the repository root. No command switches runtime storage.
Database passwords are requested with getpass and never printed or saved.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from uuid import uuid4

from oracle_connection import connection, settings
from oracle_mapping import TABLES, CLOBS, TIMESTAMPS, build_rows, canonical, digest

ROOT = Path(__file__).resolve().parents[1]
DATABASES = ('instruction-versions.sqlite3','feedback.sqlite3','request-limits.sqlite3')


def require_stopped():
    # Cross-store snapshots require a maintenance window, not just a JSON lock.
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(('127.0.0.1',8000)) == 0:
            raise ValueError('Stop the Harf backend before backup/import. It is still listening on port 8000.')


def sqlite_rows(path):
    if not path.exists():
        return {}
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed: '+path.name)
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        result={}
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            result[table]=sorted([dict(row) for row in db.execute('SELECT * FROM '+quoted)], key=canonical)
        return result


def current_source(root=ROOT):
    backend=root/'backend'
    prompt=root/'instructions'
    # Historical backup artifacts keep their original paths and checksums.
    if not prompt.exists():
        prompt=root/'Copywriter/backend/prompt'
    access=json.loads((backend/'access-control.json').read_text(encoding='utf-8'))
    source_files={str(p.relative_to(root)).replace('\\','/'):p.read_text(encoding='utf-8')
                  for p in sorted(prompt.rglob('*.md'))}
    import access_control
    modules={info['filename']:(module,info) for module,info in access_control.INSTRUCTION_MODULES.items()}
    instructions=[]
    for channel in access.get('channels',[]):
        directory=prompt/'channels'/channel['id']
        if directory.resolve().parent != (prompt/'channels').resolve():
            raise ValueError('Invalid channel directory in source data.')
        for file in sorted(directory.glob('*.md')):
            module,info=modules.get(file.name,(file.stem,{}))
            lower=file.name.lower()
            kind='guide' if 'guide' in lower else 'system' if 'system' in lower else 'template' if 'template' in lower else 'reference'
            instructions.append(dict(channel_id=channel['id'],module_id=module,file_name=file.name,
                                     display_name=info.get('name',file.stem),kind=kind,
                                     content=file.read_text(encoding='utf-8'),active=not bool(channel.get('deleted_at'))))
    return dict(access=access,sqlite={name:sqlite_rows(backend/name) for name in DATABASES},
                instructions=instructions,source_files=source_files)


def create_backup(root=ROOT, require_stop=True):
    if require_stop:
        require_stopped()
    from dotenv import dotenv_values
    if os.getenv('INSTRUCTION_VERSIONS_DB') or dotenv_values(root/'.env').get('INSTRUCTION_VERSIONS_DB'):
        raise ValueError('Custom INSTRUCTION_VERSIONS_DB is configured; review the source path before migrating.')
    initial=current_source(root)
    identity=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:10]
    destination=root/'backups/oracle'/identity
    destination.mkdir(parents=True,exist_ok=False)
    try:
        paths=['backend/access-control.json']+list(initial['source_files'])
        for relative in paths:
            target=destination/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((root/relative).read_bytes())
        for name in DATABASES:
            source=root/'backend'/name
            if source.exists():
                # SQLite backup includes committed WAL data; copying only .sqlite3 does not.
                with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as src:
                    with closing(sqlite3.connect(destination/'backend'/name)) as dst:
                        src.backup(dst)
        if require_stop:
            require_stopped()
        copied=current_source(destination)
        if digest(copied)!=digest(initial) or digest(current_source(root))!=digest(initial):
            raise ValueError('Source data changed during backup. This backup will not be accepted.')
        snapshot=dict(format_version=1,migration_id=identity,captured_at=datetime.now(timezone.utc).isoformat(),**copied)
        # Validate all field conversions before labeling the backup usable.
        mapped=build_rows(snapshot)
        (destination/'snapshot.json').write_text(canonical(snapshot),encoding='utf-8')
        manifest={'format_version':1,'migration_id':identity,'snapshot_sha256':digest(snapshot),
                  'row_counts':{t:len(r) for t,r in mapped.items()},
                  'files':{str(p.relative_to(destination)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(destination.rglob('*')) if p.is_file()}}
        (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        return destination,manifest
    except BaseException:
        (destination/'INCOMPLETE.txt').write_text('Backup failed. Do not use this directory for migration.',encoding='utf-8')
        raise


def load_backup(directory):
    directory=Path(directory).resolve()
    if (directory/'INCOMPLETE.txt').exists():
        raise ValueError('This backup is incomplete.')
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for relative,expected in manifest['files'].items():
        path=(directory/relative).resolve()
        if not path.is_relative_to(directory) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Backup integrity check failed: '+relative)
    snapshot=json.loads((directory/'snapshot.json').read_text(encoding='utf-8'))
    if snapshot.get('format_version')!=1 or digest(snapshot)!=manifest['snapshot_sha256'] or snapshot['migration_id']!=manifest['migration_id']:
        raise ValueError('Snapshot integrity/version check failed.')
    return snapshot


def preflight(db, safety=False):
    with db.cursor() as cursor:
        cursor.execute("SELECT version_id FROM genai_harf_schema_versions")
        versions={row[0] for row in cursor}
        if not {'001',*(['002'] if safety else [])}.issubset(versions):
            raise ValueError('Required schema version is missing. Run the SQL installation/safety scripts first.')
        cursor.execute("SELECT value FROM nls_database_parameters WHERE parameter='NLS_CHARACTERSET'")
        if cursor.fetchone()[0]!='AL32UTF8':
            raise ValueError('AL32UTF8 is required for Arabic and English.')
        cursor.execute("SELECT COUNT(*) FROM user_objects WHERE (object_name LIKE 'RW\\_%' ESCAPE '\\' OR object_name LIKE 'HARF\\_%' ESCAPE '\\') AND status <> 'VALID'")
        if cursor.fetchone()[0]:
            raise ValueError('The schema contains invalid application objects.')


def lock_tables(db):
    with db.cursor() as cursor:
        for table in (*TABLES,'genai_harf_migration_snapshots','genai_harf_runtime_state'):
            cursor.execute('LOCK TABLE '+table+' IN EXCLUSIVE MODE NOWAIT')


def insert_rows(db, table, records):
    import oracledb
    with db.cursor() as cursor:
        for record in records:
            columns=list(record)
            expressions=["TO_TIMESTAMP_TZ(:"+c+", 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')" if c in TIMESTAMPS else ':'+c for c in columns]
            cursor.setinputsizes(**{c:oracledb.DB_TYPE_CLOB if c in CLOBS else oracledb.DB_TYPE_VARCHAR if c in TIMESTAMPS else None for c in columns})
            cursor.execute('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join(expressions)+')',record)


def normalized(record):
    # Oracle maps empty VARCHAR2 strings to NULL. The raw snapshot retains exact originals.
    return {key:None if value=='' else int(value) if isinstance(value,float) and value.is_integer() else value
            for key,value in record.items()}


def compare_rows(db, expected):
    for table,records in expected.items():
        with db.cursor() as cursor:
            if not records:
                cursor.execute('SELECT COUNT(*) FROM '+table)
                if cursor.fetchone()[0]!=0:
                    raise ValueError('Unexpected rows in '+table)
                continue
            columns=list(records[0])
            projections=["TO_CHAR("+c+", 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6TZH:TZM')" if c in TIMESTAMPS else c for c in columns]
            cursor.execute('SELECT '+','.join(projections)+' FROM '+table)
            actual=[]
            for values in cursor:
                actual.append({c:(value.read() if hasattr(value,'read') else value) for c,value in zip(columns,values)})
            if sorted(canonical(normalized(r)) for r in records)!=sorted(canonical(normalized(r)) for r in actual):
                if len(records)!=len(actual):
                    detail=' Row counts differ.'
                else:
                    differing=[column for column in columns
                        if sorted(canonical(normalized({column:r[column]})) for r in records)
                        !=sorted(canonical(normalized({column:r[column]})) for r in actual)]
                    detail=' Differing fields: '+', '.join(differing[:6])+'.' if differing else ' Row relationships differ.'
                # Diagnose types/columns without disclosing source text or credentials.
                raise ValueError('Content/count verification failed for '+table+'.'+detail+' No rows will be committed or removed.')


def migrate(db, snapshot, root=ROOT):
    require_stopped()
    source={k:snapshot[k] for k in ('access','sqlite','instructions','source_files')}
    if digest(current_source(root))!=digest(source):
        raise ValueError('The live source differs from this backup. Create a fresh backup while the backend is stopped.')
    expected=build_rows(snapshot)
    preflight(db,safety=True)
    try:
        lock_tables(db)
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM genai_harf_schema_versions WHERE version_id='003'")
            if cursor.fetchone()[0]!=1: raise ValueError('Install 04_runtime_storage.sql before importing.')
            cursor.execute('SELECT COUNT(*) FROM genai_harf_runtime_state')
            if cursor.fetchone()[0]: raise ValueError('Runtime state already exists; import will not replace it.')
            for table in TABLES:
                cursor.execute('SELECT COUNT(*) FROM '+table)
                if cursor.fetchone()[0]:
                    raise ValueError('Import requires empty application tables. Existing data found in '+table)
        for table,records in expected.items():
            insert_rows(db,table,records)
        import oracledb
        with db.cursor() as cursor:
            cursor.setinputsizes(snapshot=oracledb.DB_TYPE_CLOB)
            cursor.execute("INSERT INTO genai_harf_migration_snapshots(migration_id,snapshot_sha256,snapshot_json,migration_status) VALUES(:identity,:checksum,:snapshot,'imported')",
                           dict(identity=snapshot['migration_id'],checksum=digest(snapshot),snapshot=canonical(snapshot)))
            cursor.setinputsizes(payload=oracledb.DB_TYPE_CLOB)
            cursor.execute("INSERT INTO genai_harf_runtime_state(state_id,revision,migration_id,baseline_at,access_json) VALUES('access',1,:identity,:baseline,:payload)",
                           identity=snapshot['migration_id'],baseline=snapshot['captured_at'],payload=canonical(snapshot['access']))
        compare_rows(db,expected)
        verify_snapshot(db,snapshot)
        verify_runtime_baseline(db,snapshot)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return {table:len(records) for table,records in expected.items()}


def verify_snapshot(db, snapshot):
    with db.cursor() as cursor:
        cursor.execute('SELECT snapshot_sha256,snapshot_json,migration_status FROM genai_harf_migration_snapshots WHERE migration_id=:identity',identity=snapshot['migration_id'])
        row=cursor.fetchone()
        if not row or row[2]!='imported':
            raise ValueError('This migration is not in imported state.')
        content=row[1].read() if hasattr(row[1],'read') else row[1]
        if row[0]!=digest(snapshot) or digest(json.loads(content))!=digest(snapshot):
            raise ValueError('The preserved source snapshot does not match the backup.')


def undo_import(db,snapshot):
    preflight(db,safety=True)
    try:
        lock_tables(db)
        verify_snapshot(db,snapshot)
        verify_runtime_baseline(db,snapshot)
        # Refuse to remove updated/new rows. This is undo-import, not post-cutover rollback.
        compare_rows(db,build_rows(snapshot))
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM genai_harf_runtime_state WHERE state_id='access'")
            for table in reversed(TABLES):
                cursor.execute('DELETE FROM '+table)
            cursor.execute("UPDATE genai_harf_migration_snapshots SET migration_status='rolled_back',rolled_back_at=SYSTIMESTAMP WHERE migration_id=:identity",identity=snapshot['migration_id'])
        db.commit()
    except BaseException:
        db.rollback()
        raise


def verify_runtime_baseline(db,snapshot):
    with db.cursor() as cursor:
        cursor.execute("SELECT revision,migration_id,access_json FROM genai_harf_runtime_state WHERE state_id='access'")
        row=cursor.fetchone()
        payload=row[2].read() if row and hasattr(row[2],'read') else row[2] if row else None
        if not row or row[0]!=1 or row[1]!=snapshot['migration_id'] or canonical(json.loads(payload))!=canonical(snapshot['access']):
            raise ValueError('Runtime data changed after import. Use export-local and restore-local to preserve newer changes.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','test-runtime','configure','backup','inspect','import','verify','undo-import','enable-oracle','export-local','restore-local','cutover'])
    parser.add_argument('--backup',type=Path)
    args=parser.parse_args()
    if args.action=='backup':
        path,manifest=create_backup()
        print('Verified private backup created:',path)
        print(json.dumps(manifest['row_counts'],indent=2))
        return
    snapshot=None
    if args.action not in {'check','test-runtime','configure','export-local','cutover'}:
        if not args.backup:
            parser.error('--backup is required for this action')
        snapshot=load_backup(args.backup)
        if args.action=='inspect':
            print('Backup integrity: PASS')
            print(json.dumps({t:len(r) for t,r in build_rows(snapshot).items()},indent=2))
            return
    # No password in command-line arguments, shell history or reports.
    from dotenv import load_dotenv
    from oracle_connection import CONFIG_FILE
    load_dotenv(CONFIG_FILE,override=False)
    password=None if os.getenv('ORACLE_PASSWORD') else getpass('REWRITE_APP database password (hidden): ')
    settings(password)
    with connection(password) as db:
        if args.action=='check':
            preflight(db)
            print('Oracle connection/schema 001: PASS. Runtime storage has not changed.')
        elif args.action=='test-runtime':
            preflight(db,safety=True)
            from oracle_probe import validate_runtime_sql
            validate_runtime_sql(db)
            print('Oracle runtime SQL: PASS. All fictional check data rolled back; storage selection unchanged.')
        elif args.action=='configure':
            preflight(db)
            from storage_backend import oracle_enabled
            if oracle_enabled(): raise ValueError('Oracle is already active. Do not reset storage selection; use the recovery procedure.')
            from oracle_recovery import configure
            configure('local',password or os.getenv('ORACLE_PASSWORD'))
            print('Local Oracle credentials saved in ignored project root .env. Runtime storage remains local.')
        elif args.action=='cutover':
            from oracle_cutover import cutover
            print(cutover(db,password or os.getenv('ORACLE_PASSWORD')))
        elif args.action=='import':
            print(json.dumps(migrate(db,snapshot),indent=2))
            print('Import and full content verification: PASS. Runtime storage has not changed.')
        elif args.action=='verify':
            # Stable view across tables while another administration session might run.
            db.rollback()
            with db.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            preflight(db,safety=True)
            verify_snapshot(db,snapshot)
            compare_rows(db,build_rows(snapshot))
            print('All imported rows and preserved source snapshot match: PASS.')
        elif args.action=='undo-import':
            undo_import(db,snapshot)
            print('Oracle import undone. Original local data was not modified; source snapshot retained in Oracle.')
        elif args.action=='enable-oracle':
            require_stopped()
            lock_tables(db)
            verify_snapshot(db,snapshot)
            verify_runtime_baseline(db,snapshot)
            compare_rows(db,build_rows(snapshot))
            source={k:snapshot[k] for k in ('access','sqlite','instructions','source_files')}
            if digest(current_source())!=digest(source): raise ValueError('Local data changed since import. Do not switch to an outdated snapshot.')
            from oracle_recovery import configure
            configure('oracle',password or os.getenv('ORACLE_PASSWORD'))
            print('Oracle selected. Restart the backend, then verify /api/health/storage. Original local stores remain intact.')
        elif args.action=='export-local':
            require_stopped()
            from oracle_recovery import export_snapshot,materialize
            exported=materialize(export_snapshot(db),ROOT)
            print('Current Oracle data exported and preserved:',exported)
        else:
            require_stopped()
            from oracle_recovery import export_snapshot,recovery_fingerprint,restore_local
            lock_tables(db)
            fresh=export_snapshot(db,readonly=False)
            if recovery_fingerprint(fresh)!=recovery_fingerprint(snapshot):
                raise ValueError('Oracle changed after this export. Create a fresh export-local before reverting.')
            previous=restore_local(args.backup,ROOT)
            print('Newer Oracle data restored and verified. Local storage selected. Previous local backup:',previous)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Database exception text may include SQL/binds; do not expose credentials/content.
        if isinstance(error,(ValueError,FileNotFoundError)):
            print(str(error),file=sys.stderr)
        else:
            code=getattr(error.args[0],'full_code',None) if error.args else None
            print('Database operation did not finish ('+(code or type(error).__name__)+'). Keep the existing stores and backups. Review connection/service and schema installation locally before retrying.',file=sys.stderr)
        sys.exit(1)
