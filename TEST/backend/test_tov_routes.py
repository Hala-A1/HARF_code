import unittest
from unittest.mock import patch
import ai_service


class ToneRouteTests(unittest.TestCase):
    def prompt(self, channel, task='improve', team='b2b'):
        with patch.object(ai_service, 'guidelines_for_text', return_value='Active guide'), patch.object(ai_service, 'website_component_requirements', return_value=(channel, 'Selected schema')):
            return ai_service.build_task_prompt('Verified campaign facts', task, channel, 'Business', team)

    def test_paid_search_uses_pairs_and_verified_examples(self):
        for task in ('write', 'improve'):
            prompt = self.prompt('Google Paid Search', task)
            self.assertIn('exactly two headlines', prompt)
            self.assertIn('at most 30 characters', prompt)
            self.assertIn('at most 90 characters', prompt)
            self.assertIn('never as source facts', prompt)
            self.assertNotIn('Do not include a title', prompt)

    def test_website_keeps_component_structure_and_perspective(self):
        prompt = self.prompt('Website')
        self.assertIn('selected website component fields', prompt)
        self.assertIn('not website output structure', prompt)
        self.assertIn('perspective restrictions', prompt)
        self.assertNotIn('exactly two headlines', prompt)

    def test_other_channels_and_reviews_keep_existing_behavior(self):
        self.assertNotIn('Execute the active B2B', self.prompt('Website', team='b2c'))
        self.assertNotIn('exactly two headlines', self.prompt('Google Paid Search', task='review'))


if __name__ == '__main__':
    unittest.main()
