import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from main import app
from platform_policy import settings, prune, run_retention
from request_limits import RequestLimits, month_key
from llm_rate_limits import LLMRateLimits


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/'access.json'
        self.env = self.root/'policy.env'
        self.path.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf8')
        self.patches = [patch.object(access_control, 'DATA_FILE', self.path),
                        patch.dict(os.environ, {'REWRITE_STORAGE_BACKEND':'local','PLATFORM_POLICY_ENV_FILE':str(self.env),
                                               'USER_LOG_RETENTION_DAYS':'180','LLM_RATE_ENV_FILE':str(self.root/'rate.env'),
                                               'LLM_RATE_DB':str(self.root/'rate.sqlite3')})]
        for item in self.patches: item.start(); self.addCleanup(item.stop)
        self.client = TestClient(app)
        self.admin = {'X-User-Email':'developer@eand.ae'}
        self.now = datetime.now(timezone.utc)

    def test_default_environment_and_saved_policy(self):
        self.assertEqual(settings()['retention_days'], 180)
        result = self.client.put('/api/access/platform-policy', headers=self.admin, json={'retention_days':365})
        self.assertEqual(result.status_code, 200, result.text)
        from dotenv import dotenv_values
        self.assertEqual(dotenv_values(self.env)['USER_LOG_RETENTION_DAYS'], '365')
        self.assertEqual(settings()['retention_days'], 365)
        for value in [0,30,3651,True,'180']:
            self.assertEqual(self.client.put('/api/access/platform-policy', headers=self.admin, json={'retention_days':value}).status_code, 422)

    def test_only_super_admin_can_read_change_or_clean_policy(self):
        for email in ['b2b.admin@eand.ae','b2b.user@eand.ae','b2b.approver1@eand.ae']:
            headers={'X-User-Email':email}
            for method,path,payload in [('get','',None),('put','',{'retention_days':365}),('post','/cleanup',{})]:
                result=getattr(self.client,method)('/api/access/platform-policy'+path,headers=headers,**({'json':payload} if payload is not None else {}))
                self.assertEqual(result.status_code,403,result.text)
        self.assertFalse(self.env.exists())

    def test_prune_boundary_and_stable_saved_content_are_preserved(self):
        cutoff=self.now-timedelta(days=180)
        old=(cutoff-timedelta(seconds=1)).isoformat()
        data=access_control.load_access_data()
        data.update(activity=[{'timestamp':old},{'timestamp':cutoff.isoformat()},{'timestamp':'unknown'}],
                    notifications=[{'created_at':old},{'created_at':self.now.isoformat()}],
                    approval_batches=[{'source':'Old source','generated':'Saved copy','events':[{'created_at':old,'note':'Keep legal approval evidence'}]}],
                    instruction_versions=[{'at':old,'content':'Never delete instructions'}],
                    feedback=[{'created_at':old,'reason':'Keep actionable feedback'}],
                    confidential_content={'b2b':{'digest':'protected'}},
                    token_usage={'channels':{'b2b':{'2020-01-01':{'total_tokens':20},self.now.date().isoformat():{'total_tokens':10}}}},
                    performance_metrics={'buckets':{'old':{'day':'2020-01-01'},'new':{'day':self.now.date().isoformat()}}})
        before=copy.deepcopy(data)
        result=prune(data,180,self.now)
        self.assertEqual(result['activity'],1);self.assertEqual(result['notifications'],1)
        self.assertEqual(result['token_days'],1);self.assertEqual(result['performance_buckets'],1)
        self.assertEqual(result['undated_records_preserved'],1)
        for key in ['users','channels','approval_batches','instruction_versions','feedback','confidential_content']:
            self.assertEqual(data[key],before[key],key)

    def test_cleanup_persists_and_protects_current_quota_and_live_requests(self):
        old=(self.now-timedelta(days=200)).isoformat()
        data=access_control.load_access_data(); data['activity']=[{'timestamp':old}];access_control.save_access_data(data)
        store=RequestLimits()
        with store.transaction() as db:
            for identity,month,state,expires in [('old','2020-01','completed',0),('current',month_key(),'completed',0),('live','2020-01','pending',self.now.timestamp()+3600)]:
                db.execute('INSERT INTO request_usage VALUES(?,?,?,?,?,?,?)',(identity,'b2b','local:test',month,state,expires,old))
        with LLMRateLimits().state() as rate:
            rate['changes']=[{'at':old,'actor':'obsolete@example.test'},{'at':self.now.isoformat(),'actor':'recent@example.test'}]
        result=run_retention(force=True,now=self.now)
        self.assertEqual(result['activity'],1);self.assertEqual(result['request_usage'],1);self.assertEqual(result['rate_setting_logs'],1)
        with store.transaction() as db:
            self.assertEqual({r[0] for r in db.execute('SELECT id FROM request_usage')},{'current','live'})
        self.assertEqual(access_control.load_access_data()['activity'],[])
        self.assertEqual(run_retention(now=self.now),result)

    def test_environment_is_restored_after_failed_persistence(self):
        self.env.write_text('USER_LOG_RETENTION_DAYS=180\n',encoding='utf8')
        with patch('access_control.save_access_data',side_effect=OSError('Fictional storage error')):
            with self.assertRaises(OSError):
                self.client.put('/api/access/platform-policy',headers=self.admin,json={'retention_days':365})
        self.assertEqual(settings()['retention_days'],180)

    def test_oracle_cleanup_uses_bound_timestamp_comparisons(self):
        from oracle_runtime import compile_statement
        sql,binds,_=compile_statement("DELETE FROM request_usage WHERE created_at<? AND month<>? AND (state<>'pending' OR expires<?)",
                                     [self.now.isoformat(),month_key(),self.now.timestamp()],'quota')
        self.assertIn('DELETE FROM genai_harf_request_usage',sql)
        self.assertEqual(sql.count('TO_TIMESTAMP_TZ'),2)
        self.assertEqual(len(binds),3)
        self.assertNotIn(self.now.isoformat(),sql)


if __name__=='__main__': unittest.main()
