#!/usr/bin/env bash
# Smoke test for the deployed staging backend. Hits /recommend with a minimal
# valid payload and asserts HTTP 200 + a "results" key. See skills/issue-to-pr.md
# for where this fits in the issue->PR workflow (the "smoke_testing" state).
#
# workflow_state.py transitions used here follow its transition graph exactly:
# checking_logs -> [diagnosing_runtime, smoke_testing], smoke_testing ->
# [diagnosing_runtime, pr_created]. So pr_created is only reachable from
# "smoke_testing", while a failure can advance to "diagnosing_runtime" from
# either "checking_logs" or "smoke_testing".
set -u

BACKEND_URL="${STAGING_BACKEND_URL:-https://comfortable-success-production-18a8.up.railway.app}"
WORKFLOW_STATE=".claude/workflow_state.json"
WORKFLOW_SCRIPT="scripts/workflow_state.py"

PAYLOAD='{
  "hard_filters": {
    "has_allergies": false,
    "property_type": "house",
    "has_yard": true,
    "monthly_budget_usd": 250,
    "has_other_dogs": false,
    "has_cats": false,
    "has_kids": false,
    "has_elderly": false,
    "owner_experience": "experienced",
    "noise_tolerance": "medium",
    "max_size_category": "no_preference",
    "size_strict": false
  },
  "soft_context": {
    "daily_time_available_min": 60,
    "climate": "temperate",
    "outdoor_time_expected": "medium",
    "grooming_commitment": "medium",
    "prioritize_longevity": false,
    "prioritize_low_vet_costs": false,
    "primary_purpose": "family_pet"
  },
  "trait_priority_ranking": [
    "energy_level",
    "trainability",
    "barking_level",
    "affection_level",
    "protective_instinct",
    "shedding_level"
  ]
}'

response=$(curl -s -w '\n%{http_code}' -X POST "$BACKEND_URL/recommend" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

http_code=$(printf '%s' "$response" | tail -n1)
body=$(printf '%s' "$response" | sed '$d')

pass=false
if [ "$http_code" = "200" ] && printf '%s' "$body" | grep -q '"results"'; then
  pass=true
fi

if [ -x "venv/bin/python" ]; then
  PYBIN="venv/bin/python"
else
  PYBIN="python3"
fi

current_state=""
if [ -f "$WORKFLOW_STATE" ]; then
  current_state=$("$PYBIN" -c "import json; print(json.load(open('$WORKFLOW_STATE')).get('current_state',''))" 2>/dev/null)
fi

if $pass; then
  echo "PASS: staging smoke test — $BACKEND_URL/recommend returned 200 with a 'results' key"
  if [ "$current_state" = "smoke_testing" ]; then
    "$PYBIN" "$WORKFLOW_SCRIPT" advance --to pr_created
  fi
  exit 0
else
  echo "FAIL: staging smoke test — $BACKEND_URL/recommend"
  echo "  http_code=$http_code"
  echo "  body=$(printf '%s' "$body" | head -c 500)"
  if [ -n "$current_state" ]; then
    "$PYBIN" "$WORKFLOW_SCRIPT" fail --at smoke_testing
    state_after_fail=$("$PYBIN" -c "import json; print(json.load(open('$WORKFLOW_STATE')).get('current_state',''))" 2>/dev/null)
    if [ "$state_after_fail" = "checking_logs" ] || [ "$state_after_fail" = "smoke_testing" ]; then
      "$PYBIN" "$WORKFLOW_SCRIPT" advance --to diagnosing_runtime
    fi
  fi
  exit 1
fi
