"""Preview must select exactly the rules used by an independent generation."""
import unittest
from unittest.mock import patch

import access_control
import admin
from generation_context import GenerationContext, bind_generation
from structure_retrieval import indexed_file, invalidate_file


class RetrievalPreviewParityTests(unittest.TestCase):
    def test_preview_matches_generation_for_every_component_and_consumer_format(self):
        scenarios = [('b2b', 'Website', f'Component {n} daily backup') for n in range(1, 18)]
        scenarios += [('b2c', fmt, 'payment update') for fmt in
                      ['SMS', 'Email', 'Website', 'In-app message', 'App / Push notification']]
        scenarios += [('b2c', 'Other', f'B2C-{family}-001 payment update') for family in
                      ['SMS', 'EMAIL', 'WEB', 'APP', 'PUSH']]
        scenarios += [('security', 'Other', 'Template 1 policy memo')]
        for channel, fmt, query in scenarios:
            with self.subTest(channel=channel, format=fmt, query=query):
                preview = access_control.instruction_bundle(channel, fmt, query)
                with bind_generation(GenerationContext(channel, query)):
                    actual = access_control.instruction_bundle(channel, fmt, query)
                self.assertEqual(preview['text'], actual['text'])
                self.assertEqual([f['sections'] for f in preview['files']],
                                 [f['sections'] for f in actual['files']])
                self.assertNotIn('Administrator-only maintenance guide', preview['text'])
                if channel == 'b2b':
                    self.assertLess(preview['selected_characters'], preview['original_characters'])
                    self.assertEqual(len(preview['files'][1]['excluded_components']), 16)

    def test_warm_index_does_not_read_entire_file_again(self):
        path = access_control.instruction_path('B2C_TEMPLATES', 'b2c')
        invalidate_file(path)
        _, first_hit = indexed_file(path)
        self.assertFalse(first_hit)
        access_control.instruction_bundle('b2c', 'SMS', 'payment update')
        with patch('pathlib.Path.read_text', side_effect=AssertionError('Unnecessary full-file read')):
            _, second_hit = indexed_file(path)
            selected = access_control.instruction_bundle('b2c', 'SMS', 'payment update')
        self.assertTrue(second_hit)
        self.assertEqual(selected['files'][1]['template_families'], ['SMS'])
        self.assertNotIn('## B2C-EMAIL-001', selected['text'])

    def test_preview_endpoint_reports_exact_generation_sections_without_llm(self):
        user = {'role': 'channel_admin', 'channel_id': 'b2c'}
        request = admin.RetrievalPreviewRequest(query='B2C-SMS-001 payment update', content_channel='SMS')
        with patch('ai_service.get_client', side_effect=AssertionError('Preview must not call AI')):
            preview = admin.retrieval_preview('b2c', request, user)
        with bind_generation(GenerationContext('b2c', request.query)):
            actual = access_control.instruction_bundle('b2c', request.content_channel, request.query)
        self.assertNotIn('text', preview)
        self.assertEqual(preview['files'][1]['sections'], actual['files'][1]['sections'])
        self.assertEqual(preview['files'][1]['template_families'], ['SMS'])
