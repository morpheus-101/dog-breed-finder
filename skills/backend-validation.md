# Skill: Backend Validation

Read this file before starting any backend task and again after making any backend code change.

---

## 1. Purpose

Backend validation gives Claude Code a self-contained feedback loop: write code, validate, fix failures, re-validate, repeat — without requiring the user to copy-paste errors or intervene. The user should only see the final passing result.

---

## 2. The Validation Script: `scripts/validate_backend.py`

This script is a living artifact, not a static one. It must evolve alongside the backend code, and Claude Code is responsible for keeping it accurate and relevant at all times.

Regardless of how the backend evolves, the script must always cover:

- **API contract conformance** — every response from every endpoint must match the shape defined in `skills/api-contract.md` exactly: correct keys, correct types, no missing fields, no extra undocumented fields.
- **Layer correctness** — each layer of the ranking pipeline must be testable in isolation with known inputs and expected outputs.
- **Error handling** — invalid requests must return the correct HTTP status codes and meaningful error messages, never a 500 for an expected failure mode.
- **No real external calls** — Groq API and Turso must never be called during validation. Mock or stub them. Use `breeds.db` (local SQLite) for all database access during tests.
- **Edge cases** — always test the boundaries: zero breeds surviving Layer 1, exactly one breed surviving, the maximum expected number of results, invalid `trait_priority_ranking` inputs.

---

## 3. How to Evolve the Validation Script

When the backend changes, assess whether existing tests are still valid and whether new tests are needed:

- New endpoint added → add contract conformance tests, plus at least one happy-path and one error-path test.
- A field is added or removed from a response → update all tests that assert on response shape.
- New layer behavior added → add an isolation test for it.
- A test covers behavior that no longer exists → remove it.

Never leave the validation script testing things that no longer exist, or failing to test things that do.

---

## 4. Validation Process — Non-Negotiable Rules

- Run `validate_backend.py` after every change to any file in `backend/`.
- Read the full output — do not skim it.
- If any test fails: fix the code (not the test, unless the test itself is wrong), then re-run.
- Do not consider any backend task complete until `validate_backend.py` exits with status 0.
- If a test cannot be made to pass because the test itself is wrong (e.g. it tests stale behavior): update the test first, document why in a comment, then re-run.
- Never delete a failing test to make validation pass — fix the underlying code.

---

## 5. Database Access During Tests

- Always use `breeds.db` (local SQLite) for validation — never Turso.
- The backend must support a `DB_MODE` environment variable: `DB_MODE=local` uses `breeds.db`, `DB_MODE=turso` uses the Turso HTTP API.
- Default `DB_MODE` to `local` when unset, so tests work without any environment setup beyond the venv.

---

## 6. Self-Improvement Rule

After every session where backend code changed, review `validate_backend.py` and ask: does this script still accurately reflect what the backend does and what the contract requires? If not, update the script before ending the session. The validation script must never lag behind the backend code.

---

## 7. Stop Hook

A stop hook fires before any backend task is marked complete. It:

- Checks whether `validate_backend.py` was run in the current session.
- Checks whether it passed (exit status 0).
- If either condition is not met: runs `validate_backend.py` now.
- If it fails: does not allow the task to be marked complete — fix failures and re-run.
- Only allows completion when `validate_backend.py` has exited with status 0 in the current session.
