import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from fastapi import HTTPException
from fastapi.testclient import TestClient
import access_control as access
import directory_auth as directory
import directory_provisioning as provisioning
from main import app


class DirectoryUsernameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'access.json'
        self.path.write_text(json.dumps(access.DEFAULT_DATA), encoding='utf-8')
        p = patch.object(access, 'DATA_FILE', self.path); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'REWRITE_STORAGE_BACKEND':'local','LDAP_SUPER_ADMIN_USERNAMES':'bmahrouseh,selkhiat,mohmay,haamir'}); p.start(); self.addCleanup(p.stop)
        self.person = dict(username='selkhiat', name='Corporate Administrator', email='corporate.admin@example.test', directory_id='ldap:verified-guid')
        self.client = TestClient(app)

    def test_username_login_resolves_real_email_and_allowlisted_admin_after_ldap_bind(self):
        with patch('directory_auth.enabled', return_value=True), \
                patch('directory_auth.authenticate', return_value=directory.DirectoryIdentity(self.person['directory_id'], self.person)) as bind, \
                patch('directory_auth.issue_token', return_value='signed-test-session'), patch('admin.RequestLimits'):
            response = self.client.post('/api/access/login', json={'username':'selkhiat','password':'fictional-directory-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], self.person['email'])
        self.assertEqual(response.json()['role'], 'super_admin')
        bind.assert_called_once_with('selkhiat','fictional-directory-password')
        saved = access.get_user(self.person['email'])
        self.assertNotIn('password_hash', saved)

    def test_failed_directory_bind_never_provisions_privileged_account(self):
        with patch('directory_auth.enabled', return_value=True), patch('directory_auth.authenticate', side_effect=HTTPException(401,'Invalid credentials')):
            response = self.client.post('/api/access/login', json={'username':'selkhiat','password':'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertIsNone(access.get_user(self.person['email']))

    def test_regular_directory_user_does_not_gain_access_or_admin_role(self):
        person = {**self.person, 'username':'other.employee'}
        with patch('directory_auth.enabled', return_value=True), patch('directory_auth.authenticate', return_value=directory.DirectoryIdentity(person['directory_id'],person)):
            response = self.client.post('/api/access/login', json={'username':'other.employee','password':'fictional'})
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(access.get_user(person['email']))

    def test_search_requires_admin_and_channel_access(self):
        with patch('directory_auth.enabled', return_value=False), patch('directory_auth.search_users', return_value=[self.person]) as search:
            self.assertEqual(self.client.get('/api/access/directory/users?query=sel&channel_id=b2b').status_code,401)
            self.assertEqual(self.client.get('/api/access/directory/users?query=sel&channel_id=b2b',headers={'X-User-Email':'b2b.user@eand.ae'}).status_code,403)
            self.assertEqual(self.client.get('/api/access/directory/users?query=sel&channel_id=b2c',headers={'X-User-Email':'b2b.admin@eand.ae'}).status_code,403)
            response = self.client.get('/api/access/directory/users?query=sel&channel_id=b2b',headers={'X-User-Email':'b2b.admin@eand.ae'})
            self.assertEqual(response.json()['users'], [self.person])
            search.assert_called_once_with('sel')

    def test_assignment_resolves_again_and_does_not_trust_client_email_or_name(self):
        from admin import assign_user, AssignmentRequest
        admin = access.get_user('developer@eand.ae')
        with patch('directory_auth.enabled', return_value=True), patch('directory_auth.find_user', return_value=self.person) as lookup:
            result = assign_user(AssignmentRequest(username='selkhiat', email='forged@example.test', name='Forged name',role='approval_admin',approval_layer=2,review_languages=['ar'],channel_id='b2b'),admin)
        lookup.assert_called_once_with('selkhiat')
        self.assertEqual(result['email'],self.person['email'])
        saved=access.get_user(self.person['email'])
        self.assertEqual(saved['name'],self.person['name'])
        self.assertEqual(saved['directory_id'],self.person['directory_id'])
        self.assertEqual(saved['review_languages'],['ar'])
        self.assertNotIn('password_hash',saved)
        self.assertIsNone(access.get_user('forged@example.test'))

    def test_demo_cleanup_preserves_real_people_copies_and_developer_backup(self):
        data = access.load_access_data()
        data['users'].append({**self.person,'role':'user','auth_source':'ldap'})
        data['approval_batches']=[{'id':'historic-copy','created_by_email':'mariam.k@eand.ae'}]
        provisioning.update_records(data)
        self.assertFalse(any(provisioning.is_demo_account(u) for u in data['users']))
        self.assertTrue(any(u['email']==self.person['email'] for u in data['users']))
        self.assertEqual(data['approval_batches'][0]['id'],'historic-copy')
        self.assertEqual(next(u for u in data['users'] if u['email']=='developer@eand.ae')['auth_source'],'developer_backup')
        self.assertEqual(sum(c['id']=='cx-comms' for c in data['channels']),1)
        self.assertFalse(provisioning.update_records(data))

    def test_directory_search_is_bounded_and_filter_input_escaped(self):
        connection=MagicMock()
        connection.result={'result':0}
        connection.entries=[SimpleNamespace(entry_attributes_as_dict={'sAMAccountName':['selkhiat'],'displayName':['Corporate Administrator'],'mail':[self.person['email']],'objectGUID':[b'\x01\x02']})]
        @contextmanager
        def connected(): yield connection
        with patch('directory_auth.directory_search_connection', connected):
            found=directory.search_users('se*)(mail=*)')
        query=connection.search.call_args.args[1]
        self.assertIn('se\\2a\\29\\28mail=\\2a\\29*',query)
        self.assertEqual(connection.search.call_args.kwargs['size_limit'],10)
        self.assertEqual(found[0]['name'],'Corporate Administrator')
        self.assertEqual(found[0]['directory_id'],'ldap:0102')

    def test_environment_list_never_accepts_wildcards(self):
        with patch.dict(os.environ, {'LDAP_SUPER_ADMIN_USERNAMES':'*'}):
            with self.assertRaises(ValueError): provisioning.super_admin_usernames()

    def test_removed_managed_admin_is_deactivated_on_deployment(self):
        data={'channels':[],'users':[{**self.person,'role':'super_admin','environment_managed_admin':True}]}
        with patch.dict(os.environ,{'LDAP_SUPER_ADMIN_USERNAMES':'bmahrouseh'}): provisioning.update_records(data)
        self.assertFalse(data['users'][0]['active'])

    def test_developer_email_keeps_its_existing_local_password(self):
        data=access.load_access_data()
        developer=next(u for u in data['users'] if u['email']=='developer@eand.ae')
        developer['password_hash']=access.password_hash('existing-local-password')
        provisioning.update_records(data)
        access.save_access_data(data)
        with patch.dict(os.environ, {'DEVELOPER_MODE':'true'}), patch('directory_auth.authenticate') as ldap:
            response=self.client.post('/api/access/login',json={'username':'developer@eand.ae','password':'existing-local-password'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['email'],'developer@eand.ae')
            self.assertEqual(response.json()['auth_type'],'local')
            self.assertEqual(self.client.post('/api/access/login',json={'username':'developer@eand.ae','password':'wrong'}).status_code,403)
            ldap.assert_not_called()

    def test_access_request_endpoints_are_removed_and_records_cleared(self):
        for method, path in [('GET','/api/access/request-options'),('GET','/api/access/access-requests'),
                             ('POST','/api/access/access-requests'),('POST','/api/access/access-requests/old/review')]:
            self.assertEqual(self.client.request(method,path,json={}).status_code,404)
        data={'channels':[],'users':[],'access_requests':[{'email':'old@example.test','status':'pending'}],
              'activity':[{'action':'Access request reviewed'},{'action':'Instruction edited'}]}
        provisioning.update_records(data)
        self.assertNotIn('access_requests',data)
        self.assertEqual(data['activity'],[{'action':'Instruction edited'}])

    def test_deployment_resolves_all_four_admins_before_any_write(self):
        original=self.path.read_bytes()
        with patch('directory_auth.enabled',return_value=True), \
                patch('directory_auth.find_user',side_effect=HTTPException(503,'Directory unavailable')):
            with self.assertRaises(HTTPException): provisioning.apply_deployment_updates()
        self.assertEqual(self.path.read_bytes(),original)


if __name__=='__main__': unittest.main()
