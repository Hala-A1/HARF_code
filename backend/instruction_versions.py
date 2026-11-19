"""Durable instruction snapshots behind a repository boundary for later DB migration."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from threading import RLock

from fastapi import HTTPException

_LOCK = RLock()
_ROOT = Path(__file__).resolve().parents[1]


def version_repository(source_path):
    from storage_backend import oracle_enabled
    if oracle_enabled():
        from oracle_instructions import OracleInstructionVersions
        return OracleInstructionVersions(source_path)
    return InstructionVersionRepository(source_path)


def _digest(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.instruction-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class InstructionVersionRepository:
    """SQLite is the local durable store, not browser storage or process memory.

    The HTTP/UI contract uses channel, module and version, not storage paths.
    Another database adapter can implement this repository without changing UI.
    """
    def __init__(self, source_path):
        import access_control
        source_path = Path(source_path).resolve()
        configured = os.getenv('INSTRUCTION_VERSIONS_DB')
        # Isolate temporary/test instruction trees even when callers only patch
        # the prompt directory. Never write test snapshots to the live history.
        data_path = Path(access_control.DATA_FILE).resolve()
        prompt_root = Path(access_control.CHANNEL_PROMPT_DIR).resolve()
        if data_path != Path(access_control.__file__).with_name('access-control.json').resolve():
            storage_root = data_path.parent
        elif not prompt_root.is_relative_to(_ROOT):
            storage_root = prompt_root.parent
        else:
            storage_root = data_path.parent if source_path.is_relative_to(_ROOT) else source_path.parent
        default = storage_root / 'instruction-versions.sqlite3'
        self.database = Path(configured) if configured else default

    @contextmanager
    def transaction(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            connection = sqlite3.connect(self.database, timeout=30)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute('PRAGMA synchronous=FULL')
                connection.execute('''CREATE TABLE IF NOT EXISTS instruction_versions (
                    channel_id TEXT NOT NULL, module_id TEXT NOT NULL, version INTEGER NOT NULL,
                    content TEXT NOT NULL, checksum TEXT NOT NULL, created_at TEXT NOT NULL,
                    actor_name TEXT NOT NULL, actor_email TEXT, actor_role TEXT NOT NULL,
                    action TEXT NOT NULL, note TEXT NOT NULL, restored_from INTEGER,
                    characters INTEGER NOT NULL, words INTEGER NOT NULL, lines INTEGER NOT NULL,
                    PRIMARY KEY (channel_id, module_id, version))''')
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _latest(connection, channel, module):
        return connection.execute('SELECT * FROM instruction_versions WHERE channel_id=? AND module_id=? ORDER BY version DESC LIMIT 1', (channel, module)).fetchone()

    def _append(self, connection, channel, module, content, actor, action, note='', restored_from=None):
        current = self._latest(connection, channel, module)
        version = current['version'] + 1 if current else 1
        connection.execute('''INSERT INTO instruction_versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                           (channel, module, version, content, _digest(content),
                            datetime.now(timezone.utc).isoformat(), actor['name'], actor.get('email'), actor['role'],
                            action, note, restored_from, len(content), len(content.split()), len(content.splitlines())))
        return self._latest(connection, channel, module)

    def _sync(self, connection, channel, module, path):
        content = path.read_text(encoding='utf-8')
        current = self._latest(connection, channel, module)
        if current is None or current['checksum'] != _digest(content):
            action = 'baseline' if current is None else 'external_update'
            actor = {'name': 'Existing instructions' if current is None else 'External file change', 'role': 'system'}
            current = self._append(connection, channel, module, content, actor, action,
                                   'Starting snapshot; earlier edits are not reconstructed.' if action == 'baseline'
                                   else 'Change detected outside the instruction editor; author is not recorded.')
        return current

    def current(self, channel, module, path, include_content=False):
        with self.transaction() as connection:
            row = self._sync(connection, channel, module, path)
            return dict(row) if include_content else self.public(row)

    def list(self, channel, module, path, offset=0, limit=20):
        with self.transaction() as connection:
            current = self._sync(connection, channel, module, path)
            # Content is deliberately excluded from history lists: B2B files
            # can be large. Fetch only one selected snapshot when requested.
            rows = connection.execute('SELECT channel_id,module_id,version,checksum,created_at,actor_name,actor_email,actor_role,action,note,restored_from,characters,words,lines FROM instruction_versions WHERE channel_id=? AND module_id=? ORDER BY version DESC LIMIT ? OFFSET ?', (channel, module, limit, offset)).fetchall()
            return {'versions': [dict(row) for row in rows], 'current_version': current['version'],
                    'total': current['version'], 'offset': offset, 'limit': limit}

    def get(self, channel, module, path, version):
        with self.transaction() as connection:
            self._sync(connection, channel, module, path)
            row = connection.execute('SELECT * FROM instruction_versions WHERE channel_id=? AND module_id=? AND version=?', (channel, module, version)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='Instruction version was not found.')
            return dict(row)

    def save(self, channel, module, source_path, target_path, content, actor, expected_version=None, note='', restored_from=None):
        with _LOCK:
            return self._save(channel, module, source_path, target_path, content, actor, expected_version, note, restored_from)

    def _save(self, channel, module, source_path, target_path, content, actor, expected_version=None, note='', restored_from=None):
        previous_target = None
        wrote = False
        try:
            with self.transaction() as connection:
                current = self._sync(connection, channel, module, source_path)
                if expected_version is not None and current['version'] != expected_version:
                    raise HTTPException(status_code=409, detail='This instruction file changed after you opened it. Reload the latest version before saving or restoring.')
                if current['checksum'] == _digest(content) and restored_from is None:
                    return {**self.public(current), 'unchanged': True}
                previous_target = target_path.read_text(encoding='utf-8') if target_path.exists() else None
                row = self._append(connection, channel, module, content, actor,
                                   'restore' if restored_from is not None else 'edit', note, restored_from)
                _atomic_write(target_path, content)
                wrote = True
                result = self.public(row)
            return result
        except BaseException:
            if wrote:
                if previous_target is None:
                    target_path.unlink(missing_ok=True)
                else:
                    _atomic_write(target_path, previous_target)
            raise

    @staticmethod
    def public(row):
        return {key: row[key] for key in row.keys() if key != 'content'}
