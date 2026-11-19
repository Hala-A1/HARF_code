"""Cross-worker rolling-minute budgets for every outbound LLM HTTP attempt.

Oracle uses a dedicated runtime-state row; local mode uses an atomic SQLite row.
Waiting happens outside database transactions. Monthly logical quotas are separate.
"""
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import timezone
import json
import math
import os
from pathlib import Path
import sqlite3
from threading import BoundedSemaphore
import time

from dotenv import dotenv_values
from environment import ENV_FILE, configuration_change
import httpx

_CHANNEL = ContextVar('llm_rate_channel', default=None)
_WAITERS = BoundedSemaphore(8)
_ENV_NAMES = ('LLM_REQUESTS_PER_MINUTE', 'LLM_CHANNEL_REQUESTS_PER_MINUTE', 'LLM_CHANNEL_RATE_LIMITS')


class LLMRateLimitError(RuntimeError):
    code = 'llm_rate_limit'
    status_code = 429


@contextmanager
def channel_scope(channel):
    token = _CHANNEL.set(channel)
    try:
        yield
    finally:
        _CHANNEL.reset(token)


def request_channel():
    from generation_context import current_generation
    context = current_generation()
    return context.channel if context else _CHANNEL.get()


def environment_path():
    return Path(os.getenv('LLM_RATE_ENV_FILE') or ENV_FILE)


def positive(value):
    value = int(value)
    if not 1 <= value <= 5000:
        raise ValueError('LLM limits must be whole numbers from 1 to 5,000.')
    return value


def defaults():
    local = dotenv_values(environment_path()) if environment_path().exists() else {}
    def setting(key, fallback):
        return local.get(key) or os.getenv(key, fallback)
    channels = json.loads(setting('LLM_CHANNEL_RATE_LIMITS', '{}'))
    return dict(application=positive(setting('LLM_REQUESTS_PER_MINUTE', '50')),
                default_channel=positive(setting('LLM_CHANNEL_REQUESTS_PER_MINUTE', '50')),
                channels={str(key): positive(value) for key, value in channels.items()})


