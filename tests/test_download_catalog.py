from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.download_catalog import sha256, validate_catalog


class DownloadCatalogTest(unittest.TestCase):
    def test_sha256_matches_standard_library_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.gz"
            payload = b"deterministic participant asset"
            path.write_bytes(payload)
            self.assertEqual(sha256(path), hashlib.sha256(payload).hexdigest())

    def test_validate_catalog_accepts_expected_nonempty_row_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.jsonl"
            path.write_text('{"parent_asin":"A"}\n\n{"parent_asin":"B"}\n', encoding="utf-8")
            self.assertEqual(validate_catalog(path, expected_rows=2), 2)

    def test_validate_catalog_rejects_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.jsonl"
            path.write_text('{"parent_asin":"A"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Expected 2 products"):
                validate_catalog(path, expected_rows=2)


if __name__ == "__main__":
    unittest.main()
