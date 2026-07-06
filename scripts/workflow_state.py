#!/usr/bin/env python3
"""Deterministic state tracker for the GitHub issue -> PR workflow.

See skills/issue-to-pr.md for the full workflow this enforces. State is
persisted in .claude/workflow_state.json (gitignored, per-checkout only).

This tool does not replace scripts/validate_backend.py's stop-hook loop —
"validating_backend" / "fixing_backend" are just two states in this larger
graph, and validate_backend.py calls back into this script to advance
through them automatically.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "workflow_state.json"

STATES = [
    "idle",
    "synced",
    "issue_read",
    "implementing",
    "validating_backend",
    "fixing_backend",
    "validating_frontend",
    "fixing_frontend",
    "pushed_to_staging",
    "ci_pending",
    "diagnosing_ci",
    "staging_deployed",
    "checking_logs",
    "diagnosing_runtime",
    "smoke_testing",
    "fixing",
    "pr_created",
    "done",
    "blocked",
]

# Allowed transitions: current_state -> [allowed next states].
# CRITICAL: no state here may be named anything related to "main", and no
# transition may lead to one. Merging/pushing to main is exclusively a
# manual human action outside this tool.
TRANSITIONS = {
    "idle": ["synced"],
    "synced": ["issue_read"],
    "issue_read": ["implementing"],
    "implementing": ["validating_backend"],
    "validating_backend": ["fixing_backend", "validating_frontend"],
    "fixing_backend": ["validating_backend"],
    "validating_frontend": ["fixing_frontend", "pushed_to_staging"],
    "fixing_frontend": ["validating_frontend"],
    "pushed_to_staging": ["ci_pending"],
    "ci_pending": ["diagnosing_ci", "staging_deployed"],
    "diagnosing_ci": ["fixing"],
    "fixing": ["validating_backend"],
    "staging_deployed": ["checking_logs"],
    "checking_logs": ["diagnosing_runtime", "smoke_testing"],
    "diagnosing_runtime": ["fixing"],
    "smoke_testing": ["diagnosing_runtime", "pr_created"],
    "pr_created": ["done"],
    "done": [],
    "blocked": [],
}

RESTARTABLE_STATES = {"done", "idle", "blocked"}
MAX_RETRIES = 3  # a 4th failure at the same state forces "blocked"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def load_state():
    """Returns the parsed state dict, or None if the file does not exist.
    Exits with a clear error (never a raw traceback) if the file exists but
    is corrupted or missing required keys."""
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError as exc:
        _fail(
            f"{STATE_FILE} is corrupted (invalid JSON: {exc}). "
            "Run 'python scripts/workflow_state.py reset' to clear it, then "
            "'start --issue <n>' to begin a fresh session."
        )
    for key in ("issue_number", "current_state", "session_started", "history", "retry_counts"):
        if key not in data:
            _fail(
                f"{STATE_FILE} is missing required key '{key}'. "
                "Run 'python scripts/workflow_state.py reset' to clear it, then "
                "'start --issue <n>' to begin a fresh session."
            )
    return data


def save_state(data) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2) + "\n")


def cmd_start(args) -> None:
    existing = load_state()
    if existing is not None and existing["current_state"] not in RESTARTABLE_STATES:
        _fail(
            f"an in-progress workflow session already exists (current_state="
            f"'{existing['current_state']}', issue_number={existing['issue_number']}). "
            "Finish it, get it to 'blocked', or run "
            "'python scripts/workflow_state.py reset' before starting a new one."
        )

    data = {
        "issue_number": args.issue,
        "current_state": "idle",
        "session_started": _now(),
        "history": [{"state": "idle", "timestamp": _now()}],
        "retry_counts": {},
    }
    save_state(data)
    print(f"Started new workflow session for issue #{args.issue}. current_state=idle")


def cmd_advance(args) -> None:
    data = load_state()
    if data is None:
        _fail(
            "no workflow session exists. Run "
            "'python scripts/workflow_state.py start --issue <n>' first."
        )

    to_state = args.to
    if to_state not in STATES:
        _fail(f"'{to_state}' is not a known state. Known states: {', '.join(STATES)}")

    current = data["current_state"]
    allowed = TRANSITIONS.get(current, [])
    if to_state not in allowed:
        _fail(
            f"illegal transition '{current}' -> '{to_state}'. "
            f"Valid next states from '{current}': {allowed or '(none - terminal state)'}"
        )

    if to_state == "pushed_to_staging":
        import subprocess

        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if branch != "staging":
            _fail(
                f"cannot advance to 'pushed_to_staging' from branch '{branch}'. "
                "Check out 'staging' before pushing."
            )

    data["current_state"] = to_state
    data["history"].append({"state": to_state, "timestamp": _now()})
    save_state(data)
    print(f"Advanced: {current} -> {to_state}")


def cmd_fail(args) -> None:
    data = load_state()
    if data is None:
        _fail(
            "no workflow session exists. Run "
            "'python scripts/workflow_state.py start --issue <n>' first."
        )

    state = args.at
    retry_counts = data["retry_counts"]
    retry_counts[state] = retry_counts.get(state, 0) + 1
    count = retry_counts[state]

    if count > MAX_RETRIES:
        previous = data["current_state"]
        data["current_state"] = "blocked"
        data["history"].append({"state": "blocked", "timestamp": _now()})
        save_state(data)
        print(
            f"BLOCKED: '{state}' has failed {count} times (was at '{previous}'). "
            "Manual intervention needed - stop retrying and ask the user for guidance."
        )
        return

    save_state(data)
    print(f"Recorded failure #{count} at '{state}' (blocked after {MAX_RETRIES + 1}).")


def cmd_current(args) -> None:
    data = load_state()
    if data is None:
        print("No workflow session in progress.")
        return

    print(f"current_state: {data['current_state']}")
    print(f"issue_number: {data['issue_number']}")
    print("last 5 history entries:")
    for entry in data["history"][-5:]:
        print(f"  {entry['timestamp']}  {entry['state']}")


def cmd_reset(args) -> None:
    if not STATE_FILE.exists():
        print("No workflow state file to reset.")
        return
    STATE_FILE.unlink()
    print(f"Deleted {STATE_FILE}.")


def cmd_require(args) -> None:
    data = load_state()
    if data is None:
        sys.exit(0)

    if data["current_state"] in (args.state, "done"):
        sys.exit(0)

    print(
        f"current_state is '{data['current_state']}', required '{args.state}'. "
        "Continue the remaining steps in skills/issue-to-pr.md, or if genuinely "
        "stuck, report the blocked state to the user instead of finishing."
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue-to-PR workflow state tracker.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start a fresh workflow session.")
    p_start.add_argument("--issue", type=int, required=True)
    p_start.set_defaults(func=cmd_start)

    p_advance = sub.add_parser("advance", help="Advance to a new state.")
    p_advance.add_argument("--to", required=True, choices=STATES)
    p_advance.set_defaults(func=cmd_advance)

    p_fail = sub.add_parser("fail", help="Record a failure at a state.")
    p_fail.add_argument("--at", required=True, choices=STATES)
    p_fail.set_defaults(func=cmd_fail)

    p_current = sub.add_parser("current", help="Print current state and recent history.")
    p_current.set_defaults(func=cmd_current)

    p_reset = sub.add_parser("reset", help="Delete the state file entirely.")
    p_reset.set_defaults(func=cmd_reset)

    p_require = sub.add_parser("require", help="Used by the stop hook to enforce a state.")
    p_require.add_argument("--state", required=True, choices=STATES)
    p_require.set_defaults(func=cmd_require)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
