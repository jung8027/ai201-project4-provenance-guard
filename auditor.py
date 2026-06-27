"""Structured audit logging (planning.md §4, specs/auditor-spec.md).

The audit log is an append-only JSONL file. Submissions are logged with event "submission";
appeals append an event "appeal" record carrying status "under_review" beside a snapshot of the
original decision. The current status of a content_id is the status on its most recent entry.
"""
import datetime
import json
import os

import config


def _ensure_log_dir():
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _read_all():
    """Return every audit record in file order (oldest first)."""
    if not os.path.exists(config.LOG_PATH):
        return []
    records = []
    with open(config.LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _append(record):
    _ensure_log_dir()
    with open(config.LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_submission(record):
    """Append one structured submission record (a dict) as a JSON line to the audit log."""
    record.setdefault("event", "submission")
    _append(record)
    # Mirror the RepairSafe [LOGGED] terminal line for visibility during testing.
    print(
        f"[LOGGED] attribution={record.get('attribution'):<13} "
        f"confidence={record.get('confidence')} "
        f"content_id={record.get('content_id')}"
    )


def find_submission(content_id):
    """Return the original submission record for a content_id, or None if not found."""
    for record in _read_all():
        if record.get("content_id") == content_id and record.get("event") == "submission":
            return record
    return None


def log_appeal(content_id, creator_reasoning):
    """Log an appeal beside the original decision and flip status to under_review.

    Returns the appeal record, or None if the content_id is unknown. No automated
    reclassification — a human reviewer acts on the queued entry.
    """
    original = find_submission(content_id)
    if original is None:
        return None

    record = {
        "event": "appeal",
        "content_id": content_id,
        "creator_id": original.get("creator_id"),
        "timestamp": _utc_now(),
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "original_attribution": original.get("attribution"),
        "original_confidence": original.get("confidence"),
        "llm_score": original.get("llm_score"),
        "style_score": original.get("style_score"),
    }
    _append(record)
    print(f"[APPEAL] content_id={content_id} -> status=under_review")
    return record


def get_log(limit=None, status=None):
    """Return audit records, most recent first. Optionally filter by status / cap to `limit`.

    A `status` filter (e.g. "under_review") yields the human-reviewer appeal queue.
    """
    entries = _read_all()
    entries.reverse()  # most recent first
    if status is not None:
        entries = [e for e in entries if e.get("status") == status]
    if limit is not None:
        entries = entries[:limit]
    return entries
