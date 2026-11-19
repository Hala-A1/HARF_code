"""Exercise real B2B instruction routing and enforce explicit website voice rules."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import access_control
import ai_service
from structure_retrieval import select_instructions


FACTS = 'Business Internet: approved 25% off for six months, AED 750/month excluding VAT, then AED 1,000/month; 24-month contract; up to 1Gbps; free Payment Device. Icons supplied separately.'


def english_copy(title='Business Internet'):
    return f'''[COPY READY CONTENT]
Component: Component 4 — USP Featured
Title: {title}
Sub-title: 25% off for six months on a 24-month contract
[REFERENCE AND VALIDATION]
Purpose: Present the approved offer.
Character counts:
- Title: {len(title)}/20 — PASS
- Sub-title: 44/65 — PASS
Source facts:
- Supplied terms only.
Requirements:
- Icon: Supplied separately
Overall validation: PASS'''


ARABIC_COPY = '''[المحتوى الجاهز للنسخ]
المكوّن: المكوّن 4
العنوان: إنترنت الأعمال
العنوان الفرعي: خصم 25% لمدة ستة أشهر وعقد لمدة 24 شهراً
[المرجع والتحقق]
الغرض: عرض شروط موثّقة
عدد الأحرف:
- العنوان: 14/20 — مطابق
الحقائق المصدرية:
- العرض وفق المصدر
المتطلبات:
- الأيقونة: متوفرة
التحقق العام: مطابق'''


class ComponentToneTests(unittest.TestCase):
    def test_all_seventeen_selected_components_load_website_voice(self):
        blocks = ai_service.website_component_blocks('b2b')
        self.assertEqual(set(blocks), set(range(1, 18)))
        for number in blocks:
            with self.subTest(component=number):
                prompt = ai_service.build_task_prompt(FACTS, 'write', 'Other', 'Business', 'b2b', f'Component {number}')
                self.assertIn('# B2B Website Tone of Voice', prompt)
                self.assertIn(f'LOCKED COMPONENT: Component {number}', prompt)
                self.assertIn('WEBSITE VOICE PRIORITY', prompt)
                self.assertIn('Do not force promotional prose into factual rows', prompt)
                self.assertNotIn('Produce exactly two headlines', prompt)
                # Full original rules are now retained alongside later updates;
                # historical source pages stay indexed instead of filling prompts.
                self.assertLess(len(prompt), 350000)

    def test_scope_inference_also_covers_translation_and_preview(self):
        for query in ['Component 4', 'المكوّن 4']:
            bundle = access_control.instruction_bundle('b2b', 'Other', query)
            self.assertEqual(bundle['files'][-1]['module'], 'B2B_TEMPLATES')
            self.assertEqual(bundle['files'][-1]['format_scope'], 'website')
        self.assertIn('# B2B Website Tone of Voice', ai_service.translation_instructions(english_copy(), 'ar', 'b2b'))
        paid = access_control.instruction_bundle('b2b', 'Google Paid Search', FACTS)
        self.assertNotIn('# B2B Website Tone of Voice', paid['text'])
        self.assertEqual(paid['files'][-1]['format_scope'], 'paid_search')

    def test_channel_saved_tone_file_is_read_on_the_next_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'b2b').mkdir()
            (directory / 'b2b' / '01_B2B_SYSTEM_INSTRUCTIONS.md').write_text('# B2B foundation\nPreserve supplied facts.', encoding='utf-8')
            saved_voice = directory / 'b2b' / '02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md'
            saved_voice.write_text('<!-- B2B_SCOPE: website -->\n# Channel website tone\nUse the newly approved website phrase.', encoding='utf-8')
            with patch.object(access_control, 'CHANNEL_PROMPT_DIR', directory):
                prompt = ai_service.build_task_prompt(FACTS, team_channel='b2b', instructions='Component 4')
                self.assertIn('newly approved website phrase', prompt)
                saved_voice.write_text('<!-- B2B_SCOPE: website -->\n# Channel website tone\nUse the revised approved website phrase.', encoding='utf-8')
                refreshed = ai_service.build_task_prompt(FACTS, team_channel='b2b', instructions='Component 4')
                self.assertIn('revised approved website phrase', refreshed)
                self.assertNotIn('newly approved website phrase', refreshed)

    def test_reference_ranking_preserves_rules_and_glossary_and_refreshes_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'cx.md'
            path.write_text('# Guide\n## Mandatory rules\nNever invent claims.\n## Glossary\nKeep approved Arabic terms.\n## Source-faithful page reference\n### Source page 1\nInternet example\n### Source page 2\nTravel example', encoding='utf-8')
            text, report = select_instructions(path, 'Internet', references=True, limit=1)
            self.assertIn('Never invent claims', text)
            self.assertIn('Keep approved Arabic terms', text)
            self.assertIn('Internet example', text)
            self.assertNotIn('Travel example', text)
            self.assertEqual(report['selected_references'], 1)
            path.write_text('# Guide\n## Mandatory rules\nUpdated mandatory rule.', encoding='utf-8')
            text, report = select_instructions(path, 'Internet', references=True, limit=1)
            self.assertIn('Updated mandatory rule', text)
            self.assertNotIn('Internet example', text)

    def test_customer_facing_pronouns_trigger_repair_without_rejecting_source_notes(self):
        component = ai_service.detect_website_component('Component 4', 'b2b')
        bad = english_copy('Grow your business')
        good = english_copy()
        with patch.object(ai_service, '_run_completion', side_effect=[bad, good]) as completion:
            result = ai_service._component_validated_completion('Website rules', FACTS, component)
        self.assertEqual(completion.call_count, 2)
        self.assertIn('Website Tone of Voice forbids', completion.call_args.args[0])
        self.assertNotIn('Grow your business', result)
        self.assertFalse(ai_service._component_voice_issues(good.replace('Supplied terms only.', 'Old draft said: your business.')))
        with patch.object(ai_service, '_run_completion', return_value=bad):
            with self.assertRaises(ValueError):
                ai_service._component_validated_completion('Website rules', FACTS, component)

    def test_arabic_cta_and_stale_validation_are_repaired(self):
        component = ai_service.detect_website_component('Component 4', 'b2b')
        bad = ARABIC_COPY.replace('[المرجع والتحقق]', 'زر الإجراء: Buy Now\n[المرجع والتحقق]')
        self.assertTrue(ai_service._component_voice_issues(bad, 'ar'))
        stale = english_copy().replace('Icon: Supplied separately', 'Sub-title exceeds the character limit.')
        self.assertTrue(ai_service._component_validation_issues(stale, component))
        with patch.object(ai_service, '_run_completion', side_effect=[stale, english_copy()]) as completion:
            result = ai_service._component_validated_completion('Website rules', FACTS, component)
        self.assertEqual(completion.call_count, 1)
        self.assertNotIn('exceeds the character limit', result)

    def test_bilingual_generation_repairs_english_voice_too(self):
        first = json.dumps({'english': english_copy('Grow your business'), 'arabic': ARABIC_COPY}, ensure_ascii=False)
        with patch.object(ai_service, '_run_completion', side_effect=[first, english_copy()]) as completion:
            result = ai_service.enhance_bilingual_feedback(FACTS, 'write', 'Other', 'Business', 'b2b', 'Component 4')
        self.assertEqual(completion.call_count, 2)
        self.assertNotIn('Grow your business', result['english'])
        self.assertIn('العنوان:', result['arabic'])

    def test_offer_qualifiers_cannot_be_hidden_in_source_notes(self):
        without_period = english_copy('25% off internet').replace('25% off for six months on a 24-month contract', 'Business Internet with a free Payment Device')
        self.assertTrue(ai_service._component_offer_issues(without_period, FACTS))
        without_vat = english_copy().replace('25% off for six months on a 24-month contract', 'AED 750/month for six months')
        self.assertTrue(ai_service._component_offer_issues(without_vat, FACTS))
        self.assertFalse(ai_service._component_offer_issues(english_copy(), FACTS))
        contract_only = english_copy('25% off internet').replace('25% off for six months on a 24-month contract', 'Business Internet on a 24-month contract')
        self.assertTrue(ai_service._component_offer_issues(contract_only, FACTS))

    def test_last_resort_shortening_cannot_remove_offer_duration(self):
        component = ai_service.detect_website_component('Component 4', 'b2b')
        long_copy = english_copy('25% off internet').replace('25% off for six months on a 24-month contract', 'Business Internet with a free Payment Device and a 24-month contract, for six months')
        with patch.object(ai_service, '_run_completion', return_value=long_copy):
            with self.assertRaises(ValueError):
                ai_service._component_validated_completion('Website rules', FACTS, component)


if __name__ == '__main__':
    unittest.main()
