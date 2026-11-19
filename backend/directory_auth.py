"""Optional LDAPS authentication. Roles remain explicitly assigned by admins."""
import base64
import hashlib
import hmac
import json
import os
import ssl
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

from fastapi import HTTPException


def _boolean(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {'true', 'false'}:
        raise HTTPException(status_code=503, detail=f'{name} must be true or false. Contact your administrator.')
    return value == 'true'


def enabled():
    if _boolean('DEVELOPER_MODE'):
        return False
    # Keep existing deployments compatible; new settings use AUTH_PROVIDER.
    provider = (os.getenv('AUTH_PROVIDER') or os.getenv('AUTH_MODE', 'local')).strip().lower()
    if provider not in {'ldap', 'local'}:
        raise HTTPException(status_code=503, detail='The authentication provider is not configured correctly.')
    return provider == 'ldap'


def _setting(primary, legacy='', default=''):
    return os.getenv(primary) or (os.getenv(legacy) if legacy else None) or default


def _session_secret():
    return _setting('JWT_SECRET', 'LDAP_SESSION_SECRET')


def status():
    password = os.getenv('LDAP_BIND_PASSWORD', '')
    configured = bool(_setting('LDAP_SERVER', 'LDAP_HOST') and
                      _setting('LDAP_USER_SEARCH_BASE', 'LDAP_BASE_DN') and
                      os.getenv('LDAP_BIND_DN') and password and password.strip('*') and
                      len(_session_secret()) >= 32)
    return {'mode': 'ldap' if enabled() else 'local', 'configured': configured,
            'developer_mode': _boolean('DEVELOPER_MODE'),
            'identity_source': 'LDAP directory' if enabled() else 'Assigned local accounts'}


def _secret():
    secret = _session_secret()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail='Directory sign-in needs a configured session secret. Contact your administrator.')
    return secret.encode()


def issue_token(user):
    try:
        hours = int(os.getenv('JWT_EXPIRY_HOURS', '8'))
        if not 1 <= hours <= 168:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=503, detail='JWT_EXPIRY_HOURS must be between 1 and 168.') from None
    payload = base64.urlsafe_b64encode(json.dumps({'email': user['email'], 'directory_id': user['directory_id'], 'expires': time.time()+hours*3600}, separators=(',', ':')).encode()).rstrip(b'=')
    signature = hmac.new(_secret(), payload, hashlib.sha256).hexdigest()
    return payload.decode() + '.' + signature


def verify_token(token):
    try:
        payload, signature = token.split('.')
        if not hmac.compare_digest(hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest(), signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        if float(data['expires']) <= time.time() or not data.get('directory_id') or not isinstance(data.get('email'), str) or not data['email']:
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError):
        raise HTTPException(status_code=401, detail='Your directory session expired or is invalid. Sign in again.') from None


