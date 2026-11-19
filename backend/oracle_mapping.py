"""Lossless source snapshots plus explicit mappings to schema 001.

No source normalization is written back. Unknown fields remain in JSON payloads
and the complete source snapshot, so future migrations can recover them.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def timestamp(value):
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        result = datetime.fromtimestamp(value, timezone.utc)
    else:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError('Source timestamp has no timezone; migration requires explicit timezone information.')
    return result.isoformat(timespec='microseconds')


TABLES = (
    'genai_harf_channels', 'genai_harf_users', 'genai_harf_instructions', 'genai_harf_instruction_versions',
    'genai_harf_batches', 'genai_harf_copy_items', 'genai_harf_outputs', 'genai_harf_copy_versions',
    'genai_harf_approval_events', 'genai_harf_language_approvals', 'genai_harf_notifications',
    'genai_harf_activity', 'genai_harf_feedback', 'genai_harf_channel_limits', 'genai_harf_user_limits', 'genai_harf_request_usage',
)

CLOBS = {
    'config_json', 'review_languages', 'profile_json', 'content_md', 'metadata_json',
    'change_note', 'user_instructions', 'payload_json', 'source_text',
    'generation_instructions', 'format_instructions', 'output_text', 'quality_report',
    'change_request', 'event_note', 'approval_note', 'message_text', 'detail_text',
    'reason_text', 'snapshot_json', 'instruction_manifest', 'admin_note',
}
TIMESTAMPS = {'created_at','updated_at','deleted_at','submitted_at','completed_at',
              'occurred_at','approved_at','reviewed_at','expires_at'}


def build_rows(snapshot):
    rows = {table: [] for table in TABLES}
    add = lambda table, **values: rows[table].append(values)
    data = snapshot['access']
    captured = timestamp(snapshot['captured_at'])
    for c in data.get('channels', []):
        add('genai_harf_channels', channel_id=c['id'], channel_name=c['name'],
            is_active=int(not c.get('deleted_at')), created_at=timestamp(c.get('created_at')) or captured,
            deleted_at=timestamp(c.get('deleted_at')), deleted_by=c.get('deleted_by'), config_json=canonical(c))
    for u in data.get('users', []):
        add('genai_harf_users', email=u['email'], display_name=u['name'], role_name=u['role'], channel_id=u.get('channel_id'),
            is_active=int(u.get('active',True)), approval_layer=u.get('approval_layer'), directory_id=u.get('directory_id'),
            auth_source=u.get('auth_source') or ('ldap' if u.get('directory_id') else 'local'), password_hash=u.get('password_hash'),
            review_languages=canonical(u.get('review_languages', [])), profile_json=canonical(u),
            created_at=timestamp(u.get('created_at')) or captured, updated_at=timestamp(u.get('updated_at')) or captured)
    histories = snapshot['sqlite'].get('instruction-versions.sqlite3', {}).get('instruction_versions', [])
    current = {(i['channel_id'],i['module_id']): dict(i) for i in snapshot['instructions']}
    for h in histories:
        key = (h['channel_id'],h['module_id'])
        if key not in current:
            candidates = [x for x in histories if (x['channel_id'],x['module_id']) == key]
            latest = max(candidates,key=lambda x:x['version'])
            current[key] = dict(channel_id=key[0], module_id=key[1], file_name=key[1]+'.md',
                                content=latest['content'], kind='reference', active=False)
    for key, i in current.items():
        versions = [h for h in histories if (h['channel_id'],h['module_id'])==key]
        latest = max(versions,key=lambda h:h['version']) if versions else None
        checksum=hashlib.sha256(i['content'].encode('utf-8')).hexdigest()
        version = latest['version'] if latest else 0
        if latest is None or latest['checksum']!=checksum:
            version+=1
            histories=histories+[dict(channel_id=key[0],module_id=key[1],version=version,content=i['content'],checksum=checksum,
                actor_name='Migration snapshot',actor_email=None,actor_role='system',action='migration_baseline',
                note='Current file captured at migration; existing history preserved.',restored_from=None,
                characters=len(i['content']),words=len(i['content'].split()),lines=len(i['content'].splitlines()),created_at=captured)]
        add('genai_harf_instructions', channel_id=key[0],module_id=key[1],file_name=i['file_name'],
            display_name=i.get('display_name',i['file_name']), instruction_kind=i['kind'],
            is_active=int(i.get('active', True)), current_version=version,
            checksum=checksum, content_md=i['content'],
            metadata_json=canonical(i), updated_at=captured)
    for h in histories:
        add('genai_harf_instruction_versions',channel_id=h['channel_id'],module_id=h['module_id'],version_no=h['version'],
            content_md=h['content'],checksum=h['checksum'],actor_name=h['actor_name'],actor_email=h.get('actor_email'),
            actor_role=h['actor_role'],change_action=h['action'],change_note=h.get('note'),restored_from=h.get('restored_from'),
            character_count=h['characters'],word_count=h['words'],line_count=h['lines'],created_at=timestamp(h['created_at']))
    for b in data.get('approval_batches', []):
        add('genai_harf_batches',batch_id=b['id'],channel_id=b['channel_id'],title=b['title'],archive_name=b.get('archive_name'),
            task_name=b.get('task'),content_channel=b.get('content_channel'),audience=b.get('audience'),product_type=b.get('product_type'),
            user_instructions=b.get('instructions'),status=b['status'],current_layer=b.get('current_layer',0),progress=b.get('progress',0),
            created_by_email=b['created_by_email'],created_by_name=b['created_by'],created_by_id=b.get('created_by_id'),
            created_at=timestamp(b['created_at']),updated_at=timestamp(b['updated_at']),submitted_at=timestamp(b.get('submitted_at')),
            completed_at=timestamp(b.get('completed_at')),approval_method=b.get('approval_method','normal_review'),payload_json=canonical(b))
        for i in b.get('items', []):
            source=i.get('source_details',{})
            add('genai_harf_copy_items',batch_id=b['id'],item_id=i['id'],source_filename=i.get('source_filename') or i.get('filename'),
                archive_name=i.get('archive_name'),output_key=i.get('output_id'),output_name=i.get('output_name'),source_text=i.get('source'),
                generation_instructions=i.get('generation_instructions'),format_instructions=i.get('format_instructions'),
                source_bytes=source.get('size_bytes'),source_characters=source.get('characters'),source_words=source.get('words'),metadata_json=canonical(i))
            for lang,text in i.get('generated',{}).items():
                if lang not in {'en','ar'}:
                    raise ValueError('Unrecognized output language; no content will be silently discarded.')
                versions=[v for v in i.get('versions',[]) if v['language']==lang]
                version=max(i.get('initial_versions',{}).get(lang,1),1)+len(versions)
                details=i.get('generated_details',{}).get(lang,{})
                add('genai_harf_outputs',batch_id=b['id'],item_id=i['id'],language_code=lang,version_no=version,
                    output_text=text,guideline_score=details.get('score'),character_count=len(text),word_count=len(text.split()),
                    quality_report=canonical(details['quality_report']) if details.get('quality_report') is not None else None,
                    metadata_json=canonical(details),updated_at=timestamp(b['updated_at']))
                for n,v in enumerate(versions,1):
                    add('genai_harf_copy_versions',batch_id=b['id'],item_id=i['id'],language_code=lang,version_no=n,
                        output_text=v['text'],actor_email=v.get('actor_email'),created_at=timestamp(v['timestamp']),
                        change_request=v.get('change_request'),metadata_json=canonical(v))
        for n,e in enumerate(b.get('events',[])):
            add('genai_harf_approval_events',event_id=e.get('id') or digest([b['id'],n,e]),batch_id=b['id'],event_action=e['action'],
                actor_email=e.get('actor_email'),actor_name=e['actor'],actor_role=e.get('actor_role'),from_layer=e.get('from_layer'),
                to_layer=e.get('to_layer'),event_note=e.get('note'),occurred_at=timestamp(e['timestamp']),payload_json=canonical(e))
        for layer, approvals in b.get('language_approvals',{}).items():
            for lang, a in approvals.items():
                add('genai_harf_language_approvals',batch_id=b['id'],layer_no=int(layer),language_code=lang,
                    reviewer_email=a.get('email') or a.get('actor_email'),reviewer_name=a.get('name') or a.get('actor') or a.get('reviewer_name') or 'Recorded reviewer',
                    approved_at=timestamp(a.get('timestamp') or a.get('approved_at')),approval_note=a.get('note'),payload_json=canonical(a))
    for n in data.get('notifications',[]):
        add('genai_harf_notifications',notification_id=n['id'],channel_id=n.get('channel_id'),batch_id=n.get('batch_id'),
            recipient_email=n['recipient_email'],title=n['title'],message_text=n['message'],notification_kind=n['kind'],
            is_read=int(n.get('read',False)),created_at=timestamp(n['created_at']),payload_json=canonical(n))
    activity_duplicates={}
    for a in data.get('activity',[]):
        fingerprint=digest(a)
        occurrence=activity_duplicates.get(fingerprint,0)
        activity_duplicates[fingerprint]=occurrence+1
        add('genai_harf_activity',activity_id=a.get('id') or digest([fingerprint,occurrence]),channel_id=a.get('channel_id'),actor_email=a['actor_email'],
            actor_name=a['actor'],actor_id=a.get('actor_id'),event_action=a['action'],detail_text=a.get('detail'),
            occurred_at=timestamp(a['timestamp']),metadata_json=canonical(a))
    for f in snapshot['sqlite'].get('feedback.sqlite3',{}).get('feedback',[]):
        add('genai_harf_feedback',feedback_id=f['id'],channel_id=f['channel_id'],workspace_name=f['workspace'],user_email=f['user_email'],
            user_name=f['user_name'],fingerprint=f['fingerprint'],rating=f['rating'],reason_text=f['reason'],snapshot_json=f['snapshot'],
            instruction_manifest=f['instruction_manifest'],created_at=timestamp(f['created_at']),updated_at=timestamp(f['updated_at']),
            review_status=f['status'],admin_note=f['admin_note'],reviewed_by=f.get('reviewed_by'),reviewed_at=timestamp(f.get('reviewed_at')))
    limits=snapshot['sqlite'].get('request-limits.sqlite3',{})
    for c in limits.get('channel_limits',[]):
        add('genai_harf_channel_limits',channel_id=c['channel'],monthly_limit=c['monthly_limit'])
    for u in limits.get('user_limits',[]):
        add('genai_harf_user_limits',channel_id=u['channel'],principal_id=u['principal'],monthly_limit=u['monthly_limit'])
    for u in limits.get('request_usage',[]):
        add('genai_harf_request_usage',request_id=u['id'],channel_id=u['channel'],principal_id=u['principal'],month_key=u['month'],
            request_state=u['state'],expires_at=timestamp(u['expires']),created_at=timestamp(u['created_at']))
    validate_rows(rows)
    return rows


def validate_rows(rows):
    """Check the installed schema's column lengths/required values before any import."""
    schema=(Path(__file__).resolve().parents[1]/'database/oracle/01_create_tables.sql').read_text(encoding='utf-8')
    for table,body in re.findall(r'CREATE TABLE (genai_harf_\w+)\s*\((.*?)\n\);',schema,re.S|re.I):
        if table not in rows:
            continue
        columns={}
        for line in body.splitlines():
            m=re.match(r'\s*(\w+)\s+(VARCHAR2\((\d+) CHAR\)|CLOB|NUMBER(?:\([^)]*\))?|TIMESTAMP\(6\) WITH TIME ZONE)(.*)',line,re.I)
            if m:
                columns[m[1]]=(int(m[3]) if m[3] else None,'NOT NULL' in m[4].upper() or 'PRIMARY KEY' in m[4].upper())
        for record in rows[table]:
            if set(record)-columns.keys():
                raise ValueError('Unrecognized migration columns in '+table)
            for column,(limit,required) in columns.items():
                value=record.get(column)
                if required and (value is None or value==''):
                    raise ValueError('Missing required value: '+table+'.'+column)
                if limit and value is not None and len(str(value))>limit:
                    raise ValueError('Source exceeds column length: '+table+'.'+column+'. Nothing was shortened.')
    for table,column,parent,parent_column in (
        ('genai_harf_users','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_instructions','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_batches','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_copy_items','batch_id','genai_harf_batches','batch_id'),
        ('genai_harf_approval_events','batch_id','genai_harf_batches','batch_id'),
        ('genai_harf_language_approvals','batch_id','genai_harf_batches','batch_id'),
        ('genai_harf_notifications','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_notifications','batch_id','genai_harf_batches','batch_id'),
        ('genai_harf_activity','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_feedback','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_channel_limits','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_user_limits','channel_id','genai_harf_channels','channel_id'),
        ('genai_harf_request_usage','channel_id','genai_harf_channels','channel_id'),
    ):
        parents={r[parent_column] for r in rows[parent]}
        if any(r[column] is not None and r[column] not in parents for r in rows[table]):
            raise ValueError('Orphaned source reference: '+table+'.'+column+'. Review the original data; no rows were discarded.')
