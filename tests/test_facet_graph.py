from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from submission.facet_agent import FacetGraphAgent, HybridFacetAgent
from submission.facet_graph import FacetGraphIndex
from submission.state import Constraint


def product(
    product_id: str,
    category: str,
    features: list[str],
    store: str,
    price: float,
    popularity: int,
) -> dict:
    return {
        "parent_asin": product_id,
        "title": f"{store} {category}",
        "features": features,
        "description": [],
        "price": price,
        "categories": ["Clothing", category],
        "details": {"Department": "unisex"},
        "average_rating": 4.5,
        "rating_number": popularity,
        "store": store,
    }


class FacetGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.tempdir.name) / "catalog.jsonl"
        rows = [
            product("p1", "Running Shoes", ["cotton", "red", "trail running"], "Acme", 40, 20),
            product("p2", "Running Shoes", ["nylon", "blue", "road running"], "Beta", 70, 30),
            product("p3", "Sun Hats", ["cotton", "red", "wide brim"], "Acme", 20, 10),
            {
                **product("p4", "Leggings", ["polyester", "red"], "Gamma", 35, 5),
                "categories": ["Clothing", "Women", "Bottoms", "Leggings"],
            },
        ]
        rows.extend(
            product(f"bulk{i:02d}", "Socks", ["cotton", "casual"], f"Brand {i % 4}", 10 + i, i)
            for i in range(15)
        )
        cls.catalog.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def setUp(self) -> None:
        self.index = FacetGraphIndex(self.catalog, oversized_limit=11, max_relaxations=2)

    def tearDown(self) -> None:
        self.index.close()

    def constraint(self, value: str, attribute: str, hardness: str = "hard", confidence: float = 1.0) -> Constraint:
        return Constraint(value, attribute, hardness, "positive", 1, confidence)

    def test_explicit_facets_use_posting_intersection(self) -> None:
        result = self.index.search(
            "s",
            [self.constraint("Running Shoes", "category"), self.constraint("cotton", "material")],
            ("category:running shoes", "material:cotton"),
        )
        self.assertEqual(result.ids, ["p1"])
        self.assertEqual(result.strict_candidate_count, 1)
        self.assertEqual(result.intersection_order[0], "category")
        self.assertFalse(result.relaxations)

    def test_postings_are_applied_in_selectivity_order(self) -> None:
        clauses = [
            self.index.resolve_constraint(self.constraint("cotton", "feature")),
            self.index.resolve_constraint(self.constraint("Running Shoes", "category")),
        ]
        expected = [item.attribute for item in sorted(clauses, key=lambda item: (len(item.ids), item.attribute, item.value))]
        result = self.index.search("s", [
            self.constraint("cotton", "feature"),
            self.constraint("Running Shoes", "category"),
        ], ("x",))
        self.assertEqual(result.intersection_order, expected)

    def test_contradiction_uses_bounded_logged_relaxation(self) -> None:
        result = self.index.search(
            "s",
            [
                self.constraint("Running Shoes", "category"),
                self.constraint("Sun Hats", "feature", hardness="soft", confidence=0.5),
            ],
            ("contradiction",),
        )
        self.assertEqual(set(result.ids), {"p1", "p2"})
        self.assertEqual(len(result.relaxations), 1)
        self.assertEqual(result.relaxations[0].attribute, "feature")
        self.assertEqual(result.relaxations[0].reason, "empty_conjunction")
        self.assertGreater(result.relaxations[0].after_count, 0)

    def test_relaxation_count_is_bounded(self) -> None:
        limited = FacetGraphIndex(self.catalog, max_relaxations=0)
        try:
            result = limited.search("s", [
                self.constraint("Running Shoes", "category"),
                self.constraint("Sun Hats", "feature", hardness="soft"),
            ], ("none",))
            self.assertEqual(result.relaxations, [])
        finally:
            limited.close()

    def test_numeric_budget_is_a_real_filter(self) -> None:
        clause = self.index.resolve_constraint(self.constraint("budget under $50", "budget"))
        self.assertEqual(clause.resolution, "numeric_ceiling")
        self.assertIn("p1", clause.ids)
        self.assertNotIn("p2", clause.ids)

    def test_category_tokens_need_not_be_adjacent(self) -> None:
        clause = self.index.resolve_constraint(self.constraint("Women Leggings", "category"))
        self.assertEqual(clause.resolution, "category_all_terms")
        self.assertIn("p4", clause.ids)

    def test_labeled_color_is_canonicalized_to_the_color_value(self) -> None:
        clause = self.index.resolve_constraint(self.constraint("color: red", "color"))
        self.assertIn("p4", clause.ids)
        self.assertIn("p1", clause.ids)

    def test_oversized_pool_produces_catalog_grounded_entropy_question(self) -> None:
        result = self.index.search("s", [self.constraint("Socks", "category")], ("socks",))
        self.assertTrue(result.oversized)
        decision = self.index.clarification(result.candidate_ids)
        self.assertIsNotNone(decision.attribute)
        self.assertGreater(decision.information_gain_bits, 0)
        self.assertGreater(decision.candidate_entropy_bits, 0)
        self.assertLess(decision.expected_remaining_candidates, len(result.candidate_ids))
        self.assertTrue(decision.top_values)
        for value in decision.top_values:
            self.assertIn(value, decision.question)
        self.assertEqual(decision.curve[0]["stage"], "before")

    def test_information_bound_is_computable_and_nonnegative(self) -> None:
        decision = self.index.clarification(list(self.index.products))
        self.assertGreaterEqual(decision.lower_bound_turns, 0)
        self.assertGreaterEqual(decision.unresolved_fraction, 0)
        self.assertLessEqual(decision.unresolved_fraction, 1)
        if decision.greedy_expected_turns is not None:
            self.assertGreaterEqual(decision.greedy_expected_turns, 1)

    def test_pagination_is_deterministic_and_resets_on_changed_slots(self) -> None:
        constraint = self.constraint("Socks", "category")
        first = self.index.search("s", [constraint], ("socks",), 3)
        second = self.index.search("s", [constraint], ("socks",), 3)
        changed = self.index.search("s", [constraint], ("changed",), 3)
        self.assertFalse(set(first.ids) & set(second.ids))
        self.assertEqual(changed.ids, first.ids)


