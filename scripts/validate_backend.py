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

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

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

# 13. /filter-count — Layer 1 only, returns a valid breed count
limiter.reset()
resp = client.post("/filter-count", json={"hard_filters": base_request()["hard_filters"]})
ok = resp.status_code == 200
body = resp.json() if ok else {}
check(
    "filter-count: 200 with breed_count between 0 and total seeded breeds",
    ok
    and isinstance(body.get("breed_count"), int)
    and 0 <= body["breed_count"] <= len(TEST_BREEDS)
    and body.get("total_breeds_considered") == len(TEST_BREEDS),
    detail=f"status={resp.status_code} body={resp.text[:300]}" if not ok else f"body={body}",
)

# 14. /filter-count agrees with /recommend's breeds_after_hard_filters for
# the same hard_filters, and a stricter filter set never yields a higher count.
limiter.reset()
recommend_resp = client.post("/recommend", json=base_request())
limiter.reset()
count_resp = client.post("/filter-count", json={"hard_filters": base_request()["hard_filters"]})
ok = recommend_resp.status_code == 200 and count_resp.status_code == 200
check(
    "filter-count: agrees with /recommend's breeds_after_hard_filters",
    ok and count_resp.json()["breed_count"] == recommend_resp.json()["breeds_after_hard_filters"],
    detail=f"count={count_resp.text[:200]} recommend={recommend_resp.text[:200]}",
)

limiter.reset()
loose_resp = client.post("/filter-count", json={"hard_filters": base_request()["hard_filters"]})
limiter.reset()
strict_resp = client.post(
    "/filter-count", json={"hard_filters": base_request(has_allergies=True)["hard_filters"]}
)
ok = loose_resp.status_code == 200 and strict_resp.status_code == 200
check(
    "filter-count: stricter hard_filters never increase the count",
    ok and strict_resp.json()["breed_count"] <= loose_resp.json()["breed_count"],
    detail=f"loose={loose_resp.text[:200]} strict={strict_resp.text[:200]}",
)

# --- Property-based tests (hypothesis) ---------------------------------
#
# These generate many random inputs per test rather than a single fixed
# case. Groq and the rate limiter are still mocked/reset the same way as
# the fixed tests above, so no real external calls happen here either.

HYPOTHESIS_SETTINGS = settings(
    max_examples=50,
    deadline=5000,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.filter_too_much,
    ],
)

_soft_context_strategy = st.fixed_dictionaries(
    {
        "daily_time_available_min": st.integers(min_value=0, max_value=240),
        "climate": st.sampled_from(["hot", "cold", "temperate", "varies"]),
        "outdoor_time_expected": st.sampled_from(["low", "medium", "high"]),
        "grooming_commitment": st.sampled_from(["low", "medium", "high"]),
        "prioritize_longevity": st.booleans(),
        "prioritize_low_vet_costs": st.booleans(),
        "primary_purpose": st.sampled_from(
            [
                "companionship",
                "family_pet",
                "guard_protection",
                "active_sports_partner",
                "emotional_support",
            ]
        ),
    }
)

_trait_ranking_strategy = st.permutations(ALL_TRAITS).map(list)

_valid_hard_filters_strategy = st.fixed_dictionaries(
    {
        "has_allergies": st.booleans(),
        "property_type": st.sampled_from(["apartment", "house"]),
        "has_yard": st.booleans(),
        "monthly_budget_usd": st.integers(min_value=50, max_value=500),
        "has_other_dogs": st.booleans(),
        "has_cats": st.booleans(),
        "has_kids": st.booleans(),
        "has_elderly": st.booleans(),
        "owner_experience": st.sampled_from(["first_time", "some", "experienced"]),
        "noise_tolerance": st.sampled_from(["low", "medium", "high"]),
        "max_size_category": st.sampled_from(
            ["small", "medium", "large", "giant", "no_preference"]
        ),
        "size_strict": st.booleans(),
    }
)

valid_request_strategy = st.fixed_dictionaries(
    {
        "hard_filters": _valid_hard_filters_strategy,
        "soft_context": _soft_context_strategy,
        "trait_priority_ranking": _trait_ranking_strategy,
    }
)

_REQUIRED_RESULT_KEYS = {"breed_name", "rank", "match_explanation", "image_url", "key_stats"}
_REQUIRED_KEY_STATS_KEYS = {"size_category", "energy_level", "monthly_total_cost_usd"}


# 15. Random valid requests always return correct response shape
@HYPOTHESIS_SETTINGS
@given(req=valid_request_strategy)
def _test_random_valid_requests_shape(req):
    limiter.reset()
    resp = client.post("/recommend", json=req)
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:300]}"
    body = resp.json()
    assert {"results", "total_breeds_considered", "breeds_after_hard_filters"} <= set(body.keys())
    assert body["total_breeds_considered"] == len(TEST_BREEDS)
    assert body["breeds_after_hard_filters"] <= body["total_breeds_considered"]
    results = body["results"]
    assert isinstance(results, list)
    assert 0 <= len(results) <= 15
    for i, r in enumerate(results, start=1):
        assert _REQUIRED_RESULT_KEYS <= set(r.keys())
        assert r["rank"] == i
        assert _REQUIRED_KEY_STATS_KEYS <= set(r["key_stats"].keys())


try:
    _test_random_valid_requests_shape()
    check("property: random valid requests always return correct response shape", True)
