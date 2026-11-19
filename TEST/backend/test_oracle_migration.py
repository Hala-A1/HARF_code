"""Migration safety tests use disposable files and a transaction-capable DB double.

These do not claim live Oracle compatibility; live verification requires the local
REWRITE_APP password and schema 002.
"""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import oracle_migration as migration
from oracle_mapping import build_rows,canonical,digest,timestamp,TABLES
from oracle_connection import settings

NOW='2026-10-18T12:00:00+00:00'


def fixture(root):
    backend=root/'backend'
    backend.mkdir()
    prompt=root/'instructions/channels/b2c'
    prompt.mkdir(parents=True)
    (prompt/'01_B2C_SYSTEM_INSTRUCTIONS.md').write_text('Keep facts. العربية سليمة.',encoding='utf-8')
    access=dict(channels=[dict(id='b2c',name='B2C')],
                users=[dict(email='test@example.test',name='Test',role='user',channel_id='b2c')],
                activity=[],notifications=[],approval_batches=[dict(id='batch1',channel_id='b2c',title='Test offer',
                status='draft',languages=['en','ar'],urgent=False,current_layer=0,progress=0,
                created_by_email='test@example.test',created_by='Test',created_at=NOW,updated_at=NOW,
                items=[dict(id='item1',source='AED 100',generated={'en':'AED 100','ar':'100 درهم'},
                            generated_details={'en':{'score':92}},versions=[])],events=[])])
    (backend/'access-control.json').write_text(json.dumps(access,ensure_ascii=False),encoding='utf-8')
    with closing(sqlite3.connect(backend/'request-limits.sqlite3')) as db:
        db.execute('CREATE TABLE channel_limits(channel TEXT PRIMARY KEY,monthly_limit INTEGER)')
        db.execute("INSERT INTO channel_limits VALUES('b2c',100)")
        db.commit()
    source=migration.current_source(root)
    return dict(format_version=1,migration_id='fixture',captured_at=NOW,**source)


class Cursor:
    def __init__(self,db):
        self.db=db
        self.cursor=db.sqlite.cursor()
    def __enter__(self): return self
    def __exit__(self,*args): self.cursor.close()
    def setinputsizes(self,**kwargs): pass
    def execute(self,sql,parameters=None,**kwargs):
        if sql.startswith('LOCK TABLE '): return self
        if sql.startswith('SELECT version_id FROM genai_harf_schema_versions'):
            self.cursor.execute("SELECT '001' UNION ALL SELECT '002' UNION ALL SELECT '003'"); return self
        if sql.startswith("SELECT COUNT(*) FROM genai_harf_schema_versions WHERE version_id='003'"):
            self.cursor.execute('SELECT 1'); return self
        if 'FROM nls_database_parameters' in sql:
            self.cursor.execute("SELECT 'AL32UTF8'"); return self
        if 'FROM user_objects' in sql:
            self.cursor.execute('SELECT 0'); return self
        sql=re.sub(r"TO_TIMESTAMP_TZ\((:\w+), '[^']*'\)",r'\1',sql)
        sql=re.sub(r"TO_CHAR\((\w+), '[^']*'\)",r'\1',sql)
        sql=sql.replace('SYSTIMESTAMP',"'2026-10-18T12:00:00+00:00'")
        self.cursor.execute(sql,parameters if parameters is not None else kwargs)
        return self
    def fetchone(self): return self.cursor.fetchone()
    def __iter__(self): return iter(self.cursor)


class Database:
    def __init__(self,rows):
        self.sqlite=sqlite3.connect(':memory:')
        for table,records in rows.items():
            if records:
                self.sqlite.execute('CREATE TABLE '+table+' ('+','.join('"'+k+'"' for k in records[0])+')')
            else:
                self.sqlite.execute('CREATE TABLE '+table+' (unused)')
        self.sqlite.execute('CREATE TABLE genai_harf_migration_snapshots(migration_id,snapshot_sha256,snapshot_json,migration_status,rolled_back_at)')
        self.sqlite.execute('CREATE TABLE genai_harf_runtime_state(state_id,revision,migration_id,baseline_at,access_json,updated_at)')
        self.commits=0
    def cursor(self): return Cursor(self)
    def commit(self): self.sqlite.commit(); self.commits+=1
    def rollback(self): self.sqlite.rollback()


class MigrationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.snapshot=fixture(self.root)
        self.rows=build_rows(self.snapshot)
        self.db=Database(self.rows)
        self.addCleanup(self.db.sqlite.close)

    def migrate(self):
        with patch.object(migration,'require_stopped'):
            return migration.migrate(self.db,self.snapshot,self.root)

    def test_bilingual_full_text_round_trip_and_safe_undo(self):
        original=(self.root/'backend/access-control.json').read_bytes()
        self.migrate()
        migration.compare_rows(self.db,self.rows)
        migration.verify_snapshot(self.db,self.snapshot)
        arabic=self.db.sqlite.execute("SELECT output_text FROM genai_harf_outputs WHERE language_code='ar'").fetchone()[0]
        self.assertEqual(arabic,'100 درهم')
        migration.undo_import(self.db,self.snapshot)
        for table in TABLES:
            self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
        self.assertEqual(self.db.sqlite.execute('SELECT migration_status FROM genai_harf_migration_snapshots').fetchone()[0],'rolled_back')
        self.assertEqual(original,(self.root/'backend/access-control.json').read_bytes())

    def test_undo_refuses_modified_outputs(self):
        self.migrate()
        self.db.sqlite.execute("UPDATE genai_harf_outputs SET output_text='Changed after import' WHERE language_code='en'")
        self.db.sqlite.commit()
        commits=self.db.commits
        with self.assertRaisesRegex(ValueError,'verification failed'):
            migration.undo_import(self.db,self.snapshot)
        self.assertEqual(self.db.commits,commits)
        self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM genai_harf_channels').fetchone()[0],1)

    def test_import_refuses_occupied_tables(self):
        self.migrate()
        with self.assertRaisesRegex(ValueError,'Runtime state already exists'):
            self.migrate()
        self.assertEqual(self.db.commits,1)

    def test_insert_failure_rolls_back_every_table(self):
        actual=migration.insert_rows
        def fail(db,table,records):
            if table=='genai_harf_outputs': raise RuntimeError('simulated failure')
            actual(db,table,records)
        with patch.object(migration,'insert_rows',side_effect=fail),self.assertRaises(RuntimeError):
            self.migrate()
        self.assertEqual(self.db.commits,0)
        for table in TABLES:
            self.assertEqual(self.db.sqlite.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)

    def test_stale_backup_rejected_before_inserts(self):
        path=self.root/'backend/access-control.json'
        data=json.loads(path.read_text(encoding='utf-8')); data['users'][0]['name']='Later update'
        path.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'differs from this backup'):
            self.migrate()
        self.assertEqual(self.db.commits,0)

    def test_backup_and_tampering_detection(self):
        with patch.dict('os.environ',{'INSTRUCTION_VERSIONS_DB':''}):
            directory,manifest=migration.create_backup(self.root,require_stop=False)
        restored=migration.load_backup(directory)
        self.assertEqual(restored['access'],self.snapshot['access'])
        self.assertEqual(manifest['row_counts']['genai_harf_outputs'],2)
        (directory/'backend/access-control.json').write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'integrity check failed'):
            migration.load_backup(directory)

    def test_empty_target_still_rejects_unexpected_added_rows(self):
        self.migrate()
        self.db.sqlite.execute("INSERT INTO genai_harf_activity VALUES('new activity')")
        self.db.sqlite.commit()
        with self.assertRaisesRegex(ValueError,'Unexpected rows'):
            migration.undo_import(self.db,self.snapshot)

    def test_no_silent_truncation_or_orphan_dropping(self):
        bad=deepcopy(self.snapshot); bad['access']['users'][0]['name']='x'*241
        with self.assertRaisesRegex(ValueError,'Nothing was shortened'):
            build_rows(bad)
        bad=deepcopy(self.snapshot); bad['access']['users'][0]['channel_id']='missing'
        with self.assertRaisesRegex(ValueError,'Orphaned'):
            build_rows(bad)

    def test_complete_unknown_details_preserved(self):
        snapshot=deepcopy(self.snapshot)
        snapshot['access']['approval_batches'][0]['future_feature']={'new':'سياق'}
        row=build_rows(snapshot)['genai_harf_batches'][0]
        self.assertEqual(json.loads(row['payload_json'])['future_feature'],{'new':'سياق'})
        self.assertNotEqual(digest(snapshot),digest(self.snapshot))

    def test_current_instruction_has_baseline_history(self):
        self.assertEqual(len(self.rows['genai_harf_instruction_versions']),1)
        self.assertEqual(self.rows['genai_harf_instructions'][0]['content_md'],self.rows['genai_harf_instruction_versions'][0]['content_md'])
        self.assertEqual(self.rows['genai_harf_instructions'][0]['current_version'],1)

    def test_system_connection_rejected_without_password(self):
        with patch.dict('os.environ',{'ORACLE_USER':'SYSTEM'}):
            with self.assertRaisesRegex(ValueError,'never SYSTEM'):
                settings('not-a-real-password')

    def test_dates_require_timezone_and_preserve_instant(self):
        self.assertEqual(timestamp('2026-10-18T16:00:00+04:00'),'2026-10-18T16:00:00.000000+04:00')
        with self.assertRaisesRegex(ValueError,'timezone'):
            timestamp('2026-10-18T16:00:00')
        self.assertTrue(timestamp(0).endswith('+00:00'))


if __name__=='__main__': unittest.main()
