import copy
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from docx import Document
import access_control
from main import app
from copy_export import create_copy_document, create_copy_workbook
from docling_client import parse_result, extract_document, DoclingBlockedByPolicyError, DoclingError


class ExportTests(unittest.TestCase):
    def test_metadata_tables_arabic_and_formula_safety(self):
        sections = [{"language": "ar", "text": "# مذكرة\n\n| Action | Owner |\n| --- | --- |\n| =1+1 | Team |",
                     "metadata": {"version": "3", "created_by": "Author", "status": "Approved by administrator override"}}]
        document = Document(BytesIO(create_copy_document(sections)))
        self.assertIn("Created by: Author", document.paragraphs[0].text)
        self.assertEqual(len(document.tables), 1)
        workbook = load_workbook(BytesIO(create_copy_workbook(sections)))
        self.assertEqual(workbook.sheetnames, ["Outputs"])
        self.assertEqual(workbook['Outputs']['C2'].value, sections[0]['text'])
        self.assertEqual(workbook['Outputs']['C2'].alignment.readingOrder, 2)
        self.assertEqual(workbook['Outputs']['D2'].value, 'Author')
        self.assertEqual(workbook['Outputs'].max_column, 6)
        formula_book = load_workbook(BytesIO(create_copy_workbook([{'text': '=1+1'}])))
        self.assertEqual(formula_book['Outputs']['C2'].data_type, 's')

    def test_print_attribution_is_small_left_aligned_and_once_per_document(self):
        metadata = {'created_by': 'Development Team', 'created_at': '2026-10-17T15:47:23.140483+00:00', 'version': '1', 'status': 'draft', 'sequence_number': 'private-id'}
        document = Document(BytesIO(create_copy_document([{'text': 'English copy', 'language': 'en', 'metadata': metadata}, {'text': 'نص عربي', 'language': 'ar', 'metadata': metadata}])))
        text = '\n'.join(paragraph.text for paragraph in document.paragraphs)
        self.assertEqual(text.count('Created by:'), 1)
        self.assertEqual(text.count('Created at:'), 1)
        self.assertEqual(text.count('Score:'), 2)
        self.assertIn('Created at: 2026-10-17 15:47:23', document.paragraphs[0].text)
        self.assertEqual(document.paragraphs[0].runs[0].font.size.pt, 8)
        self.assertEqual(document.paragraphs[0].alignment, 0)
        for removed in ['Sequence number', 'Version', 'Status', 'Channel', 'Product', 'Reviewed by', 'private-id', '+00:00', '.140483']:
            self.assertNotIn(removed, text)

    def test_long_excel_content_not_truncated(self):
        text = 'a' * 32767
        workbook = load_workbook(BytesIO(create_copy_workbook([{'text': text}])))
        self.assertEqual(workbook['Outputs']['C2'].value, text)
        with self.assertRaisesRegex(ValueError, '32,767'):
            create_copy_workbook([{'text': text + 'a'}])


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'data.json'
        self.path.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', self.path)
        self.patch.start()
        self.client = TestClient(app)
        self.owner = {'X-User-Email': 'b2b.user@eand.ae'}
        self.admin = {'X-User-Email': 'b2b.admin@eand.ae'}
        draft = self.client.post('/api/approvals/draft', headers=self.owner, json={'team_channel': 'b2b', 'source': 'Facts', 'english': 'Output'}).json()
        self.url = '/api/approvals/' + draft['id']

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_override_permissions_reason_history_notification(self):
        endpoint = self.url + '/admin-action'
        body = {'action': 'override_approve', 'reason': 'Reviewed and approved for urgent use'}
        self.assertEqual(self.client.post(endpoint, headers=self.admin, json=body).status_code, 409)
        self.client.post(self.url + '/move', headers=self.owner, json={})
        for email in ('b2b.user@eand.ae', 'b2b.approver1@eand.ae', 'b2c.admin@eand.ae'):
            self.assertEqual(self.client.post(endpoint, headers={'X-User-Email': email}, json=body).status_code, 403)
        self.assertEqual(self.client.post(endpoint, headers=self.admin, json={**body, 'reason': ' '}).status_code, 422)
        result = self.client.post(endpoint, headers=self.admin, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        batch = result.json()
        self.assertEqual(batch['status'], 'approved')
        self.assertEqual(batch['approval_method'], 'administrator_override')
        self.assertEqual(batch['events'][-1]['note'], body['reason'])
        self.assertFalse(any(e['action'] == 'final_approved' for e in batch['events']))
        self.assertEqual(self.client.post(endpoint, headers=self.admin, json=body).status_code, 409)
        notices = self.client.get('/api/notifications', headers=self.owner).json()['notifications']
        self.assertTrue(any(n['kind'] == 'admin_override_approve' for n in notices))

    def test_retrieval_preview_permissions_and_routing(self):
        body = {'query': 'Mobile renewal SMS', 'content_channel': 'Google Paid Search'}
        url = '/api/access/channels/b2b/retrieval-preview'
        self.assertEqual(self.client.post(url, headers=self.owner, json=body).status_code, 403)
        self.assertEqual(self.client.post(url, headers={'X-User-Email': 'b2c.admin@eand.ae'}, json=body).status_code, 403)
        response = self.client.post(url, headers=self.admin, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        modules = {item['module'] for item in response.json()['files']}
        self.assertEqual(modules, {'B2B_SYSTEM', 'B2B_TEMPLATES'})
        self.assertEqual(response.json()['files'][-1]['format_scope'], 'paid_search')
        self.assertNotIn('03_WEBSITE_COMPONENT_SCHEMA', modules)
        self.assertNotIn('06_B2C_MESSAGING_EXAMPLES', modules)
        self.assertNotIn('text', response.json())

    def test_channel_admin_normal_approval_and_scope(self):
        self.client.post(self.url + '/move', headers=self.owner, json={})
        for email in ('b2c.admin@eand.ae', 'b2b.approver2@eand.ae', 'b2b.user@eand.ae'):
            response = self.client.post(self.url + '/decision', headers={'X-User-Email': email}, json={'action': 'approve'})
            self.assertEqual(response.status_code, 403)
        response = self.client.post(self.url + '/decision', headers=self.admin, json={'action': 'approve'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pending_layer_2')
        self.assertEqual(response.json()['events'][-1]['actor_role'], 'channel_admin')
        response = self.client.post(self.url + '/decision', headers={'X-User-Email': 'b2b.approver2@eand.ae'}, json={'action': 'approve'})
        self.assertEqual(response.json()['status'], 'pending_layer_3')

    def test_new_channel_has_only_three_independent_files(self):
        import admin
        import ai_service
        directory = Path(self.temp.name) / 'channels'
        with patch.object(admin, 'CHANNEL_PROMPT_DIR', directory), patch.object(access_control, 'CHANNEL_PROMPT_DIR', directory):
            headers = {'X-User-Email': 'developer@eand.ae'}
            response = self.client.post('/api/access/channels', headers=headers, json={'name': 'Research'})
            self.assertEqual(response.status_code, 200, response.text)
            assigned = self.client.put('/api/access/assignments', headers=headers, json={'email':'research.admin@example.test','name':'Research Admin','role':'channel_admin','channel_id':'research','workspaces':['rewrite']})
            self.assertEqual(assigned.status_code, 200)
            headers = {'X-User-Email':'research.admin@example.test'}
            files = self.client.get('/api/access/channels/research/instructions', headers=headers).json()['instructions']
            self.assertEqual({f['id'] for f in files}, {'CHANNEL_SYSTEM', 'CHANNEL_TEMPLATES', 'CHANNEL_USER_ADMIN_GUIDE'})
            prompt = ai_service.build_task_prompt('Brief', team_channel='research')
            self.assertIn('Behavioural Instructions', prompt)
            self.assertNotIn('e& CX', prompt)
            self.assertNotIn('QoS', prompt)
            self.assertNotIn('Component 13', prompt)
            self.assertNotIn('Administrator-only maintenance guide', prompt)
            bundle = access_control.instruction_bundle('research', query='fictional brief')
            self.assertEqual([f['module'] for f in bundle['files']], ['CHANNEL_SYSTEM', 'CHANNEL_TEMPLATES'])
            guide_url = '/api/access/channels/research/instructions/CHANNEL_USER_ADMIN_GUIDE'
            full = self.client.get(guide_url, headers=headers)
            self.assertIn('Part B', full.json()['content'])
            removed_boundary = self.client.put(guide_url, headers=headers, json={'content': '# Private instructions'})
            self.assertEqual(removed_boundary.status_code, 422)

    def test_other_admin_actions_and_super_admin(self):
        self.client.post(self.url + '/move', headers=self.owner, json={})
        for action in ('urgent', 'note', 'warning'):
            result = self.client.post(self.url + '/admin-action', headers=self.admin, json={'action': action, 'reason': 'Test reason'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['status'], 'pending_layer_1')
        self.assertTrue(result.json()['urgent'])
        result = self.client.post(self.url + '/admin-action', headers=self.admin, json={'action': 'return_to_user', 'reason': 'Please revise'})
        self.assertEqual(result.json()['status'], 'returned_to_user')
        self.client.post(self.url + '/move', headers=self.owner, json={})
        result = self.client.post(self.url + '/admin-action', headers={'X-User-Email': 'developer@eand.ae'}, json={'action': 'reject', 'reason': 'Unsupported claim'})
        self.assertEqual(result.status_code, 403)

    def test_xlsx_endpoint(self):
        result = self.client.post('/api/export/xlsx', headers=self.owner, json={'sections': [{'text': 'Copy', 'metadata': {'created_by': 'Author', 'version': '2'}}]})
        self.assertEqual(result.status_code, 200, result.text)
        workbook = load_workbook(BytesIO(result.content))
        self.assertEqual(workbook['Outputs'].max_column, 6)
        self.assertNotIn('Version', [cell.value for cell in workbook['Outputs'][1]])


class DoclingTests(unittest.IsolatedAsyncioTestCase):
    def test_image_cleanup(self):
        self.assertEqual(parse_result({'document': {'md_content': 'Hello ![x](data:image/png;base64,abc) <img src="x">'}}), 'Hello')

    async def test_explicit_ocr_languages_and_preset_are_sent_to_service(self):
        import httpx
        real_client=httpx.AsyncClient
        requests=[]
        def handler(request):
            requests.append(request)
            if 'convert' in request.url.path:return httpx.Response(200,json={'task_id':'fictional'})
            if 'status' in request.url.path:return httpx.Response(200,json={'task_status':'success'})
            return httpx.Response(200,json={'document':{'md_content':'Extracted Arabic العربية'}})
        with patch.dict('os.environ',{'DOCLING_BASE_URL':'https://docling.example','DOCLING_DO_OCR':'true','SCAN_OCR_FALLBACK_ENABLED':'false','DOCLING_OCR_LANGUAGES':'ar,en,ar','DOCLING_OCR_PRESET':'easyocr'}),patch('docling_client.httpx.AsyncClient',side_effect=lambda **kw:real_client(**kw,transport=httpx.MockTransport(handler))):
            self.assertIn('العربية',await extract_document('sample.pdf',b'synthetic','application/pdf'))
        body=requests[0].content.decode()
        self.assertEqual(body.count('name="ocr_lang"'),2)
        self.assertIn('name="ocr_preset"',body)
        self.assertIn('easyocr',body)

    async def test_failed_ocr_explains_administrator_action_with_task_reference(self):
        import httpx
        real_client=httpx.AsyncClient
        def handler(request):
            return httpx.Response(200,json={'task_id':'fictional-ocr-job'} if 'convert' in request.url.path else {'task_status':'failure','error_message':'PRIVATE INTERNAL DETAILS'})
        with patch.dict('os.environ',{'DOCLING_BASE_URL':'https://docling.example','DOCLING_DO_OCR':'true','SCAN_OCR_FALLBACK_ENABLED':'false','DOCLING_OCR_LANGUAGES':'','DOCLING_OCR_PRESET':''}),patch('docling_client.httpx.AsyncClient',side_effect=lambda **kw:real_client(**kw,transport=httpx.MockTransport(handler))):
            with self.assertRaisesRegex(DoclingError,'administrator.*fictional-ocr-job') as error:
                await extract_document('sample.pdf',b'synthetic','application/pdf')
            self.assertNotIn('PRIVATE',str(error.exception))

    async def test_async_conversion_and_policy_error(self):
        import httpx
        real_client = httpx.AsyncClient
        def handler(request):
            if 'convert' in request.url.path:
                return httpx.Response(200, json={'task_id': '123'})
            if 'status' in request.url.path:
                return httpx.Response(200, json={'task_status': 'success'})
            return httpx.Response(200, json={'document': {'md_content': '# Extracted'}})
        with patch.dict('os.environ', {'DOCLING_BASE_URL': 'https://docling.example', 'DOCLING_DO_OCR': 'false'}), patch('docling_client.httpx.AsyncClient', side_effect=lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler))):
            self.assertEqual(await extract_document('sample.pdf', b'synthetic', 'application/pdf'), '# Extracted')
        with patch.dict('os.environ', {'DOCLING_BASE_URL': 'https://docling.example', 'DOCLING_DO_OCR': 'false'}), patch('docling_client.httpx.AsyncClient', side_effect=lambda **kw: real_client(**kw, transport=httpx.MockTransport(lambda r: httpx.Response(403)))):
            with self.assertRaises(DoclingBlockedByPolicyError):
                await extract_document('sample.pdf', b'synthetic', 'application/pdf')

