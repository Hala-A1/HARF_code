import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
import ai_service
from main import app


class InstructionRefinerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / 'access.json'
        path.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
        self.patch = patch.object(access_control, 'DATA_FILE', path)
        self.patch.start()
        self.client = TestClient(app)
        self.url = '/api/access/channels/b2b/refine-instructions'
        self.headers = {'X-User-Email': 'b2b.admin@eand.ae'}

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def post(self, module='B2B_SYSTEM', **overrides):
        return self.client.post(self.url, headers=self.headers, json={
            'module_id': module, 'instructions': 'Keep all supplied VAT conditions. Never invent an expiry date.', **overrides})

    def test_draft_preserves_files_and_does_not_save_access_data(self):
        paths = [access_control.instruction_path(module, 'b2b') for module in access_control.used_instruction_ids('b2b')]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        reply = {'markdown': '## Offer accuracy\n- Preserve VAT conditions.\n- Never invent an expiry date.', 'warnings': []}
        with patch('instruction_refiner._run_completion', return_value=json.dumps(reply)) as completion, patch('admin.save_access_data') as save:
            response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['saved'])
        self.assertEqual(response.json()['markdown'], reply['markdown'])
        self.assertIn('01_B2B_SYSTEM_INSTRUCTIONS.md', response.json()['placement'])
        save.assert_not_called()
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        self.assertIn('relevant_existing_rules', completion.call_args.args[0])
        self.assertLess(len(completion.call_args.args[0]), 40000)

    def test_only_own_channel_admin_can_use_helper(self):
        body = {'module_id': 'B2B_SYSTEM', 'instructions': 'Use clear wording.'}
        with patch('instruction_refiner._run_completion', return_value='{"markdown":"## Clarity\\nUse clear wording.","warnings":[]}') as completion:
            for email in ['b2b.user@eand.ae', 'b2b.approver1@eand.ae', 'b2c.admin@eand.ae']:
                result = self.client.post(self.url, headers={'X-User-Email': email}, json=body)
                self.assertEqual(result.status_code, 403)
            completion.assert_not_called()
            result = self.client.post(self.url, headers={'X-User-Email': 'developer@eand.ae'}, json=body)
            self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.client.post(self.url, json=body).status_code, 401)
        self.assertEqual(self.post('B2C_SYSTEM').status_code, 404)

    def test_b2b_format_marker_and_guide_placement(self):
        reply = '{"markdown":"## Scope\\nUse the approved format.","warnings":["Confirm the applicable field limit."]}'
        with patch('instruction_refiner._run_completion', return_value=reply):
            result = self.post('B2B_TEMPLATES', template_scope='paid_search').json()
            self.assertTrue(result['markdown'].startswith('<!-- B2B_SCOPE: paid_search -->'))
            self.assertNotIn('<!-- B2B_SCOPE: shared -->', result['markdown'])
            self.assertTrue(result['warnings'])
            for part, expected in [('admin', 'Part B'), ('user', 'Part A')]:
                guide = self.post('B2B_USER_GUIDE', guide_part=part).json()
                self.assertIn(expected, guide['placement'])
                self.assertNotIn('admin-only', guide['markdown'])

    def test_security_and_b2c_use_their_own_files(self):
        reply = '{"markdown":"## Validation\\nKeep source facts.","warnings":[]}'
        for channel, module in [('b2c', 'B2C_TEMPLATES'), ('security', 'SECURITY_MEMO')]:
            with patch('instruction_refiner._run_completion', return_value=reply) as completion:
                response = self.client.post(f'/api/access/channels/{channel}/refine-instructions', headers={'X-User-Email': f'{channel}.admin@eand.ae'}, json={'module_id': module, 'instructions': 'Keep source facts.'})
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'"channel": "{channel}"', completion.call_args.args[0])
                self.assertNotIn('<!-- B2B_SCOPE:', response.json()['markdown'])

    def test_placement_uses_real_lines_matching_scope_and_protected_guide_part(self):
        reply = '{"markdown":"## Rule\\nKeep facts.","warnings":[],"placement_section_id":"invented"}'
        with patch('instruction_refiner._run_completion', return_value=reply):
            for scope in ['website', 'paid_search', 'messaging', 'shared']:
                result = self.post('B2B_TEMPLATES', template_scope=scope).json()
                target = result['placements'][0]
                text = access_control.instruction_path('B2B_TEMPLATES', 'b2b').read_text(encoding='utf-8')
                active = 'shared'
                for line in text.splitlines()[:target['line']-1]:
                    if line.startswith('<!-- B2B_SCOPE: '): active = line.split(': ')[1].split(' ')[0]
                self.assertEqual(active, scope)
                self.assertEqual(target['file_version'], hashlib.sha256(text.encode()).hexdigest()[:16])
            for part in ['user', 'admin']:
                result = self.post('B2B_USER_GUIDE', guide_part=part).json()
                target = result['placements'][0]
                text = access_control.instruction_path('B2B_USER_GUIDE', 'b2b').read_text(encoding='utf-8')
                boundary = next(i for i, line in enumerate(text.splitlines(), 1) if line.startswith('<a id="b2b-admin-only"'))
                self.assertTrue(target['line'] < boundary if part == 'user' else target['line'] > boundary)

    def test_invalid_drafts_and_protected_markers_fail_safely(self):
        for response in ['not json', '[]', '{"markdown":"","warnings":[]}', '{"markdown":"Hi","warnings":"bad"}', json.dumps({'markdown': '<a id="b2b-admin-only"></a>', 'warnings': []})]:
            with patch('instruction_refiner._run_completion', return_value=response):
                self.assertEqual(self.post().status_code, 502)
        self.assertEqual(self.post(instructions='   ').status_code, 422)
        self.assertEqual(self.post(instructions='a' * 12001).status_code, 422)
        self.assertEqual(self.post(template_scope='unknown').status_code, 422)
        with patch('instruction_refiner._run_completion', side_effect=RuntimeError('private service details')):
            response = self.post()
            self.assertEqual(response.status_code, 502)
            self.assertNotIn('private service details', response.text)


class ContextualArabicTests(unittest.TestCase):
    def test_contextual_rules_used_in_translation_and_arabic_generation(self):
        with patch.object(ai_service, 'guidelines_for_text', return_value='Approved glossary'), patch.object(ai_service, 'website_component_requirements', return_value=('SMS', '')):
            translation = ai_service.translation_instructions('Your plan renews tomorrow. Manage it in the app.', 'ar', 'b2c')
            generated = ai_service.build_task_prompt('Plan renewal tomorrow', team_channel='b2c', output_language='ar')
        for prompt in [translation, generated]:
            self.assertIn('First understand the complete brief/message', prompt)
            self.assertIn('not translate isolated English words', prompt)
            self.assertIn('Compare the completed Arabic against the source meaning', prompt)
            self.assertIn('never invent context', prompt.lower())


if __name__ == '__main__':
    unittest.main()
