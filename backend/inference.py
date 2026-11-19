"""Two trusted gateways, administrator-owned model policy and fail-closed routing.

Credentials stay in environment variables. Model rows never contain endpoints or keys.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from types import SimpleNamespace as NS
from urllib.parse import urlsplit
import json
import os
import ssl

from openai import OpenAI, omit
from stream_errors import StreamFailure

_SCOPE = ContextVar('inference_scope', default=None)


class InferencePolicyError(ValueError):
    code = 'inference_policy'
    status_code = 409


def scope():
    return _SCOPE.get() or {}


@contextmanager
def inference_scope(value):
    token = _SCOPE.set(value)
    try:
        yield
    finally:
        _SCOPE.reset(token)


def confidential():
    return bool(scope().get('confidential'))


def live_enabled():
    return os.getenv('MODEL_PROVIDER', '').lower() in {'live', 'azure_openai', 'litellm'}


def model_names(variable):
    raw = catalog_value(variable, '[]')
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise InferencePolicyError(f'{variable} must be a JSON array of deployment names.')
    return list(dict.fromkeys(value))


def catalog_value(name, fallback=''):
    """Optional shared env file supports live catalog edits without secret reloads."""
    from pathlib import Path
    from dotenv import dotenv_values
    path = os.getenv('INFERENCE_CATALOG_ENV_FILE')
    local = dotenv_values(Path(path)) if path else {}
    return local.get(name) if local.get(name) is not None else os.getenv(name, fallback)


def bootstrap():
    from ai_service import copywriter_settings
    from platform_policy import settings
    inputs = settings()
    cloud = model_names('AZURE_EXPLICIT_DEPLOYMENTS')
    if not cloud and copywriter_settings().get('AZURE_OPENAI_MODEL'):
        cloud = [copywriter_settings()['AZURE_OPENAI_MODEL']]
    local = model_names('ON_PREM_EXPLICIT_MODELS')
    rows = [dict(id=f'{gateway}:{name}', name=name, upstream=name, gateway=gateway,
                 enabled=True, vision=gateway == 'cloud' and name in {'gpt-5.1', 'gpt-4.1', 'gpt-4o'}, temperature=None,
                 max_tokens=int(catalog_value('DEFAULT_MAX_TOKENS', '4096')),
                 max_input_tokens=inputs['model_input_token_limits'].get(f'{gateway}:{name}', inputs['default_max_input_tokens']))
            for gateway, names in [('cloud', cloud), ('onprem', local)] for name in names]
    return dict(models=rows, default_model=rows[0]['id'] if rows else '',
                confidential_model=f'onprem:{local[0]}' if local else '', channels={}, revision=0)


def _sync_catalog(data):
    """Three-way merge: update configuration defaults, preserve admin overrides."""
    source = bootstrap()
    saved = deepcopy(data.get('inference_policy') or source)
    before = deepcopy(saved)
    previous = {row['id']: row for row in data.get('inference_catalog_snapshot', {}).get('models', [])}
    source_rows = {row['id']: row for row in source['models']}
    by_id = {row['id']: row for row in saved['models']}
    for identity, row in source_rows.items():
        if identity not in by_id:
            saved['models'].append(deepcopy(row))
        elif identity in previous:
            existing = by_id[identity]
            for field, value in row.items():
                if existing.get(field) == previous[identity].get(field):
                    existing[field] = value
    for identity in previous.keys() - source_rows.keys():
        if identity in by_id:
            by_id[identity]['enabled'] = False
    from platform_policy import settings
    inputs = settings()
    for row in saved['models']:
        row['max_input_tokens'] = inputs['model_input_token_limits'].get(row['id'], row.get('max_input_tokens', inputs['default_max_input_tokens']))
    # Keep explicit routing selections. A removed/disabled selected model must
    # fail closed until the admin chooses a replacement; never switch gateways.
    if saved != before:
        saved['revision'] = before.get('revision', 0) + 1
    data['inference_policy'] = deepcopy(saved)
    data['inference_catalog_snapshot'] = source
    return deepcopy(saved)


def policy(data=None):
    if data is not None:
        return _sync_catalog(data)
    from access_control import DATA_LOCK, load_access_data, save_access_data
    with DATA_LOCK:
        data = load_access_data()
        before = (deepcopy(data.get('inference_policy')), deepcopy(data.get('inference_catalog_snapshot')))
        result = _sync_catalog(data)
        if before != (data['inference_policy'], data['inference_catalog_snapshot']):
            save_access_data(data)
        return result


def connection(gateway):
    if os.getenv('INFERENCE_CONNECTION_SOURCE', 'environment') != 'environment':
        raise InferencePolicyError('This application supports environment-owned inference connections only.')
    prefix = 'APIM' if gateway == 'cloud' else 'LITELLM'
    base = os.getenv(f'{prefix}_BASE_URL', '').rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise InferencePolicyError(f'Configure a valid HTTPS {prefix}_BASE_URL without credentials or query parameters.')
    protocol = os.getenv(f'{prefix}_API_TYPE', 'responses' if gateway == 'cloud' else 'chat_completions')
    required = 'responses' if gateway == 'cloud' else 'chat_completions'
    if protocol != required:
        raise InferencePolicyError(f'{gateway} must use {required}.')
    key = os.getenv(f'{prefix}_API_KEY', '')
    if not key:
        raise InferencePolicyError(f'Configure {prefix}_API_KEY in the environment.')
    header = os.getenv('APIM_AUTH_HEADER', 'api-key') if gateway == 'cloud' else 'Authorization'
    if not header.replace('-', '').isalnum():
        raise InferencePolicyError('The inference authentication header is invalid.')
    style = os.getenv('APIM_API_STYLE', 'azure')
    if gateway == 'cloud' and style not in {'azure', 'openai'}:
        raise InferencePolicyError('APIM_API_STYLE must be azure or openai.')
    version = os.getenv('APIM_API_VERSION', '') if gateway == 'cloud' and style == 'azure' else ''
    if gateway == 'cloud' and os.getenv('APIM_API_STYLE', 'azure') == 'azure' and not version:
        raise InferencePolicyError('Azure Responses requires APIM_API_VERSION.')
    return dict(base=base, key=key, header=header, version=version, protocol=protocol)


def resolve():
    context = scope()
    if context.get('route'):
        return context['route']
    settings = deepcopy(context.get('policy')) if context.get('policy') else policy()
    key = settings['confidential_model'] if confidential() else settings.get('channels', {}).get(context.get('channel'), settings['default_model'])
    row = next((row for row in settings['models'] if row['id'] == key and row['enabled']), None)
    if row is None:
        raise InferencePolicyError('No enabled on-premise model is assigned to confidential documents. Contact the super admin.' if confidential() else 'No enabled model is assigned. Contact the super admin.')
    if confidential() and row['gateway'] != 'onprem':
        raise InferencePolicyError('Confidential content is restricted to the on-premise gateway. Cloud fallback is blocked.')
    allowed = model_names('AZURE_EXPLICIT_DEPLOYMENTS' if row['gateway'] == 'cloud' else 'ON_PREM_EXPLICIT_MODELS')
    if allowed and row['upstream'] not in allowed:
        raise InferencePolicyError('This model is outside the environment deployment allowlist.')
    route = {**row, **connection(row['gateway']), 'confidential': confidential(), 'revision': settings['revision']}
    if context:
        context['route'] = route
    return route


def route_identity():
    if live_enabled() or confidential():
        row = resolve()
        return (row['gateway'], row['base'], row['upstream'], row['protocol'], row['version'],
                row['revision'], row['max_tokens'], row['temperature'], confidential())
    from ai_service import copywriter_settings
    values = copywriter_settings()
    return ('legacy', values.get('AZURE_OPENAI_ENDPOINT'), values.get('AZURE_OPENAI_MODEL'))


def attribution():
    if not live_enabled() and not confidential():
        return {'confidential': False}
    row = resolve()
    return dict(confidential=confidential(), inference_gateway=row['gateway'], inference_model=row['upstream'])


def response_input(messages):
    result = []
    for message in messages:
        content = message['content']
        if isinstance(content, list):
            content = [dict(type='input_text', text=item['text']) if item['type'] == 'text' else
                       dict(type='input_image', image_url=item['image_url']['url'], detail=item['image_url'].get('detail', 'auto')) for item in content]
        result.append({'role': message['role'], 'content': content})
    return result


def choice(text='', finish=None):
    return NS(choices=[NS(message=NS(content=text), delta=NS(content=text), finish_reason=finish)])


class ResponseStream:
    def __init__(self, stream):
        self.stream, self.reported = stream, False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self.reported:
            from token_usage import record
            record(None)
        self.stream.close()

    def __iter__(self):
        for event in self.stream:
            if event.type == 'response.output_text.delta':
                yield choice(event.delta)
            elif event.type == 'response.completed':
                from token_usage import record, field
                record(field(field(event, 'response'), 'usage'))
                self.reported = True
                yield choice(finish='stop')
                return
            elif event.type in {'response.failed', 'error'}:
                raise StreamFailure('server_error')
            elif event.type == 'response.incomplete':
                yield choice(finish='length')
                return
        raise StreamFailure('stream_disconnected')


class RoutedClient:
    """Chat-shaped adapter keeps component validation, streaming and OCR intact."""
    def __init__(self, route=None, sdk=None):
        self.route = route or resolve()
        if sdk is None:
            from llm_rate_limits import RateLimitedHttpClient
            row = self.route
            auth = 'Bearer ' + row['key'] if row['header'].lower() == 'authorization' else row['key']
            headers = {row['header']: auth}
            if row['header'].lower() != 'authorization':
                headers['Authorization'] = omit
            sdk = OpenAI(api_key=row['key'], base_url=row['base'],
                         default_headers=headers,
                         default_query={'api-version': row['version']} if row['version'] else {},
                         timeout=float(os.getenv('TIMEOUT_SECONDS', '120')), max_retries=0,
                         http_client=RateLimitedHttpClient(follow_redirects=False, verify=ssl.create_default_context()))
        self.sdk = sdk
        self.chat = NS(completions=NS(create=self.create))

    def with_options(self, **options):
        return RoutedClient(self.route, self.sdk.with_options(**options))

    def close(self):
        self.sdk.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def create(self, *, model, messages, stream=False, response_format=None, **options):
        row = self.route
        if confidential() and row['gateway'] != 'onprem':
            raise InferencePolicyError('Confidential content cannot be sent to a cloud model.')
        images = any(isinstance(m['content'], list) and any(p.get('type') == 'image_url' for p in m['content']) for m in messages)
        if images and not row['vision']:
            raise InferencePolicyError('The selected model is not approved for image reading. Ask the super admin to configure an on-premise vision model for confidential scans.' if confidential() else 'The selected model is not approved for image reading. Ask the super admin to enable a supported vision model.')
        common = dict(model=row['upstream'], stream=stream)
        if row['header'].lower() != 'authorization':
            common['extra_headers'] = {'Authorization': omit}
        if row['temperature'] is not None:
            common['temperature'] = row['temperature']
        from input_tokens import enforce
        enforce(messages, row['upstream'], response_format=response_format, model_id=row.get('id'), maximum=row.get('max_input_tokens'))
        if row['protocol'] == 'chat_completions':
            from token_usage import MeteredStream, record, field
            if stream:
                common['stream_options'] = {'include_usage': True}
            response = self.sdk.chat.completions.create(**common, messages=messages, max_tokens=row['max_tokens'],
                **({'response_format': response_format} if response_format else {}))
            if stream:
                return MeteredStream(response)
            record(field(response, 'usage'))
            return response
        result = self.sdk.responses.create(**common, input=response_input(messages), max_output_tokens=row['max_tokens'], store=False,
            **({'text': {'format': response_format}} if response_format else {}))
        if stream:
            return ResponseStream(result)
        from token_usage import record, field
        record(field(result, 'usage'))
        if result.status != 'completed':
            raise StreamFailure('max_output_tokens' if result.status == 'incomplete' else 'server_error')
        if not result.output_text.strip():
            raise StreamFailure('empty_output')
        return choice(result.output_text, 'stop')
