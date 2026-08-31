from __future__ import annotations

import unittest

from submission.policy import QuestionPolicy
from submission.state import IntentLedger
from tests.helpers import product


class QuestionPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [product(index) for index in range(12)]

    def test_competition_mode_uses_universal_channel(self) -> None:
        decision = QuestionPolicy("competition").decide(IntentLedger("s"), self.candidates, 1)
        self.assertEqual(decision.attribute, "other")
        self.assertEqual(decision.reason, "universal_constraint_channel")

    def test_turn_ten_does_not_waste_a_question(self) -> None:
        decision = QuestionPolicy("competition").decide(IntentLedger("s"), self.candidates, 10)
        self.assertIsNone(decision.attribute)

    def test_adaptive_mode_chooses_allowed_concrete_attribute(self) -> None:
        decision = QuestionPolicy("adaptive").decide(IntentLedger("s"), self.candidates, 1)
        self.assertIn(decision.attribute, {"material", "feature", "color", "style", "size", "brand", "budget", "use_case"})
        self.assertEqual(decision.reason, "candidate_information_gain")

    def test_adaptive_mode_does_not_repeat_asked_attribute(self) -> None:
        ledger = IntentLedger("s")
        policy = QuestionPolicy("adaptive")
        first = policy.decide(ledger, self.candidates, 1)
        ledger.record_ask(first.attribute)
        second = policy.decide(ledger, self.candidates, 2)
        self.assertNotEqual(first.attribute, second.attribute)

    def test_adaptive_mode_respects_no_preference(self) -> None:
        ledger = IntentLedger("s")
        ledger.closed_attributes.add("material")
        decision = QuestionPolicy("adaptive").decide(ledger, self.candidates, 1)
        self.assertNotEqual(decision.attribute, "material")

    def test_router_is_reversible(self) -> None:
        ledger = IntentLedger("s")
        self.assertEqual(QuestionPolicy().route(ledger)[0], "browsing")
        ledger.update("A key requirement is: cotton.", 1)
        self.assertEqual(QuestionPolicy().route(ledger)[0], "buying")

    def test_invalid_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            QuestionPolicy("opaque-llm")


if __name__ == "__main__":
    unittest.main()
