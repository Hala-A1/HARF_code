import copy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
import admin
from instruction_versions import InstructionVersionRepository
from main import app


class InstructionVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'access-control.json'
        self.data.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.prompts = self.root / 'channels'
        self.prompts.mkdir()
        self.path = self.prompts / 'b2c' / '01_B2C_SYSTEM_INSTRUCTIONS.md'
        self.path.parent.mkdir()
        self.path.write_text('# Consumer rules\nUse clear language.', encoding='utf-8')
        self.patches = [patch.object(access_control, 'DATA_FILE', self.data),
                        patch.object(access_control, 'CHANNEL_PROMPT_DIR', self.prompts),
                        patch.object(admin, 'CHANNEL_PROMPT_DIR', self.prompts)]
        for item in self.patches: item.start()
        self.client = TestClient(app)
        self.url = '/api/access/channels/b2c/instructions/B2C_SYSTEM'
        self.headers = {'X-User-Email': 'b2c.admin@eand.ae'}

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def current(self):
        result = self.client.get(self.url, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def save(self, text, version, note='Updated consumer language'):
        return self.client.put(self.url, headers=self.headers, json={'content': text, 'expected_version': version, 'change_note': note})

    def test_save_captures_starting_content_and_actor_without_bloating_history_list(self):
        before = self.current()
        self.assertEqual(before['version']['version'], 1)
        saved = self.save('# New rules\nWrite naturally in Arabic.', 1)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['version']['version'], 2)
        history = self.client.get(self.url + '/versions', headers=self.headers).json()
        self.assertEqual([row['version'] for row in history['versions']], [2, 1])
        self.assertNotIn('content', history['versions'][0])
        self.assertEqual(history['versions'][0]['actor_email'], 'b2c.admin@eand.ae')
        self.assertEqual(history['versions'][0]['note'], 'Updated consumer language')
        old = self.client.get(self.url + '/versions/1', headers=self.headers).json()
        self.assertEqual(old['content'], before['content'])
        self.assertEqual(old['action'], 'baseline')

    def test_restore_appends_version_and_refreshes_generation_file_index(self):
        old = self.current()['content']
        self.save('# Updated rules', 1)
        from structure_retrieval import indexed_file
        self.assertIn('Updated', indexed_file(self.path)[0]['text'])
        restored = self.client.post(self.url + '/versions/1/restore', headers=self.headers, json={'expected_version': 2, 'reason': 'Restore the approved wording'})
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()['version']['version'], 3)
        self.assertEqual(restored.json()['version']['restored_from'], 1)
        self.assertEqual(restored.json()['version']['action'], 'restore')
        self.assertEqual(self.path.read_text(encoding='utf-8'), old)
        self.assertEqual(indexed_file(self.path)[0]['text'], old)
        self.assertEqual(self.client.get(self.url + '/versions/2', headers=self.headers).json()['content'], '# Updated rules')

    def test_stale_edit_and_restore_are_rejected_without_overwriting(self):
        self.current()
        self.assertEqual(self.save('# First update', 1).status_code, 200)
        self.assertEqual(self.save('# Stale update', 1).status_code, 409)
        response = self.client.post(self.url + '/versions/1/restore', headers=self.headers, json={'expected_version': 1, 'reason': 'Stale restore'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.current()['content'], '# First update')
        self.assertEqual(self.current()['version']['version'], 2)

    def test_concurrent_admins_cannot_overwrite_same_base_version(self):
        self.current()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda value: self.save(value, 1), ['# Update A', '# Update B']))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        self.assertEqual(self.current()['version']['version'], 2)

    def test_versions_survive_reopening_store_and_identical_saves_are_not_duplicates(self):
        old = self.current()['content']
        identical = self.save(old, 1)
        self.assertTrue(identical.json()['version']['unchanged'])
        self.save('# A persisted update', 1)
        reopened = InstructionVersionRepository(self.path)
        self.assertTrue(reopened.database.exists())
        self.assertEqual(reopened.get('b2c', 'B2C_SYSTEM', self.path, 1)['content'], old)
        self.assertEqual(reopened.list('b2c', 'B2C_SYSTEM', self.path)['total'], 2)

    def test_history_and_restore_are_private_to_authorised_admins(self):
        self.current()
        for email in ['b2c.user@eand.ae', 'b2c.approver1@eand.ae', 'b2b.admin@eand.ae']:
            headers = {'X-User-Email': email}
            for suffix in ['/versions', '/versions/1']:
                self.assertEqual(self.client.get(self.url + suffix, headers=headers).status_code, 403)
            self.assertEqual(self.client.post(self.url + '/versions/1/restore', headers=headers, json={'expected_version': 1, 'reason': 'Attempt restore'}).status_code, 403)
        super_user = next(user for user in access_control.DEFAULT_DATA['users'] if user['role'] == 'super_admin')
        headers = {'X-User-Email': super_user['email']}
        self.assertEqual(self.client.get(self.url + '/versions', headers=headers).status_code, 200)
        saved = self.client.put(self.url, headers=headers, json={'content': '# Platform maintained rules', 'expected_version': 1, 'change_note': 'Update instructions'})
        self.assertEqual(saved.status_code, 200, saved.text)
        restored = self.client.post(self.url + '/versions/1/restore', headers=headers, json={'expected_version': 2, 'reason': 'Restore original instructions'})
        self.assertEqual(restored.status_code, 200, restored.text)

    def test_external_edits_are_captured_without_inventing_an_author(self):
        self.current()
        self.path.write_text('# External update', encoding='utf-8')
        history = self.client.get(self.url + '/versions', headers=self.headers).json()
        self.assertEqual(history['current_version'], 2)
        self.assertEqual(history['versions'][0]['action'], 'external_update')
        self.assertIsNone(history['versions'][0]['actor_email'])

    def test_failed_file_write_does_not_leave_a_saved_revision(self):
        old = self.current()['content']
        with patch('instruction_versions._atomic_write', side_effect=OSError('Simulated disk failure')):
            with self.assertRaises(OSError): self.save('# Failed update', 1)
        self.assertEqual(self.current()['version']['version'], 1)
        self.assertEqual(self.path.read_text(encoding='utf-8'), old)

    def test_legacy_prompt_route_uses_same_system_history(self):
        self.current()
        response = self.client.put('/api/access/channels/b2c/prompt', headers=self.headers,
                                   json={'content': '# Legacy route update', 'expected_version': 1})
        self.assertEqual(response.status_code, 200, response.text)
        history = self.client.get(self.url + '/versions', headers=self.headers).json()
        self.assertEqual(history['total'], 2)
        self.assertEqual(history['versions'][0]['action'], 'edit')

    def test_restore_cannot_remove_admin_guide_boundary(self):
        guide = self.path.parent / '03_B2C_USER_AND_ADMIN_GUIDE.md'
        guide.write_text('# Old guide\nNo protected boundary', encoding='utf-8')
        url = self.url.replace('B2C_SYSTEM', 'B2C_USER_GUIDE')
        self.client.get(url, headers=self.headers)
        content = '# Guide\n<a id="b2c-admin-only"></a>\nPrivate admin instructions'
        result = self.client.put(url, headers=self.headers, json={'content': content, 'expected_version': 1})
        self.assertEqual(result.status_code, 200)
        rejected = self.client.post(url + '/versions/1/restore', headers=self.headers, json={'expected_version': 2, 'reason': 'Try older guide'})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(guide.read_text(encoding='utf-8'), content)

    def test_pagination_not_found_and_restore_reason_validation(self):
        self.current()
        for number in range(1, 5): self.save(f'# Rules {number}', number)
        page = self.client.get(self.url + '/versions?offset=2&limit=2', headers=self.headers).json()
        self.assertEqual([row['version'] for row in page['versions']], [3, 2])
        self.assertEqual(page['total'], 5)
        self.assertEqual(self.client.get(self.url + '/versions/999', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(self.url + '/versions/1/restore', headers=self.headers, json={'expected_version': 5, 'reason': '   '}).status_code, 422)

    def test_channel_override_keeps_history_and_does_not_modify_shared_default(self):
        self.path.unlink()
        defaults = self.root / 'instruction-pack'
        defaults.mkdir()
        shared = defaults / self.path.name
        shared.write_text('# Shared starting rules', encoding='utf-8')
        with patch.object(access_control, 'INSTRUCTION_PACK_DIR', defaults):
            self.assertEqual(self.current()['version']['version'], 1)
            self.assertEqual(self.save('# Channel-specific rules', 1).status_code, 200)
            self.assertEqual(self.current()['version']['version'], 2)
            self.assertEqual(shared.read_text(encoding='utf-8'), '# Shared starting rules')
            previous = self.client.get(self.url + '/versions/1', headers=self.headers).json()
            self.assertEqual(previous['content'], '# Shared starting rules')

    def test_database_commit_failure_restores_file_and_does_not_keep_revision(self):
        before = self.current()['content']
        connect = sqlite3.connect
        class FailingCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('Simulated database commit failure')
        with patch('instruction_versions.sqlite3.connect', side_effect=lambda *args, **kwargs: connect(*args, **kwargs, factory=FailingCommit)):
            with self.assertRaises(sqlite3.OperationalError):
                self.save('# This update must roll back', 1)
        self.assertEqual(self.path.read_text(encoding='utf-8'), before)
        self.assertEqual(self.current()['version']['version'], 1)
