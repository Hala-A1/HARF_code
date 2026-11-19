"""Environment-managed corporate administrators and repeatable deployment updates."""
from copy import deepcopy
from datetime import datetime, timezone
import os
import re


def super_admin_usernames():
    names = {value.strip().casefold() for value in os.getenv('LDAP_SUPER_ADMIN_USERNAMES', '').split(',') if value.strip()}
    if any(not re.fullmatch(r'[a-z0-9_.-]{2,128}', value) for value in names):
        raise ValueError('LDAP_SUPER_ADMIN_USERNAMES must contain comma-separated corporate usernames.')
    return names


def provision_authenticated_admin(person):
    if person.get('username', '').casefold() not in super_admin_usernames():
        return False
    if not person.get('email') or not person.get('directory_id'):
        raise ValueError('The approved directory administrator has no usable email or stable identity.')
    import access_control as access
    with access.DATA_LOCK:
        data = access.load_access_data()
        existing = next((u for u in data['users'] if u['email'].casefold() == person['email'].casefold()), None)
        if any(u.get('directory_id') == person['directory_id'] and u['email'].casefold() != person['email'].casefold() for u in data['users']):
            raise ValueError('Directory identity is already assigned to a different account.')
        if existing and existing.get('directory_id') and existing['directory_id'] != person['directory_id']:
            raise ValueError('The administrator email belongs to a different directory identity.')
        expected = dict(email=person['email'], name=person['name'], username=person['username'],
                        directory_id=person['directory_id'], auth_source='ldap', role='super_admin',
                        channel_id=None, workspaces=['rewrite'], active=True, environment_managed_admin=True)
        if existing and all(existing.get(k) == v for k, v in expected.items()) and 'password_hash' not in existing:
            return True
        if existing:
            existing.update(expected); existing.pop('password_hash', None)
        else:
            data['users'].append({**expected, 'created_at': datetime.now(timezone.utc).isoformat()})
        access.save_access_data(data)
    return True


def is_demo_account(user):
    if user.get('auth_source') == 'ldap' or user.get('directory_id'):
        return False
    email = user.get('email', '').casefold()
    return email in {'mariam.k@eand.ae', 'consumer.admin@eand.ae'} or bool(re.fullmatch(
        r'(?:b2b|b2c|security)\.(?:admin|user|approver[1-3])@eand\.ae', email))


def update_records(data):
    """Keep real people/history, remove known demos, and register the shipped pack."""
    before = deepcopy(data)
    data.pop('access_requests', None)
    data['activity'] = [event for event in data.get('activity', []) if event.get('action') != 'Access request reviewed']
    data['users'] = [u for u in data['users'] if not is_demo_account(u)]
    if not any(u['email'].casefold() == 'developer@eand.ae' for u in data['users']):
        from access_control import DEFAULT_WORKSPACES
        data['users'].append(dict(email='developer@eand.ae', name='Development Team', role='super_admin',
                                  channel_id=None, workspaces=DEFAULT_WORKSPACES, auth_source='developer_backup', active=True))
    developer = next(u for u in data['users'] if u['email'].casefold() == 'developer@eand.ae')
    developer.update(username='developer', auth_source='developer_backup')
    names = super_admin_usernames()
    for user in data['users']:
        user.pop('onboarding_pending', None)
        if user.get('environment_managed_admin') and user.get('username', '').casefold() not in names:
            user['active'] = False
    if not any(c['id'] == 'cx-comms' for c in data['channels']):
        data['channels'].append(dict(id='cx-comms', name='CX Comms',
            instruction_modules=['CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES','CX_COMMS_USER_GUIDE'],
            created_at=datetime.now(timezone.utc).isoformat()))
    return data != before


def seed_cx_instructions():
    import access_control as access
    from storage_backend import oracle_enabled
    if not oracle_enabled():
        return
    from oracle_runtime import transaction
    from oracle_instructions import append_version
    with transaction() as db, db.cursor() as cursor:
        cursor.execute("SELECT is_active FROM genai_harf_channels WHERE channel_id='cx-comms'")
        channel = cursor.fetchone()
        if not channel or not channel[0]: return
        for module in ('CX_COMMS_SYSTEM','CX_COMMS_TEMPLATES','CX_COMMS_USER_GUIDE'):
            cursor.execute('SELECT COUNT(*) FROM genai_harf_instructions WHERE channel_id=:channel AND module_id=:module', channel='cx-comms', module=module)
            if cursor.fetchone()[0]: continue  # Oracle edits remain authoritative.
            file = access.CHANNEL_PROMPT_DIR / 'cx-comms' / access.INSTRUCTION_MODULES[module]['filename']
            if not file.is_file():
                raise ValueError('The CX Comms instruction pack is missing from the deployment.')
            append_version(db, 'cx-comms', module, file, file.read_text(encoding='utf-8'),
                           {'name':'Deployment setup','role':'system'}, 'baseline', 'Register the checked-in CX Comms pack.')


def apply_deployment_updates(strict=True):
    import access_control as access
    from directory_auth import enabled, find_user
    # Resolve all configured admins before touching saved account permissions.
    try:
        people = [find_user(username) for username in sorted(super_admin_usernames())] if enabled() else []
    except Exception as error:
        if strict: raise
        import logging
        logging.getLogger(__name__).warning('Directory administrator provisioning deferred type=%s; run deployment setup when LDAP is available.', type(error).__name__)
        people = []
    with access.DATA_LOCK:
        data = access.load_access_data()
        if update_records(data): access.save_access_data(data)
        seed_cx_instructions()
        for person in people: provision_authenticated_admin(person)
    return {'directory_admins': len(people), 'channel': 'cx-comms'}


if __name__ == '__main__':
    from environment import load_environment
    load_environment()
    from directory_auth import enabled
    if not enabled() or not super_admin_usernames():
        raise SystemExit('The production pipeline requires AUTH_PROVIDER=ldap, DEVELOPER_MODE=false and the approved LDAP_SUPER_ADMIN_USERNAMES list.')
    from oracle_migration import require_stopped
    require_stopped()
    print(apply_deployment_updates())
