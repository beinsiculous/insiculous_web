import os
import unittest
from pathlib import Path

from helpers import DATA, REPOSITORY_ROOT, WORKBOOK_DATA
from fk_core import keys
from fk_core.derive import default_import_document, menu_by_day, plan_by_day
from fk_core.validate import ValidationReport, check_import_document, validate_data
from fk_core.xlsx import read_workbook, rows_as_records

# The archived workbook is personal data and lives outside this public repository (see the note on
# source/ in .gitignore), so the one test that cross-checks the derived menu against the original
# spreadsheet skips unless you point FORTKNIGHT_WORKBOOK at your copy — the same way the tests that
# drive the JavaScript modules skip when node is not installed.
WORKBOOK_PATH = Path(os.environ["FORTKNIGHT_WORKBOOK"]) if os.environ.get("FORTKNIGHT_WORKBOOK") else REPOSITORY_ROOT / "source" / "FortKnight.xlsx"


class ValidationTests(unittest.TestCase):
    def test_canonical_data_validates_and_is_neutral(self):
        report = validate_data(DATA)
        self.assertTrue(report.ok, report.render())
        self.assertEqual(DATA["activities"]["activities"], [], "data/ carries nobody's activities")
        self.assertEqual(DATA["menus"], {}, "data/ carries nobody's menus")
        self.assertTrue(all(not day["blockFocus"] and day["mainFocus"] is None for day in DATA["days"]["days"].values()), "data/ carries nobody's focus grid")
        self.assertTrue(all(season["menuId"] is None for season in DATA["seasons"]["seasons"]))
        self.assertIsNone(DATA["weights"])

    def test_workbook_example_overlay_validates(self):
        report = validate_data(WORKBOOK_DATA)
        self.assertTrue(report.ok, report.render())
        self.assertEqual(len(WORKBOOK_DATA["activities"]["activities"]), 64)
        self.assertEqual(list(WORKBOOK_DATA["menus"]), ["spooky-season"])
        self.assertEqual(WORKBOOK_DATA["days"]["days"]["sun-a"]["blockFocus"]["early"], "meals", "the overlay replaces days.json")
        self.assertEqual(WORKBOOK_DATA["categories"], DATA["categories"], "shared files come from data/")
        self.assertEqual(WORKBOOK_DATA["weights"]["id"], "baseline")

    def test_broken_meal_reference_is_caught(self):
        import copy
        broken = copy.deepcopy(WORKBOOK_DATA)
        for activity in broken["activities"]["activities"]:
            if activity["detail"].get("mealRefs"):
                activity["detail"]["mealRefs"][0]["mealKey"] = "sun-a+sat-b"
                break
        report = validate_data(broken)
        self.assertFalse(report.ok)
        self.assertTrue(any("mealRef" in error for error in report.errors))

    def test_known_start_that_disagrees_with_the_rule_is_caught(self):
        import copy
        broken = copy.deepcopy(DATA)
        broken["seasons"]["seasons"][0]["knownStarts"]["2026"] = "2026-03-05"  # the sheet's typo; the rule says 03-08
        report = validate_data(broken)
        self.assertFalse(report.ok)
        self.assertTrue(any("knownStarts[2026]" in error and "2026-03-08" in error for error in report.errors), report.render())
        unruly = copy.deepcopy(DATA)
        unruly["seasons"]["seasons"][1]["startRule"] = {"kind": "solar", "term": "midsummer", "offsetDays": 0, "snap": None}
        report = validate_data(unruly)
        self.assertTrue(any("midsummer" in error for error in report.errors), report.render())  # the schema enum catches it first