def authenticate(email, password):
    if not password:
        raise HTTPException(status_code=401, detail='The email or password is incorrect.')
    if not status()['configured']:
        raise HTTPException(status_code=503, detail='LDAP connection settings are incomplete. Contact your administrator.')
    _secret()
    try:
        from ldap3 import Server, Connection, Tls, SUBTREE
        from ldap3.utils.conv import escape_filter_chars
        from ldap3.utils.dn import escape_rdn
    except ImportError:
        raise HTTPException(status_code=503, detail='The LDAP connector dependency is not installed. Contact your administrator.') from None
    search = login = None
    try:
        address = _setting('LDAP_SERVER', 'LDAP_HOST').strip()
        parsed = urlsplit(address if '://' in address else '//' + address)
        if not parsed.hostname or parsed.scheme not in {'', 'ldap', 'ldaps'} or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
            raise HTTPException(status_code=503, detail='LDAP_SERVER must contain a directory hostname or LDAP URL.')
        use_ssl = _boolean('LDAP_USE_SSL', True)
        if parsed.scheme == 'ldaps' and not use_ssl:
            raise HTTPException(status_code=503, detail='An ldaps:// server requires LDAP_USE_SSL=true.')
        port = int(os.getenv('LDAP_PORT') or parsed.port or (636 if use_ssl else 389))
        timeout = int(os.getenv('LDAP_RECEIVE_TIMEOUT_SECONDS', '10'))
        if not 1 <= port <= 65535 or not 1 <= timeout <= 120:
            raise HTTPException(status_code=503, detail='LDAP port or timeout is outside the supported range.')
        tls = Tls(validate=ssl.CERT_REQUIRED if _boolean('LDAP_TLS_VALIDATE_CERTIFICATES', True) else ssl.CERT_NONE,
                  ca_certs_file=os.getenv('LDAP_CA_CERT_FILE') or None)
        server = Server(parsed.hostname, port=port, use_ssl=use_ssl, tls=tls, connect_timeout=timeout)
        search = Connection(server, user=os.environ['LDAP_BIND_DN'], password=os.environ['LDAP_BIND_PASSWORD'], auto_bind=True, receive_timeout=timeout)
        username = email.rsplit('\\', 1)[-1].split('@', 1)[0]
        template = _setting('LDAP_USER_SEARCH_FILTER', 'LDAP_USER_FILTER', '(mail={email})')
        if '@' not in email and '{email}' in template:
            template = os.getenv('LDAP_USERNAME_SEARCH_FILTER', '(&(objectClass=person)(sAMAccountName={username}))')
        user_filter = template.replace('{email}', escape_filter_chars(email)).replace('{username}', escape_filter_chars(username)).replace('{}', escape_filter_chars(username))
        identity_attribute = os.getenv('LDAP_ID_ATTRIBUTE', 'objectGUID')
        search.search(_setting('LDAP_USER_SEARCH_BASE', 'LDAP_BASE_DN'), user_filter, search_scope=SUBTREE,
                      attributes=['mail', 'userPrincipalName', 'sAMAccountName', 'displayName', identity_attribute], size_limit=2)
        if len(search.entries) != 1:
            raise HTTPException(status_code=401, detail='The email or password is incorrect.')
        entry = search.entries[0]
        attributes = entry.entry_attributes_as_dict
        upn = attributes.get('userPrincipalName')
        upn = upn[0] if isinstance(upn, list) and upn else upn
        prefer_upn = _boolean('LDAP_PREFER_UPN_BIND') if 'LDAP_PREFER_UPN_BIND' in os.environ else _boolean('LDAP_BIND_PREFER_UPN', True)
        user_dn = entry.entry_dn or os.getenv('LDAP_USER_DN_TEMPLATE', '').replace('{username}', escape_rdn(username))
        login_identity = upn if prefer_upn and upn else user_dn
        if not login_identity:
            raise HTTPException(status_code=503, detail='The directory did not provide a usable login identity.')
        login = Connection(server, user=login_identity, password=password, receive_timeout=timeout)
        if not login.bind():
            raise HTTPException(status_code=401, detail='The email or password is incorrect.')
        raw = attributes.get(identity_attribute)
        value = raw[0] if isinstance(raw, list) and raw else raw
        if not value:
            raise HTTPException(status_code=503, detail='The directory must provide a stable objectGUID or entryUUID for request allocations.')
        value = value.hex() if isinstance(value, bytes) else str(value)
        return DirectoryIdentity('ldap:' + value.casefold(), directory_person(entry, username))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail='The directory service could not be reached securely. Contact your administrator.') from None
    finally:
        for connection in (login, search):
            if connection is not None:
                try: connection.unbind()
                except Exception: pass


class DirectoryIdentity(str):
    """Stable identity remains string-compatible with stored sessions and quotas."""
    def __new__(cls, value, person):
        identity = super().__new__(cls, value)
        identity.person = person
        return identity


