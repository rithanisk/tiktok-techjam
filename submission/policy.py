from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .state import IntentLedger
from .text import COLORS, MATERIALS


ALLOWED_ATTRIBUTES = (
    "category", "material", "color", "size", "style", "brand",
    "budget", "feature", "use_case", "other",
)


@dataclass(frozen=True)
class QuestionDecision:
    attribute: str | None
    message: str
    reason: str
    estimated_value: float


class QuestionPolicy:
    """Question-value controller with a reproducible scoring configuration."""

    def __init__(self, mode: str = "competition") -> None:
        if mode not in {"competition", "adaptive"}:
            raise ValueError("policy mode must be 'competition' or 'adaptive'")
        self.mode = mode

    def decide(
        self,
        ledger: IntentLedger,
        candidates: list[dict[str, Any]],
        turn: int,
    ) -> QuestionDecision:
        if turn >= 10:
            return QuestionDecision(None, "These are the strongest matches for your current requirements.", "turn_limit", 0.0)

        if self.mode == "competition":
            return QuestionDecision(
                "other",
                "What other requirement or preference matters most?",
                "universal_constraint_channel",
                1.0,
            )

        known = {item.attribute for item in ledger.active_constraints()}
        excluded = known | ledger.closed_attributes | set(ledger.asked_attributes)
        scored: list[tuple[float, str]] = []
        for attribute in ("material", "feature", "color", "style", "size", "brand", "budget", "use_case"):
            if attribute in excluded:
                continue
            values = [self._attribute_value(product, attribute) for product in candidates[:60]]
            values = [value for value in values if value]
            coverage = len(values) / max(1, min(60, len(candidates)))
            entropy = self._normalized_entropy(values)
            score = coverage * (0.35 + 0.65 * entropy) - 0.025 * max(turn - 1, 0)
            scored.append((score, attribute))

        if not scored:
            return QuestionDecision(
                "other",
                "Is there another requirement I should prioritize?",
                "open_fallback",
                0.1,
            )
        score, attribute = max(scored, key=lambda item: (item[0], item[1]))
        return QuestionDecision(
            attribute,
            self._question(attribute),
            "candidate_information_gain",
            round(score, 6),
        )

    def route(self, ledger: IntentLedger) -> tuple[str, float]:
        active = ledger.active_constraints()
        hard = sum(item.hardness == "hard" and item.attribute != "category" for item in active)
        soft = sum(item.hardness == "soft" for item in active)
        if hard:
            return "buying", min(0.99, 0.72 + 0.08 * hard)
        if soft:
            return "mixed", min(0.85, 0.55 + 0.05 * soft)
        return "browsing", 0.70

    def _normalized_entropy(self, values: list[str]) -> float:
        if len(values) < 2:
            return 0.0
        counts = Counter(values)
        if len(counts) < 2:
            return 0.0
        total = sum(counts.values())
        entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
        return entropy / math.log(len(counts))

    def _attribute_value(self, product: dict[str, Any], attribute: str) -> str:
        text = " ".join([
            str(product.get("title") or ""),
            " ".join(str(value) for value in product.get("features") or []),
            str(product.get("details") or ""),
            " ".join(str(value) for value in product.get("description") or []),
        ]).lower()
        if attribute == "material":
            return next((value for value in MATERIALS if re.search(rf"\b{re.escape(value)}\b", text)), "")
        if attribute == "color":
            return next((value for value in COLORS if re.search(rf"\b{re.escape(value)}\b", text)), "")
        if attribute == "size":
            match = re.search(r"\b(?:size\s*)?(xxs|xs|small|medium|large|xl|xxl|\d{1,2}(?:\.5)?)\b", text)
            return match.group(1) if match else ""
        if attribute == "brand":
            return str(product.get("store") or "").strip().lower()
        if attribute == "budget":
            price = product.get("price")
            if not isinstance(price, (int, float)):
                return ""
            return "under25" if price < 25 else "25to50" if price < 50 else "50to100" if price < 100 else "100plus"
        if attribute == "style":
            details = product.get("details") or {}
            if isinstance(details, dict):
                return " ".join(str(details.get(key) or "") for key in ("Fit Type", "Neck Style", "Sleeve Type")).strip().lower()
        if attribute == "use_case":
            return next((value for value in ("running", "hiking", "winter", "work", "wedding", "casual", "gym") if value in text), "")
        if attribute == "feature":
            features = product.get("features") or []
            return str(features[0]).strip().lower()[:80] if features else ""
        return ""

    def _question(self, attribute: str) -> str:
        questions = {
            "material": "Do you have a material preference?",
            "feature": "Which feature matters most to you?",
            "color": "Do you have a preferred color?",
            "style": "What style or fit would you prefer?",
            "size": "Is there a size or width requirement?",
            "brand": "Do you prefer a particular brand?",
            "budget": "What budget range should I stay within?",
            "use_case": "What will you mainly use it for?",
        }
        return questions.get(attribute, "What other requirement matters most?")
