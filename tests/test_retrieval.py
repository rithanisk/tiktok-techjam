from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from submission.retrieval import FIELD_WEIGHTS, RetrievalPortfolio
from tests.helpers import write_catalog


class RetrievalPortfolioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.temp.name) / "catalog.jsonl"
        write_catalog(cls.catalog, 35)
        cls.index = RetrievalPortfolio(cls.catalog, candidate_limit=35)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.index.close()
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.index.reset_session(self.id())

    def test_three_views_are_configured(self) -> None:
        self.assertEqual(len(FIELD_WEIGHTS), 3)

    def test_search_returns_valid_unique_ids(self) -> None:
        result = self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        self.assertEqual(len(result.ids), 10)
        self.assertEqual(len(result.ids), len(set(result.ids)))
        self.assertTrue(all(value in self.index.products for value in result.ids))
        self.assertEqual(result.view_count, 3)

    def test_same_query_advances_to_unseen_page(self) -> None:
        first = self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        second = self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        self.assertEqual(first.page, 0)
        self.assertEqual(second.page, 1)
        self.assertFalse(set(first.ids) & set(second.ids))

    def test_changed_query_resets_page(self) -> None:
        self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        second = self.index.search(self.id(), ["cotton"], ("cotton",), 10)
        self.assertEqual(second.page, 0)
        self.assertTrue(second.query_changed)

    def test_reset_session_resets_page(self) -> None:
        self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        self.index.reset_session(self.id())
        result = self.index.search(self.id(), ["shoe"], ("shoe",), 10)
        self.assertEqual(result.page, 0)

    def test_empty_query_has_deterministic_popularity_fallback(self) -> None:
        result = self.index.search(self.id(), [], (), 10)
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.ids[0], "A034")
        self.assertEqual(len(result.ids), 10)

    def test_top_k_is_clamped_to_contract_limit(self) -> None:
        result = self.index.search(self.id(), ["shoe"], ("shoe",), 100)
        self.assertLessEqual(len(result.ids), 10)

    def test_product_rows_preserve_requested_order(self) -> None:
        rows = self.index.product_rows(["A003", "missing", "A001"])
        self.assertEqual([row["parent_asin"] for row in rows], ["A003", "A001"])

    def test_missing_catalog_has_actionable_error(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "download_catalog"):
            RetrievalPortfolio(Path(self.temp.name) / "missing.jsonl")

    def test_no_novelty_repeats_head_results(self) -> None:
        index = RetrievalPortfolio(self.catalog, candidate_limit=35, enable_novelty=False)
        self.addCleanup(index.close)
        first = index.search("no-novelty", ["shoe"], ("shoe",), 10)
        second = index.search("no-novelty", ["shoe"], ("shoe",), 10)
        self.assertEqual(first.ids, second.ids)
        self.assertEqual(second.page, 0)

    def test_invalid_view_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalPortfolio(self.catalog, field_weights=())
        with self.assertRaises(ValueError):
            RetrievalPortfolio(self.catalog, field_weights=((1.0, 2.0),))


if __name__ == "__main__":
    unittest.main()
