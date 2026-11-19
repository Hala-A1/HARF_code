"""Local Windows cutover wizard. Credentials are entered before maintenance starts."""
import json
import os
import time
from urllib.request import urlopen

from oracle_mapping import build_rows
from oracle_migration import (ROOT,preflight,create_backup,load_backup,migrate,compare_rows,
                             verify_runtime_baseline,verify_snapshot,lock_tables)
from oracle_recovery import configure
from oracle_probe import validate_runtime_sql


def maintenance(action):
    if os.name!='nt': raise ValueError('This local wizard is for Windows. Use the documented administration commands on other hosts.')
    from backend_process import maintenance as manage_backend
    return manage_backend(action)


def await_health(mode):
    for _ in range(30):
        try:
            with urlopen('http://127.0.0.1:8000/api/health/storage',timeout=2) as response:
                data=json.loads(response.read())
                if data=={'status':'ok','storage':mode}: return
        except Exception: pass
        time.sleep(0.5)
    raise ValueError('The backend did not pass its storage health check.')


def cutover(db,password):
    from storage_backend import oracle_enabled
    if oracle_enabled(): raise ValueError('Oracle is already selected; this wizard will not repeat migration.')
    preflight(db,safety=True)
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM genai_harf_schema_versions WHERE version_id='003'")
        if cursor.fetchone()[0]!=1: raise ValueError('Run 04_runtime_storage.sql in SQL Developer as REWRITE_APP first.')
        cursor.execute('SELECT COUNT(*) FROM genai_harf_runtime_state')
        if cursor.fetchone()[0]: raise ValueError('Runtime data already exists. Use the guarded recovery/import procedure rather than overwriting it.')
    print('Checking actual Oracle SQL with fictional data; all check rows will be rolled back.')
    validate_runtime_sql(db)
    print('Oracle runtime SQL: PASS. Pausing the local backend for backup and migration.')
    stopped=False
    selected=False
    snapshot=None
    try:
        maintenance('stop'); stopped=True
        path,_=create_backup()
        print('Original data backup:',path)
        snapshot=load_backup(path)
        migrate(db,snapshot)
        verify_snapshot(db,snapshot)
        compare_rows(db,build_rows(snapshot))
        # Persist only after all data checks pass. The ignored local file contains a
        # database service password; deployment must use IT-managed secrets instead.
        configure('oracle',password); selected=True
        maintenance('start'); stopped=False
        await_health('oracle')
        return 'Oracle migration and runtime health check: PASS. Original local data remains in place. Backup: '+str(path)
    except BaseException:
        if selected:
            # Never revert to stale local data if any runtime writer reached Oracle.
            maintenance('stop'); stopped=True
            try:
                lock_tables(db)
                verify_snapshot(db,snapshot)
                verify_runtime_baseline(db,snapshot)
                compare_rows(db,build_rows(snapshot))
            except BaseException:
                raise ValueError('Oracle contains changes after activation. Backend kept stopped to protect data. Use export-local and restore-local; do not switch to stale local files.') from None
            finally:
                db.rollback()
            configure('local')
        if stopped:
            maintenance('start')
        raise
