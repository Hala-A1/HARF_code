"""Platform governance settings and age-based operational-log retention.

Saved work, approval evidence, feedback and instruction history are never purged.
"""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import logging
import json
import os
from pathlib import Path

from dotenv import dotenv_values
from environment import ENV_FILE
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from access_control import current_user, require_role

router = APIRouter(prefix='/api/access/platform-policy', tags=['platform governance'])
LOGGER = logging.getLogger(__name__)


def environment_path():
    return Path(os.getenv('PLATFORM_POLICY_ENV_FILE') or ENV_FILE)


def settings():
    local = dotenv_values(environment_path()) if environment_path().exists() else {}
    days = int(local.get('USER_LOG_RETENTION_DAYS') or os.getenv('USER_LOG_RETENTION_DAYS', '180'))
    if not 31 <= days <= 3650:
        raise ValueError('USER_LOG_RETENTION_DAYS must be between 31 and 3650.')
    maximum = int(local.get('DEFAULT_MAX_INPUT_TOKENS') or os.getenv('DEFAULT_MAX_INPUT_TOKENS') or local.get('LLM_MAX_INPUT_TOKENS') or '64000')
    if maximum <= 0:
        raise ValueError('DEFAULT_MAX_INPUT_TOKENS must be a positive whole number.')
    limits = json.loads(local.get('LLM_MODEL_INPUT_TOKEN_LIMITS') or os.getenv('LLM_MODEL_INPUT_TOKEN_LIMITS', '{}'))
    if not isinstance(limits, dict) or any(not isinstance(key, str) or not key or type(value) is not int or value <= 0 for key, value in limits.items()):
        raise ValueError('LLM_MODEL_INPUT_TOKEN_LIMITS must map model IDs to positive whole numbers.')
    return {'retention_days': days, 'default_max_input_tokens': maximum, 'model_input_token_limits': limits}


def write_settings(path, config):
    from instruction_versions import _atomic_write
    from environment import updated_content, CONFIG_LOCK
    with CONFIG_LOCK:
        _atomic_write(path, updated_content(path, {
            'USER_LOG_RETENTION_DAYS': config['retention_days'],
            'DEFAULT_MAX_INPUT_TOKENS': config['default_max_input_tokens'],
            'LLM_MODEL_INPUT_TOKEN_LIMITS': json.dumps(config['model_input_token_limits'], sort_keys=True),
        }))



def parse_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (ValueError, TypeError):
        return None


def prune(data, days, now):
    """Explicit allowlist: never traverse arbitrary nested saved-content fields."""
    cutoff = now - timedelta(days=days)
    counts = {}
    unknown = 0
    for collection, key in [('activity', 'timestamp'), ('notifications', 'created_at')]:
        kept = []
        for row in data.get(collection, []):
            at = parse_time(row.get(key))
            unknown += int(at is None)
            if at is None or at >= cutoff:
                kept.append(row)
        counts[collection] = len(data.get(collection, [])) - len(kept)
        if collection in data:
            data[collection] = kept
    # Daily buckets expire only when the complete UAE day is outside the window.
    day = cutoff.astimezone(timezone(timedelta(hours=4))).date().isoformat()
    counts['token_days'] = 0
    for buckets in data.get('token_usage', {}).get('channels', {}).values():
        for date in list(buckets):
            at = parse_time(date)
            if at is not None and date < day:
                del buckets[date]
                counts['token_days'] += 1
    metrics = data.get('performance_metrics', {}).get('buckets', {})
    counts['performance_buckets'] = 0
    for key, row in list(metrics.items()):
        if parse_time(row.get('day')) is not None and row['day'] < day:
            del metrics[key]
            counts['performance_buckets'] += 1
    return {**counts, 'undated_records_preserved': unknown, 'cutoff': cutoff.isoformat()}


def run_retention(*, force=False, now=None):
    from access_control import DATA_LOCK, load_access_data, save_access_data
    from request_limits import RequestLimits, month_key
    from llm_rate_limits import LLMRateLimits
    now = now or datetime.now(timezone.utc)
    with DATA_LOCK:
        data = load_access_data()
        previous = data.get('log_retention', {})
        last = parse_time(previous.get('last_run_at'))
        if not force and last and now - last < timedelta(hours=1):
            return previous
        config = settings()
        result = prune(data, config['retention_days'], now)
        # Keep current billing-month counters and any live reservations intact.
        with RequestLimits().transaction() as db:
            removed = db.execute("DELETE FROM request_usage WHERE created_at<? AND month<>? AND (state<>'pending' OR expires<?)",
                                 (result['cutoff'], month_key(), now.timestamp()))
            result['request_usage'] = removed.rowcount
        with LLMRateLimits().state() as rate:
            changes = rate.get('changes', [])
            rate['changes'] = [row for row in changes if (at := parse_time(row.get('at'))) is None or at >= parse_time(result['cutoff'])]
            result['rate_setting_logs'] = len(changes) - len(rate['changes'])
            LLMRateLimits.events(rate, now.timestamp())
        result.update(last_run_at=now.isoformat(), retention_days=config['retention_days'])
        data['log_retention'] = result
        save_access_data(data)
        return result


async def retention_worker():
    while True:
        job = asyncio.create_task(asyncio.to_thread(run_retention))
        try:
            await asyncio.shield(job)
        except asyncio.CancelledError:
            with suppress(Exception):
                await job
            raise
        except Exception as error:
            LOGGER.warning('Log retention did not complete type=%s', type(error).__name__)
        await asyncio.sleep(3600)


class PolicyUpdate(BaseModel):
    model_config = {'extra': 'forbid'}
    retention_days: int | None = Field(default=None, strict=True, ge=31, le=3650)


@router.get('')
def get_policy(user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    from access_control import load_access_data
    data = load_access_data()
    return {'retention_days': settings()['retention_days'], 'environment_file': environment_path().name,
            'last_cleanup': data.get('log_retention'),
            'expires': ['Activity logs', 'Notifications', 'Past-month request usage', 'Daily token usage', 'Daily contributor metrics', 'Rate-limit settings audit logs'],
            'preserves': ['Users and channels', 'Saved inputs, files and generated copies', 'Approval decisions and notes attached to saved copies', 'Feedback', 'Instructions and all instruction versions', 'Request allocations and model configuration']}


@router.put('')
def update_policy(request: PolicyUpdate, user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    from access_control import DATA_LOCK, load_access_data, save_access_data, record_activity
    from fastapi import HTTPException
    from instruction_versions import _atomic_write
    path = environment_path()
    written = False
    try:
        with DATA_LOCK:
            old = path.read_text(encoding='utf8') if path.exists() else None
            data = load_access_data()
            config = settings()
            if request.retention_days is None:
                raise HTTPException(422, 'Provide a retention period.')
            if request.retention_days is not None:
                config['retention_days'] = request.retention_days
            write_settings(path, config)
            written = True
            record_activity(data, user, 'Platform policy updated', f"Log retention: {config['retention_days']} days. Model token limits, saved content and instructions are preserved.")
            save_access_data(data)
    except BaseException:
        if written:
            if old is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, old)
        raise
    return get_policy(user)


@router.post('/cleanup')
def cleanup(user: dict = Depends(current_user)):
    require_role(user, 'super_admin')
    return run_retention(force=True)
