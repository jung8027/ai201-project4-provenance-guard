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
        # label is still a placeholder until Milestone 5
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
