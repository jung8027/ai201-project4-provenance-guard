# Spec — labeler.py (Milestone 5)

Maps a combined confidence score to one of three plain-language transparency labels.

## `make_label(attribution, confidence) -> str`
- `likely_ai`   → High-confidence AI label text
- `likely_human`→ High-confidence human label text
- `uncertain`   → Uncertain label text
- The returned text MUST change by band — never a constant string.
- Exact verbatim wording of all three variants lives in `data/label_variants.md` and the README.

The label is written for a non-technical reader and must make the confidence level meaningful.
A false positive (human work labeled AI) is the worst outcome — the uncertain label must not
read as an accusation.
