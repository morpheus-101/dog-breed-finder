# Skill: API Contract — `/recommend`

Read this file before writing any backend code for the `/recommend` endpoint — request handling, Layer 1 filtering, Layer 2 scoring, or Layer 3 Groq integration. This is the authoritative field-by-field contract. Column names referenced below are defined in `skills/data-ingestion.md`.

---

## 1. Endpoint

`POST /recommend` — the only public endpoint. Stateless, no auth, no user data persisted.

---

## 2. Request Body Schema

```json
{
  "hard_filters": {
    "has_allergies": boolean,
    "property_type": "apartment" | "house",
    "has_yard": boolean,
    "monthly_budget_usd": integer,
    "has_other_dogs": boolean,
    "has_cats": boolean,
    "has_kids": boolean,
    "has_elderly": boolean,
    "owner_experience": "first_time" | "some" | "experienced",
    "noise_tolerance": "low" | "medium" | "high",
    "max_size_category": "small" | "medium" | "large" | "giant" | "no_preference",
    "size_strict": boolean
  },
  "soft_context": {
    "daily_time_available_min": integer,
    "climate": "hot" | "cold" | "temperate" | "varies",
    "outdoor_time_expected": "low" | "medium" | "high",
    "grooming_commitment": "low" | "medium" | "high",
    "prioritize_longevity": boolean,
    "prioritize_low_vet_costs": boolean,
    "primary_purpose": "companionship" | "family_pet" | "guard_protection" | "active_sports_partner" | "emotional_support"
  },
  "trait_priority_ranking": ["...6 unique values from: energy_level, trainability, barking_level, affection_level, protective_instinct, shedding_level"]
}
```

## 3. Response Body Schema

```json
{
  "results": [
    {
      "breed_name": "string",
      "rank": "integer",
      "match_explanation": "string",
      "image_url": "string or null",
      "key_stats": {
        "size_category": "string",
        "energy_level": "integer",
        "monthly_total_cost_usd": "integer"
      }
    }
  ],
  "total_breeds_considered": "integer",
  "breeds_after_hard_filters": "integer"
}
```

Only the final top 10–15 ranked breeds from Layer 3 go into `results` — never the full filtered pool.

`image_url` = DB `image_url_1`, falling back to `image_url_2` if `image_url_1` is null.

---

## 4. Layer 1 — Hard Filter Elimination (exact rules)

| Request field | Condition | Eliminate breed where |
|---|---|---|
| `has_allergies` | `true` | `hypoallergenic != 1` |
| `property_type` | `"apartment"` | `apartment_suitable != 1` |
| `has_yard` | `false` | `needs_yard = 1` |
| `monthly_budget_usd` | always | `monthly_total_cost_usd > monthly_budget_usd` |
| `has_other_dogs` | `true` | `good_with_dogs = 0` |
| `has_cats` | `true` | `good_with_cats = 0` |
| `has_kids` | `true` | `good_with_kids = 0` |
| `has_elderly` | `true` | `good_with_elderly = 0` |
| `owner_experience` | `"first_time"` | `first_time_owner_suitable != 1` |
| `noise_tolerance` | `"low"` | `barking_level > 2` |
| `noise_tolerance` | `"medium"` | `barking_level > 4` |
| `noise_tolerance` | `"high"` | no elimination |

`good_with_dogs`, `good_with_cats`, `good_with_kids`, `good_with_elderly` are boolean `0/1` columns (see correction in `skills/data-ingestion.md` §1) — eliminate on `= 0`, not a numeric threshold.

**Size filter:**
- `max_size_category = "no_preference"` → skip size filtering entirely in Layer 1, regardless of `size_strict`.
- `size_strict = true` and `max_size_category != "no_preference"` → eliminate any breed whose `size_category` is larger than `max_size_category`, using order `small < medium < large < giant`.
- `size_strict = false` → do **not** eliminate on size in Layer 1. Pass `max_size_category` through to Layer 2 as a soft scoring factor (§5).

---

## 5. Layer 2 — Weighted Scoring

1. Convert `trait_priority_ranking` into weights by position:

   | Rank | Weight |
   |---|---|
   | 1st | 1.00 |
   | 2nd | 0.83 |
   | 3rd | 0.67 |
   | 4th | 0.50 |
   | 5th | 0.33 |
   | 6th | 0.17 |

2. For each breed surviving Layer 1: `score = sum(weight[trait] * breed[trait])` across the 6 ranked traits.
3. If `size_strict = false` and `max_size_category != "no_preference"`: add a flat-weight (0.5, not user-ranked) size factor to the score. Exact match to `max_size_category` = full credit; one size step away = half credit; two steps away = no credit (using the `small < medium < large < giant` order).
4. Sort all scored breeds descending. Take the top 10–15 (default cutoff: 12) to pass to Layer 3.
5. **Exception:** if fewer than 10 breeds survive Layer 1, skip the top-N cutoff — pass all surviving breeds directly to Layer 3.

---

## 6. Layer 3 — Groq Context Construction

- Send per breed: `breed_name`, `llm_summary`, and the shortlisted breeds' key numeric stats only — never all 46 columns.
- Always include the full `soft_context` object in the Groq prompt as user context. `primary_purpose`, `climate`, `daily_time_available_min`, `grooming_commitment`, `prioritize_longevity`, `prioritize_low_vet_costs`, and `outdoor_time_expected` are used **only** here — never in Layer 1 or Layer 2.
- Groq's job: re-rank the shortlist if warranted by `soft_context`, and generate a 1–2 sentence `match_explanation` per breed referencing the user's specific situation.
- Groq returns exactly the `results` shape from §3: `breed_name`, `rank`, `match_explanation`. The backend — not Groq — fills in `key_stats` (`size_category`, `energy_level`, `monthly_total_cost_usd`) and `image_url` from the database.

---

## 7. Non-Obvious Rules

- `soft_context` fields must never be used as hard filters or in Layer 2 scoring — they are LLM-context-only by design.
- `trait_priority_ranking` must contain exactly 6 items and be a valid permutation of the 6 allowed trait names. Validate on request; return `422` with a clear message if invalid.
- If fewer than 10 breeds survive Layer 1, skip Layer 2's top-N cutoff and pass all surviving breeds directly to Layer 3.
- If zero breeds survive Layer 1, return `200` with an empty `results` array and a `message` field explaining no breeds matched — not an error.
