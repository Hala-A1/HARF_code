"""Output feedback with immutable context snapshots and channel-scoped administration."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from storage_lock import atomic_change

from access_control import (
    current_user, require_channel_access, require_workspace_access, require_role,
    DATA_LOCK, load_access_data, save_access_data, instruction_bundle,
)

router = APIRouter(prefix='/api/feedback', tags=['feedback'])
FEEDBACK_DB = Path(__file__).with_name('feedback.sqlite3')


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    from storage_backend import oracle_enabled
    if oracle_enabled():
        from oracle_runtime import RepositoryConnection
        return RepositoryConnection('feedback')
    db = sqlite3.connect(FEEDBACK_DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, workspace TEXT NOT NULL,
        user_email TEXT NOT NULL, user_name TEXT NOT NULL, fingerprint TEXT NOT NULL,
        rating TEXT NOT NULL CHECK(rating IN ('up','down')), reason TEXT NOT NULL,
        snapshot TEXT NOT NULL, instruction_manifest TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new', admin_note TEXT NOT NULL DEFAULT '',
        reviewed_by TEXT, reviewed_at TEXT,
        UNIQUE(user_email, channel_id, fingerprint))''')
    db.execute('CREATE INDEX IF NOT EXISTS feedback_channel_date ON feedback(channel_id, updated_at DESC)')
    db.commit()
    return db


class FeedbackSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_id: str = Field(min_length=1, max_length=80)
    workspace: Literal['rewrite'] = 'rewrite'
    task: str = Field(default='improve', min_length=1, max_length=100)
    source_text: str = Field(default='', max_length=2000000)
    output_text: str = Field(default='', max_length=200000)
    language: str = Field(default='', max_length=20)
    instructions: str = Field(default='', max_length=200000)
    request_title: str = Field(default='', max_length=300)
    content_channel: str = Field(default='Other', max_length=120)
    audience: str = Field(default='Unknown', max_length=120)
    product_type: str = Field(default='', max_length=160)
    filename: str = Field(default='', max_length=300)
    batch_id: str = Field(default='', max_length=80)
    item_id: str = Field(default='', max_length=80)
    version: str = Field(default='1', max_length=80)
    score: int | None = Field(default=None, ge=0, le=100)
    generated_at: str = Field(default='', max_length=80)
    generation_options: dict[str, str | int | float | bool | None] = Field(default_factory=dict, max_length=30)

    @model_validator(mode='after')
    def validate_output(self):
        if self.workspace == 'rewrite' and not self.output_text.strip():
            raise ValueError('Generate text before leaving feedback.')
        if len(json.dumps(self.generation_options, ensure_ascii=False)) > 20000:
            raise ValueError('Generation settings are too large.')
        return self


class FeedbackRequest(BaseModel):
    snapshot: FeedbackSnapshot
    rating: Literal['up', 'down']
    reason: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def reason_required(self):
        self.reason = self.reason.strip()
        if self.rating == 'down' and not self.reason:
            raise ValueError('Please explain the thumbs-down feedback.')
        if self.rating == 'up':
            self.reason = ''
        return self


class ReviewRequest(BaseModel):
    status: Literal['new', 'reviewed']
    admin_note: str = Field(default='', max_length=4000)
    expected_updated_at: str = Field(min_length=1, max_length=80)


def fingerprint(snapshot):
    # Keep this ordered list aligned with feedbackIdentity() in the web client.
    fields = [snapshot.channel_id, snapshot.workspace, snapshot.task, snapshot.source_text,
              snapshot.output_text, snapshot.language, snapshot.instructions, '',
              '', snapshot.filename, snapshot.batch_id, snapshot.item_id, snapshot.version]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def manifest(snapshot):
    captured = now()
    bundle = instruction_bundle(snapshot.channel_id, snapshot.content_channel,
                                snapshot.instructions + '\n' + snapshot.output_text[:12000])
    files = [{key: file[key] for key in ('module', 'filename', 'version')} for file in bundle['files']]
    return {'captured_at': captured, 'basis': 'Instruction versions at feedback submission, not a verified generation-time manifest.', 'files': files}


def notify_admins(entry):
    # No feedback reason or output is put in the shared activity feed.
    with DATA_LOCK:
        data = load_access_data()
        recipients = {u['email'] for u in data['users'] if u.get('active', True) and (
            u['role'] == 'channel_admin' and u.get('channel_id') == entry['channel_id'])}
        for email in recipients:
            data.setdefault('notifications', []).insert(0, {
                'id': uuid4().hex, 'recipient_email': email, 'title': 'New output feedback',
                'message': f"{entry['user_name']} left {'positive' if entry['rating'] == 'up' else 'negative'} feedback in {entry['channel_id'].upper()}.",
                'kind': 'output_feedback', 'feedback_id': entry['id'], 'channel_id': entry['channel_id'],
                'created_at': entry['updated_at'], 'read': False, 'urgent': False,
            })
        data['notifications'] = data.get('notifications', [])[:2000]
        save_access_data(data)


@router.post('')
@atomic_change
def submit_feedback(request: FeedbackRequest, user: dict = Depends(current_user)):
    snapshot = request.snapshot
    require_channel_access(user, snapshot.channel_id)
    require_workspace_access(user, snapshot.workspace)
    key = fingerprint(snapshot)
    captured_manifest = json.dumps(manifest(snapshot), ensure_ascii=False)
    timestamp = now()
    db = connect()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT * FROM feedback WHERE user_email=? AND channel_id=? AND fingerprint=?',
                               (user['email'], snapshot.channel_id, key)).fetchone()
            changed = not prior or prior['rating'] != request.rating or prior['reason'] != request.reason
            if not prior:
                identity = uuid4().hex
                db.execute('''INSERT INTO feedback
                    (id,channel_id,workspace,user_email,user_name,fingerprint,rating,reason,snapshot,instruction_manifest,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (identity, snapshot.channel_id, snapshot.workspace, user['email'], user['name'], key,
                     request.rating, request.reason, snapshot.model_dump_json(), captured_manifest, timestamp, timestamp))
            else:
                identity = prior['id']
                if changed:
                    db.execute("UPDATE feedback SET rating=?,reason=?,updated_at=?,status='new',reviewed_by=NULL,reviewed_at=NULL WHERE id=?",
                               (request.rating, request.reason, timestamp, identity))
    finally:
        db.close()
    entry = {'id': identity, 'channel_id': snapshot.channel_id, 'user_name': user['name'],
             'rating': request.rating, 'reason': request.reason, 'updated_at': timestamp}
    if changed:
        notify_admins(entry)
    return {'id': identity, 'rating': request.rating, 'reason': request.reason, 'fingerprint': key}


@router.get('/mine')
def own_feedback(channel_id: str, fingerprint: str = Query(pattern=r'^[a-f0-9]{64}$'), user: dict = Depends(current_user)):
    require_channel_access(user, channel_id)
    db = connect()
    try:
        row = db.execute("SELECT id,rating,reason FROM feedback WHERE workspace='rewrite' AND user_email=? AND channel_id=? AND fingerprint=?",
                         (user['email'], channel_id, fingerprint)).fetchone()
        return {'feedback': dict(row) if row else None}
    finally:
        db.close()


@router.get('')
def list_feedback(channel_id: str, rating: Literal['all','up','down'] = 'all', status: Literal['all','new','reviewed'] = 'all',
                  search: str = Query(default='', max_length=300), page: int = Query(default=1, ge=1), user: dict = Depends(current_user)):
    require_role(user, 'channel_admin')
    require_channel_access(user, channel_id)
    clauses, values = ["workspace='rewrite'", 'channel_id=?'], [channel_id]
    if rating != 'all':
        clauses.append('rating=?'); values.append(rating)
    if status != 'all':
        clauses.append('status=?'); values.append(status)
    if search.strip():
        clauses.append("(user_name LIKE ? ESCAPE '\\' OR user_email LIKE ? ESCAPE '\\' OR reason LIKE ? ESCAPE '\\' OR snapshot LIKE ? ESCAPE '\\')")
        pattern = '%' + search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        values.extend([pattern] * 4)
    where = ' AND '.join(clauses)
    db = connect()
    try:
        total = db.execute('SELECT COUNT(*) FROM feedback WHERE ' + where, values).fetchone()[0]
        rows = db.execute('''SELECT id,channel_id,workspace,user_name,user_email,rating,substr(reason,1,240) AS reason,
            created_at,updated_at,status,json_extract(snapshot,'$.task') AS task,
            json_extract(snapshot,'$.filename') AS filename,json_extract(snapshot,'$.language') AS language
            FROM feedback WHERE ''' + where + ' ORDER BY updated_at DESC,id DESC LIMIT 20 OFFSET ?', values + [(page-1)*20]).fetchall()
        stats = dict(db.execute("SELECT COUNT(*) AS total,COALESCE(SUM(rating='up'),0) AS positive,COALESCE(SUM(rating='down'),0) AS negative,COALESCE(SUM(status='new'),0) AS new FROM feedback WHERE workspace='rewrite' AND channel_id=?", (channel_id,)).fetchone())
        return {'items': [dict(row) for row in rows], 'total': total, 'page': page, 'page_size': 20, 'stats': stats}
    finally:
        db.close()


def admin_entry(db, feedback_id, user):
    require_role(user, 'channel_admin')
    row = db.execute('SELECT * FROM feedback WHERE id=?', (feedback_id,)).fetchone()
    if not row or row['workspace'] != 'rewrite':
        raise HTTPException(status_code=404, detail='Feedback was not found.')
    if user.get('channel_id') != row['channel_id']:
        raise HTTPException(status_code=404, detail='Feedback was not found.')
    require_channel_access(user, row['channel_id'])
    return row


@router.get('/{feedback_id}')
def feedback_detail(feedback_id: str, user: dict = Depends(current_user)):
    db = connect()
    try:
        entry = dict(admin_entry(db, feedback_id, user))
        entry['snapshot'] = json.loads(entry['snapshot'])
        entry['instruction_manifest'] = json.loads(entry['instruction_manifest'])
        entry.pop('fingerprint')
        return entry
    finally:
        db.close()


@router.patch('/{feedback_id}')
@atomic_change
def review_feedback(feedback_id: str, request: ReviewRequest, user: dict = Depends(current_user)):
    db = connect()
    try:
        admin_entry(db, feedback_id, user)
        with db:
            timestamp = now()
            changed = db.execute('UPDATE feedback SET status=?,admin_note=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=? AND updated_at=?',
                       (request.status, request.admin_note.strip(), user['email'], timestamp, timestamp, feedback_id, request.expected_updated_at)).rowcount
            if not changed:
                raise HTTPException(status_code=409, detail='This feedback changed. Reload it before saving your review.')
    finally:
        db.close()
    return feedback_detail(feedback_id, user)
