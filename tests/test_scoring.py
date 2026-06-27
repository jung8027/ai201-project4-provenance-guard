"""Milestone 4 calibration harness.

Runs deliberately chosen inputs through the full two-signal pipeline and prints both
individual signal scores alongside the combined confidence, so the scoring can be
inspected for meaningful variation. Run from the project root: `python tests/test_scoring.py`
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import detector

CASES = [
    ("clearly AI (formal essay)",
     "Artificial intelligence represents a transformative paradigm shift in modern "
     "society. It is important to note that while the benefits of AI are numerous, it is "
     "equally essential to consider the ethical implications. Furthermore, stakeholders "
     "across various sectors must collaborate to ensure responsible deployment."),
    ("clearly human (casual review)",
     "ok so i finally tried that new ramen place downtown and honestly? underwhelming. "
     "the broth was fine but they put WAY too much sodium in it and i was thirsty for "
     "like three hours after. my friend got the spicy version and said it was better. "
     "probably wont go back unless someone drags me there"),
    ("borderline: formal human writing",
     "The relationship between monetary policy and asset price inflation has been "
     "extensively studied in the literature. Central banks face a fundamental tension "
     "between their mandate for price stability and the unintended consequences of "
     "prolonged low interest rates on equity and real estate valuations."),
    ("borderline: lightly edited AI",
     "I've been thinking a lot about remote work lately. There are genuine tradeoffs, "
     "flexibility and no commute on one side, isolation and blurred work-life boundaries "
     "on the other. Studies show productivity varies widely by individual and role type."),
    ("strongly templated AI (long, uniform)",
     "Effective time management is a critical skill in the modern workplace. First, it is "
     "important to prioritize tasks based on their relative urgency and importance. "
     "Second, it is essential to eliminate distractions in order to maintain focus. "
     "Third, it is beneficial to take regular breaks to sustain productivity. Finally, it "
     "is advisable to review progress at the end of each working day. In conclusion, "
     "these strategies will significantly improve overall efficiency and effectiveness."),
]


def main():
    header = f"{'CASE':38} {'LLM':>5} {'STYLE':>6} {'REL':>4} {'CONF':>6}  ATTRIBUTION"
    print(header)
    print("-" * len(header))
    for name, text in CASES:
        s1 = detector.llm_signal(text)
        s2 = detector.stylometric_signal(text)
        combined = detector.combine_signals(s1["p_ai"], s2["style_score"], s2["reliable"])
        print(f"{name:38} {s1['p_ai']:>5.2f} {s2['style_score']:>6.2f} "
              f"{str(s2['reliable']):>4} {combined['p_ai']:>6.2f}  {combined['attribution']}")


if __name__ == "__main__":
    main()
