"""Read message rows without executing formulas or sending operational codes to AI."""
import csv
import io
import json
from datetime import date, datetime
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

from openpyxl import load_workbook

MAX_ROWS = 100000
MAX_COLUMNS = 80
ALIASES = {
    'text': {'replymessage', 'message', 'originalmessage', 'copy', 'text', 'content', 'originalcopy', 'messagetext'},
    'language': {'languageflag', 'language', 'sourcelanguage', 'lang'},
    'id': {'replyid', 'messageid', 'id', 'recordid'},
}


class SpreadsheetImportError(ValueError):
    pass


def key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def cell_text(cell):
    value = cell.value
    if value is None:
        return ''
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = str(int(value)) if float(value).is_integer() else str(value)
        if re.fullmatch(r'0+', cell.number_format or '') and number.isdigit():
            return number.zfill(len(cell.number_format))
        return number
    return str(value)


def header_names(values):
    if len(values) > MAX_COLUMNS:
        raise SpreadsheetImportError('Use at most 80 columns in the message worksheet.')
    names = [str(value or '').strip() or f'Column {i + 1}' for i, value in enumerate(values)]
    normalized = [name.casefold() for name in names]
    if any(name in {'__file', '__sheet', '__row'} for name in names):
        raise SpreadsheetImportError('Rename reserved columns __file, __sheet or __row before importing.')
    if len(set(normalized)) != len(normalized):
        raise SpreadsheetImportError('Each column needs a unique header in the first row. Rename duplicate headers before importing.')
    return names


