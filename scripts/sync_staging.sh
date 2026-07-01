#!/usr/bin/env bash
# Resets the local and remote `staging` branch to exactly match `main`.
# See the "Development Workflow" section in CLAUDE.md for when to run this:
# before starting new feature work, and again immediately after a PR from
# staging is merged into main.
#
# This is destructive to `staging` — any commits on staging not yet merged
# into main are discarded from the branch (force-pushed over on the remote).
# It is never destructive to main.
set -euo pipefail

if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree is not clean. Commit, stash, or discard changes before syncing staging." >&2
  git status --short
  exit 1
fi

echo "Fetching latest from origin..."
git fetch origin

echo "Checking out staging..."
git checkout staging

echo "Resetting staging to origin/main..."
git reset --hard origin/main

echo "Force-pushing staging to origin (force-with-lease)..."
git push origin staging --force-with-lease

echo
echo "Done. staging now matches origin/main:"
git log --oneline -3 origin/main
