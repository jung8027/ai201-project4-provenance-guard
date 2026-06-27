# Spec: audit log & content status

**File:** `auditor.py`
**Status:** Implemented (Milestones 3 & 5) — Implementation Notes filled in below

---

## Purpose

Record every attribution decision and every appeal to a structured audit log, and track the
status of each piece of content. Audit logs are a production requirement: they are how systematic
classifier errors are caught after deployment, how a disputed decision is reconstructed, and how
the system demonstrates accountability. In this project the log is also the canonical evidence
graders read and the storage backing the appeals workflow.

---

## Input / Output Contract

### `log_submission(record)` *(Milestone 3)*

| Parameter | Type | Description |
|-----------|------|-------------|
| `record` | `dict` | The submission decision (see fields below) |

**Output:** `None` — appends one JSON line to `logs/audit.jsonl` and prints a `[LOGGED]` line.
Sets `record["event"] = "submission"` if not already present.

### `log_appeal(content_id, creator_reasoning)` *(Milestone 5)*

| Parameter | Type | Description |
|-----------|------|-------------|
| `content_id` | `str` | The id from the original `/submit` response |
| `creator_reasoning` | `str` | The creator's free-text justification |

**Output:** the appended appeal `dict`, or `None` if the `content_id` is unknown (drives the `404`).

### `find_submission(content_id)` → `dict | None`

Returns the original submission record for a `content_id`, or `None`.

### `get_log(limit=None, status=None)` → `list[dict]`

Returns records most-recent-first; optional `status` filter yields the reviewer appeal queue;
optional `limit` caps the count.

---

## Design Decisions

---

### Submission record fields

| Field | Type | Description |
|-------|------|-------------|
| `"event"` | `str` | `"submission"` — distinguishes row type from appeals |
| `"content_id"` | `str` | UUID assigned at submission; the join key for appeals |
| `"creator_id"` | `str` | Who submitted the content |
| `"timestamp"` | `str` | ISO 8601 UTC |
| `"attribution"` | `str` | `likely_ai` / `uncertain` / `likely_human` |
| `"confidence"` | `float` | Combined `p_ai` |
| `"llm_score"` | `float` | Signal 1 raw score |
| `"style_score"` | `float` | Signal 2 raw score |
| `"style_reliable"` | `bool` | Whether the stylometric signal was reliable for this text |
| `"llm_rationale"` | `str` | The LLM's one-line justification |
| `"status"` | `str` | `"classified"` at submission |

**Why log both individual signal scores, not just the combined confidence:**

`llm_score` and `style_score` — when a decision looks wrong, the combined score alone can't tell you
*which* signal misbehaved. Logging both makes the failure diagnosable at a glance: a `likely_ai`
verdict driven by `style_score=0.9` while `llm_score=0.2` is a stylometric false positive (probably
formal or repetitive human writing), and you can see that without re-running anything.

`style_reliable` — a `style_score` from a 15-word submission means something completely different
from one computed over 300 words. Without the flag, a reviewer can't tell whether the structural
signal was trustworthy for that decision.

---

### Appeal record fields

| Field | Type | Description |
|-------|------|-------------|
| `"event"` | `str` | `"appeal"` |
| `"content_id"` | `str` | Same id as the original submission |
| `"creator_id"` | `str` | Carried over from the original submission |
| `"timestamp"` | `str` | ISO 8601 UTC of the appeal |
| `"status"` | `str` | `"under_review"` |
| `"appeal_reasoning"` | `str` | The creator's justification |
| `"original_attribution"` | `str` | Snapshot of the original verdict |
| `"original_confidence"` | `float` | Snapshot of the original score |
| `"llm_score"` / `"style_score"` | `float` | Snapshot of the original signal scores |

The appeal record carries a **snapshot of the original decision** so a human reviewer opening the
queue has full context in one record, without cross-referencing the original submission line.

---

### Append-only status model

```
The log is append-only JSONL. An appeal does NOT mutate the original submission row; it appends a
new "appeal" record carrying status "under_review". The CURRENT status of a content_id is the
status on its most-recent entry.

Why append-only rather than rewriting the original row:
  - It preserves a complete audit trail — you can see both the original classification and the
    appeal, in order, rather than losing the original state.
  - JSONL is designed for append, not in-place edit; rewriting a line means rewriting the file.
  - The project spec said to update status "in whatever storage you're using" — here the log IS
    the storage, and "most-recent-entry-wins" is a clean, standard event-sourcing pattern.
```

