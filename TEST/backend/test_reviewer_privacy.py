import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from main import app


class ReviewerPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'access.json'
        data = copy.deepcopy(access_control.DEFAULT_DATA)
        data['activity'] = [
            {'actor_email': 'b2b.user@eand.ae', 'actor': 'Other user', 'channel_id': 'b2b', 'action': 'Private generation', 'detail': 'Other user activity'},
            {'actor_email': 'b2c.user@eand.ae', 'actor': 'Other channel', 'channel_id': 'b2c', 'action': 'Private generation', 'detail': 'Other channel activity'},
        ]
        self.path.write_text(json.dumps(data), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', self.path)
        self.patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def headers(self, channel, role='approver1'):
        return {'X-User-Email': f'{channel}.{role}@eand.ae'}

    def test_reviewers_cannot_open_instruction_endpoints(self):
        for channel, module in [('b2b', 'B2B_SYSTEM'), ('b2c', 'B2C_SYSTEM'), ('security', 'SECURITY_POLICY')]:
            headers = self.headers(channel)
            base = f'/api/access/channels/{channel}'
            overview = self.client.get('/api/access/overview', headers=headers).json()
            self.assertEqual(overview['activity'], [])
            self.assertEqual([u['email'] for u in overview['users']], [headers['X-User-Email']])
            for suffix in ['/instructions', f'/instructions/{module}', '/prompt']:
                self.assertEqual(self.client.get(base + suffix, headers=headers).status_code, 403)
            for suffix, body in [('/retrieval-preview', {'query': 'memo'}), ('/refine-instructions', {'module_id': module, 'instructions': 'Read these rules'})]:
                self.assertEqual(self.client.post(base + suffix, headers=headers, json=body).status_code, 403)
            options = self.client.get(f'/api/output-options?team_channel={channel}', headers=headers)
            self.assertEqual(options.status_code, 200)
            self.assertTrue(options.json()['options'])
            self.assertTrue(all('instructions' not in x for x in options.json()['options']))

    def test_review_context_retained_without_private_rules_in_get_or_decision(self):
        owner = self.headers('b2b', 'user')
        with patch('approval.enhance_feedback', return_value='Generated copy'):
            result = self.client.post('/api/bulk/generate', headers=owner, json={'team_channel': 'b2b', 'items': [{'filename': 'brief.txt', 'text': 'Verified fictional facts'}], 'languages': ['en'], 'output_ids': ['component-4'], 'instructions': 'Keep the supplied price.'})
        self.assertEqual(result.status_code, 200, result.text)
        batch_id = result.json()['id']
        original_rules = result.json()['items'][0]['format_instructions']
        self.assertTrue(original_rules)
        self.client.post(f'/api/approvals/{batch_id}/move', headers=owner, json={})
        reviewer = self.headers('b2b')
        replies = [self.client.get(f'/api/approvals/{batch_id}', headers=reviewer),
                   self.client.get('/api/approvals?channel_id=b2b', headers=reviewer),
                   self.client.post(f'/api/approvals/{batch_id}/decision', headers=reviewer, json={'action': 'note', 'note': 'Please check the date.'})]
        for response in replies:
            self.assertEqual(response.status_code, 200, response.text)
            batch = response.json().get('batches', [response.json()])[0]
            item = batch['items'][0]
            self.assertNotIn('format_instructions', item)
            self.assertEqual(item['generation_instructions'], 'Keep the supplied price.')
            self.assertEqual(item['source'], 'Verified fictional facts')
            self.assertEqual(item['generated']['en'], 'Generated copy')
        saved = next(b for b in access_control.load_access_data()['approval_batches'] if b['id'] == batch_id)
        self.assertEqual(saved['items'][0]['format_instructions'], original_rules)
        admin_view = self.client.get(f'/api/approvals/{batch_id}', headers=self.headers('b2b', 'admin')).json()
        self.assertEqual(admin_view['items'][0]['format_instructions'], original_rules)

    def test_admins_retain_scoped_activity_and_instructions(self):
        view = self.client.get('/api/access/overview', headers=self.headers('b2b', 'admin')).json()
        self.assertEqual(len(view['activity']), 1)
        self.assertEqual(view['activity'][0]['channel_id'], 'b2b')
        response = self.client.get('/api/access/channels/b2b/instructions', headers=self.headers('b2b', 'admin'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['instructions']), 3)

    def test_reviewer_quality_summary_does_not_disclose_rule_quotes(self):
        assessment = {'score': 90, 'checks': [{'rule': 'Accuracy', 'status': 'met', 'references': [{'rule_quote': 'PRIVATE RULE', 'filename': 'system.md'}]}], 'files': [{'filename': 'system.md'}]}
        with patch('copywriter.analyze_copy', return_value=copy.deepcopy(assessment)):
            response = self.client.post('/api/analyze', headers=self.headers('b2b'), json={'generated': 'Copy', 'original': 'Facts', 'team_channel': 'b2b'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['score'], 90)
        self.assertNotIn('PRIVATE RULE', response.text)
        self.assertEqual(response.json()['files'], [])


if __name__ == '__main__':
    unittest.main()
