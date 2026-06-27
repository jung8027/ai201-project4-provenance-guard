# Spec: `make_label()`

**File:** `labeler.py`
**Status:** Implemented (Milestone 5) — Implementation Notes filled in below

---

## Purpose

Turn a confidence verdict into the plain-language transparency label a reader sees on the
platform. The same submission gets fundamentally different label text depending on its band — not
a constant string with a number swapped in, but a different message: "this is likely AI," "we
can't tell," or "this is likely human." The label is a UX surface as much as a technical one: it
has to make a probabilistic verdict meaningful to a non-technical reader without overstating
certainty.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `attribution` | `str` | The band: `"likely_ai"`, `"uncertain"`, or `"likely_human"` |
| `confidence` | `float` | Accepted for interface symmetry / future wording; not required for selection |

**Output:** `str` — the reader-facing label text.

**Errors:** raises `ValueError` if `attribution` is not one of the three known values.

---

## Design Decisions

---

### Why select by `attribution`, not by re-deriving the band from `confidence`

```
make_label() keys off attribution, which combine_signals() already computed from the thresholds.
It accepts `confidence` only for interface symmetry (and future wording like showing a percentage),
but does not re-threshold it.

Rationale: the score-to-band thresholds (0.80 / 0.30) must live in exactly one place
(score_to_attribution in detector.py). If the labeler re-derived the band from the raw score, a
future change to a threshold would have to be made in two files and the two could silently diverge,
producing a label that contradicts the attribution in the same response. One source of truth.
```

---

### Label variant: high-confidence AI (`likely_ai`, `p_ai ≥ 0.80`)

```
🤖 Likely AI-generated. Our automated analysis found strong signs this text was produced with an
AI tool. This is an estimate, not a final verdict — if you wrote this yourself, you can appeal and
a person will review it.
```

Even the most confident label is hedged ("an estimate, not a final verdict") and names the appeal
path, because the system can still be wrong and the accused party is a real creator.

---

### Label variant: uncertain (`uncertain`, `0.30 < p_ai < 0.80`)

```
❔ Origin uncertain. Our automated analysis couldn't confidently determine whether this text was
written by a person or an AI tool, so we're not drawing a conclusion. Treat the authorship as
undetermined.
```

This is the most carefully worded variant. It must **not read as a soft accusation** — "uncertain"
should land as a neutral "we don't know," not "we suspect AI but can't prove it." On a writing
platform an insinuation is nearly as damaging as a false accusation, so the wording explicitly
declines to draw any conclusion.

---

### Label variant: high-confidence human (`likely_human`, `p_ai ≤ 0.30`)

```
✍️ Likely human-written. Our automated analysis found no strong signs of AI generation in this
text. This is an automated estimate, not a guarantee of authorship.
```

Phrased as "no strong signs of AI generation" rather than "this is human," because the signals can
only fail to find AI markers — they cannot prove human authorship. The "not a guarantee" caveat
keeps the platform from over-promising.

---

### The false-positive asymmetry, expressed in wording

```
A false positive (a human's work labeled AI) is the worst outcome on a writing platform. The label
design reflects that asymmetry in three ways:
  1. The AI label always pairs the verdict with the appeal path.
  2. The uncertain label refuses to insinuate AI — it states no conclusion.
  3. The human label avoids over-claiming ("no strong signs," "not a guarantee").
The thresholds already make the AI band hard to reach; the wording ensures that even when it is
reached, the message is contestable rather than final.
```

---

### Source of truth for the text

```
The verbatim strings live in labeler.py (the executable source) and are mirrored in
data/label_variants.md and the README for documentation. Any wording change must be made in
labeler.py first; the docs follow.
```

---

## Implementation Notes

**A label variant that was reworded after a second reading, and why:**

```
The "uncertain" variant originally ended with "...we couldn't tell." On re-reading it sounded like
a hedged suspicion of AI rather than a genuine non-conclusion. It was reworded to "...so we're not
drawing a conclusion. Treat the authorship as undetermined." — which makes the neutrality explicit.
On a writing platform, an ambiguous "we couldn't tell" can still read as an insinuation; the final
wording removes that.
```

**Which band's wording was hardest to get right, and why:**

```
The uncertain band, by far. The AI and human labels are straightforward — they state a verdict and
hedge it. The uncertain label has to communicate "no verdict" without the absence of a verdict
reading as a quiet accusation. It is the band the system produces most often for real prose, so its
tone matters more than either confident label's.
```
