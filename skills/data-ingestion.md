# Skill: Data Ingestion

Read this file before writing any database schema, ingestion script, or data pipeline code.

---

## 1. Authoritative `breeds` Table Schema

| Column | Type | Source | Nullable |
|---|---|---|---|
| `id` | INTEGER PK | derived (autoincrement) | No |
| `breed_name` | TEXT | AKC CSV | No |
| `akc_group` | TEXT | AKC CSV (`group` column, renamed) | Yes |
| `popularity_rank` | INTEGER | AKC CSV (`popularity` column) | Yes — 79 breeds have no rank, leave NULL |
| `height_min_cm` | REAL | AKC CSV (`min_height`) | Yes |
| `height_max_cm` | REAL | AKC CSV (`max_height`) | Yes |
| `weight_min_kg` | REAL | AKC CSV (`min_weight`) | Yes |
| `weight_max_kg` | REAL | AKC CSV (`max_weight`) | Yes |
| `life_expectancy_min` | INTEGER | AKC CSV (`min_expectancy`) | Yes |
| `life_expectancy_max` | INTEGER | AKC CSV (`max_expectancy`) | Yes |
| `size_category` | TEXT | derived (see §6) | No |
| `energy_level` | INTEGER | AKC CSV (`energy_level_value`, converted) | Yes |
| `trainability` | INTEGER | AKC CSV (`trainability_value`, converted) | Yes |
| `shedding_level` | INTEGER | AKC CSV (`shedding_value`, converted) | Yes |
| `grooming_frequency` | INTEGER | AKC CSV (`grooming_frequency_value`, converted) | Yes |
| `good_with_strangers` | INTEGER | AKC CSV (`demeanor_value`, converted) | Yes |
| `hypoallergenic` | INTEGER | Dog API | No |
| `coat_type` | TEXT | Dog API (`coat`) | Yes |
| `image_url_1` | TEXT | Dog API (image search) | Yes |
| `image_url_2` | TEXT | Dog API (image search) | Yes |
| `origin_country` | TEXT | Claude batch | Yes |
| `grooming_cost_tier` | INTEGER | Claude batch | Yes |
| `exercise_min_per_day` | INTEGER | Claude batch | Yes |
| `monthly_food_cost_usd` | INTEGER | Claude batch | Yes |
| `vet_cost_tier` | INTEGER | Claude batch | Yes |
| `monthly_total_cost_usd` | INTEGER | Claude batch | Yes |
| `playfulness` | INTEGER | Claude batch | Yes |
| `affection_level` | INTEGER | Claude batch | Yes |
| `intelligence` | INTEGER | Claude batch | Yes |
| `independence` | INTEGER | Claude batch | Yes |
| `barking_level` | INTEGER | Claude batch | Yes |
| `protective_instinct` | INTEGER | Claude batch | Yes |
| `separation_anxiety` | INTEGER | Claude batch | Yes |
| `good_with_kids` | INTEGER (0/1) | Claude batch | Yes |
| `good_with_dogs` | INTEGER (0/1) | Claude batch | Yes |
| `good_with_cats` | INTEGER (0/1) | Claude batch | Yes |
| `good_with_elderly` | INTEGER (0/1) | Claude batch | Yes |
| `apartment_suitable` | INTEGER (0/1) | Claude batch | Yes |
| `needs_yard` | INTEGER (0/1) | Claude batch | Yes |
| `heat_tolerance` | INTEGER | Claude batch | Yes |
| `cold_tolerance` | INTEGER | Claude batch | Yes |
| `urban_suitable` | INTEGER (0/1) | Claude batch | Yes |
| `first_time_owner_suitable` | INTEGER (0/1) | Claude batch | Yes |
| `experience_required` | INTEGER | Claude batch | Yes |
| `guard_dog` | INTEGER (0/1) | Claude batch | Yes |
| `working_dog` | INTEGER (0/1) | derived (see §6) | No |
| `llm_summary` | TEXT | Claude batch | Yes |

---

## 2. AKC CSV Specifics

- **File:** `datasets/akc-data-latest.csv`
- **Rows:** 277 breeds
- **Columns:** 21

**Column name mapping** (CSV → schema):

