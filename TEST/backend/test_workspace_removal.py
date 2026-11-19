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


class RewriteOnlyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        data_file = root / 'access.json'
        data_file.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.data_patch = patch.object(access_control, 'DATA_FILE', data_file)
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.db_patch = patch.object(feedback, 'FEEDBACK_DB', root / 'feedback.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.client = TestClient(app, headers={'X-User-Email': 'b2b.admin@eand.ae'})

    def test_removed_endpoints_are_not_registered_or_accessible(self):
        schema = app.openapi()
        for path in ['/api/generate', '/api/resize', '/api/enhance-description']:
            self.assertNotIn(path, schema['paths'])
            self.assertEqual(self.client.post(path, json={}).status_code, 404)
        self.assertIn('/api/enhance', schema['paths'])
        self.assertIn('/api/analyze', schema['paths'])
        self.assertIn('/api/export/docx', schema['paths'])

    def test_old_workspace_cannot_be_assigned(self):
        response = self.client.put('/api/access/assignments', json={
            'email': 'test@example.com', 'name': 'Test', 'role': 'user',
            'channel_id': 'b2b', 'workspaces': ['create'],
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(access_control.WORKSPACES, {'rewrite'})

    def test_legacy_permissions_are_retired_without_granting_rewrite(self):
        data = access_control.load_access_data()
        first = next(user for user in data['users'] if user['email'] == 'b2b.user@eand.ae')
        second = next(user for user in data['users'] if user['email'] == 'b2c.user@eand.ae')
        old_password = first['password_hash']
        first['workspaces'] = ['create']
        second['workspaces'] = ['rewrite', 'create']
        access_control.save_access_data(data)
        users = {user['email']: user for user in access_control.load_access_data()['users']}
        self.assertEqual(users[first['email']]['workspaces'], [])
        self.assertEqual(users[second['email']]['workspaces'], ['rewrite'])
        self.assertEqual(users[first['email']]['password_hash'], old_password)
        with self.assertRaises(Exception) as raised:
            access_control.require_workspace_access(users[first['email']], 'rewrite')
        self.assertEqual(raised.exception.status_code, 403)

    def test_legacy_visual_feedback_is_hidden_without_deleting_records(self):
        db = feedback.connect()
        self.addCleanup(db.close)
        with db:
            for identity, workspace, fingerprint in [('old', 'create', 'a' * 64), ('text', 'rewrite', 'b' * 64)]:
                db.execute('''INSERT INTO feedback (id,channel_id,workspace,user_email,user_name,fingerprint,
                    rating,reason,snapshot,instruction_manifest,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (identity, 'b2b', workspace, 'b2b.admin@eand.ae', 'Test', fingerprint,
                     'up', '', '{}', '{}', '2026-10-14', '2026-10-14'))
        db.close()
        listing = self.client.get('/api/feedback?channel_id=b2b').json()
        self.assertEqual(listing['total'], 1)
        self.assertEqual(listing['stats']['total'], 1)
        self.assertEqual(listing['items'][0]['id'], 'text')
        self.assertEqual(self.client.get('/api/feedback/old').status_code, 404)
        self.assertIsNone(self.client.get('/api/feedback/mine?channel_id=b2b&fingerprint=' + 'a' * 64).json()['feedback'])
        db = feedback.connect()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM feedback').fetchone()[0], 2)
        db.close()


if __name__ == '__main__':
    unittest.main()
