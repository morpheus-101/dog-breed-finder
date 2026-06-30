# MOCKED — replace real Groq integration in a future session
"""Layer 3 — mocked LLM re-ranking and explanation.

Per skills/api-contract.md section 6, Groq returns only breed_name, rank,
and match_explanation for each shortlisted breed. The backend (main.py)
fills in key_stats and image_url from the database afterward.
"""

PLACEHOLDER_EXPLANATION = "This breed is a strong match based on your lifestyle profile."


def get_llm_rankings(shortlisted_breeds: list[dict], request_body: dict) -> list[dict]:
    """Mock of the Groq re-rank + explain step. Preserves the Layer 2 score order.

    Args:
        shortlisted_breeds: top breeds from scoring.py (already includes 'score').
        request_body: full request body, for soft_context (unused by the mock).

    Returns:
        list of dicts with breed_name, rank, match_explanation.
    """
    results = []
    for i, breed in enumerate(shortlisted_breeds):
        results.append(
            {
                "breed_name": breed["breed_name"],
                "rank": i + 1,
                "match_explanation": PLACEHOLDER_EXPLANATION,
            }
        )
    return results
