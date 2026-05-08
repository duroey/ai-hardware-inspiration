"""Fetch product carrier categories from JD.com category tree.

Extracts physical product categories that could serve as "carriers" for
AI hardware (everyday objects that sensors/actuators can be embedded into).
"""

import json
import re
import argparse
from pathlib import Path
from urllib.parse import unquote

import requests

JD_CATEGORY_URL = "https://dc.3.cn/category/get"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "catalog" / "raw" / "jd_carriers.json"

# Top-level category indices to INCLUDE (physical products that can be carriers)
# Excluded: food(4), beauty-consumables(5), industrial(6), medicine(11),
#           travel(16), art(17), services(18), finance(19)
INCLUDE_INDICES = [0, 1, 2, 3, 7, 8, 9, 10, 12, 13, 14, 15]

# Keywords that indicate non-carrier items (services, digital, consumables)
EXCLUDE_KEYWORDS = [
    "充值", "会员", "服务", "安装", "维修", "保险", "金融", "白条",
    "机票", "酒店", "旅游", "演出", "培训", "课程", "考试",
    "食品", "生鲜", "零食", "饮料", "奶粉", "营养",
    "药品", "计生", "隐形眼镜",
    "电子书", "音乐", "影视", "游戏点卡",
    "运营商", "话费", "流量",
]


def fetch_jd_categories() -> list:
    """Fetch the complete JD category tree.

    Returns:
        List of top-level category dicts.
    """
    resp = requests.get(JD_CATEGORY_URL, params={"from": "jd"}, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("gbk", errors="ignore")
    data = json.loads(text)
    return data.get("data", [])


def parse_category_name(raw: str) -> str:
    """Extract clean category name from JD's pipe-separated format.

    Args:
        raw: Raw category string like "search.jd.com/...|名称||0"

    Returns:
        Clean category name.
    """
    parts = raw.split("|")
    if len(parts) >= 2:
        name = parts[1]
        return unquote(name).strip()
    return raw.strip()


def extract_carriers(categories: list) -> list[dict]:
    """Extract physical product categories suitable as AI hardware carriers.

    Args:
        categories: Raw JD category tree.

    Returns:
        List of carrier category dicts with id, name, parent, level.
    """
    carriers = []
    carrier_id = 0

    for idx in INCLUDE_INDICES:
        if idx >= len(categories):
            continue
        cat = categories[idx]
        subs = cat.get("s", [])

        for sub in subs:
            sub_name = parse_category_name(sub.get("n", ""))
            if not sub_name or should_exclude(sub_name):
                continue

            # Level 2 category
            third_level = sub.get("s", [])
            if third_level:
                for third in third_level:
                    third_name = parse_category_name(third.get("n", ""))
                    if not third_name or should_exclude(third_name):
                        continue
                    carrier_id += 1
                    carriers.append({
                        "id": f"carrier_{carrier_id:04d}",
                        "name": third_name,
                        "parent": sub_name,
                        "level": 3,
                    })
            else:
                carrier_id += 1
                carriers.append({
                    "id": f"carrier_{carrier_id:04d}",
                    "name": sub_name,
                    "parent": "",
                    "level": 2,
                })

    return carriers


def should_exclude(name: str) -> bool:
    """Check if a category name should be excluded.

    Args:
        name: Category name to check.

    Returns:
        True if the category should be excluded.
    """
    return any(kw in name for kw in EXCLUDE_KEYWORDS)


def main():
    parser = argparse.ArgumentParser(description="Fetch carrier categories from JD.com")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output file path",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: print categories without saving",
    )
    args = parser.parse_args()

    print("Fetching JD.com category tree...")
    categories = fetch_jd_categories()
    print(f"Got {len(categories)} top-level categories")

    carriers = extract_carriers(categories)
    print(f"Extracted {len(carriers)} carrier categories")

    if args.test:
        # Group by parent
        by_parent = {}
        for c in carriers:
            parent = c["parent"] or "(top)"
            by_parent.setdefault(parent, []).append(c["name"])
        for parent, names in sorted(by_parent.items()):
            print(f"\n  [{parent}]")
            for n in names[:8]:
                print(f"    - {n}")
            if len(names) > 8:
                print(f"    ... +{len(names)-8} more")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(carriers, f, ensure_ascii=False, indent=2)
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
