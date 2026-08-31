from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from submission.text import terms


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {item}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


class WeakBM25Agent:
    """Frozen equivalent of the official stateless weak starter."""

    def __init__(self, catalog_path: str | Path = "data/catalog.jsonl") -> None:
        self.connection = sqlite3.connect(":memory:")
        self.sessions: set[str] = set()
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE VIRTUAL TABLE products USING fts5("
            "parent_asin UNINDEXED, title, categories, features, details, store, description, "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        batch = []
        with Path(catalog_path).open(encoding="utf-8") as handle:
            for line in handle:
                product = json.loads(line)
                batch.append((
                    str(product["parent_asin"]), _text(product.get("title")),
                    _text(product.get("categories")), _text(product.get("features")),
                    _text(product.get("details")), _text(product.get("store")),
                    _text(product.get("description")),
                ))
                if len(batch) >= 1000:
                    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()
        if batch:
            cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", batch)
        self.connection.commit()

    def reset(self, session_id: str, user_profile: dict) -> None:
        self.sessions.add(session_id)

    def respond(self, session_id: str, user_message: str, turn: int, top_k: int) -> dict:
        if session_id not in self.sessions:
            raise RuntimeError("reset must be called before respond")
        values = terms(user_message, limit=40)
        expression = " OR ".join(f'"{value}"' for value in values)
        rows = [] if not expression else self.connection.execute(
            "SELECT parent_asin FROM products WHERE products MATCH ? "
            "ORDER BY bm25(products, 0.0, 6.0, 4.0, 2.5, 2.5, 1.5, 1.0) LIMIT ?",
            (expression, top_k),
        ).fetchall()
        return {
            "message": "Here are the closest matches I found.",
            "ask_attribute": None,
            "recommendations": [{"parent_asin": str(row[0])} for row in rows],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
