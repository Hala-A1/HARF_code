"""Security restructuring preserves requirements, scope and guide access."""
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import access_control
import admin
import ai_service
from copywriter import output_catalog


class SecurityPackTests(unittest.TestCase):
    def test_legacy_and_new_guide_boundaries_remain_private(self):
        legacy = '<a id="security-admin-only"></a>'
        current = '<a id="regulatory-compliance-admin-only"></a>'
        for marker in [legacy, current]:
            text = f'Public guide\n{marker}\nPrivate administrator notes'
            self.assertEqual(text.split(admin.guide_boundary('SECURITY_USER_GUIDE', text))[0].strip(), 'Public guide')
        text = f'Public\n{legacy}\nPrivate\n{current}\nMore private'
        self.assertEqual(admin.guide_boundary('SECURITY_USER_GUIDE', text), legacy)

    def user(self, role='channel_admin', channel='security'):
        return {'role': role, 'channel_id': channel, 'email': 'security-test@example.com', 'name': 'Security Test'}

    def test_exactly_three_files_and_only_two_generation_modules(self):
        items = admin.list_channel_instructions('security', self.user())['instructions']
        self.assertEqual([i['id'] for i in items], ['SECURITY_POLICY', 'SECURITY_MEMO', 'SECURITY_USER_GUIDE'])
        self.assertTrue(all(i['available'] and i['editable'] for i in items))
        for language in ['English', 'Arabic']:
            bundle = access_control.instruction_bundle('security', query=f'{language} Template 1 reporting deadline')
            self.assertEqual([i['module'] for i in bundle['files']], ['SECURITY_POLICY', 'SECURITY_MEMO'])
            self.assertNotIn('Administrator-only maintenance guide', bundle['text'])
            self.assertNotIn('B2C — System Writing Instructions', bundle['text'])
            self.assertNotIn('B2B Website Tone of Voice', bundle['text'])

    def test_all_important_existing_details_and_index_retained(self):
        system = access_control.instruction_path('SECURITY_POLICY', 'security').read_text(encoding='utf-8')
        template = access_control.instruction_path('SECURITY_MEMO', 'security').read_text(encoding='utf-8')
        for detail in ['11 July 2024', '24 July', '25 July', '30 calendar days', 'section 8.1', 'five-year', 'Section 9.4', '20 August 2024', 'GCC&WO', 'CTIO']:
            self.assertIn(detail, system)
        for detail in ['400-600', '30-60', '60-100', '90-140', '30-50', '12-25', '120 words', 'QoS Policy V 30.pdf', 'QoS Compliance memo-.pdf', 'momosecurity.docx', 'Recommended Action', 'Action Owner', 'Never use HTML tables or code fences']:
            self.assertIn(detail, template)
        self.assertIn('REGULATORY-COMPLIANCE-TEMPLATE-001', template)
        self.assertIn('system_dependency: REGULATORY-COMPLIANCE-SYSTEM', template)
        anchors = re.findall(r'<a id="([^"]+)"></a>', template)
        for link in re.findall(r'\]\(#([^)]+)\)', template):
            self.assertIn(link, anchors)
        options = output_catalog('security')
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['id'], 'template-1')
        self.assertIn('REGULATORY-COMPLIANCE-TEMPLATE-001', options[0]['instructions'])

    def test_user_and_reviewer_cannot_read_admin_part(self):
        for role in ['user']:
            text = admin.get_instruction('security', 'SECURITY_USER_GUIDE', self.user(role))['content']
            self.assertIn('Part A', text)
            self.assertNotIn('Part B', text)
            self.assertNotIn('Add a future template to the index', text)
        with self.assertRaises(HTTPException):
            admin.get_instruction('security', 'SECURITY_USER_GUIDE', self.user('approval_admin'))
        self.assertIn('Part B', admin.get_instruction('security', 'SECURITY_USER_GUIDE', self.user())['content'])
        self.assertEqual([i['id'] for i in admin.list_channel_instructions('security', self.user('user'))['instructions']], ['SECURITY_USER_GUIDE'])
        with self.assertRaises(HTTPException):
            admin.get_instruction('security', 'SECURITY_USER_GUIDE', self.user(channel='b2c'))

    def test_admin_boundary_is_enforced_and_missing_marker_fails_closed(self):
        with self.assertRaises(HTTPException) as error:
            admin.update_instruction('security', 'SECURITY_USER_GUIDE', admin.InstructionUpdateRequest(content='Private admin notes'), self.user())
        self.assertEqual(error.exception.status_code, 422)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'guide.md'
            path.write_text('Private admin notes', encoding='utf-8')
            with patch.object(admin, 'instruction_path', return_value=path):
                result = admin.get_instruction('security', 'SECURITY_USER_GUIDE', self.user('user'))
                self.assertNotIn('Private admin notes', result['content'])

    def test_saved_rules_apply_without_hardcoded_template_competition(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            local = directory / 'security'
            local.mkdir()
            for module in ['SECURITY_POLICY', 'SECURITY_MEMO', 'SECURITY_USER_GUIDE']:
                source = access_control.instruction_path(module, 'security')
                (local / source.name).write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
            with patch.object(access_control, 'CHANNEL_PROMPT_DIR', directory), patch.object(admin, 'CHANNEL_PROMPT_DIR', directory), patch.object(admin, 'save_access_data'):
                admin.update_instruction('security', 'SECURITY_MEMO', admin.InstructionUpdateRequest(content='# Updated Template 1\nUse the revised approved section order.'), self.user())
                prompt = ai_service.build_task_prompt('Verified policy facts', team_channel='security')
                self.assertIn('revised approved section order', prompt)
                self.assertNotIn('Use these headings in order:', prompt)
                self.assertNotIn('Administrator-only maintenance guide', prompt)

    def test_added_pairs_are_editorial_examples_with_source_limits(self):
        bundle = access_control.instruction_bundle('security', query='Template 1 duplicate IMEI UWB')
        text = bundle['text']
        for value in ['REGULATORY-COMPLIANCE-EX-IMEI-001', 'REGULATORY-COMPLIANCE-EX-UWB-SRD-001', 'five-working-day', 'periodic reporting', 'Class Authorization', 'non-interference/non-protection', 'Article 5.1', 'effectiveness from issuance', '600-800', '120 words', 'missing supporting instruments', '31 July/8 August 2023']:
            self.assertIn(value, text)
        self.assertEqual(len(output_catalog('security')), 1)
        self.assertEqual([f['module'] for f in bundle['files']], ['SECURITY_POLICY', 'SECURITY_MEMO'])


if __name__ == '__main__':
    unittest.main()
