# Provenance Guard — AI Content Attribution System

**AI201 Project 4**

Provenance Guard is a backend system that creative-sharing platforms can use to classify submitted content as human-written or AI-generated. It uses a multi-signal detection pipeline to produce a confidence score, surfaces a transparency label to users, and supports creator appeals for contested classifications.

---

## Setup

1. Clone your repo locally
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Mac/Linux
   # or: .venv\Scripts\activate  # Windows
   ```

3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add your Groq API key
5. Run the app: `python app.py`

---

## Architecture Overview

The path a single submission takes from input to the label a user sees:

```
POST /submit  →  rate limit  →  assign content_id
      │
      ├─▶ Signal 1: llm_signal()        (detector.py · Groq · semantic)   → llm_score
      └─▶ Signal 2: stylometric_signal() (detector.py · pure Python · structural) → style_score
                                   │
                                   ▼
              combine_signals()  →  p_ai + attribution   (detector.py)
                                   ▼
              make_label()       →  transparency label   (labeler.py)
                                   ▼
              log_submission()   →  logs/audit.jsonl      (auditor.py)
                                   ▼
        response: { content_id, attribution, confidence, label }
```

`app.py` orchestrates; `detector.py` holds both signals and the scoring; `labeler.py` turns a score
into reader-facing text; `auditor.py` is the structured log and content-status store. The **appeal
path** (`POST /appeal`) looks up the `content_id`, appends an `under_review` record with the
creator's reasoning beside the original decision, and returns a confirmation — no automated
reclassification. Full narrative and diagrams live in [planning.md](planning.md) (`## Architecture`).

---

## Detection Signals

Two **independent** signals — one semantic, one structural — so they fail in different situations.
Agreement is real evidence; disagreement is itself a useful uncertainty signal. Single-signal
detection would have no such cross-check.

### Signal 1 — LLM classifier (Groq, semantic)
- **Measures:** whether the text *reads* as AI-generated, judged holistically (tone, voice, fluency,
  even hedging, over-uniform structure). Output: `p_ai ∈ [0,1]` + a one-line rationale.
- **Why chosen:** the holistic "does this sound generated" read is the single strongest indicator,
  and an LLM captures it without hand-engineering.
- **What it misses:** fooled by framing (a polished, formal human can read "AI") and by lightly
  edited AI; non-deterministic between calls.

### Signal 2 — Stylometric heuristics (pure Python, structural)
- **Measures:** how *uniform* the writing is — sentence-length burstiness (coefficient of
  variation), type-token ratio, punctuation density → a single `style_score ∈ [0,1]` where higher
  = more uniform = more AI-like.
- **Why chosen:** it is genuinely independent of the LLM (structure, not meaning), costs nothing,
  and provides the cross-check that catches the LLM's blind spots.
- **What it misses:** length-sensitive (unreliable below ~3 sentences / 25 words, where it is
  down-weighted) and genre-blind — it mis-reads deliberately uniform human writing (formal
  abstracts, repetition-heavy poetry) as AI.

---

## Confidence Scoring — Testing & Results

The pipeline combines two signals into a single `p_ai` (probability the text is AI-generated):
`p_ai = 0.6 · llm_score + 0.4 · style_score`, with a disagreement pull toward 0.5 when the
semantic and structural signals conflict, and the stylometric signal down-weighted on
short/unreliable text. Attribution bands are deliberately asymmetric to suppress false positives
(`≥ 0.80 → likely_ai`, `0.30–0.80 → uncertain`, `≤ 0.30 → likely_human`).

Five deliberately chosen inputs run through the full pipeline (`python tests/test_scoring.py`):

```
CASE                                     LLM  STYLE  REL   CONF  ATTRIBUTION
----------------------------------------------------------------------------
clearly AI (formal essay)               0.80   0.44 True   0.66  uncertain
clearly human (casual review)           0.20   0.17 True   0.19  likely_human
borderline: formal human writing        0.80   0.47 False   0.75  uncertain
borderline: lightly edited AI           0.20   0.40 True   0.28  likely_human
strongly templated AI (long, uniform)   0.90   0.71 True   0.82  likely_ai
```

**What this shows**

- **Meaningful variation, not a binary flip.** Combined scores span `0.19 → 0.82` and reach all
  three label bands — a 0.66 and a 0.82 produce different labels (`uncertain` vs `likely_ai`).
