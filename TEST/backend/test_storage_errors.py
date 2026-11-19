import asyncio
import json
from types import SimpleNamespace
import unittest

from main import storage_unavailable


class StorageErrorTests(unittest.TestCase):
    def response(self, code):
        # Never expose Oracle messages, SQL, account names or content to clients.
        error = Exception(SimpleNamespace(code=code, message='PRIVATE DATABASE DETAILS'))
        return asyncio.run(storage_unavailable(None, error))

    def test_quota_exhaustion_explains_required_administrator_action(self):
        response = self.response(1536)
        self.assertEqual(response.status_code, 503)
        detail = json.loads(response.body)['detail']
        self.assertIn('storage allowance is full', detail)
        self.assertIn('increase the Oracle storage quota', detail)
        self.assertNotIn('PRIVATE', detail)

    def test_other_database_errors_remain_private(self):
        response = self.response(12541)
        self.assertEqual(response.status_code, 503)
        self.assertIn('temporarily unavailable', json.loads(response.body)['detail'])
        self.assertNotIn('PRIVATE', response.body.decode())
