from __future__ import annotations

import json
from pathlib import Path


def product(index: int, **overrides: object) -> dict:
    materials = ("cotton", "leather", "wool", "nylon")
    colors = ("blue", "black", "red", "green")
    row = {
        "parent_asin": f"A{index:03d}",
        "title": f"{colors[index % 4]} test shoe model {index}",
        "features": [f"unique-feature-{index}", materials[index % 4], "comfortable fit"],
        "details": {"Department": "unisex", "Fit Type": "regular" if index % 2 else "relaxed"},
        "description": [f"catalog item {index} for running and walking"],
        "categories": ["Clothing", "Shoes", "Test Shoes"],
        "store": f"Brand {index % 5}",
        "average_rating": 3.0 + (index % 20) / 10,
        "rating_number": index * 10,
        "price": 15.0 + index * 3,
    }
    row.update(overrides)
    return row


def write_catalog(path: Path, count: int = 30) -> list[dict]:
    rows = [product(index) for index in range(count)]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return rows
