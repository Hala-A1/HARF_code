import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import access_control
from main import app
from request_limits import RequestLimits, principal


class UserRemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'access-control.json'
        self.path.write_text(json.dumps(copy.deepcopy(access_control.DEFAULT_DATA)), encoding='utf8')
        patcher = patch.object(access_control, 'DATA_FILE', self.path)
        patcher.start(); self.addCleanup(patcher.stop)
        self.client = TestClient(app)

    def remove(self, email='mariam.k@eand.ae', actor='b2b.admin@eand.ae', channel='b2b'):
        return self.client.delete(f'/api/access/channels/{channel}/users/{email}', headers={'X-User-Email': actor})

    def test_remove_revokes_existing_session_and_login_and_preserves_history(self):
        data = access_control.load_access_data()
        data['approval_batches'] = [{'id':'retained', 'created_by_email':'mariam.k@eand.ae', 'channel_id':'b2b', 'status':'approved'}]
        access_control.save_access_data(data)
        result = self.remove()
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/access/me',headers={'X-User-Email':'mariam.k@eand.ae'}).status_code,401)
        self.assertEqual(self.client.post('/api/access/login',json={'email':'mariam.k@eand.ae','password':'111111'}).status_code,403)
        data = access_control.load_access_data()
        self.assertEqual(data['approval_batches'][0]['id'],'retained')
        self.assertEqual(data['activity'][0]['action'],'User removed')
        member = next(row for row in data['users'] if row['email']=='mariam.k@eand.ae')
        self.assertFalse(member['active']); self.assertEqual(member['removed_by'],'b2b.admin@eand.ae')

    def test_channel_admin_can_remove_reviewer(self):
        self.assertEqual(self.remove('b2b.approver1@eand.ae').status_code,200)
        self.assertEqual(self.client.get('/api/access/me',headers={'X-User-Email':'b2b.approver1@eand.ae'}).status_code,401)

    def test_permission_boundaries_and_self_protection(self):
        self.assertEqual(self.remove(channel='b2c',email='b2c.user@eand.ae').status_code,403)
        self.assertEqual(self.remove(email='b2c.user@eand.ae').status_code,404)
        self.assertEqual(self.remove(actor='mariam.k@eand.ae').status_code,403)
        self.assertEqual(self.remove(actor='b2b.approver1@eand.ae').status_code,403)
        self.assertEqual(self.remove(email='b2b.admin@eand.ae').status_code,422)
        self.assertEqual(self.remove(email='unknown@example.test').status_code,404)
        data = access_control.load_access_data()
        data['users'].append({'email':'second.admin@example.test','name':'Other admin','role':'channel_admin','channel_id':'b2b','active':True})
        access_control.save_access_data(data)
        self.assertEqual(self.remove(email='second.admin@example.test').status_code,403)
        self.assertTrue(next(row for row in access_control.load_access_data()['users'] if row['email']=='second.admin@example.test')['active'])

    def test_super_admin_can_remove_channel_admin(self):
        self.assertEqual(self.remove(email='b2b.admin@eand.ae',actor='developer@eand.ae').status_code,200)

    def test_remove_is_idempotent_and_assignment_can_restore_access(self):
        self.assertEqual(self.remove().status_code,200)
        self.assertEqual(self.remove().status_code,200)
        self.assertEqual(sum(row['action']=='User removed' for row in access_control.load_access_data()['activity']),1)
        response=self.client.put('/api/access/assignments',headers={'X-User-Email':'b2b.admin@eand.ae'},json={'email':'mariam.k@eand.ae','name':'Mariam','role':'user','channel_id':'b2b','workspaces':['rewrite']})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/access/me',headers={'X-User-Email':'mariam.k@eand.ae'}).status_code,200)
        self.assertNotIn('removed_by',access_control.get_user('mariam.k@eand.ae'))

    def test_removal_releases_allocation_without_erasing_usage(self):
        user=access_control.get_user('mariam.k@eand.ae')
        limits=RequestLimits()
        with limits.transaction() as db:
            db.execute('INSERT INTO user_limits(channel,principal,monthly_limit) VALUES(?,?,?)',('b2b',principal(user),20))
            db.execute('INSERT INTO request_usage VALUES(?,?,?,?,?,?,?)',('historical','b2b',principal(user),'2026-10','completed',0,'2026-10-01'))
        self.assertEqual(self.remove().status_code,200)
        with limits.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_limits WHERE principal=?',(principal(user),)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM request_usage WHERE principal=?',(principal(user),)).fetchone()[0],1)

if __name__ == '__main__': unittest.main()
