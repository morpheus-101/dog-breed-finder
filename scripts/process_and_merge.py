import json
import re
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv
from rapidfuzz import process as fuzz_process

load_dotenv()

ROOT = Path(__file__).parent.parent
AKC_CSV = ROOT / "datasets" / "akc-data-latest.csv"
DOG_API_BREEDS = ROOT / "data" / "raw" / "dog_api_breeds.json"
DOG_API_IMAGES = ROOT / "data" / "raw" / "dog_api_images.json"
PROCESSED_DIR = ROOT / "data" / "processed"
FINAL_DIR = ROOT / "data" / "final"
CHECKPOINT = PROCESSED_DIR / "breeds_with_claude.csv"
UNMATCHED_LOG = PROCESSED_DIR / "unmatched_breeds.txt"
ERROR_LOG = PROCESSED_DIR / "claude_batch_errors.txt"
FINAL_CSV = FINAL_DIR / "breeds.csv"

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 10
CHECKPOINT_EVERY = 5

SCHEMA_COLUMNS = [
    "breed_name", "akc_group", "popularity_rank",
    "height_min_cm", "height_max_cm",
    "weight_min_kg", "weight_max_kg",
    "life_expectancy_min", "life_expectancy_max",
    "size_category",
    "energy_level", "trainability", "shedding_level",
    "grooming_frequency", "good_with_strangers",
    "hypoallergenic", "coat_type",
    "image_url_1", "image_url_2",
    "origin_country", "grooming_cost_tier",
    "exercise_min_per_day", "monthly_food_cost_usd",
    "vet_cost_tier", "monthly_total_cost_usd",
    "playfulness", "affection_level", "intelligence",
    "independence", "barking_level", "protective_instinct",
    "separation_anxiety",
    "good_with_kids", "good_with_dogs", "good_with_cats",
    "good_with_elderly", "apartment_suitable", "needs_yard",
    "heat_tolerance", "cold_tolerance", "urban_suitable",
    "first_time_owner_suitable", "experience_required",
    "guard_dog", "working_dog",
    "llm_summary",
]

CLAUDE_COLUMNS = [
    "hypoallergenic", "coat_type", "grooming_cost_tier",
    "exercise_min_per_day", "monthly_food_cost_usd",
    "vet_cost_tier", "monthly_total_cost_usd",
    "playfulness", "affection_level", "intelligence",
    "independence", "barking_level", "protective_instinct",
    "separation_anxiety",
    "good_with_kids", "good_with_dogs", "good_with_cats",
    "good_with_elderly", "apartment_suitable", "needs_yard",
    "heat_tolerance", "cold_tolerance", "urban_suitable",
    "first_time_owner_suitable", "experience_required",
    "guard_dog", "llm_summary",
]

BOOLEAN_COLUMNS = [
    "good_with_kids", "good_with_dogs", "good_with_cats",
    "good_with_elderly", "apartment_suitable", "needs_yard",
    "urban_suitable", "first_time_owner_suitable",
    "guard_dog", "working_dog", "hypoallergenic",
]

SCORING_CONVERSIONS = {
    "energy_level_value": "energy_level",
    "trainability_value": "trainability",
    "shedding_value": "shedding_level",
    "grooming_frequency_value": "grooming_frequency",
    "demeanor_value": "good_with_strangers",
}


# ---------------------------------------------------------------------------
# Step 1 — Load inputs
# ---------------------------------------------------------------------------

def load_inputs():
    print("Loading AKC CSV ...")
    akc = pd.read_csv(AKC_CSV)
    print(f"  -> {len(akc)} breeds")

    print("Loading Dog API breeds JSON ...")
    dog_breeds = json.loads(DOG_API_BREEDS.read_text())
    print(f"  -> {len(dog_breeds)} breeds")

    print("Loading Dog API images JSON ...")
    dog_images = json.loads(DOG_API_IMAGES.read_text())
    print(f"  -> {len(dog_images)} breed image entries")

    return akc, dog_breeds, dog_images


# ---------------------------------------------------------------------------
# Step 2 — Merge AKC + Dog API
# ---------------------------------------------------------------------------

def flatten_dog_api(dog_breeds: list[dict]) -> pd.DataFrame:
    rows = []
    for b in dog_breeds:
        rows.append({
            "dog_api_id": b.get("id"),
            "dog_api_name": b.get("name", ""),
            "coat_type": None,
            "origin_country": b.get("origin", None),
        })
    return pd.DataFrame(rows)


def strip_size_qualifier(name: str) -> str:
    """Remove parenthetical suffixes before fuzzy matching.

    'Poodle (Standard)' -> 'Poodle', so it matches the Dog API's 'Poodle'
    rather than scoring poorly against 'Poodle (Miniature)' or 'Poodle (Toy)'.
    """
    return re.sub(r"\s*\(.*?\)\s*$", "", name).strip()


