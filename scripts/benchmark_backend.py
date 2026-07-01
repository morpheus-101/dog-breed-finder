"""Standalone performance benchmark for backend/. See skills/backend-validation.md.

Run directly:  python scripts/benchmark_backend.py
Run as part of validate_backend.py: imported and called there as an advisory
(non-blocking) final check — the hard pass/fail assertion lives only here.

Fully self-contained, like validate_backend.py: seeds an in-memory SQLite
database and patches backend.db.get_all_breeds to return it, and patches
backend.groq_client._call_groq so no real Groq or Turso calls are ever made.

Measures Layer 1 + Layer 2 latency only, via the X-Pipeline-Ms response
header set in backend/main.py (which explicitly excludes Groq/network time).
"""

import json
import os
import random
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DB_MODE", "local")
# groq_client.py raises RuntimeError at import time if GROQ_API_KEY is unset.
# The real Groq call is patched out below, so this key is never actually used.
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used-real-calls-are-mocked")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend import db as backend_db  # noqa: E402
from backend import groq_client  # noqa: E402
from backend.main import app  # noqa: E402

NUM_REQUESTS = 50
P95_THRESHOLD_MS = 200.0
RNG_SEED = 1337

ALL_TRAITS = [
    "energy_level",
    "trainability",
    "barking_level",
    "affection_level",
    "protective_instinct",
    "shedding_level",
]

# --- Seeded breed data, same shape/rows as scripts/validate_backend.py -----
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
        conn.execute(f"CREATE TABLE breeds ({', '.join(_TEST_BREED_COLUMNS)})")
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
        conn.executemany(f"INSERT INTO breeds VALUES ({placeholders})", rows)
        conn.commit()
        return [dict(row) for row in conn.execute("SELECT * FROM breeds").fetchall()]
    finally:
        conn.close()


def _mock_groq_call(prompt: str) -> str:
    """Same realistic stand-in used by validate_backend.py: extracts the
    breed names groq_client put into the prompt and returns a valid
    re-ranked JSON array, same shape a real Groq response would have."""
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


def _random_request(rng: random.Random) -> dict:
    traits = ALL_TRAITS[:]
    rng.shuffle(traits)
    return {
        "hard_filters": {
            "has_allergies": rng.choice([True, False]),
            "property_type": rng.choice(["apartment", "house"]),
            "has_yard": rng.choice([True, False]),
            "monthly_budget_usd": rng.randint(50, 500),
            "has_other_dogs": rng.choice([True, False]),
            "has_cats": rng.choice([True, False]),
            "has_kids": rng.choice([True, False]),
            "has_elderly": rng.choice([True, False]),
            "owner_experience": rng.choice(["first_time", "some", "experienced"]),
            "noise_tolerance": rng.choice(["low", "medium", "high"]),
            "max_size_category": rng.choice(
                ["small", "medium", "large", "giant", "no_preference"]
            ),
            "size_strict": rng.choice([True, False]),
        },
        "soft_context": {
            "daily_time_available_min": rng.randint(0, 240),
            "climate": rng.choice(["hot", "cold", "temperate", "varies"]),
            "outdoor_time_expected": rng.choice(["low", "medium", "high"]),
            "grooming_commitment": rng.choice(["low", "medium", "high"]),
            "prioritize_longevity": rng.choice([True, False]),
            "prioritize_low_vet_costs": rng.choice([True, False]),
            "primary_purpose": rng.choice(
                [
                    "companionship",
                    "family_pet",
                    "guard_protection",
                    "active_sports_partner",
                    "emotional_support",
                ]
            ),
        },
        "trait_priority_ranking": traits,
    }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100)
    lower = int(k)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (k - lower)


def run_benchmark(num_requests: int = NUM_REQUESTS) -> dict:
    """Runs `num_requests` varied requests against the full pipeline (Groq
    and the DB mocked) and returns latency stats in milliseconds, measuring
    only Layer 1 + Layer 2 time via the X-Pipeline-Ms response header."""
    test_breeds = _build_test_breeds()
    rng = random.Random(RNG_SEED)

    with patch.object(backend_db, "get_all_breeds", return_value=test_breeds), patch.object(
        groq_client, "_call_groq", side_effect=_mock_groq_call
    ):
        client = TestClient(app)
        limiter = app.state.limiter
        latencies_ms = []
        for _ in range(num_requests):
            # /recommend is rate-limited 5/minute per IP; TestClient always
            # presents the same client IP, so reset before every request.
            limiter.reset()
            resp = client.post("/recommend", json=_random_request(rng))
            if resp.status_code != 200:
                raise RuntimeError(
                    f"benchmark request failed: status={resp.status_code} "
                    f"body={resp.text[:300]}"
                )
            pipeline_ms = resp.headers.get("X-Pipeline-Ms")
            if pipeline_ms is None:
                raise RuntimeError(
                    "X-Pipeline-Ms header missing from response — check the "
                    "timing instrumentation in backend/main.py"
                )
            latencies_ms.append(float(pipeline_ms))
        limiter.reset()

    sorted_latencies = sorted(latencies_ms)
    return {
        "count": len(sorted_latencies),
        "min": sorted_latencies[0],
        "p50": _percentile(sorted_latencies, 50),
        "p95": _percentile(sorted_latencies, 95),
        "p99": _percentile(sorted_latencies, 99),
        "max": sorted_latencies[-1],
    }


def print_summary(stats: dict) -> None:
    print()
    print("Backend pipeline latency benchmark (Layer 1 + Layer 2, Groq excluded)")
    print(f"  requests: {stats['count']}")
    print(f"  {'metric':<8}{'latency (ms)':>14}")
    for label in ("min", "p50", "p95", "p99", "max"):
        print(f"  {label:<8}{stats[label]:>14.2f}")
    print()


if __name__ == "__main__":
    benchmark_stats = run_benchmark()
    print_summary(benchmark_stats)
    if benchmark_stats["p95"] >= P95_THRESHOLD_MS:
        print(
            f"FAIL: p95 latency {benchmark_stats['p95']:.2f}ms exceeds "
            f"{P95_THRESHOLD_MS:.0f}ms threshold"
        )
        sys.exit(1)
    print(
        f"PASS: p95 latency {benchmark_stats['p95']:.2f}ms is under "
        f"{P95_THRESHOLD_MS:.0f}ms threshold"
    )
    sys.exit(0)
