# Skill: Git Commit

Read this file whenever the user asks to commit, push, or save code changes ("commit this", "commit my changes", "push this to git", "let's commit", etc.).

---

## 1. Purpose

When the user asks to commit, Claude Code reviews all pending changes, writes an accurate commit message based on the actual diff, and commits — without requiring the user to write the message themselves.

---

## 2. Pre-Commit Checks

Run these before staging anything:

```
git status
git diff
git diff --staged   # only if files are already staged
```

Then confirm:

- **`.env` is not in the changeset.** If it appears in `git status`, stop immediately and warn the user — it contains API keys and must never be committed.
- **`venv/` is not in the changeset.** If it appears, stop and warn — the virtual environment must never be tracked.
- **`breeds.db` is not in the changeset.** If it appears, stop and warn — it is the local dev database and is excluded from version control.

If any of the above are present, do not proceed with the commit until the user resolves it.

---

## 3. Staging

Stage relevant project files explicitly:

```
git add <file1> <file2> ...
```

Do not use `git add -A` or `git add .` without first verifying the output of `git status`. Even if `.gitignore` is complete, manually confirm `.env`, `venv/`, and `breeds.db` are not being staged.

---

## 4. Commit Message Format

Write the message based on the actual diff content — not a generic description.

**Format:**

```
<prefix>: <short imperative summary, under 72 characters>

- Bullet describing what changed and why (optional, for substantial changes)
- Up to 4 bullets if needed
```

**Prefixes:**

| Prefix | When to use |
|--------|-------------|
| `feat:` | New functionality |
| `fix:` | Bug fix |
| `data:` | Dataset or pipeline change |
| `docs:` | Documentation or skill file update |
| `chore:` | Housekeeping, dependency, config |

**Rules:**
- Imperative mood: "Add", "Fix", "Remove" — not "Added" or "Adds"
- Summary under 72 characters
- No AI attribution, generator tags, or "Co-authored-by" lines unless the user explicitly requests them
- If changes span clearly unrelated concerns, ask the user whether they want one commit or separate commits before proceeding

---

## 5. Execution

```
git commit -m "..."
git log -1
```

Show the user the result of `git log -1` after committing so they can confirm the commit landed correctly.

Do **not** run `git push` automatically. Only push if the user explicitly asks.

---

## 6. Non-Obvious Rules

- If `git status` is clean, tell the user there is nothing to commit — do not create an empty commit.
- Never amend a published commit (one that has already been pushed).
- Never force-push or rewrite history under any circumstance.
