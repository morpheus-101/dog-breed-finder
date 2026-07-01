"""Living validation script for backend/. See skills/backend-validation.md.

Fully self-contained — does not touch breeds.db or Turso. A temporary in-memory
SQLite database is seeded with realistic test breed rows below, and
backend.db.get_all_breeds is patched to return that seeded data for every
request in this script. backend/groq_client.py's real Groq API call
(_call_groq) is likewise patched out for every request, so no real Groq or
Turso calls are ever made during validation. Run after every change to backend/.
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

os.environ["DB_MODE"] = "local"
# groq_client.py raises RuntimeError at import time if GROQ_API_KEY is unset.
# The real Groq call is patched out below, so this key is never actually used.
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used-real-calls-are-mocked")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend import db as backend_db  # noqa: E402

# --- Seed an in-memory SQLite database with realistic test breed data -------
#
# The real breeds.db (277 AKC/Dog-API/Claude-derived breeds) is not committed
# to the repo and doesn't exist in CI, so this script must not depend on it.
# Instead, seed a throwaway :memory: database with a fixed, hand-authored set
# of breeds that exercises every hard filter and both scoring-relevant traits,
# then hand the resulting rows to a mock of backend.db.get_all_breeds so the
# rest of the script — and backend/main.py's request handling — behaves
# exactly as it would against a real database.
_TEST_BREED_COLUMNS = [
    "id",
    "breed_name",
    "size_category",
    "hypoallergenic",
    "apartment_suitable",
    "needs_yard",
    "monthly_total_cost_usd",
    "good_with_dogs",
    "good_with_cats",
    "good_with_kids",
    "good_with_elderly",
    "first_time_owner_suitable",
    "barking_level",
    "energy_level",
    "trainability",
    "shedding_level",
    "affection_level",
    "protective_instinct",
    "llm_summary",
    "image_url_1",
    "image_url_2",
]

# (breed_name, size, hypoallergenic, apartment_ok, needs_yard, cost,
#  good_w_dogs, good_w_cats, good_w_kids, good_w_elderly, first_time_ok,
#  barking, energy, trainability, shedding, affection, protective)
_TEST_BREED_DATA = [
    ("Poodle", "medium", 1, 1, 0, 180, 1, 1, 1, 1, 1, 2, 4, 5, 1, 5, 2),
    ("Bichon Frise", "small", 1, 1, 0, 90, 1, 1, 1, 1, 1, 3, 3, 4, 1, 5, 1),
    ("Portuguese Water Dog", "medium", 1, 0, 1, 210, 1, 0, 1, 0, 0, 3, 5, 5, 1, 4, 3),
    ("Labrador Retriever", "large", 0, 0, 1, 150, 1, 1, 1, 1, 1, 3, 5, 5, 4, 5, 3),
    ("Golden Retriever", "large", 0, 0, 1, 160, 1, 1, 1, 1, 1, 2, 5, 5, 4, 5, 2),
    ("German Shepherd", "large", 0, 0, 1, 190, 0, 0, 1, 0, 0, 4, 5, 5, 4, 4, 5),
    ("Chihuahua", "small", 0, 1, 0, 45, 0, 0, 0, 1, 0, 5, 3, 2, 2, 4, 3),
    ("Yorkshire Terrier", "small", 1, 1, 0, 70, 1, 0, 0, 1, 0, 4, 3, 3, 1, 4, 2),
    ("Great Dane", "giant", 0, 0, 1, 320, 1, 0, 1, 0, 0, 2, 3, 4, 2, 5, 4),
    ("Saint Bernard", "giant", 0, 0, 1, 350, 1, 1, 1, 0, 0, 2, 2, 3, 4, 5, 3),
    ("Beagle", "medium", 0, 1, 0, 110, 1, 0, 1, 1, 1, 5, 4, 3, 3, 4, 2),
    ("Dachshund", "small", 0, 1, 0, 85, 0, 0, 0, 1, 1, 5, 3, 3, 2, 4, 3),
    ("Border Collie", "medium", 0, 0, 1, 140, 1, 0, 1, 0, 0, 4, 5, 5, 3, 4, 3),
    ("Bulldog", "medium", 0, 1, 0, 250, 1, 1, 1, 1, 1, 1, 1, 2, 2, 4, 1),
    ("Shih Tzu", "small", 1, 1, 0, 95, 1, 1, 1, 1, 1, 2, 2, 3, 1, 5, 1),
    ("Doberman Pinscher", "large", 0, 0, 1, 175, 0, 0, 0, 0, 0, 3, 5, 5, 2, 4, 5),
    ("Cavalier King Charles Spaniel", "small", 0, 1, 0, 100, 1, 1, 1, 1, 1, 2, 3, 4, 3, 5, 1),
    ("Siberian Husky", "large", 0, 0, 1, 145, 1, 0, 1, 0, 0, 3, 5, 3, 5, 4, 2),
    ("Maltese", "small", 1, 1, 0, 80, 1, 1, 0, 1, 1, 3, 2, 3, 1, 5, 1),
    ("Rottweiler", "large", 0, 0, 1, 200, 0, 0, 0, 0, 0, 3, 4, 4, 3, 4, 5),
    ("Pomeranian", "small", 0, 1, 0, 65, 1, 1, 0, 1, 1, 5, 3, 3, 3, 4, 2),
    ("Newfoundland", "giant", 0, 0, 1, 400, 1, 1, 1, 0, 0, 1, 2, 4, 4, 5, 3),
]


def _build_test_breeds() -> list[dict]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            f"CREATE TABLE breeds ({', '.join(_TEST_BREED_COLUMNS)})"
        )
        rows = [
            (
                i + 1,
                name,
                size,
                hypoallergenic,
                apartment_ok,
                needs_yard,
                cost,
                good_dogs,
                good_cats,
                good_kids,
                good_elderly,
                first_time_ok,
                barking,
                energy,
                trainability,
                shedding,
                affection,
                protective,
                f"The {name} is a {size}-sized breed known for its "
                f"distinctive temperament, making it a great match for "
                f"the right household.",
                f"https://example.com/images/{name.lower().replace(' ', '-')}-1.jpg",
                None,
            )
            for i, (
                name,
                size,
                hypoallergenic,
                apartment_ok,
                needs_yard,
                cost,
                good_dogs,
                good_cats,
                good_kids,
                good_elderly,
                first_time_ok,
                barking,
                energy,
                trainability,
                shedding,
                affection,
                protective,
            ) in enumerate(_TEST_BREED_DATA)
        ]
        placeholders = ", ".join("?" for _ in _TEST_BREED_COLUMNS)
        conn.executemany(
            f"INSERT INTO breeds VALUES ({placeholders})", rows
        )
        conn.commit()
        return [dict(row) for row in conn.execute("SELECT * FROM breeds").fetchall()]
    finally:
        conn.close()


TEST_BREEDS = _build_test_breeds()
assert len(TEST_BREEDS) >= 20, "need at least 20 seeded test breeds"

db_patch = patch.object(backend_db, "get_all_breeds", return_value=TEST_BREEDS)
db_patch.start()

client = TestClient(app)

# The /recommend endpoint is rate-limited (5/minute per IP, see backend/main.py).
# TestClient always presents the same client IP, so every check below would
# otherwise accumulate against that limit across the whole script. Reset the
# limiter before each check so the rate limit itself is only exercised by the
# dedicated rate-limiting test at the end.
limiter = app.state.limiter


def _mock_groq_call(prompt: str) -> str:
    """Realistic stand-in for groq_client._call_groq: extracts the breed names
    groq_client put into the prompt and returns a valid re-ranked JSON array,
    same shape a real Groq response would have."""
    breeds_section = prompt.split("Candidate breeds")[1].split("Re-rank these breeds")[0]
    breed_names = re.findall(r"^- (.+?): ", breeds_section, re.MULTILINE)
    mock_results = [
        {
            "breed_name": name,
            "rank": i + 1,
            "match_explanation": f"{name} fits well with your lifestyle profile.",
        }
        for i, name in enumerate(breed_names)
    ]
    return json.dumps(mock_results)


groq_patch = patch("backend.groq_client._call_groq", side_effect=_mock_groq_call)
groq_patch.start()

ALL_TRAITS = [
    "energy_level",
    "trainability",
    "barking_level",
    "affection_level",
    "protective_instinct",
    "shedding_level",
]

SENTINEL_PATH = PROJECT_ROOT / ".claude" / ".validate_backend_passed"

passed = []
failed = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        passed.append(name)
        print(f"PASS: {name}")
    else:
        failed.append(name)
        print(f"FAIL: {name} {detail}")


def base_request(**hard_filter_overrides) -> dict:
    hard_filters = {
        "has_allergies": False,
        "property_type": "house",
        "has_yard": True,
        "monthly_budget_usd": 250,
        "has_other_dogs": False,
        "has_cats": False,
        "has_kids": False,
        "has_elderly": False,
        "owner_experience": "experienced",
        "noise_tolerance": "medium",
        "max_size_category": "no_preference",
        "size_strict": False,
    }
    hard_filters.update(hard_filter_overrides)
    return {
        "hard_filters": hard_filters,
        "soft_context": {
            "daily_time_available_min": 60,
            "climate": "temperate",
            "outdoor_time_expected": "medium",
            "grooming_commitment": "medium",
            "prioritize_longevity": False,
            "prioritize_low_vet_costs": False,
            "primary_purpose": "family_pet",
        },
        "trait_priority_ranking": ALL_TRAITS,
    }


def get_breeds_by_name() -> dict:
    return {b["breed_name"]: b for b in backend_db.get_all_breeds()}


breeds_by_name = get_breeds_by_name()


# 1. Happy path
limiter.reset()
resp = client.post("/recommend", json=base_request())
ok = resp.status_code == 200
body = resp.json() if ok else {}
ok = (
    ok
    and "results" in body
    and "total_breeds_considered" in body
    and "breeds_after_hard_filters" in body
    and 1 <= len(body["results"]) <= 15
    and body["breeds_after_hard_filters"] < body["total_breeds_considered"]
)
check(
    "happy path: 200, correct shape, 1-15 results, filtered < total",
    ok,
    detail=f"status={resp.status_code} body={resp.text[:300]}" if not ok else "",
)
check(
    "happy path: message field absent when results non-empty",
    ok and "message" not in body,
    detail=f"body keys={list(body.keys())}",
)

# 2. Allergic user
limiter.reset()
resp = client.post("/recommend", json=base_request(has_allergies=True))
ok = resp.status_code == 200
body = resp.json() if ok else {}
violators = (
    [r["breed_name"] for r in body.get("results", []) if breeds_by_name[r["breed_name"]]["hypoallergenic"] == 0]
    if ok
    else ["<request failed>"]
)
check("allergic user: no non-hypoallergenic breed in results", ok and not violators, detail=str(violators))

# 3. Apartment, no yard
limiter.reset()
resp = client.post(
    "/recommend", json=base_request(property_type="apartment", has_yard=False)
)
ok = resp.status_code == 200
body = resp.json() if ok else {}
violators = (
    [r["breed_name"] for r in body.get("results", []) if breeds_by_name[r["breed_name"]]["needs_yard"] == 1]
    if ok
    else ["<request failed>"]
)
check("apartment/no-yard user: no needs_yard breed in results", ok and not violators, detail=str(violators))

# 4. Budget filter
limiter.reset()
resp = client.post("/recommend", json=base_request(monthly_budget_usd=50))
ok = resp.status_code == 200
body = resp.json() if ok else {}
violators = (
    [r["breed_name"] for r in body.get("results", []) if r["key_stats"]["monthly_total_cost_usd"] > 50]
    if ok
    else ["<request failed>"]
)
check("budget=50: no breed over budget in results", ok and not violators, detail=str(violators))

# 5. First time owner
limiter.reset()
resp = client.post("/recommend", json=base_request(owner_experience="first_time"))
ok = resp.status_code == 200
body = resp.json() if ok else {}
violators = (
    [
        r["breed_name"]
        for r in body.get("results", [])
        if breeds_by_name[r["breed_name"]]["first_time_owner_suitable"] != 1
    ]
    if ok
    else ["<request failed>"]
)
check("first_time owner: no unsuitable breed in results", ok and not violators, detail=str(violators))

# 6. Invalid trait_priority_ranking — wrong number of items
limiter.reset()
req = base_request()
req["trait_priority_ranking"] = ALL_TRAITS[:4]
resp = client.post("/recommend", json=req)
check("invalid ranking (wrong count) -> 422", resp.status_code == 422, detail=f"status={resp.status_code}")

# 7. Invalid trait name in ranking
req = base_request()
req["trait_priority_ranking"] = ALL_TRAITS[:5] + ["not_a_real_trait"]
resp = client.post("/recommend", json=req)
check("invalid ranking (bad trait name) -> 422", resp.status_code == 422, detail=f"status={resp.status_code}")

# 8. Zero-results case
limiter.reset()
resp = client.post(
    "/recommend", json=base_request(has_allergies=True, monthly_budget_usd=1)
)
ok = resp.status_code == 200
body = resp.json() if ok else {}
check(
    "zero-survivor request -> 200 with empty results",
    ok and body.get("results") == [] and "message" in body,
    detail=f"status={resp.status_code} body={resp.text[:300]}" if not (ok and body.get("results") == []) else "",
)
check(
    "zero-survivor request: message present with non-empty string value",
    ok and isinstance(body.get("message"), str) and len(body.get("message", "")) > 0,
    detail=f"message={body.get('message')!r}",
)

# 9. size_strict=true, max_size_category=small
limiter.reset()
resp = client.post(
    "/recommend",
    json=base_request(size_strict=True, max_size_category="small"),
)
ok = resp.status_code == 200
body = resp.json() if ok else {}
violators = (
    [r["breed_name"] for r in body.get("results", []) if r["key_stats"]["size_category"] != "small"]
    if ok
    else ["<request failed>"]
)
check("size_strict=true/small: no non-small breed in results", ok and not violators, detail=str(violators))

# 10. Response shape — every field present with correct type
limiter.reset()
resp = client.post("/recommend", json=base_request())
ok = resp.status_code == 200
body = resp.json() if ok else {}
shape_ok = ok
if ok:
    for r in body["results"]:
        shape_ok = (
            shape_ok
            and isinstance(r["breed_name"], str)
            and isinstance(r["rank"], int)
            and isinstance(r["match_explanation"], str)
            and (r["image_url"] is None or isinstance(r["image_url"], str))
            and isinstance(r["key_stats"]["size_category"], str)
            and isinstance(r["key_stats"]["energy_level"], int)
            and isinstance(r["key_stats"]["monthly_total_cost_usd"], int)
        )
check("response shape: all fields present with correct types", shape_ok)

# 11. Groq returns malformed JSON -> fallback to Layer 2 order, still 200
limiter.reset()
with patch("backend.groq_client._call_groq", return_value="not valid json {{{"):
    resp = client.post("/recommend", json=base_request())
ok = resp.status_code == 200
body = resp.json() if ok else {}
fallback_ok = (
    ok
    and len(body.get("results", [])) > 0
    and all(
        r["match_explanation"] == "Match determined by lifestyle scoring."
        for r in body.get("results", [])
    )
    and [r["rank"] for r in body["results"]] == list(range(1, len(body["results"]) + 1))
)
check(
    "Groq malformed JSON -> 200 with Layer 2 order fallback",
    fallback_ok,
    detail=f"status={resp.status_code} body={resp.text[:300]}" if not fallback_ok else "",
)

# 12. Rate limiting — 6th request within a minute from the same IP returns 429
limiter.reset()
rate_limit_statuses = []
for _ in range(6):
    rate_limit_statuses.append(client.post("/recommend", json=base_request()).status_code)
check(
    "rate limiting: first 5 requests/min succeed, 6th returns 429",
    rate_limit_statuses[:5] == [200] * 5 and rate_limit_statuses[5] == 429,
    detail=f"statuses={rate_limit_statuses}",
)
limiter.reset()

groq_patch.stop()
db_patch.stop()

print()
print(f"{len(passed)} passed, {len(failed)} failed")

if failed:
    sys.exit(1)

SENTINEL_PATH.parent.mkdir(parents=True, exist_ok=True)
SENTINEL_PATH.write_text("")
sys.exit(0)
