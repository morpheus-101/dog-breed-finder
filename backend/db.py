"""Database access layer. DB_MODE=local uses breeds.db (sqlite3); DB_MODE=turso uses Turso HTTP API (httpx)."""

import os
import sqlite3
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_PATH = PROJECT_ROOT / "breeds.db"


def _get_all_breeds_local() -> list[dict]:
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM breeds").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


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
            breed[col_name] = cell.get("value")
        breeds.append(breed)
    return breeds


def get_all_breeds() -> list[dict]:
    """Returns all rows from the breeds table as a list of dicts."""
    db_mode = os.environ.get("DB_MODE", "local")
    if db_mode == "turso":
        return _get_all_breeds_turso()
    return _get_all_breeds_local()
