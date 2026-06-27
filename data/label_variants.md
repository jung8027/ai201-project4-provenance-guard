# Transparency Label Variants (verbatim, finalized in Milestone 2)

These are the exact strings `labeler.make_label()` returns. The label **changes by confidence
band** and the "uncertain" variant is deliberately worded so it never reads as an accusation —
because on a writing platform, falsely labeling a human's work as AI is the worst outcome.

## High-confidence AI  (`p_ai ≥ 0.80`)
> 🤖 Likely AI-generated. Our automated analysis found strong signs this text was produced with
> an AI tool. This is an estimate, not a final verdict — if you wrote this yourself, you can appeal
> and a person will review it.

## Uncertain  (`0.30 < p_ai < 0.80`)
> ❔ Origin uncertain. Our automated analysis couldn't confidently determine whether this text was
> written by a person or an AI tool, so we're not drawing a conclusion. Treat the authorship as
> undetermined.

## High-confidence human  (`p_ai ≤ 0.30`)
> ✍️ Likely human-written. Our automated analysis found no strong signs of AI generation in this
> text. This is an automated estimate, not a guarantee of authorship.
