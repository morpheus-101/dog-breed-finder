"""FastAPI entrypoint. Orchestrates filters.py -> scoring.py -> groq_client.py.

See skills/api-contract.md for the authoritative /recommend contract.
"""

import json
import logging
import os
import sys
import time
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

# Attribute names present on every stdlib LogRecord — anything else on a
# record came from `extra={...}` and should be surfaced in the JSON output.
_STANDARD_LOG_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _configure_logging() -> None:
    debug = os.environ.get("DEBUG", "").lower() == "true"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(stdout_handler)

    axiom_token = os.environ.get("AXIOM_TOKEN")
    axiom_dataset = os.environ.get("AXIOM_DATASET")
    if axiom_token and axiom_dataset:
        from axiom_py import Client as AxiomClient
        from axiom_py.logging import AxiomHandler

        # AxiomHandler.emit() flushes synchronously and does not catch
        # shipping errors itself, so a bad dataset name or an unreachable
        # Axiom API would otherwise raise out of every logger.info/warning
        # call — including calls made deep inside request handling (e.g.
        # httpx's own internal request logging) — and crash the request
        # with an unrelated 500. Catch here so log shipping can never take
        # down the app.
        class _SafeAxiomHandler(AxiomHandler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    super().emit(record)
                except Exception:
                    self.handleError(record)

        axiom_client = AxiomClient(token=axiom_token)
        axiom_handler = _SafeAxiomHandler(axiom_client, axiom_dataset)
        axiom_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(axiom_handler)


_configure_logging()

logger = logging.getLogger(__name__)

from backend import db, filters, groq_client, scoring  # noqa: E402

VALID_TRAITS = {
    "energy_level",
    "trainability",
    "barking_level",
    "affection_level",
    "protective_instinct",
    "shedding_level",
}

app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
_allow_origins = (
    [origin.strip() for origin in _allowed_origins_env.split(",")]
    if _allowed_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HardFilters(BaseModel):
    has_allergies: bool
    property_type: Literal["apartment", "house"]
    has_yard: bool
    monthly_budget_usd: int
    has_other_dogs: bool
    has_cats: bool
    has_kids: bool
    has_elderly: bool
    owner_experience: Literal["first_time", "some", "experienced"]
    noise_tolerance: Literal["low", "medium", "high"]
    max_size_category: Literal["small", "medium", "large", "giant", "no_preference"]
    size_strict: bool


class SoftContext(BaseModel):
    daily_time_available_min: int
    climate: Literal["hot", "cold", "temperate", "varies"]
    outdoor_time_expected: Literal["low", "medium", "high"]
    grooming_commitment: Literal["low", "medium", "high"]
    prioritize_longevity: bool
    prioritize_low_vet_costs: bool
    primary_purpose: Literal[
        "companionship",
        "family_pet",
        "guard_protection",
        "active_sports_partner",
        "emotional_support",
    ]


class RecommendRequest(BaseModel):
    hard_filters: HardFilters
    soft_context: SoftContext
    trait_priority_ranking: list[str]

    @field_validator("trait_priority_ranking")
    @classmethod
    def validate_trait_priority_ranking(cls, value: list[str]) -> list[str]:
        if len(value) != 6:
            raise ValueError(
                f"trait_priority_ranking must contain exactly 6 items, got {len(value)}"
            )
        invalid = [t for t in value if t not in VALID_TRAITS]
        if invalid:
            raise ValueError(
                f"trait_priority_ranking contains invalid trait name(s): {invalid}. "
                f"Valid traits are: {sorted(VALID_TRAITS)}"
            )
        if len(set(value)) != 6:
            raise ValueError(
                "trait_priority_ranking must contain 6 unique trait names, found duplicates"
            )
        return value


class KeyStats(BaseModel):
    size_category: str
    energy_level: int
    monthly_total_cost_usd: int


class ResultItem(BaseModel):
    breed_name: str
    rank: int
    match_explanation: str
    image_url: Optional[str]
    key_stats: KeyStats


class RecommendResponse(BaseModel):
    results: list[ResultItem]
    total_breeds_considered: int
    breeds_after_hard_filters: int
    message: Optional[str] = None


def _resolve_image_url(breed: dict) -> Optional[str]:
    return breed.get("image_url_1") or breed.get("image_url_2")


@app.post("/recommend", response_model=None)
@limiter.limit("5/minute")
def recommend(request: Request, body: RecommendRequest) -> dict:
    start_time = time.perf_counter()
    os.environ.setdefault("DB_MODE", "local")

    all_breeds = db.get_all_breeds()
    breeds_by_name = {b["breed_name"]: b for b in all_breeds}

    filtered_breeds, total_before, total_after = filters.apply_hard_filters(
        all_breeds, body.hard_filters.model_dump()
    )

    if total_after == 0:
        logger.info(
            "request_complete",
            extra={
                "breeds_before_filters": total_before,
                "breeds_after_filters": 0,
                "breeds_sent_to_groq": 0,
                "groq_succeeded": None,
                "response_time_ms": round((time.perf_counter() - start_time) * 1000),
            },
        )
        return RecommendResponse(
            results=[],
            total_breeds_considered=total_before,
            breeds_after_hard_filters=0,
            message="No breeds matched your criteria. Try relaxing some filters.",
        ).model_dump()

    shortlisted = scoring.score_and_rank_breeds(
        filtered_breeds,
        body.trait_priority_ranking,
        body.hard_filters.max_size_category,
        body.hard_filters.size_strict,
    )

    llm_rankings, groq_succeeded = groq_client.get_llm_rankings(
        shortlisted, body.model_dump()
    )

    results = []
    for ranked in llm_rankings:
        breed = breeds_by_name[ranked["breed_name"]]
        results.append(
            ResultItem(
                breed_name=breed["breed_name"],
                rank=ranked["rank"],
                match_explanation=ranked["match_explanation"],
                image_url=_resolve_image_url(breed),
                key_stats=KeyStats(
                    size_category=breed["size_category"],
                    energy_level=breed["energy_level"] or 0,
                    monthly_total_cost_usd=breed["monthly_total_cost_usd"] or 0,
                ),
            )
        )

    logger.info(
        "request_complete",
        extra={
            "breeds_before_filters": total_before,
            "breeds_after_filters": total_after,
            "breeds_sent_to_groq": len(shortlisted),
            "groq_succeeded": groq_succeeded,
            "response_time_ms": round((time.perf_counter() - start_time) * 1000),
        },
    )

    return RecommendResponse(
        results=results,
        total_breeds_considered=total_before,
        breeds_after_hard_filters=total_after,
    ).model_dump(exclude={"message"})
