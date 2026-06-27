#!/usr/bin/env bash
#
# Provenance Guard — Portfolio Demo Walkthrough
#
# Structured for video recording. Covers every graded feature in the rubric:
#
#   Feature 1: Content submission endpoint — structured JSON response with attribution,
#               confidence score, and transparency label text.
#   Feature 2: Multi-signal detection pipeline — LLM (semantic) + stylometric (structural)
#               scores shown individually alongside the combined score.
#   Feature 3: Confidence scoring with uncertainty — high-confidence AI, uncertain, and
#               high-confidence human cases to show the full range.
#   Feature 4: Transparency label — three distinct plain-language variants, different
#               text per band (not just a different number).
#   Feature 5: Appeals workflow — appeal submitted with reasoning; status updated to
#               "under_review" and visible in the audit log.
#   Feature 6: Rate limiting — 429 response on the 11th POST /submit within a minute.
#   Feature 7: Audit log — 3+ structured JSON entries each showing attribution,
#               confidence, and timestamp; appeal alongside original classification.
#
# Requires GROQ_API_KEY in .env. Starts and stops its own Flask server.
# Usage:  ./demo.sh

set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
BASE=http://localhost:5000
SERVER_PID=""
SERVER_LOG="$(mktemp)"

cleanup() { [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

# ── formatting helpers ────────────────────────────────────────────────────────
hr()     { printf '%.0s─' $(seq 1 78); echo; }
banner() { echo; hr; printf '  %s\n' "$1"; hr; }
note()   { printf '\n  [narrate]  %s\n\n' "$1"; }
pp()     { "$PY" -m json.tool; }

start_server() {
  "$PY" app.py >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "$BASE/log" 2>/dev/null && return 0
    sleep 0.5
  done
  echo "Server failed to start. Log:"; cat "$SERVER_LOG"; exit 1
}

pause() { printf '\n  Press [Enter] to continue…'; read -r; echo; }

restart_server() { cleanup; SERVER_PID=""; sleep 1; start_server; }

submit() {   # $1=text  $2=creator_id  → prints raw JSON response
  curl -s -X POST "$BASE/submit" -H "Content-Type: application/json" \
    -d "{\"text\": $("$PY" -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1"), \
        \"creator_id\": \"$2\"}"
}

latest_log_entry() {   # prints the single most-recent audit.jsonl entry, pretty
  curl -s "$BASE/log" \
    | "$PY" -c 'import sys,json; e=json.load(sys.stdin)["entries"]; print(json.dumps(e[0], indent=2)) if e else print("(empty)")'
}

# ── startup ───────────────────────────────────────────────────────────────────
banner "PROVENANCE GUARD  ·  Portfolio Demo"
note "This is Provenance Guard — a Flask API that classifies submitted text as \
human-written or AI-generated using two independent signals, then shows a \
plain-language transparency label. Let me walk through each graded feature."
echo "  Starting Flask development server…"
start_server
echo "  Server running (pid $SERVER_PID)  →  $BASE"

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURE 1  ·  Content Submission Endpoint  (POST /submit)"
# ═════════════════════════════════════════════════════════════════════════════
note "Send a text to POST /submit with a creator_id. The response is structured \
JSON that includes an attribution result, a calibrated confidence score, and \
the full transparency label text."

AI_TEXT="Effective time management is a critical skill in the modern workplace. \
First, it is important to prioritize tasks based on their relative urgency. \
Second, it is essential to eliminate distractions in order to maintain focus. \
Third, it is beneficial to take regular breaks to sustain productivity. \
Finally, it is advisable to review progress at the end of each day. \
In conclusion, these strategies will significantly improve overall efficiency."

echo; echo "  POST /submit  →  highly-templated AI essay:"
AI_RESP=$(submit "$AI_TEXT" "demo-ai")
echo "$AI_RESP" | pp
AI_CID=$("$PY" -c 'import sys,json;print(json.load(sys.stdin)["content_id"])' <<< "$AI_RESP")

note "The response has four fields: content_id (a UUID), attribution (the \
verdict band), confidence (the combined p_ai score), and label (the \
plain-language transparency text). All three pieces the rubric requires are \
here in one call."

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURE 4  ·  Transparency Label  (three distinct variants)"
# ═════════════════════════════════════════════════════════════════════════════
note "The label text changes entirely between bands — it is not the same string \
with a different number. Here are all three variants across three submissions."

HUMAN_TEXT="ok so i finally tried that new ramen place downtown and honestly? \
underwhelming. the broth was fine but they put WAY too much sodium in it and \
i was thirsty for like three hours after. probably wont go back unless someone \
drags me there"

FORMAL_TEXT="The relationship between monetary policy and asset price inflation \
has been extensively studied in the literature. Central banks face a \
fundamental tension between their mandate for price stability and the \
unintended consequences of prolonged low interest rates on wealth distribution."

echo; echo "  Label for HIGH-CONFIDENCE AI text:"
echo "$AI_RESP" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["label"])'

