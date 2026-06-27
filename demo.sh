#!/usr/bin/env bash
#
# Provenance Guard — end-to-end feature demo.
#
# Walks through every required feature from the project spec, live against a real server:
#   1. Content submission endpoint
#   2. Multi-signal detection pipeline (Groq LLM + stylometric)
#   3. Confidence scoring with uncertainty
#   4. Transparency label (all three variants)
#   5. Appeals workflow
#   6. Rate limiting
#   7. Audit log
#
# Requires a GROQ_API_KEY in .env (the submission calls Groq). The script starts and stops
# its own Flask server and appends to logs/audit.jsonl (non-destructive).
#
# Usage:  ./demo.sh
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
BASE=http://localhost:5000
SERVER_PID=""
SERVER_LOG="$(mktemp)"

cleanup() { [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

hr()      { printf '%.0s─' $(seq 1 78); echo; }
banner()  { echo; hr; echo "  $1"; hr; }
pp()      { "$PY" -m json.tool; }   # pretty-print JSON from stdin

start_server() {
  "$PY" app.py >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "$BASE/log" 2>/dev/null && return 0
    sleep 0.5
  done
  echo "Server failed to start. Log:"; cat "$SERVER_LOG"; exit 1
}

restart_server() { cleanup; SERVER_PID=""; sleep 1; start_server; }

submit() {  # $1=text  $2=creator_id  -> prints raw JSON response
  curl -s -X POST "$BASE/submit" -H "Content-Type: application/json" \
    -d "{\"text\": $("$PY" -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1"), \"creator_id\": \"$2\"}"
}

banner "PROVENANCE GUARD — feature demo"
echo "Classifies submitted text as human-written or AI-generated, scores confidence,"
echo "shows a transparency label, and handles creator appeals. Starting server…"
start_server
echo "Server up (pid $SERVER_PID)."

# ─────────────────────────────────────────────────────────────────────────────
banner "FEATURES 1-4  ·  Submission · multi-signal detection · confidence · label"
echo "Three submissions chosen to land in each confidence band. Each response shows the"
echo "content_id, attribution, the combined confidence (p_ai), and the transparency label."

echo; echo ">> (a) Strongly templated AI text — expect HIGH confidence AI"
AI_TEXT="Effective time management is a critical skill in the modern workplace. First, it is important to prioritize tasks based on their relative urgency. Second, it is essential to eliminate distractions in order to maintain focus. Third, it is beneficial to take regular breaks to sustain productivity. Finally, it is advisable to review progress at the end of each day. In conclusion, these strategies will significantly improve overall efficiency."
submit "$AI_TEXT" "demo-ai" | pp

echo; echo ">> (b) Casual human review — expect HIGH confidence human"
HUMAN_TEXT="ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. probably wont go back unless someone drags me there"
HUMAN_RESP="$(submit "$HUMAN_TEXT" "demo-human")"
echo "$HUMAN_RESP" | pp
CID="$(echo "$HUMAN_RESP" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["content_id"])')"

echo; echo ">> (c) Formal human paragraph — expect UNCERTAIN (the false-positive guard)"
FORMAL_TEXT="The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates."
submit "$FORMAL_TEXT" "demo-formal" | pp

echo
echo "↳ Two signals (semantic LLM + structural stylometric) are combined into one calibrated"
echo "  score; the same text gets a different label per band — not a constant string."

# ─────────────────────────────────────────────────────────────────────────────
banner "FEATURE 5  ·  Appeals workflow"
echo "The 'human' creator contests the classification using their content_id ($CID)."
curl -s -X POST "$BASE/appeal" -H "Content-Type: application/json" \
  -d "{\"content_id\": \"$CID\", \"creator_reasoning\": \"I wrote this review myself after eating there; the casual tone is just how I write.\"}" | pp

echo; echo "↳ Appeal queue a human reviewer sees  (GET /log?status=under_review):"
curl -s "$BASE/log?status=under_review" | pp

echo; echo ">> Appeal with an unknown content_id returns HTTP 404:"
curl -s -o /dev/null -w "   HTTP %{http_code}\n" -X POST "$BASE/appeal" \
  -H "Content-Type: application/json" \
  -d '{"content_id": "does-not-exist", "creator_reasoning": "test"}'

# ─────────────────────────────────────────────────────────────────────────────
banner "FEATURE 7  ·  Audit log"
echo "Every submission and appeal is a structured JSON record with both signal scores."
echo "Most recent 4 entries (GET /log):"
curl -s "$BASE/log" | "$PY" -c 'import sys,json;[print(json.dumps(e)) for e in json.load(sys.stdin)["entries"][:4]]'

# ─────────────────────────────────────────────────────────────────────────────
banner "FEATURE 6  ·  Rate limiting (10 / minute on POST /submit)"
echo "Restarting the server for a clean rate-limit window, then firing 12 rapid requests."
restart_server
for i in $(seq 1 12); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/submit" \
    -H "Content-Type: application/json" \
    -d '{"text": "short request used only for rate-limit testing", "creator_id": "demo-rl"}')
  printf "   request %2d -> %s\n" "$i" "$code"
done
echo "↳ First 10 succeed (200); the rest are throttled (429)."

banner "DEMO COMPLETE"
echo "All seven required features demonstrated end-to-end. Server shutting down."