def fuzzy_merge(akc: pd.DataFrame, dog_df: pd.DataFrame) -> pd.DataFrame:
    dog_names = dog_df["dog_api_name"].tolist()
    dog_names_stripped = [strip_size_qualifier(n) for n in dog_names]
    matched_rows = []
    unmatched = []

    for _, akc_row in akc.iterrows():
        breed_name = akc_row["breed_name"]
        breed_name_stripped = strip_size_qualifier(breed_name)
        result = fuzz_process.extractOne(
            breed_name_stripped, dog_names_stripped, score_cutoff=85
        )
        if result:
            matched_name, _score, idx = result
            dog_row = dog_df.iloc[idx]
            matched_rows.append({
                "breed_name": breed_name,
                "dog_api_id": dog_row["dog_api_id"],
                "coat_type": dog_row["coat_type"],
                "origin_country": dog_row["origin_country"],
            })
        else:
            matched_rows.append({
                "breed_name": breed_name,
                "dog_api_id": None,
                "coat_type": None,
                "origin_country": None,
            })
            unmatched.append(breed_name)

    matched_in_akc = {r["breed_name"] for r in matched_rows
                      if r["dog_api_id"] is not None}
    dog_unmatched = [
        n for n in dog_names if n not in matched_in_akc
    ]
    if dog_unmatched:
        UNMATCHED_LOG.write_text("\n".join(dog_unmatched))
        print(f"  -> {len(dog_unmatched)} Dog API breeds unmatched "
              f"(logged to {UNMATCHED_LOG})")

    return pd.DataFrame(matched_rows)


def apply_scale_conversion(akc: pd.DataFrame) -> pd.DataFrame:
    for src_col, dst_col in SCORING_CONVERSIONS.items():
        if src_col in akc.columns:
            akc[dst_col] = akc[src_col].apply(
                lambda v: round(1 + v * 4) if pd.notna(v) else None
            )
    return akc


def derive_size_category(weight_max_kg, height_max_cm=None):
    if not pd.isna(weight_max_kg):
        if weight_max_kg <= 9:
            return "small"
        if weight_max_kg <= 25:
            return "medium"
        if weight_max_kg <= 45:
            return "large"
        return "giant"
    if not pd.isna(height_max_cm):
        if height_max_cm > 60:
            return "large"
        if height_max_cm >= 40:
            return "medium"
        return "small"
    return None


def add_image_urls(
    df: pd.DataFrame, dog_images: dict[str, list]
) -> pd.DataFrame:
    url1, url2 = [], []
    for _, row in df.iterrows():
        breed_id = row.get("dog_api_id")
        images = dog_images.get(str(int(breed_id))
                                if pd.notna(breed_id) else "", [])
        url1.append(images[0]["url"] if len(images) > 0 else None)
        url2.append(images[1]["url"] if len(images) > 1 else None)
    df["image_url_1"] = url1
    df["image_url_2"] = url2
    return df


def merge_step(
    akc: pd.DataFrame,
    dog_breeds: list[dict],
    dog_images: dict,
) -> pd.DataFrame:
    print("\nStep 2: Merging AKC CSV with Dog API ...")

    dog_df = flatten_dog_api(dog_breeds)
    match_df = fuzzy_merge(akc, dog_df)

    df = akc.copy()
    df = df.merge(match_df, on="breed_name", how="left")

    df = apply_scale_conversion(df)

    df.rename(columns={
        "popularity": "popularity_rank",
        "group": "akc_group",
        "min_height": "height_min_cm",
        "max_height": "height_max_cm",
        "min_weight": "weight_min_kg",
        "max_weight": "weight_max_kg",
        "min_expectancy": "life_expectancy_min",
        "max_expectancy": "life_expectancy_max",
    }, inplace=True)

    df["size_category"] = df.apply(
        lambda r: derive_size_category(r["weight_max_kg"], r.get("height_max_cm")),
        axis=1,
    )

    df["working_dog"] = df["akc_group"].apply(
        lambda g: 1
        if g in ("Working Group", "Herding Group")
        else 0
    )

    cat_cols = [c for c in df.columns if c.endswith("_category") and c != "size_category"]
    src_cols = list(SCORING_CONVERSIONS.keys())
    drop_cols = [c for c in cat_cols + src_cols if c in df.columns]
    df.drop(columns=drop_cols, inplace=True)

    df = add_image_urls(df, dog_images)

    dupes = df[df["breed_name"].duplicated()]
    if not dupes.empty:
        raise ValueError(
            f"Duplicate breed_name after merge: "
            f"{dupes['breed_name'].tolist()}"
        )

    print(f"  -> Merge complete. {len(df)} breeds.")
    return df