- **Two contrasting example submissions** (as required):
  - *High-confidence:* the strongly templated AI essay — `llm 0.90`, `style 0.71`, **combined 0.82
    → likely_ai**. Both signals agree, so the score clears the conservative 0.80 bar.
  - *Lower-confidence:* the casual human review — `llm 0.20`, `style 0.17`, **combined 0.19 →
    likely_human**. Both signals agree the text is bursty and informal.
- **False-positive mitigation works.** The *formal human* paragraph that signal 1 alone rated AI
  (`llm 0.80`) lands at **0.75 `uncertain`**, not `likely_ai`, because the short-text down-weighting
  keeps the system from confidently accusing a human writer.
- **The 0.80 bar is intentionally hard to clear.** Short *clearly-AI* text (`combined 0.66`) stays in
  `uncertain` rather than `likely_ai` unless both signals concur — the documented anti-false-positive
  asymmetry, not a miscalibration.

---

## Transparency Label

The label returned by `POST /submit` is plain-language and **changes by confidence band** — it is
never a constant string. The "uncertain" variant is deliberately worded so it never reads as an
accusation, because on a writing platform falsely labeling a human's work as AI is the worst
outcome. All three variants were verified reachable by submitting inputs that land in each band.

| Variant | Band (`p_ai`) | Exact text displayed |
|---------|---------------|----------------------|
| **High-confidence AI** | `≥ 0.80` | 🤖 Likely AI-generated. Our automated analysis found strong signs this text was produced with an AI tool. This is an estimate, not a final verdict — if you wrote this yourself, you can appeal and a person will review it. |
| **Uncertain** | `0.30 – 0.80` | ❔ Origin uncertain. Our automated analysis couldn't confidently determine whether this text was written by a person or an AI tool, so we're not drawing a conclusion. Treat the authorship as undetermined. |
| **High-confidence human** | `≤ 0.30` | ✍️ Likely human-written. Our automated analysis found no strong signs of AI generation in this text. This is an automated estimate, not a guarantee of authorship. |

Reachability check (each input produced the expected band and label):

```
INPUT                          CONF   ATTRIBUTION    LABEL VARIANT
-------------------------------------------------------------------------
templated AI essay             0.82   likely_ai      🤖 Likely AI-generated…
casual human review            0.16   likely_human   ✍️ Likely human-written…
formal human paragraph         0.77   uncertain      ❔ Origin uncertain…
```

---

## Appeals Workflow

`POST /appeal` lets a creator contest a classification. It accepts `content_id` (from the original
`/submit` response) and `creator_reasoning`. The endpoint flips the content's status to
`under_review`, appends an appeal record beside a snapshot of the original decision, and returns a
confirmation. An unknown `content_id` returns `404`. There is no automated reclassification — a
human reviewer acts on the queue (`GET /log?status=under_review`).

```
$ curl -s -X POST localhost:5000/appeal -H "Content-Type: application/json" \
    -d '{"content_id":"5001ed6e-…","creator_reasoning":"I wrote this review myself…"}'
{"content_id": "5001ed6e-…", "status": "under_review",
 "message": "Appeal received. The classification is now under review by a human."}

$ curl -s -X POST localhost:5000/appeal -d '{"content_id":"does-not-exist",…}'   # → HTTP 404
{"error": "No submission found for content_id 'does-not-exist'."}
```

---

## Rate Limiting

`POST /submit` is rate limited with Flask-Limiter (in-memory store):

```python
@limiter.limit("10 per minute;100 per day")
```

**Chosen limits and reasoning.** A real creator submits their own work a handful of times — even
heavy editing-and-resubmitting rarely exceeds a few requests per minute, so **10/minute** comfortably
covers genuine use while stopping a script from hammering the (paid, LLM-backed) endpoint. The
**100/day** cap bounds sustained abuse over a day while still accommodating a prolific creator or a
small team sharing an IP. The numbers are intentionally generous to humans and hostile to floods.

Evidence — 12 rapid requests against the 10/minute limit (first 10 succeed, the rest are rejected):

```
request 1  -> 200      request 7  -> 200
request 2  -> 200      request 8  -> 200
request 3  -> 200      request 9  -> 200
request 4  -> 200      request 10 -> 200
request 5  -> 200      request 11 -> 429
request 6  -> 200      request 12 -> 429
```

---

## Audit Log

