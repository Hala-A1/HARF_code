import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import access_control
from channel_instruction_clone import MODULES,cx_comms_copy
from copywriter import output_catalog
from main import app


class CXCommsPackTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'access.json'
        data=copy.deepcopy(access_control.DEFAULT_DATA)
        data['channels'].append({'id':'cx-comms','name':'CX Comms','instruction_modules':['CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES']})
        for role in ['user','channel_admin']:
            data['users'].append({'email':role+'@cx.example.test','name':'CX account','role':role,'channel_id':'cx-comms','workspaces':['rewrite']})
        self.path.write_text(json.dumps(data),encoding='utf8')
        p=patch.object(access_control,'DATA_FILE',self.path);p.start();self.addCleanup(p.stop)
        self.client=TestClient(app)

    def test_rename_preserves_all_rules_examples_and_valid_identifiers(self):
        original='# B2C\n01_B2C_SYSTEM_INSTRUCTIONS.md\nB2C-SMS-001\n<a id="b2c-admin-only"></a>\n/admin/b2c\nKeep 140 characters, AED 100 and the URL https://example.test.\nنفس التفاصيل العربية\nDuplicate term: new rule\nDuplicate term: different rule'
        result=cx_comms_copy(original)
        self.assertIn('CX Comms',result);self.assertIn('CX-COMMS-SMS-001',result)
        self.assertIn('01_CX_COMMS_SYSTEM_INSTRUCTIONS.md',result)
        self.assertIn('cx-comms-admin-only',result);self.assertIn('/admin/cx-comms',result)
        self.assertEqual(result.splitlines()[-4:],original.splitlines()[-4:])
        self.assertNotIn('B2C',result)

    def test_cx_pack_has_independent_paths_and_the_five_indexed_format_parents(self):
        for source,target in MODULES.items():
            source_path=access_control.CHANNEL_PROMPT_DIR/'b2c'/access_control.INSTRUCTION_MODULES[source]['filename']
            target_path=access_control.CHANNEL_PROMPT_DIR/'cx-comms'/access_control.INSTRUCTION_MODULES[target]['filename']
            self.assertNotEqual(target_path.resolve(),source_path.resolve())
            self.assertTrue(target_path.is_file())
            # Exact copy preservation is checked by the one-time copy audit.
            # Later authorised edits in either channel must stay independent.
        self.assertEqual(access_control.used_instruction_ids('cx-comms'),list(MODULES.values()))
        options=output_catalog('cx-comms')
        self.assertGreaterEqual(len(options),5)
        self.assertTrue({'cx-comms-sms-001','cx-comms-email-001','cx-comms-web-001','cx-comms-app-001','cx-comms-push-001'} <= {row['id'] for row in options})
        self.assertTrue(all(row['id'].startswith('cx-comms-') for row in options))

    def test_indexed_retrieval_and_prompt_use_only_cx_files(self):
        bundle=access_control.instruction_bundle('cx-comms','SMS','CX-COMMS-SMS-001 renewal')
        self.assertEqual({row['module'] for row in bundle['files']},{'CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES'})
        self.assertIn('CX-COMMS-SMS-001',bundle['text'])
        self.assertNotIn('B2C-',bundle['text'])
        self.assertNotIn('## CX-COMMS-EMAIL-001',bundle['text'])
        import ai_service
        prompt=ai_service.build_task_prompt('Renewal facts',channel='SMS',team_channel='cx-comms')
        self.assertIn('matching indexed CX Comms template',prompt)
        self.assertNotIn('B2C-',prompt)
        self.assertEqual(ai_service.detect_website_component('Component 1','cx-comms'),None)

    def test_channel_boundaries_and_user_admin_guide_remain_private(self):
        base='/api/access/channels/cx-comms/instructions'
        for email in ['b2c.admin@eand.ae','b2c.user@eand.ae']:
            self.assertEqual(self.client.get(base,headers={'X-User-Email':email}).status_code,403)
        user={'X-User-Email':'user@cx.example.test'}
        listed=self.client.get(base,headers=user).json()['instructions']
        self.assertEqual([row['id'] for row in listed],['CX_COMMS_USER_GUIDE'])
        guide=self.client.get(base+'/CX_COMMS_USER_GUIDE',headers=user).json()['content']
        self.assertNotIn('cx-comms-admin-only',guide)
        self.assertEqual(self.client.get(base+'/CX_COMMS_SYSTEM',headers=user).status_code,403)


if __name__=='__main__':unittest.main()
