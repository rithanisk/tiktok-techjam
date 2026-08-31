from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator.local_evaluator import catalog_index, evaluate, load_jsonl
from submission.agent import Agent
from submission.facet_agent import FacetGraphAgent, HybridFacetAgent


class TimedAgent:
    def __init__(self, agent: object) -> None:
        self.agent = agent
        self.latencies: list[float] = []

    def reset(self, session_id: str, profile: dict) -> None:
        self.agent.reset(session_id, profile)

    def respond(self, session_id: str, message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, message, turn, top_k)
        self.latencies.append((time.perf_counter() - started) * 1000.0)
        return response


def aggregate(result: dict, latencies: list[float], build_seconds: float) -> dict:
    return {
        "build_seconds": round(build_seconds, 6),
        "mean_latency_ms": round(statistics.fmean(latencies), 6) if latencies else 0.0,
        **{key: value for key, value in result.items() if key != "sessions"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare facet graph and current retrieval on the same evaluator")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--output", default="docs/facet_graph_comparison.json")
    args = parser.parse_args()
    samples = load_jsonl(args.dataset)
    catalog_ids, categories, products = catalog_index(args.catalog)
    factories = (
        ("current_progressive_portfolio", lambda: Agent(args.catalog, policy_mode="competition")),
        ("facet_graph_entropy", lambda: FacetGraphAgent(args.catalog, question_mode="entropy")),
        ("facet_graph_other_channel", lambda: FacetGraphAgent(args.catalog, question_mode="competition")),
        ("hybrid_exact_intersection", lambda: HybridFacetAgent(args.catalog)),
    )
    report: dict[str, dict] = {}
    for name, factory in factories:
        started = time.perf_counter()
        raw = factory()
        build_seconds = time.perf_counter() - started
        timed = TimedAgent(raw)
        result = evaluate(timed, samples, catalog_ids, categories, products)
        report[name] = aggregate(result, timed.latencies, build_seconds)
        raw.close()
        print(name, result["recommended_technical_score"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