except Exception as exc:  # noqa: BLE001 - hypothesis raises assertion/shrunk failures here
    check("property: random valid requests always return correct response shape", False, detail=str(exc))

# 16. Hard filters never increase breed count
@HYPOTHESIS_SETTINGS
@given(req=valid_request_strategy)
def _test_hard_filters_never_increase_count(req):
    limiter.reset()
    resp = client.post("/recommend", json=req)
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:300]}"
    body = resp.json()
    assert body["breeds_after_hard_filters"] <= body["total_breeds_considered"]


try:
    _test_hard_filters_never_increase_count()
    check("property: hard filters never increase breed count", True)
except Exception as exc:  # noqa: BLE001
    check("property: hard filters never increase breed count", False, detail=str(exc))

# 17. Invalid trait_priority_ranking always returns 422
_invalid_ranking_strategy = st.one_of(
    # Right count, but not a valid permutation (duplicate trait names).
    st.lists(st.sampled_from(ALL_TRAITS), min_size=6, max_size=6).filter(
        lambda l: len(set(l)) != 6
    ),
    # Right count, but contains names outside the allowed trait set.
    st.lists(
        st.text(min_size=1, max_size=20).filter(lambda s: s not in ALL_TRAITS),
        min_size=6,
        max_size=6,
    ),
    # Wrong number of items entirely.
    st.lists(st.sampled_from(ALL_TRAITS), min_size=0, max_size=10).filter(
        lambda l: len(l) != 6
    ),
)


@HYPOTHESIS_SETTINGS
@given(ranking=_invalid_ranking_strategy)
def _test_invalid_ranking_always_422(ranking):
    limiter.reset()
    req = base_request()
    req["trait_priority_ranking"] = ranking
    resp = client.post("/recommend", json=req)
    assert resp.status_code == 422, f"ranking={ranking} status={resp.status_code} body={resp.text[:300]}"


try:
    _test_invalid_ranking_always_422()
    check("property: invalid trait_priority_ranking always returns 422", True)
except Exception as exc:  # noqa: BLE001
    check("property: invalid trait_priority_ranking always returns 422", False, detail=str(exc))

# 18. Zero-result guaranteed inputs return 200, never 500
_zero_result_hard_filters_strategy = st.fixed_dictionaries(
    {
        "has_allergies": st.just(True),
        "property_type": st.sampled_from(["apartment", "house"]),
        "has_yard": st.booleans(),
        "monthly_budget_usd": st.just(1),
        "has_other_dogs": st.booleans(),
        "has_cats": st.booleans(),
        "has_kids": st.booleans(),
        "has_elderly": st.booleans(),
        "owner_experience": st.sampled_from(["first_time", "some", "experienced"]),
        "noise_tolerance": st.sampled_from(["low", "medium", "high"]),
        "max_size_category": st.sampled_from(
            ["small", "medium", "large", "giant", "no_preference"]
        ),
        "size_strict": st.booleans(),
    }
)

_zero_result_request_strategy = st.fixed_dictionaries(
    {
        "hard_filters": _zero_result_hard_filters_strategy,
        "soft_context": _soft_context_strategy,
        "trait_priority_ranking": _trait_ranking_strategy,
    }
)


@HYPOTHESIS_SETTINGS
@given(req=_zero_result_request_strategy)
def _test_zero_results_returns_200(req):
    limiter.reset()
    resp = client.post("/recommend", json=req)
    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text[:300]}"
    body = resp.json()
    assert body["results"] == [], f"expected empty results, got {body['results']}"


try:
    _test_zero_results_returns_200()
    check("property: guaranteed zero-survivor inputs always return 200 with empty results", True)
except Exception as exc:  # noqa: BLE001
    check(
        "property: guaranteed zero-survivor inputs always return 200 with empty results",
        False,
        detail=str(exc),
    )

groq_patch.stop()
db_patch.stop()

print()
print(f"{len(passed)} passed, {len(failed)} failed")

if failed:
    sys.exit(1)

# --- Advisory performance benchmark (non-blocking) --------------------
#
# scripts/benchmark_backend.py owns the hard p95 < 200ms assertion (it exits
# 1 and fails CI on its own, as a separate step). Here it's just a heads-up:
# a slow p95 is printed as a warning but never fails validate_backend.py.
try:
    from scripts.benchmark_backend import P95_THRESHOLD_MS, print_summary, run_benchmark

    benchmark_stats = run_benchmark()
    print_summary(benchmark_stats)
    if benchmark_stats["p95"] >= P95_THRESHOLD_MS:
        print(
            f"WARNING: benchmark p95 latency {benchmark_stats['p95']:.2f}ms exceeds "
            f"{P95_THRESHOLD_MS:.0f}ms threshold. This is advisory only here — run "
            f"scripts/benchmark_backend.py directly for the hard-failing check."
        )
    else:
        print(
            f"Benchmark OK: p95 latency {benchmark_stats['p95']:.2f}ms is under "
            f"{P95_THRESHOLD_MS:.0f}ms"
        )
except Exception as exc:  # noqa: BLE001 - benchmark failures here are advisory only
    print(f"WARNING: benchmark could not be run: {exc}")

SENTINEL_PATH.parent.mkdir(parents=True, exist_ok=True)
SENTINEL_PATH.write_text("")
sys.exit(0)
