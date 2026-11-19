import tempfile
import unittest
from pathlib import Path
from structure_retrieval import sections, select_instructions, document_segments


class StructureRetrievalTests(unittest.TestCase):
    def test_headings_and_fenced_text(self):
        result = sections("# Rules\nKeep facts.\n## Examples\n```text\n# Not a heading\n```\n## Output\nFinal")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1]['path'], 'Rules > Examples')
        self.assertIn('# Not a heading', result[1]['text'])

    def test_examples_keep_rules_and_full_language_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.md'
            path.write_text('# Rules\nNever invent claims.\n### Example 1\n#### Before\nRenewal account\n#### After\nRenewal confirmed\n#### Arabic\nتم التجديد\n### Example 2\nRoaming travel holiday', encoding='utf-8')
            text, report = select_instructions(path, 'renewal account', examples=True, limit=1)
            self.assertIn('Never invent claims', text)
            self.assertIn('تم التجديد', text)
            self.assertNotIn('Roaming', text)
            self.assertEqual(report['selected_examples'], 1)
            _, cached = select_instructions(path, 'renewal account', examples=True)
            self.assertTrue(cached['cache_hit'])
            path.write_text('# Rules\nNew mandatory rule.', encoding='utf-8')
            text, fresh = select_instructions(path, 'renewal account', examples=True)
            self.assertIn('New mandatory rule', text)
            self.assertNotEqual(report['version'], fresh['version'])
            self.assertFalse(fresh['cache_hit'])

    def test_no_match_preserves_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'guide.md'
            path.write_text('# Mandatory\nKeep approved terms.\n### Example 1\nRoaming', encoding='utf-8')
            text, report = select_instructions(path, 'unrelated', examples=True)
            self.assertIn('Keep approved terms', text)
            self.assertEqual(report['selected_examples'], 0)
            full, _ = select_instructions(path, 'unrelated', examples=False)
            self.assertIn('Roaming', full)

    def test_document_coverage_and_boundaries(self):
        text = '# Scope\n' + 'A' * 700 + '\n## Exceptions\n' + 'B' * 700 + '\n## Penalties\nFINAL OBLIGATION'
        parts = document_segments(text, limit=1200)
        self.assertTrue(all(len(part) <= 1200 for part in parts))
        joined = '\n'.join(parts)
        self.assertIn('FINAL OBLIGATION', joined)
        self.assertIn('Source heading: Scope > Exceptions', joined)
        self.assertEqual(joined.count('A'), 702)  # includes A in FINAL and OBLIGATION
        self.assertEqual(joined.count('B'), 701)  # includes B in OBLIGATION
