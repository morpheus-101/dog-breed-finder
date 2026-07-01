"""Layer 3 — Groq API re-ranking and explanation generation.

Per skills/api-contract.md section 6, Groq returns only breed_name, rank,
and match_explanation for each shortlisted breed. The backend (main.py)
fills in key_stats and image_url from the database afterward.
"""

import json
import logging
import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"

_groq_api_key = os.environ.get("GROQ_API_KEY")
if not _groq_api_key:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Add it to .env before starting the backend."
    )

_client = Groq(api_key=_groq_api_key)

FALLBACK_EXPLANATION = "Match determined by lifestyle scoring."


def _format_soft_context(soft_context: dict) -> str:
    return (
        f"- Primary purpose for getting a dog: {soft_context['primary_purpose']}\n"
        f"- Climate where they live: {soft_context['climate']}\n"
        f"- Daily time available for the dog: {soft_context['daily_time_available_min']} minutes\n"
        f"- Grooming commitment they're willing to make: {soft_context['grooming_commitment']}\n"
        f"- Expected outdoor time with the dog: {soft_context['outdoor_time_expected']}\n"
        f"- Prioritizes long-lived breeds: {soft_context['prioritize_longevity']}\n"
        f"- Prioritizes low vet costs: {soft_context['prioritize_low_vet_costs']}"
    )


def _build_prompt(
    top_breeds: list[dict], soft_context: dict, trait_priority_ranking: list[str]
) -> str:
    ranking_text = ", ".join(
        f"{i + 1}. {trait}" for i, trait in enumerate(trait_priority_ranking)
    )
    breeds_text = "\n".join(
        f"- {b['breed_name']}: {b['llm_summary']}" for b in top_breeds
    )
    return (
        "You are helping match dog breeds to a prospective owner's lifestyle.\n\n"
        "User context:\n"
        f"{_format_soft_context(soft_context)}\n\n"
        f"User's trait priorities, most to least important: {ranking_text}\n\n"
        "Candidate breeds (already pre-filtered and scored against the user's hard "
        "requirements and trait priorities):\n"
        f"{breeds_text}\n\n"
        "Re-rank these breeds from best to worst fit for this specific user, taking the "
        "context above into account. Write a 1-2 sentence match_explanation per breed "
        "that references the user's specific situation.\n\n"
        "Return only a valid JSON array, no preamble, no markdown, one object per breed "
        'with keys: "breed_name", "rank", "match_explanation". Return breeds in ranked '
        "order."
    )


def _call_groq(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_response(raw_response: str) -> list[dict]:
    cleaned = _strip_markdown_fences(raw_response)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("Groq response is not a JSON array")
    return parsed


def _merge_with_input(groq_results: list[dict], top_breeds: list[dict]) -> list[dict]:
    """Trusts only breed_name and match_explanation from Groq. key_stats and image_url
    are filled in by main.py from the database, never from Groq."""
    breeds_by_lower_name = {b["breed_name"].lower(): b for b in top_breeds}

    merged = []
    for item in groq_results:
        groq_name = item.get("breed_name", "")
        matched_breed = breeds_by_lower_name.get(groq_name.lower())
        if matched_breed is None:
            logger.warning("Groq returned unknown breed_name %r; skipping", groq_name)
            continue
        merged.append(
            {
                "breed_name": matched_breed["breed_name"],
                "rank": item["rank"],
                "match_explanation": item["match_explanation"],
            }
        )
    return merged


def _fallback_results(top_breeds: list[dict]) -> list[dict]:
    return [
        {
            "breed_name": b["breed_name"],
            "rank": i + 1,
            "match_explanation": FALLBACK_EXPLANATION,
        }
        for i, b in enumerate(top_breeds)
    ]


def get_llm_rankings(
    shortlisted_breeds: list[dict], request_body: dict
) -> tuple[list[dict], bool]:
    """Re-ranks the Layer 2 shortlist via Groq and generates per-breed explanations.

    Args:
        shortlisted_breeds: top breeds from scoring.py (full breed dicts, includes
            'score', 'llm_summary', and all DB columns).
        request_body: full request body — soft_context and trait_priority_ranking
            are used to build the Groq prompt.

    Returns:
        (results, groq_succeeded) — results is a list of dicts with breed_name,
        rank, match_explanation, in ranked order. Falls back to Layer 2 order
        with a generic explanation if Groq fails or returns malformed output —
        never raises.
    """
    if not shortlisted_breeds:
        return [], True

    soft_context = request_body["soft_context"]
    trait_priority_ranking = request_body["trait_priority_ranking"]
    prompt = _build_prompt(shortlisted_breeds, soft_context, trait_priority_ranking)

    try:
        raw_response = _call_groq(prompt)
        parsed = _parse_response(raw_response)
        merged = _merge_with_input(parsed, shortlisted_breeds)
        if not merged:
            raise ValueError("No Groq breed names matched the input shortlist")
        logger.info("groq_success", extra={"breeds_ranked": len(merged)})
        return merged, True
    except Exception as exc:
        logger.warning(
            "groq_fallback",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        return _fallback_results(shortlisted_breeds), False
