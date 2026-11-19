from pathlib import Path
import tempfile
import unittest
from dotenv import dotenv_values
from environment import updated_content
from platform_policy import write_settings


class EnvironmentTests(unittest.TestCase):
    def test_admin_policy_write_preserves_credentials_and_other_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("# Keep this comment\nORACLE_PASSWORD='fictional-password'\nLLM_REQUESTS_PER_MINUTE=50\nAUTH_PROVIDER=ldap\n", encoding='utf-8')
            write_settings(path, {'retention_days': 180, 'default_max_input_tokens': 64000,
                                  'model_input_token_limits': {'cloud:fictional': 90000}})
            actual = dotenv_values(path)
            self.assertEqual(actual['ORACLE_PASSWORD'], 'fictional-password')
            self.assertEqual(actual['LLM_REQUESTS_PER_MINUTE'], '50')
            self.assertEqual(actual['AUTH_PROVIDER'], 'ldap')
            self.assertEqual(actual['USER_LOG_RETENTION_DAYS'], '180')
            self.assertIn('# Keep this comment', path.read_text(encoding='utf-8'))

    def test_selected_updates_round_trip_quotes_slashes_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('KEEP=original\nCHANGE=old\nCHANGE=older\n', encoding='utf-8')
            values = {'CHANGE': "HOENG\\srv'example", 'NEW': '{"test": 50}'}
            path.write_text(updated_content(path, values), encoding='utf-8')
            actual = dotenv_values(path)
            self.assertEqual(actual['KEEP'], 'original')
            self.assertEqual(actual['CHANGE'], values['CHANGE'])
            self.assertEqual(actual['NEW'], values['NEW'])
            self.assertEqual(path.read_text(encoding='utf-8').count('CHANGE='), 1)
