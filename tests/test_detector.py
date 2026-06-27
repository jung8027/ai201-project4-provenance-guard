"""Unit tests for the detection signals and confidence scoring (detector.py).

These are deterministic and make no network/API calls — they exercise the stylometric
signal, the signal-combination logic, and the attribution mapping. (The live two-signal
calibration harness that does call Groq lives in test_scoring.py.)

Run: python -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import detector

UNIFORM = (
    "Effective time management is a critical skill in the modern workplace. First, it is "
    "important to prioritize tasks based on their relative urgency. Second, it is essential "
    "to eliminate distractions in order to maintain focus. Third, it is beneficial to take "
    "regular breaks to sustain productivity. Finally, it is advisable to review progress."
)
BURSTY = (
    "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the "
    "broth was fine but they put WAY too much sodium in it and i was thirsty for like three "
    "hours after. probably wont go back unless someone drags me there"
)
SHORT = "Nice day. Went out."


class TestStylometricSignal(unittest.TestCase):
    def test_score_in_range_and_metrics_present(self):
        r = detector.stylometric_signal(UNIFORM)
        self.assertGreaterEqual(r["style_score"], 0.0)
        self.assertLessEqual(r["style_score"], 1.0)
        for key in ("sentence_stdev", "sentence_cv", "type_token_ratio",
                    "punct_density", "n_sentences", "n_words"):
            self.assertIn(key, r["metrics"])

    def test_uniform_text_scores_more_ai_like_than_bursty(self):
        uniform = detector.stylometric_signal(UNIFORM)["style_score"]
        bursty = detector.stylometric_signal(BURSTY)["style_score"]
        self.assertGreater(uniform, bursty)

    def test_short_text_flagged_unreliable(self):
        self.assertFalse(detector.stylometric_signal(SHORT)["reliable"])

    def test_long_text_flagged_reliable(self):
        self.assertTrue(detector.stylometric_signal(UNIFORM)["reliable"])


class TestCombineSignals(unittest.TestCase):
    def test_weighted_blend_when_signals_agree(self):
        # disagreement 0.2 (<0.4) -> no pull; 0.6*0.9 + 0.4*0.7 = 0.82
        out = detector.combine_signals(0.9, 0.7, style_reliable=True)
        self.assertAlmostEqual(out["p_ai"], 0.82, places=2)
        self.assertEqual(out["attribution"], "likely_ai")

    def test_disagreement_pulls_toward_uncertain(self):
        # raw blend for (0.9, 0.1) is 0.58; the pull must move it closer to 0.5
        out = detector.combine_signals(0.9, 0.1, style_reliable=True)
        self.assertLess(abs(out["p_ai"] - 0.5), abs(0.58 - 0.5))

    def test_unreliable_style_is_downweighted_toward_llm(self):
        reliable = detector.combine_signals(1.0, 0.0, style_reliable=True)["p_ai"]
        unreliable = detector.combine_signals(1.0, 0.0, style_reliable=False)["p_ai"]
        # With style down-weighted, the result leans harder on the (high) LLM score.
        self.assertGreater(unreliable, reliable)

    def test_output_shape(self):
        out = detector.combine_signals(0.5, 0.5)
        self.assertIn("p_ai", out)
        self.assertIn(out["attribution"], detector.config.VALID_ATTRIBUTIONS)
        self.assertGreaterEqual(out["p_ai"], 0.0)
        self.assertLessEqual(out["p_ai"], 1.0)


class TestScoreToAttribution(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(detector.score_to_attribution(0.95), "likely_ai")
        self.assertEqual(detector.score_to_attribution(0.80), "likely_ai")   # boundary inclusive
        self.assertEqual(detector.score_to_attribution(0.50), "uncertain")
        self.assertEqual(detector.score_to_attribution(0.30), "likely_human")  # boundary inclusive
        self.assertEqual(detector.score_to_attribution(0.05), "likely_human")


if __name__ == "__main__":
    unittest.main()
