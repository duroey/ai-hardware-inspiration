"""Classify raw products into abstract types using Claude API."""

import json
import os
import time
import argparse
from pathlib import Path

import anthropic

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001")

CATALOG_DIR = Path(__file__).parent.parent / "catalog"

SENSOR_PROMPT = """你是一个电子元器件分类专家。我会给你一批传感器产品名称，请把它们归类为抽象的传感器类型。

规则：
1. 同类传感器合并为一个类型（如 MQ2、MQ4、MQ5 都是"气体传感器"）
2. 类型名用中文，简洁明确（如"温湿度传感器"、"距离传感器"、"摄像头"）
3. 每个产品只归到一个类型
4. 如果产品不是传感器（是开发板、套件、配件等），归类为"非传感器"

请以 JSON 格式输出，格式为：
{"types": {"类型名": ["产品1", "产品2", ...]}}

以下是产品列表：
"""

ACTUATOR_PROMPT = """你是一个电子元器件分类专家。我会给你一批执行器/输出设备产品名称，请把它们归类为抽象的执行器类型。

规则：
1. 同类执行器合并为一个类型（如各种型号的舵机都是"舵机"）
2. 类型名用中文，简洁明确（如"舵机"、"OLED显示屏"、"蜂鸣器"、"继电器"）
3. 每个产品只归到一个类型
4. 如果产品不是执行器（是开发板、传感器、套件、配件等），归类为"非执行器"

请以 JSON 格式输出，格式为：
{"types": {"类型名": ["产品1", "产品2", ...]}}

以下是产品列表：
"""


def classify_batch(names: list[str], prompt_template: str, batch_idx: int) -> dict:
    """Send a batch of product names to Claude for classification.

    Args:
        names: List of product names to classify.
        prompt_template: The system prompt for classification.
        batch_idx: Batch index for logging.

    Returns:
        Dict mapping type names to lists of product names.
    """
    client = anthropic.Anthropic(api_key=API_KEY, base_url=BASE_URL)

    names_text = "\n".join(f"- {name}" for name in names)
    prompt = prompt_template + names_text

    print(f"  Batch {batch_idx}: classifying {len(names)} products...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    # Extract JSON from response
    try:
        # Try to find JSON block
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0]
        else:
            json_str = text

        result = json.loads(json_str.strip())
        types = result.get("types", result)
        print(f"    Got {len(types)} types")
        return types
    except (json.JSONDecodeError, IndexError) as e:
        print(f"    Parse error: {e}")
        print(f"    Raw response: {text[:500]}")
        return {}


def merge_types(all_batches: list[dict]) -> dict:
    """Merge classification results from multiple batches.

    Args:
        all_batches: List of type dicts from each batch.

    Returns:
        Merged dict mapping type names to product lists.
    """
    merged = {}
    for batch in all_batches:
        for type_name, products in batch.items():
            if type_name in merged:
                merged[type_name].extend(products)
            else:
                merged[type_name] = list(products)
    return merged


def main():
    parser = argparse.ArgumentParser(description="Classify products into abstract types using Claude")
    parser.add_argument(
        "--target",
        choices=["sensors", "actuators", "both"],
        default="both",
        help="What to classify",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="Products per API call",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between API calls",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only classify first batch",
    )
    args = parser.parse_args()

    if args.target in ("sensors", "both"):
        print("=== Classifying Sensors ===")
        with open(CATALOG_DIR / "raw" / "_sensor_names.json") as f:
            sensors = json.load(f)
        names = [s["name"] for s in sensors]
        # Deduplicate names
        names = list(dict.fromkeys(names))
        print(f"  {len(names)} unique sensor product names")

        batches = [names[i:i+args.batch_size] for i in range(0, len(names), args.batch_size)]
        if args.test:
            batches = batches[:1]

        all_results = []
        for i, batch in enumerate(batches):
            result = classify_batch(batch, SENSOR_PROMPT, i+1)
            all_results.append(result)
            if i < len(batches) - 1:
                time.sleep(args.delay)

        merged = merge_types(all_results)
        # Remove non-sensor category
        merged.pop("非传感器", None)

        output = CATALOG_DIR / "classified_sensors.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print(f"  Saved {len(merged)} sensor types to {output}")

    if args.target in ("actuators", "both"):
        print("\n=== Classifying Actuators ===")
        with open(CATALOG_DIR / "raw" / "_actuator_names.json") as f:
            actuators = json.load(f)
        names = [a["name"] for a in actuators]
        names = list(dict.fromkeys(names))
        print(f"  {len(names)} unique actuator product names")

        batches = [names[i:i+args.batch_size] for i in range(0, len(names), args.batch_size)]
        if args.test:
            batches = batches[:1]

        all_results = []
        for i, batch in enumerate(batches):
            result = classify_batch(batch, ACTUATOR_PROMPT, i+1)
            all_results.append(result)
            if i < len(batches) - 1:
                time.sleep(args.delay)

        merged = merge_types(all_results)
        merged.pop("非执行器", None)

        output = CATALOG_DIR / "classified_actuators.json"
        with open(output, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print(f"  Saved {len(merged)} actuator types to {output}")

    print("\nDone.")


if __name__ == "__main__":
    main()
