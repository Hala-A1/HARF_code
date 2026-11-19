import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from archive_names import ensure_archive_names
from main import app


class ArchiveNameTests(unittest.TestCase):
    def test_short_meaningful_names_preserve_source_and_copy(self):
        batch = {'id': 'saved-id', 'title': '2-file copy batch', 'product_type': 'Unknown', 'items': [
            {'id': 'one', 'filename': 'upload-09.docx', 'source_filename': 'upload-09.docx', 'output_id': 'component-4', 'output_name': 'Component 4 — USP Featured', 'generated': {'en': '[COPY READY CONTENT]\nTitle: Cloud backup\nSub-title: Daily protection'}, 'source': 'Original facts'},
            {'id': 'two', 'filename': 'input.txt', 'generated': {'ar': 'الموضوع: تجديد باقة الهاتف\nالنص'}, 'source': 'Facts'}]}
        original = copy.deepcopy(batch)
        self.assertTrue(ensure_archive_names(batch))
        self.assertIn('Cloud backup', batch['archive_name'])
        self.assertIn('2 copies', batch['archive_name'])
        self.assertIn('C4', batch['items'][0]['archive_name'])
        self.assertIn('تجديد باقة الهاتف', batch['items'][1]['archive_name'])
        self.assertFalse(ensure_archive_names(batch))
        for before, after in zip(original['items'], batch['items']):
            self.assertEqual(before, {key: value for key, value in after.items() if key != 'archive_name'})
            self.assertLessEqual(len(after['archive_name']), 78)
        self.assertEqual(batch['id'], original['id']); self.assertEqual(batch['title'], original['title'])

    def test_plain_copy_and_long_titles_do_not_use_random_upload_name(self):
        batch = {'title': 'Generated copy', 'content_channel': 'SMS', 'items': [{'filename': 'e853aa99ba8a4ed9a5114dfbae8d8f81.txt', 'generated': {'en': 'Your mobile plan renews tomorrow. The monthly price is AED 100 including VAT.'}}]}
        ensure_archive_names(batch)
        self.assertIn('Your mobile plan renews tomorrow', batch['archive_name'])
        self.assertNotIn('e853aa', batch['archive_name'])
        long = {'title': 'Generated copy', 'items': [{'generated': {'en': 'Title: ' + 'Cloud backup ' * 40}}]}
        ensure_archive_names(long)
        self.assertLessEqual(len(long['archive_name']), 78)

    def test_existing_and_new_archive_names_persist_without_an_ai_naming_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'access.json'
            data = copy.deepcopy(access_control.DEFAULT_DATA)
            data['approval_batches'] = [{'id': 'old', 'title': 'Generated copy', 'channel_id': 'b2c', 'created_by_email': 'b2c.user@eand.ae', 'items': [{'id': 'item', 'filename': 'input.txt', 'generated': {'en': 'Subject: Welcome gift reminder'}}]}]
            path.write_text(json.dumps(data), encoding='utf-8')
            with patch.object(access_control, 'DATA_FILE', path):
                first = access_control.load_access_data()
                saved = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(first['approval_batches'][0]['archive_name'], 'Welcome gift reminder')
                self.assertEqual(saved['approval_batches'], first['approval_batches'])
                client = TestClient(app)
                with patch('approval.enhance_feedback', return_value='Subject: Mobile renewal notice') as generation:
                    response = client.post('/api/bulk/generate', headers={'X-User-Email': 'b2c.user@eand.ae'}, json={'team_channel': 'b2c', 'items': [{'filename': 'upload-3.txt', 'text': 'Fictional renewal facts'}], 'languages': ['en']})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('Mobile renewal notice', response.json()['archive_name'])
                generation.assert_called_once()


if __name__ == '__main__': unittest.main()
