import copy
from datetime import datetime, timezone
import unittest

from channel_performance import summary, record_generation

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def event(day='2026-10-26T10:00:00+00:00', channel='b2c', generated=None):
    return {'timestamp': day, 'channel_id': channel, 'actor_email': 'user@example.test',
            'action': 'Bilingual copy generated', 'metadata': {'generated': generated or {'english': 'Hello', 'arabic': 'مرحبا'}, 'content_channel': 'SMS', 'task': 'improve'}}


class PerformanceTests(unittest.TestCase):
    def test_private_summary_preserves_counts_without_titles_or_approval_states(self):
        sample=event()
        sample['metadata'].update(content_channel='Confidential custom label',task='Private task')
        result=summary({'activity':[sample]},'b2c',7,NOW,private=True)
        self.assertEqual(result['outputs'],2)
        self.assertEqual(result['generation_runs'],1)
        self.assertEqual(result['formats'],[{'name':'Other','count':2}])
        self.assertNotIn('approvals',result)
        self.assertNotIn('Confidential',str(result))
        self.assertNotIn('Private task',str(result))

    def test_channel_scope_prior_period_uae_boundary_and_zero_days(self):
        data = {'activity': [event(), event(channel='b2b'), event('2026-10-19T10:00:00+00:00'),
                             event('2026-10-19T21:00:00+00:00')]}
        result = summary(data, 'b2c', 7, NOW)
        self.assertEqual(result['outputs'], 4)
        self.assertEqual(result['previous_outputs'], 2)
        self.assertEqual(result['change_percent'], 100)
        self.assertEqual(result['active_contributors'], 1)
        self.assertEqual(len(result['daily']), 7)
        self.assertEqual(result['daily'][0], {'date': '2026-10-20', 'count': 2})
        self.assertEqual(result['daily'][1]['count'], 0)

    def test_rollup_survives_activity_truncation_without_counting_saves(self):
        data = {'activity': [event()]}
        next_event = event('2026-10-26T11:00:00+00:00')
        record_generation(data, next_event)
        data['activity'] = []
        record_generation(data, {'action': 'Copy saved'})
        self.assertEqual(summary(data, 'b2c', 7, NOW)['outputs'], 4)
        self.assertEqual(summary(copy.deepcopy(data), 'b2c', 7, NOW)['generation_runs'], 2)

    def test_first_bulk_write_not_double_counted_and_saved_single_not_counted(self):
        batch = {'id': 'one', 'channel_id': 'b2c', 'created_at': NOW.isoformat(), 'created_by_email': 'user@example.test',
                 'task': 'write', 'items': [{'output_id': 'b2c-sms-001', 'output_name': 'SMS', 'generated': {'en': 'Hi', 'ar': 'مرحبا'}}],
                 'events': [{'action': 'generated'}]}
        saved_single = dict(batch, id='saved', events=[{'action': 'saved'}])
        data = {'approval_batches': [batch, saved_single], 'activity': []}
        record_generation(data, {'action': 'Bulk copy generated', 'metadata': {'batch_id': 'one'}})
        result = summary(data, 'b2c', 30, NOW)
        self.assertEqual(result['outputs'], 2)
        self.assertEqual(result['generation_runs'], 1)
        self.assertEqual(result['formats'], [{'name': 'SMS', 'count': 2}])
        self.assertEqual(result['languages'], [{'name': 'en', 'count': 1}, {'name': 'ar', 'count': 1}])

    def test_missing_or_invalid_history_is_empty_not_fabricated(self):
        data = {'activity': [event('invalid')]}
        result = summary(data, 'b2c', 7, NOW)
        self.assertEqual(result['outputs'], 0)
        self.assertIsNone(result['change_percent'])
        self.assertEqual(result['active_contributors'], 0)