class LLMRateLimits:
    @contextmanager
    def state(self):
        from storage_backend import oracle_enabled
        if oracle_enabled():
            from oracle_runtime import transaction, text
            import oracledb
            with transaction() as db, db.cursor() as cursor:
                cursor.execute("SELECT access_json FROM genai_harf_runtime_state WHERE state_id='llm_rate' FOR UPDATE")
                row = cursor.fetchone()
                if row is None:
                    # Serialize first creation across processes without schema DDL.
                    cursor.execute("SELECT migration_id FROM genai_harf_runtime_state WHERE state_id='access' FOR UPDATE")
                    if cursor.fetchone() is None:
                        raise RuntimeError('Application storage has not been initialized.')
                    cursor.execute("SELECT access_json FROM genai_harf_runtime_state WHERE state_id='llm_rate' FOR UPDATE")
                    row = cursor.fetchone()
                    if row is None:
                        cursor.execute("INSERT INTO genai_harf_runtime_state(state_id,revision,migration_id,baseline_at,access_json) SELECT 'llm_rate',1,migration_id,baseline_at,'{}' FROM genai_harf_runtime_state WHERE state_id='access'")
                state = json.loads(text(row[0])) if row else {}
                cursor.execute('SELECT SYS_EXTRACT_UTC(SYSTIMESTAMP) FROM dual')
                state['_clock'] = cursor.fetchone()[0].replace(tzinfo=timezone.utc).timestamp()
                yield state
                state.pop('_clock', None)
                cursor.setinputsizes(payload=oracledb.DB_TYPE_CLOB)
                cursor.execute("UPDATE genai_harf_runtime_state SET access_json=:payload,revision=revision+1,updated_at=SYSTIMESTAMP WHERE state_id='llm_rate'",payload=json.dumps(state))
            return
        import access_control
        path = Path(os.getenv('LLM_RATE_DB') or Path(access_control.DATA_FILE).with_name('llm-rate-limits.sqlite3'))
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=10)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS llm_rate (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM llm_rate WHERE id=1').fetchone()
            state = json.loads(row[0]) if row else {}
            yield state
            db.execute('INSERT INTO llm_rate VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (json.dumps(state),))

    @staticmethod
    def config(state):
        return state.get('settings') or defaults()

    @staticmethod
    def events(state, now):
        state['events'] = [event for event in state.get('events', []) if event[0] > now - 60]
        return state['events']

    def reserve(self, channel, now=None):
        """Return wait seconds, or consume both application and channel slots."""
        with self.state() as state:
            now = state.get('_clock', time.time()) if now is None else now
            config = self.config(state)
            events = self.events(state, now)
            mine = [event for event in events if event[1] == channel]
            cap = config['channels'].get(channel, config['default_channel'])
            waits = []
            if len(events) >= config['application']:
                waits.append(events[-config['application']][0] + 60 - now)
            if len(mine) >= cap:
                waits.append(mine[-cap][0] + 60 - now)
            if waits:
                return max(waits)
            events.append([now, channel])
            return 0

    def summary(self):
        with self.state() as state:
            config = self.config(state)
            events = self.events(state, state.get('_clock', time.time()))
            used = {}
            for _, channel in events:
                key = channel or 'unassigned'
                used[key] = used.get(key, 0) + 1
            return {**config, 'application_used': len(events), 'channel_used': used,
                    'window_seconds': 60, 'environment_file': environment_path().name,
                    'counting_rule': 'Every outbound LLM attempt counts, including generation, translation, retries, repairs, context detection, guideline checks, instruction enhancement and image OCR. Calls wait briefly when capacity is full. Monthly user allocations are separate.'}

    @configuration_change
    def update(self, application, channel, channel_limit, actor):
        from datetime import datetime, timezone
        from instruction_versions import _atomic_write
        application, channel_limit = positive(application), positive(channel_limit)
        path = environment_path()
        old = path.read_text(encoding='utf-8') if path.exists() else None
        written = False
        try:
            with self.state() as state:
                config = self.config(state)
                config = {**config, 'application': application, 'channels': {**config['channels'], channel: channel_limit}}
                values = dict(zip(_ENV_NAMES, [str(application), str(config['default_channel']), json.dumps(config['channels'],sort_keys=True)]))
                local = dotenv_values(path) if path.exists() else {}
                values['LLM_RATE_LIMIT_MAX_WAIT_SECONDS'] = local.get('LLM_RATE_LIMIT_MAX_WAIT_SECONDS') or os.getenv('LLM_RATE_LIMIT_MAX_WAIT_SECONDS', '120')
                from environment import updated_content
                content = updated_content(path, values)
                _atomic_write(path, content)
                written = True
                state['settings'] = config
                # Retain a bounded settings audit without storing source/generated content.
                state['changes'] = [*state.get('changes', []), dict(at=datetime.now(timezone.utc).isoformat(),actor=actor.get('email'),application=application,channel=channel,channel_limit=channel_limit)][-100:]
            os.environ.update(values)
        except BaseException:
            if written:
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, old)
            raise
        return self.summary()


def acquire_slot(channel=None, *, max_wait=None):
    """Bound the queue so saturated LLM traffic cannot occupy all API workers."""
    store = LLMRateLimits()
    wait = store.reserve(channel)
    if not wait:
        return
    if not _WAITERS.acquire(blocking=False):
        raise LLMRateLimitError('AI request capacity is busy. Please wait a moment and retry.')
    try:
        local = dotenv_values(environment_path()) if environment_path().exists() else {}
        maximum = float(local.get('LLM_RATE_LIMIT_MAX_WAIT_SECONDS') or os.getenv('LLM_RATE_LIMIT_MAX_WAIT_SECONDS', '120')) if max_wait is None else max_wait
        deadline = time.monotonic() + maximum
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LLMRateLimitError(f'AI request capacity is busy. Retry in about {math.ceil(wait)} seconds.')
            time.sleep(min(wait + .01, remaining, 2))
            wait = store.reserve(channel)
            if not wait:
                return
    finally:
        _WAITERS.release()


class RateLimitedHttpClient(httpx.Client):
    def send(self, request, **kwargs):
        if request.method == 'POST' and request.url.path.rstrip('/').endswith(('/chat/completions', '/responses', '/completions')):
            try:
                acquire_slot(request_channel())
            except LLMRateLimitError as error:
                # A local capacity response must not trigger invisible SDK retries.
                return httpx.Response(429, request=request,
                    headers={'x-should-retry': 'false', 'Retry-After': '2'},
                    json={'error': {'code': error.code, 'message': str(error), 'type': 'rate_limit_error'}})
        return super().send(request, **kwargs)
