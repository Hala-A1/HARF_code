"""Explicit Oracle connection for administration tools; never changes runtime storage."""
from contextlib import contextmanager
from pathlib import Path
import os

from dotenv import load_dotenv

from environment import ENV_FILE
CONFIG_FILE = ENV_FILE


def json_text_handler(cursor, metadata):
    """Keep IS JSON CLOBs as LOB text, not driver-decoded dictionaries/lists.

    python-oracledb 2+ otherwise decodes these columns automatically. Our stores
    deliberately retain exact JSON text and parse it at the repository boundary.
    Oracle documents this compatibility handler in its driver upgrade appendix.
    """
    if metadata.is_json:
        return cursor.var(metadata.type_code, arraysize=cursor.arraysize)


def configure_fetch(db):
    db.outputtypehandler = json_text_handler
    return db


def settings(password=None):
    load_dotenv(CONFIG_FILE, override=False)
    user = os.getenv('ORACLE_USER', 'REWRITE_APP').strip()
    if user.upper() != 'REWRITE_APP':
        raise ValueError('Use REWRITE_APP, never SYSTEM or SYS, for application data.')
    result = dict(user=user, dsn=os.getenv('ORACLE_DSN', 'localhost:1521/FREEPDB1').strip(),
                  password=password or os.getenv('ORACLE_PASSWORD'))
    if not result['password']:
        raise ValueError('Enter the database password in the local tool prompt, or configure the project root .env.')
    return result


@contextmanager
def connection(password=None):
    import oracledb
    db = oracledb.connect(**settings(password), tcp_connect_timeout=10)
    configure_fetch(db)
    db.call_timeout = 30000
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT SYS_CONTEXT('USERENV','SESSION_USER'), SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
            if cursor.fetchone() != ('REWRITE_APP', 'REWRITE_APP'):
                raise ValueError('The connection must use the REWRITE_APP account and schema.')
        yield db
    finally:
        db.rollback()
        db.close()
