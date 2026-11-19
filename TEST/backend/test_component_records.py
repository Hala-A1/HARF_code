import unittest
import json
from unittest.mock import patch

import ai_service as ai
from component_records import render_record, split_bilingual_record
from component_records import ComponentResponseError


class ComponentRecordTests(unittest.TestCase):
    def test_shared_bilingual_cards_keep_identities_and_card_count(self):
        fields = [{'label': 'Title', 'value': {'english': 'Daily backup', 'arabic': 'نسخ يومي'}},
                  {'label': 'Description', 'value': {'english': 'Restore files quickly', 'arabic': 'استعادة الملفات بسرعة'}}]
        record = {'component_name': {'english': 'Image cards', 'arabic': 'بطاقات الصور'},
                  'cards': [{'name': {'english': 'First', 'arabic': 'الأولى'}, 'fields': fields},
                            {'name': {'english': 'Second', 'arabic': 'الثانية'}, 'fields': fields}]}
        split = split_bilingual_record(record)
        self.assertEqual(len(split['english']['cards']), len(split['arabic']['cards']))
        with patch.object(ai, '_run_completion', return_value=json.dumps(record)) as completion:
            result = ai.enhance_bilingual_feedback('Daily backup and fast restore.', instructions='Component 9')
        self.assertEqual(completion.call_count, 1)
        self.assertEqual(result['english'].count('### Card'), 2)
        self.assertEqual(result['arabic'].count('### البطاقة'), 2)
        self.assertIn('العنوان: نسخ يومي', result['arabic'])

    def test_shared_record_missing_language_preserves_complete_language(self):
        record = {'cards': [{'fields': [{'label': 'Title', 'value': {'english': 'Daily backup'}}]}]}
        split = split_bilingual_record(record)
        self.assertTrue(split['english'])
        self.assertFalse(split['arabic'])

    def record(self, language='en'):
        return {'component_name': 'بطاقات الصور' if language == 'ar' else 'Component 9', 'cards': [{'fields': [
            {'label': 'Title', 'value': 'نسخ يومي' if language == 'ar' else 'Daily backup'},
            {'label': 'Description', 'value': 'استعادة الملفات بسرعة' if language == 'ar' else 'Restore files quickly'},
            {'label': 'Image', 'value': 'متوفرة بشكل منفصل' if language == 'ar' else 'Supplied separately'},
        ]}]}

    def test_invalid_card_structure_is_retried_and_not_returned_as_raw_json(self):
        component = ai.detect_website_component('Component 9', 'b2b')
        with patch.object(ai, '_run_completion', side_effect=['{"cards":[{}]}', json.dumps(self.record())]) as completion:
            result = ai._component_validated_completion('Rules', 'Daily backup and fast restore.', component)
        self.assertEqual(completion.call_count, 2)
        self.assertIn('Title: Daily backup', result)

    def test_bilingual_recovery_preserves_valid_language(self):
        initial = {'english': self.record(), 'arabic': {'cards': [{}]}}
        with patch.object(ai, '_run_completion', side_effect=[json.dumps(initial), json.dumps(self.record('ar'))]) as completion:
            result = ai.enhance_bilingual_feedback('Daily backup and fast restore.', instructions='Component 9')
        self.assertEqual(completion.call_count, 2)
        self.assertIn('Title: Daily backup', result['english'])
        self.assertIn('العنوان: نسخ يومي', result['arabic'])

    def test_malformed_bilingual_json_recovers_languages_independently(self):
        with patch.object(ai, '_run_completion', side_effect=['{"english":', json.dumps(self.record()), json.dumps(self.record('ar'))]) as completion:
            result = ai.enhance_bilingual_feedback('Daily backup and fast restore.', instructions='Component 9')
        self.assertEqual(completion.call_count, 3)
        self.assertIn('العنوان: نسخ يومي', result['arabic'])

    def test_invalid_response_recovery_is_bounded_and_classified(self):
        from stream_errors import stream_error_details
        component = ai.detect_website_component('Component 9', 'b2b')
        with patch.object(ai, '_run_completion', return_value='{"cards": []}') as completion:
            with self.assertRaises(ComponentResponseError) as caught:
                ai._component_validated_completion('Rules', 'Facts', component)
        self.assertEqual(completion.call_count, 2)
        self.assertEqual(stream_error_details(caught.exception)['code'], 'component_response_invalid')

    def test_rate_cards_do_not_require_optional_sticker(self):
        component = ai.detect_website_component('Component 5', 'b2b')
        record = {'cards': [{'fields': [
            {'label': 'Plan Name', 'value': 'Business First Plus'},
            {'label': 'Price', 'value': '100 درهم بدون ضريبة القيمة المضافة'},
            {'label': 'USPs', 'value': [{'name': 'البيانات', 'value': 'بدون توقف'}, {'name': 'الدقائق', 'value': '100 دقيقة'}]},
            {'label': 'CTA', 'value': 'Buy Now'},
        ]}]}
        text = render_record(record, component, 'ar')
        self.assertIn('[المحتوى الجاهز للنسخ]', text)
        self.assertIn('اشتر الآن', text)
        self.assertNotIn('Buy Now', text)
        self.assertFalse(ai._component_limit_issues(text, component))

    def test_legacy_rate_card_without_marker_is_recovered(self):
        component = ai.detect_website_component('Component 5', 'b2b')
        text = ai._normalize_component_layout('اسم الباقة: باقة أعمال\nالسعر: 100 درهم\nالمزايا: بيانات ودقائق\nالدعوة لاتخاذ إجراء: اشتر الآن')
        self.assertFalse(ai._component_limit_issues(text, component))

    def test_structured_single_language_output_owns_its_markers(self):
        component = ai.detect_website_component('Component 1', 'b2b')
        record = {'cards': [{'fields': [{'label': 'Title', 'value': 'Daily backup'}, {'label': 'Sub-title', 'value': 'Fast file restore'}]}]}
        text = ai._component_output(record, component, 'en')
        self.assertIn('[COPY READY CONTENT]', text)
        self.assertIn('Image: REQUIRED INPUT', text)
        self.assertIn('[REFERENCE AND VALIDATION]', text)

    def test_intro_copy_subtitle_limit_is_enforced(self):
        # Test the parser independently of channel-admin edits to active field names.
        component = {'number': 2, 'definition': '### Component 2 — Intro Copy\n- Title: mandatory, max 65 characters\n- Sub-title: mandatory, approximately 300 characters max; small paragraph'}
        self.assertEqual(ai._component_field_limits(component)['subtitle'][1], 300)
        text = '[COPY READY CONTENT]\nTitle: Business\nSub-title: ' + 'A' * 301
        self.assertTrue(ai._component_limit_issues(text, component))


if __name__ == '__main__':
    unittest.main()
