from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIELD_WEIGHTS = (
    (0.0, 10.0, 5.0, 2.0, 2.0, 2.0, 1.0),
    (0.0, 2.0, 3.0, 7.0, 7.0, 2.0, 4.0),
    (0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0),
)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


@dataclass(frozen=True)
class SearchResult:
    ids: list[str]
    candidate_ids: list[str]
    scores: dict[str, float]
    page: int
    query_changed: bool
    view_count: int
    used_fallback: bool = False


class RetrievalPortfolio:
    """Three-view fielded FTS retrieval with deterministic fusion and novelty."""

    def __init__(
        self,
        catalog_path: str | Path,
        candidate_limit: int = 100,
        field_weights: tuple[tuple[float, ...], ...] = FIELD_WEIGHTS,
        enable_novelty: bool = True,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        if not self.catalog_path.exists():
            raise FileNotFoundError(
                f"Catalog not found at {self.catalog_path}. Run: python3 scripts/download_catalog.py"
            )
        self.candidate_limit = max(20, candidate_limit)
        if not field_weights:
            raise ValueError("at least one field-weight view is required")
        if any(len(weights) != 7 for weights in field_weights):
            raise ValueError("each field-weight view must contain seven values")
        self.field_weights = field_weights
        self.enable_novelty = enable_novelty
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._lock = threading.RLock()
        self.products: dict[str, dict[str, Any]] = {}
        self._page_state: dict[str, tuple[tuple[str, ...], int]] = {}
        self._popularity: list[str] = []
        self._build_index()

    def _build_index(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
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
                parent_asin = str(product["parent_asin"])
                self.products[parent_asin] = product
                popularity.append((
                    int(product.get("rating_number") or 0),
                    float(product.get("average_rating") or 0.0),
                    parent_asin,
                ))
                batch.append((
                    parent_asin,
                    _text(product.get("title")),
                    _text(product.get("categories")),
                    _text(product.get("features")),
                    _text(product.get("details")),
                    _text(product.get("store")),
                    _text(product.get("description")),
                ))
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()
        popularity.sort(key=lambda item: (-item[0], -item[1], item[2]))
        self._popularity = [item[2] for item in popularity]

    def reset_session(self, session_id: str) -> None:
        self._page_state.pop(session_id, None)

    def search(
        self,
        session_id: str,
        query_terms: list[str],
        fingerprint: tuple[str, ...],
        top_k: int = 10,
    ) -> SearchResult:
        top_k = max(1, min(int(top_k), 10))
        canonical = tuple(query_terms[:80]) or fingerprint
        previous = self._page_state.get(session_id)
        query_changed = previous is None or previous[0] != canonical
        page = 0 if query_changed or not self.enable_novelty else previous[1] + 1
        self._page_state[session_id] = (canonical, page)

        if not query_terms:
            ids = self._popularity[:top_k]
            return SearchResult(ids, self._popularity[:self.candidate_limit], {}, page, query_changed, 0, True)

        expression = " OR ".join(f'"{term}"' for term in query_terms[:80])
        scores: dict[str, float] = {}
        best_rank: dict[str, int] = {}
        with self._lock:
            for weights in self.field_weights:
                weight_sql = ", ".join(str(value) for value in weights)
                rows = self.connection.execute(
                    "SELECT parent_asin FROM products WHERE products MATCH ? "
                    f"ORDER BY bm25(products, {weight_sql}) LIMIT ?",
                    (expression, self.candidate_limit),
                ).fetchall()
                for rank, row in enumerate(rows, start=1):
                    parent_asin = str(row[0])
                    scores[parent_asin] = scores.get(parent_asin, 0.0) + 1.0 / (20 + rank)
                    best_rank[parent_asin] = min(best_rank.get(parent_asin, rank), rank)

        fused = sorted(scores, key=lambda value: (-scores[value], best_rank[value], value))
        offset = page * top_k
        ids = fused[offset:offset + top_k]
        if not ids and fused:
            page = 0
            self._page_state[session_id] = (canonical, page)
            ids = fused[:top_k]
        return SearchResult(ids, fused, scores, page, query_changed, len(self.field_weights))

    def product_rows(self, ids: list[str]) -> list[dict[str, Any]]:
        return [self.products[value] for value in ids if value in self.products]

    def fallback_ids(self, top_k: int = 10) -> list[str]:
        return self._popularity[:max(1, min(top_k, 10))]

    def close(self) -> None:
        with self._lock:
            self.connection.close()
