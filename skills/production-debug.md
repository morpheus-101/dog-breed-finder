# Skill: Production Debugging

Read this file whenever the user reports a production error, deployment failure, CI failure, or asks to debug or check logs. This file replaces any previous `railway-debug.md` — if that file still exists, delete it and treat this file as authoritative.

This skill covers autonomously diagnosing and fixing production issues using logs from Railway (runtime errors), GitHub Actions (CI/build/test failures), and Axiom (structured application logs) — without asking the user to copy-paste anything.

---

## 1. Prerequisites

- **Railway CLI** installed (`npm install -g @railway/cli`) and linked to the project (`railway link`).
- **GitHub CLI** installed (`brew install gh`) and authenticated (`gh auth login`).
- Both CLIs work outside the venv — no activation needed.
- If `railway link` has not been run yet, run it first: `railway link`, then select the project, then select the backend service.

---

## 2. Step 1 — Fetch Logs From Three Sources

**Railway runtime logs** (production errors, 500s, crashes) — fetch from both services explicitly so it works regardless of which service is linked:

```bash
railway logs --service dog-breed-finder --tail 200 > /tmp/railway_backend_logs.txt
railway logs --service surprising-tranquility --tail 200 > /tmp/railway_frontend_logs.txt
```

Read both files during diagnosis. Backend logs take priority since most runtime errors originate there.

**GitHub Actions logs** (CI failures, build errors, test failures):

```bash
gh run list --limit 1 --json databaseId --jq '.[0].databaseId' | xargs -I{} gh run view {} --log > /tmp/gh_actions_logs.txt
```

**Axiom application logs** (structured app-level events, errors, Groq fallbacks) — load `AXIOM_TOKEN` and `AXIOM_DATASET` from `.env` first, then:

```bash
curl -s -H "Authorization: Bearer $AXIOM_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.axiom.co/v1/datasets/$AXIOM_DATASET/query" \
  -d '{"apl": "[$AXIOM_DATASET] | where level == \"error\" or level == \"warning\" | limit 50", "startTime": "2h", "endTime": "now"}' \
  > /tmp/axiom_errors.txt
```

Fetch recent request_complete events for performance visibility:

```bash
curl -s -H "Authorization: Bearer $AXIOM_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.axiom.co/v1/datasets/$AXIOM_DATASET/query" \
  -d '{"apl": "[$AXIOM_DATASET] | where message == \"request_complete\" | limit 20", "startTime": "2h", "endTime": "now"}' \
  > /tmp/axiom_requests.txt
```

Read all files immediately after fetching. Do not ask the user what the error is — read the logs and diagnose it yourself.

---

## 3. Step 2 — Diagnose

- In `railway_backend_logs.txt`: look for Python tracebacks, `ValueError`, `ValidationError`, `ImportError`, or any line containing `ERROR`.
- In `gh_actions_logs.txt`: look for `FAILED`, `Error`, `exit code 1`, or test failure output.
- Check `/tmp/axiom_errors.txt` for error and warning level events including `groq_fallback` and `coercion_warning`.
- Check `/tmp/axiom_requests.txt` for performance patterns — if `response_time_ms` is consistently high, that indicates a Groq latency issue rather than a code bug.
- Identify the root cause — file name, line number, and nature of the error.
- If both logs show errors, fix the Railway (runtime) error first — it affects live users.

---

## 4. Step 3 — Fix

- Make the minimal code change needed to fix the identified error.
- Do not refactor unrelated code.
- If the fix touches `backend/` files, run `scripts/validate_backend.py` and confirm all tests pass before proceeding.
- If the fix touches `frontend/` files, run `npm run build` in `frontend/` to confirm no build errors.

---

## 5. Step 4 — Deploy

- Commit the fix with an appropriate message, following `skills/git-commit.md` conventions.
- Push to `main` — GitHub Actions will trigger automatically.
- After 2–3 minutes, re-fetch Railway logs to confirm the error is gone:

  ```bash
  railway logs --tail 50 > /tmp/railway_backend_logs_after.txt
  ```

- If the error persists, repeat from Step 2.

**Note:** this push-to-`main`-without-asking step is specific to this skill's autonomous debug-and-deploy loop and intentionally overrides `skills/git-commit.md`'s general "never push automatically" rule for this scenario only. Outside of production-debug workflows, that rule still applies.

---

## 6. Non-Obvious Rules

- Never ask the user to copy-paste logs — always fetch them directly using the CLIs.
- Never fix a symptom without understanding the root cause from the logs.
- If the Railway log shows the same error repeating multiple times, read all occurrences — later ones may have more context.
- If GitHub Actions logs are too large, focus on lines containing `FAILED`, `Error`, or `Traceback`.
- Always run `validate_backend.py` before pushing a backend fix — never push untested backend code.
- If `railway link` is not set up, run it first: `railway link`, select the project, select the backend service.
- If `AXIOM_TOKEN` or `AXIOM_DATASET` is not set in `.env`, skip the Axiom fetch step and rely on Railway and GitHub Actions logs only.
- Axiom logs have up to a 30 second ingestion delay — if logs seem missing, wait and retry.
