import unittest
from unittest.mock import patch

from approval import approvals


class ApprovalQueueTests(unittest.TestCase):
    def test_submitted_queue_excludes_drafts_without_removing_archived_copies(self):
        batches = [{'id': status, 'status': status, 'items': [], 'events': []}
                   for status in ['draft', 'pending_layer_1', 'approved', 'rejected', 'returned_to_user']]
        with patch('approval.load_access_data', return_value={'approval_batches': batches}), patch('approval._can_view', return_value=True):
            user = {'role': 'channel_admin'}
            archived = approvals(user=user)['batches']
            queue = approvals(submitted_only=True, user=user)['batches']
            summary = approvals(submitted_only=True, summary=True, user=user)['batches']
        self.assertEqual(len(archived), 5)
        expected = ['pending_layer_1', 'approved', 'rejected', 'returned_to_user']
        self.assertEqual([batch['id'] for batch in queue], expected)
        self.assertEqual([batch['id'] for batch in summary], expected)


if __name__ == '__main__':
    unittest.main()
