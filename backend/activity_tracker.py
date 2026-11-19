"""Read-only activity projection with server-side ownership and channel boundaries."""
import hashlib
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from access_control import current_user, load_access_data, available_channels, require_channel_access

router = APIRouter(prefix='/api/activity', tags=['activity'])
COLLAPSE_AT = 180


def display(value):
    if value is None: return ''
    if isinstance(value, str): return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def output_text(value):
    if not isinstance(value, dict): return display(value)
    labels = {'en': 'English', 'ar': 'Arabic', 'english': 'English', 'arabic': 'Arabic'}
    return '\n\n'.join(f'{labels.get(language, language)}\n{display(text)}' for language, text in value.items())


def visible(user, channel, email, actor_id=None):
    if user['role'] == 'super_admin':
        return (actor_id == user.get('directory_id') if actor_id and actor_id.startswith('ldap:')
                else email.casefold() == user['email'].casefold())
    if channel != user.get('channel_id'): return False
    if user['role'] == 'channel_admin': return True
    return (actor_id == user.get('directory_id') if actor_id and actor_id.startswith('ldap:')
            else email.casefold() == user['email'].casefold())


def rows_for(user, data):
    rows = []
    visible_batches = {}
    for batch in data.get('approval_batches', []):
        if not visible(user, batch.get('channel_id'), batch.get('created_by_email', ''), batch.get('created_by_id')): continue
        visible_batches[batch['id']] = batch
        sent = bool(batch.get('submitted_at') or any(e.get('action') == 'submitted' for e in batch.get('events', [])))
        final = {'approved': 'Approved', 'rejected': 'Not approved'}.get(batch.get('status'), 'No final decision')
        for item in batch.get('items', []):
            rows.append({'id': f"copy:{batch['id']}:{item['id']}", 'time': batch.get('created_at', ''),
                         'channel': batch.get('channel_id', ''), 'person': batch.get('created_by', ''), 'email': batch.get('created_by_email', ''),
                         'action': 'Generated copy', 'task': batch.get('task', ''), 'format': batch.get('content_channel', ''),
                         'product': batch.get('product_type', ''), 'audience': batch.get('audience', ''),
                         'input': item.get('source', ''), 'output': output_text(item.get('generated', {})),
                         'instructions': batch.get('instructions', ''),
                         'source_files': item.get('source_filename') or item.get('filename', ''),
                         'output_files': item.get('output_name') or item.get('filename', ''),
                         'sent_to_approval': 'Yes' if sent else 'No', 'final_status': final,
                         'details': display({'title': batch.get('title'), 'source_details': item.get('source_details'), 'generated_details': item.get('generated_details')})})
    for event in data.get('activity', []):
        if not visible(user, event.get('channel_id'), event.get('actor_email', ''), event.get('actor_id')): continue
        action = event.get('action', '')
        meta = event.get('metadata') or {}
        # Batch generation already appears once per output above. Approval workflow stays in its own queue.
        if action in {'Bulk copy generated', 'Copy saved for approval'} and meta.get('batch_id'): continue
        if re.search(r'approval|approved|rejected|returned|warning|urgent', action, re.I): continue
        identity = event.get('id') or hashlib.sha256(json.dumps(event, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        batch = visible_batches.get(meta.get('batch_id'), {})
        sent = bool(batch.get('submitted_at') or any(e.get('action') == 'submitted' for e in batch.get('events', [])))
        mapped = {'task', 'content_channel', 'audience', 'product_type', 'source', 'generated', 'instructions', 'filename', 'files', 'output_files'}
        rows.append({'id': 'event:' + identity, 'time': event.get('timestamp', ''), 'channel': event.get('channel_id') or '',
                     'person': event.get('actor', ''), 'email': event.get('actor_email', ''), 'action': action,
                     'task': meta.get('task', ''), 'format': meta.get('content_channel', meta.get('format', '')),
                     'product': meta.get('product_type', ''), 'audience': meta.get('audience', ''),
                     'input': display(meta.get('source', '')), 'output': output_text(meta.get('generated', '')),
                     'instructions': meta.get('instructions', ''), 'source_files': display(meta.get('files', meta.get('filename', ''))),
                     'output_files': display(meta.get('output_files', '')), 'sent_to_approval': ('Yes' if sent else 'No') if batch else '—',
                     'final_status': {'approved': 'Approved', 'rejected': 'Not approved'}.get(batch.get('status'), 'No final decision') if batch else '—',
                     'details': display({'description': event.get('detail', ''), **{k: v for k, v in meta.items() if k not in mapped and not re.search(r'approval|status|layer|decision|progress|reason|format_instructions', k, re.I)}})})
    return sorted(rows, key=lambda row: row['time'], reverse=True)


@router.get('')
def activity(channel_id: str = '', search: str = Query(default='', max_length=200), final_status: str = 'all',
             offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100), user: dict = Depends(current_user)):
    if channel_id: require_channel_access(user, channel_id)
    data = load_access_data()
    rows = rows_for(user, data)
    if channel_id: rows = [row for row in rows if row['channel'] == channel_id]
    if final_status != 'all': rows = [row for row in rows if row['final_status'] == final_status]
    if search.strip():
        query = search.strip().casefold()
        rows = [row for row in rows if any(query in display(value).casefold() for value in row.values())]
    total = len(rows)
    previews = []
    for row in rows[offset:offset+limit]:
        long = [key for key, value in row.items() if len(display(value)) > COLLAPSE_AT]
        previews.append({**{key: display(value)[:COLLAPSE_AT] for key, value in row.items()}, 'expandable': long})
    return {'rows': previews, 'total': total, 'channels': available_channels(user, data), 'offset': offset, 'limit': limit,
            'scope': 'Your channel activity' if user['role'] == 'channel_admin' else 'Your activity only'}


@router.get('/{row_id}')
def activity_detail(row_id: str, user: dict = Depends(current_user)):
    row = next((row for row in rows_for(user, load_access_data()) if row['id'] == row_id), None)
    if not row: raise HTTPException(status_code=404, detail='This activity is unavailable.')
    return row
