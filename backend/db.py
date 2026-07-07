"""Database access layer. DB_MODE=local uses breeds.db (sqlite3); DB_MODE=turso uses Turso HTTP API (httpx)."""

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_PATH = PROJECT_ROOT / "breeds.db"

# Turso's HTTP API returns every column value as a string. SQLite (local dev)
# returns native types already, so this coercion only applies to the Turso path.
REAL_COLUMNS = {
    "height_min_cm",
    "height_max_cm",
    "weight_min_kg",
    "weight_max_kg",
}

INTEGER_COLUMNS = {
    "popularity_rank",
    "life_expectancy_min",
    "life_expectancy_max",
    "energy_level",
    "trainability",
    "shedding_level",
    "grooming_frequency",
    "good_with_strangers",
    "hypoallergenic",
    "grooming_cost_tier",
    "exercise_min_per_day",
    "monthly_food_cost_usd",
    "vet_cost_tier",
    "monthly_total_cost_usd",
    "playfulness",
    "affection_level",
    "intelligence",
    "independence",
    "barking_level",
    "protective_instinct",
    "separation_anxiety",
    "good_with_kids",
    "good_with_dogs",
    "good_with_cats",
    "good_with_elderly",
    "apartment_suitable",
    "needs_yard",
    "heat_tolerance",
    "cold_tolerance",
    "urban_suitable",
    "first_time_owner_suitable",
    "experience_required",
    "guard_dog",
    "working_dog",
}


def _coerce_turso_value(col_name: str, value):
    if value is None:
        return None
    if col_name in REAL_COLUMNS:
        return float(value)
    if col_name in INTEGER_COLUMNS:
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                "coercion_warning", extra={"column": col_name, "value": str(value)}
            )
            return value
    return value


def _get_all_breeds_local() -> list[dict]:
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM breeds").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _get_breed_by_name_local(breed_name: str) -> Optional[dict]:
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM breeds WHERE breed_name = ?", (breed_name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_breed_by_name_turso(breed_name: str) -> Optional[dict]:
    turso_url = os.environ["TURSO_URL"]
    turso_auth_token = os.environ["TURSO_AUTH_TOKEN"]

    http_url = turso_url.replace("libsql://", "https://")
    response = httpx.post(
        f"{http_url}/v2/pipeline",
        headers={"Authorization": f"Bearer {turso_auth_token}"},
        json={
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": "SELECT * FROM breeds WHERE breed_name = ?",
                        "args": [{"type": "text", "value": breed_name}],
                    },
                },
                {"type": "close"},
            ]
        },
    )
    response.raise_for_status()
    result = response.json()

    result_set = result["results"][0]["response"]["result"]
    columns = [col["name"] for col in result_set["cols"]]
    rows = result_set["rows"]

    if not rows:
        return None

    return {
        col_name: _coerce_turso_value(col_name, cell.get("value"))
        for col_name, cell in zip(columns, rows[0])
    }


def _get_all_breeds_turso() -> list[dict]:
    turso_url = os.environ["TURSO_URL"]
    turso_auth_token = os.environ["TURSO_AUTH_TOKEN"]

    http_url = turso_url.replace("libsql://", "https://")
    response = httpx.post(
        f"{http_url}/v2/pipeline",
        headers={"Authorization": f"Bearer {turso_auth_token}"},
        json={
            "requests": [
                {"type": "execute", "stmt": {"sql": "SELECT * FROM breeds"}},
                {"type": "close"},
            ]
        },
    )
    response.raise_for_status()
    result = response.json()

    result_set = result["results"][0]["response"]["result"]
    columns = [col["name"] for col in result_set["cols"]]
    rows = result_set["rows"]

    breeds = []
    for row in rows:
        breed = {}
        for col_name, cell in zip(columns, row):
            breed[col_name] = _coerce_turso_value(col_name, cell.get("value"))
        breeds.append(breed)
    return breeds


def get_all_breeds() -> list[dict]:
    """Returns all rows from the breeds table as a list of dicts."""
    db_mode = os.environ.get("DB_MODE", "local")
    if db_mode == "turso":
        return _get_all_breeds_turso()
    return _get_all_breeds_local()


def get_breed_by_name(breed_name: str) -> Optional[dict]:
    """Returns a single breed row as a dict, or None if breed_name is not found."""
    db_mode = os.environ.get("DB_MODE", "local")
    if db_mode == "turso":
        return _get_breed_by_name_turso(breed_name)
    return _get_breed_by_name_local(breed_name)
