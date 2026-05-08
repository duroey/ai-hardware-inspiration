"""Search for similar existing products for each generated idea."""

import json
import os
import time
import argparse
from pathlib import Path

import requests

XAI_API_KEY = os.environ.get("GROK_API_KEY", "")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_MODEL = "grok-3-fast-latest"

RESULTS_DIR = Path(__file__).parent.parent / "results"

SEARCH_PROMPT_TEMPLATE = """搜索以下AI硬件产品创意是否已有类似产品在市面上存在。

产品创意：
- 场景：{scene}
- 卖点：{selling_point}
- 组合：{sensor} + {model} + {actuator} + {carrier}

请搜索并回答：
1. 是否已有类似产品？（yes/no/partial）
2. 如果有，列出最相关的1-3个已有产品（名称+品牌+简述）
3. 与本创意的差异点是什么？
4. 市场竞争程度评估（蓝海/红海/微创新空间）

以JSON格式输出：
{{"exists": "yes/no/partial", "similar_products": ["{{"name": "...", "brand": "...", "description": "..."}}"], "difference": "...", "market": "蓝海/红海/微创新"}}"""


def search_similar(idea: dict) -> dict:
    """Search for similar products for a given idea.

    Args:
        idea: A generated product idea dict.

    Returns:
        Search result dict with similar products info.
    """
    prompt = SEARCH_PROMPT_TEMPLATE.format(
        scene=idea.get("scene", ""),
        selling_point=idea.get("selling_point", ""),
        sensor=idea.get("sensor", ""),
        model=idea.get("model", ""),
        actuator=idea.get("actuator", ""),
        carrier=idea.get("carrier", ""),
    )

    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": XAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "search_mode": "auto",
        "temperature": 0.3,
    }

    resp = requests.post(XAI_API_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    text = data["choices"][0]["message"]["content"]

    # Parse JSON from response
    try:
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0]
        else:
            start = text.find("{")
            end = text.rfind("}") + 1
            json_str = text[start:end]
        return json.loads(json_str.strip())
    except (json.JSONDecodeError, ValueError):
        return {"exists": "unknown", "raw_response": text[:500]}


def main():
    parser = argparse.ArgumentParser(description="Search for similar existing products")
    parser.add_argument(
        "--input",
        type=Path,
        default=RESULTS_DIR / "sample.json",
        help="Input results file to enrich",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file (default: overwrite input)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between search requests",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only search first valid idea",
    )
    args = parser.parse_args()

    with open(args.input) as f:
        results = json.load(f)

    valid_ideas = [r for r in results if r.get("valid", True)]
    print(f"Loaded {len(results)} results, {len(valid_ideas)} valid ideas to search")

    if args.test:
        valid_ideas = valid_ideas[:1]

    for i, idea in enumerate(valid_ideas, 1):
        print(f"\n[{i}/{len(valid_ideas)}] Searching: {idea.get('scene', '')[:40]}...")
        try:
            search_result = search_similar(idea)
            idea["market_research"] = search_result
            exists = search_result.get("exists", "unknown")
            market = search_result.get("market", "?")
            print(f"  → exists={exists}, market={market}")
            if search_result.get("similar_products"):
                for p in search_result["similar_products"][:2]:
                    print(f"    - {p.get('name', '?')} ({p.get('brand', '?')})")
        except Exception as e:
            print(f"  Error: {e}")
            idea["market_research"] = {"exists": "error", "error": str(e)}

        if i < len(valid_ideas):
            time.sleep(args.delay)

    # Save enriched results
    output_path = args.output or args.input
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved enriched results to {output_path}")


if __name__ == "__main__":
    main()
