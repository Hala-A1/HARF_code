import asyncio
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse
import access_control
from main import app
from request_limits import RequestLimits, monthly_request
import directory_auth


class ActivityLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'access.json'
        self.data = copy.deepcopy(access_control.DEFAULT_DATA)
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', self.path)
        self.patch.start()
        self.mode = patch.dict('os.environ', {'AUTH_MODE': 'local'})
        self.mode.start()
        self.client = TestClient(app)
        self.user = access_control.get_user('b2b.user@eand.ae')
        self.admin = access_control.get_user('b2b.admin@eand.ae')
        self.store = RequestLimits()

    def tearDown(self):
        self.mode.stop(); self.patch.stop(); self.temp.cleanup()

    def headers(self, email): return {'X-User-Email': email}

    def test_role_scoped_activity_and_expanded_details(self):
        data = access_control.load_access_data()
        for person, channel, text in [(self.user, 'b2b', 'own secret'), (self.admin, 'b2b', 'admin secret'), (access_control.get_user('b2c.user@eand.ae'), 'b2c', 'b2c secret')]:
            access_control.record_activity(data, person, 'Copy generated', 'Generated', channel, {'source': text * 60, 'generated': text * 100})
        access_control.record_activity(data, self.admin, 'Approval decision', 'Hidden decision', 'b2b')
        access_control.save_access_data(data)
        own = self.client.get('/api/activity', headers=self.headers(self.user['email'])).json()
        self.assertEqual(len(own['rows']), 1)
        self.assertIn('output', own['rows'][0]['expandable'])
        self.assertEqual(len(own['rows'][0]['output']), 180)
        detail = self.client.get('/api/activity/' + own['rows'][0]['id'], headers=self.headers(self.user['email'])).json()
        self.assertEqual(detail['output'], 'own secret' * 100)
        admin_rows = self.client.get('/api/activity', headers=self.headers(self.admin['email'])).json()['rows']
        self.assertEqual(len(admin_rows), 2)
        other_id = next(row['id'] for row in admin_rows if row['email'] != self.user['email'])
        self.assertEqual(self.client.get('/api/activity/' + other_id, headers=self.headers(self.user['email'])).status_code, 404)
        self.assertEqual(self.client.get('/api/activity?channel_id=b2c', headers=self.headers(self.admin['email'])).status_code, 403)
        root = self.client.get('/api/activity', headers=self.headers('developer@eand.ae'))
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()['rows'], [])
        reviewer = self.client.get('/api/activity', headers=self.headers('b2b.approver1@eand.ae')).json()
        self.assertFalse(reviewer['rows'])

    def test_batch_columns_and_private_rules_never_disclosed(self):
        data = access_control.load_access_data()
        data['approval_batches'] = [{'id': 'a', 'channel_id': 'b2b', 'created_by_email': self.user['email'], 'created_by': self.user['name'], 'status': 'approved', 'submitted_at': 'now', 'items': [{'id': 'b', 'source': 'Input', 'generated': {'en': 'Output'}, 'format_instructions': 'PRIVATE RULES'}]}]
        access_control.save_access_data(data)
        result = self.client.get('/api/activity', headers=self.headers(self.user['email'])).json()
        row = result['rows'][0]
        self.assertEqual(row['sent_to_approval'], 'Yes')
        self.assertEqual(row['final_status'], 'Approved')
        self.assertNotIn('PRIVATE RULES', json.dumps(self.client.get('/api/activity/' + row['id'], headers=self.headers(self.user['email'])).json()))
        summary = self.client.get('/api/approvals?channel_id=b2b&summary=true', headers=self.headers(self.admin['email'])).json()
        self.assertEqual(summary['batches'][0]['items'], [])
        self.assertTrue(summary['batches'][0]['summary'])
        self.assertNotIn('PRIVATE RULES', json.dumps(summary))

    def test_allocation_permissions_and_no_user_directory_leak(self):
        root = '/api/access/request-limits/b2b'
        self.assertEqual(self.client.put(root + '/channel', headers=self.headers(self.admin['email']), json={'limit': 10}).status_code, 403)
        self.assertEqual(self.client.put(root + '/channel', headers=self.headers('developer@eand.ae'), json={'limit': 10}).status_code, 200)
        self.assertEqual(self.client.put(root + '/users/' + self.user['email'], headers=self.headers(self.admin['email']), json={'limit': 4}).status_code, 200)
        self.assertEqual(self.client.put(root + '/users/' + self.admin['email'], headers=self.headers(self.admin['email']), json={'limit': 7}).status_code, 409)
        own = self.client.get(root, headers=self.headers(self.user['email'])).json()
        self.assertNotIn('users', own)
        self.assertNotIn('directory', own)
        self.assertEqual(own['mine']['limit'], 4)
        self.assertEqual(self.client.put(root + '/users/' + self.user['email'], headers=self.headers(self.user['email']), json={'limit': 8}).status_code, 403)
        self.assertEqual(self.client.get('/api/access/request-limits/b2c', headers=self.headers(self.admin['email'])).status_code, 403)

    def test_atomic_concurrency_failures_and_month_reset(self):
        self.store.set_channel('b2b', 3)
        self.store.set_user('b2b', self.user, 2)
        def attempt(_):
            try: return self.store.reserve('b2b', self.user)
            except HTTPException as error: self.assertEqual(error.status_code, 429); return None
        with ThreadPoolExecutor(max_workers=6) as pool:
            reservations = list(filter(None, pool.map(attempt, range(8))))
        self.assertEqual(len(reservations), 2)
        self.store.finish(reservations[0], False)
        self.store.finish(reservations[1], True)
        replacement = self.store.reserve('b2b', self.user)
        self.store.finish(replacement, True)
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 2)
        with patch('request_limits.month_key', return_value='2099-01'):
            self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 0)
            self.store.reserve('b2b', self.user)

    def test_ldap_link_preserves_allocations_and_usage(self):
        self.store.set_channel('b2b', 10); self.store.set_user('b2b', self.user, 4)
        self.store.finish(self.store.reserve('b2b', self.user), True)
        self.store.link_identity(self.user['email'], 'ldap:stable')
        linked = {**self.user, 'directory_id': 'ldap:stable'}
        summary = self.store.summary('b2b', [linked], linked)
        self.assertEqual((summary['mine']['limit'], summary['mine']['used']), (4, 1))

    def test_channel_reassignment_frees_allocation_but_preserves_usage(self):
        self.store.set_channel('b2b', 10); self.store.set_user('b2b', self.user, 6)
        self.store.finish(self.store.reserve('b2b', self.user), True)
        result = self.client.put('/api/access/assignments', headers=self.headers('developer@eand.ae'), json={
            'email': self.user['email'], 'name': self.user['name'], 'role': 'user', 'channel_id': 'b2c', 'workspaces': ['rewrite']})
        self.assertEqual(result.status_code, 200, result.text)
        summary = self.store.summary('b2b', [], self.admin)
        self.assertEqual((summary['allocated'], summary['channel_used']), (0, 1))

    def test_single_batch_action_counts_once_and_failed_action_refunded(self):
        self.store.set_channel('b2b', 3); self.store.set_user('b2b', self.user, 3)
        @monthly_request
        def generation(user): return 'Several components in two languages'
        generation(user=self.user)
        @monthly_request
        def failure(user): raise HTTPException(status_code=502)
        with self.assertRaises(HTTPException): failure(user=self.user)
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 1)

    def test_failed_and_completed_stream_accounting(self):
        @monthly_request
        def generation(user, failed=False):
            def chunks():
                yield 'data: {"type":"delta","text":"Hello"}\n\n'
                yield 'data: {"type":"error"}\n\n' if failed else 'data: {"type":"done"}\n\n'
            return StreamingResponse(chunks())
        async def consume(response):
            async for _ in response.body_iterator: pass
        asyncio.run(consume(generation(user=self.user, failed=True)))
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 0)
        asyncio.run(consume(generation(user=self.user)))
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 1)

    def test_bilingual_regeneration_route_is_one_request_and_shares_context(self):
        from generation_context import current_generation
        contexts = []
        def rewrite(*args):
            contexts.append(current_generation())
            return 'Revised ' + args[-1]
        with patch('copywriter.enhance_feedback', side_effect=rewrite):
            result = self.client.post('/api/regenerate', headers=self.headers(self.user['email']), json={
                'team_channel': 'b2b', 'items': [{'feedback': 'Fictional brief', 'team_channel': 'b2b', 'output_language': language} for language in ['en', 'ar']]})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['outputs'], ['Revised en', 'Revised ar'])
        self.assertIsNotNone(contexts[0]); self.assertIs(contexts[0], contexts[1])
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 1)

    def test_client_closing_after_done_still_counts_completed_stream(self):
        @monthly_request
        def generation(user):
            def chunks():
                yield 'data: {"type":"delta","text":"Hello"}\n\n'
                yield 'data: {"type":"done"}\n\n'
            return StreamingResponse(chunks())
        async def client():
            response = generation(user=self.user)
            await anext(response.body_iterator)
            await anext(response.body_iterator)
            await response.body_iterator.aclose()
        asyncio.run(client())
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 1)

    def test_quota_rejection_happens_before_ai_and_failed_ai_refunds(self):
        self.store.set_channel('b2b', 1); self.store.set_user('b2b', self.user, 1)
        with patch('copywriter.enhance_feedback', side_effect=RuntimeError('provider failure')):
            self.assertEqual(self.client.post('/api/enhance', headers=self.headers(self.user['email']), json={'feedback': 'Fictional brief'}).status_code, 502)
        self.assertEqual(self.store.summary('b2b', [self.user], self.user)['mine']['used'], 0)
        self.store.finish(self.store.reserve('b2b', self.user), True)
        with patch('copywriter.enhance_feedback') as model:
            result = self.client.post('/api/enhance', headers=self.headers(self.user['email']), json={'feedback': 'Fictional brief'})
            self.assertEqual(result.status_code, 429); model.assert_not_called()

    def test_ldap_fails_closed_and_signed_session_cannot_be_spoofed(self):
        with patch.dict('os.environ', {'AUTH_MODE': 'ldap', 'LDAP_SESSION_SECRET': 's' * 48}):
            self.assertEqual(self.client.get('/api/access/me', headers=self.headers(self.user['email'])).status_code, 401)
            token = directory_auth.issue_token({**self.user, 'directory_id': 'ldap:stable'})
            self.assertEqual(directory_auth.verify_token(token)['email'], self.user['email'])
            with self.assertRaises(HTTPException): directory_auth.verify_token(token + 'x')
            with patch('directory_auth.time.time', return_value=99999999999):
                with self.assertRaises(HTTPException): directory_auth.verify_token(token)
            # A token for an unlinked account must not grant access.
            self.assertEqual(self.client.get('/api/access/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)


if __name__ == '__main__': unittest.main()
