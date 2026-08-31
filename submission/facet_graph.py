from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .state import Constraint
from .text import COLORS, MATERIALS, clean_value, terms


USE_CASES = ("running", "hiking", "winter", "outdoor", "work", "wedding", "casual", "gym")
SIZES = ("xxs", "xs", "small", "medium", "large", "xl", "xxl", "wide", "narrow")
STYLE_KEYS = ("fit type", "neck style", "sleeve type", "style", "department")
QUESTION_ATTRIBUTES = ("material", "color", "size", "style", "budget", "use_case", "brand")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
BUDGET_RE = re.compile(
    r"(?:budget(?:\s+(?:around|of))?|under|below|less\s+than|up\s+to|<=?)\s*\$?\s*(\d+(?:\.\d+)?)",
    re.I,
)


def _flatten(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _normalized_tokens(value: str, limit: int = 24) -> list[str]:
    return terms(clean_value(value), limit=limit)


@dataclass(frozen=True)
class FacetClause:
    attribute: str
    value: str
    hardness: str
    confidence: float
    ids: frozenset[str]
    resolution: str


@dataclass(frozen=True)
class RelaxationEvent:
    step: int
    attribute: str
    value: str
    hardness: str
    reason: str
    before_count: int
    after_count: int


@dataclass(frozen=True)
class FacetSearchResult:
    ids: list[str]
    candidate_ids: list[str]
    strict_candidate_count: int
    oversized: bool
    clauses: list[FacetClause]
    intersection_order: list[str]
    applied_attributes: list[str]
    relaxations: list[RelaxationEvent]
    page: int
    query_changed: bool


@dataclass(frozen=True)
class EntropyDecision:
    attribute: str | None
    question: str
    information_gain_bits: float
    candidate_entropy_bits: float
    expected_remaining_candidates: float
    lower_bound_turns: float
    greedy_expected_turns: float | None
    unresolved_fraction: float
    top_values: tuple[str, ...]
    curve: tuple[dict[str, float | str], ...]


class FacetGraphIndex:
    """Deterministic posting-list retrieval and catalog-grounded clarification.

    Every constraint resolves to an explicit posting list. Lists are intersected
    from most selective to least selective. No learned score, embedding, fusion,
    or routing threshold participates in candidate membership.
    """

    def __init__(
        self,
        catalog_path: str | Path,
        oversized_limit: int = 80,
        max_relaxations: int = 3,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog not found at {self.catalog_path}")
        self.oversized_limit = max(11, int(oversized_limit))
        self.max_relaxations = max(0, int(max_relaxations))
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.RLock()
        self.products: dict[str, dict[str, Any]] = {}
        self.product_facets: dict[str, dict[str, str]] = {}
        self._all_ids: frozenset[str] = frozenset()
        self._popularity: list[str] = []
        self._page_state: dict[str, tuple[tuple[str, ...], int]] = {}
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE catalog USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch: list[tuple[str, str, str, str, str, str, str]] = []
        popularity: list[tuple[int, float, str]] = []
        with self.catalog_path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                product = json.loads(line)
                product_id = str(product["parent_asin"])
                self.products[product_id] = product
                popularity.append((
                    int(product.get("rating_number") or 0),
                    float(product.get("average_rating") or 0.0),
                    product_id,
                ))
                batch.append((
                    product_id,
                    _flatten(product.get("title")),
                    _flatten(product.get("categories")),
                    _flatten(product.get("features")),
                    _flatten(product.get("details")),
                    _flatten(product.get("store")),
                    _flatten(product.get("description")),
                ))
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO catalog VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO catalog VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()
        popularity.sort(key=lambda item: (-item[0], -item[1], item[2]))
        self._popularity = [item[2] for item in popularity]
        self._all_ids = frozenset(self.products)

    def _extract_facets(self, product: dict[str, Any], searchable: str) -> dict[str, str]:
        result: dict[str, str] = {}
        material = next((value for value in MATERIALS if re.search(rf"\b{re.escape(value)}\b", searchable)), "")
        color = next((value for value in COLORS if re.search(rf"\b{re.escape(value)}\b", searchable)), "")
        use_case = next((value for value in USE_CASES if re.search(rf"\b{re.escape(value)}\b", searchable)), "")
        size = next((value for value in SIZES if re.search(rf"\b{re.escape(value)}\b", searchable)), "")
        if material:
            result["material"] = material
        if color:
            result["color"] = color
        if use_case:
            result["use_case"] = use_case
        if size:
            result["size"] = size
        store = clean_value(str(product.get("store") or "")).lower()
        if store:
            result["brand"] = store
        price = product.get("price")
        if isinstance(price, (int, float)):
            result["budget"] = (
                "under $25" if price < 25 else "$25–$50" if price < 50
                else "$50–$100" if price < 100 else "$100+"
            )
        details = product.get("details") or {}
        if isinstance(details, dict):
            style = " ".join(
                clean_value(str(value)).lower()
                for key, value in details.items()
                if str(key).lower() in STYLE_KEYS and value not in (None, "")
            )
            if style:
                result["style"] = style[:80]
        return result

    def reset_session(self, session_id: str) -> None:
        self._page_state.pop(session_id, None)

    def _fts_ids(self, expression: str) -> frozenset[str]:
        try:
            with self._lock:
                rows = self.connection.execute(
                    "SELECT parent_asin FROM catalog WHERE catalog MATCH ?",
                    (expression,),
                ).fetchall()
        except sqlite3.OperationalError:
            return frozenset()
        return frozenset(str(row[0]) for row in rows)

    def _phrase_expression(self, tokens_: list[str], column: str | None = None) -> str:
        phrase = " ".join(token.replace('"', "") for token in tokens_)
        quoted = f'"{phrase}"'
        return f"{column}:{quoted}" if column else quoted

    def resolve_constraint(self, constraint: Constraint) -> FacetClause:
        value = clean_value(constraint.value)
        attribute = constraint.attribute
        tokens_ = _normalized_tokens(value)
        if attribute == "budget":
            match = BUDGET_RE.search(value)
            if match:
                ceiling = float(match.group(1))
                ids = frozenset(
                    product_id for product_id, product in self.products.items()
                    if isinstance(product.get("price"), (int, float)) and float(product["price"]) <= ceiling
                )
                return FacetClause(attribute, value, constraint.hardness, constraint.confidence, ids, "numeric_ceiling")

        column = {"category": "categories", "brand": "store"}.get(attribute)

        # Slot labels are not facet values. The simulator may say ``color: red``
        # while the catalog contains only ``red``; canonicalize controlled
        # vocabularies before resolving their posting lists.
        if attribute == "color":
            canonical = [color for color in COLORS if color in tokens_]
            if canonical:
                tokens_ = canonical
        elif attribute == "material":
            canonical = [material for material in MATERIALS if material in tokens_]
            if len(tokens_) <= 2 and canonical:
                tokens_ = canonical

        # Category paths contain intervening hierarchy nodes (for example,
        # ``Women / Clothing / Leggings``). Requiring an adjacent phrase would
        # create false precision, so category semantics are an AND of tokens in
        # the category column.
        if attribute == "category" and tokens_:
            term_lists = [self._fts_ids(self._phrase_expression([token], column)) for token in tokens_]
            term_lists = [values for values in term_lists if values]
            ids = set.intersection(*(set(values) for values in term_lists)) if term_lists else set()
            return FacetClause(
                attribute, value, constraint.hardness, constraint.confidence,
                frozenset(ids), "category_all_terms" if ids else "unresolved",
            )

        phrase_ids = self._fts_ids(self._phrase_expression(tokens_, column)) if tokens_ else frozenset()
        if phrase_ids:
            return FacetClause(attribute, value, constraint.hardness, constraint.confidence, phrase_ids, "exact_phrase")

        # Deterministic lexical back-off: intersect every meaningful term. This
        # still resolves through posting lists; it does not introduce a ranker.
        term_lists = [self._fts_ids(self._phrase_expression([token], column)) for token in tokens_]
        term_lists = [values for values in term_lists if values]
        ids = set.intersection(*(set(values) for values in term_lists)) if term_lists else set()
        return FacetClause(
            attribute, value, constraint.hardness, constraint.confidence,
            frozenset(ids), "all_terms" if ids else "unresolved",
        )

    def _intersection(self, clauses: Iterable[FacetClause]) -> set[str]:
        ordered = sorted(clauses, key=lambda item: (len(item.ids), item.attribute, item.value.lower()))
        if not ordered:
            return set(self._all_ids)
        result = set(ordered[0].ids)
        for clause in ordered[1:]:
            result.intersection_update(clause.ids)
            if not result:
                break
        return result

    def search(
        self,
        session_id: str,
        constraints: list[Constraint],
        fingerprint: tuple[str, ...],
        top_k: int = 10,
    ) -> FacetSearchResult:
        top_k = max(1, min(int(top_k), 10))
        clauses = [self.resolve_constraint(item) for item in constraints]
        usable = [item for item in clauses if item.ids]
        strict = self._intersection(usable) if usable else set(self._all_ids)
        candidates = set(strict)
        active = list(usable)
        relaxations: list[RelaxationEvent] = []

        # Relax only when strict conjunction fails. Soft/low-confidence clauses
        # are removed before hard clauses; every step is bounded and auditable.
        removal_order = sorted(
            usable,
            key=lambda item: (
                item.hardness == "hard",
                item.confidence,
                -len(item.ids),
                item.attribute,
            ),
        )
        for clause in removal_order[: self.max_relaxations]:
            if candidates:
                break
            before = len(candidates)
            active.remove(clause)
            candidates = self._intersection(active) if active else set(self._all_ids)
            relaxations.append(RelaxationEvent(
                len(relaxations) + 1,
                clause.attribute,
                clause.value,
                clause.hardness,
                "empty_conjunction",
                before,
                len(candidates),
            ))

        canonical = fingerprint or tuple(f"{item.attribute}:{item.value.lower()}" for item in constraints)
        previous = self._page_state.get(session_id)
        changed = previous is None or previous[0] != canonical
        page = 0 if changed else previous[1] + 1
        self._page_state[session_id] = (canonical, page)

        candidate_set = candidates or set(self._all_ids)
        # Popularity is precomputed once. Selecting from it is a deterministic
        # bounded pass and avoids scoring/sorting a large live candidate pool.
        ordered_ids = [product_id for product_id in self._popularity if product_id in candidate_set]
        offset = page * top_k
        ids = ordered_ids[offset:offset + top_k]
        if not ids and ordered_ids:
            page = 0
            self._page_state[session_id] = (canonical, page)
            ids = ordered_ids[:top_k]
        return FacetSearchResult(
            ids=ids,
            candidate_ids=ordered_ids,
            strict_candidate_count=len(strict),
            oversized=len(candidate_set) > self.oversized_limit,
            clauses=clauses,
            intersection_order=[
                item.attribute
                for item in sorted(active, key=lambda item: (len(item.ids), item.attribute, item.value.lower()))
            ],
            applied_attributes=[item.attribute for item in active],
            relaxations=relaxations,
            page=page,
            query_changed=changed,
        )

    def facet_distribution(self, candidate_ids: Iterable[str], attribute: str) -> Counter[str]:
        return Counter(
            self._facets_for(product_id).get(attribute, "unknown")
            for product_id in candidate_ids
        )

    def _facets_for(self, product_id: str) -> dict[str, str]:
        cached = self.product_facets.get(product_id)
        if cached is not None:
            return cached
        product = self.products.get(product_id, {})
        searchable = " ".join(
            _flatten(product.get(field))
            for field in ("title", "categories", "features", "details", "store", "description")
        ).lower()
        facets = self._extract_facets(product, searchable)
        self.product_facets[product_id] = facets
        return facets

    @staticmethod
    def entropy(counts: Counter[str]) -> float:
        total = sum(counts.values())
        if total <= 1:
            return 0.0
        return -sum((count / total) * math.log2(count / total) for count in counts.values() if count)

    def clarification(
        self,
        candidate_ids: list[str],
        excluded_attributes: set[str] | None = None,
        top_k: int = 10,
    ) -> EntropyDecision:
        excluded = excluded_attributes or set()
        pool = candidate_ids[:5000]
        base_entropy = math.log2(max(1, len(pool)))
        scored: list[tuple[float, str, Counter[str]]] = []
        for attribute in QUESTION_ATTRIBUTES:
            if attribute in excluded:
                continue
            counts = self.facet_distribution(pool, attribute)
            gain = self.entropy(counts)
            if len(counts) > 1 and gain > 0:
                scored.append((gain, attribute, counts))
        if not scored:
            return EntropyDecision(None, "", 0.0, base_entropy, float(len(pool)), math.inf, None, 1.0, (), ())

        gain, attribute, counts = max(scored, key=lambda item: (item[0], item[1]))
        total = max(1, sum(counts.values()))
        expected_remaining = sum(count * count for count in counts.values()) / total
        max_outcomes = max(
            len(self.facet_distribution(pool, candidate))
            for candidate in QUESTION_ATTRIBUTES
            if candidate not in excluded
        )
        lower_bound = (
            max(0.0, math.log(max(1, len(pool) / max(1, top_k)), max_outcomes))
            if max_outcomes > 1 else math.inf
        )
        top_values = tuple(value for value, _ in counts.most_common(3) if value != "unknown")
        choices = ", ".join(top_values)
        question = (
            f"Which {attribute.replace('_', ' ')} best fits—{choices}?"
            if choices else f"Which {attribute.replace('_', ' ')} should I use to narrow these matches?"
        )
        curve = (
            {"stage": "before", "candidates": float(len(pool)), "entropy_bits": round(base_entropy, 6)},
            {
                "stage": f"after_{attribute}",
                "candidates": round(expected_remaining, 6),
                "entropy_bits": round(max(0.0, base_entropy - gain), 6),
            },
        )
        greedy_depth, unresolved = self._greedy_tree_depth(pool, tuple(
            candidate for candidate in QUESTION_ATTRIBUTES if candidate not in excluded
        ), top_k)
        return EntropyDecision(
            attribute,
            question,
            round(gain, 6),
            round(base_entropy, 6),
            round(expected_remaining, 6),
            round(lower_bound, 6),
            None if math.isinf(greedy_depth) else round(greedy_depth, 6),
            round(unresolved / max(1, len(pool)), 6),
            top_values,
            curve,
        )

    def _greedy_tree_depth(
        self,
        candidate_ids: list[str],
        attributes: tuple[str, ...],
        top_k: int,
    ) -> tuple[float, int]:
        """Return exact expected depth of this finite greedy tree.

        The value is a valid upper bound for this constructed policy only when
        ``unresolved == 0``. It is deliberately not presented as proof that ID3
        is globally near-optimal for arbitrary shoppers.
        """
        if len(candidate_ids) <= top_k:
            return 0.0, 0
        if not attributes:
            return math.inf, len(candidate_ids)
        choices: list[tuple[float, str, dict[str, list[str]]]] = []
        for attribute in attributes:
            groups: dict[str, list[str]] = {}
            for product_id in candidate_ids:
                value = self._facets_for(product_id).get(attribute, "unknown")
                groups.setdefault(value, []).append(product_id)
            entropy = self.entropy(Counter({key: len(value) for key, value in groups.items()}))
            if len(groups) > 1:
                choices.append((entropy, attribute, groups))
        if not choices:
            return math.inf, len(candidate_ids)
        _, chosen, groups = max(choices, key=lambda item: (item[0], item[1]))
        remaining = tuple(value for value in attributes if value != chosen)
        expected = 1.0
        unresolved = 0
        for group in groups.values():
            depth, group_unresolved = self._greedy_tree_depth(group, remaining, top_k)
            unresolved += group_unresolved
            if not math.isinf(depth):
                expected += (len(group) / len(candidate_ids)) * depth
        return (math.inf if unresolved else expected), unresolved

    def product_rows(self, ids: list[str]) -> list[dict[str, Any]]:
        return [self.products[value] for value in ids if value in self.products]

    def close(self) -> None:
        with self._lock:
            self.connection.close()
