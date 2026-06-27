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
├── app.py              ← Flask app, submission endpoint, appeal endpoint
├── detector.py         ← Detection signals and confidence scoring logic
├── config.py           ← Constants (API key, model, log path, thresholds)
├── logs/               ← audit.jsonl written here
├── planning.md         ← Architecture, spec, and AI tool plan (write before any code)
└── .env                ← GROQ_API_KEY (never commit)
```
