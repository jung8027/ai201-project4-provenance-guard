"""Structured audit logging (planning.md §4, specs/auditor-spec.md).

Milestone 3: log_submission() appends one structured JSON line per submission to
logs/audit.jsonl, and get_log() reads recent entries back for GET /log.
log_appeal() / status updates arrive in Milestone 5.
"""
import json
import os

import config


def _ensure_log_dir():
    os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)


def log_submission(record):
    """Append one structured audit record (a dict) as a JSON line to the audit log."""
    _ensure_log_dir()
    with open(config.LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    # Mirror the RepairSafe [LOGGED] terminal line for visibility during testing.
    print(
        f"[LOGGED] attribution={record.get('attribution'):<13} "
        f"confidence={record.get('confidence')} "
        f"content_id={record.get('content_id')}"
    )


def get_log(limit=None):
    """Return audit records, most recent first. Optionally cap to `limit` entries."""
    if not os.path.exists(config.LOG_PATH):
        return []
    entries = []
    with open(config.LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    entries.reverse()  # most recent first
    if limit is not None:
        entries = entries[:limit]
    return entries
