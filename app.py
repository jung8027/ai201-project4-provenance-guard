"""Provenance Guard — Flask app and API endpoints.

Mirrors the orchestration role of app.py in the RepairSafe Lab 4 starter.

Endpoints: POST /submit (two-signal detection + confidence + transparency label, rate limited),
POST /appeal (contest a classification), GET /log (audit log / appeal queue).
"""
import datetime
import uuid

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import auditor
import config
import detector
import labeler

app = Flask(__name__)

# Rate limiting (M5). In-memory storage is fine for local dev; default_limits=[] so only the
# routes we explicitly decorate are limited.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@app.route("/submit", methods=["POST"])
@limiter.limit(config.SUBMIT_RATE_LIMIT)
def submit():
    body = request.get_json(silent=True) or {}
    text = body.get("text")
    creator_id = body.get("creator_id")

    if not text or not creator_id:
        return jsonify({"error": "Both 'text' and 'creator_id' are required."}), 400

    content_id = str(uuid.uuid4())

    # --- Signal 1: Groq LLM classifier (semantic) ---
    signal1 = detector.llm_signal(text)
    llm_score = signal1["p_ai"]

    # --- Signal 2: stylometric heuristics (structural) ---
    signal2 = detector.stylometric_signal(text)
    style_score = signal2["style_score"]

    # --- Confidence scoring: combine both signals into one calibrated p_ai (M4) ---
    combined = detector.combine_signals(llm_score, style_score, signal2["reliable"])
    confidence = combined["p_ai"]
    attribution = combined["attribution"]

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": _utc_now(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "style_score": style_score,
        "style_reliable": signal2["reliable"],
        "llm_rationale": signal1["rationale"],
        "status": "classified",
    }
    auditor.log_submission(record)

    # --- Transparency label: varies by confidence band (M5) ---
    label = labeler.make_label(attribution, confidence)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id")
    creator_reasoning = body.get("creator_reasoning")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "Both 'content_id' and 'creator_reasoning' are required."}), 400

    record = auditor.log_appeal(content_id, creator_reasoning)
    if record is None:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received. The classification is now under review by a human.",
    })


@app.route("/log", methods=["GET"])
def log():
    # Optional ?status=under_review yields the human-reviewer appeal queue.
    status = request.args.get("status")
    return jsonify({"entries": auditor.get_log(status=status)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