def directory_person(entry, fallback=''):
    values = entry.entry_attributes_as_dict
    def value(key):
        found = values.get(key)
        return found[0] if isinstance(found, list) and found else found
    raw = value(os.getenv('LDAP_ID_ATTRIBUTE', 'objectGUID'))
    stable = raw.hex() if isinstance(raw, bytes) else str(raw or '')
    email = str(value('mail') or value('userPrincipalName') or '').strip().lower()
    return {'username': str(value('sAMAccountName') or fallback).strip(),
            'email': email if '@' in email else '',
            'name': str(value('displayName') or value('sAMAccountName') or fallback).strip(),
            'directory_id': 'ldap:' + stable.casefold() if stable else ''}


@contextmanager
def directory_search_connection():
    if not enabled() or not status()['configured']:
        raise HTTPException(503, 'LDAP search is not configured. Contact IT support.')
    from ldap3 import Server, Connection, Tls
    connection = None
    try:
        address = _setting('LDAP_SERVER', 'LDAP_HOST').strip()
        parsed = urlsplit(address if '://' in address else '//' + address)
        if not parsed.hostname or parsed.scheme not in {'', 'ldap', 'ldaps'} or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
            raise HTTPException(503, 'LDAP_SERVER must contain a directory hostname or LDAP URL.')
        ssl_enabled = _boolean('LDAP_USE_SSL', True)
        if parsed.scheme == 'ldaps' and not ssl_enabled:
            raise HTTPException(503, 'An ldaps:// server requires LDAP_USE_SSL=true.')
        port = int(os.getenv('LDAP_PORT') or parsed.port or (636 if ssl_enabled else 389))
        timeout = int(os.getenv('LDAP_RECEIVE_TIMEOUT_SECONDS', '10'))
        if not 1 <= port <= 65535 or not 1 <= timeout <= 120:
            raise HTTPException(503, 'LDAP port or timeout is outside the supported range.')
        tls = Tls(validate=ssl.CERT_REQUIRED if _boolean('LDAP_TLS_VALIDATE_CERTIFICATES', True) else ssl.CERT_NONE,
                  ca_certs_file=os.getenv('LDAP_CA_CERT_FILE') or None)
        server = Server(parsed.hostname, port=port, use_ssl=ssl_enabled, tls=tls, connect_timeout=timeout)
        connection = Connection(server, user=os.environ['LDAP_BIND_DN'], password=os.environ['LDAP_BIND_PASSWORD'], auto_bind=True, receive_timeout=timeout)
        yield connection
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'The corporate directory could not be reached. Contact IT support.') from None
    finally:
        if connection is not None:
            try: connection.unbind()
            except Exception: pass


def search_users(query, exact=False):
    from ldap3 import SUBTREE
    from ldap3.utils.conv import escape_filter_chars
    query = query.strip()
    if not 2 <= len(query) <= 128:
        raise HTTPException(422, 'Enter at least two characters of the corporate username.')
    username = query.rsplit('\\', 1)[-1].split('@', 1)[0]
    safe = escape_filter_chars(username)
    # Prefix search is confined to usernames; no unbounded directory browsing.
    match = safe if exact else safe + '*'
    identity_attribute = os.getenv('LDAP_ID_ATTRIBUTE', 'objectGUID')
    with directory_search_connection() as connection:
        match_filter = f'(sAMAccountName={match})'
        if exact and '@' in query:
            address = escape_filter_chars(query)
            match_filter = f'(|(mail={address})(userPrincipalName={address}))'
        connection.search(_setting('LDAP_USER_SEARCH_BASE', 'LDAP_BASE_DN'),
            f'(&(objectClass=person){match_filter})', search_scope=SUBTREE,
            attributes=['mail', 'userPrincipalName', 'sAMAccountName', 'displayName', identity_attribute],
            size_limit=2 if exact else 10, time_limit=5)
        result = connection.result or {}
        if result.get('result', 0) not in {0, 4}:
            raise HTTPException(503, 'The directory search could not complete. Contact IT support.')
        return [person for entry in connection.entries if (person := directory_person(entry, username))['email'] and person['directory_id']]


def find_user(username):
    matches = search_users(username, exact=True)
    if len(matches) != 1:
        raise HTTPException(422, 'Select one valid corporate directory account with an email and stable identity.')
    return matches[0]
