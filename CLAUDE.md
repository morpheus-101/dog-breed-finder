# PawMatch — Dog Breed Recommendation Engine

## What This App Does

A user completes a multi-step lifestyle questionnaire (housing, activity level, budget, allergies, family setup, experience with dogs, etc.). The backend processes these inputs through a three-layer ranking pipeline and returns a ranked list of dog breeds with plain-English explanations of fit. No user data is stored anywhere.

---

## Architecture Overview

```
React Frontend
    │
    │  POST /recommend  (full user profile as JSON)
    ▼
FastAPI Backend
    ├── Layer 1: Hard filters (Python, local breed DB, no LLM)
    ├── Layer 2: Weighted scoring (Python, trait weights computed from user rankings)
    └── Layer 3: Groq API — re-rank + explanation (Llama 3.1 8B)
    │
    ▼
Turso (hosted libSQL) — read-only at runtime
```

The backend is fully stateless. Every `/recommend` request is self-contained; nothing is written to any database at runtime.

---

## Three-Layer Ranking Pipeline

### Layer 1 — Hard Filters (Boolean elimination)
- Runs in Python against the Turso breed database.
- Eliminates breeds that are a categorical mismatch for the user.
- No LLM involvement.
- Examples of elimination rules:
  - User has allergies → remove all non-hypoallergenic breeds.
  - User has no outdoor space → remove breeds requiring a yard.
  - User's budget is below a breed's cost threshold → remove that breed.
- **Hypoallergenic is a hard filter here, not a scored trait in Layer 2.**

### Layer 2 — Weighted Scoring
- The user drag-ranks six traits in order of personal importance.
- Six traits: `energy_level`, `trainability`, `barking_level`, `affection_level`, `protective_instinct`, `shedding_level`.
- Rank position → linear weight mapping:
  | Rank | Weight |
  |------|--------|
  | 1st  | 1.00   |
  | 2nd  | 0.83   |
  | 3rd  | 0.67   |
  | 4th  | 0.50   |
  | 5th  | 0.33   |
  | 6th  | 0.17   |
- A weighted score is computed per breed across the six traits; breeds are sorted descending.
- The **top 10–15 breeds** are passed to Layer 3.

### Layer 3 — LLM Re-ranking and Explanation
- Input: top 10–15 breeds from Layer 2 + full user profile.
- API: **Groq API, free tier**, model `llama-3.1-8b-instant`.
- Groq re-ranks the shortlist and generates a plain-English explanation per breed.
- Always send the `llm_summary` field for each breed — never raw numeric columns.
- Output: final ranked list with per-breed explanations, returned to the frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (multi-step questionnaire, drag-and-rank UI, results page) |
| Backend | FastAPI (Python) |
| Database | Turso (hosted SQLite / libSQL) — queried via Turso HTTP API |
| LLM | Groq API — `llama-3.1-8b-instant` (free tier — 30 req/min, 14k req/day) |
| Async HTTP | `httpx` (Python) |
| Env vars | `python-dotenv` |
| Data processing | `pandas` (scripts only, not runtime) |

---

## Project Structure

```
dog-breed-finder/
├── frontend/                   # React app
├── backend/
│   └── main.py                 # FastAPI entrypoint; all pipeline logic lives here or is imported here
├── datasets/                   # AKC breed dataset (static, downloaded once)
├── data/
│   ├── raw/                    # Raw API responses (JSON)
│   ├── processed/              # Merged, cleaned CSVs
│   └── final/                  # breeds.csv — final file loaded into Turso
├── scripts/
│   ├── ingest_dog_api.py       # Fetches breed data from The Dog API
│   ├── process_and_merge.py    # Cleans, merges, fills gaps (may call Anthropic API for missing columns)
│   └── load_to_turso.py        # One-time load of breeds.csv into Turso
├── skills/
│   ├── data-ingestion.md       # Full breed DB schema + ingestion details — READ BEFORE writing DB code
│   └── data-processing.md      # Data cleaning and merge logic
├── .env                        # API keys, Turso URL and auth token (never committed)
├── breeds.db                   # Local SQLite for development
└── CLAUDE.md                   # This file
```

---

## Database

- **Provider:** Turso (hosted libSQL). Accessed via Turso's HTTP API at runtime.
- **Local dev:** `breeds.db` (standard SQLite) mirrors the Turso schema.
- **Single table:** `breeds`
- **Access pattern:** read-only at runtime. No writes ever happen from the backend or frontend.
- **Images:** stored as CDN URLs from The Dog API — not self-hosted.
- **Critical rule:** Do not assume column names or types. Always read `skills/data-ingestion.md` before writing any database-related code. That file is the authoritative schema reference.

---

## Data Sources (ingestion only, not runtime)

| Source | Purpose |
|---|---|
| The Dog API (`thedogapi.com`) | Structured breed data and image URLs |
| AKC CSV (`datasets/akc-data-latest.csv`) | Pre-downloaded CSV of 277 breeds with lifestyle scoring attributes |
| Anthropic API | Batch-generating missing columns during data processing |

---

## Environment Variables (`.env`)

```
TURSO_URL=          # Turso database HTTP endpoint
TURSO_AUTH_TOKEN=   # Turso auth token
GROQ_API_KEY=       # Groq API key
DOG_API_KEY=        # The Dog API key (scripts only)
ANTHROPIC_API_KEY=  # Anthropic API key (scripts only)
```

---

## Key Constraints and Invariants

1. **No user data stored.** The backend is fully stateless. Each `/recommend` request is self-contained. No sessions, no logs of user input, no analytics.
2. **Breed database is read-only at runtime.** The only write path is `scripts/load_to_turso.py`, run once during setup.
3. **Always use `llm_summary` for Groq.** When constructing the Layer 3 prompt, use each breed's `llm_summary` field. Never send raw numeric columns to the LLM.
4. **Hypoallergenic is a hard filter (Layer 1), not a scored trait (Layer 2).**
5. **httpx for all async HTTP** in the backend (Turso API calls, Groq API calls).
6. **python-dotenv** for all environment variable loading.
7. **pandas** is for scripts only — not imported in the FastAPI runtime.

---

## Frontend Behaviour

- Multi-step questionnaire collects the full user lifestyle profile.
- Drag-and-rank UI lets the user order the six traits by personal importance.
- Results page displays ranked breeds with images (CDN URLs) and the LLM-generated explanation per breed.
- No state is persisted beyond the active browser session.

---

## Skill Files

Read these before working in their domain — do not guess:

- `skills/data-ingestion.md` — **authoritative breed table schema**, column names and types, ingestion pipeline details.
- `skills/data-processing.md` — data cleaning logic, merge strategy, how missing columns were filled.
- `skills/api-contract.md` — **authoritative `/recommend` API contract**, read before writing any backend code for request handling, Layer 1 filtering, Layer 2 scoring, or Layer 3 Groq integration.
- `skills/venv-setup.md` — read before running any Python script or installing dependencies.
- `skills/git-commit.md` — read whenever the user asks to commit or push code changes.

---

## Session Rules for Claude Code

- Read `CLAUDE.md` (this file) at the start of every session.
- Read the relevant skill file before writing any database or data-pipeline code.
- Do not invent column names — consult `skills/data-ingestion.md`.
- Do not add user data persistence under any circumstances.
- Do not write to the Turso database at runtime.
- Default to `httpx` (async) for all HTTP calls in the backend.
- The Groq model is `llama-3.1-8b-instant` — do not substitute another model without explicit instruction.
