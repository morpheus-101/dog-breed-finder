#!/usr/bin/env bash
# Stop hook: blocks task completion until scripts/validate_backend.py has
# passed (exit 0) against the latest backend/ changes in this session.
# See skills/backend-validation.md for the rules this enforces.
set -u

SENTINEL=".claude/.validate_backend_passed"
VALIDATOR="scripts/validate_backend.py"

changed_files=$(git status --porcelain --untracked-files=all -- backend/ 2>/dev/null | awk '{print $NF}')

# No backend/ changes in the working tree -> not a backend task, allow stop.
if [ -z "$changed_files" ]; then
  exit 0
fi

newest_change=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  mtime=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)
  [ -n "$mtime" ] && [ "$mtime" -gt "$newest_change" ] && newest_change=$mtime
done <<< "$changed_files"

sentinel_mtime=0
if [ -f "$SENTINEL" ]; then
  sentinel_mtime=$(stat -f %m "$SENTINEL" 2>/dev/null || stat -c %Y "$SENTINEL" 2>/dev/null)
fi

# Already validated after the most recent backend/ change -> allow stop.
if [ "$sentinel_mtime" -gt "$newest_change" ]; then
  exit 0
fi

if [ ! -f "$VALIDATOR" ]; then
  echo '{"decision":"block","reason":"backend/ has uncommitted changes but scripts/validate_backend.py does not exist yet. Create it per skills/backend-validation.md (API contract conformance, layer isolation tests, error handling, edge cases, no real Groq/Turso calls), then re-run it before marking this task complete."}'
  exit 0
fi

if [ -x "venv/bin/python" ]; then
  PYBIN="venv/bin/python"
else
  PYBIN="python3"
fi

output=$("$PYBIN" "$VALIDATOR" 2>&1)
status=$?

if [ "$status" -eq 0 ]; then
  mkdir -p "$(dirname "$SENTINEL")"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$SENTINEL"
  exit 0
fi

printf '%s' "$output" | tail -c 4000 | "$PYBIN" -c '
import json, sys
output = sys.stdin.read()
reason = (
    "validate_backend.py failed (exit '"$status"'). Fix the underlying code "
    "(not the test, unless the test itself is wrong per skills/backend-validation.md), "
    "then re-run scripts/validate_backend.py before marking this task complete. Output:\n"
    + output
)
print(json.dumps({"decision": "block", "reason": reason}))
'
exit 0
