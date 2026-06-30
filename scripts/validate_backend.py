"""Living validation script for backend/. See skills/backend-validation.md.

Uses breeds.db (local SQLite) for all tests — never Turso. No real Groq calls
(backend/groq_client.py is mocked). Run after every change to backend/.
"""

import os
import sys
from pathlib import Path

os.environ["DB_MODE"] = "local"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend import db as backend_db  # noqa: E402

client = TestClient(app)

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


print()
print(f"{len(passed)} passed, {len(failed)} failed")

if failed:
    sys.exit(1)

SENTINEL_PATH.parent.mkdir(parents=True, exist_ok=True)
SENTINEL_PATH.write_text("")
sys.exit(0)
