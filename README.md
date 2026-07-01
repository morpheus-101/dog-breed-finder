# PawMatch

[![CI/CD](https://github.com/morpheus-101/dog-breed-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/morpheus-101/dog-breed-finder/actions/workflows/ci.yml)

PawMatch is an AI-powered dog breed recommendation engine. A user works through a multi-step lifestyle questionnaire — housing, household, budget, daily routine, noise tolerance, and a drag-ranked set of personality traits — and gets back a ranked, explained shortlist of dog breeds suited to their actual life, not just a filtered table.

What makes it technically interesting is the three-layer pipeline behind that shortlist: cheap, deterministic boolean elimination and weighted scoring run first to cut a 277-breed database down to a manageable shortlist, and only that shortlist — never the full table — is handed to an LLM for re-ranking and natural-language explanation. The app is fully stateless: no accounts, no stored user input, no database writes at runtime.

---

## Live Demo

- **Frontend:** https://surprising-tranquility-production-5bbd.up.railway.app
- **Backend API:** https://dog-breed-finder-production.up.railway.app

---

## Architecture

```
┌─────────────────┐
│  React Frontend │  Multi-step questionnaire, drag-and-rank UI, results page
│  (Vite)         │
└────────┬─────────┘
         │ POST /recommend  (full user profile as JSON)
         ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI Backend                                          │
│                                                            │
│  ┌────────────┐   ┌────────────┐   ┌──────────────────┐  │
│  │  Layer 1   │ → │  Layer 2   │ → │     Layer 3       │  │
│  │ Hard       │   │ Weighted   │   │ Groq LLM re-rank  │  │
│  │ Filters    │   │ Scoring    │   │ + explanation     │  │
│  └─────┬──────┘   └─────┬──────┘   └─────────┬──────────┘  │
│        │                │                    │             │
└────────┼────────────────┼────────────────────┼─────────────┘
         │                │                    │
         ▼                ▼                    ▼
   ┌───────────┐    (same data,           ┌──────────┐
   │   Turso   │     in-memory)            │ Groq API │
   │ (libSQL)  │                          │ Llama 3.1│
   │ 277 breeds│                          │ 8B-instant│
   └───────────┘                          └──────────┘
```

### Layer 1 — Hard Filters

Pure Python, boolean elimination against the breed database. No LLM involvement. Removes any breed that is a categorical mismatch — e.g. non-hypoallergenic breeds when the user has allergies, breeds needing a yard when the user has none, breeds over budget. Each rule is implemented as its own named function so it can be unit-tested in isolation.

### Layer 2 — Weighted Scoring

The user drag-ranks six personality traits (`energy_level`, `trainability`, `barking_level`, `affection_level`, `protective_instinct`, `shedding_level`) by personal importance. Rank position is converted into a linear weight (1st = 1.00 down to 6th = 0.17), and every breed that survived Layer 1 gets a weighted score across those six traits. The top 10–15 breeds (12 by default) move on to Layer 3.

### Layer 3 — LLM Re-ranking and Explanation

The Layer 2 shortlist, each breed's `llm_summary`, and the user's soft context (climate, daily time available, primary purpose, etc.) are sent to Groq. The model may re-rank the shortlist based on that context and writes a 1–2 sentence, situation-specific explanation per breed. Only summarized text is sent — raw numeric columns never reach the LLM. If the Groq call fails or returns malformed output, the backend falls back to the Layer 2 order with a generic explanation rather than failing the request.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + Vite | Fast dev server, no-frills SPA tooling, no need for a meta-framework here |
| Backend | FastAPI (Python) | Async-native, automatic request validation via Pydantic, minimal boilerplate |
| Database | Turso (hosted libSQL/SQLite) | SQLite's simplicity with a managed, globally-replicated HTTP API; read-only at runtime over 277 breeds — no need for a heavier RDBMS |
| LLM | Groq API — Llama 3.1 8B Instant | Free tier with generous throughput and very low inference latency, which matters for a synchronous user-facing request |
| Data pipeline | Python, pandas, rapidfuzz, Anthropic API (Claude Haiku) | pandas for merge/transform, rapidfuzz for fuzzy breed-name matching across data sources, Claude Haiku for cheap, fast batch generation of the columns no public dataset provides |
| Deployment | Railway | Single platform for both the FastAPI backend and the static frontend build, simple environment-variable-based config |
| Data sources | AKC dataset, The Dog API, Claude batch generation | See [Data Pipeline](#data-pipeline) below |

---

## Data Pipeline

The `breeds` table backing the app was built once, offline, by a three-stage pipeline (none of this runs at request time):

1. **AKC CSV** (`datasets/akc-data-latest.csv`) — 277 breeds with AKC lifestyle scoring attributes (energy, trainability, shedding, grooming, demeanor) as the base spine. Every AKC row survives to the final table.
2. **The Dog API** — merged in via fuzzy name matching (`rapidfuzz`, threshold 85) to add image URLs and the `hypoallergenic` flag. Unmatched breeds are logged, never silently dropped.
3. **Claude Haiku batch generation** (`claude-haiku-4-5-20251001`) — fills the 26 columns no public dataset covers: compatibility flags (`good_with_kids`, `good_with_dogs`, `good_with_cats`, `good_with_elderly`), cost estimates (`monthly_food_cost_usd`, `vet_cost_tier`, `monthly_total_cost_usd`), `coat_type`, climate tolerance, and the 2–3 sentence `llm_summary` used in Layer 3 prompts.

The merged dataset is validated against **99 automated data quality checks** (`scripts/validate_breeds_data.py`) — schema conformance, null tolerance, value-range and domain checks, logical consistency (e.g. a "giant" breed shouldn't be apartment-suitable with high confidence), content quality, and spot checks against known breeds — before being loaded into both Turso and the local `breeds.db` mirror via `scripts/load_to_turso.py`.

```
scripts/ingest_dog_api.py     →  data/raw/dog_api_breeds.json
scripts/process_and_merge.py  →  data/final/breeds.csv     (AKC + Dog API + Claude batch)
scripts/validate_breeds_data.py → 99 data quality checks against the loaded table
scripts/load_to_turso.py      →  Turso (production) + breeds.db (local dev mirror)
```

---

## Project Structure

```
dog-breed-finder/
├── backend/
│   ├── main.py            # FastAPI app, /recommend endpoint, request/response models, CORS
│   ├── db.py               # DB_MODE-aware data access: breeds.db (sqlite3) or Turso (httpx)
│   ├── filters.py          # Layer 1 — hard filter rules, one function per rule
│   ├── scoring.py          # Layer 2 — trait-rank-to-weight conversion and scoring
│   └── groq_client.py      # Layer 3 — Groq prompt construction, response parsing, fallback
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Top-level view state machine (questionnaire/loading/results/error)
│   │   ├── api/recommend.js        # POST /recommend client
│   │   ├── context/                # Questionnaire state (useContext)
│   │   ├── constants/              # Friendly labels, default form state, trait metadata
│   │   └── components/
│   │       ├── Questionnaire/      # 6-step form, progress bar, drag-and-rank trait ranking
│   │       ├── Results/            # Breed cards, empty-results and error states
│   │       └── shared/             # Reusable form primitives (toggle, slider, option cards)
│   └── vite.config.js              # Dev proxy: /recommend → localhost:8001
├── datasets/
│   └── akc-data-latest.csv         # Source AKC dataset (277 breeds)
├── data/
│   ├── raw/                        # Raw Dog API responses
│   ├── processed/                  # Intermediate merge output, unmatched-breed log
│   └── final/breeds.csv            # Final, schema-conformant breed table
├── scripts/
│   ├── ingest_dog_api.py           # Pulls breed data + images from The Dog API
│   ├── process_and_merge.py        # Merges AKC + Dog API, runs Claude batch generation
│   ├── validate_breeds_data.py     # 99 automated data quality checks
│   ├── load_to_turso.py            # One-time load into Turso + breeds.db
│   └── validate_backend.py         # Living backend validation suite (see below)
├── CLAUDE.md                       # Project-level instructions for AI-assisted development
├── breeds.db                       # Local SQLite mirror (not committed — generated by load_to_turso.py)
└── .env                            # API keys and DB config (not committed)
```

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+

### 1. Clone the repo

```bash
git clone https://github.com/morpheus-101/dog-breed-finder.git
cd dog-breed-finder
```

### 2. Set up the Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Configure environment variables

Create a `.env` file at the project root with:

| Variable | Description |
|---|---|
| `TURSO_URL` | Turso database HTTP endpoint (only needed for `DB_MODE=turso`) |
| `TURSO_AUTH_TOKEN` | Turso auth token (only needed for `DB_MODE=turso`) |
| `GROQ_API_KEY` | Groq API key, used by the backend for Layer 3 re-ranking |
| `DOG_API_KEY` | The Dog API key (only needed to re-run the data pipeline) |
| `ANTHROPIC_API_KEY` | Anthropic API key (only needed to re-run the data pipeline's Claude batch step) |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins (optional — defaults to allow-all for local dev) |
| `DB_MODE` | `local` or `turso` (optional — defaults to `local`) |

For the frontend, optionally set `VITE_API_URL` in `frontend/.env` to point at a non-local backend; if unset, the Vite dev server proxies `/recommend` to `http://localhost:8001`.

### 5. Run the data pipeline (optional)

`breeds.db` is not committed. If you don't already have one, generate it:

```bash
python scripts/ingest_dog_api.py
python scripts/process_and_merge.py
python scripts/validate_breeds_data.py
python scripts/load_to_turso.py
```

### 6. Run the backend

```bash
uvicorn backend.main:app --reload --port 8001
```

### 7. Run the frontend

```bash
cd frontend
npm run dev
```

### 8. Open the app

Visit **http://localhost:5173**.

---

## API Reference

### `POST /recommend`

The only public endpoint. Stateless — no auth, no user data persisted.

#### Request Body

```json
{
  "hard_filters": {
    "has_allergies": "boolean",
    "property_type": "apartment | house",
    "has_yard": "boolean",
    "monthly_budget_usd": "integer",
    "has_other_dogs": "boolean",
    "has_cats": "boolean",
    "has_kids": "boolean",
    "has_elderly": "boolean",
    "owner_experience": "first_time | some | experienced",
    "noise_tolerance": "low | medium | high",
    "max_size_category": "small | medium | large | giant | no_preference",
    "size_strict": "boolean"
  },
  "soft_context": {
    "daily_time_available_min": "integer",
    "climate": "hot | cold | temperate | varies",
    "outdoor_time_expected": "low | medium | high",
    "grooming_commitment": "low | medium | high",
    "prioritize_longevity": "boolean",
    "prioritize_low_vet_costs": "boolean",
    "primary_purpose": "companionship | family_pet | guard_protection | active_sports_partner | emotional_support"
  },
  "trait_priority_ranking": [
    "...exactly 6 unique values from: energy_level, trainability, barking_level, affection_level, protective_instinct, shedding_level"
  ]
}
```

#### Response Body

```json
{
  "results": [
    {
      "breed_name": "string",
      "rank": "integer",
      "match_explanation": "string",
      "image_url": "string or null",
      "key_stats": {
        "size_category": "string",
        "energy_level": "integer",
        "monthly_total_cost_usd": "integer"
      }
    }
  ],
  "total_breeds_considered": "integer",
  "breeds_after_hard_filters": "integer"
}
```

`results` contains only the final, Layer-3-ranked top 10–15 breeds — never the full filtered pool. If zero breeds survive Layer 1, the endpoint returns `200` with an empty `results` array and a `message` field explaining why, rather than an error. An invalid `trait_priority_ranking` (wrong length, duplicate, or unrecognized trait name) returns `422`.

#### Example

```bash
curl -X POST https://dog-breed-finder-production.up.railway.app/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "hard_filters": {
      "has_allergies": false,
      "property_type": "house",
      "has_yard": true,
      "monthly_budget_usd": 150,
      "has_other_dogs": false,
      "has_cats": false,
      "has_kids": true,
      "has_elderly": false,
      "owner_experience": "first_time",
      "noise_tolerance": "medium",
      "max_size_category": "medium",
      "size_strict": false
    },
    "soft_context": {
      "daily_time_available_min": 60,
      "climate": "temperate",
      "outdoor_time_expected": "medium",
      "grooming_commitment": "low",
      "prioritize_longevity": true,
      "prioritize_low_vet_costs": true,
      "primary_purpose": "family_pet"
    },
    "trait_priority_ranking": [
      "affection_level",
      "trainability",
      "energy_level",
      "shedding_level",
      "barking_level",
      "protective_instinct"
    ]
  }'
```

Full field-by-field contract, including the exact Layer 1 elimination rules and Layer 2 scoring formula, lives in [`skills/api-contract.md`](skills/api-contract.md).

---

## Skill Files and Development Conventions

This repo is developed with heavy AI assistance (Claude Code), and uses a `CLAUDE.md` + `skills/` convention to keep that assistance consistent across sessions:

- **`CLAUDE.md`** — the top-level brief: what the app does, the tech stack, project structure, and the hard invariants (stateless backend, read-only database, no raw numeric data sent to the LLM, etc.).
- **`skills/`** — focused, single-topic reference files read before working in a given area, so column names, API shapes, and conventions are never guessed:
  - `data-ingestion.md` — authoritative breed table schema
  - `data-processing.md` — data cleaning and merge logic
  - `api-contract.md` — authoritative `/recommend` request/response contract
  - `frontend.md` — frontend design direction and constraints
  - `backend-validation.md` — rules for `scripts/validate_backend.py`, a living test suite that must stay in sync with the backend and is enforced by a Claude Code stop hook before any backend task is considered done
  - `venv-setup.md`, `git-commit.md` — environment and workflow conventions

The effect is that schema details, API contracts, and design constraints live in one authoritative place each, rather than being re-derived (and potentially re-guessed) every session.

---

## Releases

Releases are fully automated with [semantic-release](https://github.com/semantic-release/semantic-release): every push to `main` that passes CI is analyzed for release-worthy commits, versioned, changelogged, and published as a GitHub Release automatically. See the [Releases page](https://github.com/morpheus-101/dog-breed-finder/releases) for the version history, and [`CHANGELOG.md`](CHANGELOG.md) for the generated changelog.

This only works because the project uses [Conventional Commits](https://www.conventionalcommits.org/) — commit message prefixes are what semantic-release reads to decide whether a release happens and what version bump it gets:

| Prefix | Meaning | Release |
|---|---|---|
| `feat:` | New feature | Minor version bump |
| `fix:` | Bug fix | Patch version bump |
| `chore:` | Maintenance, no user-facing change | No release |
| `docs:` | Documentation only | No release |
| `data:` | Dataset or pipeline change | Patch version bump |
| `perf:` | Performance improvement | Patch version bump |

---

## What's Not Included

This is a v1, and some things were deliberately left out of scope:

- **No user accounts or saved results.** Every request is self-contained; nothing about a user or their answers is persisted anywhere.
- **No analytics or usage tracking.**
- **The breed database is static.** It was built once via the data pipeline above and loaded into Turso; there's no scheduled re-ingestion or auto-update process.
- **Groq's free tier rate limits apply** (30 requests/minute, 14k requests/day at time of writing). There's no paid-tier fallback or request queuing.

