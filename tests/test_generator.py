"""The generator (weights -> proposed blockFocusGrid): the rule, its validation, and Python/JavaScript parity."""
import copy
import json
import shutil
import unittest

from tests.helpers import DATA, REPOSITORY_ROOT, STDIN_PRELUDE, WORKBOOK_DATA, module_import, run_node

from fk_core import keys
from fk_core.allocations import allocate_by_block_focus
from fk_core.generator import DEFAULT_GENERATOR, REST_DAY_REASON, block_key_for_time, diff_block_focus_grid, generate_activities, generate_block_focus_grid, proposal_from_weights
from fk_core.validate import ValidationReport, check_against_schema_file, check_block_focus_grid, check_weights_references
from fk_core.weights import default_answers, weights_from_answers

BASELINE_PATH = REPOSITORY_ROOT / "examples" / "workbook" / "weights.baseline.json"
SPOOKY_SEASON_FOCUS = next(season["focus"] for season in DATA["seasons"]["seasons"] if season["id"] == "spooky-season")
QUESTIONNAIRE = DATA["questionnaire"]


def baseline_weights():
    with open(BASELINE_PATH, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def derive(answers, **overrides):
    options = {"weights_id": "sample", "days": DATA["days"]}
    options.update(overrides)
    return weights_from_answers(answers, DATA["categories"], QUESTIONNAIRE, **options)


def answers_with(**changes):
    answers = default_answers(QUESTIONNAIRE, DATA["categories"])
    answers.update(changes)
    return answers


def clinic(weekdays=("monday", "wednesday"), start="09:00", duration_minutes=150):
    return {"title": "Clinic", "weekdays": list(weekdays), "start": start, "durationMinutes": duration_minutes, "category": "health", "cadence": {"kind": "weekly"}}


def subjects_scope_answers():
    """Agenda scope 'subjects' with no standouts (every subject at the same range) -> one `flexible` block."""
    answers = answers_with(agendaScope="subjects", restDays=[])
    for subject_answer in answers["subjectTime"].values():
        subject_answer["minutesPerDay"] = {"min": 30, "max": 60}
        subject_answer["peripheral"] = False
    return answers


def anchored_night_owl_answers():
    """A 20:00-10:00 waking window (wraps midnight) with a daily 21:00-00:30 commitment: pins across midnight."""
    return answers_with(wakingWindow={"start": "20:00", "end": "10:00"}, restDays=[],
                        standingAppointments=[{"title": "Night shift", "weekdays": list(keys.WEEKDAY_NAMES), "start": "21:00", "durationMinutes": 210, "category": "working", "cadence": {"kind": "weekly"}}])


def focus_minutes(weights, blocks=None):
    focus_blocks = [block for block in weights.get("blocks", []) if block["carriesFocus"]] or [dict(key=key, **blocks["blocks"][key]) for key in keys.FOCUS_BLOCK_KEYS]
    return {block["key"]: block["durationMinutes"] for block in focus_blocks}


def delivered_minutes(grid, cell_minutes):
    totals = {key: 0 for key in keys.CATEGORY_KEY_ORDER + [keys.FLEXIBLE_FOCUS]}
    for cells in grid.values():
        for block_key, focus in cells.items():
            totals[focus] += cell_minutes[block_key]
    return totals


class WorkbookBaselineTests(unittest.TestCase):
    """Generating from the workbook baseline reproduces its shares (the round trip through allocations)."""

    def setUp(self):
        self.weights = baseline_weights()
        self.result = generate_block_focus_grid(self.weights, QUESTIONNAIRE, SPOOKY_SEASON_FOCUS, WORKBOOK_DATA["blocks"])

    def test_every_cell_is_filled_and_valid(self):
        grid = self.result["blockFocusGrid"]
        self.assertEqual(list(grid), keys.DAY_KEY_ORDER)
        for cells in grid.values():
            self.assertEqual(list(cells), keys.FOCUS_BLOCK_KEYS)
        report = ValidationReport()
        check_block_focus_grid(grid, keys.FOCUS_BLOCK_KEYS, keys.CATEGORY_KEY_ORDER, report, "proposal")
        self.assertTrue(report.ok, report.render())
        self.assertEqual(self.result["warnings"], [])

    def test_shares_come_back_within_one_cell(self):
        days = {"order": keys.DAY_KEY_ORDER, "days": {day_key: {"blockFocus": cells} for day_key, cells in self.result["blockFocusGrid"].items()}}
        allocations = allocate_by_block_focus(days, WORKBOOK_DATA["blocks"])
        total = sum(WORKBOOK_DATA["blocks"]["blocks"][key]["durationMinutes"] for key in keys.FOCUS_BLOCK_KEYS) * 14
        largest_cell = max(WORKBOOK_DATA["blocks"]["blocks"][key]["durationMinutes"] for key in keys.FOCUS_BLOCK_KEYS)
        for category_key in keys.CATEGORY_KEY_ORDER:
            self.assertLessEqual(abs(allocations["byCategory"][category_key] - self.weights["categories"][category_key]["share"] * total), largest_cell, category_key)
        self.assertLessEqual(abs(allocations["byCategory"][keys.FLEXIBLE_FOCUS] - self.weights["flexibleShare"] * total), largest_cell)

    def test_diff_against_the_workbook_grid_covers_every_cell(self):
        diff = diff_block_focus_grid(self.weights["blockFocusGrid"], self.result["blockFocusGrid"])
        counts = diff["counts"]
        self.assertEqual(counts["same"] + counts["changed"], 42)
        self.assertEqual(counts["added"], 0)
        self.assertEqual(counts["removed"], 0)
        self.assertEqual(len(diff["changes"]), counts["changed"])
        for change in diff["changes"]:
            self.assertEqual(self.weights["blockFocusGrid"][change["dayKey"]][change["block"]], change["imported"])
            self.assertEqual(self.result["blockFocusGrid"][change["dayKey"]][change["block"]], change["proposed"])

    def test_season_focus_tags_show_up_in_reasons(self):
        reasons = " ".join(reason for cells in self.result["reasons"].values() for reason in cells.values())
        self.assertIn("season focus #1", reasons)
        self.assertNotIn("energy peak", reasons)  # the thin baseline has no energyPeak


class RuleTests(unittest.TestCase):
    def test_rest_days_are_flexible_all_day(self):
        weights = derive(answers_with(restDays=["saturday", "sunday"]))
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        for day_key in ("sat-a", "sat-b", "sun-a", "sun-b"):
            for block_key, focus in result["blockFocusGrid"][day_key].items():
                self.assertEqual(focus, keys.FLEXIBLE_FOCUS, day_key)
                self.assertEqual(result["reasons"][day_key][block_key], REST_DAY_REASON)
        self.assertNotIn(keys.FLEXIBLE_FOCUS, result["blockFocusGrid"]["mon-a"].values())
        self.assertTrue(any(warning.startswith("rest days give flexible") for warning in result["warnings"]))

    def test_an_anchor_covering_most_of_the_block_pins_it_but_a_short_one_does_not(self):
        # Default 06:00-22:00 window, 3 blocks of 320 minutes: early = 06:00-11:20.
        long_clinic = derive(answers_with(restDays=[], standingAppointments=[clinic(start="06:00", duration_minutes=240)]))
        pinned = generate_block_focus_grid(long_clinic, QUESTIONNAIRE)
        for day_key in ("mon-a", "mon-b", "wed-a", "wed-b"):
            self.assertEqual(pinned["blockFocusGrid"][day_key]["early"], "health", day_key)
            self.assertRegex(pinned["reasons"][day_key]["early"], r"^anchor: standing--clinic--1 covers (75|100)%$")  # the cut snaps to the clinic's end
        short_clinic = derive(answers_with(restDays=[], standingAppointments=[clinic(start="06:00", duration_minutes=60)]))
        unpinned = generate_block_focus_grid(short_clinic, QUESTIONNAIRE)
        self.assertFalse(any(reason.startswith("anchor:") for cells in unpinned["reasons"].values() for reason in cells.values()))

    def test_anchors_pin_across_midnight(self):
        weights = derive(anchored_night_owl_answers())
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        first_block = [block for block in weights["blocks"] if block["carriesFocus"]][0]
        self.assertEqual(first_block["start"], "20:00")
        for day_key in keys.DAY_KEY_ORDER:
            self.assertEqual(result["blockFocusGrid"][day_key][first_block["key"]], "working", day_key)
            self.assertTrue(result["reasons"][day_key][first_block["key"]].startswith("anchor: standing--night-shift--1 covers"), day_key)

    def test_appointment_blocks_do_not_change_the_grid(self):
        weights = derive(answers_with(restDays=[]))
        with_blocks = copy.deepcopy(weights)
        with_blocks["appointmentBlocks"] = {day_key: "early" for day_key in keys.DAY_KEY_ORDER}
        self.assertEqual(generate_block_focus_grid(with_blocks, QUESTIONNAIRE), generate_block_focus_grid(weights, QUESTIONNAIRE))

    def test_deterministic_and_independent_of_anchor_order(self):
        weights = derive(answers_with(restDays=[], standingAppointments=[clinic(start="06:00", duration_minutes=240), clinic(weekdays=("friday",), start="12:00", duration_minutes=200)]))
        first = generate_block_focus_grid(weights, QUESTIONNAIRE)
        self.assertEqual(first, generate_block_focus_grid(weights, QUESTIONNAIRE))
        shuffled = copy.deepcopy(weights)
        shuffled["blockSplit"]["anchors"].reverse()
        self.assertEqual(first, generate_block_focus_grid(shuffled, QUESTIONNAIRE))

    def test_one_block_profile_fills_fourteen_flexible_keyed_cells(self):
        weights = derive(subjects_scope_answers())
        focus_block_keys = [block["key"] for block in weights["blocks"] if block["carriesFocus"]]
        self.assertEqual(focus_block_keys, ["flexible"])
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        self.assertEqual([list(cells) for cells in result["blockFocusGrid"].values()], [["flexible"]] * 14)
        self.assertNotIn("preferred block", " ".join(reason for cells in result["reasons"].values() for reason in cells.values()))

    def test_a_share_smaller_than_a_cell_is_reported_not_scheduled(self):
        weights = derive(answers_with(restDays=[]))
        weights["categories"]["operations"]["share"] = 0.001
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        self.assertTrue(any(warning.startswith("operations: share 0.001") and warning.endswith("not scheduled") for warning in result["warnings"]), result["warnings"])
        self.assertFalse(any("operations" in cells.values() for cells in result["blockFocusGrid"].values()))

    def test_energy_peak_puts_a_struggle_category_in_the_peak_block(self):
        weights = derive(answers_with(restDays=[], energyPeak="morning", sentiment={"cleaning": "struggle"}))
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        early_cleaning = sum(1 for cells in result["blockFocusGrid"].values() if cells["early"] == "cleaning")
        late_cleaning = sum(1 for cells in result["blockFocusGrid"].values() if cells["late"] == "cleaning")
        self.assertGreater(early_cleaning, late_cleaning)
        self.assertIn("energy peak", " ".join(reason for cells in result["reasons"].values() for reason in cells.values()))

    def test_delivered_minutes_track_shares_for_a_questionnaire_profile(self):
        weights = derive(answers_with(restDays=[]))
        result = generate_block_focus_grid(weights, QUESTIONNAIRE)
        cell_minutes = focus_minutes(weights)
        total = sum(cell_minutes.values()) * 14
        delivered = delivered_minutes(result["blockFocusGrid"], cell_minutes)
        for category_key in keys.CATEGORY_KEY_ORDER:
            self.assertLessEqual(abs(delivered[category_key] - weights["categories"][category_key]["share"] * total), max(cell_minutes.values()), category_key)

    def test_unknown_season_focus_is_ignored_with_a_warning(self):
        weights = derive(answers_with(restDays=[]))
        result = generate_block_focus_grid(weights, QUESTIONNAIRE, ["meals", "gardening"])
        self.assertIn("seasonFocus: unknown category 'gardening'; ignored", result["warnings"])

    def test_tunables_default_when_the_questionnaire_has_none(self):
        weights = derive(answers_with(restDays=[]))
        self.assertEqual(QUESTIONNAIRE["generator"], DEFAULT_GENERATOR)
        self.assertEqual(generate_block_focus_grid(weights, {}), generate_block_focus_grid(weights, QUESTIONNAIRE))


class DiffTests(unittest.TestCase):
    def test_counts_added_removed_changed_same(self):
        imported = {"sun-a": {"early": "meals", "midday": "cleaning", "afternoon": "working"}}
        proposed = {"sun-a": {"early": "meals", "midday": "working", "late": "cleaning"}, "mon-b": {"early": "meals"}}
        diff = diff_block_focus_grid(imported, proposed)
        self.assertEqual(diff["counts"], {"same": 1, "changed": 1, "added": 2, "removed": 1})
        self.assertEqual(diff["changes"][0], {"dayKey": "sun-a", "block": "midday", "imported": "cleaning", "proposed": "working"})
        self.assertEqual(diff_block_focus_grid(None, None), {"changes": [], "counts": {"same": 0, "changed": 0, "added": 0, "removed": 0}})


class WeightsIntegrationTests(unittest.TestCase):
    """weights_from_answers carries the proposal; the person's own grid wins over the import's."""

    def test_proposal_rides_on_the_weights_and_validates(self):
        weights = derive(answers_with(restDays=[]), season_focus=SPOOKY_SEASON_FOCUS, season_id="spooky-season")
        proposal = weights["proposal"]
        self.assertEqual(proposal["seasonId"], "spooky-season")
        self.assertEqual(proposal["diff"]["counts"], {"same": 0, "changed": 0, "added": 42, "removed": 0})  # nothing imported
        self.assertEqual(proposal, proposal_from_weights({key: value for key, value in weights.items() if key != "proposal"}, QUESTIONNAIRE, DATA["categories"], SPOOKY_SEASON_FOCUS, "spooky-season"))
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), QUESTIONNAIRE, report)
        self.assertTrue(report.ok, report.render())

    def test_the_persons_own_grid_beats_the_imported_one(self):
        imported = {day_key: {"early": "meals", "midday": "cleaning", "late": "working"} for day_key in keys.DAY_KEY_ORDER}
        own = {day_key: {"early": "working", "midday": "meals", "late": "cleaning", "afternoon": "health"} for day_key in keys.DAY_KEY_ORDER}
        answers = answers_with(restDays=[], startup={"groupSize": 1, "importJson": "", "import": {"schemaVersion": 2, "source": {"kind": "other"}, "blockFocusGrid": imported}})
        self.assertEqual(derive(answers)["blockFocusGrid"]["sun-a"], imported["sun-a"])
        answers["blockFocusGrid"] = own
        weights = derive(answers)
        self.assertEqual(weights["blockFocusGrid"]["sun-a"], {"early": "working", "midday": "meals", "late": "cleaning"})
        self.assertIn("blockFocusGrid (your own): focus for block afternoon does not match this profile's blocks (early, midday, late); dropped", weights["blockSplit"]["warnings"])
        self.assertEqual(weights["proposal"]["diff"]["counts"]["added"], 0)


