from pathlib import Path
import tempfile
import unittest
from instruction_locations import instruction_relative_path, instruction_restore_path


class InstructionLocationTests(unittest.TestCase):
    def test_old_and_new_paths_map_to_the_same_current_location(self):
        new = 'instructions/channels/b2c/01_B2C_SYSTEM_INSTRUCTIONS.md'
        old = 'Copywriter/backend/prompt/channels/b2c/01_B2C_SYSTEM_INSTRUCTIONS.md'
        self.assertEqual(instruction_relative_path(old), new)
        self.assertEqual(instruction_relative_path(new), new)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(instruction_restore_path(root, old), root / new)

    def test_unrelated_and_escaping_paths_are_rejected(self):
        for value in ['backend/main.py', '/instructions/a.md', 'instructions/../.env',
                      'instructions/channels/../../.env', 'Copywriter/backend/prompt/../a.md',
                      'instructions/C:/secret.md', 'instructions/a\\b.md', 'instructions//a.md']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                instruction_relative_path(value)
