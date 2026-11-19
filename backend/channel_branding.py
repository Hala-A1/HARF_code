"""Rename the regulatory workspace without changing identities or history keys."""
import re

NAME = 'Regulatory Compliance'


def instruction_labels(content):
    content = re.sub(r'\bSecurity\b', NAME, content)
    # These are file references, not permanent template/index IDs.
    return (content.replace('_SECURITY_', '_REGULATORY_COMPLIANCE_')
            .replace('SECURITY-', 'REGULATORY-COMPLIANCE-')
            .replace('security-', 'regulatory-compliance-'))


def rename_channel_records(data):
    changed = False
    for channel in data.get('channels', []):
        if channel['id'] == 'security' and channel.get('name') != NAME:
            channel['name'] = NAME
            changed = True
    for person in data.get('users', []):
        if person.get('channel_id') == 'security':
            name = re.sub(r'\bSecurity\b', NAME, person.get('name', ''))
            if name != person.get('name', ''):
                person['name'] = name
                changed = True
    return changed


def migrate_regulatory_channel():
    import access_control as access
    from instruction_versions import version_repository, _atomic_write
    from storage_backend import oracle_enabled
    with access.DATA_LOCK:
        data = access.load_access_data()
        if rename_channel_records(data):
            access.save_access_data(data)
        actor = {'name': 'Channel naming update', 'role': 'system'}
        for module in ['SECURITY_POLICY', 'SECURITY_MEMO', 'SECURITY_USER_GUIDE']:
            source = access.instruction_path(module, 'security')
            if not source.exists():
                continue
            target = access.CHANNEL_PROMPT_DIR / 'security' / access.INSTRUCTION_MODULES[module]['filename']
            original = source.read_text(encoding='utf-8')
            revised = instruction_labels(original)
            if revised != original:
                version_repository(source).save('security', module, source, target, revised, actor,
                                                note='Rename the channel and instruction index labels to Regulatory Compliance; writing requirements, account identities and version history retained.')
            if not target.exists() or target.read_text(encoding='utf-8') != revised:
                _atomic_write(target, revised)
            if oracle_enabled():
                from oracle_runtime import transaction
                with transaction() as db, db.cursor() as cursor:
                    cursor.execute('UPDATE genai_harf_instructions SET file_name=:name WHERE channel_id=:channel AND module_id=:module AND file_name<>:name',
                                   name=target.name, channel='security', module=module)
            # Remove only the obsolete cache in this channel, after saving its
            # replacement and retaining its previous content in version history.
            if source != target and source.parent.resolve() == target.parent.resolve() and source.name.startswith(('01_SECURITY_', '02_SECURITY_', '03_SECURITY_')):
                source.unlink(missing_ok=True)