Every submission and appeal writes a structured JSON line to `logs/audit.jsonl`, capturing the
timestamp, content ID, attribution, combined confidence, **both individual signal scores**, and —
for appeals — the creator's reasoning and `under_review` status. Retrieve entries via `GET /log`
(or `GET /log?status=under_review` for the appeal queue). Live sample (3 submissions, one per band,
plus one appeal):

```json
{"content_id": "514eb07f-e7a8-4ac9-99f3-7cc7d8fd6897", "creator_id": "u-templated", "timestamp": "2026-06-27T01:40:46.247068+00:00", "attribution": "likely_ai", "confidence": 0.8171, "llm_score": 0.9, "style_score": 0.6927, "style_reliable": true, "llm_rationale": "The text exhibits an overly uniform and formulaic structure.", "status": "classified", "event": "submission"}
{"content_id": "5001ed6e-8f1a-4653-b3ee-d3d35bc3e742", "creator_id": "u-human", "timestamp": "2026-06-27T01:40:46.504034+00:00", "attribution": "likely_human", "confidence": 0.1603, "llm_score": 0.2, "style_score": 0.1007, "style_reliable": true, "llm_rationale": "The text's informal tone, use of colloquial expressions, and personal opinion suggest human authorship.", "status": "classified", "event": "submission"}
{"content_id": "d6337685-3f6d-431e-bf7f-bb6c86b86ae1", "creator_id": "u-econ", "timestamp": "2026-06-27T01:40:46.860801+00:00", "attribution": "uncertain", "confidence": 0.7688, "llm_score": 0.8, "style_score": 0.5921, "style_reliable": false, "llm_rationale": "The text exhibits a formal and overly uniform tone, typical of AI-generated content.", "status": "classified", "event": "submission"}
{"event": "appeal", "content_id": "5001ed6e-8f1a-4653-b3ee-d3d35bc3e742", "creator_id": "u-human", "timestamp": "2026-06-27T01:40:46.897210+00:00", "status": "under_review", "appeal_reasoning": "I wrote this review myself after eating there; the casual tone is just how I write.", "original_attribution": "likely_human", "original_confidence": 0.1603, "llm_score": 0.2, "style_score": 0.1007}
```

The appeal record carries a snapshot of the original decision (`original_attribution`,
`original_confidence`, both signal scores) so a reviewer has full context without cross-referencing.
The current status of a `content_id` is the status on its most recent entry.

---

## Known Limitations

