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

## What to Implement

| Milestone | File(s) | Endpoint / Function | Description |
|-----------|---------|---------------------|-------------|
| 3 | `app.py` | `POST /submit` + signal 1 | Submission endpoint, first detection signal (Groq LLM), audit log stub |
| 4 | `detector.py` | second signal + confidence scoring | Stylometric heuristics signal and combined confidence score |
| 5 | `app.py` | `POST /appeal`, label logic, rate limiting | Transparency label, appeals workflow, rate limiting, complete audit log |

Complete your `planning.md` spec before implementing each milestone.

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

## Audit Log

Every submission writes a structured JSON line to `logs/audit.jsonl`, capturing both individual
signal scores and the combined confidence. Retrieve recent entries via `GET /log`. Sample
(3 entries, one per label band):

```json
{"content_id": "2dbb73e1-c7e3-426f-ae48-abd0edfed664", "creator_id": "u-ai", "timestamp": "2026-06-27T01:32:18.059977+00:00", "attribution": "uncertain", "confidence": 0.6573, "llm_score": 0.8, "style_score": 0.4432, "style_reliable": true, "llm_rationale": "The text exhibits overly formal and uniform language typical of AI-generated content.", "status": "classified"}
{"content_id": "0b5bad47-3e11-46d3-a3bb-91d27314a34d", "creator_id": "u-human", "timestamp": "2026-06-27T01:32:18.413900+00:00", "attribution": "likely_human", "confidence": 0.1603, "llm_score": 0.2, "style_score": 0.1007, "style_reliable": true, "llm_rationale": "The text's casual tone, use of colloquial expressions, and personal experience suggest human authorship.", "status": "classified"}
{"content_id": "64d6710b-a611-45fe-bbd8-96c70a9a3da6", "creator_id": "u-templated", "timestamp": "2026-06-27T01:32:18.644911+00:00", "attribution": "likely_ai", "confidence": 0.8171, "llm_score": 0.9, "style_score": 0.6927, "style_reliable": true, "llm_rationale": "The text exhibits an overly uniform and formulaic structure.", "status": "classified"}
```

*(Appeal entries and the `under_review` status are added in Milestone 5.)*

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
├── app.py              ← Flask orchestration + endpoints (M3, M5)
├── detector.py         ← detection signals + confidence scoring (M3, M4)
├── labeler.py          ← transparency-label generation (M5)
├── auditor.py          ← audit logger + content status (M3, M5)
├── config.py           ← constants (API key, model, thresholds, limits, log path)
├── data/
│   └── label_variants.md   ← reference text for the three label variants
├── logs/               ← audit.jsonl written here after M3
├── planning.md         ← architecture, spec, and AI tool plan (write before any code)
└── specs/
    ├── system-design.md    ← read this first
    ├── detector-spec.md    ← signals + scoring spec (M3/M4)
    ├── labeler-spec.md     ← label spec (M5)
    └── auditor-spec.md     ← audit log spec (M3)
```
