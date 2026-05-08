"""Scrape sensor and actuator products from DFRobot product search API."""

import json
import time
import argparse
from pathlib import Path

import requests

API_URL = "https://www.dfrobot.com/api/main/product/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json",
}

# DFRobot category IDs (from their category page URLs: /category-{id}.html)
CATEGORIES = {
    "sensors": {"id": "36", "label": "Sensors"},
    "actuators": {"id": "173", "label": "Actuators"},
    "motors": {"id": "49", "label": "Motors & Servos"},
    "displays": {"id": "53", "label": "Displays"},
    "leds": {"id": "54", "label": "LEDs"},
    "relays": {"id": "133", "label": "Relays"},
    "robotics": {"id": "77", "label": "Robotics"},
    "communication": {"id": "52", "label": "Communication"},
}

DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "catalog" / "raw" / "dfrobot"


def search_products(category_id: str, size: int = 50, from_idx: int = 0) -> dict:
    """Search products in a DFRobot category.

    Args:
        category_id: DFRobot category ID string.
        size: Number of results per page.
        from_idx: Starting index for pagination.

    Returns:
        Raw API response dict.
    """
    payload = {
        "category_category_ids": category_id,
        "pm_tag": "",
        "sort": "{}",
        "size": size,
        "from": from_idx,
    }
    resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_product_info(item: dict) -> dict:
    """Extract relevant fields from a DFRobot product item.

    Args:
        item: Raw product item from API (contains 'product' key).

    Returns:
        Cleaned product dict.
    """
    p = item.get("product", item)
    attr = p.get("attribute", {})
    return {
        "product_id": p.get("product_id"),
        "name": attr.get("title", p.get("name", "")),
        "sku": p.get("model", ""),
        "categories": p.get("category_names", "").split(","),
        "category_ids": p.get("category_category_ids", "").split(),
        "description": attr.get("summary", attr.get("structured_description", "")),
        "url": p.get("href", ""),
        "image_url": p.get("image", ""),
        "price": p.get("display_price", ""),
        "available": p.get("available_for_sale", ""),
        "source": "DFRobot",
    }


def fetch_all_products(category_id: str, label: str, delay: float = 1.0) -> list[dict]:
    """Fetch all products for a category, handling pagination.

    Args:
        category_id: DFRobot category ID.
        label: Category label for logging.
        delay: Seconds between requests.

    Returns:
        List of cleaned product dicts.
    """
    all_products = []
    from_idx = 0
    page_size = 100

    while True:
        print(f"  Fetching from index {from_idx}...")
        try:
            data = search_products(category_id, size=page_size, from_idx=from_idx)
        except requests.RequestException as e:
            print(f"  Error at index {from_idx}: {e}")
            break

        if data.get("code") != 0:
            print(f"  API error: {data.get('message')}")
            break

        result = data.get("data", {})
        total_hits = result.get("hits", 0)
        products_raw = result.get("products", [])

        if not products_raw:
            break

        products = [extract_product_info(item) for item in products_raw]
        all_products.extend(products)
        print(f"  Got {len(products)} products (total: {len(all_products)}/{total_hits})")

        if len(all_products) >= total_hits:
            break

        from_idx += page_size
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
    output_path = output_dir / f"dfrobot_{category}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(products)} products to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Scrape DFRobot product catalog")
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
        default=1.0,
        help="Delay between API requests in seconds",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: fetch 3 products from first category",
    )
    args = parser.parse_args()

    print("Scraping DFRobot products...")
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
                data = search_products(cat_info["id"], size=3, from_idx=0)
                result = data.get("data", {})
                total = result.get("hits", 0)
                products = result.get("products", [])
                print(f"  Found {total} total products, showing first {len(products)}:")
                for item in products:
                    p = item.get("product", {})
                    attr = p.get("attribute", {})
                    name = attr.get("title", p.get("name", "?"))
                    sku = p.get("model", "?")
                    print(f"    - {name} (SKU: {sku})")
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