def practices_and_meals_answers():
    """Two practices, a two-slot meal whose first slot is unplaceable, and a clinic that eats the early cells."""
    return answers_with(restDays=["saturday"], practices=["yoga", "meditation"],
                        meals={"perDay": 2, "meals": [{"slots": ["anytime", "evening"]}, {"slots": ["late-evening"]}]},
                        standingAppointments=[clinic(start="06:00", duration_minutes=240)])


def meal_plan_answers():
    """A lunch eaten Sunday A + Wednesday B (leftovers) and a dinner on Monday B — with the default prep/cook toggles."""
    return answers_with(restDays=[], mealPlan={"items": [
        {"id": "dinner--sun-a--wed-b", "meal": "dinner", "dish": "Lentil soup", "days": ["sun-a", "wed-b"], "notes": None},
        {"id": "snack--mon-b", "meal": "snack", "dish": "Hummus", "days": ["mon-b"], "notes": None},
    ]})


def by_cell(activities):
    cells = {}
    for activity in activities:
        cells.setdefault((activity["dayKey"], activity["block"]), []).append(activity)
    return cells


class ActivityTests(unittest.TestCase):
    """generate_activities: sessions, practices and meals inside the cells of a grid."""

    def setUp(self):
        self.weights = derive(practices_and_meals_answers())
        self.grid = self.weights["proposal"]["blockFocusGrid"]
        self.result = generate_activities(self.weights, self.grid, QUESTIONNAIRE, DATA["categories"])
        self.focus_blocks = [block for block in self.weights["blocks"] if block["carriesFocus"]]

    def test_records_are_well_formed_and_ids_unique(self):
        ids = [activity["id"] for activity in self.result["activities"]]
        self.assertEqual(len(ids), len(set(ids)))
        for activity in self.result["activities"]:
            self.assertTrue(activity["id"].startswith(f"proposed--{activity['kind']}--"))
            self.assertEqual(activity["source"], "proposed")
            self.assertIn(activity["block"], [block["key"] for block in self.focus_blocks])
            self.assertIn(activity["kind"], ("session", "practice", "meal"))
            self.assertGreater(activity["minutes"], 0)
            self.assertEqual(activity["timing"] is not None, activity["kind"] == "meal")

    def test_cell_minutes_never_exceed_the_capacity_left_by_anchors(self):
        durations = {block["key"]: block["durationMinutes"] for block in self.focus_blocks}
        for (day_key, block_key), cell in by_cell(self.result["activities"]).items():
            sessions = sum(activity["minutes"] for activity in cell if activity["kind"] == "session")
            fixed = sum(activity["minutes"] for activity in cell if activity["kind"] != "session")
            anchored = 240 if day_key.startswith(("mon", "wed")) and block_key == "early" else 0
            self.assertLessEqual(sessions, max(0, durations[block_key] - anchored - fixed), (day_key, block_key))

    def test_sessions_track_targets_and_never_exceed_them(self):
        for subject_id, minutes in self.result["placedMinutes"].items():
            self.assertLessEqual(minutes["placed"], minutes["target"], subject_id)
            self.assertEqual(minutes["target"] % QUESTIONNAIRE["generator"]["sessionGridMinutes"], 0)
        placed_total = sum(minutes["placed"] for minutes in self.result["placedMinutes"].values())
        target_total = sum(minutes["target"] for minutes in self.result["placedMinutes"].values())
        self.assertGreater(placed_total, 0.8 * target_total)

    def test_sessions_only_in_cells_of_their_focus_or_flexible_spillover(self):
        for activity in self.result["activities"]:
            if activity["kind"] != "session":
                continue
            focus = self.grid[activity["dayKey"]][activity["block"]]
            if focus == keys.FLEXIBLE_FOCUS:
                self.assertEqual(activity["priority"], 4)
                self.assertTrue(activity["reason"].startswith("spillover:"))
            else:
                self.assertEqual(activity["categories"], [focus])
                self.assertEqual(activity["priority"], 3)

    def test_rest_days_carry_practices_and_meals_but_no_sessions(self):
        for day_key in ("sat-a", "sat-b"):
            kinds = {activity["kind"] for activity in self.result["activities"] if activity["dayKey"] == day_key}
            self.assertEqual(kinds, {"practice", "meal"}, day_key)

    def test_practices_land_in_the_spirituality_cell_else_the_first_block(self):
        first_block = self.focus_blocks[0]["key"]
        for day_key in keys.DAY_KEY_ORDER:
            practices = [activity for activity in self.result["activities"] if activity["dayKey"] == day_key and activity["kind"] == "practice"]
            self.assertEqual([activity["title"] for activity in practices], ["Practice: yoga", "Practice: meditation"])
            spirituality_blocks = [block_key for block_key, focus in self.grid[day_key].items() if focus == "spirituality-development"]
            expected = spirituality_blocks[0] if spirituality_blocks else first_block
            self.assertEqual({activity["block"] for activity in practices}, {expected}, day_key)

    def test_meals_take_the_first_placeable_slot_and_warn_otherwise(self):
        meals = [activity for activity in self.result["activities"] if activity["kind"] == "meal" and activity["dayKey"] == "mon-a"]
        self.assertEqual([(activity["title"], activity["timing"]["estimatedStart"], activity["reason"]) for activity in meals],
                         [("Breakfast", "18:00", "meal slot evening"), ("Dinner", "21:00", "meal slot late-evening")])  # unnamed test meals take the default names by position
        early_bird = derive(answers_with(restDays=[], wakingWindow={"start": "05:00", "end": "17:00"}, meals={"perDay": 2, "meals": [{"slots": ["anytime"]}, {"slots": ["late-evening"]}]}))
        result = generate_activities(early_bird, early_bird["proposal"]["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"])
        self.assertIn("activities: meal 1: slot anytime fall outside the focus blocks; not placed", result["warnings"])
        self.assertIn("activities: meal 2: slot late-evening fall outside the focus blocks; not placed", result["warnings"])
        self.assertFalse(any(activity["kind"] == "meal" for activity in result["activities"]))

    def test_deterministic_under_shuffled_subject_order(self):
        shuffled = copy.deepcopy(self.weights)
        shuffled["subjects"] = dict(reversed(list(shuffled["subjects"].items())))
        self.assertEqual(generate_activities(shuffled, self.grid, QUESTIONNAIRE, DATA["categories"]), self.result)

    def test_baseline_without_subjects_places_nothing(self):
        baseline = baseline_weights()
        result = generate_activities(baseline, baseline["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"], WORKBOOK_DATA["blocks"])
        self.assertEqual(result, {"activities": [], "placedMinutes": {}, "warnings": ["activities: the weights carry no subjects; nothing to place"]})

    def test_one_block_profile_uses_its_flexible_keyed_cell(self):
        weights = derive(subjects_scope_answers())
        result = generate_activities(weights, weights["proposal"]["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"])
        self.assertTrue(result["activities"])
        self.assertEqual({activity["block"] for activity in result["activities"]}, {"flexible"})

    def test_night_owl_meals_follow_wrapping_blocks(self):
        weights = derive(anchored_night_owl_answers())
        result = generate_activities(weights, weights["proposal"]["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"])
        meal_starts = {activity["timing"]["estimatedStart"] for activity in result["activities"] if activity["kind"] == "meal"}
        self.assertEqual(meal_starts, {"07:00"})  # 13:00 and 18:00 fall in the unscheduled block (10:00-20:00)
        self.assertEqual(block_key_for_time(weights["blocks"], "02:00"), [block for block in weights["blocks"] if block["carriesFocus"]][1]["key"])

    def test_meal_plan_titles_the_meals(self):
        weights = derive(meal_plan_answers())
        result = generate_activities(weights, weights["proposal"]["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"])
        titles = {(activity["dayKey"], activity["title"]) for activity in result["activities"] if activity["kind"] == "meal"}
        self.assertIn(("sun-a", "Dinner: Lentil soup"), titles)
        self.assertIn(("wed-b", "Dinner: Lentil soup (leftovers)"), titles)
        self.assertIn(("mon-b", "Snack: Hummus"), titles)
        self.assertIn(("sun-a", "Breakfast"), titles)  # unplanned meals keep their name
        self.assertEqual({activity["kind"] for activity in result["activities"]}, {"session", "practice", "meal"})  # prep/cook come as tasks from ForkKnife, not proposals

    def test_over_committed_cells_are_listed_but_warned(self):
        # The clinic covers the whole early block on Mondays/Wednesdays; the practices there still show, with a warning.
        weights = derive(answers_with(restDays=[], practices=["yoga"], standingAppointments=[clinic(start="06:00", duration_minutes=240)]))
        grid = {day_key: {"early": "spirituality-development", "midday": "working", "late": "cleaning"} for day_key in keys.DAY_KEY_ORDER}
        result = generate_activities(weights, grid, QUESTIONNAIRE, DATA["categories"])
        self.assertTrue(any(activity["kind"] == "practice" and activity["dayKey"] == "mon-a" and activity["block"] == "early" for activity in result["activities"]))
        over = [warning for warning in result["warnings"] if warning.startswith("activities: over-committed by anchors:")]
        self.assertEqual(len(over), 1)
        self.assertIn("Monday A early (45 min of practices/meals, 0 min free)", over[0])  # yoga 15 + the default breakfast 30

    def test_a_max_session_below_the_grid_does_not_hang(self):
        questionnaire = copy.deepcopy(QUESTIONNAIRE)
        questionnaire["generator"]["maxSessionMinutes"] = 5
        result = generate_activities(self.weights, self.grid, questionnaire, DATA["categories"])
        self.assertFalse(any(activity["priority"] == 4 for activity in result["activities"]))  # no spillover could be placed

    def test_proposal_carries_activities_and_validates(self):
        report = ValidationReport()
        check_against_schema_file(self.weights, "weights", report)
        check_weights_references(self.weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), QUESTIONNAIRE, report)
        self.assertTrue(report.ok, report.render())
        self.assertEqual(self.weights["proposal"]["activities"], self.result["activities"])
        self.assertTrue(any(warning.startswith("activities:") for warning in self.weights["proposal"]["warnings"]))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class JavaScriptParityTests(unittest.TestCase):
    """src/lib/shared/generator-rules.js must produce exactly what fk_core/generator.py produces."""

    def run_javascript(self, weights, season_focus=None, blocks=None):
        script = module_import("generator-rules.js", "generateBlockFocusGrid") + STDIN_PRELUDE + """
            process.stdout.write(JSON.stringify(generateBlockFocusGrid(inputs.weights, inputs.questionnaire, { seasonFocus: inputs.seasonFocus, categoryOrder: inputs.categoryOrder, fallbackBlocks: inputs.blocks })));"""
        return run_node(script, {"weights": weights, "questionnaire": QUESTIONNAIRE, "seasonFocus": season_focus, "categoryOrder": DATA["categories"]["order"], "blocks": blocks})

    def assert_parity(self, weights, season_focus=None, blocks=None):
        self.assertEqual(self.run_javascript(weights, season_focus, blocks), generate_block_focus_grid(weights, QUESTIONNAIRE, season_focus, blocks))

    def test_workbook_baseline(self):
        self.assert_parity(baseline_weights(), SPOOKY_SEASON_FOCUS, WORKBOOK_DATA["blocks"])

    def test_default_answers(self):
        self.assert_parity(derive(default_answers(QUESTIONNAIRE, DATA["categories"])), ["meals", "health"])

    def test_one_block_subjects_profile(self):
        self.assert_parity(derive(subjects_scope_answers()))

    def test_anchored_night_owl(self):
        self.assert_parity(derive(anchored_night_owl_answers()))

    def test_energy_peak_and_pins(self):
        self.assert_parity(derive(answers_with(restDays=["saturday"], energyPeak="evening", sentiment={"working": "struggle", "cleaning": "struggle"}, standingAppointments=[clinic(start="06:00", duration_minutes=240)])), SPOOKY_SEASON_FOCUS)

    def test_diff_matches(self):
        script = module_import("generator-rules.js", "diffBlockFocusGrid") + STDIN_PRELUDE + "process.stdout.write(JSON.stringify(diffBlockFocusGrid(inputs.imported, inputs.proposed)));"
        imported = {"sun-a": {"early": "meals", "midday": "cleaning", "afternoon": "working"}}
        proposed = {"sun-a": {"early": "meals", "midday": "working", "late": "cleaning"}, "mon-b": {"early": "meals"}}
        self.assertEqual(run_node(script, {"imported": imported, "proposed": proposed}), diff_block_focus_grid(imported, proposed))

    def run_javascript_activities(self, weights, grid, blocks=None):
        script = module_import("generator-rules.js", "generateActivities") + STDIN_PRELUDE + """
            process.stdout.write(JSON.stringify(generateActivities(inputs.weights, inputs.grid, inputs.questionnaire, { categories: inputs.categories, fallbackBlocks: inputs.blocks })));"""
        return run_node(script, {"weights": weights, "grid": grid, "questionnaire": QUESTIONNAIRE, "categories": DATA["categories"], "blocks": blocks})

    def test_activities_match_on_every_fixture(self):
        for name, weights in (("defaults", derive(default_answers(QUESTIONNAIRE, DATA["categories"]))), ("practices", derive(practices_and_meals_answers())), ("meal plan", derive(meal_plan_answers())),
                              ("night owl", derive(anchored_night_owl_answers())), ("one block", derive(subjects_scope_answers()))):
            grid = weights["proposal"]["blockFocusGrid"]
            self.assertEqual(self.run_javascript_activities(weights, grid), generate_activities(weights, grid, QUESTIONNAIRE, DATA["categories"]), name)
        baseline = baseline_weights()
        self.assertEqual(self.run_javascript_activities(baseline, baseline["blockFocusGrid"], WORKBOOK_DATA["blocks"]), generate_activities(baseline, baseline["blockFocusGrid"], QUESTIONNAIRE, DATA["categories"], WORKBOOK_DATA["blocks"]))

    def test_day_plan_places_proposed_activities(self):
        weights = derive(practices_and_meals_answers())
        script = module_import("day-plan.js", "dayPlan") + STDIN_PRELUDE + """
            const plan = dayPlan({ weights: inputs.weights, answers: inputs.answers, dayKey: "mon-a", days: inputs.days, proposedActivities: inputs.weights.proposal.activities });
            process.stdout.write(JSON.stringify({ blocks: plan.blocks.map((block) => ({ key: block.key, proposed: block.activities.filter((activity) => activity.source === "proposed").map((activity) => [activity.title, activity.start, activity.minutes]) })), unplaced: plan.unplaced.length }));"""
        plan = run_node(script, {"weights": weights, "answers": weights["questionnaire"]["answers"], "days": DATA["days"]})
        placed = {block["key"]: block["proposed"] for block in plan["blocks"]}
        expected = {}
        for activity in weights["proposal"]["activities"]:
            if activity["dayKey"] == "mon-a":
                expected.setdefault(activity["block"], []).append([activity["title"], activity["timing"]["estimatedStart"] if activity["timing"] else None, activity["minutes"]])
        for block_key, items in expected.items():
            self.assertEqual(sorted(map(str, placed[block_key])), sorted(map(str, items)), block_key)
        self.assertEqual(plan["unplaced"], 0)

    def test_weights_from_answers_carry_the_same_proposal(self):
        answers = answers_with(restDays=["saturday"], standingAppointments=[clinic()])
        script = module_import("weights-rules.js", "weightsFromAnswers") + STDIN_PRELUDE + """
            const weights = weightsFromAnswers(inputs.answers, inputs.categories, inputs.questionnaire, { weightsId: "sample", days: inputs.days, seasonFocus: inputs.seasonFocus, seasonId: "spooky-season" });
            process.stdout.write(JSON.stringify(weights.proposal));"""
        javascript = run_node(script, {"answers": answers, "categories": DATA["categories"], "questionnaire": QUESTIONNAIRE, "days": DATA["days"], "seasonFocus": SPOOKY_SEASON_FOCUS})
        self.assertEqual(javascript, derive(answers, season_focus=SPOOKY_SEASON_FOCUS, season_id="spooky-season")["proposal"])


if __name__ == "__main__":
    unittest.main()
