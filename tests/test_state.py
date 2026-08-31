from __future__ import annotations

import unittest

from submission.state import IntentLedger


class IntentLedgerTest(unittest.TestCase):
    def test_buying_message_extracts_category_and_hard_constraint(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I'm looking for running shoes. A key requirement is: cotton.", 1)
        active = ledger.active_constraints()
        self.assertEqual(active[0].attribute, "category")
        self.assertEqual(active[0].value, "running shoes")
        self.assertTrue(any(item.value == "cotton" and item.hardness == "hard" for item in active))

    def test_browsing_message_keeps_only_category(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I'm looking for Test Shoes, but I'm still exploring.", 1)
        self.assertEqual([(item.attribute, item.value) for item in ledger.active_constraints()], [("category", "Test Shoes")])

    def test_constraint_accumulation_is_deduplicated(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("For that, what matters is: cotton; color: blue.", 1)
        ledger.update("For that, what matters is: cotton.", 2)
        self.assertEqual(sum(item.value.lower() == "cotton" for item in ledger.constraints), 1)

    def test_override_tombstones_soft_preference_and_preserves_category(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I'm looking for jackets. I prefer a red relaxed fit.", 1)
        ledger.update("Actually, ignore my earlier preference. What I need is: black wool.", 3)
        category = next(item for item in ledger.constraints if item.attribute == "category")
        old = next(item for item in ledger.constraints if "red relaxed" in item.value.lower())
        new = next(item for item in ledger.constraints if "black wool" in item.value.lower())
        self.assertTrue(category.active)
        self.assertFalse(old.active)
        self.assertEqual(old.superseded_by_turn, 3)
        self.assertTrue(new.active)
        self.assertEqual(ledger.last_update_kind, "override")

    def test_explicit_whole_preference_override_tombstones_all_noncategory_constraints(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I'm looking for shoes. A key requirement is: leather.", 1)
        ledger.update("For that, what matters is: color: black.", 2)
        ledger.update("Actually, ignore my earlier preference. What I need is: cotton and blue.", 3)
        active = ledger.active_constraints()
        self.assertTrue(any(item.attribute == "category" for item in active))
        self.assertFalse(any("leather" in item.value.lower() for item in active))
        self.assertFalse(any("black" in item.value.lower() for item in active))
        self.assertTrue(any("cotton" in item.value.lower() for item in active))
        self.assertTrue(any("blue" in item.value.lower() for item in active))

    def test_no_preference_closes_attribute_without_negative_constraint(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I don't have a preference for material; please use your judgment.", 2)
        self.assertIn("material", ledger.closed_attributes)
        self.assertEqual(ledger.active_constraints(), [])
        self.assertEqual(ledger.last_update_kind, "no_preference")

    def test_additional_no_preference_is_recognized(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I don't have an additional preference for color.", 2)
        self.assertIn("color", ledger.closed_attributes)

    def test_empty_and_generic_retry_messages_do_not_add_constraints(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("", 1)
        ledger.update("Those options are not quite right yet. Ask me about one specific attribute.", 2)
        self.assertEqual(ledger.constraints, [])

    def test_history_terms_are_sanitized_unique_and_bounded(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("' OR products MATCH * ; DROP TABLE products; blue blue", 1)
        result = ledger.history_terms()
        self.assertIn("blue", result)
        self.assertEqual(len(result), len(set(result)))
        self.assertLessEqual(len(result), 80)
        self.assertNotIn("'", result)

    def test_snapshot_retains_tombstone_provenance(self) -> None:
        ledger = IntentLedger("s")
        ledger.update("I'm looking for coats. red relaxed fit.", 1)
        ledger.update("Actually, instead, what I need is: wool.", 2)
        snapshot = ledger.snapshot()
        self.assertTrue(any(not item["active"] for item in snapshot["constraints"]))
        self.assertTrue(any(item["superseded_by_turn"] == 2 for item in snapshot["constraints"]))

    def test_profile_is_copied_not_aliased(self) -> None:
        profile = {"preference_tags": ["fit"]}
        ledger = IntentLedger("s", profile)
        profile["preference_tags"].append("style")
        self.assertEqual(ledger.user_profile["preference_tags"], ["fit"])


if __name__ == "__main__":
    unittest.main()
