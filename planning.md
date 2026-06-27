# Provenance Guard — Planning & Spec

> **Status:** Milestone 1 (architecture) and Milestone 2 (spec) complete. This document is the
> contract every later milestone implements against, and the primary context handed to AI tools
> in Milestones 3–5.
> **Update before stretch features.**

This spec answers the five required design questions (§1–§5), then pins down the architecture
(`## Architecture`) and the AI prompting plan (`## AI Tool Plan`).

---

## 1. Detection Signals

The pipeline uses **two genuinely independent signals** — one semantic, one structural. They are
independent because they inspect different properties of the text, so agreement is meaningful
evidence and disagreement is itself a useful uncertainty signal. Single-signal detection would
have no such cross-check.

### Signal 1 — LLM Classifier (Groq, semantic)
- **File / function:** `detector.py → llm_signal(text)`
- **What it measures:** Whether the text *reads* as AI-generated, judged holistically — tone,
  fluency, "voice," even hedging, and the over-structured/over-polite quality large models tend
  to produce.
- **Output shape:** `{ "p_ai": float in [0,1], "rationale": str }` — `p_ai` is the model's estimate
  that the text is AI-generated. **Not a binary flag** — a graded score.
- **Why the property differs:** AI prose is coherent, evenly hedged, tonally neutral; human prose
  carries idiosyncratic voice, opinion, irregular emphasis.
- **Blind spot:** Fooled by **framing and lightly edited AI** — a human writing in a polished formal
  register can read "AI," and edited AI can read "human." Also non-deterministic; can drift between
  calls.

### Signal 2 — Stylometric Heuristics (pure Python, structural)
- **File / function:** `detector.py → stylometric_signal(text)`
- **What it measures:** Quantifiable regularity of the writing:
  - **Sentence-length variance** — humans vary sentence length far more than AI.
  - **Type-token ratio (TTR)** — vocabulary diversity; AI reuses a tighter vocabulary band.
  - **Punctuation density** — rate and spread of punctuation marks.
- **Output shape:** `{ "style_score": float in [0,1], "metrics": {...} }` — `style_score` higher =
  more uniform = more AI-like. A graded score, with the raw metrics returned for debugging.
- **Why the property differs:** AI text is statistically *smoother*; human writing is bursty and
  irregular.
- **Blind spot:** **Length-sensitive and genre-blind.** On short inputs the statistics are
  unreliable; it mis-scores legitimately uniform human writing (formal abstracts, repetition-heavy
  poetry, technical specs) as "AI."

### Combination → single confidence score
- **File / function:** `detector.py → combine_signals(llm_score, style_score)`
- **Formula:** `p_ai = 0.6 * llm_score + 0.4 * style_score`. The LLM is weighted higher because the
  holistic read is the stronger single indicator; stylometrics is the structural cross-check.
- **Disagreement adjustment:** when `|llm_score − style_score| > 0.4`, pull `p_ai` toward 0.5
  (uncertain). Rationale: when a semantic and a structural signal conflict, the honest answer is
  "we don't know," not a confident average — and this is the main defense against false positives.
- **Output:** `{ "p_ai": float, "attribution": "likely_ai" | "uncertain" | "likely_human" }`.

---

## 2. Uncertainty Representation

- **What the score is:** `confidence` = `p_ai`, the system's estimated probability the text is
  AI-generated, in `[0, 1]`. Distance from 0.5 = strength of the verdict.
- **What 0.6 means:** "Leans AI, but not confidently." Because the system requires strong evidence
  to *accuse* (see asymmetry below), **0.6 does not produce an AI label** — it lands in the
  **uncertain** band. A user seeing 0.6 should read "the system isn't sure, slightly AI-leaning,"
  not "this is AI."
- **Mapping raw → calibrated:** each signal already emits a `[0,1]` score; `combine_signals()`
  produces the calibrated `p_ai` via the weighted blend + disagreement pull (§1). Calibration is
  *validated* in Milestone 4 against deliberately chosen inputs (clear-AI, clear-human, two
  borderline), adjusting weights/threshold if scores don't match intuition.
