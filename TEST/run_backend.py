"""Run isolated backend tests from any working directory; never use production Oracle."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.chdir(ROOT)
# Imports may read real .env settings. Override storage/auth before importing tests.
os.environ.update(REWRITE_STORAGE_BACKEND='local', AUTH_PROVIDER='', AUTH_MODE='local',
                  DEVELOPER_MODE='false', MODEL_PROVIDER='mock')
# Legacy identity fixtures remain available only to isolated tests, never runtime.
sys.path.insert(0, str(ROOT / 'TEST/backend'))
from access_fixtures import DEMO_ACCESS_DATA
import access_control
access_control.DEFAULT_DATA = DEMO_ACCESS_DATA

if __name__ == '__main__':
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'test_*.py'
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'TEST/backend'), pattern=pattern)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
