import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from assessment_cache import AssessmentCache, SOURCE_FACTS, OUTPUT_REVIEWS
from ai_service import analyze_copy

class CacheTests(unittest.TestCase):
    def test_private_copies_expiry_and_capacity(self):
        cache = AssessmentCache(maximum=1, ttl=10)
        with patch('assessment_cache.time.monotonic', return_value=0):
            value, hit = cache.get_or_compute('a', lambda: {'items': []})
            value['items'].append('redacted')
            self.assertFalse(hit)
            self.assertEqual(cache.get_or_compute('a', lambda: None)[0], {'items': []})
        with patch('assessment_cache.time.monotonic', return_value=11):
            self.assertFalse(cache.get_or_compute('a', lambda: {})[1])
            cache.get_or_compute('b', lambda: {})
            self.assertNotIn('a', cache.entries)
        tiny = AssessmentCache(byte_limit=1)
        tiny.get_or_compute('a', lambda: {'large': 'value'})
        self.assertFalse(tiny.entries)

    def test_concurrent_calls_share_one_computation(self):
        cache = AssessmentCache()
        started, release = Event(), Event()
        calls = []
        def compute():
            calls.append(1); started.set(); release.wait(2); return {'ok': True}
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(cache.get_or_compute, 'key', compute)
            self.assertTrue(started.wait(2))
            b = pool.submit(cache.get_or_compute, 'key', compute)
            release.set()
            self.assertEqual(a.result()[0], b.result()[0])
        self.assertEqual(len(calls), 1)

    def test_failure_is_not_cached(self):
        cache = AssessmentCache()
        with self.assertRaises(ValueError):
            cache.get_or_compute('a', lambda: (_ for _ in ()).throw(ValueError('fail')))
        self.assertFalse(cache.pending)
        self.assertEqual(cache.get_or_compute('a', lambda: 1), (1, False))

class AnalysisCacheTests(unittest.TestCase):
    def setUp(self):
        SOURCE_FACTS.clear(); OUTPUT_REVIEWS.clear()
        self.version = 'v1'
        self.model = 'test-model'
        self.fact_calls = self.review_calls = 0
        def evidence(*args):
            return 'Clear wording', {'G1': {'id': 'G1', 'filename': 'system.md', 'section': 'Clarity', 'line': 1, 'end_line': 2, 'version': self.version, 'text': 'Use clear wording.'}}
        def completion(instructions, payload, **kwargs):
            data = json.loads(payload)
            if 'source' in data:
                self.fact_calls += 1
                return json.dumps({'facts': []})
            self.review_calls += 1
            return json.dumps({'checks': [{'rule': 'Clarity', 'category': 'clarity', 'status': 'met', 'output_quote': data['generated_output'], 'references': [{'source_id': 'G1', 'rule_quote': 'Use clear wording.'}]}]})
        for target, options in [
            ('quality_analysis.evidence_context', {'side_effect': evidence}),
            ('ai_service.website_component_requirements', {'return_value': ('Other', '')}),
            ('quality_analysis.component_length_checks', {'return_value': []}),
            ('ai_service.copywriter_settings', {'side_effect': lambda: {'AZURE_OPENAI_ENDPOINT': 'https://example.test', 'AZURE_OPENAI_MODEL': self.model}}),
            ('ai_service._run_completion', {'side_effect': completion}),
        ]:
            patcher = patch(target, **options); patcher.start(); self.addCleanup(patcher.stop)

    def check(self, output='Hello', source='Hello', language='en', instructions='', channel='b2c'):
        return analyze_copy(output, source, channel, 'Other', instructions, 'improve', language)

    def test_ten_outputs_use_eleven_calls_and_repeat_uses_zero(self):
        for number in range(10):
            self.assertIsNotNone(self.check(f'Hello {number}')['score'])
        self.assertEqual((self.fact_calls, self.review_calls), (1, 10))
        result = self.check('Hello 0')
        result['checks'].clear()
        self.assertTrue(self.check('Hello 0')['checks'])
        self.assertEqual((self.fact_calls, self.review_calls), (1, 10))

    def test_languages_versions_context_and_models_invalidate_correctly(self):
        self.check(); self.check(language='ar')
        self.assertEqual((self.fact_calls, self.review_calls), (1, 2))
        self.version = 'v2'; self.check()
        self.check(instructions='Be concise')
        self.assertEqual((self.fact_calls, self.review_calls), (1, 4))
        self.check(source='New source')
        self.check(channel='b2b')
        self.model = 'new-model'; self.check()
        self.assertEqual((self.fact_calls, self.review_calls), (4, 7))

if __name__ == '__main__':
    unittest.main()
