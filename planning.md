# Provenance Guard — Planning

> **Status:** Milestone 1 (Understand the System and Define the Architecture) complete.
> Milestone 2 will extend this document with the full spec, edge-case analysis, and AI Tool Plan.

---

## 1. Architecture Narrative — The Path a Submission Takes

A single piece of text travels through the system as follows:

1. **Client → `POST /submit`** (`app.py`). A creator's platform sends a JSON body containing `text` (the content) and `creator_id`. The endpoint is the system's only entry point for new content. Before any logic runs, **rate limiting** (Flask-Limiter, configured in `app.py`) checks that this client hasn't exceeded its allowance; over-limit requests are rejected with `429` and never reach detection.

2. **Submission handler assigns a `content_id`** (`app.py`). A UUID is generated so the submission can be referenced later — by the response, the audit log, and any future appeal. This ID is the thread that ties every record together.

3. **Signal 1 — LLM classifier** (`detector.py → llm_signal()`). The raw text is sent to Groq (`llama-3.3-70b-versatile`) with a prompt asking it to assess whether the writing reads as human or AI-generated. It returns a structured score in `[0, 1]` (`p_ai`, the probability the text is AI-generated) plus a short rationale. This signal captures **semantic and stylistic coherence holistically** — the things a reader "feels" about whether prose sounds machine-made.

4. **Signal 2 — Stylometric heuristics** (`detector.py → stylometric_signal()`). The same raw text is analyzed in pure Python — no model call. It computes measurable structural properties (sentence-length variance, type-token ratio, punctuation density) and maps them to a score in `[0, 1]`. This signal captures **structural uniformity** — AI text tends to be statistically smoother than human text.

5. **Confidence scoring** (`detector.py → combine_signals()`). The two signal scores are combined into a single calibrated confidence (`p_ai ∈ [0, 1]`) using a weighted blend plus a disagreement adjustment that pulls the result toward "uncertain" when the signals conflict. The combined score also yields an `attribution` verdict (`likely_ai` / `uncertain` / `likely_human`).

6. **Transparency label** (`labeler.py → make_label()`). The combined confidence is mapped to one of three plain-language label variants shown to a non-technical reader. The label text changes by score band — it is never a constant string.

7. **Audit log** (`auditor.py → log_submission()`). A structured JSON record (timestamp, `content_id`, `creator_id`, attribution, combined confidence, both individual signal scores, status) is appended to `logs/audit.jsonl`. The current content status (`classified`) is also tracked so an appeal can later flip it.

8. **Response → Client** (`app.py`). The endpoint returns `content_id`, `attribution`, `confidence`, and the `label` text. The creator's platform displays the label; the `content_id` is retained in case the creator appeals.

A separate **appeal flow** reuses the same components — see §5 (API surface) and §6 (diagram).

---

## 2. Detection Signals (chosen before any code)

The pipeline uses **two genuinely independent signals**: one semantic, one structural. They are independent because they look at different properties of the text, so agreement between them is meaningful evidence and disagreement is a useful uncertainty signal.

### Signal 1 — LLM Classifier (Groq, semantic)

- **What it measures:** Whether the text *reads* as AI-generated when judged holistically — tone, fluency, "voice," topic-handling, and the subtle over-politeness/over-structure that large models tend to produce. Output: `p_ai ∈ [0, 1]` + rationale.
- **Why the property differs between human and AI:** AI prose is typically coherent, evenly hedged, and tonally neutral; human prose carries idiosyncratic voice, opinion, and irregular emphasis. An LLM is good at recognizing the gestalt of "this sounds generated."
- **Blind spot:** It can be **fooled by framing and by lightly edited AI output**. A human writing in a polished, formal register can read as "AI," and AI text that a human has lightly edited can read as "human." It is also non-deterministic and can drift between calls.

### Signal 2 — Stylometric Heuristics (pure Python, structural)

- **What it measures:** Quantifiable regularity of the text:
  - **Sentence-length variance** — humans vary sentence length far more than AI.
  - **Type-token ratio (TTR)** — vocabulary diversity; AI often reuses a tighter vocabulary band.
  - **Punctuation density** — distribution and rate of punctuation marks.
  - These combine into a single `style_score ∈ [0, 1]`.
- **Why the property differs:** AI text is statistically *smoother* — uniform sentence rhythm and steady vocabulary. Human writing is bursty and irregular.
- **Blind spot:** It is **length-sensitive and genre-blind**. On very short inputs the statistics are unreliable (a two-sentence note has almost no variance to measure). It will mis-score legitimately uniform human writing — a formal abstract, a poem built on deliberate repetition, or a technical spec — as "AI-like," because it only sees structure, not meaning.

