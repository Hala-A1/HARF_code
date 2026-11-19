import unittest
from access_control import instruction_text_for
from ai_service import build_task_prompt

class InstructionRoutingTests(unittest.TestCase):
    def test_b2b_dictionary_and_website_scope(self):
        website = instruction_text_for('b2b', 'Website')
        self.assertIn('# B2B Brand Dictionary', website)
        self.assertIn('# B2B Website Tone of Voice', website)
        paid = instruction_text_for('b2b', 'Google Paid Search')
        self.assertIn('# B2B Brand Dictionary', paid)
        self.assertNotIn('# B2B Website Tone of Voice', paid)
        for channel in ['b2c', 'security']:
            self.assertNotIn('# B2B Brand Dictionary', instruction_text_for(channel))

    def test_security_memo_not_all_tables(self):
        prompt = build_task_prompt('Policy facts', team_channel='security')
        self.assertIn('headings and paragraphs', prompt)
        self.assertIn('120 words', prompt)
        self.assertNotIn('Return exactly these three', prompt)
        self.assertIn('Never include CTIO', prompt)
