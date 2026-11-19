import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
import feedback
from main import app


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        directory = Path(self.temporary.name)
        self.data = directory / 'access.json'
        self.data.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.patches = [patch.object(access_control, 'DATA_FILE', self.data),
                        patch.object(feedback, 'FEEDBACK_DB', directory/'feedback.sqlite3'),
                        patch.object(feedback, 'manifest', return_value={'basis': 'Instruction versions at feedback submission', 'files': [{'filename': 'tone.md', 'version': 'test-version'}]})]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.snapshot = {'channel_id': 'b2b', 'workspace': 'rewrite', 'task': 'write',
                         'source_text': 'Verified source brief', 'output_text': 'Final generated output',
                         'language': 'en', 'instructions': 'Use Component 4 and a professional tone.',
                         'request_title': 'Write Component 4', 'content_channel': 'Website',
                         'audience': 'Business', 'product_type': 'Internet', 'filename': 'offer.docx',
                         'version': '1', 'score': 88}

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def headers(self, email='b2b.user@eand.ae'):
        return {'X-User-Email': email}

    def submit(self, rating='up', reason='', snapshot=None, email='b2b.user@eand.ae'):
        return self.client.post('/api/feedback', headers=self.headers(email), json={
            'snapshot': self.snapshot if snapshot is None else snapshot, 'rating': rating, 'reason': reason})

    def detail(self, identity, email='b2b.admin@eand.ae'):
        return self.client.get('/api/feedback/'+identity, headers=self.headers(email))

    def test_negative_requires_a_nonblank_reason(self):
        for reason in ['', '   ', '\n\t']:
            self.assertEqual(self.submit('down', reason).status_code, 422)
        self.assertEqual(self.submit('down', 'The wording is unclear.').status_code, 200)

    def test_snapshot_has_input_output_task_and_all_details(self):
        submitted = self.submit('down', 'The claim needs qualifying.').json()
        self.snapshot['source_text'] = 'A later edited brief'
        self.snapshot['output_text'] = 'A later regenerated copy'
        detail = self.detail(submitted['id']).json()
        self.assertEqual(detail['snapshot']['source_text'], 'Verified source brief')
        self.assertEqual(detail['snapshot']['output_text'], 'Final generated output')
        for key in ['task', 'instructions', 'request_title', 'audience', 'product_type', 'version', 'score', 'filename']:
            self.assertEqual(detail['snapshot'][key], self.snapshot[key])
        self.assertEqual(detail['reason'], 'The claim needs qualifying.')
        self.assertIn('feedback submission', detail['instruction_manifest']['basis'])

    def test_only_matching_channel_admin_can_read_feedback(self):
        identity = self.submit().json()['id']
        self.assertEqual(self.detail(identity).status_code, 200)
        self.assertEqual(self.detail(identity, 'developer@eand.ae').status_code, 403)
        for email in ['b2c.admin@eand.ae', 'security.admin@eand.ae', 'b2b.approver1@eand.ae', 'b2b.user@eand.ae']:
            self.assertIn(self.detail(identity, email).status_code, [403, 404])
            self.assertEqual(self.client.get('/api/feedback?channel_id=b2b', headers=self.headers(email)).status_code, 403)
        own_channel = self.client.get('/api/feedback?channel_id=b2c', headers=self.headers('b2c.admin@eand.ae')).json()
        self.assertEqual(own_channel['total'], 0)
        self.assertEqual(self.client.get('/api/feedback?channel_id=b2b', headers=self.headers('developer@eand.ae')).status_code, 403)

    def test_users_cannot_submit_for_a_different_channel_or_forbidden_workspace(self):
        wrong = {**self.snapshot, 'channel_id': 'b2c'}
        self.assertEqual(self.submit(snapshot=wrong).status_code, 403)
        self.assertEqual(self.submit(snapshot={**self.snapshot, 'channel_id': 'missing'}).status_code, 404)
        state = access_control.load_access_data()
        next(u for u in state['users'] if u['email']=='b2b.user@eand.ae')['workspaces'] = ['rewrite']
        access_control.save_access_data(state)
        image = {**self.snapshot, 'workspace': 'create', 'output_image': 'data:image/png;base64,aGVsbG8='}
        self.assertEqual(self.submit(snapshot=image).status_code, 422)

    def test_duplicates_update_one_vote_and_notifications_stay_private(self):
        first = self.submit().json()
        notifications = access_control.load_access_data()['notifications']
        expected = {u['email'] for u in access_control.DEFAULT_DATA['users'] if u['role']=='channel_admin' and u['channel_id']=='b2b'}
        self.assertEqual({item['recipient_email'] for item in notifications}, expected)
        self.assertTrue(all(item['kind']=='output_feedback' for item in notifications))
        self.assertEqual(self.submit().json()['id'], first['id'])
        self.assertEqual(len(access_control.load_access_data()['notifications']), len(notifications))
        self.assertEqual(self.submit('down', 'Use a clearer benefit.').json()['id'], first['id'])
        listing = self.client.get('/api/feedback?channel_id=b2b', headers=self.headers('b2b.admin@eand.ae')).json()
        self.assertEqual(listing['total'], 1)
        self.assertEqual(listing['stats']['negative'], 1)
        self.assertEqual(access_control.load_access_data()['activity'], [])

    def test_users_can_restore_only_their_own_vote_and_new_outputs_are_separate(self):
        first = self.submit('down', 'Needs a clearer CTA.').json()
        url = '/api/feedback/mine?channel_id=b2b&fingerprint='+first['fingerprint']
        self.assertEqual(self.client.get(url, headers=self.headers()).json()['feedback']['rating'], 'down')
        self.assertIsNone(self.client.get(url, headers=self.headers('mariam.k@eand.ae')).json()['feedback'])
        second = self.submit(snapshot={**self.snapshot, 'output_text': 'New revised copy', 'version': '2'}).json()
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['fingerprint'], second['fingerprint'])

    def test_all_channels_have_isolated_feedback(self):
        for channel in ['b2b', 'b2c', 'security']:
            self.assertEqual(self.submit('down', f'{channel} specific feedback', snapshot={**self.snapshot, 'channel_id': channel}, email=f'{channel}.user@eand.ae').status_code, 200)
        for channel in ['b2b', 'b2c', 'security']:
            listing = self.client.get('/api/feedback?channel_id='+channel, headers=self.headers(f'{channel}.admin@eand.ae')).json()
            self.assertEqual(listing['total'], 1)
            self.assertEqual(listing['items'][0]['reason'], f'{channel} specific feedback')

    def test_review_notes_and_stale_review_protection(self):
        identity = self.submit().json()['id']
        original = self.detail(identity).json()
        body = {'status': 'reviewed', 'admin_note': 'Update the tone examples.', 'expected_updated_at': original['updated_at']}
        for email in ['b2b.user@eand.ae', 'b2b.approver1@eand.ae', 'b2c.admin@eand.ae']:
            self.assertIn(self.client.patch('/api/feedback/'+identity, headers=self.headers(email), json=body).status_code, [403,404])
        reviewed = self.client.patch('/api/feedback/'+identity, headers=self.headers('b2b.admin@eand.ae'), json=body).json()
        self.assertEqual(reviewed['status'], 'reviewed')
        self.assertEqual(reviewed['admin_note'], 'Update the tone examples.')
        self.submit('down', 'Changed feedback after review.')
        stale = {**body, 'expected_updated_at': reviewed['updated_at']}
        self.assertEqual(self.client.patch('/api/feedback/'+identity, headers=self.headers('b2b.admin@eand.ae'), json=stale).status_code, 409)
        self.assertEqual(self.detail(identity).json()['status'], 'new')

    def test_search_pagination_and_full_source_preservation(self):
        source = 'تفاصيل المصدر\n' * 10000
        item = self.submit('down', 'Arabic source quality', snapshot={**self.snapshot, 'source_text': source}).json()
        self.assertEqual(self.detail(item['id']).json()['snapshot']['source_text'], source)
        for i in range(21):
            self.submit(snapshot={**self.snapshot, 'output_text': f'Unique generated text {i}'})
        headers = self.headers('b2b.admin@eand.ae')
        self.assertEqual(len(self.client.get('/api/feedback?channel_id=b2b', headers=headers).json()['items']), 20)
        self.assertEqual(len(self.client.get('/api/feedback?channel_id=b2b&page=2', headers=headers).json()['items']), 2)
        self.assertEqual(self.client.get('/api/feedback?channel_id=b2b&rating=down&search=quality', headers=headers).json()['total'], 1)
        self.assertEqual(self.client.get('/api/feedback?channel_id=b2b&search=%25', headers=headers).json()['total'], 0)

    def test_retired_image_workspace_is_rejected(self):
        image = {**self.snapshot, 'workspace': 'create', 'output_image': 'data:image/png;base64,aGVsbG8='}
        self.assertEqual(self.submit(snapshot=image).status_code, 422)
        self.assertEqual(self.submit(snapshot={**self.snapshot, 'output_image': 'https://example.invalid/old.png'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