| CSV column | Schema column |
|---|---|
| `breed_name` | `breed_name` |
| `popularity` | `popularity_rank` |
| `group` | `akc_group` |
| `min_height` / `max_height` | `height_min_cm` / `height_max_cm` |
| `min_weight` / `max_weight` | `weight_min_kg` / `weight_max_kg` |
| `min_expectancy` / `max_expectancy` | `life_expectancy_min` / `life_expectancy_max` |
| `energy_level_value` | `energy_level` (converted) |
| `trainability_value` | `trainability` (converted) |
| `shedding_value` | `shedding_level` (converted) |
| `grooming_frequency_value` | `grooming_frequency` (converted) |
| `demeanor_value` | `good_with_strangers` (converted) |

**Scoring column conversion** — applies to `energy_level_value`, `trainability_value`, `shedding_value`, `grooming_frequency_value`, `demeanor_value`:
```
integer_value = round(1 + float_value * 4)   # maps 0.0–1.0 → 1–5
```
Scoring columns with nulls: leave as NULL — Claude batch will fill them. Do not impute.

**Columns not stored:**
- `description` — used as input to Claude batch for `llm_summary` generation, not stored as its own column.
- `*_category` columns (e.g. `energy_level_category`, `shedding_category`) — human-readable labels, not stored.

**`popularity_rank`:** 79 breeds have no value. Leave as NULL — do not impute.

---

## 3. Dog API Specifics

- **Base URL:** `https://api.thedogapi.com/v1`
- **Auth:** `x-api-key` header using `DOG_API_KEY` from `.env`
- **Endpoints:**
  - `GET /v1/breeds` — pull once, save raw response to `data/raw/dog_api_breeds.json`
  - `GET /v1/images/search?breed_id={id}&limit=2` — per breed, for `image_url_1` and `image_url_2`
- **Key fields used:**
  - `name` — merge key (matches to `breed_name` in AKC CSV)
  - `image.url` — primary image URL
  - `hypoallergenic` — integer 0 or 1
  - `coat` — coat type string

**Name matching:** AKC and Dog API breed names do not match exactly. Use `rapidfuzz` fuzzy matching with threshold 85. Log all unmatched breeds to `data/processed/unmatched_breeds.txt` — do not silently drop them.

---

## 4. Claude Batch Generation

- **Purpose:** Fill all columns not sourced from AKC CSV or Dog API.
- **Input per breed:** `breed_name`, `description`, `temperament`, `akc_group`, already-populated scoring columns.
- **Batch size:** 20 breeds per API call.
- **Columns Claude fills:**
  - `origin_country`, `grooming_cost_tier`, `exercise_min_per_day`, `monthly_food_cost_usd`, `vet_cost_tier`, `monthly_total_cost_usd`
  - `playfulness`, `affection_level`, `intelligence`, `independence`, `barking_level`, `protective_instinct`, `separation_anxiety`
  - `good_with_kids`, `good_with_dogs`, `good_with_cats`, `good_with_elderly`
  - `apartment_suitable`, `needs_yard`, `heat_tolerance`, `cold_tolerance`, `urban_suitable`
  - `first_time_owner_suitable`, `experience_required`, `guard_dog`
  - `llm_summary`
- **API key:** `ANTHROPIC_API_KEY` from `.env`.

---

## 5. Scripts and Their Inputs/Outputs

| Script | Input | Output |
|---|---|---|
| `scripts/ingest_dog_api.py` | Dog API (live) | `data/raw/dog_api_breeds.json` |
| `scripts/process_and_merge.py` | `datasets/akc-data-latest.csv` + `data/raw/dog_api_breeds.json` + Anthropic API | `data/final/breeds.csv` |
| `scripts/load_to_turso.py` | `data/final/breeds.csv` | Turso DB + `breeds.db` (local) |

`load_to_turso.py` is run once. Do not re-run it against a populated database without dropping the table first.

---

## 6. Non-Obvious Rules

- **SQLite has no boolean type.** Store all boolean columns as `INTEGER` with values `0` or `1`.
- **`size_category`** is derived from `weight_max_kg`:
  - `≤9 kg` → `small`
  - `≤25 kg` → `medium`
  - `≤45 kg` → `large`
  - `>45 kg` → `giant`
- **`working_dog`** is derived: `1` if `akc_group` is `'Working Group'` or `'Herding Group'`, else `0`.
- **Always use `llm_summary`** when sending breed data to Groq. Never send raw numeric columns to the LLM.
- **`data/final/breeds.csv` must contain every schema column** before `load_to_turso.py` is run. Missing columns will cause the load to fail or produce an incomplete table.
