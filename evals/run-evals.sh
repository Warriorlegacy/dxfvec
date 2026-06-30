#!/usr/bin/env bash
# run-evals.sh — run all eval cases against a pinned agent version and collect verdicts
# Usage: bash evals/run-evals.sh
# Requires: IDS.env and .env populated, ANTHROPIC_API_KEY set

set -euo pipefail

set -a; source .env; set +a
set -a; source IDS.env; set +a

BASE=https://api.anthropic.com/v1
H=(-H "x-api-key: $ANTHROPIC_API_KEY"
   -H "anthropic-version: 2023-06-01"
   -H "anthropic-beta: managed-agents-2026-04-01"
   -H "content-type: application/json")

RESULTS_FILE="evals/results-v${AGENT_VERSION}.json"
echo "[]" > "$RESULTS_FILE"

for CASE_DIR in evals/case-*/; do
  CASE=$(basename "$CASE_DIR")
  IMAGE="$CASE_DIR/test_drawing.png"

  if [ ! -f "$IMAGE" ]; then
    echo "⚠️  No test_drawing.png in $CASE_DIR — run generate_test.py first"
    continue
  fi

  echo "▶️  Running eval: $CASE (agent v$AGENT_VERSION)"

  # Upload image
  FILE_ID=$(curl -sS "$BASE/files" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "anthropic-beta: managed-agents-2026-04-01" \
    -H "files-api-2025-04-14" \
    -F "file=@$IMAGE" \
    | python3 -c "import json,sys; print(json.JSONDecoder(strict=False).decode(sys.stdin.read())['id'])")

  # Create session (pin to current agent version)
  SESSION_ID=$(curl -sS --fail-with-body "$BASE/sessions" "${H[@]}" \
    -d "{\"agent\":{\"type\":\"agent\",\"id\":\"$AGENT_ID\",\"version\":$AGENT_VERSION},\"environment_id\":\"$ENV_ID\",\"title\":\"eval-$CASE\",\"resources\":[{\"type\":\"file\",\"file_id\":\"$FILE_ID\"}]}" \
    | python3 -c "import json,sys; print(json.JSONDecoder(strict=False).decode(sys.stdin.read())['id'])")

  # Kickoff
  curl -sS --fail-with-body "$BASE/sessions/$SESSION_ID/events" "${H[@]}" \
    -d "$(cat kickoff.json)" > /dev/null

  # Poll until done (max 15 min)
  DONE=0
  for i in $(seq 1 60); do
    sleep 15
    STATUS=$(curl -sS "$BASE/sessions/$SESSION_ID" "${H[@]}" \
      | python3 -c "import json,sys; d=json.JSONDecoder(strict=False).decode(sys.stdin.read()); print(d['status'])")
    if [ "$STATUS" = "idle" ]; then DONE=1; break; fi
  done

  # Collect verdict
  VERDICT=$(curl -sS "$BASE/sessions/$SESSION_ID" "${H[@]}" \
    | python3 -c "
import json, sys
d = json.JSONDecoder(strict=False).decode(sys.stdin.read())
evals = d.get('outcome_evaluations', [])
result = evals[-1].get('result', 'no_verdict') if evals else 'no_verdict'
print(result)
")

  echo "  ✅ $CASE → $VERDICT"

  # Append to results JSON
  python3 -c "
import json
results = json.load(open('$RESULTS_FILE'))
results.append({'case': '$CASE', 'session_id': '$SESSION_ID', 'verdict': '$VERDICT', 'agent_version': $AGENT_VERSION})
json.dump(results, open('$RESULTS_FILE', 'w'), indent=2)
"
done

echo ""
echo "📊  Results written to $RESULTS_FILE"
cat "$RESULTS_FILE"
