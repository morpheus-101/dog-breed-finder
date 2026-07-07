#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash). Second, independent enforcement layer for
the issue-to-PR workflow's "staging only, never main" rule (see
skills/issue-to-pr.md). Without this, the rule is only documented in prose
and a slip-up (or a differently-behaving agent) could push straight to main
mid-workflow. Blocks any `git push`/`git merge` targeting `main` while
.claude/workflow_state.json exists with current_state not in {done, idle}.

No-op (permissionDecision left unset -> default allow) when no
workflow_state.json exists, so normal sessions and unrelated Bash commands
are never affected.
"""

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "workflow_state.json"

# Matches `git push ... main` / `git merge ... main` in any argument order,
# including `origin main`, `--force main`, etc.
_MAIN_TARGET_RE = re.compile(
    r"\bgit\b[^|;&\n]*\b(push|merge)\b[^|;&\n]*\bmain\b", re.IGNORECASE
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command or not _MAIN_TARGET_RE.search(command):
        sys.exit(0)

    if not STATE_FILE.exists():
        sys.exit(0)

    try:
        state = json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        sys.exit(0)

    current_state = state.get("current_state")
    if current_state in ("done", "idle"):
        sys.exit(0)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked: an issue-to-PR workflow session is in progress "
                        f"(current_state='{current_state}', see skills/issue-to-pr.md). "
                        "This workflow may push to 'staging' only. Pushing to or "
                        "merging 'main' directly is not allowed while it's in "
                        "progress - merging is a manual human action taken after "
                        "'pr_created' -> 'done'."
                    ),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
