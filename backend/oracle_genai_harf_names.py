"""Backed-up GENAI_HARF table rename with compatibility views and compensating DDL.

Run only with the backend stopped. No table is dropped, copied or recreated.
The application schema/account and existing RW_ public views remain unchanged.
"""
from datetime import datetime, timezone
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import re

from oracle_mapping import canonical
from oracle_table_names import SUFFIXES

RENAMES = {'HARF_' + suffix: 'GENAI_HARF_' + suffix for suffix in SUFFIXES}
TOKEN = re.compile(r'\b(?:' + '|'.join(RENAMES) + r')\b', re.I)


def update_view(sql):
    return TOKEN.sub(lambda match: RENAMES[match.group().upper()], sql)


class SourceDatabase:
    """Read new runtime SQL against old tables while making the source backup."""
    def __init__(self, db): self.db = db
    def rollback(self): self.db.rollback()
    def cursor(self):
        base = self.db.cursor()
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): base.close()
            def __getattr__(self, name): return getattr(base, name)
            def __iter__(self): return iter(base)
            def execute(self, sql, *args, **kwargs):
                return base.execute(re.sub(r'\bGENAI_HARF_', 'HARF_', sql, flags=re.I), *args, **kwargs)
        return Cursor()


def fingerprints(db, names):
    result = {}
    with db.cursor() as cursor:
        for name in names:
            if name not in {*RENAMES, *RENAMES.values()}:
                raise ValueError('Unexpected application table.')
            cursor.execute('SELECT * FROM ' + name)
            hashes = []
            for row in cursor:
                values = [value.read() if hasattr(value, 'read') else value.isoformat() if isinstance(value, datetime) else value for value in row]
                hashes.append(hashlib.sha256(canonical(values).encode('utf8')).hexdigest())
            result[name] = {'rows': len(hashes), 'sha256': hashlib.sha256(canonical(sorted(hashes)).encode('utf8')).hexdigest()}
    return result


def preflight(db):
    with db.cursor() as cursor:
        cursor.execute('SELECT table_name FROM user_tables')
        tables = {row[0] for row in cursor}
        cursor.execute('SELECT object_name FROM user_objects')
        objects = {row[0] for row in cursor}
        if not set(RENAMES) <= tables or set(RENAMES.values()) & objects:
            raise ValueError('Expected 19 HARF_ tables and no GENAI_HARF_ object collisions. No changes made.')
        cursor.execute("SELECT object_name FROM user_objects WHERE status<>'VALID'")
        if cursor.fetchall(): raise ValueError('Resolve invalid database objects before renaming.')
        cursor.execute('SELECT name,type,referenced_name FROM user_dependencies')
        if any(kind != 'VIEW' and target in RENAMES for _, kind, target in cursor):
            raise ValueError('Non-view dependencies require DBA review. No changes made.')
        cursor.execute('SELECT table_name,grantee FROM user_tab_privs WHERE owner=USER')
        if any(table in RENAMES for table, _ in cursor):
            raise ValueError('External grants require DBA review. No changes made.')
        cursor.execute('SELECT privilege FROM session_privs')
        if 'CREATE VIEW' not in {row[0] for row in cursor}:
            raise ValueError('CREATE VIEW is required to preserve old table references.')
        cursor.execute('SELECT view_name,text FROM user_views')
        views = {name: sql.read() if hasattr(sql, 'read') else sql for name, sql in cursor}
        if any(not re.fullmatch(r'RW_[A-Z0-9_]+', name) and name not in {'GENAI_RW_' + suffix for suffix in SUFFIXES} for name in views):
            raise ValueError('Unexpected views require review before migration.')
    return views


def rename_tables(db, root):
    from oracle_migration import require_stopped, load_backup
    from oracle_recovery import export_snapshot, materialize, recovery_fingerprint
    from instruction_versions import _atomic_write
    require_stopped()
    views = preflight(db)
    source = SourceDatabase(db)
    snapshot = export_snapshot(source)
    backup = materialize(snapshot, Path(root))
    verified = load_backup(backup)
    if recovery_fingerprint(verified) != recovery_fingerprint(export_snapshot(source)):
        raise ValueError('Source changed or backup did not verify. No DDL performed.')
    db.rollback()
    before = fingerprints(db, RENAMES)
    journal = {'started_at': datetime.now(timezone.utc).isoformat(), 'mapping': RENAMES,
               'before': before, 'views': views, 'renamed': [], 'aliases': [], 'status': 'prepared'}
    path = backup / 'genai-harf-table-rename-journal.json'
    def record(): _atomic_write(path, json.dumps(journal, indent=2))
    record()
    try:
        with db.cursor() as cursor:
            for old, new in RENAMES.items():
                cursor.execute('ALTER TABLE ' + old + ' RENAME TO ' + new)
                journal['renamed'].append(old); journal['status'] = 'renaming'; record()
            for name, sql in views.items():
                cursor.execute('CREATE OR REPLACE VIEW ' + name + ' AS ' + update_view(sql))
            for old, new in RENAMES.items():
                cursor.execute('CREATE VIEW ' + old + ' AS SELECT * FROM ' + new)
                journal['aliases'].append(old); record()
            after = fingerprints(db, RENAMES.values())
            if any(before[old] != after[new] for old, new in RENAMES.items()):
                raise ValueError('Table contents did not match after rename.')
            cursor.execute("SELECT object_name FROM user_objects WHERE status<>'VALID'")
            if cursor.fetchall(): raise ValueError('Invalid objects remain after rebuilding views.')
            cursor.execute("INSERT INTO GENAI_HARF_SCHEMA_VERSIONS(version_id,description) VALUES ('006','Rename application tables to GENAI_HARF_; preserve data, owner and compatibility views')")
        db.commit()
        journal['status'] = 'completed'; journal['after'] = after; record()
        return backup
    except BaseException as error:
        journal['status'] = 'compensating'
        journal['failure_type'] = type(error).__name__
        record()
        recovery = nullcontext(db)
        try:
            db.rollback()
        except Exception:
            # A broken driver connection must not prevent compensating DDL.
            from oracle_connection import connection
            recovery = connection()
        try:
            with recovery as recovery_db, recovery_db.cursor() as cursor:
                for old in reversed(journal['aliases']): cursor.execute('DROP VIEW ' + old)
                for old in reversed(journal['renamed']): cursor.execute('ALTER TABLE ' + RENAMES[old] + ' RENAME TO ' + old)
                for name, sql in views.items(): cursor.execute('CREATE OR REPLACE VIEW ' + name + ' AS ' + sql)
            journal['status'] = 'reverted'; record()
        except BaseException:
            journal['status'] = 'manual_recovery_required'; record()
            raise
        raise
