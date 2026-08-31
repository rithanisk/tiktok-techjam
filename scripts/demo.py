from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from submission.agent import Agent


SCRIPT = [
    "I'm looking for women's running shoes, but I'm still exploring.",
    "For that, what matters is: leather; color: black.",
    "Actually, ignore my earlier preference. What I need is: cotton and blue.",
    "I don't have an additional preference for brand.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a changing-intent shopping session")
    parser.add_argument("--catalog", default="data/catalog.jsonl")
    parser.add_argument("--policy", choices=("competition", "adaptive"), default="adaptive")
    args = parser.parse_args()
    agent = Agent(args.catalog, policy_mode=args.policy)
    session_id = "demo-changing-intent"
    agent.reset(session_id, {
        "purchase_frequency": "3-4 prior purchases",
        "average_prior_rating": 4.5,
        "rating_style": "usually positive",
        "preference_tags": ["fit", "comfort"],
        "summary": "Prior purchases emphasize fit and comfort.",
    })
    for turn, message in enumerate(SCRIPT, start=1):
        response = agent.respond(session_id, message, turn, 10)
        event = agent.get_trace(session_id)[-1]
        print(f"\nTURN {turn}\nUSER: {message}\nAGENT: {response['message']}")
        print("TOP ASINS:", ", ".join(item["parent_asin"] for item in response["recommendations"][:3]))
        print("ACTIVE STATE:", json.dumps([
            {"attribute": item["attribute"], "value": item["value"]}
            for item in event["ledger"]["constraints"] if item["active"]
        ]))
        print("ROUTE/PAGE/LATENCY:", event["route"], event["retrieval"]["page"], f"{event['latency_ms']} ms")
    agent.close()


if __name__ == "__main__":
    main()
