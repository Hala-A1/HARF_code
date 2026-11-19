import copy
import json
from unittest.mock import patch
import unittest

import access_control
from inference import policy, bootstrap, inference_scope, resolve
import test_inference


class ModelCatalogSyncTests(unittest.TestCase):
    def setUp(self):
        test_inference.InferenceTests.setUp(self)

    def headers(self):
        return {'X-User-Email':'developer@eand.ae'}

    def test_new_configuration_models_appear_without_erasing_saved_admin_changes(self):
        first=policy()
        payload={key:copy.deepcopy(first[key]) for key in ['models','default_model','confidential_model','channels']}
        payload['models'][0]['name']='Admin display name'
        payload['models'][0]['max_tokens']=8000
        payload['expected_revision']=first['revision']
        saved=self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload)
        self.assertEqual(saved.status_code,200,saved.text)
        with patch.dict('os.environ',{'AZURE_EXPLICIT_DEPLOYMENTS':'["cloud-text","cloud-new"]','DEFAULT_MAX_TOKENS':'6000'}):
            current=policy()
            old=next(row for row in current['models'] if row['id']=='cloud:cloud-text')
            self.assertEqual(old['name'],'Admin display name')
            self.assertEqual(old['max_tokens'],8000)
            new=next(row for row in current['models'] if row['id']=='cloud:cloud-new')
            self.assertEqual(new['max_tokens'],6000)
            self.assertGreater(current['revision'],saved.json()['revision'])
            self.assertEqual(policy()['revision'],current['revision'])

    def test_configuration_output_changes_apply_to_unmodified_models_and_next_route(self):
        previous=policy()
        with patch.dict('os.environ',{'DEFAULT_MAX_TOKENS':'5000'}):
            current=policy()
            self.assertGreater(current['revision'],previous['revision'])
            with inference_scope({'channel':'b2b'}):
                self.assertEqual(resolve()['max_tokens'],5000)

    def test_app_added_models_and_default_selection_survive_config_sync(self):
        first=policy()
        payload={key:copy.deepcopy(first[key]) for key in ['models','default_model','confidential_model','channels']}
        added={**payload['models'][1],'id':'admin-local','name':'Admin local model','upstream':'local-b','max_tokens':7000}
        payload['models'].append(added)
        payload.update(default_model='admin-local',expected_revision=first['revision'])
        saved=self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload)
        self.assertEqual(saved.status_code,200,saved.text)
        with inference_scope({'channel':'b2b'}):
            self.assertEqual(resolve()['upstream'],'local-b')
            self.assertEqual(resolve()['max_tokens'],7000)
        with patch.dict('os.environ',{'DEFAULT_MAX_TOKENS':'6000'}):
            current=policy()
            self.assertEqual(current['default_model'],'admin-local')
            self.assertIn(added,current['models'])

    def test_live_config_file_edits_sync_and_stale_admin_saves_are_rejected(self):
        file=self.path.parent/'catalog.env'
        file.write_text('AZURE_EXPLICIT_DEPLOYMENTS=["cloud-text"]\nON_PREM_EXPLICIT_MODELS=["local-a","local-b"]\nDEFAULT_MAX_TOKENS=4096\n',encoding='utf8')
        with patch.dict('os.environ',{'INFERENCE_CATALOG_ENV_FILE':str(file)}):
            first=policy()
            file.write_text('AZURE_EXPLICIT_DEPLOYMENTS=["cloud-text","cloud-next"]\nON_PREM_EXPLICIT_MODELS=["local-a","local-b"]\nDEFAULT_MAX_TOKENS=9000\n',encoding='utf8')
            self.assertIn('cloud:cloud-next',[row['id'] for row in policy()['models']])
            self.assertEqual(bootstrap()['models'][0]['max_tokens'],9000)
            payload={key:first[key] for key in ['models','default_model','confidential_model','channels']}
            payload['expected_revision']=first['revision']
            self.assertEqual(self.client.put('/api/access/inference/policy',headers=self.headers(),json=payload).status_code,409)
            self.assertNotIn('fictional-cloud-key',json.dumps(policy()))

    def test_removing_selected_config_model_blocks_instead_of_switching_gateway(self):
        policy()
        with patch.dict('os.environ',{'AZURE_EXPLICIT_DEPLOYMENTS':'["replacement"]'}):
            current=policy()
            self.assertFalse(next(row for row in current['models'] if row['id']=='cloud:cloud-text')['enabled'])
            from inference import InferencePolicyError
            with inference_scope({'channel':'b2b'}),self.assertRaises(InferencePolicyError):resolve()


if __name__=='__main__':unittest.main()
