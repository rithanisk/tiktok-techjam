from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.weak_bm25 import WeakBM25Agent
from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from submission.agent import Agent
from submission.retrieval import FIELD_WEIGHTS


def aggregate(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "sessions"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce component-level retrieval ablations")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default="docs/ablation_results.json")
    args = parser.parse_args()
    samples = load_jsonl(args.dataset)
    catalog_ids, categories, products = catalog_index(args.catalog)
    configurations = [
        ("official_weak_baseline", lambda: WeakBM25Agent(args.catalog)),
        ("stateful_single_view", lambda: Agent(
            args.catalog, policy_mode="competition", field_weights=(FIELD_WEIGHTS[-1],), enable_novelty=False,
        )),
        ("three_view_fusion", lambda: Agent(
            args.catalog, policy_mode="competition", enable_novelty=False,
        )),
        ("progressive_portfolio", lambda: Agent(
            args.catalog, policy_mode="competition", enable_novelty=True,
        )),
    ]
    output: dict[str, dict] = {}
    for name, factory in configurations:
        started = time.perf_counter()
        agent = factory()
        result = evaluate(agent, samples, catalog_ids, categories, products)
        output[name] = {
            "wall_seconds": round(time.perf_counter() - started, 6),
            **aggregate(result),
        }
        close = getattr(agent, "close", None)
        if callable(close):
            close()
        print(f"{name}: {result['recommended_technical_score']:.6f}")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
