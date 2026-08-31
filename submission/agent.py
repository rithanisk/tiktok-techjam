from __future__ import annotations

import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .policy import QuestionPolicy
from .retrieval import RetrievalPortfolio
from .state import IntentLedger
from .trace import TraceRecorder


class Agent:
    """Offline, deterministic conversational shopping agent.

    `competition` policy mode reproduces the strongest public-evaluator path.
    Set `TECHJAM_POLICY_MODE=adaptive` for concrete information-gain questions.
    """

    def __init__(
        self,
        catalog_path: str | Path = "data/catalog.jsonl",
        policy_mode: str | None = None,
        trace_dir: str | Path | None = None,
        max_sessions: int = 1000,
        field_weights: tuple[tuple[float, ...], ...] | None = None,
        enable_novelty: bool = True,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.policy_mode = policy_mode or os.getenv("TECHJAM_POLICY_MODE", "competition")
        retrieval_options: dict[str, Any] = {"enable_novelty": enable_novelty}
        if field_weights is not None:
            retrieval_options["field_weights"] = field_weights
        self.retrieval = RetrievalPortfolio(self.catalog_path, **retrieval_options)
        self.policy = QuestionPolicy(self.policy_mode)
        self.traces = TraceRecorder(trace_dir or os.getenv("TECHJAM_TRACE_DIR"))
        self.max_sessions = max(1, int(max_sessions))
        self.sessions: OrderedDict[str, IntentLedger] = OrderedDict()
        self._last_recommendations: dict[str, list[str]] = {}

    def reset(self, session_id: str, user_profile: dict) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(user_profile, dict):
            raise TypeError("user_profile must be a dict")
        if session_id in self.sessions:
            del self.sessions[session_id]
        self.sessions[session_id] = IntentLedger(session_id, user_profile)
        self.retrieval.reset_session(session_id)
        self.traces.reset(session_id)
        self._last_recommendations.pop(session_id, None)
        while len(self.sessions) > self.max_sessions:
            expired, _ = self.sessions.popitem(last=False)
            self._last_recommendations.pop(expired, None)
            self.retrieval.reset_session(expired)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        if session_id not in self.sessions:
            raise RuntimeError("reset must be called before respond")
        ledger = self.sessions.pop(session_id)
        self.sessions[session_id] = ledger
        message = user_message if isinstance(user_message, str) else str(user_message or "")
        safe_turn = max(1, min(int(turn), 10))
        safe_top_k = max(1, min(int(top_k), 10))
        started = time.perf_counter()
        ledger.update(message, safe_turn)

        history_terms = ledger.history_terms()
        active_terms = ledger.active_terms()
        if self.policy_mode == "competition":
            query_terms = history_terms
            fingerprint = tuple(history_terms)
        else:
            query_terms = active_terms or history_terms
            fingerprint = ledger.fingerprint() or tuple(query_terms)

        error: str | None = None
        try:
            result = self.retrieval.search(session_id, query_terms, fingerprint, safe_top_k)
            recommendation_ids = result.ids
            candidate_products = self.retrieval.product_rows(result.candidate_ids)
        except Exception as exc:  # bounded local fallback; trace preserves the cause
            error = f"{type(exc).__name__}: {exc}"
            recommendation_ids = self._last_recommendations.get(session_id) or self.retrieval.fallback_ids(safe_top_k)
            candidate_products = self.retrieval.product_rows(recommendation_ids)
            result = None

        decision = self.policy.decide(ledger, candidate_products, safe_turn)
        ledger.record_ask(decision.attribute)
        route, route_confidence = self.policy.route(ledger)
        self._last_recommendations[session_id] = list(recommendation_ids)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        event = {
            "turn": safe_turn,
            "policy_mode": self.policy_mode,
            "route": route,
            "route_confidence": route_confidence,
            "query_terms": query_terms,
            "active_terms": active_terms,
            "ledger": ledger.snapshot(),
            "question": {
                "attribute": decision.attribute,
                "reason": decision.reason,
                "estimated_value": decision.estimated_value,
            },
            "retrieval": {
                "recommendations": recommendation_ids,
                "page": result.page if result else None,
                "query_changed": result.query_changed if result else None,
                "candidate_count": len(result.candidate_ids) if result else len(recommendation_ids),
                "views": result.view_count if result else 0,
                "fallback": result.used_fallback if result else True,
            },
            "latency_ms": round(elapsed_ms, 3),
            "error": error,
        }
        self.traces.record(session_id, event)

        return {
            "message": decision.message,
            "ask_attribute": decision.attribute,
            "recommendations": [{"parent_asin": value} for value in recommendation_ids],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    def get_trace(self, session_id: str) -> list[dict[str, Any]]:
        return self.traces.events(session_id)

    def close(self) -> None:
        self.retrieval.close()
