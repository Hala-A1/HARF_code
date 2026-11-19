import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

from fastapi.testclient import TestClient
import access_control
from main import app
from bulk_limits import channel_bulk_limit
from spreadsheet_import import import_messages


class BulkLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp.name) / 'access-control.json'
        self.data_file.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.data_patch = patch.object(access_control, 'DATA_FILE', self.data_file)
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(app)

    def headers(self, email='b2c.admin@eand.ae'):
        return {'X-User-Email': email}

    def update(self, limit, channel='b2c', email='b2c.admin@eand.ae'):
        return self.client.put(f'/api/access/channels/{channel}/bulk-limit', json={'limit': limit}, headers=self.headers(email))

    def test_permissions_defaults_strict_bounds_and_persistence(self):
        self.assertEqual(channel_bulk_limit({}), 20)
        self.assertEqual(self.update(30).json()['limit'], 30)
        self.assertEqual(self.client.get('/api/access/channels/b2c/bulk-limit', headers=self.headers('b2c.user@eand.ae')).json()['limit'], 30)
        self.assertEqual(self.update(5, email='b2c.user@eand.ae').status_code, 403)
        self.assertEqual(self.update(5, channel='b2b').status_code, 403)
        self.assertEqual(self.update(5, channel='b2b', email='developer@eand.ae').status_code, 200)
        for value in [0, 101, True, 1.5, '30']:
            self.assertEqual(self.update(value).status_code, 422)
        saved = json.loads(self.data_file.read_text(encoding='utf-8'))
        self.assertEqual(next(c for c in saved['channels'] if c['id'] == 'b2c')['bulk_file_limit'], 30)
        self.assertTrue(any(e['action'] == 'Bulk limit updated' for e in saved['activity']))

    @patch('approval.review_component_sets', return_value=[])
    @patch('approval.enhance_feedback', return_value='Generated copy')
    def test_more_than_twenty_and_reduced_limit_enforced_before_ai(self, generate, review):
        self.update(30)
        payload = {'items': [{'filename': f'{n}.txt', 'text': 'Draft'} for n in range(21)], 'team_channel': 'b2c', 'languages': ['en']}
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['items']), 21)
        generate.reset_mock()
        self.update(2)
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 422, response.text)
        generate.assert_not_called()
        self.assertEqual(len(self.client.get('/api/approvals', headers=self.headers()).json()['batches']), 1)

    @patch('approval.enhance_bilingual_feedback', return_value={'english': 'Hello', 'arabic': 'مرحبا'})
    @patch('approval.review_component_sets', return_value=[])
    def test_formats_share_capacity_both_languages_do_not_double_it(self, review, generate):
        self.update(1)
        payload = {'items': [{'filename': 'brief.txt', 'text': 'Draft'}], 'team_channel': 'b2c', 'languages': ['en', 'ar'], 'output_ids': ['b2c-sms-001', 'b2c-email-001']}
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 422, response.text)
        generate.assert_not_called()
        payload['output_ids'] = ['b2c-sms-001']
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()['items'][0]['generated']), {'en', 'ar'})

    def test_spreadsheet_preview_respects_current_channel_limit(self):
        csv = b'REPLY_MESSAGE\n' + b'Copy\n' * 30
        self.assertEqual(len(import_messages('messages.csv', csv, limit=30)['rows']), 30)
        self.update(3)
        response = self.client.post('/api/import-spreadsheet', headers=self.headers('b2c.user@eand.ae'),
                                    data={'team_channel': 'b2c', 'limit': '4'}, files={'file': ('messages.csv', BytesIO(csv), 'text/csv')})
        self.assertEqual(response.status_code, 422)
        self.assertIn('3', response.json()['detail'])

    def test_performance_api_scope_and_period_validation(self):
        for email, channel, status in [('b2c.admin@eand.ae', 'b2c', 200), ('b2c.admin@eand.ae', 'b2b', 403),
                                       ('b2c.approver1@eand.ae', 'b2c', 403), ('b2c.user@eand.ae', 'b2c', 403),
                                       ('developer@eand.ae', 'b2b', 200)]:
            response = self.client.get(f'/api/access/channels/{channel}/performance?days=7', headers=self.headers(email))
            self.assertEqual(response.status_code, status, response.text)
            if email == 'developer@eand.ae':
                self.assertNotIn('approvals', response.json())
        self.assertEqual(self.client.get('/api/access/channels/b2c/performance?days=3', headers=self.headers()).status_code, 422)

    def test_large_bilingual_export_supported(self):
        response = self.client.post('/api/export/xlsx', headers=self.headers('b2c.user@eand.ae'), json={
            'include_source': True, 'sections': [{'text': f'Output {n}', 'source_text': 'Input', 'language': 'en' if n % 2 else 'ar'} for n in range(200)]})
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else '')
