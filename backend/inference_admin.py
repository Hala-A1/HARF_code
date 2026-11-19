"""Authenticated model inventory and routing; connections are environment-owned."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from access_control import current_user, require_role, load_access_data, save_access_data, DATA_LOCK, record_activity
from inference import policy, connection, model_names, InferencePolicyError

router = APIRouter(prefix='/api/access/inference', tags=['models'])


class ModelRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=180, pattern=r'^[A-Za-z0-9_.:/-]+$')
    name: str = Field(min_length=1, max_length=120)
    upstream: str = Field(min_length=1, max_length=180, pattern=r'^[A-Za-z0-9_.:/-]+$')
    gateway: Literal['cloud', 'onprem']
    enabled: bool = True
    vision: bool = False
    max_tokens: int = Field(default=4096, strict=True, gt=0)
    max_input_tokens: int = Field(default=64000, strict=True, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    models: list[ModelRow] = Field(min_length=1, max_length=100)
    default_model: str
    confidential_model: str
    channels: dict[str, str] = Field(default_factory=dict, max_length=100)
    expected_revision: int = Field(ge=0)


@router.get('/policy')
def get_policy(user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    result = policy()
    connections = []
    for gateway in ['cloud', 'onprem']:
        try:
            configured = connection(gateway)
            connections.append(dict(gateway=gateway, configured=True, endpoint=configured['base'], protocol=configured['protocol']))
        except InferencePolicyError as error:
            connections.append(dict(gateway=gateway, configured=False, endpoint='', protocol='responses' if gateway == 'cloud' else 'chat_completions', message=str(error)))
    from inference import live_enabled
    from platform_policy import settings, environment_path
    return {**result, 'connections': connections, 'connection_source': 'environment', 'routing_active': live_enabled(),
            'default_max_input_tokens': settings()['default_max_input_tokens'], 'input_limits_environment_file': environment_path().name}


@router.put('/policy')
def put_policy(request: ModelPolicy, user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    rows = {row.id: row for row in request.models}
    if len(rows) != len(request.models):
        raise HTTPException(422, 'Model IDs must be unique.')
    def enabled(key):
        if key not in rows or not rows[key].enabled:
            raise HTTPException(422, 'Every selected default must refer to an enabled model.')
        return rows[key]
    enabled(request.default_model)
    if enabled(request.confidential_model).gateway != 'onprem':
        raise HTTPException(422, 'Confidential documents must use an enabled on-premise model.')
    for row in request.models:
        allowed = model_names('AZURE_EXPLICIT_DEPLOYMENTS' if row.gateway == 'cloud' else 'ON_PREM_EXPLICIT_MODELS')
        if allowed and row.upstream not in allowed:
            raise HTTPException(422, f'{row.name} is outside the environment deployment allowlist.')
    with DATA_LOCK:
        data = load_access_data()
        if policy(data)['revision'] != request.expected_revision:
            raise HTTPException(409, 'Model settings changed. Reload before saving.')
        channels = {channel['id'] for channel in data['channels'] if not channel.get('deleted_at')}
        for channel, key in request.channels.items():
            if channel not in channels:
                raise HTTPException(422, 'A selected channel no longer exists.')
            enabled(key)
        result = request.model_dump(exclude={'expected_revision'})
        result['revision'] = request.expected_revision + 1
        data['inference_policy'] = result
        record_activity(data, user, 'AI model routing updated', 'Updated model inventory and cloud/on-premise routing. Confidential cloud fallback remains blocked.', metadata={'revision': result['revision']})
        from platform_policy import settings, environment_path, write_settings
        from instruction_versions import _atomic_write
        path = environment_path()
        old = path.read_text(encoding='utf8') if path.exists() else None
        config = settings()
        config['model_input_token_limits'] = {row.id: row.max_input_tokens for row in request.models}
        try:
            write_settings(path, config)
            save_access_data(data)
        except BaseException:
            if old is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, old)
            raise
    return get_policy(user)


@router.post('/models/{model_id:path}/test')
def test_model(model_id: str, user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    row = next((row for row in policy()['models'] if row['id'] == model_id and row['enabled']), None)
    if not row:
        raise HTTPException(404, 'Enabled model not found.')
    # Never use documents, user input or confidential content for connection tests.
    try:
        from inference import RoutedClient, inference_scope
        allowed = model_names('AZURE_EXPLICIT_DEPLOYMENTS' if row['gateway'] == 'cloud' else 'ON_PREM_EXPLICIT_MODELS')
        if allowed and row['upstream'] not in allowed:
            raise InferencePolicyError('Model is outside the environment deployment allowlist.')
        route = {**row, **connection(row['gateway']), 'max_tokens': 256}
        with inference_scope({'channel': user.get('channel_id'), 'confidential': False}), RoutedClient(route) as client:
            client.with_options(timeout=20).chat.completions.create(model=row['upstream'], messages=[{'role': 'user', 'content': 'Connection test. Reply with OK only.'}])
        return {'status': 'connected', 'model': row['name'], 'gateway': row['gateway']}
    except Exception:
        raise HTTPException(502, 'Connection test failed. Check network/VPN, credentials, protocol and deployment name. No document was sent.') from None
