"""Unit tests for transparency-label generation (labeler.py).

Verifies each attribution maps to its distinct, correctly-worded variant and that an
unknown attribution is rejected. No network/API calls.

Run: python -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import labeler


class TestMakeLabel(unittest.TestCase):
    def test_ai_variant(self):
        text = labeler.make_label("likely_ai", 0.9)
        self.assertIn("AI-generated", text)
        self.assertTrue(text.startswith("🤖"))

    def test_human_variant(self):
        text = labeler.make_label("likely_human", 0.1)
        self.assertIn("human-written", text)
        self.assertTrue(text.startswith("✍️"))

    def test_uncertain_variant(self):
        text = labeler.make_label("uncertain", 0.5)
        self.assertIn("uncertain", text.lower())

    def test_three_variants_are_distinct(self):
        labels = {
            labeler.make_label("likely_ai"),
            labeler.make_label("uncertain"),
            labeler.make_label("likely_human"),
        }
        self.assertEqual(len(labels), 3)

    def test_unknown_attribution_raises(self):
        with self.assertRaises(ValueError):
            labeler.make_label("definitely_alien")


if __name__ == "__main__":
    unittest.main()
