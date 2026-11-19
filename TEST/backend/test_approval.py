import copy
import json
import tempfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import access_control
from main import app


class ApprovalWorkflowTests(unittest.TestCase):
    @patch('approval.enhance_bilingual_feedback', return_value={'english': 'My English copy', 'arabic': 'نسختي العربية'})
    def test_super_admin_can_generate_own_bulk_but_cannot_approve(self, enhance):
        headers = self.headers('developer@eand.ae')
        payload = {'items':[{'filename':'Own brief.txt','text':'My brief'}], 'team_channel':'b2c','languages':['en','ar']}
        response = self.client.post('/api/bulk/generate',json=payload,headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        batch = response.json()
        self.assertEqual(batch['items'][0]['generated'],{'en':'My English copy','ar':'نسختي العربية'})
        enhance.assert_called_once()
        self.assertEqual(self.client.get('/api/approvals/'+batch['id'],headers=headers).status_code,200)
        self.assertEqual(self.client.post('/api/approvals/'+batch['id']+'/decision',headers=headers,json={'action':'approve'}).status_code,403)

    @patch('approval.enhance_bilingual_feedback', return_value={'english': 'English copy', 'arabic': 'النص العربي'})
    def test_both_languages_override_source_language_unless_preservation_is_requested(self, enhance):
        payload = {'items': [{'filename': 'message row 2', 'text': 'Backup plan', 'source_language': 'en',
                              'source_id': '0007', 'source_metadata': {'REPLY_ID': '0007'}}],
                   'team_channel': 'b2c', 'languages': ['en', 'ar'], 'preserve_source_languages': False}
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertEqual(item['source_id'], '0007')
        self.assertEqual(item['generated'], {'en': 'English copy', 'ar': 'النص العربي'})
        self.assertEqual(enhance.call_count, 1)
        export = self.client.post('/api/export/xlsx', headers=self.headers('b2c.user@eand.ae'), json={
            'include_source': True, 'sections': [{'text': text, 'language': language, 'original_id': item['source_id'],
                                               'source_text': item['source']} for language, text in item['generated'].items()]})
        self.assertEqual(export.status_code, 200, export.text if export.status_code != 200 else '')
        from io import BytesIO
        from openpyxl import load_workbook
        sheet = load_workbook(BytesIO(export.content)).active
        self.assertEqual(sheet['B2'].value, '0007')
        self.assertEqual(sheet['C3'].value, 'Backup plan')
        self.assertEqual(sheet['D3'].value, 'النص العربي')

    def test_parallel_components_keep_selection_order_and_limit_active_work(self):
        second_finished = threading.Event()
        lock = threading.Lock()
        active, peak = 0, 0
        def generate(*args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                if 'Component 1 ' in args[5]:
                    self.assertTrue(second_finished.wait(2), 'Independent components should overlap')
                else:
                    second_finished.set()
                return 'Generated copy'
            finally:
                with lock:
                    active -= 1
        with patch('approval.enhance_feedback', side_effect=generate):
            result = self.client.post('/api/bulk/generate', headers=self.headers('b2b.user@eand.ae'), json={
                'items': [{'filename': 'brief.txt', 'text': 'Daily backup'}], 'team_channel': 'b2b',
                'languages': ['en'], 'output_ids': ['component-1', 'component-4', 'component-9'],
            })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual([item['output_id'] for item in result.json()['items']], ['component-1', 'component-4', 'component-9'])
        self.assertEqual(peak, 2)

    def setUp(self):
        review_patch = patch('approval.review_component_sets', return_value=[])
        review_patch.start()
        self.addCleanup(review_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp.name) / "access-control.json"
        self.data_file.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding="utf-8")
        self.data_patch = patch.object(access_control, "DATA_FILE", self.data_file)
        self.data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def headers(email):
        return {"X-User-Email": email}

    def test_failed_component_reports_actual_validation_and_keeps_source_safe(self):
        from ai_service import ComponentValidationError
        error = ComponentValidationError(1, 'ar', ['Title is 25 characters; maximum is 20.'])
        with patch('approval.enhance_bilingual_feedback', side_effect=error):
            result = self.client.post('/api/bulk/generate', headers=self.headers('b2b.user@eand.ae'), json={'items': [{'filename': 'brief.txt', 'text': 'PRIVATE SOURCE'}], 'team_channel': 'b2b', 'languages': ['en', 'ar'], 'output_ids': ['component-1', 'component-4']})
        self.assertEqual(result.status_code, 422)
        self.assertIn('Component 1 (Arabic)', result.json()['detail'])
        self.assertIn('maximum is 20', result.json()['detail'])
        self.assertNotIn('PRIVATE SOURCE', result.text)
        self.assertIn('Reference:', result.json()['detail'])

    @patch("approval.enhance_feedback", return_value="Generated format")
    def test_multiple_formats_are_isolated_and_validated(self, generate):
        headers = self.headers("b2b.user@eand.ae")
        catalog = self.client.get('/api/output-options?team_channel=b2b', headers=headers)
        self.assertTrue({f'component-{number}' for number in range(1, 18)}.issubset({item['id'] for item in catalog.json()['options']}))
        payload = {"items": [{"filename": "brief.txt", "text": "Cloud backup"}], "team_channel": "b2b", "languages": ["en"], "output_ids": ["component-1", "component-4"]}
        response = self.client.post('/api/bulk/generate', headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item['output_id'] for item in response.json()['items']], payload['output_ids'])
        for item in response.json()['items']:
            expected = next(option for option in catalog.json()['options'] if option['id'] == item['output_id'])
            self.assertEqual(item['output_name'], expected['name'])
            self.assertEqual(item['source_filename'], 'brief.txt')
        import ai_service
        self.assertEqual([ai_service.detect_website_component(call.args[5], 'b2b')['number'] for call in generate.call_args_list], [1, 4])
        payload['items'] *= 11
        self.assertEqual(self.client.post('/api/bulk/generate', headers=headers, json=payload).status_code, 422)
        payload['items'] = payload['items'][:1]
        payload['output_ids'] = ['template-1']
        self.assertEqual(self.client.post('/api/bulk/generate', headers=headers, json=payload).status_code, 422)
        self.assertEqual(self.client.get('/api/output-options?team_channel=security', headers=headers).status_code, 403)
        security = self.client.get('/api/output-options?team_channel=security', headers=self.headers('security.user@eand.ae'))
        self.assertEqual([item['id'] for item in security.json()['options']], ['template-1'])

    def test_password_accounts_do_not_expose_hashes(self):
        response = self.client.post("/api/access/login", json={"email": "b2b.approver1@eand.ae", "password": "B2B-Layer1!2026"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["approval_layer"], 1)
        self.assertNotIn("password_hash", response.json())
        self.assertEqual(self.client.post("/api/access/login", json={"email": "b2b.approver1@eand.ae", "password": "wrong"}).status_code, 403)

    def test_security_single_copy_return_revise_and_approve(self):
        owner = self.headers("security.user@eand.ae")
        draft = self.client.post('/api/approvals/draft', headers=owner, json={"team_channel": "security", "source": "Policy", "english": "Memo draft"})
        self.assertEqual(draft.status_code, 200)
        batch = draft.json()
        url = f"/api/approvals/{batch['id']}"
        self.assertEqual(self.client.post(url + '/move', headers=owner, json={}).status_code, 200)
        layer1 = self.headers('security.approver1@eand.ae')
        note = self.client.post(url + '/decision', headers=layer1, json={"action": "note", "note": "Check date"})
        self.assertEqual(note.json()['current_layer'], 1)
        self.client.post(url + '/decision', headers=layer1, json={"action": "return_to_user", "note": "Correct date"})
        revised = self.client.put(url + '/copy', headers=owner, json={"item_id": batch['items'][0]['id'], "language": "en", "text": "Corrected memo", "change_request": "Shorten the summary"})
        self.assertEqual(revised.status_code, 200)
        self.assertEqual(len(revised.json()['items'][0]['versions']), 1)
        self.assertEqual(revised.json()['items'][0]['revision_requests'][0]['instructions'], "Shorten the summary")
        self.assertIn("Shorten the summary", revised.json()['events'][-1]['note'])
        self.client.post(url + '/move', headers=owner, json={})
        for layer in (1, 2, 3):
            approved = self.client.post(url + '/decision', headers=self.headers(f'security.approver{layer}@eand.ae'), json={"action": "approve"})
            self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()['status'], 'approved')
        self.assertEqual(self.client.put(url + '/copy', headers=owner, json={"item_id": batch['items'][0]['id'], "language": "en", "text": "Changed"}).status_code, 409)

    def test_security_prompt_isolated_and_large_source_processed(self):
        import ai_service
        prompt = ai_service.build_task_prompt('Source', team_channel='security', instructions='Template 1 memo')
        self.assertIn('Regulatory Instrument Details', prompt)
        self.assertIn('QoS', prompt)
        self.assertNotIn('You are an e& CX Writing Assistant', prompt)
        with patch('ai_service._run_completion', return_value='Evidence with page references') as call:
            evidence = ai_service.security_evidence('a' * 96001)
            self.assertEqual(call.call_count, 3)
            self.assertIn('Segment 3', evidence)

    @patch("approval.enhance_bilingual_feedback", return_value={"english": "Improved copy", "arabic": "نسخة محسنة"})
    def test_batch_moves_through_all_three_layers(self, _enhance):
        payload = {
            "items": [{"filename": "offer.txt", "text": "Improve this offer", "size_bytes": 18, "content_type": "text/plain"}],
            "team_channel": "b2b", "channel": "Email", "audience": "Business", "languages": ["en", "ar"],
        }
        response = self.client.post("/api/bulk/generate", json=payload, headers=self.headers("b2b.user@eand.ae"))
        self.assertEqual(response.status_code, 200)
        batch_id = response.json()["id"]
        response = self.client.post(f"/api/approvals/{batch_id}/move", json={"urgent": True}, headers=self.headers("b2b.user@eand.ae"))
        self.assertEqual(response.json()["status"], "pending_layer_1")
        for layer in (1, 2, 3):
            response = self.client.post(
                f"/api/approvals/{batch_id}/decision",
                json={"action": "approve", "note": f"Layer {layer} approved"},
                headers=self.headers(f"b2b.approver{layer}@eand.ae"),
            )
            self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["progress"], 100)
        self.assertEqual(len(result["events"]), 5)
        notifications = self.client.get("/api/notifications", headers=self.headers("b2b.user@eand.ae")).json()["notifications"]
        self.assertTrue(any(item["kind"] == "final_approval" for item in notifications))

    @patch("approval.enhance_feedback", return_value="Improved")
    def test_imported_row_languages_and_metadata_survive_generation(self, enhance):
        payload = {'items': [
            {'filename': 'messages.xlsx row 2', 'text': 'Daily backup', 'source_language': 'en', 'source_metadata': {'REPLY_ID': '0007', 'SYSTEM_REPLY_CODE': '00'}},
            {'filename': 'messages.xlsx row 3', 'text': 'نسخ احتياطي يومي', 'source_language': 'ar', 'source_metadata': {'REPLY_ID': '0008'}},
        ], 'team_channel': 'b2c', 'languages': ['en'], 'preserve_source_languages': True}
        response = self.client.post('/api/bulk/generate', json=payload, headers=self.headers('b2c.user@eand.ae'))
        self.assertEqual(response.status_code, 200, response.text)
        batch = response.json()
        self.assertEqual(batch['languages'], ['en', 'ar'])
        self.assertEqual(list(batch['items'][0]['generated']), ['en'])
        self.assertEqual(list(batch['items'][1]['generated']), ['ar'])
        self.assertEqual(batch['items'][0]['source_metadata']['REPLY_ID'], '0007')
        self.assertEqual(batch['items'][0]['source_metadata']['SYSTEM_REPLY_CODE'], '00')
        self.assertNotIn('SYSTEM_REPLY_CODE', enhance.call_args_list[0].args[5])

    @patch("approval.enhance_feedback", return_value="Improved")
    def test_twenty_file_limit_and_layer_permissions(self, _enhance):
        payload = {"items": [{"filename": f"{index}.txt", "text": "Copy"} for index in range(20)], "team_channel": "b2c", "languages": ["en"]}
        response = self.client.post("/api/bulk/generate", json=payload, headers=self.headers("b2c.user@eand.ae"))
        self.assertEqual(response.status_code, 200)
        batch_id = response.json()["id"]
        self.client.post(f"/api/approvals/{batch_id}/move", json={}, headers=self.headers("b2c.user@eand.ae"))
        wrong_layer = self.client.post(f"/api/approvals/{batch_id}/decision", json={"action": "approve"}, headers=self.headers("b2c.approver2@eand.ae"))
        self.assertEqual(wrong_layer.status_code, 403)
        payload["items"].append({"filename": "too-many.txt", "text": "Copy"})
        self.assertEqual(self.client.post("/api/bulk/generate", json=payload, headers=self.headers("b2c.user@eand.ae")).status_code, 422)


if __name__ == "__main__":
    unittest.main()
