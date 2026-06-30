"""Layer 2 — weighted scoring. See skills/api-contract.md section 5."""

RANK_WEIGHTS = [1.00, 0.83, 0.67, 0.50, 0.33, 0.17]
SIZE_ORDER = {"small": 0, "medium": 1, "large": 2, "giant": 3}
SIZE_FACTOR_WEIGHT = 0.5
TOP_N_CUTOFF = 12
MIN_BREEDS_FOR_CUTOFF = 10


def trait_weights_from_ranking(trait_priority_ranking: list[str]) -> dict[str, float]:
    return {
        trait: RANK_WEIGHTS[i] for i, trait in enumerate(trait_priority_ranking)
    }


def size_match_credit(breed_size: str, max_size_category: str) -> float:
    steps_away = abs(SIZE_ORDER[breed_size] - SIZE_ORDER[max_size_category])
    if steps_away == 0:
        return 1.0
    if steps_away == 1:
        return 0.5
    return 0.0


def score_breed(
    breed: dict,
    trait_weights: dict[str, float],
    max_size_category: str,
    size_strict: bool,
) -> float:
    score = sum(
        weight * (breed[trait] or 0) for trait, weight in trait_weights.items()
    )
    if not size_strict and max_size_category != "no_preference":
        score += SIZE_FACTOR_WEIGHT * size_match_credit(
            breed["size_category"], max_size_category
        )
    return score


def score_and_rank_breeds(
    breeds: list[dict],
    trait_priority_ranking: list[str],
    max_size_category: str,
    size_strict: bool,
) -> list[dict]:
    """Returns top breeds (default cutoff 12) sorted descending by score, each with a 'score' key added."""
    trait_weights = trait_weights_from_ranking(trait_priority_ranking)

    scored = []
    for breed in breeds:
        score = score_breed(breed, trait_weights, max_size_category, size_strict)
        scored.append({**breed, "score": score})

    scored.sort(key=lambda b: b["score"], reverse=True)

    if len(breeds) < MIN_BREEDS_FOR_CUTOFF:
        return scored
    return scored[:TOP_N_CUTOFF]
