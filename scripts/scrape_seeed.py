"""Scrape sensor and actuator products from Seeed Studio via Typesense search API."""

import json
import time
import argparse
from pathlib import Path

import requests

TYPESENSE_HOST = "https://searchv2.seeedstudio.com"
TYPESENSE_API_KEY = "ZQOZ9ITiLVUzYJtNAraPN7V0CaXHYX4J"
COLLECTION = "bazaar4_retailer-products"

HEADERS = {
    "X-TYPESENSE-API-KEY": TYPESENSE_API_KEY,
    "Content-Type": "application/json",
}

# Category IDs mapped from Seeed's Typesense index
CATEGORIES = {
    "sensors": {"id": 2455, "label": "Sensors"},
    "actuators": {"id": 2452, "label": "Actuators"},
    "servos": {"id": 2575, "label": "Servos"},
    "motors": {"id": 2506, "label": "Motors"},
    "displays": {"id": 2504, "label": "Displays"},
    "leds": {"id": 2505, "label": "LEDs"},
    "relays": {"id": 2507, "label": "Relays"},
    "cameras": {"id": 2579, "label": "Cameras"},
    "motor_drivers": {"id": 2576, "label": "Motor Drivers"},
}

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "catalog" / "raw" / "seeed"


def search_products(category_id: int, page: int = 1, per_page: int = 100) -> dict:
    """Search products in a category via Typesense multi_search.

    Args:
        category_id: Seeed internal category ID.
        page: Page number (1-based).
        per_page: Results per page (max 250).

    Returns:
        Raw search response dict.
    """
    payload = {
        "searches": [
            {
                "collection": COLLECTION,
                "q": "*",
                "query_by": "name",
                "filter_by": f"category_ids:{category_id}",
                "per_page": per_page,
                "page": page,
                "sort_by": "popularity:desc",
            }
        ]
    }
    resp = requests.post(
        f"{TYPESENSE_HOST}/multi_search",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_product_info(doc: dict) -> dict:
    """Extract relevant fields from a Typesense document.

    Args:
        doc: Raw document from Typesense hit.

    Returns:
        Cleaned product dict with relevant fields.
    """
    return {
        "product_id": doc.get("product_id"),
        "name": doc.get("name", ""),
        "sku": doc.get("sku", ""),
        "categories": doc.get("category", []),
        "category_ids": doc.get("category_ids", []),
        "short_description": doc.get("short_description", ""),
        "url": doc.get("url", ""),
        "image_url": doc.get("image_url", ""),
        "price": doc.get("price", {}),
        "popularity": doc.get("popularity", 0),
        "source": "Seeed Studio",
    }


def fetch_all_products(category_id: int, label: str, delay: float = 0.5) -> list[dict]:
    """Fetch all products for a category, handling pagination.

    Args:
        category_id: Seeed internal category ID.
        label: Category label for logging.
        delay: Seconds between requests.

    Returns:
        List of cleaned product dicts.
    """
    all_products = []
    page = 1
    per_page = 250

    while True:
        print(f"  Fetching page {page}...")
        try:
            data = search_products(category_id, page=page, per_page=per_page)
        except requests.RequestException as e:
            print(f"  Error on page {page}: {e}")
            break

        results = data.get("results", [{}])[0]
        found = results.get("found", 0)
        hits = results.get("hits", [])

        if not hits:
            break

        products = [extract_product_info(hit["document"]) for hit in hits]
        all_products.extend(products)
        print(f"  Got {len(products)} products (total: {len(all_products)}/{found})")

        if len(all_products) >= found:
            break

        page += 1
        time.sleep(delay)

    return all_products


def save_results(products: list[dict], category: str, output_dir: Path) -> Path:
    """Save fetched products to a JSON file.

    Args:
        products: List of product dicts.
        category: Category key for filename.
        output_dir: Output directory.

    Returns:
        Path to saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"seeed_{category}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(products)} products to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Scrape Seeed Studio product catalog via Typesense")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=list(CATEGORIES.keys()),
        help=f"Categories to scrape. Available: {list(CATEGORIES.keys())}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for raw JSON files",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: fetch 3 products from first category",
    )
    args = parser.parse_args()

    print("Scraping Seeed Studio products via Typesense API...")
    print(f"Categories: {args.categories}")
    print(f"Output dir: {args.output_dir}")
    print()

    for cat_key in args.categories:
        cat_info = CATEGORIES.get(cat_key)
        if not cat_info:
            print(f"Unknown category: {cat_key}, skipping")
            continue

        print(f"[{cat_info['label']}] (category_id={cat_info['id']})...")

        if args.test:
            try:
                data = search_products(cat_info["id"], page=1, per_page=3)
                results = data.get("results", [{}])[0]
                found = results.get("found", 0)
                hits = results.get("hits", [])
                print(f"  Found {found} total products, showing first {len(hits)}:")
                for hit in hits:
                    doc = hit["document"]
                    print(f"    - {doc.get('name')} (SKU: {doc.get('sku', '?')[:30]})")
            except requests.RequestException as e:
                print(f"  Test failed: {e}")
            break

        products = fetch_all_products(cat_info["id"], cat_info["label"], delay=args.delay)
        if products:
            save_results(products, cat_key, args.output_dir)
        else:
            print(f"  No products found")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
