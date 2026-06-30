#!/usr/bin/env python3
"""
Data quality and integrity validation for the breeds table in local breeds.db.

Run from the project root with the venv active:
    python scripts/validate_breeds_data.py

Exits with status 0 if all hard checks pass (warnings are non-fatal).
Exits with status 1 if any hard failures are detected.
"""

import sqlite3
import struct
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "breeds.db"

EXPECTED_ROWS = 277

# Authoritative column list from skills/data-ingestion.md §1 (excluding `id`).
SCHEMA_COLUMNS = [
    "breed_name", "akc_group", "popularity_rank",
    "height_min_cm", "height_max_cm", "weight_min_kg", "weight_max_kg",
    "life_expectancy_min", "life_expectancy_max", "size_category",
    "energy_level", "trainability", "shedding_level", "grooming_frequency",
    "good_with_strangers", "hypoallergenic", "coat_type",
    "image_url_1", "image_url_2", "origin_country",
    "grooming_cost_tier", "exercise_min_per_day", "monthly_food_cost_usd",
    "vet_cost_tier", "monthly_total_cost_usd",
    "playfulness", "affection_level", "intelligence", "independence",
    "barking_level", "protective_instinct", "separation_anxiety",
    "good_with_kids", "good_with_dogs", "good_with_cats", "good_with_elderly",
    "apartment_suitable", "needs_yard", "heat_tolerance", "cold_tolerance",
    "urban_suitable", "first_time_owner_suitable", "experience_required",
    "guard_dog", "working_dog", "llm_summary",
]

# Columns the schema marks as NOT NULL.
NON_NULLABLE = {"breed_name", "hypoallergenic", "size_category", "working_dog"}

# 1–5 scored trait columns.
SCORE_1_5 = [
    "energy_level", "trainability", "shedding_level", "grooming_frequency",
    "good_with_strangers", "playfulness", "affection_level", "intelligence",
    "independence", "barking_level", "protective_instinct", "separation_anxiety",
    "heat_tolerance", "cold_tolerance",
]

# 1–3 tier columns.
TIER_1_3 = ["experience_required", "vet_cost_tier", "grooming_cost_tier"]

# Boolean (0/1) columns.
BOOL_COLS = [
    "hypoallergenic", "apartment_suitable", "needs_yard", "urban_suitable",
    "first_time_owner_suitable", "guard_dog", "working_dog",
    "good_with_kids", "good_with_dogs", "good_with_cats", "good_with_elderly",
]

# Expected null counts from the last known good pipeline run (breeds.db baseline).
# Format: column → (min_allowed, max_allowed)
# Columns not listed are expected to have 0 nulls.
EXPECTED_NULL_BOUNDS: dict[str, tuple[int, int]] = {
    "popularity_rank":    (74, 84),   # schema says ~79; allow ±5
    "weight_min_kg":      (0, 5),
    "weight_max_kg":      (0, 5),
    "life_expectancy_min": (0, 8),
    "life_expectancy_max": (0, 8),
    "size_category":      (0, 5),
    "energy_level":       (0, 10),
    "trainability":       (0, 30),
    "shedding_level":     (0, 25),
    "grooming_frequency": (0, 12),
    "good_with_strangers": (0, 30),
    "hypoallergenic":     (0, 10),
    "coat_type":          (0, 5),
    "image_url_1":        (0, 25),
    "image_url_2":        (0, 200),   # Dog API often lacks a second image
    "origin_country":     (0, 15),
    "akc_group":          (0, 5),
    "height_min_cm":      (0, 5),
    "height_max_cm":      (0, 5),
}

# Allowed values for categorical text columns.
VALID_SIZE_CATEGORIES = {"small", "medium", "large", "giant"}
VALID_COAT_TYPES = {"short", "medium", "long", "double", "wire", "curly"}

# AKC groups that qualify a breed as working_dog = 1.
WORKING_DOG_GROUPS = {"Working Group", "Herding Group"}

