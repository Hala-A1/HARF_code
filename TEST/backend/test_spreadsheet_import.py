import asyncio
from io import BytesIO
import unittest

from fastapi import HTTPException, UploadFile
from openpyxl import Workbook, load_workbook

from copy_export import create_copy_workbook
from copywriter import import_spreadsheet
from spreadsheet_import import import_messages, SpreadsheetImportError


def workbook_bytes(rows, title='Messages'):
    book = Workbook()
    book.active.title = title
    for row in rows:
        book.active.append(row)
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


class SpreadsheetImportTests(unittest.TestCase):
    def test_message_mapping_preserves_ids_codes_languages_and_placeholders(self):
        data = workbook_bytes([
            ['REPLY_ID', 'SYSTEM_REPLY_CODE', 'REPLY_MESSAGE', 'LANGUAGE_FLAG'],
            ['0007', '00', 'Balance $REMAININGVOLUMEMB$ valid until $expiryDateTime$.', 'en'],
            ['0008', '01', 'الرصيد المتبقي $REMAININGVOLUMEMB$', 'ar'],
        ])
        result = import_messages('messages.xlsx', data)
        self.assertEqual(result['total_messages'], 2)
        self.assertEqual(result['rows'][0]['source_metadata']['REPLY_ID'], '0007')
        self.assertEqual(result['rows'][0]['source_id'], '0007')
        self.assertEqual(result['rows'][0]['source_metadata']['SYSTEM_REPLY_CODE'], '00')
        self.assertNotIn('REPLY_MESSAGE', result['rows'][0]['source_metadata'])
        self.assertIn('$expiryDateTime$', result['rows'][0]['text'])
        self.assertEqual(result['rows'][1]['source_language'], 'ar')

    def test_formatted_numeric_codes_keep_leading_zeros(self):
        book = Workbook()
        book.active.append(['REPLY_ID', 'SYSTEM_REPLY_CODE', 'REPLY_MESSAGE'])
        book.active.append([7, 0, 'Original copy'])
        book.active['A2'].number_format = '0000'
        book.active['B2'].number_format = '00'
        output = BytesIO(); book.save(output); book.close()
        row = import_messages('messages.xlsx', output.getvalue())['rows'][0]
        self.assertEqual(row['source_metadata']['REPLY_ID'], '0007')
        self.assertEqual(row['source_metadata']['SYSTEM_REPLY_CODE'], '00')

    def test_row_pagination_does_not_skip_rows_and_respects_remaining_capacity(self):
        data = workbook_bytes([['REPLY_MESSAGE']] + [[f'Message {i}'] for i in range(1, 46)])
        first = import_messages('messages.xlsx', data)
        second = import_messages('messages.xlsx', data, start_row=first['next_row'])
        self.assertEqual(first['next_row'], 22)
        self.assertEqual(second['rows'][0]['text'], 'Message 21')
        self.assertEqual(second['next_row'], 42)
        self.assertEqual(len(import_messages('messages.xlsx', data, limit=3)['rows']), 3)

    def test_utf8_csv_handles_arabic_quotes_embedded_newlines_and_codes(self):
        data = '\ufeffREPLY_ID,REPLY_MESSAGE,LANGUAGE_FLAG,SYSTEM_REPLY_CODE\r\n0007,"مرحبا،\nالرصيد 100 درهم",ar,00\r\n'.encode('utf-8')
        result = import_messages('messages.csv', data)
        self.assertEqual(result['rows'][0]['text'], 'مرحبا،\nالرصيد 100 درهم')
        self.assertEqual(result['rows'][0]['source_metadata']['SYSTEM_REPLY_CODE'], '00')

    def test_worksheet_selection_avoids_summary_and_duplicate_sheets(self):
        book = Workbook(); book.active.title = 'Summary'; book.active.append(['System', 'Owner']); book.active.append(['COMS', 'Team'])
        for name in ['Messages', 'Messages (2)']:
            sheet = book.create_sheet(name); sheet.append(['REPLY_MESSAGE']); sheet.append(['Original copy'])
        output = BytesIO(); book.save(output); book.close()
        result = import_messages('messages.xlsx', output.getvalue())
        self.assertEqual(result['sheet'], 'Messages')
        self.assertEqual(len(result['rows']), 1)
        other = import_messages('messages.xlsx', output.getvalue(), sheet_name='Summary')
        self.assertFalse(other['mapping']['text'])
        self.assertFalse(other['rows'])

    def test_custom_columns_can_be_mapped_without_renaming_the_workbook(self):
        data = workbook_bytes([['Draft', 'Locale', 'Reference'], ['A copy', 'English', '0007']])
        result = import_messages('messages.xlsx', data, text_column='Draft', language_column='Locale', id_column='Reference')
        self.assertEqual(result['rows'][0]['source_language'], 'en')
        self.assertIn('ID 0007', result['rows'][0]['filename'])

    def test_blank_cells_are_skipped_and_formulas_are_not_executed(self):
        data = workbook_bytes([['REPLY_MESSAGE'], [''], ['=1+1'], ['Valid copy']])
        result = import_messages('messages.xlsx', data)
        self.assertEqual([row['text'] for row in result['rows']], ['Valid copy'])
        self.assertTrue(any('formulas' in warning for warning in result['warnings']))
        self.assertEqual(result['skipped_blank'], 1)

    def test_duplicate_ids_do_not_merge_unrelated_records(self):
        data = workbook_bytes([['REPLY_ID', 'REPLY_MESSAGE', 'LANGUAGE_FLAG'], ['7', 'First', 'en'], ['7', 'Second', 'en']])
        result = import_messages('messages.xlsx', data)
        self.assertEqual(len(result['rows']), 2)
        self.assertNotEqual(result['rows'][0]['filename'], result['rows'][1]['filename'])
        self.assertTrue(any('repeated ID' in warning for warning in result['warnings']))

    def test_invalid_mapping_headers_and_old_excel_are_reported(self):
        for name, data, options in [
            ('legacy.xls', b'invalid', {}),
            ('messages.xlsx', workbook_bytes([['Text', 'Text'], ['A', 'B']]), {}),
            ('messages.csv', b'REPLY_MESSAGE\nCopy', {'text_column': 'Missing'}),
        ]:
            with self.subTest(name=name), self.assertRaises(SpreadsheetImportError):
                import_messages(name, data, **options)

    def test_source_metadata_exports_without_formula_execution_or_changed_output_position(self):
        sections = [{'language': 'ar', 'text': 'النص الجديد', 'source_text': 'النص الأصلي',
                     'source_metadata': {'REPLY_ID': '0007', 'SYSTEM_REPLY_CODE': '00', 'SYSTEM_ACTION': '=1+1', '__row': '2'}}]
        book = load_workbook(BytesIO(create_copy_workbook(sections)))
        sheet = book.active
        self.assertEqual(sheet['C2'].value, 'النص الجديد')
        self.assertEqual(sheet.max_column, 6)
        references = {row[1].value: row[2] for row in book['Source references'].iter_rows(min_row=2)}
        self.assertEqual(references['REPLY_ID'].value, '0007')
        self.assertEqual(references['SYSTEM_REPLY_CODE'].value, '00')
        self.assertEqual(references['Original message'].value, 'النص الأصلي')
        self.assertEqual(references['SYSTEM_ACTION'].data_type, 's')

    def test_import_endpoint_enforces_channel_access_before_reading_file(self):
        file = UploadFile(filename='messages.csv', file=BytesIO(b'REPLY_MESSAGE\nCopy'))
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(import_spreadsheet(file=file, team_channel='security', user={
                'email': 'user@example.test', 'role': 'user', 'channel_id': 'b2c', 'workspaces': ['rewrite']}))
        self.assertEqual(caught.exception.status_code, 403)
