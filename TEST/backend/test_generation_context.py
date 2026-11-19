import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import access_control
import ai_service
import structure_retrieval
from generation_context import (
    GenerationContext, bind_generation, current_generation, generation_request,
)
from main import app


class GenerationContextTests(unittest.TestCase):
    def test_ten_parallel_components_share_general_and_reuse_exact_indices(self):
        context = GenerationContext('b2b', 'Cloud backup with daily backups and VAT excluded')

        def output(number):
            with bind_generation(context):
                english = access_control.instruction_bundle('b2b', 'Website', f'Component {number}')
                arabic = access_control.instruction_bundle('b2b', 'Website', f'Component {number} Arabic')
                repair = ai_service._website_tone_rules(number)
                self.assertEqual(english['text'], arabic['text'])
                self.assertEqual(english['text'], repair)
                report = next(item for item in english['files'] if item['module'] == 'B2B_TEMPLATES')
                self.assertEqual(report['exact_component'], number)
                self.assertTrue(set(range(1, 11)) - {number} <= set(report['excluded_components']))
                return english['files'][0]

        with patch('structure_retrieval.select_instructions', wraps=structure_retrieval.select_instructions) as retrieve:
            with ThreadPoolExecutor(max_workers=2) as pool:
                reports = list(pool.map(output, range(1, 11)))
        system_calls = [call for call in retrieve.call_args_list if call.args[0].name == '01_B2B_SYSTEM_INSTRUCTIONS.md']
        template_calls = [call for call in retrieve.call_args_list if call.args[0].name == '02_B2B_CHANNEL_TEMPLATE_INSTRUCTIONS.md']
        self.assertEqual(len(system_calls), 1)
        self.assertEqual(len(template_calls), 10)
        self.assertEqual(system_calls[0].args[1], context.query)
        self.assertTrue(all(report['version'] == reports[0]['version'] for report in reports))
        self.assertIsNone(current_generation())

    def test_snapshot_refreshes_next_request_and_general_is_shared_across_formats(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            channel = directory / 'b2c'
            channel.mkdir()
            system = channel / '01_B2C_SYSTEM_INSTRUCTIONS.md'
            system.write_text('# Shared\nOriginal rule', encoding='utf-8')
            (channel / '02_B2C_CHANNEL_TEMPLATE_INSTRUCTIONS.md').write_text('# Formats\nTemplate rules', encoding='utf-8')
            with patch.object(access_control, 'CHANNEL_PROMPT_DIR', directory):
                with bind_generation(GenerationContext('b2c', 'All briefs')):
                    before = access_control.instruction_text_for('b2c', 'SMS', 'first brief')
                    system.write_text('# Shared\nUpdated rule for next request', encoding='utf-8')
                    after = access_control.instruction_text_for('b2c', 'Email', 'second brief')
                    self.assertIn('Original rule', before)
                    self.assertIn('Original rule', after)
                    self.assertNotIn('Updated rule', after)
                with bind_generation(GenerationContext('b2c', 'Next brief')):
                    self.assertIn('Updated rule', access_control.instruction_text_for('b2c', 'Email', 'Next brief'))

    def test_nested_channels_and_failed_requests_cannot_leak_context(self):
        seen = []

        @generation_request
        def generate(feedback, team_channel='b2b'):
            seen.append(current_generation())
            if feedback == 'nested':
                generate('child', team_channel='security')
                self.assertIs(current_generation(), seen[0])
            if feedback == 'failed':
                raise ValueError('Expected failure')

        generate('nested')
        self.assertEqual([item.channel for item in seen], ['b2b', 'security'])
        self.assertIsNone(current_generation())
        with self.assertRaises(ValueError):
            generate('failed')
        self.assertIsNone(current_generation())
        generate('new request')
        self.assertIsNot(seen[-1], seen[0])

    def test_stream_resumes_across_contexts_and_closes_without_leaking(self):
        seen = []
        closed = []

        @generation_request
        def stream(feedback, team_channel='security'):
            try:
                for chunk in ['first', 'second']:
                    seen.append(current_generation())
                    yield chunk
            finally:
                closed.append(current_generation())

        chunks = stream('brief')
        self.assertIsNone(current_generation())
        self.assertEqual(Context().run(next, chunks), 'first')
        self.assertEqual(Context().run(next, chunks), 'second')
        Context().run(chunks.close)
        self.assertIs(seen[0], seen[1])
        self.assertIs(closed[0], seen[0])
        self.assertIsNone(current_generation())

    def test_repairs_receive_shared_rules_without_retrieval_or_duplicate_prompt(self):
        context = GenerationContext('b2b', 'brief')
        path = Path(__file__)
        context.select('B2B_SYSTEM', path, None, 'brief', True,
                       lambda query: ('Authoritative shared rule', {}))
        client = unittest.mock.MagicMock()
        client.chat.completions.create.return_value.choices[0].message.content = 'Fixed copy'
        with bind_generation(context), patch.object(ai_service, 'get_client', return_value=client), patch.object(ai_service, 'get_model', return_value='test'):
            ai_service._run_completion('Short field repair', 'source')
            ai_service._run_completion('Authoritative shared rule\nInitial generation', 'source')
        prompts = [call.kwargs['messages'][0]['content'] for call in client.chat.completions.create.call_args_list]
        self.assertTrue(all(prompt.count('Authoritative shared rule') == 1 for prompt in prompts))

    def test_bulk_seeds_all_briefs_and_shares_context_with_worker_and_languages(self):
        seen = []

        def generate(*args):
            context = current_generation()
            seen.append(context)
            self.assertIn('first brief', context.query)
            self.assertIn('final brief special terminology', context.query)
            # Simulate initial generation and an Arabic repair prompt.
            for query in [args[5], args[5] + ' Arabic repair']:
                access_control.instruction_bundle('b2b', 'Website', query)
            return {'english': 'Example copy', 'arabic': 'Example Arabic copy'}

        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / 'access.json'
            data.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
            with patch.object(access_control, 'DATA_FILE', data), patch('approval.enhance_bilingual_feedback', side_effect=generate), patch('approval.review_component_sets', return_value=[]), patch('structure_retrieval.select_instructions', wraps=structure_retrieval.select_instructions) as retrieve:
                result = TestClient(app).post('/api/bulk/generate', headers={'X-User-Email': 'b2b.user@eand.ae'}, json={
                    'items': [{'filename': 'first.txt', 'text': 'first brief'},
                              {'filename': 'last.txt', 'text': 'final brief special terminology'}],
                    'team_channel': 'b2b', 'languages': ['en', 'ar'],
                    'output_ids': ['component-1', 'component-4'],
                })
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(len(result.json()['items']), 4)
            self.assertEqual(len(seen), 4)
            self.assertTrue(all(context is seen[0] for context in seen))
            self.assertEqual(sum(call.args[0].name == '01_B2B_SYSTEM_INSTRUCTIONS.md' for call in retrieve.call_args_list), 1)
        self.assertIsNone(current_generation())

    def test_shared_terminology_in_last_brief_is_not_lost_to_query_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'general.md'
            path.write_text('# APPROVED ENGLISH–ARABIC GLOSSARY\n| Category | English | Arabic |\n| --- | --- | --- |\n| Product | zebraproduct | approved term |\n| Product | unusedproduct | unused term |\n', encoding='utf-8')
            selected, report = structure_retrieval.select_instructions(path, 'brief ' * 4000 + 'zebraproduct', glossary=True)
            self.assertIn('zebraproduct', selected)
            self.assertNotIn('unusedproduct', selected)
            self.assertEqual(report['omitted_glossary_rows'], 1)

    def test_security_bilingual_and_b2c_single_generation_use_one_general_snapshot(self):
        with patch.object(ai_service, 'security_evidence', side_effect=lambda text: text), patch.object(ai_service, '_run_completion', return_value='Synthetic memo') as complete, patch('structure_retrieval.select_instructions', wraps=structure_retrieval.select_instructions) as retrieve:
            result = ai_service.enhance_bilingual_feedback('Fictional regulation facts', team_channel='security', instructions='Template 1')
        self.assertEqual(result, {'english': 'Synthetic memo', 'arabic': 'Synthetic memo'})
        self.assertEqual(sum(call.args[0].name == '01_REGULATORY_COMPLIANCE_SYSTEM_INSTRUCTIONS.md' for call in retrieve.call_args_list), 1)
        self.assertTrue(all('Regulatory Compliance' in call.args[0] for call in complete.call_args_list))
        self.assertIsNone(current_generation())
        with patch.object(ai_service, '_run_completion', return_value='Synthetic consumer copy'), patch('structure_retrieval.select_instructions', wraps=structure_retrieval.select_instructions) as retrieve:
            ai_service.enhance_feedback('Fictional consumer brief', channel='SMS', team_channel='b2c')
            ai_service.enhance_feedback('Another fictional brief', channel='Email', team_channel='b2c')
        # Independent HTTP generations must start independent snapshots.
        self.assertEqual(sum(call.args[0].name == '01_B2C_SYSTEM_INSTRUCTIONS.md' for call in retrieve.call_args_list), 2)

    def test_b2c_index_routes_reviewed_ux_and_push_dependencies(self):
        with bind_generation(GenerationContext('b2c', 'Consumer briefs')):
            sms = access_control.instruction_bundle('b2c', 'SMS', 'payment update')
            email = access_control.instruction_bundle('b2c', 'Email', 'payment update')
            push = access_control.instruction_bundle('b2c', 'Other', 'Selected output: B2C-PUSH-001')
            app = access_control.instruction_bundle('b2c', 'Other', 'Selected output: B2C-APP-001')
            web = access_control.instruction_bundle('b2c', 'Website', 'payment screen')
        self.assertIn('## B2C-SMS-001', sms['text'])
        self.assertNotIn('## B2C-EMAIL-001', sms['text'])
        self.assertIn('## B2C-EMAIL-001', email['text'])
        self.assertNotIn('## B2C-SMS-001', email['text'])
        self.assertIn('## B2C-PUSH-001', push['text'])
        self.assertNotIn('## B2C-APP-001', push['text'])
        self.assertEqual(push['files'][1]['template_families'], ['PUSH'])
        self.assertIn('title: 25', push['text'])
        self.assertIn('CTA: 15', push['text'])
        for bundle in [app, web]:
            self.assertIn('## B2C-UX-001', bundle['text'])
            self.assertIn('Payment unsuccessful. Please try again.', bundle['text'])
            self.assertNotIn('## B2C-PUSH-001', bundle['text'])
        self.assertNotIn('## B2C-UX-001', sms['text'])


if __name__ == '__main__':
    unittest.main()
