"""Cross-channel final-layer, language, stale-round and concurrent-decision regression."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from main import app

CHANNELS=['b2b','b2c','security','cx-comms']


class ApprovalScenarioTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'access.json'
        data=copy.deepcopy(access_control.DEFAULT_DATA)
        data['channels'].append({'id':'cx-comms','name':'CX Comms','instruction_modules':[]})
        for channel in CHANNELS:
            for key,role,layer,languages in [('author','user',None,['en','ar']),('admin','channel_admin',None,['en','ar'])]+[(f'r{layer}{kind}','approval_admin',layer,languages) for layer in [1,2,3] for kind,languages in [('a',['en','ar']),('b',['en','ar']),('en',['en']),('ar',['ar'])]]:
                data['users'].append({'email':f'{key}@{channel}.example.test','name':key,'role':role,'channel_id':channel,'approval_layer':layer,'review_languages':languages,'workspaces':['rewrite']})
        self.path.write_text(json.dumps(data),encoding='utf8')
        p=patch.object(access_control,'DATA_FILE',self.path);p.start();self.addCleanup(p.stop)
        self.client=TestClient(app)

    def headers(self,channel,key):return {'X-User-Email':f'{key}@{channel}.example.test'}
    def policy(self,channel,last):
        result=self.client.put(f'/api/access/channels/{channel}/approval-policy',headers=self.headers(channel,'admin'),json={'final_approval_layer':last})
        self.assertEqual(result.status_code,200,result.text)
    def start(self,channel,last=3,languages=('en',)):
        self.policy(channel,last)
        result=self.client.post('/api/approvals/draft',headers=self.headers(channel,'author'),json={'team_channel':channel,'source':'Verified facts','english':'English copy' if 'en' in languages else '', 'arabic':'نسخة عربية' if 'ar' in languages else ''})
        self.assertEqual(result.status_code,200,result.text)
        return self.move(channel,result.json()['id'])
    def move(self,channel,identity):
        result=self.client.post(f'/api/approvals/{identity}/move',headers=self.headers(channel,'author'),json={})
        self.assertEqual(result.status_code,200,result.text);return result.json()
    def decision(self,channel,batch,key,action='approve',**extra):
        return self.client.post(f"/api/approvals/{batch['id']}/decision",headers=self.headers(channel,key),json={'action':action,'expected_layer':batch['current_layer'],'expected_round':batch['approval_round'],**extra})
    def get(self,channel,batch):return self.client.get(f"/api/approvals/{batch['id']}",headers=self.headers(channel,'admin')).json()
    def race(self,functions):
        barrier=Barrier(len(functions))
        def call(function):barrier.wait(timeout=10);return function()
        with ThreadPoolExecutor(len(functions)) as pool:return list(pool.map(call,functions))

    def test_all_channels_final_layers_and_requested_languages(self):
        for channel in CHANNELS:
            for last in [1,2,3]:
                for languages in [('en',),('ar',),('en','ar')]:
                    with self.subTest(channel=channel,last=last,languages=languages):
                        batch=self.start(channel,last,languages)
                        for layer in range(1,last+1):
                            result=self.decision(channel,batch,f'r{layer}a')
                            self.assertEqual(result.status_code,200,result.text);batch=result.json()
                            self.assertEqual(batch['status'],'approved' if layer==last else f'pending_layer_{layer+1}')
                        self.assertEqual(batch['progress'],100);self.assertTrue(batch['completed_at'])
                        self.assertEqual(sum(e['action']=='final_approved' for e in batch['events']),1)

    def test_simultaneous_same_language_reviewers_advance_exactly_once_at_each_layer(self):
        for channel in CHANNELS:
            batch=self.start(channel)
            for layer in [1,2,3]:
                responses=self.race([lambda:self.decision(channel,batch,f'r{layer}a'),lambda:self.decision(channel,batch,f'r{layer}b')])
                self.assertEqual(sorted(r.status_code for r in responses),[200,409])
                batch=self.get(channel,batch)
                self.assertEqual(len(batch['language_approvals'][str(layer)]),1)
                self.assertEqual(batch['current_layer'],min(layer+1,3))
            self.assertEqual(batch['status'],'approved')
            self.assertEqual(sum(e['action']=='final_approved' for e in batch['events']),1)

    def test_parallel_arabic_and_english_approvals_both_count_without_lost_updates(self):
        for channel in CHANNELS:
            batch=self.start(channel,2,('en','ar'))
            for layer in [1,2]:
                responses=self.race([lambda:self.decision(channel,batch,f'r{layer}en',language='en'),lambda:self.decision(channel,batch,f'r{layer}ar',language='ar')])
                self.assertEqual([r.status_code for r in responses],[200,200])
                batch=self.get(channel,batch)
                self.assertEqual(set(batch['language_approvals'][str(layer)]),{'en','ar'})
            self.assertEqual(batch['status'],'approved')

    def test_bilingual_layers_wait_for_both_languages_in_either_order(self):
        for channel in CHANNELS:
            for last in [1,2,3]:
                for order in [('en','ar'),('ar','en')]:
                    with self.subTest(channel=channel,last=last,order=order):
                        batch=self.start(channel,last,('en','ar'))
                        for layer in range(1,last+1):
                            first,second=order
                            partial=self.decision(channel,batch,f'r{layer}{first}',language=first)
                            self.assertEqual(partial.status_code,200,partial.text)
                            pending=partial.json()
                            self.assertEqual(pending['status'],f'pending_layer_{layer}')
                            self.assertEqual(pending['current_layer'],layer)
                            self.assertIsNone(pending['completed_at'])
                            self.assertLess(pending['progress'],100)
                            self.assertEqual(set(pending['language_approvals'][str(layer)]),{first})
                            self.assertEqual(self.decision(channel,pending,f'r{layer}{first}',language=first).status_code,409)
                            if layer < last:
                                self.assertEqual(self.decision(channel,pending,f'r{layer+1}{second}',language=second).status_code,403)
                            result=self.decision(channel,pending,f'r{layer}{second}',language=second)
                            self.assertEqual(result.status_code,200,result.text)
                            batch=result.json()
                            self.assertEqual(set(batch['language_approvals'][str(layer)]),{'en','ar'})
                            self.assertEqual(batch['status'],'approved' if layer==last else f'pending_layer_{layer+1}')
                        notifications=self.client.get('/api/notifications',headers=self.headers(channel,'author')).json()['notifications']
                        self.assertEqual(sum(n['batch_id']==batch['id'] and n['kind']=='final_approval' for n in notifications),1)

    def test_return_after_partial_language_approval_requires_fresh_reviews(self):
        for channel in CHANNELS:
            for first,second in [('en','ar'),('ar','en')]:
                for action in ['return_to_user','reject']:
                    with self.subTest(channel=channel,first=first,action=action):
                        original=self.start(channel,1,('en','ar'))
                        pending=self.decision(channel,original,f'r1{first}',language=first).json()
                        returned=self.decision(channel,pending,f'r1{second}',action,note='Correct the supplied facts',language=second)
                        self.assertEqual(returned.status_code,200,returned.text)
                        renewed=self.move(channel,original['id'])
                        self.assertEqual(renewed['language_approvals'],{})
                        self.assertNotEqual(renewed['approval_round'],original['approval_round'])
                        self.assertEqual(self.decision(channel,original,f'r1{second}',language=second).status_code,409)
                        pending=self.decision(channel,renewed,f'r1{second}',language=second).json()
                        self.assertEqual(pending['status'],'pending_layer_1')
                        self.assertEqual(self.decision(channel,pending,f'r1{first}',language=first).json()['status'],'approved')

    def test_duplicate_bilingual_final_approvals_are_idempotent(self):
        for channel in CHANNELS:
            batch=self.start(channel,1,('en','ar'))
            responses=self.race([lambda:self.decision(channel,batch,'r1a'),lambda:self.decision(channel,batch,'r1b')])
            self.assertEqual(sorted(r.status_code for r in responses),[200,409])
            current=self.get(channel,batch)
            self.assertEqual(current['status'],'approved')
            self.assertEqual(set(current['language_approvals']['1']),{'en','ar'})
            self.assertEqual(len({row['actor_email'] for row in current['language_approvals']['1'].values()}),1)
            self.assertEqual(sum(e['action']=='final_approved' for e in current['events']),1)
            notifications=self.client.get('/api/notifications',headers=self.headers(channel,'author')).json()['notifications']
            self.assertEqual(sum(row['batch_id']==batch['id'] and row['kind']=='final_approval' for row in notifications),1)

    def test_duplicate_resubmissions_start_the_next_round_only_once(self):
        for channel in CHANNELS:
            batch=self.start(channel,2)
            self.assertEqual(self.decision(channel,batch,'r1a','return_to_user',note='Correct the source').status_code,200)
            def submit():return self.client.post(f"/api/approvals/{batch['id']}/move",headers=self.headers(channel,'author'),json={})
            responses=self.race([submit,submit])
            self.assertEqual(sorted(row.status_code for row in responses),[200,409])
            current=self.get(channel,batch)
            self.assertEqual(current['status'],'pending_layer_1')
            self.assertNotEqual(current['approval_round'],batch['approval_round'])
            self.assertEqual(sum(event['action']=='submitted' for event in current['events']),2)

    def test_route_setting_change_racing_with_approval_preserves_both_updates(self):
        for channel in CHANNELS:
            batch=self.start(channel,3)
            responses=self.race([lambda:self.decision(channel,batch,'r1a'),lambda:self.client.put(f'/api/access/channels/{channel}/approval-policy',headers=self.headers(channel,'admin'),json={'final_approval_layer':1})])
            self.assertEqual([row.status_code for row in responses],[200,200])
            current=self.get(channel,batch)
            self.assertEqual(current['final_approval_layer'],3)
            self.assertEqual(current['status'],'pending_layer_2')
            channel_row=next(row for row in access_control.load_access_data()['channels'] if row['id']==channel)
            self.assertEqual(channel_row['final_approval_layer'],1)

    def test_final_layer_setting_changes_preserve_pending_route_and_apply_on_resubmit(self):
        for channel in CHANNELS:
            for old,new in [(3,1),(1,3),(3,2),(2,3)]:
                batch=self.start(channel,old)
                self.policy(channel,new)
                self.assertEqual(self.get(channel,batch)['final_approval_layer'],old)
                returned=self.decision(channel,batch,'r1a','return_to_user',note='Revise supplied details')
                self.assertEqual(returned.status_code,200,returned.text)
                moved=self.move(channel,batch['id'])
                self.assertEqual(moved['final_approval_layer'],new)
                self.assertNotEqual(moved['approval_round'],batch['approval_round'])
                self.assertEqual(moved['language_approvals'],{})

    def test_old_round_cannot_approve_after_return_to_layer_one_or_resubmit(self):
        for channel in CHANNELS:
            original=self.start(channel)
            batch=self.decision(channel,original,'r1a').json()
            result=self.decision(channel,batch,'r2a','return_to_layer_1',note='Check updated facts')
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(self.decision(channel,original,'r1a').status_code,409)
            batch=result.json()
            self.assertEqual(self.decision(channel,batch,'r1a').status_code,200)

    def test_rejection_and_return_races_never_skip_layers_or_apply_two_transitions(self):
        for channel in CHANNELS:
            for action in ['reject','return_to_user']:
                batch=self.start(channel)
                results=self.race([lambda:self.decision(channel,batch,'r1a'),lambda:self.decision(channel,batch,'r1b',action,note='Check source')])
                self.assertEqual(sorted(r.status_code for r in results),[200,409])
                current=self.get(channel,batch)
                self.assertIn(current['status'],['pending_layer_2','rejected','returned_to_user'])
                self.assertEqual(len([e for e in current['events'] if e['action'] in {'approved','rejected','returned_to_user'}]),1)

    def test_notes_permissions_wrong_language_and_terminal_states(self):
        for channel in CHANNELS:
            batch=self.start(channel,1,('en','ar'))
            for action in ['reject','return_to_user','note']:
                self.assertEqual(self.decision(channel,batch,'r1a',action,note='  ').status_code,422)
            self.assertEqual(self.decision(channel,batch,'r1en',language='ar').status_code,403)
            self.assertEqual(self.decision(channel,batch,'author').status_code,403)
            self.assertEqual(self.decision(channel,batch,'r2a').status_code,403)
            self.assertEqual(self.decision(channel,batch,'r1a','note',note='Reviewed source').json()['status'],'pending_layer_1')
            rejected=self.decision(channel,batch,'r1a','reject',note='Missing verified information')
            self.assertEqual(rejected.json()['status'],'rejected')
            self.assertEqual(self.decision(channel,batch,'r1b').status_code,409)
            renewed=self.move(channel,batch['id'])
            self.assertEqual(self.decision(channel,renewed,'r1a').json()['status'],'approved')
            self.assertEqual(self.decision(channel,renewed,'r1b').status_code,409)


if __name__=='__main__':unittest.main()
