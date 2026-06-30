# Skill: Data Processing

Read this file before working on `scripts/process_and_merge.py`.
For the authoritative schema (column names, types, sources), read `skills/data-ingestion.md`.

---

## 1. Purpose of `process_and_merge.py`

One-time setup script. Not run at runtime.

Takes:
- `datasets/akc-data-latest.csv`
- `data/raw/dog_api_breeds.json` (produced by `scripts/ingest_dog_api.py`)

Produces:
- `data/final/breeds.csv` — complete, schema-conformant file ready for `load_to_turso.py`

Intermediate output for resumability: `data/processed/breeds_with_claude.csv`

---

## 2. Merge Strategy

**Spine:** AKC CSV — 277 breeds, all rows must survive to the final output.

**Join type:** Left join. AKC CSV is left; Dog API JSON is right. Missing Dog API data results in NULLs, not dropped rows.

**Join key:** `breed_name` (AKC) matched to `name` (Dog API) via `rapidfuzz` fuzzy matching, threshold 85.
- Log unmatched Dog API breeds to `data/processed/unmatched_breeds.txt`.
- Do not silently drop unmatched breeds — log and continue.

**Post-merge transforms, in order:**
1. Rename AKC CSV columns to schema names (see `skills/data-ingestion.md` §2 mapping table).
2. Apply scoring column conversion: `round(1 + float_value * 4)` for `energy_level_value`, `trainability_value`, `shedding_value`, `grooming_frequency_value`, `demeanor_value`. Leave NULLs as NULL — do not impute.
3. Derive `size_category` from `weight_max_kg` (thresholds in `skills/data-ingestion.md` §6).
4. Derive `working_dog` from `akc_group` (logic in `skills/data-ingestion.md` §6).
5. Drop columns not in schema: all `*_category` columns from AKC CSV.
6. Retain `description` temporarily as Claude batch input — drop it before writing final output.

**Validation after merge:** Assert `breed_name` is unique across all rows. Duplicates indicate a merge error — raise, do not continue.

---

## 3. Claude Batch Generation

- **Model:** `claude-haiku-4-5-20251001` via Anthropic API (`ANTHROPIC_API_KEY` from `.env`)
- **Batch size:** 20 breeds per API call
- **Skip condition:** Do not call the API for breeds that already have all Claude batch columns populated — check before each batch.

**Prompt requirements:**
- Input context per breed: `breed_name`, `description`, `temperament`, `akc_group`, any already-populated numeric columns.
- Instruct Claude to return a JSON array only — one object per breed — with no preamble, no markdown, no extra text.
- The `llm_summary` field must be 2–3 sentences maximum — state this constraint explicitly in the prompt.
- Claude is responsible for the columns listed in `skills/data-ingestion.md` §4.

**Response handling:**
- Parse the JSON response and merge back into the main dataframe on `breed_name`.
- If a batch fails or returns malformed JSON: log the affected breed names to `data/processed/claude_batch_errors.txt` and continue — do not crash.

**Checkpointing:** Save intermediate progress to `data/processed/breeds_with_claude.csv` after every 5 batches.

---

## 4. Output Requirements

- **File:** `data/final/breeds.csv`
- Must contain every column defined in `skills/data-ingestion.md` §1, in schema order.
- No column may be entirely empty — individual cell NULLs are acceptable.
- `description` column must be dropped before writing this file.
- Boolean columns must be `0` or `1` integers — not Python `True`/`False`.

---

## 5. Non-Obvious Rules

- **Do not use `pandas.fillna` to impute nulls.** Leave NULLs as-is for Turso to store.
- **Boolean dtype trap:** pandas may infer bool columns as Python `True`/`False` when parsing Claude's JSON. Cast all boolean schema columns to `int` before writing CSV.
- **Column order matters:** `load_to_turso.py` expects columns in schema order. Reindex the dataframe to match `skills/data-ingestion.md` §1 before writing.
- **`llm_summary` length enforcement** belongs in the Claude prompt, not as a post-processing truncation step.
- **Do not re-run Claude batch** over breeds already present in `data/processed/breeds_with_claude.csv` if resuming after interruption — read the checkpoint and skip populated rows.
