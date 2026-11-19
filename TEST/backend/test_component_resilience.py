import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import access_control as access
import ai_service as ai
from commercial_facts import price_tax_treatment
from component_records import render_record
from copywriter import output_catalog
from structure_retrieval import select_b2b_templates, select_instructions, invalidate_file


class ComponentResilienceTests(unittest.TestCase):
    def test_tax_wording_variants_are_restored_in_every_schema(self):
        variants = ['excluding 5% VAT', 'excl. VAT', '+ VAT', 'VAT not included',
                    'exclusive of VAT', 'not inclusive of VAT', 'غير شامل ضريبة القيمة المضافة']
        for number in range(1, 18):
            component = ai.detect_website_component(f'Component {number}', 'b2b')
            for source in variants:
                with self.subTest(component=number, source=source):
                    text = '[COPY READY CONTENT]\nPrice: AED 100\n[REFERENCE AND VALIDATION]'
                    result = ai._restore_price_tax_qualification(text, 'AED 100 ' + source, 'en')
                    self.assertIn('Price: AED 100, excluding VAT', result)
                    self.assertFalse(ai._component_offer_issues(result, 'AED 100 ' + source))
                    self.assertEqual(result, ai._restore_price_tax_qualification(result, source, 'en'))

    def test_mixed_tax_is_bound_to_price_and_ambiguity_is_not_guessed(self):
        source = 'Plan A AED 100 excluding VAT; Plan B AED 200 including VAT.'
        self.assertEqual(price_tax_treatment(source, 'AED 100'), 'excluded')
        self.assertEqual(price_tax_treatment(source, '200 درهم'), 'included')
        self.assertIsNone(price_tax_treatment('VAT applies. AED 100.', 'AED 100'))
        component = ai.detect_website_component('Component 3', 'b2b')
        text = '[COPY READY CONTENT]\nTitle: Plans\nSub-title: AED 100/month\n[REFERENCE AND VALIDATION]\nRequirements:\nOverall validation: PASS'
        with patch.object(ai, '_run_completion', side_effect=AssertionError('Clarification requires no model retry')):
            result = ai._component_validated_completion('Rules', 'AED 100. VAT treatment to be confirmed.', component, initial_output=text)
        self.assertIn('Sub-title: REQUIRED INPUT', result)
        self.assertIn('Confirm whether VAT is included or excluded', result)
        self.assertIn('Overall validation: REQUIRED INPUT', result)

    def test_review_counts_every_repeated_field_using_the_generation_validator(self):
        from quality_analysis import component_length_checks, evidence_context
        _, sources = evidence_context('b2b', 'Website', 'Component 3')
        text = '[COPY READY CONTENT]\nTitle: Fits\nSub-title: Daily backup\nTitle: ' + 'A' * 24 + '\nSub-title: Fast restore\n[REFERENCE AND VALIDATION]'
        checks = component_length_checks(text, '', 'Component 3', 'b2b', sources)
        self.assertEqual(len(checks), 4)
        self.assertTrue(any(c['status'] == 'missing' and c['output_quote'] == 'A' * 24 for c in checks))

    def test_all_component_schemas_render_both_languages_without_optional_limits(self):
        for number in range(1, 18):
            component = ai.detect_website_component(f'Component {number}', 'b2b')
            for language in ['en', 'ar']:
                with self.subTest(number=number, language=language):
                    fields = [{'label': name, 'value': 'مدخل مطلوب' if language == 'ar' else 'REQUIRED INPUT'}
                              for name, mandatory in ai.schema_fields(component) if mandatory]
                    # USPs require at least one textual field, both title/subtitle optional.
                    if number == 3:
                        fields.append({'label': 'Title', 'value': 'خدمة' if language == 'ar' else 'Service'})
                    text = render_record({'cards': [{'fields': fields}]}, component, language)
                    self.assertFalse(ai._component_limit_issues(text, component))
                    if language == 'ar':
                        self.assertFalse(ai._arabic_localization_issues(text))

    def test_new_component_is_discovered_retrieved_rendered_and_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'b2b'
            directory.mkdir()
            (directory / '01_B2B_SYSTEM_INSTRUCTIONS.md').write_text('# Shared\nNever invent facts.', encoding='utf-8')
            path = directory / '02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md'
            path.write_text('<!-- B2B_SCOPE: website -->\n# Website tone\nUse neutral benefits.\n### Component 1 — Old\n- Title: mandatory, max 20 characters\n### Component 18 — New banner\n- Title: mandatory, max 12 characters\n- Description: mandatory, max 35 characters\n## Validation rules\nCount every character.', encoding='utf-8')
            with patch.object(access, 'CHANNEL_PROMPT_DIR', directory.parent):
                self.assertIn('component-18', {item['id'] for item in output_catalog('b2b')})
                component = ai.detect_website_component('المكوّن ١٨', 'b2b')
                self.assertEqual(component['number'], 18)
                bundle = access.instruction_bundle('b2b', 'Website', 'B2B-COMPONENT-018')
                self.assertIn('Component 18', bundle['text'])
                self.assertNotIn('Component 1 — Old', bundle['text'])
                self.assertIn('Never invent facts', bundle['text'])
                result = render_record({'cards': [{'fields': [{'label': 'Title', 'value': 'A' * 13}, {'label': 'Description', 'value': 'Useful service'}]}]}, component, 'en')
                self.assertTrue(ai._component_limit_issues(result, component))
                path.write_text(path.read_text(encoding='utf-8').replace('max 12', 'max 15'), encoding='utf-8')
                invalidate_file(path)  # Same invalidation used by the channel-admin save endpoint.
                updated = ai.detect_website_component('Component 18', 'b2b')
                self.assertFalse(ai._component_limit_issues(result, updated))

    def test_index_selects_component_and_pins_rules_after_admin_edit(self):
        path = access.instruction_path('B2B_TEMPLATES', 'b2b')
        for number in range(1, 18):
            with self.subTest(component=number):
                text, report = select_b2b_templates(path, f'Component {number}', 'website')
                self.assertIn(f'### Component {number} —', text)
                self.assertIn('Mandatory perspective', text)
                self.assertIn('Transparency and commercial', text)
                self.assertEqual(report['exact_component'], number)
                for other in set(range(1, 18)) - {number}:
                    self.assertNotIn(f'### Component {other} —', text)
        with tempfile.TemporaryDirectory() as temporary:
            fresh = Path(temporary) / 'instructions.md'
            fresh.write_text('# Always\nNever invent claims.\n### Component 18 — New\n- Title: mandatory, max 12 characters', encoding='utf-8')
            _, first = select_b2b_templates(fresh, 'Component 18', 'website')
            fresh.write_text(fresh.read_text(encoding='utf-8') + '\n## New global rule\nAlways preserve dates.', encoding='utf-8')
            text, next_report = select_b2b_templates(fresh, 'Component 18', 'website')
            self.assertNotEqual(first['version'], next_report['version'])
            self.assertIn('Always preserve dates', text)

    def test_old_schema_copy_does_not_override_active_admin_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'instructions.md'
            path.write_text('<!-- B2B_SCOPE: website -->\n### Component 2 — Intro\n- Description: mandatory, max 300 characters\n## Validation rules\nCount characters.\n### Component 2 — Old intro\n- Sub-title: mandatory, max 200 characters', encoding='utf-8')
            text, _ = select_b2b_templates(path, 'Component 2', 'website')
            self.assertIn('- Description:', text)
            self.assertNotIn('- Sub-title:', text)
        component = {'number': 2, 'definition': '### Component 2 — Intro\n- Title: mandatory, max 65 characters\n- Description: mandatory, max 300 characters'}
        record = {'cards': [{'fields': [{'label': 'Title', 'value': 'Business'}, {'label': 'Sub-title', 'value': 'Useful business connectivity.'}]}]}
        result = render_record(record, component, 'en')
        self.assertIn('Description: Useful business connectivity.', result)
        self.assertNotIn('Description: REQUIRED INPUT', result)


if __name__ == '__main__':
    unittest.main()
