"""Explicit storage selection. Oracle failures never fall back to stale local data."""
from pathlib import Path
import os

from dotenv import load_dotenv

from environment import load_environment
load_environment()


def oracle_enabled():
    mode = os.getenv('REWRITE_STORAGE_BACKEND', 'local').strip().lower()
    if mode not in {'local', 'oracle'}:
        raise ValueError('REWRITE_STORAGE_BACKEND must be local or oracle.')
    return mode == 'oracle'
