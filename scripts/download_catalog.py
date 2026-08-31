from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import urllib.request
from pathlib import Path


URL = "https://github.com/TechJam2026/techjam-conversational-search/releases/download/participant-kit/catalog.jsonl.gz"
EXPECTED_SHA256 = "07fd142631fd6b03e2b4d09988c3eb7d53720e9d57010c79db48eeaada50a8f8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_catalog(path: Path, expected_rows: int = 50_000) -> int:
    if not path.is_file():
        raise ValueError(f"Catalog is not a regular file: {path}")
    with path.open(encoding="utf-8") as handle:
        rows = sum(1 for line in handle if line.strip())
    if rows != expected_rows:
        raise ValueError(f"Expected {expected_rows:,} products, found {rows:,}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify the official 50k-product catalog")
    parser.add_argument("--output", default="data/catalog.jsonl")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    archive = output.with_suffix(output.suffix + ".gz")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        try:
            rows = validate_catalog(output)
        except ValueError as exc:
            raise SystemExit(f"Existing catalog failed validation: {exc}") from exc
        print(f"Catalog already exists and contains {rows:,} products: {output}")
        return
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, archive)
    actual = sha256(archive)
    if actual != EXPECTED_SHA256:
        archive.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 mismatch: expected {EXPECTED_SHA256}, received {actual}")
    with gzip.open(archive, "rb") as source, output.open("wb") as destination:
        shutil.copyfileobj(source, destination)
    archive.unlink(missing_ok=True)
    try:
        rows = validate_catalog(output)
    except ValueError as exc:
        output.unlink(missing_ok=True)
        raise SystemExit(str(exc)) from exc
    print(f"Verified {rows:,} products at {output}")


if __name__ == "__main__":
    main()
