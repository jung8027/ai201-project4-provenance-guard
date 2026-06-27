"""Transparency-label generation (planning.md §3, specs/labeler-spec.md).

Maps an attribution + confidence to one of three plain-language labels shown to a reader.
The text changes by band and is never a constant string. The "uncertain" variant is worded
so it never reads as an accusation — on a writing platform, falsely labeling a human's work as
AI is the worst outcome.
"""

# Verbatim text — kept in sync with data/label_variants.md and planning.md §3.
_LABELS = {
    "likely_ai": (
        "🤖 Likely AI-generated. Our automated analysis found strong signs this text was "
        "produced with an AI tool. This is an estimate, not a final verdict — if you wrote "
        "this yourself, you can appeal and a person will review it."
    ),
    "uncertain": (
        "❔ Origin uncertain. Our automated analysis couldn't confidently determine whether "
        "this text was written by a person or an AI tool, so we're not drawing a conclusion. "
        "Treat the authorship as undetermined."
    ),
    "likely_human": (
        "✍️ Likely human-written. Our automated analysis found no strong signs of AI "
        "generation in this text. This is an automated estimate, not a guarantee of authorship."
    ),
}


def make_label(attribution, confidence=None):
    """Return the reader-facing transparency label for the given attribution.

    `confidence` is accepted for interface symmetry / future wording (e.g. showing a percentage)
    but the variant is selected by the attribution band, which already encodes the score.
    """
    if attribution not in _LABELS:
        raise ValueError(f"Unknown attribution: {attribution!r}")
    return _LABELS[attribution]
