"""Request-lifetime classification, including streams and persisted copy provenance."""
import hashlib
import json
from urllib.parse import parse_qs

from starlette.concurrency import run_in_threadpool
from inference import inference_scope

CONTENT_KEYS = {'source', 'feedback', 'generated', 'enhanced', 'text', 'original', 'context', 'english', 'arabic', 'source_text', 'output_text'}


def content_values(value, active=False):
    if isinstance(value, str):
        return [value] if active and value.strip() else []
    if isinstance(value, dict):
        return [text for key, item in value.items() for text in content_values(item, active or key in CONTENT_KEYS)]
    if isinstance(value, list):
        return [text for item in value for text in content_values(item, active)]
    return []


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def classify(body, headers, path, query):
    from access_control import load_access_data
    data = load_access_data()
    channel = body.get('team_channel') or query.get('team_channel', [''])[0]
    parts = path.split('/')
    batch = next((batch for batch in data.get('approval_batches', []) if len(parts) > 3 and parts[2] == 'approvals' and batch['id'] == parts[3]), None)
    if batch:
        channel = batch['channel_id']
    # The ledger contains digests, never the confidential documents themselves.
    ledger = data.get('confidential_content', {}).get(channel, {})
    marked = headers.get(b'x-confidential-document', b'false').lower() == b'true' or body.get('confidential') is True
    protected = marked or bool(batch and batch.get('confidential')) or any(digest(text) in ledger for text in content_values(body))
    return dict(channel=channel, confidential=protected, policy=data.get('inference_policy'))


def remember(context, values):
    if not context['confidential'] or not context.get('channel') or not values:
        return
    from access_control import DATA_LOCK, load_access_data, save_access_data
    with DATA_LOCK:
        data = load_access_data()
        ledger = data.setdefault('confidential_content', {}).setdefault(context['channel'], {})
        new = {digest(text): True for text in values if text.strip() and digest(text) not in ledger}
        if new:
            ledger.update(new)
            save_access_data(data)


def protect_upload(content, channel):
    """The same protected file stays protected if re-uploaded without a checkbox."""
    from inference import scope
    from access_control import DATA_LOCK, load_access_data, save_access_data
    context = scope()
    context['channel'] = channel
    key = 'file:' + hashlib.sha256(content).hexdigest()
    with DATA_LOCK:
        data = load_access_data()
        existing = data.get('confidential_content', {}).get(channel, {}).get(key)
        if existing or context.get('confidential'):
            context['confidential'] = True
            context.pop('route', None)
            if not existing:
                data.setdefault('confidential_content', {}).setdefault(channel, {})[key] = True
                save_access_data(data)


class InferenceGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        sensitive = path.startswith(('/api/enhance', '/api/translate', '/api/approvals/', '/api/bulk/')) or path in {'/api/analyze', '/api/detect-context', '/api/extract-upload', '/api/import-spreadsheet', '/api/regenerate'} or path.endswith('/refine-instructions')
        if scope['type'] != 'http' or not sensitive:
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        raw, body = b'', {}
        is_json = b'application/json' in headers.get(b'content-type', b'')
        if is_json:
            chunks = []
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                chunks.append(event.get('body', b''))
                if not event.get('more_body'):
                    break
            raw = b''.join(chunks)
            try:
                decoded = json.loads(raw)
                body = decoded if isinstance(decoded, dict) else {}
            except (ValueError, UnicodeError):
                pass
        delivered = False
        async def replay():
            nonlocal delivered
            if is_json and not delivered:
                delivered = True
                return {'type': 'http.request', 'body': raw, 'more_body': False}
            return await receive()
        from oracledb import Error as OracleError
        from starlette.responses import JSONResponse
        try:
            context = await run_in_threadpool(classify, body, headers, scope['path'], parse_qs(scope.get('query_string', b'').decode()))
        except OracleError:
            return await JSONResponse({'detail': 'Application storage is temporarily unavailable. No AI request was sent.'}, status_code=503)(scope, replay, send)
        if context['confidential'] and body and context.get('channel'):
            # Persist classification before inference, including failed generations.
            # Only authenticated people with access to this channel may mark content.
            def remember_input():
                from access_control import current_user, require_channel_access, require_workspace_access
                from fastapi import HTTPException
                try:
                    user = current_user(headers.get(b'x-user-email', b'').decode(), headers.get(b'authorization', b'').decode())
                    require_workspace_access(user, 'rewrite')
                    require_channel_access(user, context['channel'])
                except HTTPException:
                    return
                remember(context, content_values(body))
            try:
                await run_in_threadpool(remember_input)
            except OracleError:
                return await JSONResponse({'detail': 'Could not save document classification. No AI request was sent.'}, status_code=503)(scope, replay, send)
        status, response_type, captured = 500, b'', bytearray()
        async def remember_response():
            values = content_values(body)
            try:
                if b'application/json' in response_type:
                    values.extend(content_values(json.loads(captured)))
                elif b'text/event-stream' in response_type:
                    deltas = []
                    for line in captured.decode().splitlines():
                        if line.startswith('data: '):
                            event = json.loads(line[6:])
                            if event.get('type') == 'delta':
                                deltas.append(event.get('text', ''))
                    if deltas:
                        values.append(''.join(deltas))
            except (ValueError, UnicodeError):
                pass
            await run_in_threadpool(remember, context, values)
        async def guarded_send(event):
            nonlocal status, response_type
            if event['type'] == 'http.response.start':
                status = event['status']
                response_type = dict(event['headers']).get(b'content-type', b'')
                if status < 400:
                    event['headers'] = [*event['headers'], (b'x-content-classification', b'confidential' if context['confidential'] else b'standard')]
            if event['type'] == 'http.response.body' and context['confidential'] and (b'application/json' in response_type or b'text/event-stream' in response_type):
                captured.extend(event.get('body', b''))
            if event['type'] == 'http.response.body' and not event.get('more_body') and status < 400 and context['confidential']:
                await remember_response()
            await send(event)
        with inference_scope(context):
            await self.app(scope, replay, guarded_send)
