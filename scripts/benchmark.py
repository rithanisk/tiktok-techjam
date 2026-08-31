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
from starter.agent import Agent as SubmissionAgent
from submission.agent import Agent as PortfolioAgent


class TimedAgent:
    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.latencies_ms: list[float] = []

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.agent.reset(session_id, user_profile)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        started = time.perf_counter()
        response = self.agent.respond(session_id, user_message, turn, top_k)
        self.latencies_ms.append((time.perf_counter() - started) * 1000.0)
        return response


def percentile(values: list[float], proportion: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * proportion)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official metrics plus local latency measurements")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--dataset", default="data/public_set.jsonl")
    parser.add_argument("--policy", choices=("competition", "adaptive"), default="competition")
    parser.add_argument("--output", default="docs/benchmark_results.json")
    args = parser.parse_args()
    build_started = time.perf_counter()
    agent = (
        SubmissionAgent(args.catalog)
        if args.policy == "competition"
        else PortfolioAgent(args.catalog, policy_mode="adaptive")
    )
    index_build_seconds = time.perf_counter() - build_started
    timed = TimedAgent(agent)
    catalog_ids, categories, products = catalog_index(args.catalog)
    result = evaluate(timed, load_jsonl(args.dataset), catalog_ids, categories, products)
    latencies = timed.latencies_ms
    report = {
        "policy_mode": args.policy,
        "index_build_seconds": round(index_build_seconds, 6),
        "response_count": len(latencies),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 6) if latencies else 0.0,
            "p50": round(percentile(latencies, 0.50), 6),
            "p95": round(percentile(latencies, 0.95), 6),
            "p99": round(percentile(latencies, 0.99), 6),
            "max": round(max(latencies), 6) if latencies else 0.0,
        },
        "metrics": {key: value for key, value in result.items() if key != "sessions"},
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    agent.close()


if __name__ == "__main__":
    main()
