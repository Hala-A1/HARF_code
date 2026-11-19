import json
import unittest
from unittest.mock import patch

import ai_service as ai


ARABIC = '''[المحتوى الجاهز للنسخ]
المكوّن: المكوّن 1 — صورة رئيسية
العنوان: نسخ احتياطي سحابي للأعمال
النص الفرعي: حماية يومية واستعادة سريعة للملفات

[المرجع والتحقق]
الغرض: توضيح فائدة النسخ الاحتياطي
عدد الأحرف:
- العنوان: 20/20 — مطابق
- النص الفرعي: 35/50 — مطابق
الحقائق المصدرية:
- نسخ احتياطي يومي واستعادة سريعة
المتطلبات:
- الصورة: مزودة بشكل منفصل
التحقق العام: مطابق'''


class ComponentFieldRepairTests(unittest.TestCase):
    def setUp(self):
        self.component = ai.detect_website_component('Component 1', 'b2b')

    def test_explicit_vat_is_restored_without_an_ai_retry(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: Business plans\nSub-title: Plans from AED 100/month\n[REFERENCE AND VALIDATION]\nSource facts:\n- AED 100/month excluding VAT'
        with patch.object(ai, '_run_completion', side_effect=AssertionError('No AI call needed')):
            result = ai._component_validated_completion('Rules', 'AED 100/month excluding VAT', component, initial_output=text)
        self.assertIn('Sub-title: Plans from AED 100/month, excluding VAT', result)
        self.assertFalse(ai._component_limit_issues(result, component))
        self.assertFalse(ai._component_offer_issues(result, 'AED 100/month excluding VAT'))

    def test_tax_restoration_never_guesses_or_changes_mixed_tax_sources(self):
        text = '[COPY READY CONTENT]\nPrice: AED 100\n[REFERENCE AND VALIDATION]'
        for source in ['AED 100. VAT treatment to be confirmed.', 'Plan A AED 100 excluding VAT; Plan B AED 100 including VAT.']:
            result = ai._restore_price_tax_qualification(text, source, 'en')
            self.assertIn('Price: REQUIRED INPUT', result)
            self.assertIn('Confirm whether VAT is included or excluded', result)
        self.assertIn('excluding VAT', ai._restore_price_tax_qualification(text, 'Plan A AED 100 excluding VAT; Plan B AED 200 including VAT.', 'en'))
        result = ai._restore_price_tax_qualification(text, 'AED 100 including VAT', 'ar')
        self.assertIn('شامل ضريبة القيمة المضافة', result)
        self.assertEqual(result, ai._restore_price_tax_qualification(result, 'AED 100 including VAT', 'ar'))

    def test_restored_tax_is_still_subject_to_field_limits(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: Plans from AED 100\n[REFERENCE AND VALIDATION]'
        restored = ai._restore_price_tax_qualification(text, 'AED 100 excluding VAT', 'en')
        self.assertTrue(ai._component_limit_issues(restored, component))

    def test_actual_arabic_count_selects_a_fitting_alternative(self):
        choices = {'candidates': [{'العنوان': 'نسخ احتياطي سحابي للأعمال'}, {'العنوان': 'نسخ احتياطي سحابي'}, {'العنوان': 'نسخ يومي آمن'}]}
        with patch.object(ai, '_run_completion', side_effect=[ARABIC, ARABIC, json.dumps(choices, ensure_ascii=False)]), patch.object(ai, '_website_tone_rules', return_value='Website rules'):
            result = ai._component_validated_completion('Rules', 'Daily backup and fast file restore.', self.component, initial_output=ARABIC, output_language='ar')
        self.assertIn('العنوان: نسخ احتياطي سحابي\n', result)
        self.assertFalse(ai._component_limit_issues(result, self.component))
        self.assertIn('النص الفرعي: حماية يومية واستعادة سريعة للملفات', result)
        self.assertIn(f'- العنوان: {len("نسخ احتياطي سحابي")}/20', result)

    def test_english_validation_status_does_not_require_another_ai_call(self):
        text = ARABIC.replace('نسخ احتياطي سحابي للأعمال', 'نسخ يومي').replace('مطابق', 'PASS')
        text = text.replace('التحقق العام: PASS', 'التقييم الإجمالي: PASS')
        with patch.object(ai, '_run_completion', side_effect=AssertionError('Fixed metadata requires no AI request')):
            result = ai._component_validated_completion('Rules', 'Daily backup.', self.component, initial_output=text, output_language='ar')
        self.assertIn('التحقق العام: مطابق', result)
        self.assertFalse(ai._arabic_localization_issues(result))
        self.assertNotIn('PASS', result)

    def test_localisation_preserves_failures_missing_inputs_names_and_source_facts(self):
        text = '''[المحتوى الجاهز للنسخ]
العنوان: PASS
الصورة: REQUIRED INPUT
[المرجع والتحقق]
عدد الأحرف:
- العنوان: 4/20 — PASS
- الوصف: 60/50 — FAIL
الحقائق المصدرية:
- اسم المنتج المعتمد PASS
المتطلبات:
- الصورة: REQUIRED INPUT
- الأيقونة: PASS
التقييم الإجمالي: FAIL'''
        result = ai._localize_component_metadata(text)
        self.assertIn('العنوان: PASS', result)
        self.assertIn('اسم المنتج المعتمد PASS', result)
        self.assertIn('60/50 — غير مطابق', result)
        self.assertIn('الصورة: مدخل مطلوب', result)
        self.assertIn('الأيقونة: مطابق', result)
        self.assertIn('التحقق العام: غير مطابق', result)
        self.assertFalse(ai._arabic_localization_issues(result))
        self.assertEqual(result, ai._localize_component_metadata(result))

    def test_mixed_labels_and_numbered_statuses_are_localised(self):
        text = '[COPY READY CONTENT]\nTitle 1: نسخ يومي\n[REFERENCE AND VALIDATION]\nCharacter counts:\n- Title 1: 8/20 — PASS\nSource facts:\n- نسخ احتياطي يومي\nRequirements:\n- Image: REQUIRED INPUT\nOverall validation: REQUIRED INPUT'
        result = ai._localize_component_metadata(text)
        self.assertIn('العنوان 1: نسخ يومي', result)
        self.assertIn('التحقق العام: مدخل مطلوب', result)
        self.assertFalse(ai._arabic_localization_issues(result))

    def test_arabic_subtitle_alias_is_actually_checked(self):
        long = ARABIC.replace('حماية يومية واستعادة سريعة للملفات', 'ملفات ' * 12)
        self.assertTrue(any('Sub-title' in issue for issue in ai._component_limit_issues(long, self.component)))

    def test_no_valid_alternative_has_specific_safe_error(self):
        with patch.object(ai, '_run_completion', return_value='{"candidates": []}'), patch.object(ai, '_website_tone_rules', return_value='Website rules'):
            with self.assertRaises(ai.ComponentValidationError) as caught:
                ai._component_validated_completion('Rules', 'Facts', self.component, initial_output=ARABIC, output_language='ar')
        self.assertIn('Component 1 (Arabic)', caught.exception.public_message)
        self.assertIn('maximum is 20', caught.exception.public_message)

    def test_bilingual_repair_reuses_initial_results(self):
        initial = {'english': 'English initial', 'arabic': 'Arabic initial'}
        with patch.object(ai, '_run_completion', return_value=json.dumps(initial)), patch.object(ai, 'bilingual_output_instructions', return_value='Rules'), patch.object(ai, 'build_task_prompt', return_value='Rules'), patch.object(ai, '_component_for_request', return_value=self.component), patch.object(ai, '_component_validated_completion', side_effect=['English repaired', 'Arabic repaired']) as repair:
            result = ai.enhance_bilingual_feedback('Facts', instructions='Component 1')
        self.assertEqual(result['arabic'], 'Arabic repaired')
        self.assertEqual(repair.call_args_list[0].kwargs['initial_output'], 'English initial')
        self.assertEqual(repair.call_args_list[1].kwargs['initial_output'], 'Arabic initial')

    def test_correct_arabic_headings_and_bold_fields_are_normalized(self):
        text = '## النص الجاهز للنسخ\n**العنوان:** نسخ يومي\n**النص الفرعي:** حماية الملفات\n## المراجع والتحقق\nالغرض: حماية الملفات'
        result = ai._normalize_component_layout(text)
        self.assertIn('[المحتوى الجاهز للنسخ]\nالعنوان: نسخ يومي', result)
        self.assertIn('[المرجع والتحقق]\nالغرض:', result)
        self.assertFalse(ai._component_limit_issues(result, self.component))

    def test_json_mode_is_requested_for_bilingual_generation(self):
        with patch.object(ai, '_run_completion', return_value='{"english":"Hello","arabic":"مرحباً"}') as completion, patch.object(ai, 'bilingual_output_instructions', return_value='JSON'), patch.object(ai, '_component_for_request', return_value=None):
            self.assertEqual(ai.enhance_bilingual_feedback('Greeting')['english'], 'Hello')
        self.assertTrue(completion.call_args.kwargs['json_mode'])

    def test_repeated_usp_titles_are_all_checked_and_repaired_in_place(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '''[COPY READY CONTENT]
Component: Component 3 — USPs
USP 1
Title: Daily backup
Sub-title: Automatic daily backups.
USP 2
Title: Fast business file restore
Sub-title: Restore files quickly.
[REFERENCE AND VALIDATION]
Character counts:
- Title: 24/20 — FAIL
Source facts:
- Daily backups and fast restore.
Overall validation: FAIL'''
        entries = ai._limited_component_fields(text, component)
        offending = next(f for f in entries if f['current'] == 'Fast business file restore')
        choices = {'candidates': [{offending['id']: 'Fast file restore'}]}
        self.assertTrue(ai._component_limit_issues(text, component))
        with patch.object(ai, '_run_completion', return_value=json.dumps(choices)):
            result = ai._repair_overlong_component_fields(text, component, 'Daily backups and fast file restore.', 'en')
        self.assertIn('Title: Daily backup\n', result)
        self.assertIn('Title: Fast file restore\n', result)
        self.assertIn('- Title: 12/20', result)
        self.assertIn('- Title: 17/20', result)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_first_repeated_and_numbered_titles_cannot_escape_validation(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        for label in ['Title', 'Title 1', 'USP 1 Title', 'العنوان ١']:
            with self.subTest(label=label):
                text = f'[COPY READY CONTENT]\n{label}: ' + 'A' * 24 + '\nTitle: Fits\n[REFERENCE AND VALIDATION]'
                self.assertTrue(ai._component_limit_issues(text, component))
                with self.assertRaises(ai.ComponentValidationError):
                    ai._truncate_component_fields(text, component)

    def test_alternatives_can_be_selected_independently_for_each_field(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: ' + 'A' * 24 + '\nTitle: ' + 'B' * 25 + '\n[REFERENCE AND VALIDATION]'
        choices = {'candidates': [{'field-1': 'Daily backup'}, {'field-2': 'Fast restore'}]}
        with patch.object(ai, '_run_completion', return_value=json.dumps(choices)):
            result = ai._repair_overlong_component_fields(text, component, 'Daily backup and fast restore.', 'en')
        self.assertIn('Title: Daily backup\nTitle: Fast restore', result)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_list_fields_and_unknown_layout_cannot_bypass_limits(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\n- **العنوان ١:** ' + 'أ' * 24 + '\n[المرجع والتحقق]'
        normalized = ai._normalize_component_layout(text)
        self.assertTrue(ai._component_limit_issues(normalized, component))
        self.assertIn('العنوان ١: ', normalized)
        self.assertTrue(ai._component_limit_issues('[COPY READY CONTENT]\nUnrecognised text\n[REFERENCE AND VALIDATION]', component))
        for label in ['Description 1', 'الوصف ١']:
            text = f'[COPY READY CONTENT]\nTitle: Fits\n{label}: ' + 'A' * 66
            self.assertTrue(any('maximum is 65' in issue for issue in ai._component_limit_issues(text, component)))

    def test_component_seven_keeps_valid_repairs_between_attempts(self):
        component = ai.detect_website_component('Component 7', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\nالعنوان: ' + 'أ' * 30 + '\nالوصف: ' + 'ب' * 263 + '\n[المرجع والتحقق]'
        choices = [
            {'candidates': [{'field-1': 'اتصال أسرع', 'field-2': 'ج' * 200}]},
            {'candidates': [{'field-2': 'اتصال موثوق للأعمال مع دعم فني متواصل.'}]},
        ]
        with patch.object(ai, '_run_completion', side_effect=[json.dumps(c, ensure_ascii=False) for c in choices]) as completion:
            result = ai._repair_overlong_component_fields(text, component, 'Reliable business internet with technical support.', 'ar')
        self.assertEqual(completion.call_count, 2)
        self.assertFalse(ai._component_limit_issues(result, component))
        self.assertIn('العنوان: اتصال أسرع', result)
        # The second call repairs only the remaining description, without regenerating the valid title.
        self.assertIn('اتصال أسرع', completion.call_args.args[0])
        self.assertIn('"target": 99', completion.call_args.args[0])

    def test_length_repair_is_not_blocked_by_unrelated_localisation(self):
        component = ai.detect_website_component('Component 7', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\nالعنوان: ' + 'أ' * 30 + '\nالوصف: خدمة أعمال\n[المرجع والتحقق]\nPurpose: English explanation still needs localisation.'
        with patch.object(ai, '_run_completion', return_value=json.dumps({'candidates': [{'field-1': 'خدمات الأعمال'}]}, ensure_ascii=False)):
            result = ai._repair_overlong_component_fields(text, component, 'Business services.', 'ar')
        self.assertFalse(ai._component_limit_issues(result, component))
        self.assertTrue(ai._arabic_localization_issues(result))

    def test_short_candidates_are_retried_with_measured_feedback(self):
        component = ai.detect_website_component('Component 7', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: ' + 'A' * 30 + '\nDescription: Business services\n[REFERENCE AND VALIDATION]'
        choices = [{'candidates': [{'field-1': 'B' * 25}]}, {'candidates': [{'field-1': 'Business services'}]}]
        with patch.object(ai, '_run_completion', side_effect=[json.dumps(c) for c in choices]) as completion:
            result = ai._repair_overlong_component_fields(text, component, 'Business services.', 'en')
        self.assertEqual(completion.call_count, 2)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_field_alternative_arrays_cover_multiple_fields_without_duplicate_keys(self):
        component = ai.detect_website_component('Component 7', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: ' + 'A' * 30 + '\nDescription: ' + 'B' * 200 + '\n[REFERENCE AND VALIDATION]'
        choices = {'fields': [
            {'id': 'field-1', 'alternatives': ['A' * 24, 'Business services', 'Services']},
            {'id': 'field-2', 'alternatives': ['Reliable business connectivity.', 'Business connectivity.', 'Business service.']},
        ]}
        with patch.object(ai, '_run_completion', return_value=json.dumps(choices)):
            result = ai._repair_overlong_component_fields(text, component, 'Reliable business connectivity.', 'en')
        self.assertIn('Title: Business services', result)
        self.assertIn('Description: Reliable business connectivity.', result)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_component_prompts_draft_below_limits_in_each_language(self):
        _, prompt = ai.website_component_requirements('Business service', 'Component 7', 'Website', 'b2b', 'ar')
        self.assertIn('Title: maximum 20; draft target 14', prompt)
        self.assertIn('Description: maximum 180; draft target 126', prompt)
        self.assertIn('Compose English and Arabic independently', prompt)

    def test_stale_length_notes_are_removed_but_missing_assets_are_preserved(self):
        component = ai.detect_website_component('Component 7', 'b2b')
        text = '''[COPY READY CONTENT]
Title: Business services
Description: Reliable business connectivity.
[REFERENCE AND VALIDATION]
Character counts:
- Title: 30/20 — FAIL
Source facts:
- Reliable business connectivity.
Requirements:
- Description exceeds the character limit and requires shortening.
- Image: REQUIRED INPUT
Overall validation: FAIL'''
        result = ai._truncate_component_fields(text, component)
        self.assertNotIn('requires shortening', result)
        self.assertIn('Image: REQUIRED INPUT', result)
        self.assertIn('Overall validation: REQUIRED INPUT', result)
        self.assertFalse(ai._component_validation_issues(result, component))

    def test_discount_price_requires_period_even_without_percentage_in_copy(self):
        source = 'Approved 20% discount for the first three months: AED 80/month excluding VAT, then AED 100/month excluding VAT.'
        copy = '[COPY READY CONTENT]\nTitle: Business services\nDescription: AED 80/month then AED 100/month excluding VAT\n[REFERENCE AND VALIDATION]'
        self.assertTrue(ai._component_offer_issues(copy, source))
        self.assertFalse(ai._component_offer_issues(copy.replace('80/month then', '80/month for three months then'), source))

    def test_all_seventeen_schemas_repair_each_limited_field(self):
        for number in range(1, 18):
            component = ai.detect_website_component(f'Component {number}', 'b2b')
            for language in ['en', 'ar']:
                with self.subTest(component=number, language=language):
                    limits = ai._component_field_limits(component)
                    if not limits:
                        # Component 6 is media-only; its schema has no character limits.
                        self.assertEqual(number, 6)
                        continue
                    lines = [f'{label}: ' + ('أ' if language == 'ar' else 'A') * (maximum + 10) for label, maximum in limits.values()]
                    text = '[COPY READY CONTENT]\n' + '\n'.join(lines) + '\n[REFERENCE AND VALIDATION]'
                    choices = {'candidates': [{f'field-{index + 1}': 'خدمة' if language == 'ar' else 'Service' for index in range(len(limits))}]}
                    with patch.object(ai, '_run_completion', return_value=json.dumps(choices, ensure_ascii=False)):
                        result = ai._repair_overlong_component_fields(text, component, 'Business service.', language)
                    self.assertFalse(ai._component_limit_issues(result, component))

    def test_bad_alternative_does_not_erase_valid_repairs_to_other_usp_cards(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\nالعنوان: نسخ يومي\nالعنوان الفرعي: ' + 'نسخ الملفات يوميا ' * 6 + '\nالعنوان: استعادة سريعة\nالعنوان الفرعي: ' + 'استعادة الملفات بسرعة ' * 6 + '\n[المرجع والتحقق]'
        choices = {'fields': [
            {'id': 'field-2', 'alternatives': ['نسخ الملفات يوميا']},
            {'id': 'field-4', 'alternatives': ['استعادة ملفات شركتك', 'استعادة سريعة للملفات']},
        ]}
        with patch.object(ai, '_run_completion', return_value=json.dumps(choices, ensure_ascii=False)):
            result = ai._repair_component_fields_once(text, component, 'Daily file backups and fast file restoration.', 'ar')
        self.assertIn('العنوان الفرعي: نسخ الملفات يوميا', result)
        self.assertIn('العنوان الفرعي: استعادة سريعة للملفات', result)
        self.assertNotIn('شركتك', result)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_late_arabic_usp_subtitles_are_repaired_without_regenerating_valid_cards(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        subtitles = ['نسخ يومي', 'استعادة سريعة', 'حماية الملفات', 'نسخ الملفات يوميا ' * 6, 'خدمة الأعمال', 'استعادة الملفات بسرعة ' * 6]
        text = '[المحتوى الجاهز للنسخ]\n' + '\n'.join(
            f'الميزة {number}\nالعنوان: خدمة الأعمال\nالعنوان الفرعي: {subtitle}'
            for number, subtitle in enumerate(subtitles, 1)
        ) + '\n[المرجع والتحقق]'
        calls = []
        def answer(prompt, source, **kwargs):
            calls.append(prompt)
            if len(calls) <= 4:
                return '{"fields": []}'
            # Final isolated repairs only receive one requested occurrence.
            self.assertIn('Rewrite ONE website field', prompt)
            return json.dumps({'alternatives': ['نسخ يومي للملفات' if len(calls) == 5 else 'استعادة سريعة للملفات']}, ensure_ascii=False)
        with patch.object(ai, '_run_completion', side_effect=answer), patch.object(ai, '_component_completion', side_effect=AssertionError('Valid cards must not be regenerated')):
            result = ai._component_validated_completion('Rules', 'Daily backups and fast restoration.', component, initial_output=text, output_language='ar')
        self.assertEqual(len(calls), 6)
        self.assertFalse(ai._component_limit_issues(result, component))
        self.assertEqual(result.count('العنوان: خدمة الأعمال'), 6)
        self.assertIn('العنوان الفرعي: حماية الملفات', result)

    def test_candidate_is_remeasured_after_mandatory_tax_qualification(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: Business service\nSub-title: ' + 'Business connectivity ' * 6 + '\n[REFERENCE AND VALIDATION]'
        choices = {'fields': [{'id': 'field-2', 'alternatives': [
            'Business connectivity from AED 100 each month for business',
            'From AED 100/month excluding VAT',
        ]}]}
        with patch.object(ai, '_run_completion', return_value=json.dumps(choices)):
            result = ai._repair_component_fields_once(text, component, 'Business connectivity from AED 100/month excluding VAT.', 'en')
        self.assertIn('Sub-title: From AED 100/month excluding VAT', result)
        self.assertFalse(ai._component_limit_issues(result, component))


    def test_isolated_recovery_handles_more_than_four_remaining_cards(self):
        component = ai.detect_website_component('Component 13', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\n' + '\n'.join(
            f'### البطاقة {i}\nالعنوان: ' + 'عنوان طويل جدا ' * 4 + f'\nالوصف: استعادة الملفات {i}'
            for i in range(1, 7)
        ) + '\n[المرجع والتحقق]'
        calls = []
        def answer(prompt, source, **kwargs):
            calls.append(prompt)
            if len(calls) <= 2:
                return '{"fields": []}'
            self.assertIn('Rewrite ONE website field', prompt)
            self.assertEqual(prompt.count('### البطاقة'), 1)
            return json.dumps({'alternatives': ['استعادة سريعة']}, ensure_ascii=False)
        with patch.object(ai, '_run_completion', side_effect=answer):
            result = ai._repair_overlong_component_fields(text, component, 'Fast file recovery.', 'ar')
        self.assertEqual(result.count('العنوان: استعادة سريعة'), 6)
        self.assertFalse(ai._component_limit_issues(result, component))
        for i in range(1, 7):
            self.assertIn(f'الوصف: استعادة الملفات {i}', result)

    def test_isolated_recovery_retries_shorter_when_all_first_choices_are_overlong(self):
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[المحتوى الجاهز للنسخ]\nالعنوان: ' + 'استعادة الملفات بسرعة كبيرة جدا ' * 2 + '\nالعنوان الفرعي: استعادة الملفات\n[المرجع والتحقق]'
        answers = ['{"fields": []}', '{"fields": []}',
                   json.dumps({'alternatives': ['خدمة استعادة الملفات للشركات بسرعة كبيرة']}, ensure_ascii=False),
                   json.dumps({'alternatives': ['استعادة سريعة']}, ensure_ascii=False)]
        with patch.object(ai, '_run_completion', side_effect=answers) as completion:
            result = ai._repair_overlong_component_fields(text, component, 'Fast file recovery.', 'ar')
        self.assertEqual(completion.call_count, 4)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_future_component_uses_its_own_budget_without_hardcoded_component_number(self):
        component = {'number': 18, 'definition': '### Component 18 — Future card\n- Title: mandatory, max 14 characters'}
        self.assertEqual(ai._component_field_limits(component)['title'][1], 14)
        record = {'cards': [{'fields': [{'label': 'Title', 'value': 'A very long benefit title', 'alternatives': ['Daily backup']}]}]}
        result = ai._component_output(record, component, 'en')
        self.assertIn('Title: Daily backup', result)
        self.assertFalse(ai._component_limit_issues(result, component))

    def test_all_schemas_render_fitting_alternatives_for_repeated_bilingual_cards(self):
        for number in range(1, 18):
            component = ai.detect_website_component(f'Component {number}', 'b2b')
            fields = [{'label': label, 'value': {'english': 'B' * (maximum + 10), 'arabic': 'ب' * (maximum + 10)},
                       'alternatives': [{'english': 'Daily backup', 'arabic': 'نسخ يومي'}]}
                      for label, maximum in ai._component_field_limits(component).values()]
            if not fields:
                fields = [{'label': 'Image', 'value': {'english': 'Supplied separately', 'arabic': 'متوفرة بشكل منفصل'}}]
            record = {'cards': [{'fields': fields} for _ in range(6)]}
            localized = ai.split_bilingual_record(record)
            for language, name in [('en', 'english'), ('ar', 'arabic')]:
                with self.subTest(component=number, language=language):
                    result = ai._component_output(localized[name], component, language)
                    self.assertFalse(ai._component_limit_issues(result, component))
                    self.assertEqual(result.count('### Card' if language == 'en' else '### البطاقة'), 6)


if __name__ == '__main__':
    unittest.main()