# ---------------------------------------------------------------------------
# Step 3 — Claude batch generation
# ---------------------------------------------------------------------------

def all_claude_cols_populated(row: pd.Series) -> bool:
    return all(pd.notna(row.get(c)) for c in CLAUDE_COLUMNS)


def build_prompt(batch: list[dict]) -> str:
    breed_lines = []
    for b in batch:
        breed_lines.append(json.dumps(b))
    breeds_json = "\n".join(breed_lines)

    columns_list = ", ".join(CLAUDE_COLUMNS)
    return (
        f"For each dog breed below, return a JSON array with one object "
        f"per breed containing exactly these keys: {columns_list}.\n\n"
        f"Rules:\n"
        f"- All integer score fields (not llm_summary) "
        f"use the scale defined in Column definitions below.\n"
        f"- Boolean fields (hypoallergenic, good_with_kids, good_with_dogs,"
        f" good_with_cats, good_with_elderly, apartment_suitable, needs_yard,"
        f" urban_suitable, first_time_owner_suitable, guard_dog) must be"
        f" 0 or 1 integers.\n"
        f"- experience_required is an integer 1-3 "
        f"(1=none, 2=some, 3=experienced).\n"
        f"- llm_summary: exactly 2-3 sentences describing this breed's "
        f"suitability as a pet. Maximum 3 sentences.\n"
        f"- Return only the JSON array. No preamble, no markdown, "
        f"no explanation.\n"
        f"- Return the breeds in the exact same order they were provided, "
        f"with no breeds skipped or reordered.\n\n"
        f"Column definitions:\n"
        f"- energy_level: 1=very low energy, 5=extremely high energy\n"
        f"- barking_level: 1=rarely barks, 5=barks constantly\n"
        f"- trainability: 1=very difficult to train, "
        f"5=extremely easy to train\n"
        f"- affection_level: 1=very aloof, 5=extremely affectionate\n"
        f"- protective_instinct: 1=no guarding tendency, "
        f"5=strong guard dog\n"
        f"- independence: 1=very clingy/needy, 5=very independent\n"
        f"- playfulness: 1=very low playfulness, 5=extremely playful\n"
        f"- intelligence: 1=low intelligence, 5=highly intelligent\n"
        f"- separation_anxiety: 1=very calm when alone, "
        f"5=severe separation anxiety\n"
        f"- good_with_strangers: 1=aggressive or fearful with strangers, "
        f"5=very friendly\n"
        f"- heat_tolerance: 1=very poor heat tolerance, "
        f"5=thrives in heat\n"
        f"- cold_tolerance: 1=very poor cold tolerance, "
        f"5=thrives in cold\n"
        f"- grooming_cost_tier: 1=low cost occasional brushing, "
        f"2=medium regular grooming, "
        f"3=high frequent professional grooming\n"
        f"- vet_cost_tier: 1=generally healthy low vet costs, "
        f"2=moderate health issues, "
        f"3=prone to expensive health problems\n"
        f"- experience_required: 1=perfect for first-time owners, "
        f"2=some experience helpful, 3=experienced owners only\n"
        f"- exercise_min_per_day: average minutes of exercise needed "
        f"daily as an integer\n"
        f"- monthly_food_cost_usd: average monthly food cost in USD "
        f"as an integer\n"
        f"- monthly_total_cost_usd: average monthly total cost food plus "
        f"grooming in USD as an integer\n"
        f"- hypoallergenic: 1 if the breed has a coat type that does not shed"
        f" dander significantly and is commonly considered hypoallergenic"
        f" (e.g. Poodle, Bichon Frise), 0 otherwise\n"
        f"- coat_type: one of exactly these values: "
        f"short, medium, long, double, wire, curly\n\n"
        f"Breeds:\n{breeds_json}"
    )


def strip_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def cast_booleans(df: pd.DataFrame) -> pd.DataFrame:
    for col in BOOLEAN_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            ).astype("Int64")
    return df


