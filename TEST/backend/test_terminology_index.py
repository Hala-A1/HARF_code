from pathlib import Path
import tempfile
import unittest

from structure_retrieval import select_instructions


class TerminologyIndexTests(unittest.TestCase):
    def select(self, text, query):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'instructions.md'
            path.write_text(text, encoding='utf-8')
            return select_instructions(path, query)

    def test_b2c_header_retrieves_both_languages_and_distinct_usage(self):
        text = '''# System rules
Never invent claims.
## Consolidated glossary and brand terminology
| Source reference | Category | English | Arabic | Meaning / description | Usage note |
|---|---|---|---|---|---|
| row 2 | Roaming | Abroad | في الخارج | Outside UAE | Travel context |
| row 3 | Account | Balance | الرصيد | Money remaining | Account |
| row 4 | Account | Balance | رصيد البيانات | Data remaining | Data |
| row 5 | Brand | etisalat | اتصالات | Company name | Exact |
| row 6 | Legacy | forbidden spelling | قديم | Restricted | Do not use |
'''
        result, report = self.select(text, 'رصيد البيانات')
        self.assertIn('Data remaining', result)
        self.assertIn('Money remaining', result)
        self.assertIn('Never invent claims.', result)
        self.assertIn('etisalat', result)
        self.assertIn('Do not use', result)
        self.assertNotIn('Outside UAE', result)
        self.assertTrue(report['terminology_entries'])

    def test_brand_dictionary_tables_are_selected_without_filtering_rules(self):
        result, _ = self.select('''# Brand Dictionary
Always preserve exact approved names.
## AI terminology
| Preferred term | Usage |
|---|---|
| generative AI | Technical category |
| sovereign cloud | Hosting category |
''', 'generative AI')
        self.assertIn('generative AI', result)
        self.assertNotIn('sovereign cloud', result)
        self.assertIn('Always preserve exact approved names.', result)

    def test_examples_and_template_tables_are_never_filtered_as_terminology(self):
        text = '# Email instructions\n| English | Arabic |\n|---|---|\n| Mandatory greeting | الترحيب المطلوب |'
        result, _ = self.select(text, 'unrelated')
        self.assertIn('Mandatory greeting', result)

    def test_restriction_headers_pin_all_rows_even_when_term_is_not_in_query(self):
        result, _ = self.select('# Brand terminology\n| Do not use | Use instead |\n|---|---|\n| Legacy label | Current label |', 'unrelated')
        self.assertIn('Legacy label', result)
        self.assertIn('Current label', result)

    def test_updates_rebuild_index_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.md'
            text = '# Glossary\n| English | Arabic |\n|---|---|\n| Roaming | التجوال |'
            path.write_text(text, encoding='utf-8')
            first, old = select_instructions(path, 'roaming')
            self.assertIn('التجوال', first)
            path.write_text(text.replace('التجوال', 'خدمات التجوال'), encoding='utf-8')
            second, updated = select_instructions(path, 'roaming')
            self.assertIn('خدمات التجوال', second)
            self.assertNotEqual(old['version'], updated['version'])
            self.assertNotEqual(old['terminology_entries'][0]['id'], updated['terminology_entries'][0]['id'])