class FacetGraphAgentTest(unittest.TestCase):
    def test_agent_contract_and_trace_include_proof_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "catalog.jsonl"
            rows = [
                product(f"p{i}", "Socks", ["cotton", "casual"], f"Brand {i % 3}", 20, i)
                for i in range(15)
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            agent = FacetGraphAgent(path, question_mode="entropy", oversized_limit=11)
            try:
                agent.reset("session", {})
                response = agent.respond("session", "I'm looking for Socks.", 1, 10)
                self.assertLessEqual(len(response["recommendations"]), 10)
                self.assertIn(response["ask_attribute"], {
                    "material", "color", "size", "style", "budget", "use_case", "brand", None,
                })
                trace = agent.get_trace("session")[0]
                self.assertIn("intersection_order", trace)
                self.assertIn("clarification", trace)
                self.assertIn("latency_ms", trace)
            finally:
                agent.close()

    def test_hybrid_uses_only_small_unrelaxed_intersections(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "catalog.jsonl"
            rows = [
                product("exact", "Running Shoes", ["cotton", "red"], "Exact", 20, 1),
                product("other", "Sun Hats", ["nylon", "blue"], "Other", 30, 999),
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            agent = HybridFacetAgent(path)
            try:
                agent.reset("session", {})
                response = agent.respond(
                    "session",
                    "I'm looking for Running Shoes. A key requirement is: cotton.",
                    1,
                    10,
                )
                self.assertEqual(response["recommendations"], [{"parent_asin": "exact"}])
                self.assertEqual(agent.decisions["session"][0]["source"], "facet_graph")
                trace = agent.get_trace("session")
                self.assertEqual(trace[0]["hybrid"]["source"], "facet_graph")
                self.assertIsNotNone(trace[0]["portfolio"])
                self.assertIsNotNone(trace[0]["facet"])
            finally:
                agent.close()

    def test_hybrid_decision_state_is_lru_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "catalog.jsonl"
            path.write_text(json.dumps(product("p1", "Socks", ["cotton"], "Acme", 20, 1)) + "\n")
            agent = HybridFacetAgent(path, max_sessions=2)
            try:
                for session_id in ("one", "two", "three"):
                    agent.reset(session_id, {})
                self.assertEqual(list(agent.decisions), ["two", "three"])
            finally:
                agent.close()

    def test_hybrid_falls_back_to_portfolio_if_facet_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "catalog.jsonl"
            path.write_text(json.dumps(product("p1", "Socks", ["cotton"], "Acme", 20, 1)) + "\n")
            agent = HybridFacetAgent(path)
            try:
                agent.reset("session", {})
                agent.facets.respond = lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("injected"))
                response = agent.respond("session", "I'm looking for Socks.", 1, 10)
                self.assertTrue(response["recommendations"])
                self.assertEqual(agent.decisions["session"][0]["source"], "progressive_portfolio")
                self.assertIn("TimeoutError", agent.decisions["session"][0]["facet_error"])
            finally:
                agent.close()


if __name__ == "__main__":
    unittest.main()
