"""The person's day and allocations from their profile (src/lib/shared/day-plan.js, src/lib/shared/allocations-rules.js),
driven through node; the allocations port is checked against fk_core.allocations on the workbook example."""
import json
import shutil
import unittest

from tests.helpers import DATA, REPOSITORY_ROOT, STDIN_PRELUDE, WORKBOOK_DATA, module_import, run_node

from fk_core import keys
from fk_core.allocations import compute_allocations
from fk_core.derive import default_import_document

IMPORT_FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "import.sample.json"


def load_import_fixture():
    return json.loads(IMPORT_FIXTURE_PATH.read_text(encoding="utf-8"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class DayPlanTests(unittest.TestCase):
    def day_plan(self, weights, answers, day_key):
        script = module_import("day-plan.js", "dayPlan") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(dayPlan({ weights: inputs.weights, answers: inputs.answers, dayKey: inputs.dayKey, days: inputs.days })));"
        return run_node(script, {"weights": weights, "answers": answers, "dayKey": day_key, "days": DATA["days"]})

    def test_the_menu_line_follows_the_meal_plan(self):
        weights = {"blocks": [{"key": "early", "start": "06:00", "end": "22:00", "durationMinutes": 960, "carriesFocus": True}], "blockFocusGrid": {},
                   "meals": {"perDay": 2, "meals": [{"name": "Lunch", "slots": ["afternoon"]}, {"name": "Dinner", "slots": ["evening"]}]}}
        answers = {"mealPlan": {"items": [{"id": "lunch--sun-a--wed-b", "meal": "lunch", "dish": "Lentil soup", "days": ["sun-a", "wed-b"], "notes": None}]}}
        self.assertEqual([(entry["meal"], entry["dish"], entry["leftovers"]) for entry in self.day_plan(weights, answers, "wed-b")["menu"]], [("Lunch", "Lentil soup", True), ("Dinner", None, False)])
        self.assertEqual([entry["dish"] for entry in self.day_plan(weights, answers, "mon-a")["menu"]], [None, None])
        self.assertEqual(self.day_plan({"blocks": []}, {}, "mon-a")["menu"], [])

    def test_imported_activities_appointments_and_meals_land_in_the_persons_blocks(self):
        document = load_import_fixture()
        weights = {
            "blocks": document["blocks"],
            "blockFocusGrid": document["blockFocusGrid"],
            "appointmentBlocks": document["appointmentBlocks"],
        }
        answers = {"startup": {"import": document}, "standingAppointments": document["standingAppointments"]}
        plan = self.day_plan(weights, answers, "wed-a")
        self.assertEqual((plan["label"], plan["week"], plan["weekday"], plan["hasImport"]), ("Wednesday A", 2, "wednesday", True))
        self.assertEqual([block["key"] for block in plan["blocks"]], ["unscheduled", "early", "late"])
        late = plan["blocks"][2]
        self.assertEqual(late["focus"], document["blockFocusGrid"]["wed-a"]["late"])
        self.assertTrue(late["isAppointmentBlock"])
        self.assertEqual([activity["title"] for activity in late["activities"]], ["Choir practice"], "the fixed activity lands in its own block")
        self.assertEqual(late["activities"][0]["source"], "import")
        self.assertEqual(plan["meals"], [{"slot": "dinner", "menu": "Lentil soup", "cookExtra": False}], "menu entries with a `days` list")
        self.assertEqual(plan["unplaced"], [])
        # Friday carries the weekly piano lesson (a standing appointment) on both fortnight Fridays, placed by its start time.
        for day_key in ("fri-b", "fri-a"):
            friday = self.day_plan(weights, answers, day_key)
            late_activities = friday["blocks"][2]["activities"]
            self.assertEqual([(activity["title"], activity["source"], activity["start"], activity["end"]) for activity in late_activities], [("Piano lesson", "standing-appointment", "14:00", "16:15")])
        self.assertEqual(self.day_plan(weights, answers, "fri-b")["meals"], [{"slot": "brunch", "menu": "Pancakes", "cookExtra": False}], "menu entries with a dayKey")

    def test_activity_whose_block_is_not_the_persons_is_placed_by_time_or_listed_unplaced(self):
        document = load_import_fixture()
        document["fixedActivities"][0]["block"] = "midday"  # the person's day has no midday block; 18:30 falls in "late"
        untimed = {"id": "x", "title": "Untimed thing", "dayKey": "wed-a", "block": "midday", "categories": ["health"]}
        document["fixedActivities"].append(untimed)
        weights = {"blocks": document["blocks"], "blockFocusGrid": {}, "appointmentBlocks": {}}
        plan = self.day_plan(weights, {"startup": {"import": document}, "standingAppointments": []}, "wed-a")
        self.assertEqual([activity["title"] for activity in plan["blocks"][2]["activities"]], ["Choir practice"])
        self.assertEqual([activity["title"] for activity in plan["unplaced"]], ["Untimed thing"])

    def test_tasks_land_in_the_block_their_time_of_day_falls_in(self):
        # Tasks live in answers.tasks — typed in Startup 2 or merged there from an applied import (applyImportDocument).
        with open(REPOSITORY_ROOT / "tests" / "fixtures" / "import.v2.sample.json", encoding="utf-8") as file_handle:
            document = json.load(file_handle)
        blocks = load_import_fixture()["blocks"]  # unscheduled 22-06, early 06-14, late 14-22
        weights = {"blocks": blocks, "blockFocusGrid": {}, "appointmentBlocks": {}}
        script = module_import("weights-rules.js", "applyImportDocument") + module_import("day-plan.js", "dayPlan") + STDIN_PRELUDE + """
            const answers = { standingAppointments: [], tasks: inputs.tasks };
            applyImportDocument(answers, inputs.document, inputs.categories.order, inputs.weekdays, null, inputs.categories);
            process.stdout.write(JSON.stringify(Object.fromEntries(inputs.dayKeys.map((dayKey) => [dayKey, dayPlan({ weights: inputs.weights, answers, dayKey, days: inputs.days })]))));"""
        hand_typed = [{"title": "Call mum", "weekdays": ["tuesday"], "cadence": {"kind": "weekly"}, "timeOfDay": "morning", "durationMinutes": 20, "category": "friends-family"}]
        plans = run_node(script, {"weights": weights, "document": document, "tasks": hand_typed, "categories": DATA["categories"], "weekdays": keys.WEEKDAY_NAMES, "days": DATA["days"], "dayKeys": ["tue-b", "wed-a"]})
        plan = plans["tue-b"]
        late = [activity for activity in plan["blocks"][2]["activities"] if activity["source"] == "task"]
        self.assertEqual([(activity["title"], activity["timeOfDay"], activity["priority"]) for activity in late], [("Take out the bins", "evening", 2)], "evening (19:00) falls in the late block on both Tuesdays")
        early = [activity for activity in plan["blocks"][1]["activities"] if activity["source"] == "task"]
        self.assertEqual([(activity["title"], activity["timeOfDay"]) for activity in early], [("Call mum", "morning")], "hand-typed tasks (Startup 2) sit beside the import's")
        self.assertEqual([activity["title"] for activity in plan["unplaced"]], [], "an anytime task on Wednesday/Saturday is not Tuesday's")
        self.assertEqual([(activity["title"], activity["timeOfDay"]) for activity in plans["wed-a"]["unplaced"]], [("Water the plants", "anytime")])

    def test_no_import_and_no_appointments_is_just_the_blocks(self):
        weights = {"blocks": [{"key": "flexible", "start": "06:00", "end": "22:00", "durationMinutes": 960, "carriesFocus": True}], "blockFocusGrid": {}, "appointmentBlocks": {}}
        plan = self.day_plan(weights, {"startup": {"import": None}, "standingAppointments": []}, "sun-a")
        self.assertFalse(plan["hasImport"])
        self.assertEqual([(block["key"], block["focus"], block["activities"]) for block in plan["blocks"]], [("flexible", None, [])])
        self.assertEqual((plan["meals"], plan["unplaced"]), ([], []))

    def test_the_workbook_example_document_renders_a_full_day(self):
        document = default_import_document(WORKBOOK_DATA)
        weights = {"blocks": document["blocks"], "blockFocusGrid": document["blockFocusGrid"], "appointmentBlocks": document["appointmentBlocks"]}
        plan = self.day_plan(weights, {"startup": {"import": document}, "standingAppointments": []}, "sun-a")
        titles = [activity["title"] for block in plan["blocks"] for activity in block["activities"]]
        self.assertIn("Church", titles)
        self.assertEqual(plan["unplaced"], [], "every workbook activity names one of the five blocks")
        self.assertEqual(plan["blocks"][1]["focus"], "meals")
        self.assertEqual(sorted(meal["slot"] for meal in plan["meals"]), ["brunch", "dinner", "snack"], "the example's menu travels in meals")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class AllocationsRulesTests(unittest.TestCase):
    def test_block_focus_port_matches_python_on_the_workbook_example(self):
        expected = compute_allocations(WORKBOOK_DATA)["byBlockFocus"]
        document = default_import_document(WORKBOOK_DATA)
        focus_blocks = [block for block in document["blocks"] if block["carriesFocus"]]
        script = module_import("allocations-rules.js", "allocateByBlockFocus", "allocationsFromWeights") + STDIN_PRELUDE + """
            const view = allocateByBlockFocus(inputs.grid, inputs.focusBlocks, inputs.categories, inputs.dayKeys);
            const views = allocationsFromWeights({ id: "x", categories: { meals: { share: 0.25 }, cleaning: { share: 0.75 } }, flexibleShare: 0, blocks: inputs.focusBlocks, blockFocusGrid: inputs.grid }, inputs.categories, inputs.dayKeys);
            const bare = allocationsFromWeights({ id: "y", categories: { meals: { share: 1 } }, flexibleShare: 0, blocks: inputs.focusBlocks, blockFocusGrid: {} }, inputs.categories, inputs.dayKeys);
            process.stdout.write(JSON.stringify({ view, views: Object.keys(views), weightsShares: views.byWeights.shareByCategory, bare: Object.keys(bare) }));
        """
        result = run_node(script, {"grid": document["blockFocusGrid"], "focusBlocks": focus_blocks, "categories": keys.CATEGORY_KEY_ORDER, "dayKeys": keys.DAY_KEY_ORDER})
        self.assertEqual(result["view"]["byCategory"], expected["byCategory"])
        for category, share in expected["shareByCategory"].items():
            self.assertAlmostEqual(result["view"]["shareByCategory"][category], share, places=3, msg=category)
        self.assertEqual(result["views"], ["byWeights", "byBlockFocus"])
        self.assertEqual(result["weightsShares"]["meals"], 0.25)
        self.assertEqual(result["weightsShares"]["flexible"], 0)
        self.assertEqual(result["bare"], ["byWeights"], "no imported grid -> no focus-grid view")

    def test_two_block_profile_by_hand(self):
        # A 2-block day: one focus block of 960 minutes; a grid that fills 10 of 14 days with meals, 2 with cleaning, 2 empty.
        grid = {day_key: {"flexible": "meals"} for day_key in keys.DAY_KEY_ORDER[:10]}
        grid.update({day_key: {"flexible": "cleaning"} for day_key in keys.DAY_KEY_ORDER[10:12]})
        script = module_import("allocations-rules.js", "allocateByBlockFocus") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(allocateByBlockFocus(inputs.grid, [{ key: 'flexible', durationMinutes: 960, carriesFocus: true }], inputs.categories, inputs.dayKeys)));"
        view = run_node(script, {"grid": grid, "categories": keys.CATEGORY_KEY_ORDER, "dayKeys": keys.DAY_KEY_ORDER})
        self.assertEqual((view["byCategory"]["meals"], view["byCategory"]["cleaning"], view["byCategory"]["flexible"]), (9600, 1920, 1920))
        self.assertEqual((view["shareByCategory"]["meals"], view["shareByCategory"]["cleaning"], view["shareByCategory"]["flexible"]), (0.7143, 0.1429, 0.1429))
        self.assertAlmostEqual(sum(view["shareByCategory"].values()), 1.0, places=3)

    def test_neutral_grid_is_all_flexible(self):
        # A fresh device applies no grid at all (the neutral default document has none): every focus block is flexible.
        script = module_import("allocations-rules.js", "allocateByBlockFocus") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(allocateByBlockFocus(inputs.grid, inputs.focusBlocks, inputs.categories, inputs.dayKeys).shareByCategory));"
        focus_blocks = [{"key": key, **DATA["blocks"]["blocks"][key]} for key in DATA["blocks"]["order"] if DATA["blocks"]["blocks"][key]["carriesFocus"]]
        shares = run_node(script, {"grid": {}, "focusBlocks": focus_blocks, "categories": keys.CATEGORY_KEY_ORDER, "dayKeys": keys.DAY_KEY_ORDER})
        self.assertEqual(shares["flexible"], 1)
        self.assertTrue(all(shares[category] == 0 for category in keys.CATEGORY_KEY_ORDER))


if __name__ == "__main__":
    unittest.main()
