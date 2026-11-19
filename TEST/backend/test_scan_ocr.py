import io
import unittest
import threading
from contextvars import ContextVar
from unittest.mock import patch, MagicMock

from PIL import Image
import scan_ocr
from docling_client import extract_document, DoclingError


class ScanOCRTests(unittest.TestCase):
    def test_long_scan_overlaps_two_pages_preserves_order_and_channel_context(self):
        context = ContextVar('scan_test_context', default='missing')
        token = context.set('channel scope')
        lock = threading.Lock()
        started = threading.Event()
        active = peak = 0
        def transcribe(image, timeout):
            nonlocal active, peak
            self.assertEqual(context.get(), 'channel scope')
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 2: started.set()
            try:
                self.assertTrue(started.wait(2))
                return f'Page content {image}'
            finally:
                with lock: active -= 1
        try:
            with patch.object(scan_ocr, 'page_inventory', return_value=[('', True)] * 3), patch.object(scan_ocr, 'render_page', side_effect=lambda content, index: index), patch.object(scan_ocr, 'transcribe_page', side_effect=transcribe):
                result = scan_ocr.extract_scan_if_needed(b'pdf')
            self.assertEqual(peak, 2)
            self.assertLess(result.index('content 0'), result.index('content 1'))
            self.assertLess(result.index('content 1'), result.index('content 2'))
        finally:
            context.reset(token)
    def test_real_image_only_pdf_is_detected_and_rendered(self):
        image = Image.new('RGB', (800, 1100), 'white')
        output = io.BytesIO()
        image.save(output, format='PDF', resolution=150)
        image.close()
        pages = scan_ocr.page_inventory(output.getvalue())
        self.assertEqual(pages, [('', True)])
        rendered = scan_ocr.render_page(output.getvalue(), 0)
        with Image.open(io.BytesIO(rendered)) as result:
            self.assertLessEqual(max(result.size), 2601)
            self.assertEqual(result.format, 'PNG')

    def test_mixed_pdf_preserves_page_order_and_ocr_only_scans(self):
        with patch.object(scan_ocr, 'page_inventory', return_value=[('Native page', False), ('Footer', True), ('Last page', False)]), patch.object(scan_ocr, 'render_page', return_value=b'image') as render, patch.object(scan_ocr, 'transcribe_page', return_value='السعر: 100 درهم') as transcribe:
            result = scan_ocr.extract_scan_if_needed(b'pdf')
        self.assertEqual(result, '## Source page 1\nNative page\n\n## Source page 2\nالسعر: 100 درهم\n\n## Source page 3\nLast page')
        render.assert_called_once_with(b'pdf', 1)
        transcribe.assert_called_once()

    def test_readable_pdf_never_uses_image_ai(self):
        with patch.object(scan_ocr, 'page_inventory', return_value=[('Readable Arabic العربية', False)]), patch.object(scan_ocr, 'transcribe_page') as ai:
            self.assertIsNone(scan_ocr.extract_scan_if_needed(b'pdf'))
        ai.assert_not_called()

    def test_failed_page_does_not_return_partial_document_and_releases_slot(self):
        with patch.object(scan_ocr, 'page_inventory', return_value=[('', True), ('', True)]), patch.object(scan_ocr, 'render_page', return_value=b'image'), patch.object(scan_ocr, 'transcribe_page', side_effect=['First page', ValueError('service failed')]):
            with self.assertRaisesRegex(scan_ocr.ScanOCRError, 'Page 2.*no partial document'):
                scan_ocr.extract_scan_if_needed(b'pdf')
        self.assertTrue(scan_ocr._OCR_SLOTS.acquire(blocking=False))
        scan_ocr._OCR_SLOTS.release()

    def test_large_scan_is_rejected_before_any_ai_calls(self):
        with patch.dict('os.environ', {'SCAN_OCR_MAX_PAGES': '1'}), patch.object(scan_ocr, 'page_inventory', return_value=[('', True), ('', True)]), patch.object(scan_ocr, 'transcribe_page') as ai:
            with self.assertRaisesRegex(scan_ocr.ScanOCRError, 'at most 1 scanned pages'):
                scan_ocr.extract_scan_if_needed(b'pdf')
        ai.assert_not_called()

    def test_truncated_vision_response_is_not_accepted(self):
        choice = MagicMock(finish_reason='length')
        with patch.object(scan_ocr, 'image_views', return_value=[]), patch('ai_service.get_client') as client, patch('ai_service.get_model', return_value='configured-model'):
            client.return_value.__enter__.return_value.with_options.return_value.chat.completions.create.return_value.choices = [choice]
            with self.assertRaisesRegex(scan_ocr.ScanOCRError, 'too dense'):
                scan_ocr.transcribe_page(b'png', 30)

    def test_arabic_numerals_and_decimal_values_are_compared_without_changing_values(self):
        self.assertEqual(scan_ocr.numeric_values('١٢٣٤٥٦ ١٠٠٫٥٠ 1,000'), scan_ocr.numeric_values('123456 100.50 1000'))
        self.assertNotEqual(scan_ocr.numeric_values('١٢٢٤٥٦'), scan_ocr.numeric_values('123456'))

    def test_source_grounded_verification_counts_repeated_body_values_and_headings_locally(self):
        raw='{"uncertain":false,"headings":["المادة (1)","المادة (2)"],"lines":["1.2.2 3GPP outside 3GPP", "3.2.2 Price 100 and 100", "-41.3 dBm"]}'
        result=scan_ocr.verified_numbers(raw)
        self.assertEqual(result,scan_ocr.numeric_values('المادة (1) المادة (2) 1.2.2 3GPP outside 3GPP 3.2.2 Price 100 and 100 -41.3 dBm'))
        self.assertEqual(result['100'],2)
        self.assertEqual(result['3'],2)
        self.assertIn('-41.3',result)
        self.assertEqual(scan_ocr.verified_numbers('{"headings":["Article"],"lines":["Nothing numeric","Price 100"]}'),scan_ocr.numeric_values('100'))
        for raw in ['{"lines":[100]}', '{"headings":"Article 1","lines":[]}', '{"uncertain":true,"lines":["100"]}']:
            with self.assertRaises(scan_ocr.ScanOCRError):scan_ocr.verified_numbers(raw)

    def test_numeric_disagreement_triggers_fresh_read_and_never_accepts_unchecked_digits(self):
        for reread, passes in [('رقم الحساب: ١٢٣٤٥٦', True), ('رقم الحساب: ١٢٢٤٥٦', False)]:
            with self.subTest(passes=passes), patch.object(scan_ocr, 'image_views', return_value=[]), patch('ai_service.get_client') as client, patch('ai_service.get_model', return_value='configured-model'):
                create = client.return_value.__enter__.return_value.with_options.return_value.chat.completions.create
                responses = ['رقم الحساب: ١٢٢٤٥٦', '{"numbers":["123456"]}', reread]
                if not passes: responses.append('{"numbers":["123456"]}')
                create.side_effect = [MagicMock(choices=[MagicMock(finish_reason='stop', message=MagicMock(content=text))]) for text in responses]
                if passes:
                    self.assertEqual(scan_ocr.transcribe_page(b'png', 30), reread)
                else:
                    with self.assertRaisesRegex(scan_ocr.ScanOCRError, 'Numeric readings disagree'):
                        scan_ocr.transcribe_page(b'png', 30)
                self.assertEqual(create.call_count, 3 if passes else 4)

    def transcribe_responses(self, responses):
        with patch.object(scan_ocr, 'image_views', return_value=[]), patch('ai_service.get_client') as client, patch('ai_service.get_model', return_value='configured-model'):
            create = client.return_value.__enter__.return_value.with_options.return_value.chat.completions.create
            create.side_effect = [MagicMock(choices=[MagicMock(finish_reason='stop', message=MagicMock(content=text))]) for text in responses]
            result = scan_ocr.transcribe_page(b'png', 30)
            return result, create.call_args_list

    def test_invalid_numeric_verifier_retries_without_discarding_good_transcription(self):
        result, calls = self.transcribe_responses(['قرار 35 لسنة 2023 UWB', '{"numbers":["35","2023","UWB"]}', '{"uncertain":false,"numbers":["35","2023"]}'])
        self.assertEqual(result, 'قرار 35 لسنة 2023 UWB')
        self.assertEqual(len(calls), 3)
        self.assertNotIn('قرار 35', str(calls[2].kwargs['messages']))

    def test_wrong_first_verifier_is_not_a_permanent_veto(self):
        result, calls = self.transcribe_responses(['تاريخ 7 أكتوبر 2023', '{"numbers":["17","2023"]}', 'تاريخ 7 أكتوبر 2023', '{"numbers":["7","2023"]}'])
        self.assertEqual(result, 'تاريخ 7 أكتوبر 2023')
        self.assertEqual(len(calls), 4)

    def test_numeric_verifier_receives_only_full_page_and_no_proposed_transcription(self):
        views=[{'type':'image_url','image_url':{'url':'full-page'}},
               {'type':'image_url','image_url':{'url':'overlapping-crop'}}]
        with patch.object(scan_ocr,'image_views',return_value=views), patch('ai_service.get_client') as client, patch('ai_service.get_model',return_value='configured-model'):
            create=client.return_value.__enter__.return_value.with_options.return_value.chat.completions.create
            create.side_effect=[MagicMock(choices=[MagicMock(finish_reason='stop',message=MagicMock(content=text))])
                                for text in ['PRIVATE TEXT 1.2.2 3GPP 3GPP 2003','{"uncertain":false,"numbers":["1.2.2","3","3","2003"]}']]
            self.assertEqual(scan_ocr.transcribe_page(b'png',30),'PRIVATE TEXT 1.2.2 3GPP 3GPP 2003')
            transcription=create.call_args_list[0].kwargs['messages'][1]['content']
            verification=create.call_args_list[1].kwargs['messages'][1]['content']
            self.assertEqual(transcription[1:],views)
            self.assertEqual(verification[1:],views[:1])
            self.assertNotIn('PRIVATE TEXT',str(verification))
            self.assertEqual(create.call_count,2)

    def test_uncertain_rechecks_still_block_and_values_are_never_silently_ignored(self):
        for raw in ['{"numbers":["35","UWB"]}', '{"uncertain":true,"numbers":[]}', '{"numbers":[35]}']:
            with self.subTest(raw=raw), self.assertRaises(scan_ocr.ScanOCRError):
                scan_ocr.verified_numbers(raw)

    def test_duplicate_article_and_list_labels_do_not_block_verified_body_numbers(self):
        text = 'المادة (1)\nالمادة (2)\n1. القرار 55 لسنة 2020\n2. النشر في 2023'
        result, calls = self.transcribe_responses([text, '{"numbers":["1","2","55","2020","2023"]}', text])
        self.assertEqual(result, text)
        self.assertEqual(len(calls), 3)
        self.assertEqual(scan_ocr.numeric_values(result)['1'], 2)
        self.assertNotEqual(scan_ocr.numeric_content_values('1. Value 100\n2. Value 100'), scan_ocr.numeric_values('100'))

    def test_structural_exception_never_hides_a_different_digit_or_missing_repeated_price(self):
        self.assertFalse(scan_ocr.structural_count_agreement('1. Account 122456', '1. Account 122456', scan_ocr.numeric_values('123456')))
        self.assertFalse(scan_ocr.structural_count_agreement('1. Price 100\n2. Price 100', '1. Price 100\n2. Price 100', scan_ocr.numeric_values('100')))
        self.assertEqual(scan_ocr.numeric_content_values('1.5 MHz\n125. account'), scan_ocr.numeric_values('1.5 125'))

    def test_negative_power_limits_remain_distinct_and_ranges_do_not_create_negative_values(self):
        self.assertNotEqual(scan_ocr.numeric_values('-41.3 dBm'), scan_ocr.numeric_values('41.3 dBm'))
        self.assertEqual(scan_ocr.numeric_values('−٤١٫٣ dBm'), scan_ocr.verified_numbers('{"numbers":["-41.3"]}'))
        self.assertEqual(scan_ocr.numeric_values('3-5 GHz; 2023-10-17'), scan_ocr.numeric_values('3 5 2023 10 17'))

    def test_parallel_failure_still_discards_the_whole_document_and_releases_slot(self):
        def fail(image, timeout):
            if image == 1: raise scan_ocr.ScanOCRError('Uncertain numbers')
            return 'Complete page'
        with patch.object(scan_ocr, 'page_inventory', return_value=[('', True)] * 3), patch.object(scan_ocr, 'render_page', side_effect=lambda content, index: index), patch.object(scan_ocr, 'transcribe_page', side_effect=fail):
            with self.assertRaisesRegex(scan_ocr.ScanOCRError, 'Page 2: Uncertain numbers'):
                scan_ocr.extract_scan_if_needed(b'pdf')
        self.assertTrue(scan_ocr._OCR_SLOTS.acquire(blocking=False))
        scan_ocr._OCR_SLOTS.release()


class ScanRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_pdf_fallback_returns_complete_text_before_docling_call(self):
        with patch.dict('os.environ', {'DOCLING_DO_OCR': 'true', 'SCAN_OCR_FALLBACK_ENABLED': 'true'}), patch.object(scan_ocr, 'extract_scan_if_needed', return_value='نص عربي') as scan, patch('docling_client.httpx.AsyncClient') as remote:
            self.assertEqual(await extract_document('scan.pdf', b'pdf', 'application/pdf'), 'نص عربي')
            scan.assert_called_once()
            remote.assert_not_called()

    async def test_scan_failure_is_a_safe_document_error(self):
        with patch.dict('os.environ', {'DOCLING_DO_OCR': 'true', 'SCAN_OCR_FALLBACK_ENABLED': 'true'}), patch.object(scan_ocr, 'extract_scan_if_needed', side_effect=scan_ocr.ScanOCRError('Page 2 could not be scanned.')):
            with self.assertRaisesRegex(DoclingError, 'Page 2'):
                await extract_document('scan.pdf', b'pdf', 'application/pdf')


if __name__ == '__main__':
    unittest.main()
