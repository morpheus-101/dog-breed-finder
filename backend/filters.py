"""Layer 1 — hard filter elimination. See skills/api-contract.md section 4."""

SIZE_ORDER = {"small": 0, "medium": 1, "large": 2, "giant": 3}


def filter_allergies(breeds: list[dict], has_allergies: bool) -> list[dict]:
    if not has_allergies:
        return breeds
    return [b for b in breeds if b["hypoallergenic"] == 1]


def filter_property_type(breeds: list[dict], property_type: str) -> list[dict]:
    if property_type != "apartment":
        return breeds
    return [b for b in breeds if b["apartment_suitable"] == 1]


def filter_has_yard(breeds: list[dict], has_yard: bool) -> list[dict]:
    if has_yard:
        return breeds
    return [b for b in breeds if b["needs_yard"] != 1]


def filter_budget(breeds: list[dict], monthly_budget_usd: int) -> list[dict]:
    return [b for b in breeds if b["monthly_total_cost_usd"] <= monthly_budget_usd]


def filter_has_other_dogs(breeds: list[dict], has_other_dogs: bool) -> list[dict]:
    if not has_other_dogs:
        return breeds
    return [b for b in breeds if b["good_with_dogs"] != 0]


def filter_has_cats(breeds: list[dict], has_cats: bool) -> list[dict]:
    if not has_cats:
        return breeds
    return [b for b in breeds if b["good_with_cats"] != 0]


def filter_has_kids(breeds: list[dict], has_kids: bool) -> list[dict]:
    if not has_kids:
        return breeds
    return [b for b in breeds if b["good_with_kids"] != 0]


def filter_has_elderly(breeds: list[dict], has_elderly: bool) -> list[dict]:
    if not has_elderly:
        return breeds
    return [b for b in breeds if b["good_with_elderly"] != 0]


def filter_owner_experience(breeds: list[dict], owner_experience: str) -> list[dict]:
    if owner_experience != "first_time":
        return breeds
    return [b for b in breeds if b["first_time_owner_suitable"] == 1]


def filter_noise_tolerance(breeds: list[dict], noise_tolerance: str) -> list[dict]:
    if noise_tolerance == "low":
        return [b for b in breeds if b["barking_level"] <= 2]
    if noise_tolerance == "medium":
        return [b for b in breeds if b["barking_level"] <= 4]
    return breeds


def filter_size_strict(
    breeds: list[dict], max_size_category: str, size_strict: bool
) -> list[dict]:
    if max_size_category == "no_preference" or not size_strict:
        return breeds
    max_rank = SIZE_ORDER[max_size_category]
    return [b for b in breeds if SIZE_ORDER[b["size_category"]] <= max_rank]


def apply_hard_filters(breeds: list[dict], hard_filters: dict) -> tuple[list[dict], int, int]:
    """Returns (filtered_breeds, total_before, total_after)."""
    total_before = len(breeds)

    filtered = breeds
    filtered = filter_allergies(filtered, hard_filters["has_allergies"])
    filtered = filter_property_type(filtered, hard_filters["property_type"])
    filtered = filter_has_yard(filtered, hard_filters["has_yard"])
    filtered = filter_budget(filtered, hard_filters["monthly_budget_usd"])
    filtered = filter_has_other_dogs(filtered, hard_filters["has_other_dogs"])
    filtered = filter_has_cats(filtered, hard_filters["has_cats"])
    filtered = filter_has_kids(filtered, hard_filters["has_kids"])
    filtered = filter_has_elderly(filtered, hard_filters["has_elderly"])
    filtered = filter_owner_experience(filtered, hard_filters["owner_experience"])
    filtered = filter_noise_tolerance(filtered, hard_filters["noise_tolerance"])
    filtered = filter_size_strict(
        filtered, hard_filters["max_size_category"], hard_filters["size_strict"]
    )

    return filtered, total_before, len(filtered)
