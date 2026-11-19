"""Persistent monthly allocations and atomic reservations for logical AI requests."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from inspect import signature
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from fastapi import HTTPException
from starlette.responses import StreamingResponse


def month_key():
    return datetime.now(timezone(timedelta(hours=4))).strftime('%Y-%m')


def principal(user):
    return user.get('directory_id') or 'local:' + user['email'].strip().casefold()


class RequestLimits:
    def __init__(self):
        import access_control
        self.path = Path(access_control.DATA_FILE).with_name('request-limits.sqlite3')

    @contextmanager
    def transaction(self):
        from storage_backend import oracle_enabled
        if oracle_enabled():
            from oracle_runtime import RepositoryConnection
            db = RepositoryConnection('quota')
            try:
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS channel_limits(channel TEXT PRIMARY KEY, monthly_limit INTEGER NOT NULL CHECK(monthly_limit>=0));
                CREATE TABLE IF NOT EXISTS user_limits(channel TEXT NOT NULL, principal TEXT NOT NULL, monthly_limit INTEGER NOT NULL CHECK(monthly_limit>=0), PRIMARY KEY(channel,principal));
                CREATE TABLE IF NOT EXISTS request_usage(id TEXT PRIMARY KEY, channel TEXT NOT NULL, principal TEXT NOT NULL, month TEXT NOT NULL, state TEXT NOT NULL, expires REAL NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS usage_lookup ON request_usage(channel,month,principal,state);
            ''')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def used(db, channel, identity=None):
        sql = "SELECT count(*) FROM request_usage WHERE channel=? AND month=? AND (state='completed' OR (state='pending' AND expires>?))"
        args = [channel, month_key(), time.time()]
        if identity is not None:
            sql += ' AND principal=?'
            args.append(identity)
        return db.execute(sql, args).fetchone()[0]

    @staticmethod
    def limit(db, channel, identity=None):
        if identity is None:
            row = db.execute('SELECT monthly_limit FROM channel_limits WHERE channel=?', (channel,)).fetchone()
        else:
            row = db.execute('SELECT monthly_limit FROM user_limits WHERE channel=? AND principal=?', (channel, identity)).fetchone()
        return row[0] if row is not None else None

    def summary(self, channel, users, viewer):
        with self.transaction() as db:
            cap = self.limit(db, channel)
            usage = self.used(db, channel)
            allocated = db.execute('SELECT coalesce(sum(monthly_limit),0) FROM user_limits WHERE channel=?', (channel,)).fetchone()[0]
            rows = []
            for user in users:
                identity = principal(user)
                limit = self.limit(db, channel, identity)
                if limit is None and cap is not None:
                    limit = 0
                used = self.used(db, channel, identity)
                rows.append({'email': user['email'], 'name': user['name'], 'role': user['role'],
                             'directory_linked': bool(user.get('directory_id')), 'active': user.get('active', True),
                             'limit': limit, 'used': used, 'remaining': None if limit is None else max(0, limit-used)})
            mine = next((row for row in rows if row['email'] == viewer['email']), None)
            return {'month': month_key(), 'timezone': 'Asia/Dubai', 'channel_id': channel,
                    'channel_limit': cap, 'channel_used': usage, 'allocated': allocated,
                    'unallocated': None if cap is None else max(0, cap-allocated),
                    'channel_remaining': None if cap is None else max(0, cap-usage), 'users': rows, 'mine': mine,
                    'counting_rule': 'One Generate, Regenerate, Translate or instruction-refinement/enhancement action counts as one request. A bilingual or bulk batch counts once. Failed requests, automatic repairs, context detection and guideline checks do not add requests.'}

    def set_channel(self, channel, limit):
        with self.transaction() as db:
            assigned = db.execute('SELECT coalesce(sum(monthly_limit),0) FROM user_limits WHERE channel=?', (channel,)).fetchone()[0]
            if limit < max(assigned, self.used(db, channel)):
                raise HTTPException(status_code=409, detail='The channel limit cannot be lower than its assigned user budgets or requests already used this month.')
            db.execute('INSERT INTO channel_limits VALUES(?,?) ON CONFLICT(channel) DO UPDATE SET monthly_limit=excluded.monthly_limit', (channel, limit))

    def set_user(self, channel, user, limit):
        identity = principal(user)
        with self.transaction() as db:
            cap = self.limit(db, channel)
            if cap is None:
                raise HTTPException(status_code=409, detail='The super admin must set the channel monthly limit before user budgets can be allocated.')
            others = db.execute('SELECT coalesce(sum(monthly_limit),0) FROM user_limits WHERE channel=? AND principal<>?', (channel, identity)).fetchone()[0]
            if others + limit > cap:
                raise HTTPException(status_code=409, detail='This allocation exceeds the channel monthly limit. Reduce another allocation or ask the super admin to increase the channel budget.')
            if limit < self.used(db, channel, identity):
                raise HTTPException(status_code=409, detail='The user limit cannot be lower than requests already used this month.')
            db.execute('INSERT INTO user_limits VALUES(?,?,?) ON CONFLICT(channel,principal) DO UPDATE SET monthly_limit=excluded.monthly_limit', (channel, identity, limit))

    def link_identity(self, email, directory_id):
        old = 'local:' + email.strip().casefold()
        with self.transaction() as db:
            for row in db.execute('SELECT * FROM user_limits WHERE principal=?', (old,)).fetchall():
                db.execute('INSERT OR IGNORE INTO user_limits VALUES(?,?,?)', (row['channel'], directory_id, row['monthly_limit']))
            db.execute('DELETE FROM user_limits WHERE principal=?', (old,))
            db.execute('UPDATE request_usage SET principal=? WHERE principal=?', (directory_id, old))

    def release_allocation(self, channel, user):
        """Reassignment frees the old channel budget, retaining its historical usage."""
        with self.transaction() as db:
            db.execute('DELETE FROM user_limits WHERE channel=? AND principal=?', (channel, principal(user)))

    def reserve(self, channel, user):
        identity = principal(user)
        with self.transaction() as db:
            cap = self.limit(db, channel)
            user_cap = self.limit(db, channel, identity)
            if cap is not None and self.used(db, channel) >= cap:
                raise HTTPException(status_code=429, detail='This channel has reached its monthly request limit. Contact the super admin or wait for the next calendar month (UAE time).')
            if user['role'] != 'super_admin':
                if cap is not None and user_cap is None:
                    user_cap = 0
                if user_cap is not None and self.used(db, channel, identity) >= user_cap:
                    raise HTTPException(status_code=429, detail='Your monthly request allocation is exhausted or not yet assigned. Contact your channel admin.')
            request_id = uuid4().hex
            db.execute('INSERT INTO request_usage VALUES(?,?,?,?,?,?,?)', (request_id, channel, identity, month_key(), 'pending', time.time()+3600, datetime.now(timezone.utc).isoformat()))
            return request_id

    def finish(self, request_id, success):
        with self.transaction() as db:
            db.execute("UPDATE request_usage SET state=? WHERE id=? AND state='pending'", ('completed' if success else 'released', request_id))


def monthly_request(function=None, *, admin_only=False):
    def decorate(target):
        parameters = signature(target)
        @wraps(target)
        def wrapped(*args, **kwargs):
            from access_control import require_channel_access, require_role
            values = parameters.bind(*args, **kwargs)
            values.apply_defaults()
            values = values.arguments
            user = values['user']
            request = values.get('request')
            channel = values.get('channel_id') or getattr(request, 'team_channel', None) or user.get('channel_id')
            require_channel_access(user, channel)
            if admin_only:
                require_role(user, 'super_admin', 'channel_admin')
            store = RequestLimits()
            reservation = store.reserve(channel, user)
            try:
                from llm_rate_limits import channel_scope
                with channel_scope(channel):
                    result = target(*args, **kwargs)
            except BaseException:
                store.finish(reservation, False)
                raise
            if isinstance(result, StreamingResponse):
                original = result.body_iterator
                async def counted_stream():
                    success, failed, done, buffer = False, False, False, ''
                    try:
                        async for chunk in original:
                            text = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                            buffer += text
                            while '\n\n' in buffer:
                                frame, buffer = buffer.split('\n\n', 1)
                                if frame.startswith('data: '):
                                    try:
                                        event = json.loads(frame[6:])
                                        if isinstance(event, dict) and event.get('type') == 'error':
                                            failed, success = True, False
                                        if isinstance(event, dict) and event.get('type') == 'done':
                                            done, success = True, not failed
                                    except ValueError:
                                        pass
                            yield chunk
                        success = done and not failed
                    finally:
                        store.finish(reservation, success)
                result.body_iterator = counted_stream()
                return result
            store.finish(reservation, True)
            return result
        return wrapped
    return decorate(function) if function is not None else decorate
