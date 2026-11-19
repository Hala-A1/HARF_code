import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import access_control
from main import app


class ApprovalRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'access-control.json'
        data = copy.deepcopy(access_control.DEFAULT_DATA)
        data['users'].append({'email': 'second.reviewer@example.test', 'name': 'Second reviewer', 'role': 'approval_admin',
                              'approval_layer': 1, 'channel_id': 'b2c', 'review_languages': ['en', 'ar'], 'workspaces': ['rewrite']})
        self.path.write_text(json.dumps(data), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(app)

    def headers(self, email='b2c.admin@eand.ae'):
        return {'X-User-Email': email}

    def policy(self, layer, email='b2c.admin@eand.ae', channel='b2c'):
        return self.client.put(f'/api/access/channels/{channel}/approval-policy', headers=self.headers(email), json={'final_approval_layer': layer})

    def draft(self, both=False):
        response = self.client.post('/api/approvals/draft', headers=self.headers('b2c.user@eand.ae'),
                                    json={'team_channel': 'b2c', 'source': 'Brief', 'english': 'Copy', 'arabic': 'النص' if both else ''})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['id']

    def move(self, batch):
        response = self.client.post(f'/api/approvals/{batch}/move', headers=self.headers('b2c.user@eand.ae'), json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def decide(self, batch, layer=1, email=None, **extra):
        return self.client.post(f'/api/approvals/{batch}/decision', headers=self.headers(email or f'b2c.approver{layer}@eand.ae'),
                                json={'action': 'approve', 'expected_layer': layer, **extra})

    def test_multiple_reviewers_notified_first_approval_advances_only_once(self):
        batch = self.draft()
        self.move(batch)
        for email in ['b2c.approver1@eand.ae', 'second.reviewer@example.test']:
            notes = self.client.get('/api/notifications', headers=self.headers(email)).json()['notifications']
            self.assertTrue(any(n['batch_id'] == batch and n['kind'] == 'approval_request' for n in notes))
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda email: self.decide(batch, email=email), ['b2c.approver1@eand.ae', 'second.reviewer@example.test']))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        result = self.client.get(f'/api/approvals/{batch}', headers=self.headers()).json()
        self.assertEqual(result['current_layer'], 2)
        self.assertEqual(sum(e['action'] == 'approved' for e in result['events']), 1)
        self.assertEqual(len(result['language_approvals']['1']), 1)

    def test_layer_two_final_notifies_author_without_requesting_layer_three(self):
        self.assertEqual(self.policy(2).status_code, 200)
        batch = self.draft()
        self.assertEqual(self.move(batch)['final_approval_layer'], 2)
        first = self.decide(batch)
        self.assertEqual(first.json()['progress'], 50)
        final = self.decide(batch, 2)
        self.assertEqual(final.status_code, 200, final.text)
        self.assertEqual(final.json()['status'], 'approved')
        self.assertEqual(final.json()['current_layer'], 2)
        self.assertEqual(final.json()['progress'], 100)
        self.assertTrue(final.json()['completed_at'])
        notes = self.client.get('/api/notifications', headers=self.headers('b2c.user@eand.ae')).json()['notifications']
        self.assertTrue(any(n['kind'] == 'final_approval' and 'all 2 required' in n['message'] for n in notes))
        layer_three = self.client.get('/api/notifications', headers=self.headers('b2c.approver3@eand.ae')).json()['notifications']
        self.assertFalse(any(n['kind'] == 'approval_request' and n['batch_id'] == batch for n in layer_three))

    def test_one_layer_final_and_bilingual_review_requires_both_languages(self):
        self.policy(1)
        batch = self.draft(both=True)
        self.move(batch)
        en = self.decide(batch, language='en')
        self.assertEqual(en.json()['status'], 'pending_layer_1')
        ar = self.decide(batch, email='second.reviewer@example.test', language='ar')
        self.assertEqual(ar.json()['status'], 'approved')
        self.assertEqual(ar.json()['current_layer'], 1)

    def test_regulatory_compliance_can_finish_at_layer_two(self):
        self.assertEqual(self.policy(2, 'security.admin@eand.ae', 'security').status_code, 200)
        result = self.client.post('/api/approvals/draft', headers=self.headers('security.user@eand.ae'),
                                  json={'team_channel': 'security', 'source': 'Policy facts', 'english': 'Compliance memo'})
        batch = result.json()['id']
        result = self.client.post(f'/api/approvals/{batch}/move', headers=self.headers('security.user@eand.ae'), json={})
        self.assertEqual(result.json()['final_approval_layer'], 2)
        for layer in [1, 2]:
            result = self.decide(batch, layer, email=f'security.approver{layer}@eand.ae')
            self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'approved')

    def test_pending_route_is_preserved_and_resubmission_adopts_new_setting(self):
        batch = self.draft()
        self.move(batch)
        self.policy(1)
        self.assertEqual(self.decide(batch).json()['status'], 'pending_layer_2')
        returned = self.client.post(f'/api/approvals/{batch}/decision', headers=self.headers('b2c.approver2@eand.ae'),
                                    json={'action': 'return_to_user', 'expected_layer': 2, 'note': 'Update brief'})
        self.assertEqual(returned.json()['status'], 'returned_to_user')
        self.assertEqual(self.move(batch)['final_approval_layer'], 1)
        self.assertEqual(self.decide(batch).json()['status'], 'approved')

    def test_policy_permissions_bounds_and_stale_admin_decision(self):
        for layer in [0, 4, True, '2']:
            self.assertEqual(self.policy(layer).status_code, 422)
        self.assertEqual(self.policy(2, 'b2c.user@eand.ae').status_code, 403)
        self.assertEqual(self.policy(2, channel='b2b').status_code, 403)
        self.assertEqual(self.policy(2, 'developer@eand.ae', 'b2b').status_code, 403)
        batch = self.draft(); self.move(batch)
        self.assertEqual(self.decide(batch, email='b2c.admin@eand.ae').status_code, 200)
        self.assertEqual(self.decide(batch, email='b2c.admin@eand.ae').status_code, 409)
