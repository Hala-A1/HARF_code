import json
import os
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

import httpx
from openai import AzureOpenAI, RateLimitError
from fastapi import HTTPException
import admin
from generation_context import GenerationContext, bind_generation
from llm_rate_limits import LLMRateLimits, RateLimitedHttpClient, LLMRateLimitError, acquire_slot, channel_scope, request_channel
from stream_errors import stream_error_details


class LLMRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.envfile = Path(self.directory.name)/'limits.env'
        self.environment = patch.dict(os.environ, {
            'REWRITE_STORAGE_BACKEND':'local', 'LLM_RATE_DB':str(Path(self.directory.name)/'rate.sqlite3'),
            'LLM_RATE_ENV_FILE':str(self.envfile), 'LLM_REQUESTS_PER_MINUTE':'50',
            'LLM_CHANNEL_REQUESTS_PER_MINUTE':'50', 'LLM_CHANNEL_RATE_LIMITS':'{}'})
        self.environment.start()
        self.store=LLMRateLimits()
    def tearDown(self):
        self.environment.stop(); self.directory.cleanup()

    def test_global_cap_is_shared_across_channels_and_is_rolling(self):
        for index in range(50):self.assertEqual(self.store.reserve('b2b' if index%2 else 'b2c',now=100),0)
        self.assertEqual(self.store.reserve('security',now=100),60)
        self.assertAlmostEqual(self.store.reserve('security',now=159.9),.1)
        self.assertEqual(self.store.reserve('security',now=160),0)

    def test_channel_cap_does_not_block_other_channels(self):
        with patch.dict(os.environ,{'LLM_CHANNEL_RATE_LIMITS':'{"b2b":2}'}):
            self.assertEqual(self.store.reserve('b2b',now=100),0)
            self.assertEqual(self.store.reserve('b2b',now=101),0)
            self.assertEqual(self.store.reserve('b2b',now=102),58)
            self.assertEqual(self.store.reserve('b2c',now=102),0)

    def test_concurrent_instances_cannot_oversubscribe(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            waits=list(pool.map(lambda _:LLMRateLimits().reserve('b2c',now=100),range(80)))
        self.assertEqual(waits.count(0),50)
        self.assertEqual(waits.count(60),30)

    def test_admin_updates_persist_in_environment_and_shared_store(self):
        actor={'email':'super@example.test'}
        self.store.update(25,'b2c',7,actor)
        from dotenv import dotenv_values
        self.assertEqual(dotenv_values(self.envfile)['LLM_REQUESTS_PER_MINUTE'], '25')
        self.assertIn('"b2c": 7',self.envfile.read_text())
        self.assertEqual(os.environ['LLM_REQUESTS_PER_MINUTE'],'25')
        self.assertEqual(LLMRateLimits().summary()['channels']['b2c'],7)
        with patch.dict(os.environ,{'LLM_REQUESTS_PER_MINUTE':'999'}):self.assertEqual(LLMRateLimits().summary()['application'],25)

    def test_reducing_a_limit_keeps_recent_usage(self):
        for now in [100,101,102]:self.store.reserve('b2c',now=now)
        # Avoid real-clock pruning by editing the stored config directly.
        with self.store.state() as state:state['settings']={'application':2,'default_channel':50,'channels':{}}
        self.assertEqual(self.store.reserve('b2c',now=103),58)

    def test_waiting_releases_db_lock_and_timeout_never_sends(self):
        with patch('llm_rate_limits.LLMRateLimits.reserve',return_value=60),self.assertRaises(LLMRateLimitError):
            acquire_slot('b2c',max_wait=0)
        with patch('llm_rate_limits.LLMRateLimits.reserve',side_effect=[.01,0]) as reserve,patch('llm_rate_limits.time.sleep') as sleep:
            acquire_slot('b2c',max_wait=1)
        self.assertEqual(reserve.call_count,2);sleep.assert_called_once()

    def test_sdk_retries_each_take_a_slot_for_stream_and_normal_calls(self):
        attempts=[]
        def response(request):
            attempts.append(request)
            if len(attempts)==1:return httpx.Response(429,headers={'retry-after-ms':'1'},json={'error':{'message':'busy','code':'rate_limit_exceeded'}},request=request)
            return httpx.Response(200,json={'choices':[{'message':{'content':'ok'},'finish_reason':'stop','index':0}]},request=request)
        with patch('llm_rate_limits.acquire_slot') as acquire,channel_scope('b2c'):
            with AzureOpenAI(api_key='fictional',azure_endpoint='https://example.test',api_version='2024-10-21',max_retries=1,http_client=RateLimitedHttpClient(transport=httpx.MockTransport(response))) as client:
                client.chat.completions.create(model='test',messages=[{'role':'user','content':'test'}])
        self.assertEqual(acquire.call_count,2)
        self.assertTrue(all(call.args==('b2c',) for call in acquire.call_args_list))

    def test_local_queue_full_is_not_retried_by_sdk(self):
        with patch('llm_rate_limits.acquire_slot',side_effect=LLMRateLimitError('busy')) as acquire:
            with AzureOpenAI(api_key='fictional',azure_endpoint='https://example.test',api_version='2024-10-21',max_retries=2,http_client=RateLimitedHttpClient(transport=httpx.MockTransport(lambda _:self.fail('No provider request allowed')))) as client:
                with self.assertRaises(RateLimitError) as caught:client.chat.completions.create(model='test',messages=[])
        self.assertEqual(acquire.call_count,1)
        self.assertEqual(stream_error_details(caught.exception)['code'],'llm_rate_limit')

    def test_stream_attempt_uses_same_gate(self):
        with patch('llm_rate_limits.acquire_slot') as acquire,channel_scope('security'):
            with RateLimitedHttpClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'data: [DONE]\n\n',request=request))) as client:
                with client.stream('POST','https://example.test/openai/deployments/test/chat/completions') as response:response.read()
        acquire.assert_called_once_with('security')

    def test_generation_channel_overrides_fallback_and_restores(self):
        with channel_scope('b2c'):
            self.assertEqual(request_channel(),'b2c')
            with bind_generation(GenerationContext('b2b','test')):self.assertEqual(request_channel(),'b2b')
            self.assertEqual(request_channel(),'b2c')
        self.assertIsNone(request_channel())

    def test_only_super_admin_can_read_or_update(self):
        for role in ['user','approval_admin','channel_admin']:
            user={'role':role,'email':'test@example.test','channel_id':'b2c'}
            with self.assertRaises(HTTPException):admin.llm_request_limits(user)
            with self.assertRaises(HTTPException):admin.update_llm_request_limits(admin.LLMMinuteLimitRequest(application=50,channel_id='b2c',channel_limit=10),user)

    def test_invalid_ui_values_are_rejected(self):
        from pydantic import ValidationError
        for value in [0,-1,5001,1.5,True]:
            with self.assertRaises(ValidationError):admin.LLMMinuteLimitRequest(application=value,channel_id='b2c',channel_limit=50)


if __name__=='__main__':unittest.main()
