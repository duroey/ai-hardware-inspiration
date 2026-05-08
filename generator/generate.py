"""Generate AI hardware product ideas from 4-tuple combinations."""

import json
import os
import random
import time
import argparse
from pathlib import Path
from itertools import product

import anthropic

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5-20251001")

PROJECT_ROOT = Path(__file__).parent.parent
CATALOG_DIR = PROJECT_ROOT / "catalog"
RESULTS_DIR = PROJECT_ROOT / "results"
PROMPT_FILE = Path(__file__).parent / "prompt.txt"


def load_catalog() -> dict:
    """Load all four dimensions from catalog files.

    Returns:
        Dict with keys: sensors, models, actuators, carriers.
    """
    with open(CATALOG_DIR / "classified_sensors.json") as f:
        sensors = list(json.load(f).keys())

    with open(CATALOG_DIR / "raw" / "huggingface_tasks.json") as f:
        models = [item["name"] for item in json.load(f)]

    with open(CATALOG_DIR / "classified_actuators.json") as f:
        actuators = list(json.load(f).keys())

    with open(CATALOG_DIR / "raw" / "jd_carriers.json") as f:
        carriers = [item["name"] for item in json.load(f)]

    return {
        "sensors": sensors,
        "models": models,
        "actuators": actuators,
        "carriers": carriers,
    }


def generate_combinations(catalog: dict, limit: int = None, seed: int = None) -> list[tuple]:
    """Generate all or sampled combinations from the 4 dimensions.

    Args:
        catalog: Dict with sensor/model/actuator/carrier lists.
        limit: If set, randomly sample this many combinations.
        seed: Random seed for reproducibility.

    Returns:
        List of (sensor, model, actuator, carrier) tuples.
    """
    if limit:
        rng = random.Random(seed or 42)
        combos = []
        for _ in range(limit):
            combo = (
                rng.choice(catalog["sensors"]),
                rng.choice(catalog["models"]),
                rng.choice(catalog["actuators"]),
                rng.choice(catalog["carriers"]),
            )
            combos.append(combo)
        return combos
    else:
        return list(product(
            catalog["sensors"],
            catalog["models"],
            catalog["actuators"],
            catalog["carriers"],
        ))


def build_prompt(combinations: list[tuple]) -> str:
    """Build the full prompt for a batch of combinations.

    Args:
        combinations: List of (sensor, model, actuator, carrier) tuples.

    Returns:
        Complete prompt string.
    """
    with open(PROMPT_FILE) as f:
        system_prompt = f.read().strip()

    combos_text = ""
    for i, (sensor, model, actuator, carrier) in enumerate(combinations, 1):
        combos_text += f"\n组合{i}: 传感器={sensor} | AI模型={model} | 执行器={actuator} | 载体={carrier}"

    return system_prompt + "\n" + combos_text


def call_llm(prompt: str) -> list[dict]:
    """Call Claude API to generate product ideas.

    Args:
        prompt: The full prompt string.

    Returns:
        List of result dicts, one per combination.
    """
    client = anthropic.Anthropic(api_key=API_KEY, base_url=BASE_URL)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    # Extract JSON array from response
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0]
    else:
        # Try to find array directly
        start = text.find("[")
        end = text.rfind("]") + 1
        json_str = text[start:end] if start >= 0 else text

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw: {text[:300]}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate AI hardware product ideas")
    parser.add_argument("--sample", type=int, help="Random sample N combinations (for testing)")
    parser.add_argument("--all", action="store_true", help="Generate for ALL combinations")
    parser.add_argument("--batch-size", type=int, default=10, help="Combinations per API call")
    parser.add_argument("--resume", action="store_true", help="Skip already-generated combinations")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls")
    parser.add_argument("--output", type=Path, default=None, help="Output file (default: results/)")
    args = parser.parse_args()

    if not args.sample and not args.all:
        parser.error("Specify --sample N or --all")

    print("Loading catalog...")
    catalog = load_catalog()
    print(f"  Sensors: {len(catalog['sensors'])}")
    print(f"  Models: {len(catalog['models'])}")
    print(f"  Actuators: {len(catalog['actuators'])}")
    print(f"  Carriers: {len(catalog['carriers'])}")

    if args.sample:
        combinations = generate_combinations(catalog, limit=args.sample, seed=args.seed)
        print(f"\nSampled {len(combinations)} random combinations")
    else:
        total = len(catalog["sensors"]) * len(catalog["models"]) * len(catalog["actuators"]) * len(catalog["carriers"])
        print(f"\nTotal combinations: {total:,}")
        print("WARNING: Full generation not recommended without filtering. Use --sample first.")
        return

    # Process in batches
    batches = [combinations[i:i+args.batch_size] for i in range(0, len(combinations), args.batch_size)]
    all_results = []

    for batch_idx, batch in enumerate(batches, 1):
        print(f"\nBatch {batch_idx}/{len(batches)} ({len(batch)} combinations)...")
        prompt = build_prompt(batch)
        results = call_llm(prompt)

        # Attach combination info to results
        for i, result in enumerate(results):
            if i < len(batch):
                sensor, model, actuator, carrier = batch[i]
                result["sensor"] = sensor
                result["model"] = model
                result["actuator"] = actuator
                result["carrier"] = carrier
                result["combination_id"] = f"{sensor}__{model}__{actuator}__{carrier}"

        all_results.extend(results)

        if batch_idx < len(batches):
            time.sleep(args.delay)

    # Output results
    if args.output:
        output_path = args.output
    elif args.sample:
        output_path = RESULTS_DIR / "sample.json"
    else:
        output_path = RESULTS_DIR / "batch_001.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Print results to terminal
    print(f"\n{'='*60}")
    print(f"Generated {len(all_results)} results → {output_path}")
    print(f"{'='*60}\n")

    valid_count = sum(1 for r in all_results if r.get("valid", True))
    print(f"Valid ideas: {valid_count}/{len(all_results)}\n")

    for r in all_results:
        valid = r.get("valid", True)
        marker = "✓" if valid else "✗"
        print(f"{marker} [{r.get('sensor','')} + {r.get('model','')} + {r.get('actuator','')} + {r.get('carrier','')}]")
        if valid:
            print(f"  场景: {r.get('scene', '')}")
            print(f"  卖点: {r.get('selling_point', '')}")
            print(f"  受众: {r.get('audience', '')}")
            print(f"  可行性: {r.get('feasibility', '?')}/5")
            if r.get("extra_models"):
                print(f"  额外模型: {r.get('extra_models')}")
        else:
            print(f"  原因: {r.get('reason', '')}")
        print()


if __name__ == "__main__":
    main()