# Spot-check expectations: breed_name → {column: expected_value_or_set}
# Use a set for "any of these values" checks.
SPOT_CHECKS: list[dict] = [
    {
        "breed": "Golden Retriever",
        "checks": {
            "energy_level": {4, 5},
            "good_with_kids": {1},
        },
    },
    {
        "breed": "Chihuahua",
        "checks": {
            "size_category": {"small"},
        },
    },
    {
        "breed": "Great Dane",
        "checks": {
            "size_category": {"large", "giant"},
        },
    },
    {
        "breed": "Siberian Husky",
        "checks": {
            "heat_tolerance": {1, 2},
        },
    },
    {
        "breed": "Poodle (Standard)",
        "checks": {
            "hypoallergenic": {1},
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def decode_blob_bool(val) -> int | None:
    """Interpret a SQLite BLOB-stored boolean as 0 or 1.

    Python's sqlite3 module stores Python bool values as 8-byte little-endian
    BLOBs. This decodes them back to integer 0/1 so logical checks can proceed
    even when the storage type is wrong.
    """
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, bytes):
        if len(val) == 8:
            return struct.unpack("<q", val)[0]
        return int.from_bytes(val, "little")
    return None


class Reporter:
    def __init__(self):
        self.passes = 0
        self.warnings = 0
        self.failures = 0
        self._details: list[str] = []

    def ok(self, msg: str):
        self.passes += 1
        print(f"  [PASS] {msg}")

    def warn(self, msg: str, details: list[str] | None = None):
        self.warnings += 1
        print(f"  [WARN] {msg}")
        for d in (details or []):
            print(f"         {d}")

    def fail(self, msg: str, details: list[str] | None = None):
        self.failures += 1
        print(f"  [FAIL] {msg}")
        for d in (details or []):
            print(f"         {d}")

    def summary(self):
        total = self.passes + self.warnings + self.failures
        print()
        print("=" * 62)
        print(f"SUMMARY: {total} checks — "
              f"{self.passes} passed, "
              f"{self.warnings} warnings, "
              f"{self.failures} failures")
        print("=" * 62)


def scalar(cur: sqlite3.Cursor, sql: str, params=()) -> int | float | str | None:
    return cur.execute(sql, params).fetchone()[0]


def fetch_column(cur: sqlite3.Cursor, col: str) -> list[tuple]:
    """Return (breed_name, <col>) for all rows."""
    return cur.execute(
        f'SELECT breed_name, "{col}" FROM breeds ORDER BY id'
    ).fetchall()


# ── Category 1: Row and schema integrity ─────────────────────────────────────

def check_row_and_schema(cur: sqlite3.Cursor, r: Reporter):
    print("\n[1] Row and schema integrity")

    # Row count
    count = scalar(cur, "SELECT COUNT(*) FROM breeds")
    if count == EXPECTED_ROWS:
        r.ok(f"Row count = {count}")
    else:
        r.fail(f"Row count = {count}, expected {EXPECTED_ROWS}")

    # Column presence and types
    pragma_rows = cur.execute("PRAGMA table_info(breeds)").fetchall()
    # pragma columns: cid, name, type, notnull, dflt_value, pk
    db_cols = {row[1]: row[2].upper() for row in pragma_rows}

    missing = [c for c in SCHEMA_COLUMNS if c not in db_cols]
    if missing:
        r.fail(f"{len(missing)} schema column(s) missing from table",
               [f"Missing: {', '.join(missing)}"])
    else:
        r.ok(f"All {len(SCHEMA_COLUMNS)} schema columns present")

    extra = [c for c in db_cols if c not in SCHEMA_COLUMNS and c != "id"]
    if extra:
        r.warn(f"Extra column(s) not in schema: {', '.join(extra)}")

    # breed_name: no nulls, no duplicates
    null_names = scalar(cur, "SELECT COUNT(*) FROM breeds WHERE breed_name IS NULL")
    if null_names == 0:
        r.ok("breed_name has no NULLs")
    else:
        r.fail(f"breed_name has {null_names} NULL value(s)")

    dup_count = scalar(
        cur,
        "SELECT COUNT(*) FROM (SELECT breed_name FROM breeds "
        "GROUP BY breed_name HAVING COUNT(*) > 1)"
    )
    if dup_count == 0:
        r.ok("breed_name has no duplicates")
    else:
        dups = cur.execute(
            "SELECT breed_name, COUNT(*) FROM breeds "
            "GROUP BY breed_name HAVING COUNT(*) > 1"
        ).fetchall()
        r.fail(f"breed_name has {dup_count} duplicate value(s)",
               [f"{name!r} appears {n} times" for name, n in dups])

    # id: unique and sequential 1..N
    distinct_ids = scalar(cur, "SELECT COUNT(DISTINCT id) FROM breeds")
    min_id = scalar(cur, "SELECT MIN(id) FROM breeds")
    max_id = scalar(cur, "SELECT MAX(id) FROM breeds")
    if distinct_ids == count and min_id == 1 and max_id == count:
        r.ok(f"id is unique and sequential 1–{count}")
    else:
        r.fail(f"id is not sequential 1–{count}",
               [f"distinct={distinct_ids}, min={min_id}, max={max_id}"])


# ── Category 2: Null tolerance checks ────────────────────────────────────────

def check_null_tolerance(cur: sqlite3.Cursor, r: Reporter):
    print("\n[2] Null tolerance")

    for col in SCHEMA_COLUMNS:
        null_count = scalar(cur, f'SELECT COUNT(*) FROM breeds WHERE "{col}" IS NULL')

        # Never-null columns
        if col in NON_NULLABLE:
            if null_count == 0:
                r.ok(f"{col}: no NULLs (required)")
            else:
                r.fail(f"{col}: {null_count} NULL(s) — column must never be NULL")
            continue

        # 100% null — always a pipeline failure
        if null_count == EXPECTED_ROWS:
            r.fail(f"{col}: ALL {null_count} rows are NULL — pipeline failure")
            continue

        # Columns expected to have exactly 0 nulls (not in bounds table)
        if col not in EXPECTED_NULL_BOUNDS:
            if null_count == 0:
                r.ok(f"{col}: 0 NULLs (expected 0)")
            else:
                r.fail(
                    f"{col}: {null_count} NULL(s) — expected 0",
                    [f"Run: SELECT breed_name FROM breeds "
                     f"WHERE \"{col}\" IS NULL LIMIT 5"]
                )
            continue

        # Columns with allowed null ranges
        lo, hi = EXPECTED_NULL_BOUNDS[col]
        if lo <= null_count <= hi:
            r.ok(f"{col}: {null_count} NULLs (within expected {lo}–{hi})")
        else:
            r.fail(
                f"{col}: {null_count} NULLs — outside expected range {lo}–{hi}",
                [f"Possible pipeline regression or column loss"]
            )


# ── Category 3: Value range and domain checks ─────────────────────────────────

def check_value_ranges(cur: sqlite3.Cursor, r: Reporter):
    print("\n[3] Value range and domain")

    # 1–5 scored columns
    for col in SCORE_1_5:
        bad = cur.execute(
            f'SELECT breed_name, "{col}" FROM breeds '
            f'WHERE "{col}" IS NOT NULL AND ("{col}" < 1 OR "{col}" > 5)'
        ).fetchall()
        if bad:
            r.fail(
                f"{col}: {len(bad)} out-of-range value(s) (expected 1–5)",
                [f"  {name!r}: {val}" for name, val in bad[:5]]
            )
        else:
            r.ok(f"{col}: all values in [1, 5] or NULL")

    # 1–3 tier columns
    for col in TIER_1_3:
        bad = cur.execute(
            f'SELECT breed_name, "{col}" FROM breeds '
            f'WHERE "{col}" IS NOT NULL AND ("{col}" < 1 OR "{col}" > 3)'
        ).fetchall()
        if bad:
            r.fail(
                f"{col}: {len(bad)} out-of-range value(s) (expected 1–3)",
                [f"  {name!r}: {val}" for name, val in bad[:5]]
            )
        else:
            r.ok(f"{col}: all values in [1, 3] or NULL")

    # Boolean columns — type check (must be INTEGER, not BLOB/TEXT)
    blob_cols = []
    for col in BOOL_COLS:
        blob_n = scalar(
            cur,
            f'SELECT COUNT(*) FROM breeds '
            f'WHERE typeof("{col}") = \'blob\''
        )
        if blob_n > 0:
            blob_cols.append((col, blob_n))

    if blob_cols:
        r.fail(
            f"{len(blob_cols)} boolean column(s) stored as BLOB instead of INTEGER",
            [f"  {col}: {n}/{EXPECTED_ROWS} rows are BLOBs "
             f"(Python bool not cast to int before SQLite insert)"
             for col, n in blob_cols]
        )
    else:
        r.ok("All boolean columns stored as INTEGER (not BLOB)")

    # Boolean columns — logical value check (interpret blobs for correctness)
    for col in BOOL_COLS:
        bad_rows = []
        for name, raw in fetch_column(cur, col):
            val = decode_blob_bool(raw)
            if val is not None and val not in (0, 1):
                bad_rows.append((name, raw))
        if bad_rows:
            r.fail(
                f"{col}: {len(bad_rows)} value(s) not in {{0, 1}}",
                [f"  {name!r}: {val}" for name, val in bad_rows[:5]]
            )
        else:
            r.ok(f"{col}: all logical values are 0 or 1")

    # size_category domain
    bad = cur.execute(
        "SELECT breed_name, size_category FROM breeds "
        "WHERE size_category IS NOT NULL AND size_category NOT IN "
        "('small','medium','large','giant')"
    ).fetchall()
    if bad:
        r.fail(
            f"size_category: {len(bad)} invalid value(s)",
            [f"  {name!r}: {val!r}" for name, val in bad]
        )
    else:
        r.ok("size_category: all values in {small, medium, large, giant} or NULL")

    # coat_type domain
    bad = cur.execute(
        "SELECT breed_name, coat_type FROM breeds "
        "WHERE coat_type IS NOT NULL AND coat_type NOT IN "
        "('short','medium','long','double','wire','curly')"
    ).fetchall()
    if bad:
        r.fail(
            f"coat_type: {len(bad)} invalid value(s)",
            [f"  {name!r}: {val!r}" for name, val in bad]
        )
    else:
        r.ok("coat_type: all values in {short, medium, long, double, wire, curly} or NULL")

    # weight: max >= min
    bad = cur.execute(
        "SELECT breed_name, weight_min_kg, weight_max_kg FROM breeds "
        "WHERE weight_max_kg IS NOT NULL AND weight_min_kg IS NOT NULL "
        "AND weight_max_kg < weight_min_kg"
    ).fetchall()
    if bad:
        r.fail(
            f"weight: {len(bad)} breed(s) where weight_max_kg < weight_min_kg",
            [f"  {name!r}: min={mn}, max={mx}" for name, mn, mx in bad]
        )
    else:
        r.ok("weight_max_kg >= weight_min_kg for all non-null pairs")

    # height: max >= min
    bad = cur.execute(
        "SELECT breed_name, height_min_cm, height_max_cm FROM breeds "
        "WHERE height_max_cm IS NOT NULL AND height_min_cm IS NOT NULL "
        "AND height_max_cm < height_min_cm"
    ).fetchall()
    if bad:
        r.fail(
            f"height: {len(bad)} breed(s) where height_max_cm < height_min_cm",
            [f"  {name!r}: min={mn}, max={mx}" for name, mn, mx in bad]
        )
    else:
        r.ok("height_max_cm >= height_min_cm for all non-null pairs")

    # life_expectancy: max >= min
    bad = cur.execute(
        "SELECT breed_name, life_expectancy_min, life_expectancy_max FROM breeds "
        "WHERE life_expectancy_max IS NOT NULL AND life_expectancy_min IS NOT NULL "
        "AND life_expectancy_max < life_expectancy_min"
    ).fetchall()
    if bad:
        r.fail(
            f"life_expectancy: {len(bad)} breed(s) where max < min",
            [f"  {name!r}: min={mn}, max={mx}" for name, mn, mx in bad]
        )
    else:
        r.ok("life_expectancy_max >= life_expectancy_min for all non-null pairs")


# ── Category 4: Logical consistency checks ────────────────────────────────────

def check_logical_consistency(cur: sqlite3.Cursor, r: Reporter):
    print("\n[4] Logical consistency")

    # Hypoallergenic → shedding_level should generally be low (≤2).
    # Soft check: flag as warning, not failure.
    hypo_high_shed = []
    for name, raw_hypo, shed in cur.execute(
        "SELECT breed_name, hypoallergenic, shedding_level FROM breeds "
        "WHERE shedding_level IS NOT NULL"
    ).fetchall():
        hypo = decode_blob_bool(raw_hypo)
        if hypo == 1 and shed is not None and shed > 2:
            hypo_high_shed.append((name, shed))

    if hypo_high_shed:
        r.warn(
            f"{len(hypo_high_shed)} hypoallergenic breed(s) with shedding_level > 2 "
            "(soft correlation — review for data errors)",
            [f"  {name!r}: shedding_level={s}" for name, s in hypo_high_shed]
        )
    else:
        r.ok("Hypoallergenic breeds all have shedding_level ≤ 2 (or null)")

    # working_dog=1 must be in Working Group or Herding Group only.
    bad_working = []
    for name, raw_wd, akc_group in cur.execute(
        "SELECT breed_name, working_dog, akc_group FROM breeds"
    ).fetchall():
        wd = decode_blob_bool(raw_wd)
        if wd == 1 and akc_group not in WORKING_DOG_GROUPS:
            bad_working.append((name, akc_group))

    if bad_working:
        r.fail(
            f"working_dog=1 but wrong akc_group for {len(bad_working)} breed(s)",
            [f"  {name!r}: akc_group={grp!r}" for name, grp in bad_working[:10]]
        )
    else:
        r.ok("All working_dog=1 breeds are in Working Group or Herding Group")

    # monthly_total_cost_usd >= monthly_food_cost_usd
    bad_cost = cur.execute(
        "SELECT breed_name, monthly_food_cost_usd, monthly_total_cost_usd "
        "FROM breeds WHERE monthly_total_cost_usd IS NOT NULL "
        "AND monthly_food_cost_usd IS NOT NULL "
        "AND monthly_total_cost_usd < monthly_food_cost_usd"
    ).fetchall()
    if bad_cost:
        r.fail(
            f"monthly_total_cost_usd < monthly_food_cost_usd for "
            f"{len(bad_cost)} breed(s)",
            [f"  {name!r}: food={food}, total={total}"
             for name, food, total in bad_cost[:5]]
        )
    else:
        r.ok("monthly_total_cost_usd >= monthly_food_cost_usd for all non-null pairs")


# ── Category 5: Content quality checks ───────────────────────────────────────

def check_content_quality(cur: sqlite3.Cursor, r: Reporter):
    print("\n[5] Content quality")

    # llm_summary: never empty
    empty_sum = cur.execute(
        "SELECT breed_name FROM breeds "
        "WHERE llm_summary IS NULL OR length(trim(llm_summary)) = 0"
    ).fetchall()
    if empty_sum:
        r.fail(
            f"llm_summary: {len(empty_sum)} breed(s) with NULL or empty summary",
            [f"  {row[0]!r}" for row in empty_sum[:5]]
        )
    else:
        r.ok("llm_summary: no NULL or empty values")

    # llm_summary: minimum length 20 chars
    short_sum = cur.execute(
        "SELECT breed_name, length(llm_summary) FROM breeds "
        "WHERE llm_summary IS NOT NULL AND length(trim(llm_summary)) < 20"
    ).fetchall()
    if short_sum:
        r.fail(
            f"llm_summary: {len(short_sum)} breed(s) with summary < 20 characters",
            [f"  {name!r}: {length} chars" for name, length in short_sum]
        )
    else:
        r.ok("llm_summary: all non-null summaries are ≥ 20 characters")

    # llm_summary: no markdown artifacts or placeholder text
    artifacts = cur.execute(
        "SELECT breed_name FROM breeds WHERE "
        "llm_summary LIKE '%```%' OR "
        "lower(llm_summary) LIKE '%null%' OR "
        "lower(llm_summary) LIKE '%undefined%'"
    ).fetchall()
    if artifacts:
        r.fail(
            f"llm_summary: {len(artifacts)} breed(s) contain artifact text "
            "('```', 'null', or 'undefined')",
            [f"  {row[0]!r}" for row in artifacts[:5]]
        )
    else:
        r.ok("llm_summary: no markdown artifacts or placeholder text")

    # image_url_1: where present, must start with 'http'
    bad_url1 = cur.execute(
        "SELECT breed_name, image_url_1 FROM breeds "
        "WHERE image_url_1 IS NOT NULL AND image_url_1 NOT LIKE 'http%'"
    ).fetchall()
    if bad_url1:
        r.fail(
            f"image_url_1: {len(bad_url1)} invalid URL(s)",
            [f"  {name!r}: {url!r}" for name, url in bad_url1[:5]]
        )
    else:
        null1 = scalar(cur, "SELECT COUNT(*) FROM breeds WHERE image_url_1 IS NULL")
        r.ok(f"image_url_1: all present URLs start with 'http' "
             f"({null1} NULL — no image available)")

    # image_url_2: where present, must start with 'http'
    bad_url2 = cur.execute(
        "SELECT breed_name, image_url_2 FROM breeds "
        "WHERE image_url_2 IS NOT NULL AND image_url_2 NOT LIKE 'http%'"
    ).fetchall()
    if bad_url2:
        r.fail(
            f"image_url_2: {len(bad_url2)} invalid URL(s)",
            [f"  {name!r}: {url!r}" for name, url in bad_url2[:5]]
        )
    else:
        null2 = scalar(cur, "SELECT COUNT(*) FROM breeds WHERE image_url_2 IS NULL")
        r.ok(f"image_url_2: all present URLs start with 'http' "
             f"({null2} NULL — second image unavailable)")


# ── Category 6: Known breed spot checks ──────────────────────────────────────

def check_spot_checks(cur: sqlite3.Cursor, r: Reporter):
    print("\n[6] Known breed spot checks")

    for spec in SPOT_CHECKS:
        breed = spec["breed"]
        checks = spec["checks"]

        row = cur.execute(
            f"SELECT * FROM breeds WHERE breed_name = ?", (breed,)
        ).fetchone()

        if row is None:
            r.fail(f"{breed!r}: breed not found in table")
            continue

        col_names = [desc[0] for desc in cur.description]
        data = dict(zip(col_names, row))

        for col, expected_set in checks.items():
            raw = data.get(col)
            # Decode blob booleans for comparison
            val = decode_blob_bool(raw) if col in BOOL_COLS else raw

            if val in expected_set:
                r.ok(f"{breed!r}: {col} = {val!r} (expected one of {expected_set})")
            else:
                r.fail(
                    f"{breed!r}: {col} = {val!r}, expected one of {expected_set}"
                )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        print("Run scripts/load_to_turso.py first to populate breeds.db.",
              file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    r = Reporter()

    try:
        check_row_and_schema(cur, r)
        check_null_tolerance(cur, r)
        check_value_ranges(cur, r)
        check_logical_consistency(cur, r)
        check_content_quality(cur, r)
        check_spot_checks(cur, r)
    finally:
        conn.close()

    r.summary()

    if r.failures > 0:
        print(f"\n{r.failures} hard failure(s) detected — fix before deploying.")
        sys.exit(1)
    elif r.warnings > 0:
        print(f"\nAll hard checks passed. {r.warnings} warning(s) to review.")
    else:
        print("\nAll checks passed. Breed table is ready for the ranking pipeline.")


if __name__ == "__main__":
    main()
