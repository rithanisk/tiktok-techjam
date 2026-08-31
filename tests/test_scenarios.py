from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from submission.agent import Agent
from tests.helpers import write_catalog


class ScenarioBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.catalog = Path(cls.temp.name) / "catalog.jsonl"
        write_catalog(cls.catalog, 35)
        cls.agent = Agent(cls.catalog, policy_mode="adaptive")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.agent.close()
        cls.temp.cleanup()

    def test_buying_route_and_hard_constraint(self) -> None:
        self.agent.reset("buy", {})
        self.agent.respond("buy", "I'm looking for Test Shoes. A key requirement is: leather.", 1, 10)
        event = self.agent.get_trace("buy")[-1]
        self.assertEqual(event["route"], "buying")
        self.assertTrue(any(item["hardness"] == "hard" for item in event["ledger"]["constraints"]))

    def test_browsing_route(self) -> None:
        self.agent.reset("browse", {})
        self.agent.respond("browse", "I'm looking for Test Shoes, but I'm still exploring.", 1, 10)
        self.assertEqual(self.agent.get_trace("browse")[-1]["route"], "browsing")

    def test_intent_override_tombstones_old_slot_and_resets_novelty(self) -> None:
        self.agent.reset("override", {})
        self.agent.respond("override", "I'm looking for Test Shoes. I prefer red relaxed fit.", 1, 10)
        self.agent.respond("override", "I don't have an additional preference for budget.", 2, 10)
        response = self.agent.respond(
            "override",
            "Actually, ignore my earlier preference. What I need is: black leather.",
            3,
            10,
        )
        event = self.agent.get_trace("override")[-1]
        old = next(item for item in event["ledger"]["constraints"] if "red relaxed" in item["value"].lower())
        self.assertFalse(old["active"])
        active_values = [
            item["value"].lower()
            for item in event["ledger"]["constraints"] if item["active"]
        ]
        self.assertFalse(any("red relaxed" in value for value in active_values))
        self.assertTrue(event["retrieval"]["query_changed"])
        self.assertTrue(response["recommendations"])

    def test_boundary_no_preference_is_not_repeated(self) -> None:
        self.agent.reset("boundary", {})
        first = self.agent.respond("boundary", "I'm looking for Test Shoes, but I'm still exploring.", 1, 10)
        attribute = first["ask_attribute"]
        second = self.agent.respond(
            "boundary",
            f"I don't have a preference for {attribute}; please use your judgment.",
            2,
            10,
        )
        event = self.agent.get_trace("boundary")[-1]
        self.assertIn(attribute, event["ledger"]["closed_attributes"])
        self.assertNotEqual(attribute, second["ask_attribute"])

    def test_repeated_no_new_information_explores_new_results(self) -> None:
        self.agent.reset("stall", {})
        first = self.agent.respond("stall", "shoe", 1, 10)
        second = self.agent.respond("stall", "Those options are not quite right yet. Ask me about one specific attribute.", 2, 10)
        self.assertNotEqual(first["recommendations"], second["recommendations"])


if __name__ == "__main__":
    unittest.main()