> **Why this pairing is sound:** one signal is semantic and one is structural, so they fail in *different* situations. The stylometric blind spot (formal/uniform human writing) is exactly where the LLM's holistic read can rescue the verdict, and vice-versa. Single-signal detection would have no such cross-check.

---

## 3. The False-Positive Problem (traced through the system)

**On a writing platform, labeling a human's work as AI-generated is the worst outcome** — it accuses a real creator of fraud. The system is therefore deliberately biased *against* asserting "AI."

**Scenario:** A human poet submits a piece built on heavy repetition and simple vocabulary.

1. `POST /submit` → signal 1 (LLM) reads it as human-ish (`p_ai ≈ 0.35`) because the voice feels genuine.
2. Signal 2 (stylometric) sees low sentence-length variance and low TTR from the repetition → scores it AI-like (`style_score ≈ 0.75`). **This is the false-positive risk firing.**
3. `combine_signals()` sees the two signals **disagree**. Rather than averaging to a misleading mid-high "likely AI," the disagreement adjustment pulls the combined confidence toward the **uncertain** band (`p_ai ≈ 0.55`).
4. `make_label()` returns the **uncertain** label — *not* an accusatory "AI-generated" label. The reader is told the system isn't sure, which is honest.
5. If the creator still disputes it, they file `POST /appeal` with their reasoning; status flips to `under_review` and the appeal is logged beside the original decision for a human reviewer.

**Design consequence (feeds Milestone 2):** the "likely AI" threshold is set **high** (0.80) so borderline cases land in "uncertain" instead of a false accusation, and signal disagreement actively widens uncertainty. The appeal path is the safety net when scoring still gets it wrong.

---

## 4. API Surface (contract sketch — no code yet)

| Method & Path | Accepts | Returns |
|---------------|---------|---------|
| `POST /submit` | `{ "text": str, "creator_id": str }` | `{ "content_id": uuid, "attribution": "likely_ai"\|"uncertain"\|"likely_human", "confidence": float, "label": str }` |
| `POST /appeal` | `{ "content_id": uuid, "creator_reasoning": str }` | `{ "content_id": uuid, "status": "under_review", "message": str }` |
| `GET /log` | — | `{ "entries": [ <structured audit records, most recent first> ] }` |

- `POST /submit` is **rate limited**; `GET /log` exists for documentation/grading visibility (would require auth in production).
- A `409`/`404` is returned by `/appeal` if the `content_id` is unknown.

---

## 5. Confidence Scoring Approach (M1 decision; calibrated in M4)

- **Score meaning:** `confidence` = `p_ai`, the system's estimate that the text is AI-generated, in `[0, 1]`. Higher = more AI-like.
- **Combination:** weighted blend favoring the holistic signal — `p_ai = 0.6 * llm_score + 0.4 * style_score` — then a **disagreement adjustment**: when `|llm_score − style_score|` is large, the result is pulled toward 0.5 (uncertain).
- **Label thresholds (asymmetric, to suppress false positives):**

  | Combined `p_ai` | Attribution | Label variant |
  |-----------------|-------------|---------------|
  | `≥ 0.80` | `likely_ai` | High-confidence AI |
  | `0.30 – 0.80` | `uncertain` | Uncertain |
  | `≤ 0.30` | `likely_human` | High-confidence human |

  The "AI" band requires strong evidence (≥ 0.80); everything borderline degrades to "uncertain" rather than accusing a human.

*(Exact label text written out in Milestone 2 / the README. M1 fixes the bands; M4 calibrates the numbers against real test inputs.)*

---

## 6. Architecture Diagram

### Submission flow

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

### Appeal flow

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

**Narrative:** The submission flow takes raw text, runs it through two independent detection signals, blends them into one calibrated confidence score, turns that score into a reader-facing transparency label, logs the full decision, and returns the verdict with a `content_id`. The appeal flow takes that `content_id`, flips the content's status to `under_review`, and logs the creator's reasoning beside the original decision so a human reviewer can act on it — no automated reclassification.

---

## 7. File Structure (mirrors the RepairSafe Lab 4 starter layout)

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

## ✅ Milestone 1 Checkpoint — Verification

- [x] **Can describe the full path of a submission, naming every component.** → §1 (8 stages, `app.py → detector.py → labeler.py → auditor.py → app.py`).
- [x] **Two detection signals chosen, with what each captures and what it misses.** → §2 (LLM semantic + stylometric structural, each with an explicit blind spot).
- [x] **Rough list of API endpoints.** → §4 (`POST /submit`, `POST /appeal`, `GET /log`).
- [x] **Diagram showing both submission and appeal flows.** → §6 (two ASCII diagrams, arrows labeled with raw text / signal scores / combined score / label text / status).
