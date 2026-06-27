"""Provenance Guard — Flask app and API endpoints.

Mirrors the orchestration role of app.py in the RepairSafe Lab 4 starter.

Milestone 3: POST /submit (rate limiting added in M5), the first detection signal wired in,
structured audit logging, and GET /log. Confidence and label are placeholders until
Milestones 4 (combined confidence score) and 5 (transparency label).
"""
import datetime
import uuid

from flask import Flask, jsonify, request

import auditor
import detector

app = Flask(__name__)

# Placeholders until the later milestones replace them.
PLACEHOLDER_LABEL = "Label pending (implemented in Milestone 5)"


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@app.route("/submit", methods=["POST"])
def submit():
    body = request.get_json(silent=True) or {}
    text = body.get("text")
    creator_id = body.get("creator_id")

    if not text or not creator_id:
        return jsonify({"error": "Both 'text' and 'creator_id' are required."}), 400

    content_id = str(uuid.uuid4())

    # --- Signal 1: Groq LLM classifier ---
    signal1 = detector.llm_signal(text)
    llm_score = signal1["p_ai"]

    # In M3 the attribution comes from Signal 1 alone; confidence is a placeholder for the
    # combined score (M4) and the label is a placeholder for the transparency label (M5).
    attribution = detector.score_to_attribution(llm_score)
    confidence = llm_score  # placeholder — replaced by combine_signals() in M4

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": _utc_now(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "llm_rationale": signal1["rationale"],
        "status": "classified",
    }
    auditor.log_submission(record)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": PLACEHOLDER_LABEL,
    })


@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": auditor.get_log()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
