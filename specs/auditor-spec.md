# Spec — auditor.py (Milestones 3 & 5)

Structured audit logging and content-status tracking.

## `log_submission(record) -> None`  (M3)
Appends one JSON line to `logs/audit.jsonl`. A record contains at minimum:

```json
{
  "content_id": "uuid",
  "creator_id": "test-user-1",
  "timestamp": "2026-06-26T14:32:10.123Z",
  "attribution": "likely_ai",
  "confidence": 0.78,
  "llm_score": 0.81,
  "style_score": 0.74,
  "status": "classified"
}
```

## `log_appeal(content_id, creator_reasoning) -> None`  (M5)
- Flips the content's status `classified → under_review`.
- Appends an appeal record beside the original decision, with `appeal_reasoning` populated.

## `get_log(limit) -> list`
- Returns the most recent records (for `GET /log`).

Format must be structured (JSON / JSONL), never `print()` statements.