echo; echo "  Submitting casual human review…"
HUMAN_RESP=$(submit "$HUMAN_TEXT" "demo-human")
HUMAN_CID=$("$PY" -c 'import sys,json;print(json.load(sys.stdin)["content_id"])' <<< "$HUMAN_RESP")
echo; echo "  Label for HIGH-CONFIDENCE HUMAN text:"
echo "$HUMAN_RESP" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["label"])'

echo; echo "  Submitting formal academic paragraph (false-positive guard)…"
FORMAL_RESP=$(submit "$FORMAL_TEXT" "demo-formal")
echo; echo "  Label for UNCERTAIN text:"
echo "$FORMAL_RESP" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["label"])'

note "Three completely different strings — not a template with a score plugged in. \
The uncertain variant explicitly declines to draw a conclusion so it does not \
read as a quiet accusation."

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURES 2 & 3  ·  Multi-Signal Detection  +  Confidence Scoring"
# ═════════════════════════════════════════════════════════════════════════════
note "There are two independent signals. Signal 1 is a Groq LLM call \
(llama-3.3-70b-versatile) that judges tone, voice, and structure holistically — \
a semantic read. Signal 2 is a pure-Python stylometric analysis that measures \
sentence-length burstiness (coefficient of variation), type-token ratio, and \
punctuation density — a structural read. Both are logged per submission."

echo; echo "  Audit log entry for the HIGH-CONFIDENCE AI submission:"
echo "  (shows llm_score, style_score, and combined confidence together)"
curl -s "$BASE/log" \
  | "$PY" -c "
import sys, json
entries = json.load(sys.stdin)['entries']
target = [e for e in entries if e.get('content_id') == '$AI_CID']
if target:
    e = target[0]
    print(json.dumps({
        'attribution':   e['attribution'],
        'confidence':    e['confidence'],
        'llm_score':     e['llm_score'],
        'style_score':   e['style_score'],
        'style_reliable': e['style_reliable'],
        'llm_rationale': e['llm_rationale'],
    }, indent=2))
"

echo; echo "  Audit log entry for the HIGH-CONFIDENCE HUMAN submission:"
curl -s "$BASE/log" \
  | "$PY" -c "
import sys, json
entries = json.load(sys.stdin)['entries']
target = [e for e in entries if e.get('content_id') == '$HUMAN_CID']
if target:
    e = target[0]
    print(json.dumps({
        'attribution':   e['attribution'],
        'confidence':    e['confidence'],
        'llm_score':     e['llm_score'],
        'style_score':   e['style_score'],
        'style_reliable': e['style_reliable'],
        'llm_rationale': e['llm_rationale'],
    }, indent=2))
"

note "Signal 1 (llm_score) and Signal 2 (style_score) are both stored. They are \
combined as: p_ai = 0.6 × llm + 0.4 × style. When the two signals strongly \
disagree (differ by more than 0.4), the combined score is pulled toward 0.5 — \
honest uncertainty instead of a confident wrong answer. The AI submission scores \
high on both; the human submission scores low on both. Compare the confidence \
values to see the full range."

echo; echo "  Confidence comparison across the three submissions:"
curl -s "$BASE/log" \
  | "$PY" -c "
import sys, json
entries = json.load(sys.stdin)['entries']
subs = [e for e in entries if e.get('event') == 'submission'][:3]
print('  {:<16}  {:>10}  {:>10}  {:>10}'.format('attribution', 'confidence', 'llm_score', 'style_score'))
print('  ' + '-'*58)
for e in subs:
    print('  {:<16}  {:>10.4f}  {:>10.4f}  {:>10.4f}'.format(
        e['attribution'], e['confidence'], e['llm_score'], e['style_score']))
