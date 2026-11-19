import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from approval import BulkItem, BulkGenerateRequest
from component_set_review import review_component_sets, review_set
from main import app


def items():
    return [dict(id='a', output_id='component-1', output_name='Hero',
                 generated={'en': 'Back up business files daily', 'ar': 'نسخ الملفات يومياً'}),
            dict(id='b', output_id='component-2', output_name='Intro',
                 generated={'en': 'Back up business files daily. Restore quickly.', 'ar': 'نسخ الملفات يومياً واستعادتها سريعاً'})]


class ComponentSetReviewTests(unittest.TestCase):
    def source(self, **kwargs):
        return BulkItem(filename='brief.txt', text='Daily backup and fast recovery.', **kwargs)

    def finding(self, kind='repetition'):
        return dict(kind=kind, detail='The same opening is repeated.', suggestion='Use the intro to explain recovery.',
                    evidence=[dict(output_id='component-1', language='en', quote='Back up business files daily'),
                              dict(output_id='component-2', language='en', quote='Back up business files daily')])

    def test_grounded_findings_in_all_three_categories_do_not_modify_copy(self):
        original = items()
        before = copy.deepcopy(original)
        payload = {'findings': [self.finding(kind) for kind in ['repetition', 'contradiction', 'progression']]}
        with patch('component_set_review._run_completion', return_value=json.dumps(payload)) as complete:
            report = review_set(self.source(), original)
        self.assertEqual(report['status'], 'checked')
        self.assertEqual(len(report['findings']), 3)
        self.assertEqual(original, before)
        self.assertEqual(complete.call_count, 1)
        sent = json.loads(complete.call_args.args[1])
        self.assertEqual([i['output_id'] for i in sent['outputs_in_selected_order']],
                         ['component-1', 'component-1', 'component-2', 'component-2'])
        self.assertEqual(complete.call_args.kwargs, {'timeout': 25, 'json_mode': True})

    def test_unverifiable_or_single_component_evidence_is_never_presented_as_checked(self):
        for mutation in ['quote', 'id', 'language', 'same_component', 'missing']:
            finding = self.finding()
            if mutation == 'quote': finding['evidence'][0]['quote'] = 'Invented offer'
            if mutation == 'id': finding['evidence'][0]['output_id'] = 'component-17'
            if mutation == 'language': finding['evidence'][0]['language'] = 'de'
            if mutation == 'same_component': finding['evidence'][1]['output_id'] = 'component-1'
            if mutation == 'missing': finding['evidence'] = []
            with self.subTest(mutation=mutation), patch('component_set_review._run_completion', return_value=json.dumps({'findings': [finding]})):
                report = review_set(self.source(), items())
                self.assertEqual(report['status'], 'unavailable')
                self.assertEqual(report['findings'], [])

    def test_clean_malformed_and_outage_reports_are_distinguished(self):
        for output, status in [('{}', 'unavailable'), ('not json', 'unavailable'), ('{"findings": []}', 'checked')]:
            with patch('component_set_review._run_completion', return_value=output):
                self.assertEqual(review_set(self.source(), items())['status'], status)
        with patch('component_set_review._run_completion', side_effect=TimeoutError('private service diagnostic')):
            report = review_set(self.source(), items())
        self.assertEqual(report['status'], 'unavailable')
        self.assertNotIn('private', json.dumps(report))

    def test_partial_scope_is_bounded_and_disclosed(self):
        outputs = items()
        outputs[0]['generated']['en'] = 'X' * 100000
        source = BulkItem(filename='large.txt', text='S' * 100000)
        with patch('component_set_review._run_completion', return_value='{"findings": []}') as complete:
            report = review_set(source, outputs)
        self.assertTrue(report['partial'])
        sent = json.loads(complete.call_args.args[1])
        self.assertEqual(len(sent['source']), 16000)
        self.assertLessEqual(sum(len(o['text']) for o in sent['outputs_in_selected_order']), 48000)

    def test_only_related_b2b_sets_are_checked_and_each_source_is_separate(self):
        first, second = self.source(), self.source(row_instructions='Other source')
        outputs = items() + [{**i, 'id': i['id']+'2'} for i in items()]
        jobs = [(source, {'id': key}) for source in [first, second] for key in ['component-1', 'component-2']]
        request = BulkGenerateRequest(team_channel='b2b', items=[first, second], instructions='Logical flow')
        with patch('component_set_review.review_set', return_value={'status': 'checked'}) as review:
            self.assertEqual(len(review_component_sets(request, jobs, outputs)), 2)
            self.assertEqual(review.call_count, 2)
            self.assertEqual(len(review.call_args_list[0].args[1]), 2)
            self.assertTrue(any('Other source' in call.args[2] for call in review.call_args_list))
        for channel, task in [('b2c', 'improve'), ('security', 'write'), ('b2b', 'translate'), ('b2b', 'review')]:
            request.team_channel, request.task = channel, task
            with patch('component_set_review.review_set') as review:
                self.assertEqual(review_component_sets(request, jobs, outputs), [])
                review.assert_not_called()
        request.team_channel, request.task = 'b2b', 'improve'
        with patch('component_set_review.review_set') as review:
            self.assertEqual(review_component_sets(request, jobs[:1], outputs[:1]), [])
            review.assert_not_called()

    def test_generation_persists_review_and_revision_marks_it_stale(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / 'access.json'
            data.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf-8')
            with patch.object(access_control, 'DATA_FILE', data), patch('approval.enhance_feedback', return_value='Copy'), patch('component_set_review._run_completion', return_value='{"findings": []}') as complete:
                client = TestClient(app)
                headers = {'X-User-Email': 'b2b.user@eand.ae'}
                response = client.post('/api/bulk/generate', headers=headers, json={
                    'team_channel': 'b2b', 'items': [{'filename': 'brief.txt', 'text': 'Daily backup'}],
                    'languages': ['en'], 'output_ids': ['component-1', 'component-2']})
                self.assertEqual(response.status_code, 200, response.text)
                batch = response.json()
                self.assertEqual(complete.call_count, 1)
                self.assertEqual(batch['component_set_checks'][0]['status'], 'checked')
                saved = client.get('/api/approvals/' + batch['id'], headers=headers).json()
                self.assertEqual(saved['component_set_checks'], batch['component_set_checks'])
                changed = client.put('/api/approvals/' + batch['id'] + '/copy', headers=headers,
                                     json={'item_id': batch['items'][0]['id'], 'language': 'en', 'text': 'Updated copy'})
                self.assertEqual(changed.status_code, 200, changed.text)
                self.assertTrue(changed.json()['component_set_checks'][0]['stale'])
                self.assertEqual(complete.call_count, 1)
