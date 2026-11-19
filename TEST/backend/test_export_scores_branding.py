from io import BytesIO
import unittest

from docx import Document
from openpyxl import load_workbook
from copy_export import create_copy_document, create_copy_workbook
from channel_branding import instruction_labels, rename_channel_records


class ExportScoresAndBrandingTests(unittest.TestCase):
    def test_partial_score_remains_numeric_with_a_visible_excel_comment(self):
        sheet = load_workbook(BytesIO(create_copy_workbook([{'text': 'Long document', 'metadata': {'score': '8 / 10 (partial AI assessment)'}}]))).active
        self.assertEqual(sheet['F2'].value, 8)
        self.assertIn('Partial AI assessment', sheet['F2'].comment.text)

    def test_each_output_has_its_own_numeric_score_and_missing_or_stale_status(self):
        sections = [{'text': 'English', 'language': 'en', 'metadata': {'score': '9.2 / 10 (AI assessment)'}},
                    {'text': 'العربية', 'language': 'ar', 'metadata': {'score': '85% (AI assessment)'}},
                    {'text': 'Unreviewed'}, {'text': 'Edited', 'metadata': {'score': 'Not re-evaluated after editing'}}]
        for include_source, col in [(False, 'F'), (True, 'H')]:
            sheet = load_workbook(BytesIO(create_copy_workbook(sections, include_source=include_source))).active
            self.assertEqual(sheet[f'{col}1'].value, 'Score')
            self.assertEqual(sheet[f'{col}2'].value, 9.2)
            self.assertEqual(sheet[f'{col}3'].value, 8.5)
            self.assertIn('/ 10', sheet[f'{col}2'].number_format)
            self.assertEqual(sheet[f'{col}4'].value, 'Not evaluated')
            self.assertEqual(sheet[f'{col}5'].value, 'Not re-evaluated after editing')
        doc = Document(BytesIO(create_copy_document(sections)))
        scores = [p.text for p in doc.paragraphs if p.text.startswith('Score:')]
        self.assertEqual(len(scores), 4)
        self.assertIn('9.2 / 10', scores[0])
        self.assertEqual(scores[2], 'Score: Not evaluated')

    def test_rename_retains_ids_accounts_history_and_real_source_references(self):
        data = {'channels': [{'id': 'security', 'name': 'Security'}, {'id': 'b2c', 'name': 'B2C'}],
                'users': [{'channel_id': 'security', 'email': 'security.admin@eand.ae', 'name': 'Security Admin', 'password_hash': 'same'}],
                'approval_batches': [{'channel_id': 'security', 'id': 'original'}]}
        self.assertTrue(rename_channel_records(data))
        self.assertEqual(data['channels'][0]['name'], 'Regulatory Compliance')
        self.assertEqual(data['users'][0]['name'], 'Regulatory Compliance Admin')
        self.assertEqual(data['users'][0]['email'], 'security.admin@eand.ae')
        self.assertEqual(data['users'][0]['password_hash'], 'same')
        self.assertEqual(data['approval_batches'][0]['id'], 'original')
        self.assertFalse(rename_channel_records(data))
        text = instruction_labels('# Security\nSECURITY-TEMPLATE-001\n<a id="security-admin-only"></a>\n01_SECURITY_SYSTEM_INSTRUCTIONS.md\nmomosecurity.docx')
        self.assertIn('Regulatory Compliance', text)
        self.assertIn('01_REGULATORY_COMPLIANCE_SYSTEM_INSTRUCTIONS.md', text)
        self.assertIn('REGULATORY-COMPLIANCE-TEMPLATE-001', text)
        self.assertIn('id="regulatory-compliance-admin-only"', text)
        self.assertIn('momosecurity.docx', text)
