import asyncio
import json
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "https://api.thedogapi.com/v1"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
BREEDS_FILE = RAW_DIR / "dog_api_breeds.json"
IMAGES_FILE = RAW_DIR / "dog_api_images.json"


def get_headers() -> dict:
    api_key = os.getenv("DOG_API_KEY")
    if not api_key:
        raise RuntimeError("DOG_API_KEY not set in .env")
    return {"x-api-key": api_key}


async def fetch_breeds(client: httpx.AsyncClient) -> list[dict]:
    print("Fetching /v1/breeds ...")
    response = await client.get(f"{BASE_URL}/breeds", headers=get_headers())
    response.raise_for_status()
    breeds = response.json()
    print(f"  -> {len(breeds)} breeds received")
    return breeds


async def fetch_images_for_breed(
    client: httpx.AsyncClient,
    breed_id: int,
    breed_name: str,
    failed: list[int],
) -> list[dict]:
    try:
        response = await client.get(
            f"{BASE_URL}/images/search",
            headers=get_headers(),
            params={"breed_id": breed_id, "limit": 2},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        print(f"  [ERROR] breed_id={breed_id} ({breed_name}): {e}")
        failed.append(breed_id)
        return []


async def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        breeds = await fetch_breeds(client)

        BREEDS_FILE.write_text(json.dumps(breeds, indent=2))
        print(f"Saved {BREEDS_FILE}")

        images_by_breed: dict[str, list[dict]] = {}
        failed_breed_ids: list[int] = []
        total = len(breeds)

        print(f"\nFetching images for {total} breeds "
              f"(1s delay between requests) ...")
        for i, breed in enumerate(breeds, start=1):
            breed_id = breed["id"]
            breed_name = breed.get("name", f"id={breed_id}")
            print(f"  [{i}/{total}] {breed_name}")

            images = await fetch_images_for_breed(
                client, breed_id, breed_name, failed_breed_ids
            )
            images_by_breed[str(breed_id)] = images

            if i < total:
                await asyncio.sleep(1)

    IMAGES_FILE.write_text(json.dumps(images_by_breed, indent=2))
    print(f"\nSaved {IMAGES_FILE}")

    print("\n--- Summary ---")
    print(f"Total breeds pulled:          {total}")
    print(f"Total image requests made:    {total}")
    print(f"Successful image requests:    {total - len(failed_breed_ids)}")
    if failed_breed_ids:
        print(f"Failed breed IDs ({len(failed_breed_ids)}): "
              f"        {failed_breed_ids}")
    else:
        print("Failed breed IDs:             none")


if __name__ == "__main__":
    asyncio.run(main())