---

### The `event` field

```
Every record carries event = "submission" | "appeal". This is what lets find_submission() locate
the original decision for a content_id (it filters to event == "submission"), and what lets a
reader tell the two row shapes apart. It was not in the original Milestone 3 record shape; it was
added in Milestone 5 when appeals introduced a second row type.
```

---

### The appeal queue (`get_log(status=...)`)

```
GET /log?status=under_review returns only records whose status is "under_review" — i.e. the queue
a human reviewer works from. This is a thin filter over the same log rather than a separate store,
which keeps a single source of truth. In production this endpoint would require auth; here it is
open for documentation and grading visibility.
```

---

### Directory creation

```
_ensure_log_dir() calls os.makedirs(dirname(LOG_PATH), exist_ok=True) before every write.
exist_ok=True makes it safe to call on every invocation — no conditional, no race. Without it the
first write on a fresh clone raises FileNotFoundError, because Python's open() will not create
intermediate directories. (logs/.gitkeep keeps the directory tracked in git, but the directory must
still exist at runtime.)
```

---

### Console output

```
log_submission prints:
  [LOGGED] attribution={attribution:<13} confidence={confidence} content_id={content_id}

log_appeal prints:
  [APPEAL] content_id={content_id} -> status=under_review

The terminal lines give immediate visibility during testing and the demo without having to open
the log file; the structured JSONL is the durable record.
```

---

## Implementation Notes

**The actual log file content after a clean run (3 submissions, one per band, + 1 appeal):**

```
{"content_id": "514eb07f-e7a8-4ac9-99f3-7cc7d8fd6897", "creator_id": "u-templated", "timestamp": "2026-06-27T01:40:46.247068+00:00", "attribution": "likely_ai", "confidence": 0.8171, "llm_score": 0.9, "style_score": 0.6927, "style_reliable": true, "llm_rationale": "The text exhibits an overly uniform and formulaic structure.", "status": "classified", "event": "submission"}
{"content_id": "5001ed6e-8f1a-4653-b3ee-d3d35bc3e742", "creator_id": "u-human", "timestamp": "2026-06-27T01:40:46.504034+00:00", "attribution": "likely_human", "confidence": 0.1603, "llm_score": 0.2, "style_score": 0.1007, "style_reliable": true, "llm_rationale": "The text's informal tone, use of colloquial expressions, and personal opinion suggest human authorship.", "status": "classified", "event": "submission"}
{"content_id": "d6337685-3f6d-431e-bf7f-bb6c86b86ae1", "creator_id": "u-econ", "timestamp": "2026-06-27T01:40:46.860801+00:00", "attribution": "uncertain", "confidence": 0.7688, "llm_score": 0.8, "style_score": 0.5921, "style_reliable": false, "llm_rationale": "The text exhibits a formal and overly uniform tone, typical of AI-generated content.", "status": "classified", "event": "submission"}
{"event": "appeal", "content_id": "5001ed6e-8f1a-4653-b3ee-d3d35bc3e742", "creator_id": "u-human", "timestamp": "2026-06-27T01:40:46.897210+00:00", "status": "under_review", "appeal_reasoning": "I wrote this review myself after eating there; the casual tone is just how I write.", "original_attribution": "likely_human", "original_confidence": 0.1603, "llm_score": 0.2, "style_score": 0.1007}
```

**One field you'd add if this were a real production system handling 10,000 submissions per day:**

```
"creator_id_history" / a rolling per-creator appeal count. At scale, a single creator who appeals
every "likely_ai" verdict within minutes of submitting is a different signal from a first-time
appeal — it may indicate either a miscalibrated detector for that creator's genuine style, or
someone gaming the appeal path. Per-decision records make that pattern invisible; a per-creator
aggregate (appeals filed, overturn rate) surfaces it. This mirrors the session_id reasoning from
the RepairSafe auditor spec: individual events aren't enough, you need to detect sequences.
```
