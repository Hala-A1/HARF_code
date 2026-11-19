import os
import ssl
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
import directory_auth as auth


class DirectoryAuthTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'REWRITE_STORAGE_BACKEND': 'local', 'AUTH_PROVIDER': 'ldap',
            'DEVELOPER_MODE': 'false', 'JWT_SECRET': 'fictional-test-secret-' * 3,
            'JWT_EXPIRY_HOURS': '8', 'LDAP_SERVER': 'directory.example.test',
            'LDAP_PORT': '636', 'LDAP_USE_SSL': 'true',
            'LDAP_BASE_DN': 'DC=example,DC=test',
            'LDAP_USER_SEARCH_BASE': 'OU=People,DC=example,DC=test',
            'LDAP_BIND_DN': 'EXAMPLE\\service', 'LDAP_BIND_PASSWORD': 'fictional-service-password',
            'LDAP_USER_SEARCH_FILTER': '(&(sAMAccountName={})(objectclass=person))',
            'LDAP_RECEIVE_TIMEOUT_SECONDS': '10', 'LDAP_PREFER_UPN_BIND': 'true',
        }, clear=True)
        self.environment.start()
        self.search, self.login = MagicMock(), MagicMock()
        self.search.entries = [SimpleNamespace(entry_dn='CN=Person,DC=example,DC=test',
            entry_attributes_as_dict={'objectGUID': [b'\x01\x02'], 'userPrincipalName': ['person@example.test']})]
        self.login.bind.return_value = True

    def tearDown(self):
        self.environment.stop()

    def authenticate(self, email='person@example.test'):
        with patch('ldap3.Server') as server, patch('ldap3.Tls') as tls, \
                patch('ldap3.Connection', side_effect=[self.search, self.login]) as connection:
            identity = auth.authenticate(email, 'fictional-user-password')
            return identity, server, tls, connection

    def test_developer_switch_selects_local_and_accepts_case_insensitive_boolean(self):
        self.assertTrue(auth.enabled())
        with patch.dict(os.environ, {'DEVELOPER_MODE': 'True'}):
            self.assertFalse(auth.enabled())
            self.assertTrue(auth.status()['developer_mode'])
            self.assertEqual(auth.status()['mode'], 'local')

    def test_invalid_switch_does_not_silently_enable_local_access(self):
        with patch.dict(os.environ, {'DEVELOPER_MODE': 'maybe'}):
            with self.assertRaises(HTTPException) as failure: auth.enabled()
            self.assertEqual(failure.exception.status_code, 503)

    def test_legacy_mode_and_secret_remain_supported(self):
        with patch.dict(os.environ, {'AUTH_PROVIDER': '', 'AUTH_MODE': 'local'}): self.assertFalse(auth.enabled())
        with patch.dict(os.environ, {'JWT_SECRET': '', 'LDAP_SESSION_SECRET': 'legacy-test-secret-' * 3}):
            self.assertTrue(auth.status()['configured'])
            token = auth.issue_token({'email': 'person@example.test', 'directory_id': 'ldap:stable'})
            self.assertEqual(auth.verify_token(token)['directory_id'], 'ldap:stable')

    def test_new_provider_takes_precedence_over_legacy_mode(self):
        with patch.dict(os.environ, {'AUTH_MODE': 'local'}):
            self.assertTrue(auth.enabled())

    def test_missing_or_masked_password_is_unconfigured_without_network_calls(self):
        for password in ['', '****************']:
            with patch.dict(os.environ, {'LDAP_BIND_PASSWORD': password}), patch('ldap3.Connection') as connection:
                self.assertFalse(auth.status()['configured'])
                with self.assertRaises(HTTPException) as failure: auth.authenticate('person@example.test', 'password')
                self.assertEqual(failure.exception.status_code, 503)
                connection.assert_not_called()

    def test_provided_settings_control_search_ssl_timeout_and_upn(self):
        identity, server, tls, connection = self.authenticate()
        self.assertEqual(identity, 'ldap:0102')
        self.assertEqual(server.call_args.args[0], 'directory.example.test')
        self.assertEqual(server.call_args.kwargs['port'], 636)
        self.assertTrue(server.call_args.kwargs['use_ssl'])
        self.assertEqual(tls.call_args.kwargs['validate'], ssl.CERT_REQUIRED)
        self.assertEqual(connection.call_args_list[0].kwargs['user'], 'EXAMPLE\\service')
        self.assertEqual(connection.call_args_list[1].kwargs['user'], 'person@example.test')
        self.assertEqual(connection.call_args_list[1].kwargs['receive_timeout'], 10)
        self.assertEqual(self.search.search.call_args.args, (
            'OU=People,DC=example,DC=test', '(&(sAMAccountName=person)(objectclass=person))'))
        self.search.unbind.assert_called_once()
        self.login.unbind.assert_called_once()

    def test_certificate_validation_false_is_explicitly_honoured(self):
        with patch.dict(os.environ, {'LDAP_TLS_VALIDATE_CERTIFICATES': 'False'}):
            _, _, tls, _ = self.authenticate()
            self.assertEqual(tls.call_args.kwargs['validate'], ssl.CERT_NONE)

    def test_ldaps_url_is_normalised_to_hostname(self):
        with patch.dict(os.environ, {'LDAP_SERVER': 'ldaps://directory.example.test:636'}):
            _, server, _, _ = self.authenticate()
            self.assertEqual(server.call_args.args[0], 'directory.example.test')

    def test_short_username_works_when_legacy_filter_is_email_based(self):
        with patch.dict(os.environ, {'LDAP_USER_SEARCH_FILTER':'(mail={email})'}):
            identity, _, _, _ = self.authenticate('person')
        self.assertIn('(sAMAccountName=person)',self.search.search.call_args.args[1])
        self.assertEqual(identity,'ldap:0102')

    def test_domain_username_is_accepted(self):
        identity,_,_,_=self.authenticate('EXAMPLE\\person')
        self.assertIn('(sAMAccountName=person)',self.search.search.call_args.args[1])
        self.assertEqual(identity,'ldap:0102')

    def test_filter_input_is_escaped_and_named_placeholders_work(self):
        self.authenticate('p*)(mail=*)@example.test')
        user_filter = self.search.search.call_args.args[1]
        self.assertIn('p\\2a\\29\\28mail=\\2a\\29', user_filter)
        with patch.dict(os.environ, {'LDAP_USER_SEARCH_FILTER': '(&(uid={username})(mail={email}))'}):
            self.authenticate()
            self.assertEqual(self.search.search.call_args.args[1], '(&(uid=person)(mail=person@example.test))')

    def test_upn_alias_and_dn_fallback(self):
        os.environ.pop('LDAP_PREFER_UPN_BIND')
        with patch.dict(os.environ, {'LDAP_BIND_PREFER_UPN': 'false'}):
            _, _, _, connection = self.authenticate()
            self.assertEqual(connection.call_args_list[1].kwargs['user'], 'CN=Person,DC=example,DC=test')
        self.search.entries[0].entry_attributes_as_dict.pop('userPrincipalName')
        _, _, _, connection = self.authenticate()
        self.assertEqual(connection.call_args_list[1].kwargs['user'], 'CN=Person,DC=example,DC=test')

    def test_unknown_or_ambiguous_directory_user_is_rejected(self):
        for entries in [[], self.search.entries * 2]:
            self.search.entries = entries
            with self.assertRaises(HTTPException) as failure: self.authenticate()
            self.assertEqual(failure.exception.status_code, 401)

    def test_bad_user_password_does_not_fall_back_to_local_login(self):
        self.login.bind.return_value = False
        with self.assertRaises(HTTPException) as failure: self.authenticate()
        self.assertEqual(failure.exception.status_code, 401)
        self.login.unbind.assert_called_once()

    def test_directory_failure_is_readable_and_does_not_expose_credentials(self):
        with patch('ldap3.Connection', side_effect=RuntimeError('private diagnostic')):
            with self.assertRaises(HTTPException) as failure: auth.authenticate('person@example.test', 'password')
            self.assertEqual(failure.exception.status_code, 503)
            self.assertNotIn('private diagnostic', failure.exception.detail)

    def test_stable_identity_is_required(self):
        self.search.entries[0].entry_attributes_as_dict.pop('objectGUID')
        with self.assertRaises(HTTPException) as failure: self.authenticate()
        self.assertEqual(failure.exception.status_code, 503)

    def test_configured_session_expiry_and_signature(self):
        user = {'email': 'person@example.test', 'directory_id': 'ldap:stable'}
        with patch.dict(os.environ, {'JWT_EXPIRY_HOURS': '2'}), patch('directory_auth.time.time', return_value=1000):
            token = auth.issue_token(user)
            self.assertEqual(auth.verify_token(token)['expires'], 8200)
            with self.assertRaises(HTTPException): auth.verify_token(token + 'x')
        with patch('directory_auth.time.time', return_value=8200):
            with self.assertRaises(HTTPException) as failure: auth.verify_token(token)
            self.assertEqual(failure.exception.status_code, 401)

    def test_ldap_mode_rejects_email_only_requests(self):
        from access_control import current_user
        with self.assertRaises(HTTPException) as failure:
            current_user(x_user_email='person@example.test', authorization='')
        self.assertEqual(failure.exception.status_code, 401)

    def test_developer_login_uses_existing_local_password_without_ldap(self):
        from admin import login, LoginRequest
        from access_control import password_hash
        user = {'email': 'person@example.test', 'password_hash': password_hash('fictional-local-password')}
        with patch.dict(os.environ, {'DEVELOPER_MODE': 'true'}), \
                patch('access_control.get_user', return_value=user), \
                patch('admin.profile_payload', return_value={'auth_type': 'local'}) as profile, \
                patch('directory_auth.authenticate') as ldap:
            self.assertEqual(login(LoginRequest(email=user['email'], password='fictional-local-password')), {'auth_type': 'local'})
            with self.assertRaises(HTTPException): login(LoginRequest(email=user['email'], password='wrong'))
            ldap.assert_not_called()
            profile.assert_called_once()

    def test_ldap_outage_cannot_accept_a_valid_local_password(self):
        from admin import login, LoginRequest
        from access_control import password_hash
        user = {'email': 'person@example.test', 'password_hash': password_hash('fictional-local-password')}
        with patch('access_control.get_user', return_value=user), \
                patch('directory_auth.authenticate', side_effect=HTTPException(503, 'Directory unavailable')):
            with self.assertRaises(HTTPException) as failure:
                login(LoginRequest(email=user['email'], password='fictional-local-password'))
            self.assertEqual(failure.exception.status_code, 503)


if __name__ == '__main__':
    unittest.main()
