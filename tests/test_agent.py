from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from submission.agent import Agent
from tests.helpers import write_catalog


ALLOWED = {"category", "material", "color", "size", "style", "brand", "budget", "feature", "use_case", "other", None}


class AgentContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.temp.name) / "catalog.jsonl"
        write_catalog(cls.catalog, 35)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def make_agent(self, **kwargs: object) -> Agent:
        return Agent(self.catalog, **kwargs)

    def test_contract_shape_and_types(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("s", {"preference_tags": ["fit"]})
        response = agent.respond("s", "I'm looking for test shoes, but I'm still exploring.", 1, 10)
        self.assertEqual(set(response), {"message", "ask_attribute", "recommendations", "usage"})
        self.assertIsInstance(response["message"], str)
        self.assertIn(response["ask_attribute"], ALLOWED)
        self.assertLessEqual(len(response["recommendations"]), 10)
        self.assertTrue(all(set(item) == {"parent_asin"} for item in response["recommendations"]))
        self.assertEqual(response["usage"], {"prompt_tokens": 0, "completion_tokens": 0})

    def test_reset_required(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        with self.assertRaisesRegex(RuntimeError, "reset"):
            agent.respond("missing", "shoe", 1, 10)

    def test_invalid_reset_inputs(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        with self.assertRaises(ValueError):
            agent.reset("", {})
        with self.assertRaises(TypeError):
            agent.reset("s", [])  # type: ignore[arg-type]

    def test_top_k_and_turn_are_clamped_safely(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("s", {})
        response = agent.respond("s", "shoe", 99, 100)
        self.assertLessEqual(len(response["recommendations"]), 10)
        self.assertIsNone(response["ask_attribute"])

    def test_non_string_and_unicode_messages_are_safe(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("s", {})
        first = agent.respond("s", None, 1, 10)  # type: ignore[arg-type]
        second = agent.respond("s", "蓝色 👟 ' OR MATCH *", 2, 10)
        self.assertTrue(first["recommendations"])
        self.assertIsInstance(second["recommendations"], list)

    def test_reset_clears_pagination_and_state(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("s", {})
        first = agent.respond("s", "shoe", 1, 10)
        second = agent.respond("s", "shoe", 2, 10)
        self.assertNotEqual(first["recommendations"], second["recommendations"])
        agent.reset("s", {})
        after_reset = agent.respond("s", "shoe", 1, 10)
        self.assertEqual(first["recommendations"], after_reset["recommendations"])

    def test_sessions_are_isolated_and_deterministic(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("a", {"summary": "private A"})
        agent.reset("b", {"summary": "private B"})
        a = agent.respond("a", "cotton shoe", 1, 10)
        b = agent.respond("b", "cotton shoe", 1, 10)
        self.assertEqual(a["recommendations"], b["recommendations"])
        self.assertNotIn("private A", json.dumps(agent.get_trace("b")))

    def test_max_session_limit_evicts_oldest(self) -> None:
        agent = self.make_agent(max_sessions=2)
        self.addCleanup(agent.close)
        agent.reset("a", {})
        agent.reset("b", {})
        agent.reset("c", {})
        with self.assertRaises(RuntimeError):
            agent.respond("a", "shoe", 1, 10)
        self.assertTrue(agent.respond("c", "shoe", 1, 10)["recommendations"])

    def test_retrieval_failure_uses_bounded_fallback_and_records_error(self) -> None:
        agent = self.make_agent()
        self.addCleanup(agent.close)
        agent.reset("s", {})
        original = agent.retrieval.search
        agent.retrieval.search = lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("injected"))  # type: ignore[method-assign]
        try:
            response = agent.respond("s", "shoe", 1, 10)
        finally:
            agent.retrieval.search = original  # type: ignore[method-assign]
        self.assertEqual(len(response["recommendations"]), 10)
        trace = agent.get_trace("s")[-1]
        self.assertTrue(trace["retrieval"]["fallback"])
        self.assertIn("TimeoutError", trace["error"])

    def test_trace_file_is_session_scoped_ndjson(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(trace_dir=directory)
            self.addCleanup(agent.close)
            agent.reset("unsafe/session", {})
            agent.respond("unsafe/session", "shoe", 1, 10)
            paths = list(Path(directory).glob("*.ndjson"))
            self.assertEqual(len(paths), 1)
            event = json.loads(paths[0].read_text(encoding="utf-8").strip())
            self.assertEqual(event["turn"], 1)

    def test_adaptive_mode_uses_concrete_nonrepeating_questions(self) -> None:
        agent = self.make_agent(policy_mode="adaptive")
        self.addCleanup(agent.close)
        agent.reset("s", {})
        first = agent.respond("s", "I'm looking for test shoes, but I'm still exploring.", 1, 10)
        reply = f"I don't have a preference for {first['ask_attribute']}; please use your judgment."
        second = agent.respond("s", reply, 2, 10)
        self.assertNotEqual(first["ask_attribute"], second["ask_attribute"])


if __name__ == "__main__":
    unittest.main()