"

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURE 5  ·  Appeals Workflow"
# ═════════════════════════════════════════════════════════════════════════════
note "A creator can dispute a classification. They POST to /appeal with their \
content_id and a written explanation. The API creates a new log entry with \
status under_review — the original entry is untouched (append-only log)."

echo; echo "  POST /appeal  →  human creator contests their classification:"
curl -s -X POST "$BASE/appeal" -H "Content-Type: application/json" \
  -d "{\"content_id\": \"$HUMAN_CID\", \
       \"creator_reasoning\": \"I wrote this review myself after eating there; \
the casual tone is just how I write.\"}" | pp

echo; echo "  GET /log?status=under_review  →  the human reviewer queue:"
curl -s "$BASE/log?status=under_review" | pp

echo; echo "  Appeal with an unknown content_id  →  HTTP 404:"
curl -s -w "\n  HTTP status: %{http_code}\n" -X POST "$BASE/appeal" \
  -H "Content-Type: application/json" \
  -d '{"content_id": "does-not-exist", "creator_reasoning": "test"}' | head -1
curl -s -o /dev/null -w "  HTTP status: %{http_code}\n" -X POST "$BASE/appeal" \
  -H "Content-Type: application/json" \
  -d '{"content_id": "does-not-exist", "creator_reasoning": "test"}'

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURE 7  ·  Audit Log  (GET /log)"
# ═════════════════════════════════════════════════════════════════════════════
note "Every submission and every appeal is stored as a structured JSON record in \
an append-only JSONL file. The GET /log endpoint returns them most-recent-first. \
Here are the four records from this session — three submissions and one appeal."

echo; echo "  All log entries — attribution, confidence, timestamp, and event type:"
curl -s "$BASE/log" \
  | "$PY" -c "
import sys, json
entries = json.load(sys.stdin)['entries']
for e in entries:
    row = {
        'event':       e.get('event'),
        'attribution': e.get('attribution') or e.get('original_attribution'),
        'confidence':  e.get('confidence') or e.get('original_confidence'),
        'status':      e.get('status'),
        'timestamp':   e.get('timestamp'),
        'content_id':  e.get('content_id'),
    }
    print(json.dumps(row, indent=2))
    print()
"

note "Each entry is a proper JSON object with attribution, confidence, and \
timestamp. The appeal row carries event=appeal and the original scores as a \
snapshot — a reviewer can see the full context without cross-referencing the \
submission row."

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "FEATURE 6  ·  Rate Limiting  (10 requests / minute on POST /submit)"
# ═════════════════════════════════════════════════════════════════════════════
note "POST /submit is rate-limited to 10 requests per minute per IP using \
Flask-Limiter. Let me fire 12 rapid requests and show the 429 responses."

echo "  Restarting server for a clean rate-limit window…"
restart_server
echo "  Server up. Firing 12 rapid POST /submit requests:"
echo

for i in $(seq 1 12); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/submit" \
    -H "Content-Type: application/json" \
    -d '{"text": "rate limit probe", "creator_id": "demo-rl"}')
  if [[ "$code" == "200" ]]; then
    printf "   request %2d  →  %s  ✓ accepted\n" "$i" "$code"
  else
    printf "   request %2d  →  %s  ✗ throttled\n" "$i" "$code"
  fi
done

note "Requests 1 through 10 return 200. Request 11 and beyond return 429 Too \
Many Requests. The limit was set at 10/minute because a writing platform \
submission tool would not fire more than that in normal use — bursts above that \
indicate a script or abuse."

pause
# ═════════════════════════════════════════════════════════════════════════════
banner "DEMO COMPLETE"
# ═════════════════════════════════════════════════════════════════════════════
echo "  Features demonstrated:"
echo "    1. Content submission endpoint — structured JSON with attribution + confidence + label"
echo "    2. Multi-signal detection — LLM (semantic) and stylometric (structural) scores both shown"
echo "    3. Confidence scoring — high-confidence AI, uncertain, and high-confidence human cases"
echo "    4. Transparency label — three distinct plain-language variants"
echo "    5. Appeals workflow — appeal submitted, status under_review, visible in log"
echo "    6. Rate limiting — 429 on request 11+"
echo "    7. Audit log — 3+ structured JSON entries with attribution, confidence, timestamp, and appeal"
echo
echo "  Server shutting down."
