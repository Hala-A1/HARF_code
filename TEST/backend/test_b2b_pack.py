"""B2B lossless consolidation, format boundaries and administrator protection."""
from pathlib import Path
import hashlib
import json
import re
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi import HTTPException
import access_control as access
import admin
from ai_service import website_component_blocks
from copywriter import output_catalog
from quality_analysis import evidence_context, component_length_checks


class B2BPackTests(unittest.TestCase):
    def user(self, role='channel_admin'):
        return {'role': role, 'channel_id': 'b2b', 'email': 'test@example.com', 'name': 'Pack test'}

    def test_exactly_three_visible_files_and_two_generation_files(self):
        items = admin.list_channel_instructions('b2b', self.user())['instructions']
        self.assertEqual([i['id'] for i in items], ['B2B_SYSTEM', 'B2B_TEMPLATES', 'B2B_USER_GUIDE'])
        self.assertTrue(all(i['available'] and i['editable'] for i in items))
        for channel in ['Website', 'Google Paid Search', 'SMS', 'Email', 'Other']:
            bundle = access.instruction_bundle('b2b', channel, 'fictional business internet')
            self.assertEqual([f['module'] for f in bundle['files']], ['B2B_SYSTEM', 'B2B_TEMPLATES'])
            self.assertNotIn('Administrator-only maintenance guide', bundle['text'])

    def test_every_preserved_block_matches_saved_source_checksum(self):
        root = Path(__file__).resolve().parents[2]
        report = json.loads((root / 'output/b2b-instruction-pack/preservation-report.json').read_text(encoding='utf-8'))
        self.assertGreater(report['preserved_blocks'], 1400)
        # Admins can edit active guidelines. Verify the lossless migration
        # against its saved pack, independently of subsequent authorised edits.
        with zipfile.ZipFile(root / 'output/b2b-instruction-pack/B2B_three_instruction_files.zip') as pack:
            text = {key: pack.read(next(name for name in pack.namelist() if name.endswith(key))).decode('utf-8').replace('\r\n', '\n') for key in report['files']}
        for block in report['blocks']:
            retained = text[block['target']][block['start_character']:block['end_character']]
            self.assertEqual(hashlib.sha256(retained.encode()).hexdigest(), block['sha256'], block['source'])
        with zipfile.ZipFile(root / 'output/b2b-instruction-pack/B2B_original_sources_and_previous_instructions.zip') as archive:
            names = archive.namelist()
            for name in ['LLM Component Library.docx', 'Updated - LLM Component Library.docx', 'Website Content Writing TOV Guide.docx', 'Google Paid Search Ads TOV Guide.docx', 'e& Brand Dictionary & Terms Guide.docx', 'CX writing guidelines_final.pdf', 'e_CX Style Guide.pdf', 'Copy of RW x e_CX Messaging Bank_B2B_12 December 2025.xlsx']:
                self.assertIn('original-sources/' + name, names)
            self.assertIsNone(archive.testzip())

    def test_all_source_cx_pages_have_primary_destination(self):
        root = Path(__file__).resolve().parents[2]
        blocks = json.loads((root / 'output/b2b-instruction-pack/preservation-report.json').read_text(encoding='utf-8'))['blocks']
        pages = [b for b in blocks if b['source'].startswith('CX writing guidelines_final.pdf / page ')]
        self.assertEqual(len(pages), 127)
        for item in pages:
            number = int(re.search(r'/ page (\d+)', item['source'])[1])
            self.assertFalse(item['reference'])
            self.assertEqual(item['target'].startswith('02_'), 22 <= number <= 36 or 115 <= number <= 119)

    def test_website_and_paid_rules_do_not_leak_across_scopes(self):
        website = access.instruction_bundle('b2b', 'Other', 'المكوّن 4')
        paid = access.instruction_bundle('b2b', 'Google Paid Search', 'fictional business internet')
        self.assertEqual(website['files'][-1]['format_scope'], 'website')
        self.assertIn('# B2B Website Tone of Voice', website['text'])
        self.assertIn('### Component 4 —', website['text'])
        self.assertNotIn('### Component 17 —', website['text'])
        self.assertNotIn('# Google Search Ads — Headlines', website['text'])
        self.assertIn('# Google Search Ads — Headlines', paid['text'])
        self.assertNotIn('# B2B Website Tone of Voice', paid['text'])
        self.assertNotIn('### Component 4 — USP Featured', paid['text'])
        self.assertGreater(website['files'][-1]['reference_candidates'], 0)
        self.assertLessEqual(website['files'][-1]['selected_references'], 4)

    def test_components_and_all_index_links_resolve(self):
        definitions = website_component_blocks('b2b')
        self.assertEqual(set(definitions), set(range(1, 18)))
        self.assertEqual(len(output_catalog('b2b')), 17)
        self.assertIn('name not specified in source', definitions[8].lower())
        text = access.instruction_path('B2B_TEMPLATES', 'b2b').read_text(encoding='utf-8')
        anchors = re.findall(r'<a id="([^"]+)"></a>', text)
        self.assertEqual(len(anchors), len(set(anchors)))
        for link in re.findall(r'\]\(#(b2b-[^)]+)\)', text):
            self.assertIn(link, anchors)

    def test_guide_visibility_and_boundary_validation(self):
        for role in ['user']:
            text = admin.get_instruction('b2b', 'B2B_USER_GUIDE', self.user(role))['content']
            self.assertIn('Part A', text)
            self.assertNotIn('Part B', text)
        with self.assertRaises(HTTPException):
            admin.get_instruction('b2b', 'B2B_USER_GUIDE', self.user('approval_admin'))
        self.assertEqual([i['id'] for i in admin.list_channel_instructions('b2b', self.user('user'))['instructions']], ['B2B_USER_GUIDE'])
        with self.assertRaises(HTTPException):
            admin.update_instruction('b2b', 'B2B_USER_GUIDE', admin.InstructionUpdateRequest(content='Private notes'), self.user())
        with self.assertRaises(HTTPException):
            admin.get_instruction('b2b', 'B2C_SYSTEM', self.user())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'guide.md'
            path.write_text('Private notes', encoding='utf-8')
            with patch.object(admin, 'instruction_path', return_value=path):
                self.assertNotIn('Private notes', admin.get_instruction('b2b', 'B2B_USER_GUIDE', self.user('user'))['content'])

    def test_quality_checks_cite_actual_combined_schema(self):
        _, sources = evidence_context('b2b', 'Website', 'Component 4')
        checks = component_length_checks('[COPY READY CONTENT]\nTitle: ' + 'A' * 21 + '\nSub-title: Reliable connectivity\n\n[REFERENCE AND VALIDATION]', '', 'Component 4', 'b2b', sources)
        self.assertTrue(any(c['status'] == 'missing' for c in checks))
        reference = next(c['references'][0]['source_id'] for c in checks if c['status'] == 'missing')
        self.assertEqual(sources[reference]['filename'], '02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md')

    def test_complete_template_remains_editable_and_schema_edits_refresh(self):
        text = access.instruction_path('B2B_TEMPLATES', 'b2b').read_text(encoding='utf-8')
        self.assertGreater(len(text), 1500000)
        self.assertEqual(admin.InstructionUpdateRequest(content=text).content, text)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'b2b'
            directory.mkdir()
            (directory / '01_B2B_SYSTEM_INSTRUCTIONS.md').write_text('# Shared rules', encoding='utf-8')
            path = directory / '02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md'
            path.write_text('### Component 4 — USP Featured\n- Title: mandatory, max 20 characters\n## Validation rules\nCount characters.', encoding='utf-8')
            data = {'channels': [{'id': 'b2b', 'name': 'B2B', 'instruction_modules': []}], 'activity': []}
            with patch.object(access, 'CHANNEL_PROMPT_DIR', directory.parent), patch.object(admin, 'CHANNEL_PROMPT_DIR', directory.parent), patch.object(admin, 'load_access_data', return_value=data), patch.object(admin, 'save_access_data'):
                self.assertIn('max 20', website_component_blocks('b2b')[4])
                revised = path.read_text(encoding='utf-8').replace('max 20', 'max 19')
                admin.update_instruction('b2b', 'B2B_TEMPLATES', admin.InstructionUpdateRequest(content=revised), self.user())
                self.assertIn('max 19', website_component_blocks('b2b')[4])


if __name__ == '__main__':
    unittest.main()
