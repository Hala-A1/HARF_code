import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import access_control
from main import app


class LanguageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / 'access.json'
        data = copy.deepcopy(access_control.DEFAULT_DATA)
        for account in data['users']:
            if account['email'] == 'b2b.approver1@eand.ae':
                account['review_languages'] = ['en']
        data['users'].append({'email': 'arabic-reviewer@test.local', 'name': 'Arabic reviewer', 'role': 'approval_admin', 'channel_id': 'b2b', 'approval_layer': 1, 'review_languages': ['ar'], 'workspaces': ['rewrite']})
        path.write_text(json.dumps(data), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', path)
        self.patch.start()
        self.client = TestClient(app)
        self.owner = {'X-User-Email': 'b2b.user@eand.ae'}
        self.en = {'X-User-Email': 'b2b.approver1@eand.ae'}
        self.ar = {'X-User-Email': 'arabic-reviewer@test.local'}
        result = self.client.post('/api/approvals/draft', headers=self.owner, json={'team_channel': 'b2b', 'source': 'Original facts', 'english': 'English output', 'arabic': 'نسخة عربية', 'instructions': 'Keep it brief', 'task': 'write', 'content_channel': 'SMS', 'audience': 'Business'})
        self.assertEqual(result.status_code, 200, result.text)
        self.batch = result.json()
        self.url = '/api/approvals/' + self.batch['id']
        self.client.post(self.url + '/move', headers=self.owner, json={})

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_languages_gate_next_layer_and_preserve_context(self):
        denied = self.client.post(self.url + '/decision', headers=self.en, json={'action': 'approve', 'language': 'ar'})
        self.assertEqual(denied.status_code, 403)
        first = self.client.post(self.url + '/decision', headers=self.en, json={'action': 'approve'})
        self.assertEqual(first.json()['status'], 'pending_layer_1')
        self.assertEqual(first.json()['events'][-1]['languages'], ['en'])
        repeat = self.client.post(self.url + '/decision', headers=self.en, json={'action': 'approve'})
        self.assertEqual(repeat.status_code, 409)
        second = self.client.post(self.url + '/decision', headers=self.ar, json={'action': 'approve'})
        self.assertEqual(second.json()['status'], 'pending_layer_2')
        self.assertEqual(set(second.json()['language_approvals']['1']), {'en', 'ar'})
        self.assertEqual(second.json()['instructions'], 'Keep it brief')
        self.assertEqual(second.json()['items'][0]['source'], 'Original facts')
        self.assertEqual(second.json()['content_channel'], 'SMS')

    def test_return_and_resubmit_clear_language_approvals(self):
        self.client.post(self.url + '/decision', headers=self.en, json={'action': 'approve'})
        self.client.post(self.url + '/decision', headers=self.ar, json={'action': 'return_to_user', 'note': 'Correct Arabic'})
        submitted = self.client.post(self.url + '/move', headers=self.owner, json={})
        self.assertEqual(submitted.json()['language_approvals'], {})

    def test_assignment_requires_admin_and_layer(self):
        body = {'email': 'new@test.local', 'name': 'New reviewer', 'role': 'approval_admin', 'channel_id': 'b2b', 'review_languages': ['ar']}
        self.assertEqual(self.client.put('/api/access/assignments', headers=self.en, json=body).status_code, 403)
        admin = {'X-User-Email': 'b2b.admin@eand.ae'}
        self.assertEqual(self.client.put('/api/access/assignments', headers=admin, json=body).status_code, 422)
        response = self.client.put('/api/access/assignments', headers=admin, json={**body, 'approval_layer': 2})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['review_languages'], ['ar'])
        self.assertNotIn('password_hash', response.json())
        self.assertEqual(self.client.put('/api/access/assignments', headers=admin, json={**body, 'approval_layer': 2, 'channel_id': 'b2c'}).status_code, 403)