def run_claude_batches(df: pd.DataFrame) -> pd.DataFrame:
    print("\nStep 3: Claude batch generation ...")

    if CHECKPOINT.exists():
        print(f"  Loading checkpoint from {CHECKPOINT} ...")
        checkpoint_df = pd.read_csv(CHECKPOINT)
        for col in CLAUDE_COLUMNS:
            if col in checkpoint_df.columns:
                df[col] = df[col].where(
                    df["breed_name"].map(
                        checkpoint_df.set_index("breed_name")
                        .get(col, pd.Series(dtype=object))
                    ).isna(),
                    other=df["breed_name"].map(
                        checkpoint_df.set_index("breed_name")[col]
                    ) if col in checkpoint_df.columns else df.get(col),
                )

    for col in CLAUDE_COLUMNS:
        if col not in df.columns:
            df[col] = None

    needs_fill = df[
        ~df.apply(all_claude_cols_populated, axis=1)
    ].copy()
    print(f"  -> {len(needs_fill)} breeds need Claude generation")

    client = anthropic.Anthropic()
    batches = [
        needs_fill.iloc[i:i + BATCH_SIZE]
        for i in range(0, len(needs_fill), BATCH_SIZE)
    ]
    total_batches = len(batches)

    for batch_num, batch_df in enumerate(batches, start=1):
        print(f"  Batch {batch_num}/{total_batches} "
              f"({len(batch_df)} breeds) ...")

        breed_contexts = []
        for _, row in batch_df.iterrows():
            ctx = {
                "breed_name": row.get("breed_name"),
                "description": str(row.get("description", ""))[:500],
                "temperament": row.get("temperament"),
                "akc_group": row.get("akc_group"),
            }
            for col in [
                "energy_level", "trainability", "shedding_level",
                "grooming_frequency", "good_with_strangers",
            ]:
                if col in row and pd.notna(row[col]):
                    ctx[col] = row[col]
            breed_contexts.append(ctx)

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8192,
                system=(
                    "You are a dog breed expert. "
                    "Return only valid JSON. "
                    "No preamble, no markdown, no explanation."
                ),
                messages=[{
                    "role": "user",
                    "content": build_prompt(breed_contexts),
                }],
            )
            raw = response.content[0].text
            cleaned = strip_markdown(raw)
            results = json.loads(cleaned)

            if len(results) == len(breed_contexts):
                # Positional merge: ignore Claude's breed_name field and
                # assign each result to the corresponding input row by index.
                # This is robust to unicode mismatches in returned names.
                df_indices = list(batch_df.index)
                for pos, result in enumerate(results):
                    df_idx = df_indices[pos]
                    for col in CLAUDE_COLUMNS:
                        if col in result:
                            df.at[df_idx, col] = result[col]
            else:
                # Length mismatch — fall back to name-based matching.
                print(
                    f"    [WARN] batch {batch_num}: Claude returned "
                    f"{len(results)} results for {len(breed_contexts)} "
                    f"breeds — falling back to name-based merge"
                )
                with open(ERROR_LOG, "a") as f:
                    f.write(
                        f"Batch {batch_num}: length mismatch "
                        f"({len(results)} results, "
                        f"{len(breed_contexts)} breeds) — "
                        f"using name-based fallback\n\n"
                    )
                result_df = pd.DataFrame(results)
                if "breed_name" not in result_df.columns:
                    result_df.insert(
                        0, "breed_name",
                        [b["breed_name"] for b in breed_contexts]
                    )
                for col in CLAUDE_COLUMNS:
                    if col in result_df.columns:
                        mapping = result_df.set_index(
                            "breed_name"
                        )[col].to_dict()
                        df[col] = df.apply(
                            lambda r, c=col, m=mapping: m.get(
                                r["breed_name"], r.get(c)
                            ),
                            axis=1,
                        )

            print("    -> OK")

        except Exception as e:
            failed_names = [b["breed_name"] for b in breed_contexts]
            print(f"    [ERROR] batch {batch_num}: {e}")
            with open(ERROR_LOG, "a") as f:
                f.write(f"Batch {batch_num}: {e}\n")
                f.write("\n".join(failed_names) + "\n\n")

        if batch_num % CHECKPOINT_EVERY == 0:
            df.to_csv(CHECKPOINT, index=False)
            print(f"    Checkpoint saved ({batch_num}/{total_batches})")

    df = cast_booleans(df)
    df.to_csv(CHECKPOINT, index=False)
    print(f"  Final checkpoint saved to {CHECKPOINT}")
    return df


# ---------------------------------------------------------------------------
# Step 4 — Final output
# ---------------------------------------------------------------------------

def write_final(df: pd.DataFrame) -> None:
    print("\nStep 4: Writing final output ...")

    if "description" in df.columns:
        df = df.drop(columns=["description"])

    for col in SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df.reindex(columns=SCHEMA_COLUMNS)

    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        print(f"  [WARNING] Entirely empty columns: {empty_cols}")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FINAL_CSV, index=False)
    print(f"  Saved {FINAL_CSV}")

    print("\n--- Summary ---")
    print(f"Total breeds:     {len(df)}")
    print(f"Columns written:  {len(df.columns)}")
    print("\nNull counts per column:")
    null_counts = df.isna().sum()
    for col, count in null_counts[null_counts > 0].items():
        print(f"  {col}: {count}")
    if null_counts.sum() == 0:
        print("  (none)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    akc, dog_breeds, dog_images = load_inputs()
    df = merge_step(akc, dog_breeds, dog_images)
    df = run_claude_batches(df)
    write_final(df)
    print("\nDone.")


if __name__ == "__main__":
    main()
