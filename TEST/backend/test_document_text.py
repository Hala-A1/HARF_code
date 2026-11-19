import io
import unittest
from unittest.mock import patch
from docx import Document
from docx.oxml import OxmlElement
from document_text import word_text, decode_text


class DocumentTextTests(unittest.TestCase):
    def test_multilingual_word_all_stories_and_nested_tables(self):
        doc = Document()
        doc.add_paragraph('English العربية ١٢٣ 123')
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.text = 'السعر AED 25'
        cell.add_table(rows=1, cols=1).cell(0, 0).text = 'Nested تفاصيل'
        doc.sections[0].header.paragraphs[0].text = 'Header الترويسة'
        doc.sections[0].footer.paragraphs[0].text = 'Footer تذييل'
        box = OxmlElement('w:txbxContent')
        p = OxmlElement('w:p'); r = OxmlElement('w:r'); t = OxmlElement('w:t')
        t.text = 'Textbox ملاحظة'; r.append(t); p.append(r); box.append(p)
        doc.paragraphs[0]._p.append(box)
        content = io.BytesIO(); doc.save(content)
        text = word_text(content.getvalue())
        for expected in ['English العربية ١٢٣ 123', 'السعر AED 25', 'Nested تفاصيل',
                         'Header الترويسة', 'Footer تذييل', 'Textbox ملاحظة']:
            self.assertEqual(text.count(expected), 1)

    def test_unicode_text_encodings(self):
        text = 'مرحبا English ١٢٣'
        for encoding in ['utf-8-sig', 'utf-16']:
            self.assertEqual(decode_text(text.encode(encoding)), text)
        with self.assertRaises(UnicodeDecodeError):
            decode_text(b'\xffinvalid')

    def test_pdf_uses_scan_path_without_docling(self):
        from ai_service import extract_uploaded_content
        with patch('scan_ocr.extract_scan_if_needed', return_value='Page 1 English\nPage 2 العربية'):
            self.assertEqual(extract_uploaded_content('mixed.pdf', '', b'pdf'),
                             'Page 1 English\nPage 2 العربية')

    def test_screenshot_prompt_preserves_all_source_languages(self):
        from ai_service import extract_uploaded_content
        with patch('ai_service._run_completion', return_value='نص English') as completion:
            self.assertEqual(extract_uploaded_content('scan.png', 'image/png', b'image'), 'نص English')
            prompt = completion.call_args.args[0]
            self.assertIn('Arabic and English', prompt)
            self.assertIn('footnotes', prompt)
            self.assertIn('do not translate', prompt)
