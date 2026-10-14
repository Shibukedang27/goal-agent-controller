#!/usr/bin/env bash
# Small demo: starts the API in mock mode (no API keys) and sends one goal.
# Usage: ./demo.sh  (run after `pip install -e '.[dev]'`)
set -euo pipefail
PORT="${PORT:-8000}"
unset OPENAI_API_KEY  # force the deterministic MockProvider

uvicorn agi_prototype.api:app --port "$PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT

# wait for the server to come up
for _ in $(seq 1 20); do
  curl -s "http://127.0.0.1:$PORT/health" >/dev/null && break
  sleep 0.5
done

echo "\$ curl -s localhost:$PORT/health"
curl -s "http://127.0.0.1:$PORT/health"; echo; echo

GOAL="${1:-Write a short study plan for learning SQL joins}"
echo "\$ curl -s -X POST localhost:$PORT/runs -d '{\"goal\": \"$GOAL\"}'"
curl -s -X POST "http://127.0.0.1:$PORT/runs" \
  -H 'Content-Type: application/json' \
  -d "{\"goal\": \"$GOAL\", \"max_learning_rounds\": 2}" \
| python3 -c '
import json, sys
d = json.load(sys.stdin)
short = {
    "status": d["status"],
    "state": d["state"],
    "requirements": [r["name"] for r in d["requirements"]],
    "selected_tools": d["selected_tools"],
    "artifact_type": d["execution"]["output"]["artifact_type"],
    "verification": {"score": d["verification"]["score"], "passed": d["verification"]["passed"]},
    "failures": d["failures"],
    "trace_steps": len(d["trace"]),
}
print(json.dumps(short, indent=2))
print("\n--- artifact ---")
print(d["execution"]["output"]["content"])
'
