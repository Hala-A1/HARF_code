import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import access_control
import feedback
from main import app
from llm_rate_limits import channel_scope
from token_usage import record, MeteredClient


class PlatformPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'access.json'
        self.secret = 'PRIVATE_CONTENT_MARKER_8372'
        data = copy.deepcopy(access_control.DEFAULT_DATA)
        for channel in data['channels']:
            channel.update(private_context=self.secret, instruction_modules=[self.secret], description=self.secret)
        for member in data['users']:
            member['private_note'] = self.secret
        data['activity'] = [{'action':'Copy generated','detail':self.secret,'channel_id':'b2b','actor_email':'b2b.user@eand.ae','metadata':{'source':self.secret,'generated':self.secret}}]
        data['approval_batches'] = [{'id':'private-batch','title':self.secret,'channel_id':'b2b','created_by_email':'b2b.user@eand.ae','created_by':'Author','created_at':'2026-10-30T10:00:00Z','status':'pending_layer_1','current_layer':1,'languages':['en'],'instructions':self.secret,'events':[{'note':self.secret}], 'items':[{'id':'item','filename':self.secret,'source':self.secret,'generated':{'en':self.secret}}]}]
        data['notifications'] = [{'id':'old-private','recipient_email':'developer@eand.ae','title':self.secret,'message':self.secret,'read':False}]
        self.path.write_text(json.dumps(data),encoding='utf8')
        for p in [patch.object(access_control,'DATA_FILE',self.path),patch.object(feedback,'FEEDBACK_DB',Path(self.temp.name)/'feedback.sqlite3')]:
            p.start(); self.addCleanup(p.stop)
        self.client=TestClient(app)
        self.root={'X-User-Email':'developer@eand.ae'}
        self.admin={'X-User-Email':'b2b.admin@eand.ae'}

    def test_overview_and_profile_have_no_channel_content(self):
        for url in ['/api/access/me','/api/access/overview','/api/access/platform-overview','/api/access/request-limits/b2b']:
            result=self.client.get(url,headers=self.root)
            self.assertEqual(result.status_code,200,(url,result.text))
            self.assertNotIn(self.secret,result.text)
        overview=self.client.get('/api/access/overview',headers=self.root).json()
        self.assertEqual(overview['activity'],[])
        self.assertNotIn('instruction_modules',overview['channels'][0])
        self.assertEqual(self.client.get('/api/access/me',headers=self.root).json()['workspaces'],['rewrite'])

    def test_all_content_read_paths_deny_platform_admin(self):
        urls=['/api/approvals/private-batch', '/api/feedback?channel_id=b2b','/api/feedback/known-id',
              '/api/access/channels/b2b/approval-policy']
        for url in urls:
            response=self.client.get(url,headers=self.root)
            self.assertEqual(response.status_code,403,(url,response.text))
            self.assertNotIn(self.secret,response.text)
            self.assertNotIn('x-content-classification',response.headers)

    def test_selected_channel_performance_is_aggregate_and_content_free(self):
        data=access_control.load_access_data()
        event={'timestamp':datetime.now(timezone.utc).isoformat(),'action':'Bilingual copy generated',
               'channel_id':'b2b','actor_email':'b2b.user@eand.ae',
               'metadata':{'generated':{'en':self.secret,'ar':self.secret},'content_channel':self.secret,'task':self.secret}}
        access_control.record_activity(data, data['users'][0], event['action'],self.secret,'b2b',event['metadata'])
        access_control.save_access_data(data)
        response=self.client.get('/api/access/channels/b2b/performance?days=30',headers=self.root)
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn(self.secret,response.text)
        result=response.json()
        self.assertEqual(result['outputs'],2)
        self.assertEqual(len(result['daily']),30)
        self.assertNotIn('approvals',result)
        self.assertEqual(result['formats'],[{'name':'Other','count':2}])
        other=self.client.get('/api/access/channels/b2c/performance?days=30',headers=self.root).json()
        self.assertEqual(other['outputs'],0)
        selected=self.client.get('/api/access/platform-overview?channel_id=b2b',headers=self.root).json()
        self.assertEqual([row['id'] for row in selected['channels']],['b2b'])
        self.assertEqual(selected['totals']['channels'],1)
        self.assertEqual(self.client.get('/api/access/platform-overview?channel_id=missing',headers=self.root).status_code,404)
        self.assertEqual(self.client.get('/api/access/channels/b2c/performance',headers=self.admin).status_code,403)

    def test_workspace_lists_are_available_without_other_users_content(self):
        for url, key in [('/api/approvals','batches'),('/api/approvals?channel_id=b2b&summary=true','batches'),
                         ('/api/activity','rows'),('/api/notifications','notifications')]:
            result=self.client.get(url,headers=self.root)
            self.assertEqual(result.status_code,200,(url,result.text))
            self.assertEqual(result.json()[key],[])
            self.assertNotIn(self.secret,result.text)
        self.assertEqual(self.client.get('/api/activity/copy:private-batch:item',headers=self.root).status_code,404)

    def test_super_admin_can_use_workspace_and_read_own_saved_work(self):
        from access_control import require_workspace_access
        from approval import _notify
        user=access_control.get_user('developer@eand.ae')
        require_workspace_access({**user,'workspaces':[]},'rewrite')
        data=access_control.load_access_data()
        own=copy.deepcopy(data['approval_batches'][0])
        own.update(id='own-batch',created_by_email=user['email'],title='Own copy')
        own['items'][0].update(source='Own input',generated={'en':'Own output'})
        data['approval_batches'].append(own)
        _notify(data,[user['email']],'Your copy approved','Own update',own,'approval')
        access_control.save_access_data(data)
        self.assertEqual(self.client.get('/api/approvals/own-batch',headers=self.root).status_code,200)
        self.assertEqual(len(self.client.get('/api/approvals',headers=self.root).json()['batches']),1)
        rows=self.client.get('/api/activity',headers=self.root).json()['rows']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['output'],'English\nOwn output')
        notifications=self.client.get('/api/notifications',headers=self.root).json()['notifications']
        self.assertEqual(len(notifications),1)
        self.assertEqual(notifications[0]['title'],'Your copy approved')

    def test_known_ids_cannot_bypass_approval_or_instruction_restrictions(self):
        actions=[('post','/api/approvals/private-batch/decision',{'action':'approve'}),
                 ('post','/api/approvals/private-batch/admin-action',{'action':'override_approve','reason':'Bypass'}),
                 ('post','/api/approvals/private-batch/move',{}),
                 ('put','/api/access/channels/b2b/approval-policy',{'final_approval_layer':1})]
        with patch('copywriter.analyze_copy') as check,patch('copywriter.enhance_feedback') as generate:
            for method,url,body in actions:
                result=getattr(self.client,method)(url,headers=self.root,json=body)
                self.assertEqual(result.status_code,403,(url,result.text))
            check.assert_not_called();generate.assert_not_called()
        self.assertEqual(self.client.post('/api/notifications/old-private/read',headers=self.root,json={}).status_code,404)
        data=access_control.load_access_data()
        self.assertEqual(data['approval_batches'][0]['status'],'pending_layer_1')
        self.assertFalse(data['notifications'][0]['read'])

    def test_channel_admin_retains_own_channel_workflow(self):
        result=self.client.get('/api/approvals/private-batch',headers=self.admin)
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn(self.secret,result.text)
        self.assertEqual(self.client.get('/api/approvals/private-batch',headers={'X-User-Email':'b2c.admin@eand.ae'}).status_code,403)
        self.assertEqual(self.client.get('/api/access/platform-overview',headers=self.admin).status_code,403)

    def test_platform_management_remains_available(self):
        self.assertEqual(self.client.get('/api/access/inference/policy',headers=self.root).status_code,200)
        self.assertEqual(self.client.put('/api/access/request-limits/b2b/channel',headers=self.root,json={'limit':50}).status_code,200)
        self.assertEqual(self.client.get('/api/access/llm-request-limits',headers=self.root).status_code,200)

    def test_no_new_content_notifications_to_super_admin(self):
        from approval import _notify,_admin_recipients
        data=access_control.load_access_data();data['notifications']=[]
        self.assertNotIn('developer@eand.ae',_admin_recipients(data,'b2b'))
        _notify(data,['developer@eand.ae','b2b.admin@eand.ae'],'Private','Private',data['approval_batches'][0],'approval')
        self.assertEqual([row['recipient_email'] for row in data['notifications']],['b2b.admin@eand.ae'])

    def test_measured_tokens_and_recent_users_are_aggregate_only(self):
        with channel_scope('b2b'):
            record({'input_tokens':11,'output_tokens':7,'total_tokens':18,'prompt':self.secret})
        data=access_control.load_access_data()
        member=next(row for row in data['users'] if row['email']=='b2b.user@eand.ae')
        member['created_at']=datetime.now(timezone.utc).isoformat()
        access_control.save_access_data(data)
        response=self.client.get('/api/access/platform-overview?days=7',headers=self.root)
        self.assertEqual(response.status_code,200,response.text)
        self.assertNotIn(self.secret,response.text)
        result=response.json();channel=next(row for row in result['channels'] if row['id']=='b2b')
        self.assertEqual(channel['tokens']['total_tokens'],18)
        self.assertEqual(channel['new_users'],1)
        self.assertEqual(result['totals']['reported_tokens'],18)
        self.assertNotIn('users',channel)
        self.assertNotIn(self.secret,json.dumps(data['token_usage']))

    def test_unknown_usage_is_unavailable_not_invented_zero(self):
        with channel_scope('b2b'): record(None)
        result=self.client.get('/api/access/platform-overview',headers=self.root).json()
        self.assertIsNone(result['totals']['reported_tokens'])
        row=next(row for row in result['channels'] if row['id']=='b2b')
        self.assertIsNone(row['tokens']);self.assertEqual(row['unreported_model_calls'],1)

    def test_stream_metering_captures_trailing_usage_without_content(self):
        from ai_service import stream_response_text
        sdk=MagicMock();sdk.with_options.return_value=sdk
        stream=MagicMock()
        stream.__iter__.return_value=iter([NS(choices=[NS(delta=NS(content='Hello'),finish_reason=None)],usage=None),NS(choices=[NS(delta=NS(content=''),finish_reason='stop')],usage=None),NS(choices=[],usage=NS(prompt_tokens=5,completion_tokens=2,total_tokens=7))])
        sdk.chat.completions.create.return_value=stream
        with channel_scope('b2b'),patch('ai_service.get_client',return_value=MeteredClient(sdk)),patch('ai_service.get_model',return_value='fictional'):
            self.assertEqual(''.join(stream_response_text('Rules','Input')),'Hello')
        result=self.client.get('/api/access/platform-overview',headers=self.root).json()
        self.assertEqual(result['totals']['reported_tokens'],7)
        self.assertNotIn('Hello',json.dumps(access_control.load_access_data()['token_usage']))

if __name__=='__main__': unittest.main()
