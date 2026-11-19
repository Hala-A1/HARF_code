import json
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

import access_control
from input_tokens import enforce, count_input, InputTokenLimitError
from platform_policy import settings
from token_usage import MeteredClient
from inference import RoutedClient
import test_platform_policy


class InputTokenTests(unittest.TestCase):
    def setUp(self):
        test_platform_policy.RetentionTests.setUp(self)
        models=patch.dict(os.environ, {'AZURE_EXPLICIT_DEPLOYMENTS':'["gpt-4o"]','ON_PREM_EXPLICIT_MODELS':'["local-test"]'})
        models.start();self.addCleanup(models.stop)

    def configure(self, limit):
        self.env.write_text(f'USER_LOG_RETENTION_DAYS=180\nDEFAULT_MAX_INPUT_TOKENS={limit}\nLLM_MODEL_INPUT_TOKEN_LIMITS={{}}\n',encoding='utf8')

    def save_model_limit(self, limit, headers=None):
        current=self.client.get('/api/access/inference/policy',headers=self.admin).json()
        payload={key:current[key] for key in ['models','default_model','confidential_model','channels']}
        payload['expected_revision']=current['revision']
        payload['models'][0]['max_input_tokens']=limit
        return self.client.put('/api/access/inference/policy',headers=headers or self.admin,json=payload)

    def test_input_limit_updates_immediately_and_preserves_retention(self):
        messages=[{'role':'system','content':'Guidelines '*100},{'role':'user','content':'مرحبا '*200}]
        self.configure(256)
        with self.assertRaises(InputTokenLimitError):enforce(messages,'gpt-4o')
        response=self.save_model_limit(10000)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(settings()['model_input_token_limits']['cloud:gpt-4o'],10000)
        self.assertIn('LLM_MODEL_INPUT_TOKEN_LIMITS=',self.env.read_text())
        self.assertEqual(settings()['retention_days'],180)
        self.assertLess(enforce(messages,'gpt-4o')['tokens'],10000)
        self.client.put('/api/access/platform-policy',headers=self.admin,json={'retention_days':365})
        self.assertEqual(settings()['model_input_token_limits']['cloud:gpt-4o'],10000)
        self.assertNotIn('token_budget',response.json())
        self.assertNotIn('monthly_token_limit',response.json())

    def test_only_super_admin_may_change_input_limit_and_invalid_values_are_rejected(self):
        for email in ['b2b.admin@eand.ae','b2b.user@eand.ae','b2b.approver1@eand.ae']:
            self.assertEqual(self.save_model_limit(10000,{'X-User-Email':email}).status_code,403)
        for value in [0,-1,True,'5000',10.5]:
            self.assertEqual(self.save_model_limit(value).status_code,422)
        self.assertEqual(self.client.put('/api/access/platform-policy',headers=self.admin,json={'max_input_tokens':10000}).status_code,422)
        self.assertEqual(self.client.put('/api/access/platform-policy',headers=self.admin,json={'monthly_token_limit':10000}).status_code,422)

    def test_model_limits_have_no_arbitrary_configuration_ceiling(self):
        for limit in [1,255,2000001,10000000]:
            response=self.save_model_limit(limit)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(settings()['model_input_token_limits']['cloud:gpt-4o'],limit)
        from inference_admin import ModelRow
        for limit in [1,255,128001,10000000]:
            row=ModelRow(id='test',name='Test',upstream='test',gateway='cloud',max_tokens=limit)
            self.assertEqual(row.max_tokens,limit)
        self.configure(10000000)
        self.assertEqual(settings()['default_max_input_tokens'],10000000)

    def test_english_and_arabic_are_counted_offline_including_rules_and_schema(self):
        from input_tokens import encoding
        encoding.cache_clear()
        messages=[{'role':'system','content':'Preserve all prices and dates.'},{'role':'user','content':'Hello مرحبا بالعالم'}]
        with patch('requests.get',side_effect=AssertionError('No network for token counting')):
            result=count_input(messages,'gpt-4o')
        self.assertFalse(result['estimated'])
        plain=count_input([messages[1]],'gpt-4o')['tokens']
        self.assertGreater(result['tokens'],plain)
        self.assertGreater(count_input(messages,'gpt-4o',{'type':'json_schema','schema':{'title':'Offer'}})['tokens'],result['tokens'])
        unknown=count_input(messages,'onprem-custom')
        self.assertTrue(unknown['estimated'])
        self.assertGreater(unknown['tokens'],result['tokens'])
        self.assertEqual(messages[1]['content'],'Hello مرحبا بالعالم')

    def test_boundary_accepts_exact_limit_and_rejects_above_without_truncation(self):
        messages=[{'role':'user','content':'Meaningful details '*400}]
        total=count_input(messages,'gpt-4o')['tokens']
        self.configure(total)
        self.assertEqual(enforce(messages,'gpt-4o')['tokens'],total)
        self.configure(total-1)
        with self.assertRaises(InputTokenLimitError) as caught:enforce(messages,'gpt-4o')
        self.assertIn(f'{total:,}',str(caught.exception))
        self.assertIn('Nothing was truncated',str(caught.exception))
        self.assertEqual(messages[0]['content'],'Meaningful details '*400)

    def test_images_use_vision_estimate_instead_of_base64_text_length(self):
        messages=[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,'+'A'*200000}}]}]
        result=count_input(messages,'gpt-4o')
        self.assertTrue(result['estimated'])
        self.assertLess(result['tokens'],40000)

    def test_different_model_limits_apply_to_routed_calls_and_legacy_deployment(self):
        self.configure(64000)
        self.save_model_limit(256)
        current=self.client.get('/api/access/inference/policy',headers=self.admin).json()
        local=next(row for row in current['models'] if row['gateway']=='onprem')
        messages=[{'role':'user','content':'Source facts '*300}]
        with self.assertRaises(InputTokenLimitError):enforce(messages,'gpt-4o')
        self.assertLess(enforce(messages,'local-test',model_id=local['id'],maximum=local['max_input_tokens'])['tokens'],64000)
        # A new env override must also update an already-created/pinned route.
        config=settings();config['model_input_token_limits'][local['id']]=256
        from platform_policy import write_settings
        write_settings(self.env,config)
        with self.assertRaises(InputTokenLimitError):enforce(messages,'local-test',model_id=local['id'],maximum=64000)

    def test_failed_model_save_rolls_environment_back_without_changing_other_models(self):
        self.configure(64000)
        self.save_model_limit(4000)
        before=self.env.read_text(encoding='utf8')
        current=self.client.get('/api/access/inference/policy',headers=self.admin).json()
        payload={key:current[key] for key in ['models','default_model','confidential_model','channels']}
        payload['expected_revision']=current['revision']
        payload['models'][0]['max_input_tokens']=2000
        with patch('inference_admin.save_access_data',side_effect=OSError('Fictional storage failure')):
            with self.assertRaises(OSError):
                self.client.put('/api/access/inference/policy',headers=self.admin,json=payload)
        self.assertEqual(self.env.read_text(encoding='utf8'),before)
        self.assertEqual(settings()['model_input_token_limits']['cloud:gpt-4o'],4000)
        self.assertEqual(settings()['model_input_token_limits']['onprem:local-test'],64000)

    def test_oversized_calls_never_reach_legacy_or_routed_providers_including_streams(self):
        self.configure(256)
        messages=[{'role':'system','content':'Rules '*400},{'role':'user','content':'Brief '*400}]
        for protocol in ['responses','chat_completions']:
            for stream in [False,True]:
                sdk=MagicMock()
                row={'gateway':'cloud' if protocol=='responses' else 'onprem','upstream':'gpt-4o','protocol':protocol,'vision':True,'header':'api-key','temperature':0.7,'max_tokens':500}
                with self.assertRaises(InputTokenLimitError):RoutedClient(row,sdk).create(model='ignored',messages=messages,stream=stream)
                sdk.responses.create.assert_not_called();sdk.chat.completions.create.assert_not_called()
        sdk=MagicMock()
        with self.assertRaises(InputTokenLimitError):MeteredClient(sdk).with_options(timeout=3).create(messages=messages,model='gpt-4o')
        sdk.with_options.return_value.chat.completions.create.assert_not_called()

    def test_output_limit_and_usage_reporting_stay_separate_without_monthly_charges(self):
        self.configure(10000)
        sdk=MagicMock();sdk.chat.completions.create.return_value=NS(usage=NS(prompt_tokens=8,completion_tokens=5,total_tokens=13))
        from llm_rate_limits import channel_scope
        for n in range(3):
            with channel_scope('b2b'):
                MeteredClient(sdk).create(model='gpt-4o',messages=[{'role':'user','content':'Hi'}],max_tokens=777)
        self.assertEqual(sdk.chat.completions.create.call_args.kwargs['max_tokens'],777)
        self.assertNotIn('token_budget',access_control.load_access_data())
        usage=access_control.load_access_data()['token_usage']['channels']['b2b']
        self.assertEqual(sum(row['total_tokens'] for row in usage.values()),39)

    def test_clear_http_and_stream_errors_without_retry(self):
        from stream_errors import stream_error_details
        error=InputTokenLimitError(1500,1000)
        self.assertFalse(stream_error_details(error)['retryable'])
        with patch('copywriter.enhance_feedback',side_effect=error):
            result=self.client.post('/api/enhance',headers={'X-User-Email':'b2b.admin@eand.ae'},json={'feedback':'Hi','team_channel':'b2b'})
        self.assertEqual(result.status_code,413,result.text)
        self.assertIn('input tokens',result.json()['detail'])


if __name__=='__main__':unittest.main()
