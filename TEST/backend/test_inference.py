import asyncio
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from docx import Document
import access_control
import ai_service
from generation_context import GenerationContext, bind_generation
from inference import (inference_scope, resolve, confidential, bootstrap, RoutedClient,
                       InferencePolicyError, ResponseStream, route_identity)
from inference_guard import remember
from main import app


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'access-control.json'
        self.path.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf8')
        for patcher in [patch.object(access_control, 'DATA_FILE', self.path), patch.dict(os.environ, {
            'MODEL_PROVIDER': 'live', 'INFERENCE_CONNECTION_SOURCE': 'environment',
            'REWRITE_STORAGE_BACKEND': 'local', 'AUTH_PROVIDER': '', 'DEVELOPER_MODE': 'false',
            'PLATFORM_POLICY_ENV_FILE': str(self.path.parent / 'model-policy.env'),
            'APIM_BASE_URL': 'https://cloud.example.test/openai', 'APIM_API_KEY': 'fictional-cloud-key',
            'APIM_API_VERSION': '2025-04-01-preview', 'APIM_API_TYPE': 'responses', 'APIM_API_STYLE': 'azure',
            'APIM_AUTH_HEADER': 'api-key', 'AZURE_EXPLICIT_DEPLOYMENTS': '["cloud-text"]',
            'LITELLM_BASE_URL': 'https://internal.example.test', 'LITELLM_API_KEY': 'fictional-internal-key',
            'LITELLM_API_TYPE': 'chat_completions', 'ON_PREM_EXPLICIT_MODELS': '["local-a","local-b"]',
        })]:
            patcher.start(); self.addCleanup(patcher.stop)
        self.client = TestClient(app)

    def headers(self, email='developer@eand.ae', private=False):
        return {'X-User-Email': email, **({'X-Confidential-Document': 'true'} if private else {})}

    def test_confidential_overrides_channel_cloud_preference(self):
        settings = bootstrap()
        settings['channels']['security'] = 'cloud:cloud-text'
        with inference_scope({'channel': 'security', 'confidential': True, 'policy': settings}):
            self.assertEqual(resolve()['gateway'], 'onprem')
            self.assertEqual(resolve()['upstream'], 'local-a')

    def test_no_fallback_if_local_disabled_missing_or_not_allowed(self):
        for reason in ['disabled', 'cloud', 'not-allowed']:
            settings = bootstrap()
            if reason == 'disabled': settings['models'][1]['enabled'] = False
            elif reason == 'cloud': settings['confidential_model'] = 'cloud:cloud-text'
            else: settings['models'][1]['upstream'] = 'unapproved'
            with inference_scope({'confidential': True, 'policy': settings}), self.assertRaises(InferencePolicyError):
                resolve()

    def test_missing_internal_key_cannot_use_cloud(self):
        with patch.dict(os.environ, {'LITELLM_API_KEY': ''}), inference_scope({'confidential': True}), self.assertRaises(InferencePolicyError):
            ai_service.get_client()

    def test_confidential_model_survives_worker_and_source_fact_scopes(self):
        with inference_scope({'channel': 'b2b', 'confidential': True}):
            context = GenerationContext('b2b', 'Private brief')
        def work(_):
            with bind_generation(context), bind_generation(None):
                return confidential(), resolve()['gateway']
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(work, range(4))), [(True, 'onprem')] * 4)
        self.assertFalse(confidential())

    def test_responses_adapts_messages_json_streaming_and_no_remote_storage(self):
        with inference_scope({'confidential': False}):
            row = resolve()
        sdk = MagicMock()
        sdk.responses.create.return_value = NS(status='completed', output_text='Result')
        row['vision'] = True
        client = RoutedClient(row, sdk)
        result = client.chat.completions.create(model='ignored', messages=[{'role':'user','content':[{'type':'text','text':'Brief'}, {'type':'image_url','image_url':{'url':'data:image/png;base64,AA'}}]}], response_format={'type':'json_object'})
        self.assertEqual(result.choices[0].message.content, 'Result')
        args = sdk.responses.create.call_args.kwargs
        self.assertFalse(args['store'])
        self.assertEqual(args['input'][0]['content'][1]['type'], 'input_image')
        self.assertEqual(args['text']['format']['type'], 'json_object')
        sdk.chat.completions.create.assert_not_called()
        events = iter([NS(type='response.output_text.delta',delta='Hello'), NS(type='response.completed')])
        parts = list(ResponseStream(events))
        self.assertEqual(parts[0].choices[0].delta.content, 'Hello')
        self.assertEqual(parts[-1].choices[0].finish_reason, 'stop')
        with self.assertRaises(ValueError): list(ResponseStream(iter([])))

    def test_onprem_chat_and_vision_block_before_network(self):
        with inference_scope({'confidential': True}):
            row = resolve(); sdk = MagicMock(); client = RoutedClient(row, sdk)
            client.create(model='ignored', messages=[{'role':'user','content':'Brief'}])
            self.assertEqual(sdk.chat.completions.create.call_args.kwargs['model'], 'local-a')
            sdk.responses.create.assert_not_called()
            sdk.reset_mock()
            with self.assertRaises(InferencePolicyError):
                client.create(model='ignored', messages=[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,AA'}}]}])
            sdk.chat.completions.create.assert_not_called()

    def test_connections_do_not_follow_redirects_or_append_v1(self):
        with inference_scope({'confidential': True}), patch('inference.OpenAI') as sdk:
            client = RoutedClient()
            options = sdk.call_args.kwargs
            self.assertEqual(options['base_url'], 'https://internal.example.test')
            self.assertFalse(options['http_client'].follow_redirects)
            options['http_client'].close(); client.close()

    def test_admin_only_inventory_defaults_validation_and_revision(self):
        for actor in ['b2c.admin@eand.ae', 'b2c.user@eand.ae', 'b2c.approver1@eand.ae']:
            self.assertEqual(self.client.get('/api/access/inference/policy',headers=self.headers(actor)).status_code,403)
        response = self.client.get('/api/access/inference/policy',headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn('fictional-',response.text)
        result = response.json()
        payload = {key:result[key] for key in ['models','default_model','confidential_model','channels']}
        payload['expected_revision'] = 0
        payload['confidential_model'] = 'cloud:cloud-text'
        self.assertEqual(self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload).status_code,422)
        payload['confidential_model'] = 'onprem:local-b'
        self.assertEqual(self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload).status_code,200)
        self.assertEqual(self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload).status_code,409)

    def test_ledger_enforces_classification_without_browser_header(self):
        source = 'Private regulatory source with device identifiers.'
        remember({'confidential': True, 'channel':'security'},[source])
        with patch('copywriter.analyze_copy', side_effect=lambda *args: {'gateway':resolve()['gateway']}):
            response = self.client.post('/api/analyze', headers=self.headers('security.user@eand.ae'),json={'team_channel':'security','generated':'Memo','original':source})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['gateway'],'onprem')
        self.assertEqual(response.headers['x-content-classification'],'confidential')
        self.assertNotIn(source, json.dumps(access_control.load_access_data()['confidential_content']))

    def test_confidential_saved_copy_persists_classification_and_gateway(self):
        response = self.client.post('/api/approvals/draft',headers=self.headers('security.user@eand.ae',True),json={'team_channel':'security','source':'Secret brief','english':'Secret memo'})
        self.assertEqual(response.status_code,200,response.text)
        batch = response.json()
        self.assertTrue(batch['confidential'])
        self.assertEqual(batch['inference_gateway'],'onprem')
        result = self.client.get('/api/approvals/'+batch['id'],headers=self.headers('security.user@eand.ae'))
        self.assertEqual(result.headers['x-content-classification'],'confidential')

    def test_confidential_native_word_never_calls_external_docling(self):
        from docling_client import extract_document
        doc = Document(); doc.add_paragraph('Confidential native source.'); buffer = io.BytesIO(); doc.save(buffer)
        with inference_scope({'confidential': True}), patch('docling_client.httpx.AsyncClient') as external:
            result = asyncio.run(extract_document('brief.docx',buffer.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
        self.assertEqual(result,'Confidential native source.')
        external.assert_not_called()

    def test_cache_identity_is_separate_for_cloud_and_confidential(self):
        with inference_scope({'confidential':False}): cloud = route_identity()
        with inference_scope({'confidential':True}): private = route_identity()
        self.assertNotEqual(cloud,private)

    def test_protected_file_reupload_cannot_call_docling_with_flag_removed(self):
        headers = self.headers('security.user@eand.ae', True)
        content = b'Private uploaded source document.'
        first = self.client.post('/api/extract-upload?team_channel=security',headers=headers,files={'file':('source.txt',content,'text/plain')})
        self.assertEqual(first.status_code,200,first.text)
        self.assertTrue(first.json()['confidential'])
        second = self.client.post('/api/extract-upload?team_channel=security',headers=self.headers('security.user@eand.ae'),files={'file':('renamed.txt',content,'text/plain')})
        self.assertEqual(second.status_code,200,second.text)
        self.assertTrue(second.json()['confidential'])
        self.assertEqual(second.headers['x-content-classification'],'confidential')

    def test_failed_generation_still_preserves_source_classification(self):
        payload = {'team_channel':'security','feedback':'Confidential source that failed generation.'}
        with patch('copywriter.enhance_feedback',side_effect=InferencePolicyError('No internal model configured')):
            response = self.client.post('/api/enhance',headers=self.headers('security.user@eand.ae',True),json=payload)
        self.assertEqual(response.status_code,409,response.text)
        with patch('copywriter.enhance_feedback',side_effect=lambda *args: resolve()['gateway']):
            response = self.client.post('/api/enhance',headers=self.headers('security.user@eand.ae'),json=payload)
        self.assertEqual(response.json()['enhanced'],'onprem')

    def test_unauthorized_user_cannot_classify_another_channel(self):
        response = self.client.post('/api/analyze',headers=self.headers('b2c.user@eand.ae',True),json={'team_channel':'security','generated':'Memo','original':'Private source'})
        self.assertEqual(response.status_code,403)
        self.assertNotIn('confidential_content',access_control.load_access_data())

    def test_streamed_output_is_protected_for_later_translation(self):
        with patch('copywriter.stream_enhance_feedback',side_effect=lambda *args: (part for part in ['Private ', 'memo.'])):
            response = self.client.post('/api/enhance/stream',headers=self.headers('security.user@eand.ae',True),json={'team_channel':'security','feedback':'Private source'})
        self.assertEqual(response.status_code,200,response.text)
        with patch('copywriter.analyze_copy',side_effect=lambda *args: {'gateway':resolve()['gateway']}):
            result = self.client.post('/api/analyze',headers=self.headers('security.user@eand.ae'),json={'team_channel':'security','generated':'Private memo.','original':''})
        self.assertEqual(result.json()['gateway'],'onprem')

    def test_cloud_client_cannot_be_reused_for_private_content(self):
        with inference_scope({'confidential':False}):
            client = RoutedClient(resolve(),MagicMock())
        with inference_scope({'confidential':True}),self.assertRaises(InferencePolicyError):
            client.create(model='cloud-text',messages=[{'role':'user','content':'Private'}])
        client.sdk.responses.create.assert_not_called()

    def test_real_sdk_urls_protocols_and_auth_using_mock_transport(self):
        import httpx
        from openai import OpenAI
        requests = []
        def respond(request):
            requests.append(request)
            if request.url.path.endswith('/responses'):
                return httpx.Response(200,json={'id':'resp1','object':'response','created_at':0,'status':'completed','model':'cloud-text','output':[{'type':'message','id':'msg1','role':'assistant','status':'completed','content':[{'type':'output_text','text':'OK','annotations':[]}]}]})
            return httpx.Response(200,json={'id':'chat1','object':'chat.completion','created':0,'model':'local-a','choices':[{'index':0,'message':{'role':'assistant','content':'OK'},'finish_reason':'stop'}]})
        def sdk(**kwargs):
            kwargs['http_client'].close()
            kwargs['http_client'] = httpx.Client(transport=httpx.MockTransport(respond),follow_redirects=False)
            return OpenAI(**kwargs)
        for private in [False,True]:
            with inference_scope({'confidential':private}),patch('inference.OpenAI',side_effect=sdk),RoutedClient() as client:
                self.assertEqual(client.create(model='',messages=[{'role':'user','content':'Synthetic'}]).choices[0].message.content,'OK')
        self.assertEqual(requests[0].url.path,'/openai/responses')
        self.assertEqual(requests[0].url.params['api-version'],'2025-04-01-preview')
        self.assertEqual(requests[0].headers['api-key'],'fictional-cloud-key')
        self.assertNotIn('authorization', requests[0].headers)
        self.assertEqual(requests[1].url.path,'/chat/completions')
        self.assertEqual(requests[1].headers['authorization'],'Bearer fictional-internal-key')
        self.assertNotIn('store',json.loads(requests[1].content))

    def test_storage_outage_cannot_skip_classification_and_call_cloud(self):
        import oracledb
        with patch('inference_guard.classify',side_effect=oracledb.Error('unavailable')),patch('copywriter.analyze_copy') as model:
            response = self.client.post('/api/analyze',headers=self.headers('security.user@eand.ae'),json={'team_channel':'security','generated':'Memo','original':'Source'})
        self.assertEqual(response.status_code,503,response.text)
        model.assert_not_called()

if __name__ == '__main__': unittest.main()
