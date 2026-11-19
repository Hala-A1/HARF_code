"""B2C replacement routing, isolation, editable files and guide visibility."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import access_control
import admin
import ai_service
from copywriter import output_catalog
from fastapi import HTTPException


class B2CPackTests(unittest.TestCase):
    def user(self, role='channel_admin', channel='b2c'):
        return {'role': role, 'channel_id': channel, 'email': 'test@example.com', 'name': 'Test'}

    def test_live_pack_replaces_all_old_modules_and_excludes_guide(self):
        items = admin.list_channel_instructions('b2c', self.user())['instructions']
        self.assertEqual([i['id'] for i in items], ['B2C_SYSTEM', 'B2C_TEMPLATES', 'B2C_USER_GUIDE'])
        self.assertTrue(all(i['available'] and i['editable'] for i in items))
        for channel in ['SMS', 'Email', 'Website', 'Google Paid Search', 'Other']:
            bundle = access_control.instruction_bundle('b2c', channel, 'Arabic payment reminder')
            self.assertEqual([i['module'] for i in bundle['files']], ['B2C_SYSTEM', 'B2C_TEMPLATES'])
            self.assertNotIn('Administrator-only maintenance guide', bundle['text'])
            self.assertNotIn('B2B Website Tone of Voice', bundle['text'])
        for old in ['CX_WRITING_COMPLETE_GUIDE', '01_BRAND_RULES', '06_B2C_MESSAGING_EXAMPLES']:
            with self.assertRaises(HTTPException) as error:
                admin.get_instruction('b2c', old, self.user())
            self.assertEqual(error.exception.status_code, 404)

    def test_guide_visibility_and_scope(self):
        for role in ['user']:
            text = admin.get_instruction('b2c', 'B2C_USER_GUIDE', self.user(role))['content']
            self.assertIn('Part A', text)
            self.assertNotIn('Part B', text)
            self.assertNotIn('Administrator-only maintenance guide', text)
        with self.assertRaises(HTTPException):
            admin.get_instruction('b2c', 'B2C_USER_GUIDE', self.user('approval_admin'))
        self.assertIn('Part B', admin.get_instruction('b2c', 'B2C_USER_GUIDE', self.user())['content'])
        self.assertEqual([i['id'] for i in admin.list_channel_instructions('b2c', self.user('user'))['instructions']], ['B2C_USER_GUIDE'])
        with self.assertRaises(HTTPException):
            admin.get_instruction('b2c', 'B2C_USER_GUIDE', self.user(channel='b2b'))
        with self.assertRaises(HTTPException):
            admin.get_instruction('b2c', 'B2C_SYSTEM', self.user('user'))

    def test_guide_boundary_cannot_be_removed_and_missing_boundary_fails_closed(self):
        with self.assertRaises(HTTPException) as error:
            admin.update_instruction('b2c', 'B2C_USER_GUIDE', admin.InstructionUpdateRequest(content='secret admin notes'), self.user())
        self.assertEqual(error.exception.status_code, 422)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'guide.md'
            path.write_text('secret admin notes', encoding='utf-8')
            with patch.object(admin, 'instruction_path', return_value=path):
                self.assertNotIn('secret', admin.get_instruction('b2c', 'B2C_USER_GUIDE', self.user('user'))['content'])

    def test_templates_supply_five_output_choices_and_rank_complete_examples(self):
        options = output_catalog('b2c')
        self.assertEqual([i['id'] for i in options], ['b2c-sms-001', 'b2c-email-001', 'b2c-web-001', 'b2c-app-001', 'b2c-push-001'])
        bundle = access_control.instruction_bundle('b2c', 'SMS', 'low balance recharge ADDON_NAME')
        report = bundle['files'][1]
        self.assertGreater(report['example_candidates'], 0)
        self.assertLess(report['example_candidates'], 47)
        self.assertEqual(report['template_families'], ['SMS'])
        self.assertNotIn('## B2C-EMAIL-001', bundle['text'])
        self.assertLessEqual(report['selected_examples'], 4)
        self.assertGreater(report['selected_examples'], 0)
        self.assertIn('English before', bundle['text'])
        self.assertIn('Arabic — source example', bundle['text'])
        self.assertIn('## B2C-SMS-001', bundle['text'])

    def test_admin_save_is_read_by_next_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            local = directory / 'b2c'
            local.mkdir()
            (local / '01_B2C_SYSTEM_INSTRUCTIONS.md').write_text('Initial B2C rules', encoding='utf-8')
            (local / '02_B2C_CHANNEL_TEMPLATE_INSTRUCTIONS.md').write_text('B2C template rules', encoding='utf-8')
            with patch.object(access_control, 'CHANNEL_PROMPT_DIR', directory), patch.object(admin, 'CHANNEL_PROMPT_DIR', directory), patch.object(admin, 'save_access_data'):
                admin.update_instruction('b2c', 'B2C_SYSTEM', admin.InstructionUpdateRequest(content='Updated B2C rules'), self.user())
                self.assertIn('Updated B2C rules', access_control.instruction_text_for('b2c', 'Email'))

    def test_b2c_prompts_do_not_execute_b2b_format_rules(self):
        for language in ['en', 'ar', 'both']:
            prompt = ai_service.build_task_prompt('A verified consumer benefit', channel='Website', team_channel='b2c', output_language=language)
            self.assertIn('matching indexed B2C template', prompt)
            self.assertNotIn('Return only the completed website component record', prompt)
        self.assertIsNone(ai_service.detect_website_component('Component 4', 'b2c'))
        self.assertNotIn('B2C System', access_control.instruction_text_for('b2b', 'Email'))
        self.assertNotIn('B2C System', access_control.instruction_text_for('security'))


if __name__ == '__main__':
    unittest.main()
