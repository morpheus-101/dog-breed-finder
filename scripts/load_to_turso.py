#!/usr/bin/env python3
"""
One-time script: loads data/final/breeds.csv into Turso and local breeds.db.

Run from the project root with the venv active:
    python scripts/load_to_turso.py [--force]

--force drops and recreates the breeds table before loading.
Without --force the script exits safely if either database is already populated.
"""

import argparse
import asyncio
import math
import os
import sqlite3
import sys
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
CSV_PATH = PROJECT_ROOT / "data" / "final" / "breeds.csv"
LOCAL_DB_PATH = PROJECT_ROOT / "breeds.db"

BATCH_SIZE = 10
EXPECTED_ROWS = 277

# Column order matches the authoritative schema in skills/data-ingestion.md.
# `id` is omitted — autoincrement, assigned by the DB.
COLUMNS = [
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

CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS breeds (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    breed_name                TEXT    NOT NULL,
    akc_group                 TEXT,
    popularity_rank           INTEGER,
    height_min_cm             REAL,
    height_max_cm             REAL,
    weight_min_kg             REAL,
    weight_max_kg             REAL,
    life_expectancy_min       INTEGER,
    life_expectancy_max       INTEGER,
    size_category             TEXT,
    energy_level              INTEGER,
    trainability              INTEGER,
    shedding_level            INTEGER,
    grooming_frequency        INTEGER,
    good_with_strangers       INTEGER,
    hypoallergenic            INTEGER,
    coat_type                 TEXT,
    image_url_1               TEXT,
    image_url_2               TEXT,
    origin_country            TEXT,
    grooming_cost_tier        INTEGER,
    exercise_min_per_day      INTEGER,
    monthly_food_cost_usd     INTEGER,
    vet_cost_tier             INTEGER,
    monthly_total_cost_usd    INTEGER,
    playfulness               INTEGER,
    affection_level           INTEGER,
    intelligence              INTEGER,
    independence              INTEGER,
    barking_level             INTEGER,
    protective_instinct       INTEGER,
    separation_anxiety        INTEGER,
    good_with_kids            INTEGER,
    good_with_dogs            INTEGER,
    good_with_cats            INTEGER,
    good_with_elderly         INTEGER,
    apartment_suitable        INTEGER,
    needs_yard                INTEGER,
    heat_tolerance            INTEGER,
    cold_tolerance            INTEGER,
    urban_suitable            INTEGER,
    first_time_owner_suitable INTEGER,
    experience_required       INTEGER,
    guard_dog                 INTEGER,
    working_dog               INTEGER NOT NULL,
    llm_summary               TEXT
)"""

DROP_TABLE_SQL = "DROP TABLE IF EXISTS breeds"

INSERT_SQL = (
    f"INSERT INTO breeds ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join(['?' for _ in COLUMNS])})"
)


def nan_to_none(val):
    """Map pandas NaN to None so the DB receives NULL, not 'nan'.

    Also converts numpy scalar types to native Python ints/floats so that
    sqlite3's executemany() and _turso_value() never receive numpy types.
    bool is checked before int because bool is a subclass of int in Python.
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return int(val)
    try:
        if math.isnan(val):
            return None
    except TypeError:
        pass
    if hasattr(val, "dtype"):
        if val.dtype.kind in ("i", "u"):
            return int(val)
        if val.dtype.kind == "f":
            return float(val)
    return val


def row_to_values(row) -> list:
    return [nan_to_none(row[col]) for col in COLUMNS]


# ── Local SQLite helpers ──────────────────────────────────────────────────────

def local_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def local_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM breeds").fetchone()[0]


def local_drop_recreate(conn: sqlite3.Connection):
    conn.execute(DROP_TABLE_SQL)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def local_insert(conn: sqlite3.Connection, rows: list[list]):
    conn.executemany(INSERT_SQL, rows)
    conn.commit()


# ── Turso HTTP API helpers (httpx) ────────────────────────────────────────────

def _turso_value(val) -> dict:
    """Convert a Python value to a Turso typed-value object."""
    if val is None:
        return {"type": "null"}
    if isinstance(val, bool):
        return {"type": "integer", "value": str(int(val))}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": val}
    return {"type": "text", "value": str(val)}


async def _turso_pipeline(
    http: httpx.AsyncClient,
    url: str,
    token: str,
    stmts: list[dict],
) -> list[dict]:
    """POST a list of SQL statements to the Turso /v2/pipeline endpoint."""
    requests = [{"type": "execute", "stmt": s} for s in stmts]
    requests.append({"type": "close"})
    resp = await http.post(
        f"{url}/v2/pipeline",
        headers={"Authorization": f"Bearer {token}"},
        json={"requests": requests},
        timeout=60.0,
    )
    if not resp.is_success:
        raise RuntimeError(
            f"Turso HTTP {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()["results"]


async def turso_execute(
    http: httpx.AsyncClient,
    url: str,
    token: str,
    sql: str,
    args: list | None = None,
) -> dict:
    stmt: dict = {"sql": sql}
    if args is not None:
        stmt["args"] = [_turso_value(v) for v in args]
    results = await _turso_pipeline(http, url, token, [stmt])
    result = results[0]
    if result.get("type") == "error":
        raise RuntimeError(f"Turso error: {result['error']}")
    return result["response"]["result"]


async def turso_row_count(
    http: httpx.AsyncClient, url: str, token: str
) -> int:
    result = await turso_execute(
        http, url, token, "SELECT COUNT(*) FROM breeds"
    )
    return int(result["rows"][0][0]["value"])


async def turso_drop_recreate(
    http: httpx.AsyncClient, url: str, token: str
):
    await turso_execute(http, url, token, DROP_TABLE_SQL)
    await turso_execute(http, url, token, CREATE_TABLE_SQL)


async def turso_insert_batched(
    http: httpx.AsyncClient,
    url: str,
    token: str,
    rows: list[list],
):
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i: i + BATCH_SIZE]
        stmts = [
            {
                "sql": INSERT_SQL,
                "args": [_turso_value(v) for v in row],
            }
            for row in chunk
        ]
        results = await _turso_pipeline(http, url, token, stmts)
        for j, r in enumerate(results[:-1]):  # skip the trailing close result
            if r.get("type") == "error":
                raise RuntimeError(
                    f"Insert error on row {i + j}: {r['error']}"
                )
        total += len(chunk)
        print(f"  [turso] inserted {total}/{len(rows)} rows")


async def turso_sample_row(
    http: httpx.AsyncClient,
    url: str,
    token: str,
    breed_name: str,
) -> dict | None:
    result = await turso_execute(
        http,
        url,
        token,
        "SELECT * FROM breeds WHERE breed_name = ?",
        [breed_name],
    )
    if not result["rows"]:
        return None
    cols = [c["name"] for c in result["cols"]]
    vals = [
        v.get("value") if v["type"] != "null" else None
        for v in result["rows"][0]
    ]
    return dict(zip(cols, vals))


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description=(
            "Load data/final/breeds.csv into Turso and local breeds.db."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and recreate breeds table before loading.",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    turso_url = os.environ.get("TURSO_URL", "").strip().rstrip("/")
    # libsql:// is the native Turso scheme; the HTTP pipeline API needs https://
    turso_url = turso_url.replace("libsql://", "https://", 1)
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not turso_url or not turso_token:
        print(
            "ERROR: TURSO_URL or TURSO_AUTH_TOKEN not set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    if not CSV_PATH.exists():
        print(
            f"ERROR: {CSV_PATH} not found. Run process_and_merge.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH)
    missing_cols = [c for c in COLUMNS if c not in df.columns]
    if missing_cols:
        print(
            f"ERROR: CSV is missing required columns: {missing_cols}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  {len(df)} rows, {len(df.columns)} columns found in CSV.")

    all_rows = [row_to_values(df.iloc[i]) for i in range(len(df))]

    errors: list[str] = []

    # ── Local SQLite — create table and check existing rows ──
    print("\n[local] Connecting to breeds.db ...")
    local_conn = local_connect()
    local_conn.execute(CREATE_TABLE_SQL)
    local_conn.commit()
    local_existing = local_row_count(local_conn)

    # ── Turso — create table and check existing rows ──
    print("[turso] Connecting to Turso ...")
    async with httpx.AsyncClient() as http:
        await turso_execute(http, turso_url, turso_token, CREATE_TABLE_SQL)
        turso_existing = await turso_row_count(http, turso_url, turso_token)

        # ── Guard: populated tables without --force ──
        if (local_existing > 0 or turso_existing > 0) and not args.force:
            print(
                f"\nWARNING: breeds table already has rows "
                f"(local={local_existing}, turso={turso_existing}).\n"
                "Re-run with --force to drop and reload. "
                "Exiting without changes."
            )
            local_conn.close()
            sys.exit(0)

        # ── Drop and recreate if --force ──
        if args.force:
            print(
                "\n[local]  --force: dropping and recreating breeds table ..."
            )
            local_drop_recreate(local_conn)
            print(
                "[turso]  --force: dropping and recreating breeds table ..."
            )
            await turso_drop_recreate(http, turso_url, turso_token)

        # ── Insert: local SQLite ──
        print(f"\n[local] Inserting {len(all_rows)} rows ...")
        try:
            local_insert(local_conn, all_rows)
        except Exception as e:
            errors.append(f"local: {e}")
            print(f"[local] ERROR during insert: {e}", file=sys.stderr)
        local_count = local_row_count(local_conn)
        local_conn.close()
        print(f"[local] Row count after insert: {local_count}")

        # ── Insert: Turso ──
        print(
            f"\n[turso] Inserting {len(all_rows)} rows "
            f"in batches of {BATCH_SIZE} ..."
        )
        try:
            await turso_insert_batched(
                http, turso_url, turso_token, all_rows
            )
        except Exception as e:
            errors.append(f"turso: {e}")
            print(f"[turso] ERROR during insert: {e}", file=sys.stderr)
        turso_count = await turso_row_count(http, turso_url, turso_token)
        print(f"[turso] Row count after insert: {turso_count}")

        # ── Sample validation ──
        print("\n[turso] Fetching sample row (Golden Retriever) ...")
        sample = await turso_sample_row(
            http, turso_url, turso_token, "Golden Retriever"
        )
        if sample:
            print("  Sample row:")
            for k, v in sample.items():
                print(f"    {k}: {v}")
        else:
            msg = (
                "Golden Retriever not found — "
                "verify breed_name spelling in breeds.csv"
            )
            print(f"  WARNING: {msg}")
            errors.append(msg)

    # ── Summary ──
    local_ok = local_count == EXPECTED_ROWS
    turso_ok = turso_count == EXPECTED_ROWS

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  CSV rows read:          {len(all_rows)}")
    print(f"  Columns loaded:         {len(COLUMNS)}")
    print(
        f"  Local breeds.db rows:   {local_count}  "
        f"{'OK' if local_ok else f'MISMATCH (expected {EXPECTED_ROWS})'}"
    )
    print(
        f"  Turso rows:             {turso_count}  "
        f"{'OK' if turso_ok else f'MISMATCH (expected {EXPECTED_ROWS})'}"
    )
    print(f"  Errors:                 {len(errors)}")
    for err in errors:
        print(f"    - {err}")

    if local_ok and turso_ok and not errors:
        print(
            f"\nLoad complete. {EXPECTED_ROWS} rows written to both databases."
        )
    else:
        print(
            "\nLoad finished with issues — review output above.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