def import_messages(filename, content, sheet_name='', text_column='', language_column='', id_column='', start_row=2, limit=20):
    suffix = Path(filename).suffix.lower()
    if suffix not in {'.xlsx', '.csv'}:
        raise SpreadsheetImportError('Use an Excel .xlsx workbook or UTF-8 .csv file. Save older .xls files as .xlsx first.')
    if start_row < 2 or start_row > MAX_ROWS + 1 or not 1 <= limit <= 100:
        raise SpreadsheetImportError('Choose a starting row from 2 to 100,001 and up to 100 rows per batch, within your channel limit.')
    workbook = None
    try:
        if suffix == '.xlsx':
            try:
                with ZipFile(io.BytesIO(content)) as archive:
                    if sum(item.file_size for item in archive.infolist()) > 200 * 1024 * 1024:
                        raise SpreadsheetImportError('This workbook expands beyond the supported size. Split it into smaller workbooks.')
                workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
            except (BadZipFile, OSError, KeyError, ValueError) as error:
                if isinstance(error, SpreadsheetImportError):
                    raise
                raise SpreadsheetImportError('The Excel workbook could not be opened. Save a readable, unencrypted .xlsx copy and retry.') from None
            sheets = []
            for sheet in workbook:
                first = next(sheet.iter_rows(min_row=1, max_row=1), ())
                headers = header_names([cell_text(cell) for cell in first])
                sheets.append({'name': sheet.title, 'columns': headers})
            chosen = next((s for s in sheets if s['name'] == sheet_name), None) if sheet_name else next(
                (s for s in sheets if any(key(h) in ALIASES['text'] for h in s['columns'])), sheets[0] if sheets else None)
            if not chosen:
                raise SpreadsheetImportError('The selected worksheet is not available.')
            sheet = workbook[chosen['name']]
            if (sheet.max_row or 0) > MAX_ROWS + 1:
                raise SpreadsheetImportError('Split worksheets above 100,000 data rows into smaller files.')
            if (sheet.max_column or 0) > MAX_COLUMNS:
                raise SpreadsheetImportError('Use at most 80 columns in the message worksheet.')
            def read_rows():
                for number, row in enumerate(sheet.iter_rows(min_row=2, max_row=min(sheet.max_row or MAX_ROWS + 2, MAX_ROWS + 2)), 2):
                    yield number, [cell_text(cell) for cell in row], [cell.data_type == 'f' for cell in row]
            rows = read_rows()
        else:
            try:
                encoding = 'utf-16' if content.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
                decoded = content.decode(encoding)
            except UnicodeError:
                raise SpreadsheetImportError('Save the CSV as UTF-8 so English and Arabic characters can be read correctly.') from None
            try:
                dialect = csv.Sniffer().sniff(decoded[:32000], delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            csv.field_size_limit(2_000_000)
            reader = csv.reader(io.StringIO(decoded, newline=''), dialect)
            headers = header_names(next(reader, []))
            chosen = {'name': 'CSV', 'columns': headers}
            sheets = [chosen]
            rows = ((number, row, [False] * len(row)) for number, row in enumerate(reader, 2))
        columns = chosen['columns']
        if not columns:
            raise SpreadsheetImportError('The first row must contain column headers.')
        mapping = {}
        for kind, selected in [('text', text_column), ('language', language_column), ('id', id_column)]:
            if selected and selected not in columns:
                raise SpreadsheetImportError(f'The selected {kind} column is not in this worksheet.')
            mapping[kind] = selected or next((name for name in columns if key(name) in ALIASES[kind]), '')
        result = dict(filename=Path(filename).name, sheet=chosen['name'], sheets=sheets, columns=columns,
                      mapping=mapping, rows=[], total_messages=0, skipped_blank=0, start_row=start_row, next_row=None, warnings=[])
        if not mapping['text']:
            result['warnings'].append('Choose the column containing the original messages, then preview the rows.')
            return result
        text_index = columns.index(mapping['text'])
        duplicate_ids, seen_ids, unknown_languages, formula_rows = 0, set(), 0, 0
        for number, values, formulas in rows:
            if number > MAX_ROWS + 1:
                if any(values):
                    raise SpreadsheetImportError('Split worksheets above 100,000 data rows into smaller files.')
                continue
            if len(values) > len(columns) and any(values[len(columns):]):
                raise SpreadsheetImportError(f'Row {number} has data beyond the header columns. Give every column a header.')
            values += [''] * (len(columns) - len(values))
            record = dict(zip(columns, values))
            text = record[mapping['text']]
            if not text.strip():
                result['skipped_blank'] += 1
                continue
            result['total_messages'] += 1
            raw_language = record.get(mapping['language'], '').strip().lower()
            language = {'english': 'en', 'en-us': 'en', 'en-gb': 'en', 'arabic': 'ar', 'ar-ae': 'ar'}.get(raw_language, raw_language)
            language = language if language in {'en', 'ar'} else ''
            if not language:
                unknown_languages += 1
            identity = record.get(mapping['id'], '').strip()
            if identity:
                identity_key = (identity, language)
                duplicate_ids += int(identity_key in seen_ids)
                seen_ids.add(identity_key)
            if number < start_row:
                continue
            if len(result['rows']) >= limit:
                if result['next_row'] is None:
                    result['next_row'] = number
                continue
            if text_index < len(formulas) and formulas[text_index]:
                formula_rows += 1
                continue
            if len(text) > 200000:
                raise SpreadsheetImportError(f'Message at row {number} exceeds 200,000 characters. Split it before importing.')
            metadata = {name: value for name, value in record.items() if name != mapping['text']}
            metadata.update({'__file': Path(filename).name, '__sheet': chosen['name'], '__row': str(number)})
            if len(json.dumps(metadata, ensure_ascii=False)) > 128000:
                raise SpreadsheetImportError(f'Row {number} contains too much metadata. Remove unrelated columns from the import copy.')
            name = f'{Path(filename).stem} — {chosen["name"]} row {number}'
            if identity:
                name += f' — ID {identity}'
            extra = next((value for header, value in record.items() if key(header) in {'extrainstructions', 'specificinstructions'}), '')
            if len(extra) > 4000:
                raise SpreadsheetImportError(f'Extra instructions at row {number} exceed 4,000 characters.')
            result['rows'].append(dict(row_number=number, filename=name[:240], text=text, source_language=language, source_id=identity,
                                       source_metadata=metadata, row_instructions=extra,
                                       size_bytes=len(text.encode('utf-8')), content_type='text/plain'))
        if duplicate_ids:
            result['warnings'].append(f'{duplicate_ids} repeated ID/language combinations were found; worksheet row numbers keep records distinct.')
        if unknown_languages:
            result['warnings'].append(f'{unknown_languages} rows have no recognized source-language flag. Those rows use your selected output languages.')
        if formula_rows:
            result['warnings'].append(f'{formula_rows} message cells contain formulas and were skipped. Paste their saved results as values to import them.')
        if result['skipped_blank']:
            result['warnings'].append(f'{result["skipped_blank"]} blank message rows were skipped.')
        return result
    finally:
        if workbook:
            workbook.close()
