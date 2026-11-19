import unittest
from io import BytesIO
from docx import Document
from copy_export import create_copy_document

class TableExportTests(unittest.TestCase):
    def test_headings_lists_emphasis_and_code_are_rendered(self):
        text = '# Page title\n\n#### Details\n- First benefit\n2. Second action\nA **bold** and *italic* word with `code`.\n\n```text\n# Literal heading\n| A | B |\n| --- | --- |\n<br>\n```'
        document = Document(BytesIO(create_copy_document([{'text': text, 'language': 'en'}])))
        paragraphs = {p.text: p for p in document.paragraphs}
        self.assertEqual(paragraphs['Page title'].style.name, 'Heading 1')
        self.assertEqual(paragraphs['Details'].style.name, 'Heading 4')
        self.assertEqual(paragraphs['First benefit'].style.name, 'List Bullet')
        self.assertIn('2. Second action', paragraphs)
        inline = paragraphs['A bold and italic word with code.']
        self.assertTrue(next(r for r in inline.runs if r.text == 'bold').bold)
        self.assertTrue(next(r for r in inline.runs if r.text == 'italic').italic)
        self.assertEqual(next(r for r in inline.runs if r.text == 'code').font.name, 'Consolas')
        self.assertTrue(any('# Literal heading' in p and '<br>' in p for p in paragraphs))
        self.assertEqual(len(document.tables), 0)

    def test_automatic_arabic_tables_have_direction_and_fit_the_page(self):
        document = Document(BytesIO(create_copy_document([{'text': '| الحقل | التفاصيل |\n| --- | --- |\n| التوصية | مراجعة المتطلبات |', 'language': 'auto'}])))
        table = document.tables[0]
        self.assertIn('bidiVisual', table._tbl.xml)
        available = document.sections[0].page_width - document.sections[0].left_margin - document.sections[0].right_margin
        self.assertLessEqual(abs(sum(c.width for c in table.columns) - available), 2000)
        self.assertLess(table.columns[0].width, table.columns[1].width)
        self.assertIn('tblHeader', table.rows[0]._tr.xml)

    def test_nested_recommendation_preserves_content(self):
        text = """| Section | Completed memo content |
| --- | --- |
| 1. Details | A **verified** fact<br>Another fact |
| 5. Recommendation | Register the number. |

| # | Recommended Action | Deadline | Action Owner |
| --- | --- | --- | --- |
| 1 | Register A\\|B | To be confirmed | Operations |
"""
        document = Document(BytesIO(create_copy_document([{'text': text, 'language': 'en'}])))
        self.assertEqual(len(document.tables), 1)
        table = document.tables[0]
        self.assertIn('Another fact', table.cell(1, 1).text)
        cell = table.cell(2, 1)
        self.assertIn('Register the number.', cell.text)
        self.assertEqual(len(cell.tables), 1)
        self.assertEqual(cell.tables[0].cell(1, 1).text, 'Register A|B')
        self.assertEqual(cell.tables[0].cell(1, 3).text, 'Operations')

    def test_arabic_table_direction(self):
        document = Document(BytesIO(create_copy_document([{'text': '| الحقل | التفاصيل |\n| --- | --- |\n| العنوان | مذكرة |', 'language': 'ar'}])))
        self.assertIn('bidiVisual', document.tables[0]._tbl.xml)
        self.assertIn('w:bidi', document.tables[0].cell(1, 1)._tc.xml)
        self.assertIn('w:val="start"', document.tables[0].cell(1, 1)._tc.xml)
        self.assertEqual(document.tables[0].cell(1, 1).text, 'مذكرة')

    def test_memo_paragraphs_and_recommendation_table(self):
        text = "# Compliance memo\n\n## 2. Background\nShort factual background.\n\n## 5. Recommendation\nReview the following actions.\n\n| # | Recommended Action | Deadline | Action Owner |\n| --- | --- | --- | --- |\n| 1 | Review compliance | To be confirmed | To be confirmed |"
        document = Document(BytesIO(create_copy_document([{'text': text, 'language': 'en'}])))
        self.assertEqual(len(document.tables), 1)
        self.assertIn('Short factual background.', [p.text for p in document.paragraphs])
        self.assertIn('5. Recommendation', [p.text for p in document.paragraphs])
        self.assertEqual(document.tables[0].cell(1, 1).text, 'Review compliance')
