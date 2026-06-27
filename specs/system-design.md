# System Design — Provenance Guard

> Read this first. This is the Milestone 1 design reference; the full spec is in `planning.md`.

## Purpose

A backend that classifies submitted text as human-written or AI-generated, scores confidence,
surfaces a transparency label, and supports creator appeals.

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Orchestration + API | `app.py` | `POST /submit`, `POST /appeal`, `GET /log`, rate limiting |
| Detection + scoring | `detector.py` | Signal 1 (Groq LLM), Signal 2 (stylometric), `combine_signals()` |
| Transparency label | `labeler.py` | Map combined confidence → one of three label variants |
| Audit + status | `auditor.py` | Append structured records to `logs/audit.jsonl`; track content status |
| Constants | `config.py` | API key, model, thresholds, rate limits, log path |

## Pipeline (submission)

`raw text → llm_signal() → stylometric_signal() → combine_signals() → make_label() → log_submission() → response`

## Pipeline (appeal)

`content_id → status: under_review → log_appeal() → confirmation`

See `planning.md` §1 and §6 for the full narrative and diagrams.
