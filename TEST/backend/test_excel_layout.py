from datetime import datetime
from io import BytesIO
import unittest
from zipfile import ZipFile
from xml.etree import ElementTree

from openpyxl import load_workbook
from copy_export import create_copy_workbook


class ExcelLayoutTests(unittest.TestCase):
    def test_bulk_has_original_id_input_and_output_columns_for_both_languages(self):
        sections = [{'language': language, 'text': text, 'original_id': '0007', 'source_text': '=Original input',
                     'metadata': {'created_by': 'Author', 'created_at': '2026-10-25T16:00:00Z'}}
                    for language, text in [('en', 'New copy'), ('ar', 'النص الجديد')]]
        sheet = load_workbook(BytesIO(create_copy_workbook(sections, include_source=True))).active
        self.assertEqual([cell.value for cell in sheet[1]], ['Output #', 'Original ID', 'Input', 'Output', 'Language', 'Created by', 'Created at', 'Score'])
        for row in [2, 3]:
            self.assertEqual(sheet.cell(row, 2).value, '0007')
            self.assertEqual(sheet.cell(row, 2).data_type, 's')
            self.assertEqual(sheet.cell(row, 3).value, '=Original input')
            self.assertEqual(sheet.cell(row, 3).data_type, 's')
        self.assertEqual(sheet['D2'].value, 'New copy')
        self.assertEqual(sheet['D3'].value, 'النص الجديد')
        self.assertEqual(sheet['E3'].value, 'Arabic')
        self.assertEqual(sheet['D3'].alignment.readingOrder, 2)
        self.assertEqual(sheet['F2'].value, 'Author')

    def test_bulk_legacy_id_is_preserved_and_missing_id_is_not_invented(self):
        sections = [{'text': 'Copy', 'source_text': 'Brief', 'source_metadata': {'REPLY_ID': '0009'}},
                    {'text': 'Other copy', 'source_text': 'Other brief'}]
        sheet = load_workbook(BytesIO(create_copy_workbook(sections, include_source=True))).active
        self.assertEqual(sheet['B2'].value, '0009')
        self.assertIn(sheet['B3'].value, [None, ''])
        self.assertEqual(sheet['C3'].value, 'Other brief')

    def workbook(self, sections):
        return load_workbook(BytesIO(create_copy_workbook(sections)))

    def test_output_sheet_contains_only_copy_and_attribution(self):
        book = self.workbook([{'text': 'Complete copy', 'language': 'en', 'metadata': {
            'created_by': 'Author', 'created_at': '2026-10-23T12:30:45.123456+00:00',
            'sequence_number': 'private-internal-id', 'version': '4', 'status': 'draft',
            'channel': 'b2c', 'product': 'Unknown', 'score': 'Not evaluated', 'reviewed_by': 'Not reviewed',
        }}])
        sheet = book['Outputs']
        self.assertEqual([cell.value for cell in sheet[1]], ['Output', 'Language', 'Generated output', 'Created by', 'Created at', 'Score'])
        self.assertEqual(sheet['C2'].value, 'Complete copy')
        self.assertEqual(sheet['D2'].value, 'Author')
        self.assertEqual(sheet['E2'].value, datetime(2026, 10, 23, 12, 30, 45))
        self.assertEqual(sheet['E2'].number_format, 'yyyy-mm-dd hh:mm:ss')
        self.assertEqual(book.sheetnames, ['Outputs'])

    def test_short_rows_are_compact_and_long_rows_expand_without_dropping_text(self):
        text = ('Complete policy detail, including the original facts.\n' * 45).strip()
        sheet = self.workbook([{'text': 'Short copy'}, {'text': text}])['Outputs']
        self.assertLess(sheet.row_dimensions[2].height, sheet.row_dimensions[3].height)
        self.assertLessEqual(sheet.row_dimensions[3].height, 409)
        self.assertEqual(sheet['C3'].value, text)
        self.assertTrue(sheet['C3'].alignment.wrap_text)

    def test_view_and_print_layout_do_not_lock_the_wide_copy_column(self):
        sheet = self.workbook([{'text': 'Copy'}])['Outputs']
        self.assertEqual(sheet.freeze_panes, 'A2')
        self.assertEqual(sheet.auto_filter.ref, 'A1:F2')
        self.assertFalse(sheet.sheet_view.showGridLines)
        self.assertFalse(sheet.sheet_view.rightToLeft)
        self.assertEqual(sheet.sheet_view.zoomScale, 90)
        self.assertEqual(sheet.page_setup.orientation, 'landscape')
        self.assertEqual(sheet.page_setup.fitToWidth, 1)
        self.assertEqual(len(sheet.merged_cells.ranges), 0)

    def test_arabic_and_english_stay_in_the_same_columns_with_correct_reading_order(self):
        sheet = self.workbook([{'text': 'Welcome', 'language': 'en'}, {'text': 'أهلًا بك', 'language': 'ar'}, {'text': 'النص الأصلي'}])['Outputs']
        self.assertEqual(sheet['B2'].value, 'English')
        self.assertEqual(sheet['B3'].value, 'Arabic')
        self.assertEqual(sheet['C2'].alignment.readingOrder, 1)
        self.assertEqual(sheet['C3'].alignment.readingOrder, 2)
        self.assertEqual(sheet['C3'].alignment.horizontal, 'right')
        self.assertEqual(sheet['C4'].alignment.readingOrder, 2)

    def test_source_identifiers_are_preserved_without_widening_the_output_sheet(self):
        book = self.workbook([{'text': 'Copy', 'source_text': 'Original', 'source_metadata': {
            'REPLY_ID': '00007', 'ACTION': '=HYPERLINK("https://example.test")', '__row': 0,
        }}])
        self.assertEqual(book['Outputs'].max_column, 6)
        references = {row[1].value: row[2] for row in book['Source references'].iter_rows(min_row=2)}
        self.assertEqual(references['REPLY_ID'].value, '00007')
        self.assertEqual(references['ACTION'].data_type, 's')
        self.assertEqual(references['Source row'].value, '0')
        self.assertEqual(references['Original message'].value, 'Original')
        self.assertEqual(book['Source references'].max_column, 3)

    def test_formula_like_copy_is_text_and_xml_controls_are_removed(self):
        sheet = self.workbook([{'text': '=1+1\x00', 'metadata': {'created_by': '=2+2'}}])['Outputs']
        self.assertEqual(sheet['C2'].value, '=1+1')
        self.assertEqual(sheet['C2'].data_type, 's')
        self.assertEqual(sheet['D2'].data_type, 's')

    def test_emoji_cannot_silently_overflow_excel_cell_limits(self):
        with self.assertRaisesRegex(ValueError, '32,767'):
            create_copy_workbook([{'text': '😀' * 17000}])

    def test_bilingual_twenty_output_export_reopens_as_valid_workbook(self):
        sections = [{'language': language, 'text': f'Output {index}\n\n' + ('أهلًا بك.' if language == 'ar' else 'Welcome.')}
                    for index in range(20) for language in ['en', 'ar']]
        content = create_copy_workbook(sections)
        with ZipFile(BytesIO(content)) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                if name.endswith('.xml'): ElementTree.fromstring(archive.read(name))
        sheet = load_workbook(BytesIO(content))['Outputs']
        self.assertEqual(sheet.max_row, 41)
        self.assertEqual(sheet.max_column, 6)
        for row, section in enumerate(sections, 2):
            self.assertEqual(sheet.cell(row, 3).value, section['text'])


if __name__ == '__main__':
    unittest.main()
