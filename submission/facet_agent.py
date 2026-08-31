from __future__ import annotations

import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .facet_graph import EntropyDecision, FacetGraphIndex
from .agent import Agent
from .state import IntentLedger


class FacetGraphAgent:
    """Experimental deterministic alternative used for head-to-head evaluation."""

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        question_mode: str = "entropy",
        oversized_limit: int = 80,
        max_relaxations: int = 3,
        max_sessions: int = 1000,
    ) -> None:
        if question_mode not in {"entropy", "competition"}:
            raise ValueError("question_mode must be 'entropy' or 'competition'")
        self.question_mode = question_mode
        self.index = FacetGraphIndex(catalog_path, oversized_limit, max_relaxations)
        self.max_sessions = max(1, int(max_sessions))
        self.sessions: OrderedDict[str, IntentLedger] = OrderedDict()
        self.events: dict[str, list[dict[str, Any]]] = {}

    def reset(self, session_id: str, user_profile: dict) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        self.sessions[session_id] = IntentLedger(session_id, user_profile)
        self.index.reset_session(session_id)
        self.events[session_id] = []
        while len(self.sessions) > self.max_sessions:
            expired, _ = self.sessions.popitem(last=False)
            self.events.pop(expired, None)
            self.index.reset_session(expired)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        if session_id not in self.sessions:
            raise RuntimeError("reset must be called before respond")
        ledger = self.sessions.pop(session_id)
        self.sessions[session_id] = ledger
        safe_turn = max(1, min(int(turn), 10))
        safe_top_k = max(1, min(int(top_k), 10))
        message = user_message if isinstance(user_message, str) else str(user_message or "")
        started = time.perf_counter()
        ledger.update(message, safe_turn)
        result = self.index.search(
            session_id,
            ledger.active_constraints(),
            ledger.fingerprint(),
            safe_top_k,
        )

        entropy: EntropyDecision | None = None
        ask_attribute: str | None = None
        response_message = "These products satisfy the active facet intersection."
        if safe_turn < 10 and self.question_mode == "competition":
            ask_attribute = "other"
            response_message = "What other requirement or preference matters most?"
        elif safe_turn < 10 and result.oversized:
            excluded = (
                {item.attribute for item in ledger.active_constraints()}
                | ledger.closed_attributes
                | set(ledger.asked_attributes)
            )
            entropy = self.index.clarification(result.candidate_ids, excluded, safe_top_k)
            ask_attribute = entropy.attribute
            response_message = entropy.question or "These are the strongest deterministic matches."
        ledger.record_ask(ask_attribute)

        event = {
            "turn": safe_turn,
            "question_mode": self.question_mode,
            "active_slots": [
                {
                    "attribute": item.attribute,
                    "value": item.value,
                    "hardness": item.hardness,
                    "confidence": item.confidence,
                }
                for item in ledger.active_constraints()
            ],
            "clauses": [
                {
                    "attribute": item.attribute,
                    "value": item.value,
                    "posting_count": len(item.ids),
                    "resolution": item.resolution,
                }
                for item in result.clauses
            ],
            "strict_candidate_count": result.strict_candidate_count,
            "candidate_count": len(result.candidate_ids),
            "intersection_order": result.intersection_order,
            "oversized": result.oversized,
            "relaxations": [item.__dict__ for item in result.relaxations],
            "clarification": entropy.__dict__ if entropy else None,
            "recommendations": result.ids,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        }
        self.events[session_id].append(event)
        return {
            "message": response_message,
            "ask_attribute": ask_attribute,
            "recommendations": [{"parent_asin": value} for value in result.ids],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    def get_trace(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.events.get(session_id, []))

    def close(self) -> None:
        self.index.close()


class HybridFacetAgent:
    """Use exact small facet intersections; retain portfolio recall otherwise.

    The gate is semantic and auditable: facet output is used only when the full,
    unrelaxed conjunction contains at most ``exact_pool_limit`` products.
    """

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        exact_pool_limit: int = 10,
        max_sessions: int = 1000,
    ) -> None:
        self.max_sessions = max(1, int(max_sessions))
        self.portfolio = Agent(catalog_path, policy_mode="competition", max_sessions=self.max_sessions)
        self.facets = FacetGraphAgent(
            catalog_path,
            question_mode="competition",
            max_sessions=self.max_sessions,
        )
        self.exact_pool_limit = max(1, min(int(exact_pool_limit), 10))
        self.decisions: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.portfolio.reset(session_id, user_profile)
        self.facets.reset(session_id, user_profile)
        self.decisions.pop(session_id, None)
        self.decisions[session_id] = []
        while len(self.decisions) > self.max_sessions:
            self.decisions.popitem(last=False)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        portfolio_response = self.portfolio.respond(session_id, user_message, turn, top_k)
        try:
            facet_response = self.facets.respond(session_id, user_message, turn, top_k)
        except Exception as exc:
            self.decisions[session_id].append({
                "turn": turn,
                "source": "progressive_portfolio",
                "strict_candidate_count": None,
                "relaxation_count": None,
                "facet_error": f"{type(exc).__name__}: {exc}",
            })
            return portfolio_response
        trace = self.facets.get_trace(session_id)[-1]
        strict_count = int(trace["strict_candidate_count"])
        use_facets = (
            0 < strict_count <= self.exact_pool_limit
            and not trace["relaxations"]
            and len(facet_response["recommendations"]) == strict_count
        )
        self.decisions[session_id].append({
            "turn": turn,
            "source": "facet_graph" if use_facets else "progressive_portfolio",
            "strict_candidate_count": strict_count,
            "relaxation_count": len(trace["relaxations"]),
        })
        if not use_facets:
            return portfolio_response
        return {
            **facet_response,
            # Both competition policies ask the same universal question. Keep
            # the established wording to make the only variable retrieval.
            "message": portfolio_response["message"],
            "ask_attribute": portfolio_response["ask_attribute"],
        }

    def close(self) -> None:
        self.portfolio.close()
        self.facets.close()

    def get_trace(self, session_id: str) -> list[dict[str, Any]]:
        portfolio = self.portfolio.get_trace(session_id)
        facets = self.facets.get_trace(session_id)
        decisions = self.decisions.get(session_id, [])
        return [
            {
                "hybrid": decision,
                "portfolio": portfolio[index] if index < len(portfolio) else None,
                "facet": facets[index] if index < len(facets) else None,
            }
            for index, decision in enumerate(decisions)
        ]
