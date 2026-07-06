#!/usr/bin/env python3
"""SessionStart hook. Surfaces an in-progress issue-to-PR workflow session
(see skills/issue-to-pr.md, scripts/workflow_state.py) at the start of a new
session, rather than relying on someone remembering to run
`workflow_state.py current` manually.

No-op when no .claude/workflow_state.json exists, so normal sessions and
unrelated work are never affected.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "workflow_state.json"


def main() -> None:
    if not STATE_FILE.exists():
        sys.exit(0)

    try:
        state = json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        sys.exit(0)

    current_state = state.get("current_state")
    if current_state in ("done", "idle"):
        sys.exit(0)

    issue_number = state.get("issue_number")
    history = state.get("history", [])[-5:]
    history_lines = "\n".join(f"  {h.get('timestamp')}  {h.get('state')}" for h in history)

    message = (
        f"An issue-to-PR workflow session is already in progress: issue #{issue_number}, "
        f"current_state='{current_state}'. See skills/issue-to-pr.md to continue it. "
        f"Recent history:\n{history_lines}"
    )

    print(
        json.dumps(
            {
                "systemMessage": message,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": message,
                },
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
