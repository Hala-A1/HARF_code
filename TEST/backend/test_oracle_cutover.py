"""Cutover orchestration failure paths; never stops a real process."""
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

import oracle_cutover as cutover


class Cursor:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self,sql): self.version="version_id='003'" in sql
    def fetchone(self): return (1 if self.version else 0,)


class Database:
    def cursor(self): return Cursor()
    def rollback(self): pass


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack(); self.addCleanup(self.stack.close)
        self.snapshot=dict(format_version=1,migration_id='fixture',captured_at='2026-10-18T12:00:00+00:00',
            access=dict(channels=[],users=[],approval_batches=[],notifications=[],activity=[]),sqlite={},instructions=[],source_files={})
        self.actions=[]
        self.maintenance=self.stack.enter_context(patch.object(cutover,'maintenance',side_effect=lambda action:self.actions.append(action) or {'was_running':True}))
        self.configure=self.stack.enter_context(patch.object(cutover,'configure'))
        self.stack.enter_context(patch('storage_backend.oracle_enabled',return_value=False))
        self.stack.enter_context(patch.object(cutover,'preflight'))
        self.probe=self.stack.enter_context(patch.object(cutover,'validate_runtime_sql'))
        self.stack.enter_context(patch.object(cutover,'create_backup',return_value=(Path('private-backup'),{})))
        self.stack.enter_context(patch.object(cutover,'load_backup',return_value=self.snapshot))
        self.migrate=self.stack.enter_context(patch.object(cutover,'migrate'))
        self.stack.enter_context(patch.object(cutover,'verify_snapshot'))
        self.verify_baseline=self.stack.enter_context(patch.object(cutover,'verify_runtime_baseline'))
        self.stack.enter_context(patch.object(cutover,'compare_rows'))
        self.stack.enter_context(patch.object(cutover,'lock_tables'))
        self.health=self.stack.enter_context(patch.object(cutover,'await_health'))

    def test_success_imports_before_switch_and_restarts(self):
        result=cutover.cutover(Database(),'local-test-password')
        self.assertIn('PASS',result)
        self.assertEqual(self.actions,['stop','start'])
        self.configure.assert_called_once_with('oracle','local-test-password')
        self.health.assert_called_once_with('oracle')

    def test_import_failure_restarts_original_backend_without_switch(self):
        self.migrate.side_effect=ValueError('import failed')
        with self.assertRaisesRegex(ValueError,'import failed'): cutover.cutover(Database(),'local-test-password')
        self.assertEqual(self.actions,['stop','start'])
        self.configure.assert_not_called()

    def test_health_failure_reverts_only_unchanged_data(self):
        self.health.side_effect=ValueError('health failed')
        with self.assertRaisesRegex(ValueError,'health failed'): cutover.cutover(Database(),'local-test-password')
        self.assertEqual(self.actions,['stop','start','stop','start'])
        self.assertEqual([c.args[0] for c in self.configure.call_args_list],['oracle','local'])
        self.verify_baseline.assert_called_once()

    def test_new_oracle_data_blocks_automatic_stale_fallback(self):
        self.health.side_effect=ValueError('health failed')
        self.verify_baseline.side_effect=ValueError('new data exists')
        with self.assertRaisesRegex(ValueError,'contains changes after activation'): cutover.cutover(Database(),'local-test-password')
        self.assertEqual(self.actions,['stop','start','stop'])
        self.configure.assert_called_once_with('oracle','local-test-password')

    def test_unrecognized_backend_process_stops_before_backup(self):
        self.maintenance.side_effect=ValueError('unrecognized service')
        with self.assertRaisesRegex(ValueError,'unrecognized service'): cutover.cutover(Database(),'local-test-password')
        self.migrate.assert_not_called()
        self.configure.assert_not_called()

    def test_live_sql_probe_failure_never_stops_backend_or_imports(self):
        self.probe.side_effect=ValueError('SQL validation failed')
        with self.assertRaisesRegex(ValueError,'SQL validation failed'): cutover.cutover(Database(),'local-test-password')
        self.maintenance.assert_not_called()
        self.migrate.assert_not_called()
        self.configure.assert_not_called()


if __name__=='__main__': unittest.main()
