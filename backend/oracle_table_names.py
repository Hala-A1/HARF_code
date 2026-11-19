"""One-time, backed-up table-prefix migration for the local Oracle application.

Oracle DDL commits immediately. A journal and original view definitions are
saved before the first rename; failures attempt compensating renames. Run with
the backend stopped. This tool never drops tables or replaces application data.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from oracle_mapping import canonical


SUFFIXES = (
    'SCHEMA_VERSIONS', 'CHANNELS', 'USERS', 'INSTRUCTIONS',
    'INSTRUCTION_VERSIONS', 'BATCHES', 'COPY_ITEMS', 'OUTPUTS',
    'COPY_VERSIONS', 'APPROVAL_EVENTS', 'LANGUAGE_APPROVALS',
    'NOTIFICATIONS', 'ACTIVITY', 'FEEDBACK', 'CHANNEL_LIMITS',
    'USER_LIMITS', 'REQUEST_USAGE', 'MIGRATION_SNAPSHOTS', 'RUNTIME_STATE',
)
RENAMES = {'RW_' + suffix: 'GENAI_RW_' + suffix for suffix in SUFFIXES}
_TABLE_TOKEN = re.compile(r'\b(?:' + '|'.join(RENAMES) + r')\b', re.I)


def rewrite_view(sql):
    """Replace complete table identifiers, preserving the public view names."""
    return _TABLE_TOKEN.sub(lambda match: RENAMES[match.group().upper()], sql)


def fingerprints(db, names):
    result = {}
    with db.cursor() as cursor:
        for name in names:
            if name not in {*RENAMES, *RENAMES.values()}:
                raise ValueError('Unexpected table name.')
            cursor.execute('SELECT * FROM ' + name)
            rows = []
            for row in cursor:
                values = []
                for value in row:
                    if hasattr(value, 'read'):
                        value = value.read()
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    values.append(value)
                rows.append(hashlib.sha256(canonical(values).encode('utf-8')).hexdigest())
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256(
                canonical(sorted(rows)).encode('utf-8')).hexdigest()}
    return result


def rename_tables(db, backup_directory):
    from oracle_migration import load_backup, require_stopped
    require_stopped()
    directory = Path(backup_directory).resolve()
    snapshot = load_backup(directory)
    if not snapshot['migration_id'].startswith('oracle-export-'):
        raise ValueError('A verified, current Oracle export is required.')
    with db.cursor() as cursor:
        cursor.execute('SELECT table_name FROM user_tables')
        actual = {row[0] for row in cursor}
        if not set(RENAMES) <= actual or set(RENAMES.values()) & actual:
            raise ValueError('Expected all 19 old tables and no renamed tables. No changes made.')
        cursor.execute('SELECT view_name,text FROM user_views')
        views = {name: sql for name, sql in cursor}
    # Confirm this backup still represents the live application, not stale local stores.
    from oracle_recovery import export_snapshot, recovery_fingerprint
    class OldCursor:
        def __init__(self, cursor): self.cursor = cursor
        def __enter__(self): return self
        def __exit__(self, *args): self.cursor.close()
        def __getattr__(self, name): return getattr(self.cursor, name)
        def __iter__(self): return iter(self.cursor)
        def execute(self, sql, *args, **kwargs):
            return self.cursor.execute(re.sub(r'\bGENAI_RW_', 'RW_', sql, flags=re.I), *args, **kwargs)

    class OldDatabase:
        def cursor(self): return OldCursor(db.cursor())
        def rollback(self): db.rollback()

    if recovery_fingerprint(export_snapshot(OldDatabase())) != recovery_fingerprint(snapshot):
        raise ValueError('Oracle data changed since this backup. Create a fresh export.')
    db.rollback()
    before = fingerprints(db, RENAMES)
    journal = dict(started_at=datetime.now(timezone.utc).isoformat(),
                   mapping=RENAMES, before=before, views=views, renamed=[], status='prepared')
    journal_path = directory / 'table-rename-journal.json'
    if journal_path.exists():
        raise ValueError('A rename journal already exists. Inspect it before retrying.')

    def record():
        journal_path.write_text(json.dumps(journal, indent=2), encoding='utf-8')

    record()
    completed = []
    try:
        with db.cursor() as cursor:
            for old, new in RENAMES.items():
                cursor.execute('ALTER TABLE ' + old + ' RENAME TO ' + new)
                completed.append((old, new))
                journal['renamed'].append(new)
                journal['status'] = 'renaming'
                record()
            for name, sql in views.items():
                if not re.fullmatch(r'RW_[A-Z0-9_]+', name):
                    raise ValueError('Unexpected view name.')
                cursor.execute('CREATE OR REPLACE VIEW ' + name + ' AS ' + rewrite_view(sql))
            after = fingerprints(db, RENAMES.values())
            if any(before[old] != after[new] for old, new in RENAMES.items()):
                raise ValueError('Table contents changed during the rename.')
            cursor.execute("SELECT object_name FROM user_objects WHERE status <> 'VALID'")
            if cursor.fetchall():
                raise ValueError('Invalid database objects remain after the rename.')
            cursor.execute("INSERT INTO GENAI_RW_SCHEMA_VERSIONS(version_id,description) VALUES ('004','Rename all application tables to GENAI_RW_; preserve data and view names')")
        db.commit()
        journal['status'] = 'completed'
        record()
    except BaseException:
        db.rollback()
        journal['status'] = 'compensating'
        record()
        try:
            with db.cursor() as cursor:
                for old, new in reversed(completed):
                    cursor.execute('ALTER TABLE ' + new + ' RENAME TO ' + old)
                for name, sql in views.items():
                    cursor.execute('CREATE OR REPLACE VIEW ' + name + ' AS ' + sql)
            journal['status'] = 'reverted'
        except BaseException:
            journal['status'] = 'manual_recovery_required'
            record()
            raise
        record()
        raise
    return journal_path


if __name__ == '__main__':
    import argparse
    from oracle_connection import connection
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True)
    arguments = parser.parse_args()
    with connection() as database:
        journal_file = rename_tables(database, arguments.backup)
    print('All 19 tables renamed; exact row contents verified. Journal:', journal_file)