class DerivedViewTests(unittest.TestCase):
    @unittest.skipUnless(WORKBOOK_PATH.is_file(), f"no archived workbook at {WORKBOOK_PATH} (set FORTKNIGHT_WORKBOOK)")
    def test_menu_by_day_matches_workbook_menu_sheet(self):
        menu = WORKBOOK_DATA["menus"]["spooky-season"]
        derived = menu_by_day(menu)
        workbook = read_workbook(WORKBOOK_PATH)
        checked = 0
        for record in rows_as_records(workbook["Menu"]):
            from fk_core.keys import day_key_from_label
            day_key = day_key_from_label(record["Day"].as_text())
            for slot in ("Brunch", "Snack", "Dinner"):
                expected = record[slot].as_text().lstrip("*").strip()
                self.assertEqual(derived[day_key][slot.lower()]["menu"], expected, f"{day_key} {slot}")
                checked += 1
        self.assertEqual(checked, 42)

    def test_plan_by_day_has_every_block_and_resolves_meal_prep(self):
        plan = plan_by_day(WORKBOOK_DATA, WORKBOOK_DATA["menus"]["spooky-season"])
        self.assertEqual(len(plan), 14)
        for day in plan.values():
            self.assertEqual([block["block"] for block in day["blocks"]], WORKBOOK_DATA["blocks"]["order"])
        meal_prep_targets = [
            target
            for day in plan.values() for block in day["blocks"] for activity in block["activities"]
            for target in activity["mealPrepTargets"]
        ]
        self.assertTrue(meal_prep_targets)
        self.assertTrue(all(target["menu"] for target in meal_prep_targets))



    def test_plan_by_day_on_neutral_data_has_empty_blocks_and_no_menu(self):
        plan = plan_by_day(DATA)
        self.assertEqual(len(plan), 14)
        for day in plan.values():
            self.assertEqual([block["block"] for block in day["blocks"]], DATA["blocks"]["order"])
            self.assertTrue(all(block["activities"] == [] and block["focus"] is None for block in day["blocks"]))
            self.assertEqual(day["menu"], {slot: None for slot in keys.MEAL_SLOT_ORDER})
            self.assertIsNone(day["mainFocus"])

    def test_default_import_on_neutral_data_is_the_short_readable_example(self):
        document = default_import_document(DATA)
        report = check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport())
        self.assertTrue(report.ok, report.render())
        self.assertEqual(document["schemaVersion"], 2)
        self.assertEqual(document["source"]["kind"], "other")
        self.assertNotIn("importedAt", document["source"])  # deterministic: the bundle hash must not move per build
        self.assertEqual((document["commitments"], document["tasks"], document["skipped"]), ([], [], []))
        self.assertTrue(document["review"])
        # No machine sections on a fresh device: the prefill only shows the readable shape.
        for key in ("fixedActivities", "blocks", "blockFocusGrid", "appointmentBlocks", "standingAppointments"):
            self.assertNotIn(key, document)

    def test_default_import_on_the_workbook_overlay_is_the_workbook(self):
        document = default_import_document(WORKBOOK_DATA)
        report = check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport())
        self.assertTrue(report.ok, report.render())
        self.assertEqual(document["source"]["kind"], "xlsx")
        self.assertNotIn("importedAt", document["source"])
        self.assertEqual(len(document["fixedActivities"]), len(WORKBOOK_DATA["activities"]["activities"]))
        self.assertEqual(list(document["blockFocusGrid"]), keys.DAY_KEY_ORDER)
        self.assertEqual(document["blockFocusGrid"]["sun-a"]["early"], "meals")
        self.assertEqual([block["key"] for block in document["blocks"]], WORKBOOK_DATA["blocks"]["order"])
        self.assertEqual(document["appointmentBlocks"]["sun-a"], "midday")
        self.assertEqual(document["appointmentBlocks"]["sun-b"], "early")
        self.assertEqual(document["standingAppointments"], [])
        self.assertNotIn("raw", document["fixedActivities"][0])
        self.assertEqual(len(document["meals"]), 24, "the example's menu meals travel under meals")
        self.assertEqual(document["meals"][0]["menuId"], "spooky-season")
        self.assertIn("days", document["meals"][0])


if __name__ == "__main__":
    unittest.main()