- **Thresholds (asymmetric — to suppress false positives):**

  | Combined `p_ai` | Attribution | Label variant |
  |-----------------|-------------|---------------|
  | `≥ 0.80` | `likely_ai` | High-confidence AI |
  | `0.30 – 0.80` | `uncertain` | Uncertain |
  | `≤ 0.30` | `likely_human` | High-confidence human |

  The "AI" band requires `≥ 0.80` — a deliberately high bar so borderline cases degrade to
  "uncertain" rather than falsely accusing a human writer. **This is not a binary flip at 0.5:** a
  0.51 and a 0.95 produce different labels (uncertain vs. high-confidence AI), which is the
  required behavior.

---

## 3. Transparency Label Design (exact text — all three variants)

The label is written for a **non-technical reader** and must make the confidence level meaningful.
Because a false positive (a human's work labeled AI) is the worst outcome on a writing platform,
the **uncertain** label is worded so it never reads as an accusation, and every variant states it is
an automated estimate with an appeal path.

> **High-confidence AI** (`p_ai ≥ 0.80`):
> *"🤖 Likely AI-generated. Our automated analysis found strong signs this text was produced with
> an AI tool. This is an estimate, not a final verdict — if you wrote this yourself, you can appeal
> and a person will review it."*

> **Uncertain** (`0.30 < p_ai < 0.80`):
> *"❔ Origin uncertain. Our automated analysis couldn't confidently determine whether this text
> was written by a person or an AI tool, so we're not drawing a conclusion. Treat the authorship as
> undetermined."*

> **High-confidence human** (`p_ai ≤ 0.30`):
> *"✍️ Likely human-written. Our automated analysis found no strong signs of AI generation in this
> text. This is an automated estimate, not a guarantee of authorship."*

The label text returned by `/submit` **changes by band** — it is never a constant string. Verbatim
copies also live in [`data/label_variants.md`](data/label_variants.md) and the README.

---

## 4. Appeals Workflow

- **Who can appeal:** the original creator. An appeal references the `content_id` from the
  `/submit` response; in production it would be gated to the authenticated creator whose
  `creator_id` matches the original submission. For this project, supplying a valid `content_id` +
  reasoning is sufficient.
- **What they provide:** `{ "content_id": uuid, "creator_reasoning": str }` — free text explaining
  why they believe the classification is wrong (e.g., "I wrote this poem by hand; the repetition is
  a deliberate stylistic choice").
- **What the system does** (`POST /appeal` → `auditor.py`):
  1. Validate the `content_id` exists (else `404`).
  2. Flip the content's status `classified → under_review`.
  3. Append an **appeal record** to `logs/audit.jsonl` beside the original decision, carrying:
     `content_id`, `timestamp`, `creator_reasoning`, plus the original `attribution`, `confidence`,
     and both signal scores for reviewer context.
  4. Return a confirmation `{ content_id, status: "under_review", message }`.
  - **No automated reclassification** — a human makes the final call.
- **What a human reviewer sees (appeal queue):** via `GET /log` filtered to
  `status == "under_review"`, each queued item shows: the original text (or excerpt), the original
  `attribution` + `confidence` + both individual signal scores, the creator's `creator_reasoning`,
  and timestamps for both the original decision and the appeal — enough context to overturn or
  uphold manually.

---

## 5. Anticipated Edge Cases

Two specific scenarios the system will handle poorly, tied to concrete signal properties:

1. **Repetition-heavy, simple-vocabulary human poetry.** A hand-written poem built on refrains
   and plain words produces *low* sentence-length variance and *low* TTR → the stylometric signal
   scores it **AI-like** (`style_score ≈ 0.75`), even though the LLM reads the genuine voice as
   human (`p_ai ≈ 0.35`). Without mitigation this risks a false "AI" accusation. **Mitigation:** the
   disagreement adjustment (§1) pulls the combined score into the **uncertain** band instead of
   asserting AI; the appeal path is the backstop.

2. **Short submissions (≤ ~3 sentences).** A two-line micro-poem or a 30-word note gives the
   stylometric signal almost nothing to measure — variance and TTR are statistically meaningless
   on so little text — so `style_score` is noise and the system over-relies on the LLM, which is
   itself shakier on tiny inputs. **Mitigation (M4):** below a minimum sentence/token count,
   down-weight the stylometric signal and widen the uncertain band; document the floor.

   *Additional known-poor cases (documented, lower priority):* formal/uniform human writing
   (academic abstracts, legal/technical text) where *both* signals may wrongly agree on "AI"; and
   lightly edited AI output, which intentionally lands in "uncertain."

---

## Architecture

**Submission flow:** raw text enters `POST /submit`, passes a rate-limit check, is assigned a
`content_id`, then runs through both detection signals in `detector.py`; `combine_signals()`
blends them into one calibrated `p_ai`, `labeler.py` turns that into a reader-facing transparency
label, `auditor.py` writes the full structured decision to `logs/audit.jsonl`, and the endpoint
returns `{content_id, attribution, confidence, label}`. **Appeal flow:** `POST /appeal` looks up the
`content_id`, flips its status to `under_review`, and logs the creator's reasoning beside the
original decision for a human reviewer — no automated reclassification.

### API surface

| Method & Path | Accepts | Returns |
|---------------|---------|---------|
| `POST /submit` | `{ "text": str, "creator_id": str }` | `{ content_id, attribution, confidence, label }` |
| `POST /appeal` | `{ "content_id": uuid, "creator_reasoning": str }` | `{ content_id, status: "under_review", message }` |
| `GET /log` | — | `{ "entries": [ <structured audit records, most recent first> ] }` |

`POST /submit` is rate limited (limits/reasoning finalized in M5 + README). `GET /log` exists for
documentation/grading visibility (would require auth in production). `/appeal` returns `404` for an
unknown `content_id`.

### Submission flow diagram

```
        ┌─────────────────────── POST /submit (app.py) ────────────────────────┐
        │                                                                       │
client ─┤ {text, creator_id}                                                    │
        │        │                                                              │
        │        ▼                                                              │
        │  [rate limit]──429──▶ reject                                          │
        │        │ ok                                                           │
        │        ▼                                                              │
        │  assign content_id (uuid)                                             │
        │        │ raw text                                                     │
        │        ├───────────────▶ Signal 1: llm_signal()      ─┐ llm_score    │
        │        │                 (detector.py, Groq)          │ [0..1]        │
        │        │ raw text                                      ▼               │
        │        └───────────────▶ Signal 2: stylometric_signal() ─┐ style_score│
        │                          (detector.py, pure Python)      │ [0..1]      │
        │                                                          ▼             │
        │                          combine_signals() ── p_ai [0..1] + attribution│
        │                          (detector.py)            │                    │
        │                                                    ▼                    │
        │                          make_label() ── label text (labeler.py)        │
        │                                                    │                    │
        │                                                    ▼                    │
        │                          log_submission() ── audit.jsonl (auditor.py)   │
        │                                                    │                    │
        │  ◀───────────────────────────────────────────────┘                    │
        │  {content_id, attribution, confidence, label}                          │
        └────────────────────────────────────────────────────────────────────────┘
```

### Appeal flow diagram

```
        ┌─────────────────────── POST /appeal (app.py) ────────────────────────┐
client ─┤ {content_id, creator_reasoning}                                       │
        │        │                                                              │
        │        ▼                                                              │
        │  look up content_id ──unknown──▶ 404                                  │
        │        │ found                                                        │
        │        ▼                                                              │
        │  update status: classified ──▶ under_review   (auditor.py)            │
        │        │                                                              │
        │        ▼                                                              │
        │  log_appeal() — appeal_reasoning logged beside original decision      │
        │        │        (auditor.py → audit.jsonl)                            │
        │        ▼                                                              │
        │  ◀── {content_id, status: "under_review", message}                    │
        └────────────────────────────────────────────────────────────────────────┘
```

---

## AI Tool Plan

For each implementation milestone: which spec sections feed the AI tool, what to ask it to
generate, and how the output is verified before it's trusted.

### M3 — Submission endpoint + first signal
- **Spec sections provided:** §1 (Detection Signals — Signal 1 only) + `## Architecture` diagram +
  API surface.
- **Ask the AI to generate:** (1) the Flask app skeleton with a `POST /submit` route stub that
  returns a hardcoded response, and (2) `llm_signal(text)` calling Groq and returning
  `{p_ai, rationale}`; plus the `GET /log` route and `auditor.log_submission()` stub.
- **Verify:** call `llm_signal()` directly on a few inputs and inspect the output **before** wiring it
  into the route; confirm the function signature matches §1's output shape and the route matches
  the API contract. Confirm `/submit` returns `content_id, attribution, confidence, label` and that
  each call writes one structured JSON line to `logs/audit.jsonl`.

### M4 — Second signal + confidence scoring
- **Spec sections provided:** §1 (Detection Signals — full) + §2 (Uncertainty Representation) +
  `## Architecture` diagram.
- **Ask the AI to generate:** (1) `stylometric_signal(text)` computing the three metrics → a single
  `style_score`, and (2) `combine_signals()` implementing the exact weighted blend + disagreement
  pull + threshold bands from §1/§2.
- **Verify:** confirm the generated scoring matches the §2 thresholds *exactly* (AI tools often
  drift to a reasonable-looking but wrong mapping). Run the 4 calibration inputs (clear-AI,
  clear-human, two borderline) and check scores vary meaningfully; if a score is off, print both
  signal scores separately to find the misbehaving one.

### M5 — Production layer (label + appeals + rate limiting + audit log)
- **Spec sections provided:** §3 (Transparency Label — exact text) + §4 (Appeals Workflow) +
  `## Architecture` diagram.
- **Ask the AI to generate:** (1) `labeler.make_label(attribution, confidence)` mapping the score
  to the correct variant text, and (2) the `POST /appeal` endpoint; plus Flask-Limiter wiring on
  `/submit`.
- **Verify:** ask the tool to emit all three label variants and confirm the text matches §3
  verbatim and changes by band. Submit inputs that reach all three bands. Test `/appeal` with a
  real `content_id`, then `GET /log` to confirm `status == "under_review"` and `appeal_reasoning`
  is populated. Fire 12 rapid `/submit` requests and confirm `200×10` then `429`.

---

## File Structure (mirrors the RepairSafe Lab 4 starter layout)

| RepairSafe file | Provenance Guard equivalent | Role |
|-----------------|-----------------------------|------|
| `app.py` (orchestration) | `app.py` | Flask app, `POST /submit`, `POST /appeal`, `GET /log`, rate limiting |
| `safety.py` (classifier) | `detector.py` | Detection signals + confidence scoring |
| `responder.py` (response gen) | `labeler.py` | Transparency-label generation |
| `auditor.py` (logger) | `auditor.py` | Structured audit log + content status |
| `config.py` | `config.py` | API key, model, thresholds, rate limits, log path |
| `data/repair_tiers.md` | `data/label_variants.md` | Reference text for the three label variants |
| `logs/` | `logs/` | `audit.jsonl` |
| `specs/` | `specs/` | `system-design.md`, `detector-spec.md`, `labeler-spec.md`, `auditor-spec.md` |

```
ai201-project4-provenance-guard/
├── app.py              ← Flask orchestration + endpoints (M3, M5)
├── detector.py         ← detection signals + confidence scoring (M3, M4)
├── labeler.py          ← transparency-label generation (M5)
├── auditor.py          ← audit logger + content status (M3, M5)
├── config.py           ← constants (API key, model, thresholds, limits, log path)
├── data/
│   └── label_variants.md   ← reference text for the three label variants
├── logs/               ← audit.jsonl written here after M3
└── specs/
    ├── system-design.md    ← read this first
    ├── detector-spec.md    ← signals + scoring spec (M3/M4)
    ├── labeler-spec.md     ← label spec (M5)
    └── auditor-spec.md     ← audit log spec (M3)
```

---

## ✅ Milestone 2 Checkpoint — Verification

- [x] **All five questions answered with specific, implementation-ready answers** → §1 signals,
  §2 uncertainty, §3 label design, §4 appeals, §5 edge cases.
- [x] **Three label variants written out verbatim** → §3 (high-confidence AI / uncertain /
  high-confidence human).
- [x] **Scoring produces different labels at different ranges, not a binary flip at 0.5** → §2
  thresholds: `≥0.80` AI, `0.30–0.80` uncertain, `≤0.30` human; 0.51 ≠ 0.95.
- [x] **`## Architecture` section includes the Milestone 1 diagram** → both submission and appeal
  flow diagrams + narrative + API surface.
- [x] **`## AI Tool Plan` covers all three implementation milestones** with specific spec sections,
  generation requests, and verification steps → M3 / M4 / M5.
