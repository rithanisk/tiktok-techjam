from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass
from typing import Any

from .text import classify_attribute, clean_value, terms


CORRECTION_RE = re.compile(r"\b(actually|instead|ignore|forget|rather than|changed my mind)\b", re.I)
CATEGORY_RE = re.compile(r"\b(?:i(?:'m| am)\s+)?looking for\s+(.+?)(?:,|\.|$)", re.I)
NO_PREFERENCE_RE = re.compile(
    r"\b(?:do not|don't|dont)\s+have\s+(?:(?:an\s+additional|a)\s+)?preference\s+for\s+([a-z_ -]+?)(?:;|,|\.|$)",
    re.I,
)


@dataclass
class Constraint:
    value: str
    attribute: str
    hardness: str
    polarity: str
    source_turn: int
    confidence: float
    active: bool = True
    superseded_by_turn: int | None = None


class IntentLedger:
    """Session-scoped, auditable conversational state.

    The ledger never destroys history. Corrections mark superseded preferences
    inactive, so a trace can explain both the old and new state.
    """

    def __init__(self, session_id: str, user_profile: dict[str, Any] | None = None) -> None:
        self.session_id = session_id
        self.user_profile = copy.deepcopy(user_profile or {})
        self.constraints: list[Constraint] = []
        self.raw_messages: list[str] = []
        self.asked_attributes: list[str] = []
        self.closed_attributes: set[str] = set()
        self.last_update_kind = "reset"

    def update(self, message: str, turn: int) -> None:
        message = clean_value(message, limit=4000)
        self.raw_messages.append(message)
        self.last_update_kind = "message"
        if not message:
            return

        no_preference = NO_PREFERENCE_RE.search(message)
        if no_preference:
            attribute = no_preference.group(1).strip().replace(" ", "_")
            if attribute.startswith("additional_"):
                attribute = attribute.removeprefix("additional_")
            if attribute in {
                "category", "material", "color", "size", "style", "brand",
                "budget", "feature", "use_case", "other",
            }:
                self.closed_attributes.add(attribute)
            self.last_update_kind = "no_preference"
            return

        correction = bool(CORRECTION_RE.search(message))
        if correction:
            self._tombstone_replaced_preferences(turn, message)
            self.last_update_kind = "override"

        category_match = CATEGORY_RE.search(message)
        if category_match:
            category = clean_value(category_match.group(1))
            if category and "still exploring" not in category.lower():
                self._add(category, "category", "hard", turn, 0.98)

        extracted = False
        markers = (
            ("a key requirement is:", "hard", 1.0),
            ("what matters is:", "hard", 0.95),
            ("what i need is:", "hard", 1.0),
            ("my preference is:", "soft", 0.90),
        )
        lowered = message.lower()
        for marker, hardness, confidence in markers:
            index = lowered.find(marker)
            if index < 0:
                continue
            payload = message[index + len(marker):]
            for value in re.split(r"\s*;\s*|\s+and\s+(?=[a-zA-Z])", payload):
                value = clean_value(value)
                if value:
                    self._add(value, classify_attribute(value), hardness, turn, confidence)
                    extracted = True

        if category_match and not extracted:
            remainder = message[category_match.end():]
            remainder = clean_value(remainder)
            if remainder and "still exploring" not in remainder.lower():
                self._add(remainder, classify_attribute(remainder), "soft", turn, 0.72)
                extracted = True

        if not category_match and not extracted and self._is_informative_free_text(message):
            self._add(message, classify_attribute(message), "soft", turn, 0.62)

    def _is_informative_free_text(self, message: str) -> bool:
        lowered = message.lower()
        ignored = (
            "those options are not quite right",
            "ask me about one specific attribute",
            "i don't have an additional preference",
            "i do not have an additional preference",
        )
        return not any(value in lowered for value in ignored) and len(terms(message)) > 0

    def _add(
        self,
        value: str,
        attribute: str,
        hardness: str,
        turn: int,
        confidence: float,
    ) -> None:
        normalized = clean_value(value).lower()
        if not normalized:
            return
        for existing in self.constraints:
            if existing.active and existing.attribute == attribute and existing.value.lower() == normalized:
                existing.confidence = max(existing.confidence, confidence)
                if hardness == "hard":
                    existing.hardness = "hard"
                return
        self.constraints.append(Constraint(
            value=clean_value(value),
            attribute=attribute,
            hardness=hardness,
            polarity="positive",
            source_turn=turn,
            confidence=confidence,
        ))

    def _tombstone_replaced_preferences(self, turn: int, message: str) -> None:
        lowered = message.lower()
        replace_all = any(phrase in lowered for phrase in (
            "ignore my earlier preference",
            "ignore all earlier",
            "forget my earlier preference",
            "changed my mind",
        ))
        if replace_all:
            targets = [
                item for item in self.constraints
                if item.active and item.attribute != "category"
            ]
        else:
            soft = [
                item for item in self.constraints
                if item.active and item.attribute != "category" and item.hardness == "soft"
            ]
            targets = soft or [
                item for item in self.constraints
                if item.active and item.attribute != "category"
            ][-1:]
        for item in targets:
            item.active = False
            item.superseded_by_turn = turn

    def record_ask(self, attribute: str | None) -> None:
        if attribute:
            self.asked_attributes.append(attribute)

    def active_constraints(self) -> list[Constraint]:
        return [item for item in self.constraints if item.active]

    def active_terms(self, limit: int = 80) -> list[str]:
        ordered = sorted(
            self.active_constraints(),
            key=lambda item: (item.attribute != "category", item.hardness != "hard", item.source_turn),
        )
        return terms(" ".join(item.value for item in ordered), limit=limit)

    def history_terms(self, limit: int = 80) -> list[str]:
        return terms(" ".join(self.raw_messages), limit=limit)

    def fingerprint(self) -> tuple[str, ...]:
        return tuple(
            f"{item.attribute}:{item.value.lower()}:{item.hardness}"
            for item in self.active_constraints()
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "constraints": [asdict(item) for item in self.constraints],
            "asked_attributes": list(self.asked_attributes),
            "closed_attributes": sorted(self.closed_attributes),
            "last_update_kind": self.last_update_kind,
        }
