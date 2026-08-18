import unittest

from helpers import DATA, WORKBOOK_DATA
from fk_core import keys
from fk_core.allocations import compute_allocations, weights_from_allocations


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.allocations = compute_allocations(WORKBOOK_DATA)

    def test_block_focus_totals_cover_the_whole_focus_window(self):
        block_focus = self.allocations["byBlockFocus"]
        self.assertEqual(sum(block_focus["byCategory"].values()), self.allocations["focusWindow"]["minutesPerCycle"])
        self.assertEqual(self.allocations["focusWindow"]["minutesPerCycle"], 8400)
        self.assertAlmostEqual(sum(block_focus["shareByCategory"].values()), 1.0, places=2)

    def test_untimed_activities_never_exceed_block_capacity(self):
        """Timed activities are measured (and may spill past a block, e.g. a date night); the
        untimed split must always fit inside the block."""
        per_activity = self.allocations["byActivities"]["perActivity"]
        untimed_totals = {}
        for activity in WORKBOOK_DATA["activities"]["activities"]:
            if per_activity[activity["id"]]["method"] == "block-remainder-split":
                slot = (activity["dayKey"], activity["block"])
                untimed_totals[slot] = untimed_totals.get(slot, 0) + per_activity[activity["id"]]["minutes"]
        for (day_key, block_key), minutes in untimed_totals.items():
            capacity = WORKBOOK_DATA["blocks"]["blocks"][block_key]["durationMinutes"]
            self.assertLessEqual(minutes, capacity + 1, f"{day_key}/{block_key}")

    def test_weights_contract(self):
        weights = weights_from_allocations(self.allocations, WORKBOOK_DATA["days"])
        self.assertEqual(set(weights["categories"]), set(keys.CATEGORY_KEY_ORDER))
        self.assertAlmostEqual(sum(category["share"] for category in weights["categories"].values()) + weights["flexibleShare"], 1.0, places=2)
        self.assertEqual(len(weights["blockFocusGrid"]), 14)
        self.assertGreater(weights["categories"]["meals"]["share"], 0, "the workbook example carries a real grid")

    def test_neutral_data_allocates_everything_to_flexible_without_error(self):
        allocations = compute_allocations(DATA)
        self.assertEqual(allocations["byBlockFocus"]["shareByCategory"][keys.FLEXIBLE_FOCUS], 1.0)
        self.assertTrue(all(share == 0 for category, share in allocations["byBlockFocus"]["shareByCategory"].items() if category != keys.FLEXIBLE_FOCUS))
        self.assertTrue(all(share == 0 for share in allocations["byActivities"]["shareByCategory"].values()))
        weights = weights_from_allocations(allocations, DATA["days"])
        self.assertEqual(weights["flexibleShare"], 1.0)
        self.assertEqual(weights["blockFocusGrid"], {day_key: {} for day_key in keys.DAY_KEY_ORDER})


if __name__ == "__main__":
    unittest.main()
