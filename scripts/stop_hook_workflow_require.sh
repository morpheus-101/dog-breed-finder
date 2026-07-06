#!/usr/bin/env bash
# Stop hook: blocks task completion until the issue-to-PR workflow state
# (scripts/workflow_state.py, see skills/issue-to-pr.md) has reached "done".
# No-op when no .claude/workflow_state.json exists, so unrelated sessions and
# the existing validate_backend.py stop hook are never affected.
set -u

if [ ! -f ".claude/workflow_state.json" ]; then
  exit 0
fi

if [ -x "venv/bin/python" ]; then
  PYBIN="venv/bin/python"
else
  PYBIN="python3"
fi

output=$("$PYBIN" scripts/workflow_state.py require --state done 2>&1)
status=$?

if [ "$status" -eq 0 ]; then
  exit 0
fi

printf '%s' "$output" | "$PYBIN" -c '
import json, sys
output = sys.stdin.read()
reason = (
    "The issue-to-PR workflow (skills/issue-to-pr.md) has not reached \"done\" yet. "
    "Continue the remaining steps of skills/issue-to-pr.md, or if genuinely stuck, "
    "report the blocked state to the user instead of marking this task complete. "
    + output
)
print(json.dumps({"decision": "block", "reason": reason}))
'
exit 0