**Formal, uniform human writing is the system's worst case** — e.g. a peer-reviewed abstract, a
legal clause, or a technical spec written by a person. Such text has low sentence-length variation,
so the stylometric signal scores it AI-like, *and* the LLM tends to read impersonal, polished prose
as AI-leaning. Because both signals can agree for the wrong reason, this is the one place a
**false positive** (a human's work labeled AI — the worst outcome on a writing platform) can slip
through. The root cause is intrinsic to Signal 2: it measures *uniformity*, not authorship, and
cannot distinguish disciplined human formality from machine smoothness. In testing, the formal
economics paragraph landed at `0.77` — `uncertain`, close to the `0.80` AI line. The high bar plus
the appeals path are the mitigations, but a sufficiently formal style can still drift upward.

A second specific failure: **very short submissions** (≤ ~3 sentences / 25 words, e.g. a two-line
micro-poem). The stylometric signal has too little text to measure burstiness or vocabulary
diversity meaningfully, so it is flagged unreliable and down-weighted — the system effectively
falls back to the LLM alone and loses its cross-check exactly when it is least confident.

---

## Spec Reflection

**One way the spec helped.** Deciding *in `planning.md`, before any code*, that false positives are
worse than false negatives turned confidence scoring from an ad-hoc choice into a concrete
contract: asymmetric bands (`≥ 0.80` to assert AI) plus a disagreement pull toward "uncertain."
That decision directly fixed a real bug — a formal-human paragraph that Signal 1 alone rated
`likely_ai` in Milestone 3 correctly became `uncertain` once the second signal and the spec's
scoring rules were in place.

**One way the implementation diverged.** The spec named Signal 2's first metric as raw
*sentence-length variance*. Calibrating against the four reference inputs showed raw standard
deviation barely separated AI from human on short samples, so the implementation switched to the
**coefficient of variation** (length-normalized) and pinned metric sub-weights the spec hadn't
specified. The divergence was driven by evidence from the Milestone 4 test harness, not preference.

---

## AI Usage

This project was built with Claude (Claude Code) as the AI implementation tool, directed by the
`planning.md` spec. Two specific instances:

1. **Stylometric signal (Milestone 4).** I gave the AI the detection-signals spec and asked it to
   implement Signal 2 as three metrics combined into one score. Its first version mapped raw
   sentence-length standard deviation directly to a score. Running the calibration harness
   (`tests/test_scoring.py`) showed the scores clustered and failed to separate clearly-AI from
   clearly-human short text. **I overrode** the raw-stdev mapping with a coefficient-of-variation
   formula and re-weighted the three metrics (0.65 / 0.20 / 0.15), then re-ran the harness to
   confirm meaningful separation.

2. **Appeals + audit log (Milestone 5).** I asked the AI to implement `POST /appeal` and the status
   update from the appeals spec. It produced an append-only log writer. **I kept** the append-only
   design (better audit trail) but **revised** it to add an `event` field, a `find_submission()`
   correlation by `content_id`, and a `GET /log?status=under_review` queue — the first cut had no
   way for a human reviewer to see pending appeals, which the spec required.

---

## Portfolio Walkthrough

> _A short (couple-minute) screen recording giving a tour of the system end-to-end — submitting
> content across the three confidence bands, filing an appeal, and triggering the rate limit —
> while talking through the two-signal design and the false-positive asymmetry. The detailed
> evidence is captured in the sections above; the walkthrough is the narrated tour._
>
> **Link:** _(to be recorded and added before submission)_

---

## Required Features

| Feature | Description |
|---------|-------------|
| Content Submission Endpoint | `POST /submit` accepts `text` and `creator_id`; returns `content_id`, attribution result, confidence score, and transparency label |
| Multi-Signal Detection Pipeline | At least 2 distinct signals — one semantic (LLM-based), one structural (stylometric heuristics) |
| Confidence Scoring with Uncertainty | A calibrated score (0–1) that produces meaningfully different labels at different ranges, not a binary flip |
| Transparency Label | Three variants — high-confidence AI, high-confidence human, uncertain — written as plain-language text in this README |
| Appeals Workflow | `POST /appeal` accepts `content_id` and `creator_reasoning`; updates status to `under_review` and logs the appeal |
| Rate Limiting | Flask-Limiter applied to `POST /submit`; limits and reasoning documented in this README |
| Audit Log | Every submission and appeal logged as structured JSON; `GET /log` returns recent entries |

---

## Stretch Features

| Feature | Description |
|---------|-------------|
| Ensemble detection | 3+ detection signals with a documented weighting or voting approach |
| Provenance certificate | "Verified human" credential with a defined verification step and display format |
| Analytics dashboard | View showing detection patterns, appeal rates, and one additional metric |
| Multi-modal support | Extend the pipeline to handle a second content type (e.g., image descriptions or structured metadata) |

---

## Recommended Stack

| Component | Tool | Notes |
|-----------|------|-------|
| API framework | Flask | Free, lightweight |
| Detection signal 1 | Groq (`llama-3.3-70b-versatile`) | Free tier — same account as Projects 1–3 |
| Detection signal 2 | Stylometric heuristics | Pure Python, no external libraries needed |
| Rate limiting | Flask-Limiter | Free |
| Audit log | SQLite (built-in) or structured JSON | No additional setup |

---

## Repository Structure

```
ai201-project4-provenance-guard/
├── app.py              ← Flask orchestration + all endpoints
├── detector.py         ← detection signals + confidence scoring
├── labeler.py          ← transparency-label generation
├── auditor.py          ← audit logger + content status store
├── config.py           ← constants (API key, model, thresholds, limits, log path)
├── demo.sh             ← guided demo walkthrough of all seven features
├── planning.md         ← architecture, spec, and AI tool plan
├── requirements.txt    ← Python dependencies
├── .env.example        ← template for GROQ_API_KEY
├── data/
│   └── label_variants.md   ← reference text for the three label variants
├── logs/
│   └── audit.jsonl         ← append-only structured audit log
├── specs/
│   ├── system-design.md    ← read this first
│   ├── detector-spec.md    ← signals + scoring spec
│   ├── labeler-spec.md     ← label spec
│   └── auditor-spec.md     ← audit log spec
└── tests/
    ├── test_api.py         ← endpoint integration tests
    ├── test_detector.py    ← detection signal unit tests
    ├── test_labeler.py     ← label generation tests
    └── test_scoring.py     ← confidence scoring calibration harness
```
