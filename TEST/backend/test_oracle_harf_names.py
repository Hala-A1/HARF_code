import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from oracle_harf_names import RENAMES, rename_tables, preflight, update_view


class Database:
    def __init__(self, fail=''):
        self.tables={name:[('unchanged content',1)] for name in RENAMES}
        self.views={'RW_APPROVAL_QUEUE':'SELECT * FROM GENAI_RW_BATCHES'}
        self.sql=[];self.fail=fail;self.invalid=[];self.dependencies=[];self.grants=[];self.privileges=[('CREATE VIEW',)]
    def rollback(self):pass  # DDL is deliberately not rolled back automatically.
    def commit(self):pass
    def cursor(self):
        db=self
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __iter__(self):return iter(self.rows)
            def fetchall(self):return self.rows
            def execute(self,sql,*args,**kwargs):
                db.sql.append(sql);self.rows=[]
                if db.fail and sql.startswith(db.fail):
                    db.fail='';raise RuntimeError('Injected DDL failure')
                if sql=='SELECT table_name FROM user_tables':self.rows=[(name,) for name in db.tables]
                elif sql=='SELECT object_name FROM user_objects':self.rows=[(name,) for name in {*db.tables,*db.views}]
                elif "status<>'VALID'" in sql:self.rows=db.invalid
                elif sql=='SELECT name,type,referenced_name FROM user_dependencies':self.rows=db.dependencies
                elif sql.startswith('SELECT table_name,grantee'):self.rows=db.grants
                elif sql=='SELECT privilege FROM session_privs':self.rows=db.privileges
                elif sql=='SELECT view_name,text FROM user_views':self.rows=list(db.views.items())
                elif sql.startswith('SELECT * FROM '):self.rows=db.tables[sql.split()[-1]]
                elif sql.startswith('ALTER TABLE '):
                    _,_,old,_,_,new=sql.split();db.tables[new]=db.tables.pop(old)
                elif sql.startswith('CREATE OR REPLACE VIEW '):
                    name,definition=sql.removeprefix('CREATE OR REPLACE VIEW ').split(' AS ',1);db.views[name]=definition
                elif sql.startswith('CREATE VIEW '):
                    name,definition=sql.removeprefix('CREATE VIEW ').split(' AS ',1);db.views[name]=definition
                elif sql.startswith('DROP VIEW '):db.views.pop(sql.split()[-1])
                elif sql.startswith('INSERT INTO HARF_SCHEMA_VERSIONS'):db.tables['HARF_SCHEMA_VERSIONS'].append(('005','migration marker'))
                else:raise AssertionError(sql)
                return self
        return Cursor()


class HarfRenameTests(unittest.TestCase):
    def run_migration(self,db):
        with tempfile.TemporaryDirectory() as temporary:
            backup=Path(temporary)/'verified-backup';backup.mkdir()
            snapshot={'format_version':1,'migration_id':'oracle-export-fictional','marker':'verified'}
            with patch('oracle_migration.require_stopped'),patch('oracle_recovery.export_snapshot',return_value=snapshot),patch('oracle_recovery.materialize',return_value=backup),patch('oracle_migration.load_backup',return_value=snapshot),patch('oracle_recovery.recovery_fingerprint',side_effect=lambda value:value['marker']):
                try:
                    rename_tables(db,Path(temporary))
                except RuntimeError:
                    self.assertEqual(json.loads((backup/'harf-table-rename-journal.json').read_text())['status'],'reverted')
                    raise
                return json.loads((backup/'harf-table-rename-journal.json').read_text())

    def test_success_preserves_rows_and_view_names_and_adds_old_name_compatibility(self):
        db=Database();journal=self.run_migration(db)
        self.assertEqual(set(db.tables),set(RENAMES.values()))
        self.assertEqual(journal['status'],'completed')
        self.assertEqual(len(journal['aliases']),19)
        self.assertEqual(db.views['RW_APPROVAL_QUEUE'],'SELECT * FROM HARF_BATCHES')
        for old,new in RENAMES.items():
            self.assertEqual(db.views[old],'SELECT * FROM '+new)
            self.assertEqual(journal['before'][old],journal['after'][new])
        self.assertFalse(any(sql.startswith('DROP TABLE') for sql in db.sql))

    def test_mid_rename_and_compatibility_view_failures_restore_old_schema(self):
        for fail in ['ALTER TABLE GENAI_RW_OUTPUTS','CREATE VIEW GENAI_RW_USERS']:
            db=Database(fail)
            with self.assertRaises(RuntimeError):self.run_migration(db)
            self.assertEqual(set(db.tables),set(RENAMES))
            self.assertEqual(db.views,{'RW_APPROVAL_QUEUE':'SELECT * FROM GENAI_RW_BATCHES'})

    def test_preflight_refuses_unsafe_conditions_without_ddl(self):
        cases=[lambda db:db.tables.update(HARF_USERS=[]),lambda db:setattr(db,'invalid',[('BROKEN',)]),
               lambda db:setattr(db,'dependencies',[('CUSTOM','PROCEDURE','GENAI_RW_USERS')]),
               lambda db:setattr(db,'grants',[('GENAI_RW_USERS','EXTERNAL')]),lambda db:setattr(db,'privileges',[])]
        for alter in cases:
            db=Database();alter(db)
            with self.assertRaises(ValueError):preflight(db)
            self.assertFalse(any(sql.startswith(('ALTER ','CREATE ','DROP ')) for sql in db.sql))

    def test_view_replacement_targets_complete_identifiers_only(self):
        self.assertEqual(update_view('SELECT * FROM genai_rw_users JOIN GENAI_RW_USER_LIMITS ON 1=1'), 'SELECT * FROM HARF_USERS JOIN HARF_USER_LIMITS ON 1=1')
        self.assertEqual(update_view('SELECT GENAI_RW_USERS_EXTRA FROM dual'),'SELECT GENAI_RW_USERS_EXTRA FROM dual')


if __name__=='__main__':unittest.main()
