import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import copywriter


class GenerationInstructionEnhancerTests(unittest.TestCase):
    def setUp(self):
        self.user = {'email': 'user@example.test', 'name': 'Test', 'role': 'user',
                     'channel_id': 'b2c', 'workspaces': ['rewrite']}

    def test_refines_arabic_instructions_without_generating_customer_copy(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='b2c', instructions='خليها قصيرة ولا تغير السعر', context='السعر 100 درهم')
        with patch('ai_service._run_completion', return_value=json.dumps({'instructions': 'اكتب نصاً موجزاً مع الحفاظ على السعر دون تغيير.'}, ensure_ascii=False)) as complete:
            result = copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertIn('الحفاظ على السعر', result['instructions'])
        self.assertIn('not the customer content', complete.call_args.args[0])
        self.assertIn('100', complete.call_args.args[1])

    def test_cannot_refine_for_another_channel(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='security', instructions='Keep it short')
        with patch('ai_service._run_completion') as complete, self.assertRaises(HTTPException) as caught:
            copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertEqual(caught.exception.status_code, 403)
        complete.assert_not_called()

    def test_invalid_response_keeps_original_and_returns_error(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='b2c', instructions='Keep the price')
        with patch('ai_service._run_completion', return_value='{"instructions":""}'), self.assertRaises(HTTPException):
            copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertEqual(request.instructions, 'Keep the price')

    def test_english_directions_stay_english_despite_arabic_context_and_output_request(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='b2c', instructions='Write the customer copy in Arabic. Keep it short.', context='نص عربي طويل ' * 100)
        with patch('ai_service._run_completion', return_value=json.dumps({'instructions': 'Write concise Arabic customer copy.'})) as complete:
            result = copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertEqual(result['instructions'], 'Write concise Arabic customer copy.')
        self.assertIn('REQUIRED RESPONSE LANGUAGE: English', complete.call_args.args[0])
        self.assertEqual(json.loads(complete.call_args.args[1])['response_language'], 'en')

    def test_wrong_language_is_automatically_recovered_once(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='b2c', instructions='Keep it short and reassuring.')
        answers = [json.dumps({'instructions': 'اكتب النص بأسلوب موجز ومطمئن.'}), json.dumps({'instructions': 'Use concise, reassuring wording.'})]
        with patch('ai_service._run_completion', side_effect=answers) as complete:
            result = copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertEqual(complete.call_count, 2)
        self.assertEqual(result['instructions'], 'Use concise, reassuring wording.')

    def test_quoted_arabic_is_preserved_without_changing_instruction_language(self):
        self.assertEqual(copywriter.instruction_draft_language('Include exactly "تطبق الشروط والأحكام على جميع الخدمات المذكورة".'), 'en')
        self.assertEqual(copywriter.instruction_draft_language('اكتب بوضوح مع الحفاظ على "Business Cloud Backup for Enterprise".'), 'ar')

    def test_persistent_wrong_language_is_not_presented_as_a_success(self):
        request = copywriter.InstructionEnhanceRequest(team_channel='b2c', instructions='Keep it short.')
        with patch('ai_service._run_completion', return_value=json.dumps({'instructions': 'اكتب النص بأسلوب موجز.'})), self.assertRaises(HTTPException):
            copywriter.enhance_generation_instructions.__wrapped__(request, self.user)
        self.assertEqual(request.instructions, 'Keep it short.')
