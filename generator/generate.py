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
MODEL = os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-7")

PROJECT_ROOT = Path(__file__).parent.parent
CATALOG_DIR = PROJECT_ROOT / "catalog"
RESULTS_DIR = PROJECT_ROOT / "results"
PROMPT_FILE = Path(__file__).parent / "prompt.txt"
REJECTED_CACHE = RESULTS_DIR / "rejected.json"


def load_catalog() -> dict:
    """Load all four dimensions from catalog files.

    Returns:
        Dict with keys: sensors, actuators, carriers.
    """
    with open(CATALOG_DIR / "classified_sensors.json") as f:
        sensors = list(json.load(f).keys())

    with open(CATALOG_DIR / "classified_actuators.json") as f:
        actuators = list(json.load(f).keys())

    with open(CATALOG_DIR / "raw" / "jd_carriers.json") as f:
        carriers = [item["name"] for item in json.load(f)]

    return {
        "sensors": sensors,
        "actuators": actuators,
        "carriers": carriers,
    }


def generate_combinations(catalog: dict, limit: int = None, seed: int = None) -> list[dict]:
    """Generate sampled combinations from the 4 dimensions.

    Each combination randomly picks 1-5 sensors, 1-4 actuators, 1-2 carriers.
    AI models are NOT pre-selected — left for LLM to decide.
    Skips combinations that match previously rejected patterns.

    Args:
        catalog: Dict with sensor/model/actuator/carrier lists.
        limit: Number of combinations to sample.
        seed: Random seed for reproducibility.

    Returns:
        List of combination dicts with variable-length selections.
    """
    rng = random.Random(seed or 42)
    rejected = load_rejected()
    combos = []
    attempts = 0
    max_attempts = (limit or 10) * 5

    while len(combos) < (limit or 10) and attempts < max_attempts:
        attempts += 1
        n_sensors = rng.randint(1, 5)
        n_actuators = rng.randint(1, 4)
        n_carriers = rng.randint(1, 2)

        combo = {
            "sensors": sorted(rng.sample(catalog["sensors"], min(n_sensors, len(catalog["sensors"])))),
            "actuators": sorted(rng.sample(catalog["actuators"], min(n_actuators, len(catalog["actuators"])))),
            "carriers": sorted(rng.sample(catalog["carriers"], min(n_carriers, len(catalog["carriers"])))),
        }

        key = combo_key(combo)
        if key not in rejected:
            combos.append(combo)

    if attempts >= max_attempts:
        print(f"  Warning: hit max attempts, generated {len(combos)}/{limit or 10}")

    return combos


def combo_key(combo: dict) -> str:
    """Generate a unique key for a combination for deduplication."""
    return "|".join([
        ",".join(combo["sensors"]),
        ",".join(combo["actuators"]),
        ",".join(combo["carriers"]),
    ])


def load_rejected() -> set:
    """Load previously rejected combination keys."""
    if REJECTED_CACHE.exists():
        with open(REJECTED_CACHE) as f:
            return set(json.load(f))
    return set()


def save_rejected(rejected: set):
    """Save rejected combination keys to cache."""
    REJECTED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(REJECTED_CACHE, "w", encoding="utf-8") as f:
        json.dump(sorted(rejected), f, ensure_ascii=False, indent=2)


def build_prompt(combinations: list[dict]) -> str:
    """Build the full prompt for a batch of combinations.

    Args:
        combinations: List of combo dicts with sensors/actuators/carriers.

    Returns:
        Complete prompt string.
    """
    with open(PROMPT_FILE) as f:
        system_prompt = f.read().strip()

    combos_text = ""
    for i, combo in enumerate(combinations, 1):
        sensors = ", ".join(combo["sensors"])
        actuators = ", ".join(combo["actuators"])
        carriers = ", ".join(combo["carriers"])
        combos_text += f"\n组合{i}: 传感器=[{sensors}] | 执行器=[{actuators}] | 载体=[{carriers}]"

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

    if not args.sample:
        parser.error("Specify --sample N")

    print("Loading catalog...")
    catalog = load_catalog()
    print(f"  Sensors: {len(catalog['sensors'])} types (pick 1-5)")
    print(f"  Actuators: {len(catalog['actuators'])} types (pick 1-4)")
    print(f"  Carriers: {len(catalog['carriers'])} items (pick 1-2)")
    print(f"  AI Models: LLM decides")

    combinations = generate_combinations(catalog, limit=args.sample, seed=args.seed)
    print(f"\nSampled {len(combinations)} combinations")

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
                result["sensors"] = batch[i]["sensors"]
                result["actuators"] = batch[i]["actuators"]
                result["carriers"] = batch[i]["carriers"]

        all_results.extend(results)

        if batch_idx < len(batches):
            time.sleep(args.delay)

    # Cache rejected combinations
    rejected = load_rejected()
    new_rejected = 0
    for r in all_results:
        if not r.get("valid", True):
            key = combo_key({"sensors": r.get("sensors", []), "actuators": r.get("actuators", []), "carriers": r.get("carriers", [])})
            if key not in rejected:
                rejected.add(key)
                new_rejected += 1
    if new_rejected:
        save_rejected(rejected)
        print(f"\nCached {new_rejected} new rejected combinations (total: {len(rejected)})")

    # Output results (only valid ones, append to existing)
    valid_results = [r for r in all_results if r.get("valid", True)]
    output_path = args.output or RESULTS_DIR / "ideas.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
    existing.extend(valid_results)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # Print results to terminal
    print(f"\n{'='*60}")
    print(f"Generated {len(all_results)} results → {output_path}")
    print(f"{'='*60}\n")

    print(f"Valid: {len(valid_results)}/{len(all_results)}\n")

    for r in valid_results:
        sensors = ", ".join(r.get("sensors", []))
        actuators = ", ".join(r.get("actuators", []))
        carriers = ", ".join(r.get("carriers", []))
        print(f"✓ [{r.get('product_name', '')}] 传感器=[{sensors}] | 执行器=[{actuators}] | 载体=[{carriers}]")
        print(f"  场景: {r.get('scene', '')}")
        print(f"  卖点: {r.get('selling_point', '')}")
        print(f"  受众: {r.get('audience', '')} | 可行性: {r.get('feasibility', '?')}/5")
        print()
        print()


if __name__ == "__main__":
    main()
