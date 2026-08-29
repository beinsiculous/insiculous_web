"""Questionnaire answers -> weights: the rule, its validation, and Python/JavaScript parity."""
import copy
import json
import shutil
import subprocess
import unittest

from tests.helpers import DATA, REPOSITORY_ROOT, STDIN_PRELUDE, WORKBOOK_DATA, module_import, run_node

from fk_core import keys
from fk_core.derive import default_import_document
from fk_core.dates import day_key_for_date_in_season, day_key_for_date_person_first, parse_iso_date
from fk_core.validate import ValidationReport, check_against_schema_file, check_import_document, check_weights_references, validate_data
from fk_core.keys import subject_daily_minutes
from fk_core.weights import choose_cuts, default_answers, section_days_from_year_split, round_half_up, seasons_for_answers, seasons_from_year_split, unscheduled_block_from_window, waking_window_from_answer, weights_from_answers, year_split_from_seasons

FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "questionnaire-answers.sample.json"
JAVASCRIPT_MODULE = REPOSITORY_ROOT / "src" / "lib" / "shared" / "weights-rules.js"
IMPORT_FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "import.sample.json"


def resolve_day_key(iso_date):
    """Workbook seasons only (the fixture's own seasons are exercised by the parity test below)."""
    return day_key_for_date_in_season(parse_iso_date(iso_date), DATA["seasons"]["seasons"])[0]


def person_first_resolver(answers):
    person_seasons = seasons_for_answers(answers, DATA["questionnaire"], DATA["categories"])
    return lambda iso_date: day_key_for_date_person_first(parse_iso_date(iso_date), person_seasons, DATA["seasons"]["seasons"])


def load_fixture():
    with open(FIXTURE_PATH, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def derive(answers, **overrides):
    # The workbook activities are passed as extra anchors so the sample fixture keeps its anchor expectations;
    # the app never does this (its anchors are the applied import + standing appointments).
    options = {"weights_id": "sample", "answered_at": "2026-08-15", "activities": WORKBOOK_DATA["activities"]["activities"], "days": DATA["days"], "resolve_day_key": resolve_day_key}
    options.update(overrides)
    return weights_from_answers(answers, DATA["categories"], DATA["questionnaire"], **options)


class ClockDisplayTests(unittest.TestCase):
    """formatClockTime (src/lib/shared/weights-rules.js): stored HH:MM shown to a person as 12-hour clock time."""

    def test_stored_24h_times_display_as_am_pm(self):
        script = module_import("weights-rules.js", "formatClockTime", "formatClockRange") + """
            const times = JSON.parse((await import("node:fs")).readFileSync(0, "utf8"));
            process.stdout.write(JSON.stringify([times.map(formatClockTime), formatClockRange("22:00", "06:00")]));"""
        shown, shown_range = run_node(script, ["00:00", "00:30", "06:15", "12:00", "13:05", "23:59", "not a time", ""])
        self.assertEqual(shown, ["12:00 AM", "12:30 AM", "6:15 AM", "12:00 PM", "1:05 PM", "11:59 PM", "not a time", ""])
        self.assertEqual(shown_range, "10:00 PM–6:00 AM")


class RoundingTests(unittest.TestCase):
    def test_half_up_not_bankers(self):
        self.assertEqual(round_half_up(0.5), 1)
        self.assertEqual(round_half_up(2.5), 3)
        self.assertEqual(round_half_up(0.12345, 4), 0.1235)


class WeightsRuleTests(unittest.TestCase):
    def test_sample_answers_produce_expected_shares(self):
        weights = derive(load_fixture())
        categories = weights["categories"]
        # working: billable 180 + volunteering 300 + typical defaults pr 22.5 + commute 45 (networking peripheral) = 547.5
        # spirituality-development: coaching 45 + conferences 30 + creative 180 + solo 180 + teaching 90 = 525, x1.25 = 656.25
        self.assertGreater(categories["spirituality-development"]["share"], categories["working"]["share"])
        self.assertTrue(categories["spirituality-development"]["wantMore"])
        self.assertEqual(categories["cleaning"]["sentiment"], "struggle")
        self.assertEqual(categories["health"]["sentiment"], "neutral")
        self.assertTrue(categories["meals"]["delegable"])
        self.assertEqual(sorted(key for key, category in categories.items() if category["essential"]), ["health", "operations", "working"])
        self.assertTrue(weights["subjects"]["decoration"]["peripheral"])
        self.assertEqual(weights["subjects"]["laundry"]["minutesPerDay"], {"min": 15, "max": 60})
        self.assertEqual(weights["subjects"]["exercise"], {"minutesPerDay": {"min": 30, "max": 45}, "peripheral": False, "goal": True, "currentMinutesPerDay": 0,
                                                           "everyday": True, "cadence": None, "daysPerPeriod": None, "specificDaysNote": None, "notOftenNote": None})
        self.assertEqual(weights["subjects"]["laundry"]["goal"], False)
        self.assertIsNone(weights["subjects"]["laundry"]["currentMinutesPerDay"])
        self.assertEqual(weights["unscheduledBlock"], {"start": "22:00", "end": "06:00", "minutes": 480})
        self.assertEqual(weights["wakingWindow"], {"start": "06:00", "end": "22:00", "minutesPerDay": 960, "minutesPerCycle": 13440})
        self.assertEqual(weights["source"], "questionnaire")
        self.assertEqual(weights["questionnaire"]["answers"], load_fixture())
        total = sum(category["share"] for category in categories.values()) + weights["flexibleShare"]
        self.assertAlmostEqual(total, 1, delta=0.001)
        for category in categories.values():
            self.assertEqual(category["minutesPerCycle"], round_half_up(category["share"] * 13440))

    def test_peripheral_subject_contributes_nothing(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        for subject_id in DATA["categories"]["categories"]["cleaning"]["subjects"]:
            answers["subjectTime"][subject_id]["peripheral"] = True
        self.assertEqual(derive(answers)["categories"]["cleaning"]["share"], 0)

    def test_shares_are_what_was_declared_and_the_rest_stays_flexible(self):
        """Rule 3: shares do not inflate to fill a window nobody asked to fill."""
        def declared(scale):
            answers = default_answers(DATA["questionnaire"], DATA["categories"])
            for subject_answer in answers["subjectTime"].values():
                minutes = subject_answer["minutesPerDay"]
                subject_answer["minutesPerDay"] = {"min": int(minutes["min"] * scale), "max": int(minutes["max"] * scale)}
            weights = derive(answers)
            asked = sum(subject_daily_minutes(subject_answer) for subject_answer in answers["subjectTime"].values())
            allocated = sum(category["minutesPerCycle"] for category in weights["categories"].values()) / 14
            return asked, allocated, weights["flexibleShare"]

        # A quarter of the typical person's day leaves the rest of the window open, rather than inflating to fill it.
        quarter_asked, quarter_allocated, quarter_flexible = declared(0.25)
        self.assertLess(quarter_asked, 960)
        self.assertAlmostEqual(quarter_allocated, quarter_asked, delta=1)
        self.assertAlmostEqual(quarter_flexible, 1 - quarter_asked / 960, delta=0.001)
        # The typical person now fits inside their window, with room to spare.
        default_asked, default_allocated, default_flexible = declared(1.0)
        self.assertLess(default_asked, 960)
        self.assertGreater(default_flexible, 0.05)
        self.assertAlmostEqual(default_allocated, default_asked, delta=1)
        # Ask for more day than there is and shares scale down to fit it, leaving nothing over.
        over_asked, over_allocated, over_flexible = declared(2.0)
        self.assertGreater(over_asked, 960)
        self.assertAlmostEqual(over_allocated, 960, delta=1)
        self.assertLess(over_flexible, 0.001)

    def test_a_fortnight_cadence_counts_only_the_days_it_happens_on(self):
        """Focus 1's cadence: the slider still means one day, `daysPerPeriod` says how many of the 14."""
        everyday = default_answers(DATA["questionnaire"], DATA["categories"])
        # Stated here rather than taken from a subject's own default, which is free to change with the data.
        laundry = {**everyday["subjectTime"]["laundry"], "everyday": True, "cadence": None, "daysPerPeriod": None}
        midpoint = (laundry["minutesPerDay"]["min"] + laundry["minutesPerDay"]["max"]) / 2
        self.assertEqual(subject_daily_minutes(laundry), midpoint)
        weekly = {**laundry, "everyday": False, "cadence": "fortnight", "daysPerPeriod": 2}
        self.assertEqual(subject_daily_minutes(weekly), midpoint * 2 / 14)
        # A section-cadence subject, like "not often", is done in flexible time and declares nothing.
        seasonal = {**laundry, "everyday": False, "cadence": "section", "daysPerPeriod": 2}
        self.assertEqual(subject_daily_minutes(seasonal), 0)

        # Minutes freed by moving a subject off "everyday" are not handed to the other categories — they stay open.
        modest = copy.deepcopy(everyday)
        modest["subjectTime"]["laundry"] = laundry
        moved = copy.deepcopy(modest)
        moved["subjectTime"]["laundry"] = {**modest["subjectTime"]["laundry"], "everyday": False, "cadence": "section", "daysPerPeriod": 2}
        weights, before = derive(moved), derive(modest)
        self.assertEqual(weights["subjects"]["laundry"]["cadence"], "section")
        self.assertEqual(weights["subjects"]["laundry"]["daysPerPeriod"], 2)
        self.assertLess(weights["categories"]["cleaning"]["share"], before["categories"]["cleaning"]["share"])
        self.assertGreater(weights["flexibleShare"], before["flexibleShare"])
        self.assertEqual(weights["categories"]["working"]["share"], before["categories"]["working"]["share"])

    def test_a_section_is_the_year_shared_between_its_sections(self):
        quarters = default_answers(DATA["questionnaire"], DATA["categories"])["yearSplit"]
        self.assertEqual(len(quarters["sections"]), 4)
        self.assertAlmostEqual(section_days_from_year_split(quarters), 365.25 / 4, places=4)
        self.assertAlmostEqual(section_days_from_year_split({"sections": []}), 365.25, places=4)

    def test_all_peripheral_leaves_every_share_at_zero(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        for subject_answer in answers["subjectTime"].values():
            subject_answer["peripheral"] = True
        weights = derive(answers)
        self.assertEqual(weights["flexibleShare"], 1)
        self.assertTrue(all(category["share"] == 0 for category in weights["categories"].values()))

    def test_a_goal_subject_makes_its_category_want_more(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        plain = derive(answers)
        self.assertFalse(plain["categories"]["meals"]["wantMore"])
        answers["subjectTime"]["cooking"]["goal"] = True
        answers["subjectTime"]["cooking"]["currentMinutesPerDay"] = 0
        boosted = derive(answers)
        self.assertTrue(boosted["categories"]["meals"]["wantMore"])
        self.assertFalse(boosted["categories"]["cleaning"]["wantMore"])
        self.assertGreater(boosted["categories"]["meals"]["share"], plain["categories"]["meals"]["share"])


class SubjectCadenceGateTests(unittest.TestCase):
    """answersProblem is the app's save gate and lives only in JavaScript (docs/app.md)."""

    @unittest.skipIf(shutil.which("node") is None, "node not installed")
    def test_the_save_gate_checks_cadence_day_counts_and_note_length(self):
        script = module_import("weights-rules.js", "answersProblem", "defaultAnswers", "sectionDaysFromYearSplit") + STDIN_PRELUDE + """
            const base = defaultAnswers(inputs.questionnaire, inputs.categories);
            const check = (patch) => {
              const answers = JSON.parse(JSON.stringify(base));
              Object.assign(answers.subjectTime.laundry, patch);
              return answersProblem(answers, inputs.questionnaire, inputs.categories);
            };
            process.stdout.write(JSON.stringify({
              sectionDays: sectionDaysFromYearSplit(base.yearSplit),
              everyday: check({}),
              fortnight: check({ everyday: false, cadence: "fortnight", daysPerPeriod: 3 }),
              wholeFortnight: check({ everyday: false, cadence: "fortnight", daysPerPeriod: 14 }),
              section: check({ everyday: false, cadence: "section", daysPerPeriod: 2 }),
              wholeSection: check({ everyday: false, cadence: "section", daysPerPeriod: 91 }),
              unknownCadence: check({ everyday: false, cadence: "monthly", daysPerPeriod: 2 }),
              wordyCount: check({ everyday: false, cadence: "fortnight", daysPerPeriod: "two" }),
              longNote: check({ specificDaysNote: "x".repeat(301) }),
              okNote: check({ specificDaysNote: "x".repeat(300) }),
            }));
        """
        result = run_node(script, {"questionnaire": DATA["questionnaire"], "categories": DATA["categories"]})
        self.assertAlmostEqual(result["sectionDays"], 365.25 / 4, places=4)
        self.assertIsNone(result["everyday"])
        self.assertIsNone(result["fortnight"])
        self.assertIsNone(result["section"])
        self.assertIsNone(result["okNote"])
        self.assertIn("1–13 days per fortnight", result["wholeFortnight"])
        self.assertIn("1–90 days per section", result["wholeSection"])
        self.assertIn("fortnight, section", result["unknownCadence"])
        self.assertIn("1–13 days per fortnight", result["wordyCount"])
        self.assertIn("300 characters", result["longNote"])


class BlockSplitTests(unittest.TestCase):
    def test_waking_window_may_wrap_and_the_unscheduled_block_is_its_complement(self):
        plain = waking_window_from_answer({"start": "06:00", "end": "22:00"})
        self.assertEqual((plain["start"], plain["end"], plain["minutesPerDay"], plain["minutesPerCycle"]), ("06:00", "22:00", 960, 13440))
        self.assertEqual(unscheduled_block_from_window(plain), {"start": "22:00", "end": "06:00", "minutes": 480})
        wrapped = waking_window_from_answer({"start": "10:00", "end": "02:00"})
        self.assertEqual((wrapped["start"], wrapped["end"], wrapped["minutesPerDay"]), ("10:00", "02:00", 960))
        self.assertEqual(unscheduled_block_from_window(wrapped), {"start": "02:00", "end": "10:00", "minutes": 480})

    def test_waking_window_outside_10_to_18_hours_is_a_problem(self):
        script = module_import("weights-rules.js", "answersProblem", "defaultAnswers") + STDIN_PRELUDE + """
            const answers = defaultAnswers(inputs.questionnaire, inputs.categories);
            const problems = {};
            for (const [name, window] of Object.entries({ nine: { start: "07:00", end: "16:00" }, nineteen: { start: "07:00", end: "02:00" }, ok: { start: "07:00", end: "01:00" }, broken: { start: "7am", end: "22:00" } })) {
                problems[name] = answersProblem({ ...answers, wakingWindow: window }, inputs.questionnaire, inputs.categories);
            }
            process.stdout.write(JSON.stringify(problems));
        """
        problems = run_node(script, {"questionnaire": DATA["questionnaire"], "categories": DATA["categories"]})
        self.assertIn("10–18 hours", problems["nine"])
        self.assertIn("10–18 hours", problems["nineteen"])
        self.assertIsNone(problems["ok"])
        self.assertIn("HH:MM", problems["broken"])

    def test_no_standout_gives_two_blocks(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        # give every category the same raw minutes (and no peripheral subjects) so nothing stands out
        for category_key, category in DATA["categories"]["categories"].items():
            per_subject = 420 / len(category["subjects"])
            for subject_id in category["subjects"]:
                answers["subjectTime"][subject_id] = {"minutesPerDay": {"min": per_subject, "max": per_subject}, "peripheral": False, "more": False}
        answers["agendaScope"] = "subjects"
        weights = derive(answers)
        self.assertEqual(weights["blockSplit"]["standoutCategories"], [])
        self.assertEqual(weights["blockSplit"]["focusBlockCount"], 1)
        self.assertEqual([block["key"] for block in weights["blocks"]], ["unscheduled", "flexible"])
        self.assertEqual(sum(block["durationMinutes"] for block in weights["blocks"]), 1440)

    def test_categories_scope_adds_a_focus_block(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertEqual(answers["agendaScope"], "categories")
        weights = derive(answers, activities=())
        self.assertEqual(weights["blockSplit"]["standoutCategories"], ["working", "health"])
        self.assertEqual(weights["blockSplit"]["agendaScope"], "categories")
        self.assertEqual([block["key"] for block in weights["blocks"]], ["unscheduled", "early", "midday", "late"])
        answers["agendaScope"] = "subjects"
        self.assertEqual([block["key"] for block in derive(answers, activities=())["blocks"]], ["unscheduled", "early", "late"])
        # nothing stands out + categories scope -> flexible earns a companion: early/late
        for category_key, category in DATA["categories"]["categories"].items():
            per_subject = 420 / len(category["subjects"])
            for subject_id in category["subjects"]:
                answers["subjectTime"][subject_id] = {"minutesPerDay": {"min": per_subject, "max": per_subject}, "peripheral": False, "more": False}
        answers["agendaScope"] = "categories"
        self.assertEqual([block["key"] for block in derive(answers, activities=())["blocks"]], ["unscheduled", "early", "late"])
        # the cap holds: four standouts + categories scope still give maxFocusBlocks
        max_focus_blocks = DATA["questionnaire"]["blockSplit"]["maxFocusBlocks"]
        for category_key in ["meals", "cleaning", "working", "health"]:
            for subject_id in DATA["categories"]["categories"][category_key]["subjects"]:
                answers["subjectTime"][subject_id]["minutesPerDay"] = {"min": 600, "max": 600}
        weights = derive(answers, activities=())
        self.assertEqual(weights["blockSplit"]["focusBlockCount"], max_focus_blocks)

    def test_imported_fixed_activities_and_grid_feed_the_split(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertIsNone(answers["startup"]["import"])
        answers["startup"]["import"] = default_import_document(WORKBOOK_DATA)
        weights = derive(answers, activities=())
        self.assertEqual(weights["blockFocusGrid"], {day_key: WORKBOOK_DATA["days"]["days"][day_key]["blockFocus"] for day_key in keys.DAY_KEY_ORDER})
        self.assertEqual(weights["appointmentBlocks"]["sun-a"], "midday")
        import_anchors = [anchor for anchor in weights["blockSplit"]["anchors"] if anchor["source"] == "import"]
        self.assertIn("church--sun-a--early", {anchor["activityId"] for anchor in import_anchors})
        self.assertFalse(any(warning.startswith("blockFocusGrid") for warning in weights["blockSplit"]["warnings"]))
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok, report.render())
        # a 2-focus-block profile drops the workbook's midday cells, once, with a warning
        answers["agendaScope"] = "subjects"
        weights = derive(answers, activities=())
        self.assertEqual([block["key"] for block in weights["blocks"]], ["unscheduled", "early", "late"])
        self.assertTrue(all("midday" not in cells for cells in weights["blockFocusGrid"].values()))
        grid_warnings = [warning for warning in weights["blockSplit"]["warnings"] if warning.startswith("blockFocusGrid")]
        self.assertEqual(len(grid_warnings), 1)
        self.assertIn("midday", grid_warnings[0])
        # an unknown focus value is dropped cell by cell
        answers["startup"]["import"] = copy.deepcopy(default_import_document(WORKBOOK_DATA))
        answers["startup"]["import"]["blockFocusGrid"]["sun-a"]["early"] = "napping"
        weights = derive(answers, activities=())
        self.assertNotIn("early", weights["blockFocusGrid"]["sun-a"])
        self.assertTrue(any("napping" in warning for warning in weights["blockSplit"]["warnings"]))
        # no import: empty grid, no import anchors
        answers["startup"]["import"] = None
        weights = derive(answers, activities=())
        self.assertEqual(weights["blockFocusGrid"], {})
        self.assertEqual(weights["appointmentBlocks"], {})
        self.assertFalse(any(anchor["source"] == "import" for anchor in weights["blockSplit"]["anchors"]))

    def test_sample_answers_split_into_focus_blocks_snapped_to_an_anchor_edge(self):
        weights = derive(load_fixture())
        split = weights["blockSplit"]
        self.assertEqual(split["standoutCategories"], ["working", "spirituality-development"])
        self.assertEqual([block["key"] for block in weights["blocks"]], ["unscheduled", "early", "late"])
        # the even cut (14:00) coincides with the piano-lessons anchor edge and is kept
        self.assertEqual(weights["blocks"][1]["end"], "14:00")
        self.assertTrue(any("date-night" in warning for warning in split["warnings"]))
        self.assertIn("late", weights["categories"]["spirituality-development"]["preferredBlocks"])
        anchor_blocks = {anchor["activityId"]: anchor["block"] for anchor in split["anchors"]}
        self.assertEqual(anchor_blocks["church--sun-a--early"], "early")

    def test_cuts_avoid_straddling_and_prefer_edges(self):
        block_split = DATA["questionnaire"]["blockSplit"]
        anchors = [{"startOffset": 450, "endOffset": 540}]  # covers the ideal cut at 480 (waking 960, 2 blocks)
        cuts = choose_cuts(960, 2, anchors, block_split)
        self.assertEqual(cuts, [450])  # snapped to the anchor's start edge, not inside it
        self.assertEqual(choose_cuts(960, 2, [], block_split), [480])
        self.assertEqual(choose_cuts(960, 4, [], block_split), [240, 480, 720])


class RhythmAndAppointmentTests(unittest.TestCase):
    def test_new_answers_pass_through(self):
        weights = derive(load_fixture())
        self.assertEqual(weights["meals"]["perDay"], 3)
        self.assertEqual(weights["yearSplit"]["scheme"], "custom")
        self.assertEqual(weights["yearSplit"]["sectionLabel"], "era")
        self.assertEqual([section["title"] for section in weights["yearSplit"]["sections"]], ["Planting", "Growing", "Harvest", "Rest"])
        self.assertEqual(weights["yearSplit"]["sections"][2]["start"]["description"], "Labor Day")
        self.assertEqual(weights["yearSplit"]["sections"][2]["start"]["rule"]["kind"], "nth-weekday")
        self.assertEqual(weights["yearSplit"]["sections"][3]["knownStarts"], {"2026": "2026-11-15"})
        self.assertEqual([section["startVariant"] for section in weights["yearSplit"]["sections"]], ["a", "b", "a", "b"])
        self.assertEqual(weights["weekStart"], "monday")
        self.assertEqual(weights["appointmentWeekdays"], ["tuesday", "thursday"])
        self.assertEqual(weights["practices"], ["meditation", "introspection"])
        self.assertEqual(weights["restDays"], ["saturday", "sunday"])
        self.assertEqual(weights["energyPeak"], "morning")
        self.assertEqual(weights["context"], "Two kids at school on weekdays; deep cleaning every other Saturday (week B).")
        self.assertEqual(len(weights["standingAppointments"]), 3)
        self.assertEqual(weights["tasks"], [{"title": "Take out the bins", "weekdays": ["tuesday"], "cadence": {"kind": "weekly"}, "timeOfDay": "evening", "durationMinutes": 10, "category": "cleaning"}])
        self.assertFalse(any(anchor["activityId"].startswith("task--") for anchor in weights["blockSplit"]["anchors"]), "tasks never anchor")

    def test_standing_appointments_become_anchors(self):
        weights = derive(load_fixture())
        anchors = [anchor for anchor in weights["blockSplit"]["anchors"] if anchor["source"] == "standing-appointment"]
        therapy = [anchor for anchor in anchors if anchor["activityId"] == "standing--therapy--1"]
        self.assertEqual(sorted(anchor["dayKey"] for anchor in therapy), ["thu-a", "thu-b", "tue-a", "tue-b"])  # weekly, two weekdays
        self.assertEqual(therapy[0]["end"], "16:30")
        self.assertIn(therapy[0]["block"], [block["key"] for block in weights["blocks"] if block["carriesFocus"]])
        book_club = [anchor for anchor in anchors if anchor["activityId"] == "standing--book-club--2"]
        self.assertEqual(book_club[0]["dayKey"], None)  # monthly -> no day key, still pooled
        choir = [anchor for anchor in anchors if anchor["activityId"] == "standing--choir--3"]
        expected_variant = DATA["days"]["days"][resolve_day_key("2026-10-14")]["variant"]
        self.assertEqual(len(choir), 1)
        self.assertEqual(DATA["days"]["days"][choir[0]["dayKey"]]["variant"], expected_variant)  # every-other-week -> one variant
        self.assertIn(therapy[0]["block"], weights["categories"]["health"]["preferredBlocks"])

    def test_every_other_week_without_resolver_counts_both_weeks(self):
        weights = derive(load_fixture(), resolve_day_key=None)
        choir = [anchor for anchor in weights["blockSplit"]["anchors"] if anchor["activityId"] == "standing--choir--3"]
        self.assertEqual(sorted(anchor["dayKey"] for anchor in choir), ["wed-a", "wed-b"])
        self.assertTrue(any("standing--choir--3" in warning for warning in weights["blockSplit"]["warnings"]))

    def test_cadence_rules_are_caught(self):
        data = copy.deepcopy(DATA)
        profile = derive(load_fixture())
        profile["standingAppointments"][2]["cadence"] = {"kind": "every-other-week"}  # missing firstDate
        profile["standingAppointments"][0]["weekdays"] = []  # weekly needs a weekday
        data["weightsProfiles"] = {"sample": profile}
        report = validate_data(data)
        self.assertTrue(any("needs 'firstDate'" in error for error in report.errors), report.render())
        self.assertTrue(any("at least one weekday" in error for error in report.errors), report.render())

    def test_import_document_contract(self):
        with open(IMPORT_FIXTURE_PATH, encoding="utf-8") as file_handle:
            document = json.load(file_handle)
        report = check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport())
        self.assertTrue(report.ok, report.render())
        document["source"]["kind"] = "carrier-pigeon"
        self.assertFalse(check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport()).ok)
        document["source"]["kind"] = "photo"
        document["blockFocusGrid"]["sun-a"]["midday"] = "meals"  # not one of the document's own focus blocks
        self.assertFalse(check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport()).ok)
        del document["blockFocusGrid"]["sun-a"]["midday"]
        document["fixedActivities"][0]["dayKey"] = "someday"
        self.assertFalse(check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport()).ok)
        # the workbook example's own document validates too, and so does the neutral default
        for data_set in (WORKBOOK_DATA, DATA):
            report = check_import_document(default_import_document(data_set), set(keys.CATEGORY_KEY_ORDER), ValidationReport())
            self.assertTrue(report.ok, report.render())

    def test_year_split_section_count_and_marker_are_checked(self):
        data = copy.deepcopy(DATA)
        profile = derive(load_fixture())
        profile["yearSplit"]["sections"] = profile["yearSplit"]["sections"][:1]  # fewer than 2
        data["weightsProfiles"] = {"sample": profile}
        report = validate_data(data)
        self.assertTrue(any("yearSplit: 1 sections" in error for error in report.errors), report.render())
        profile["yearSplit"]["sections"] = [dict(section, start={"marker": "vibes"}) for section in derive(load_fixture())["yearSplit"]["sections"]]
        report = validate_data(data)
        self.assertTrue(any("marker" in error and "vibes" in error for error in report.errors), report.render())

    def test_custom_scheme_starts_from_the_five_seasons(self):
        year_split = year_split_from_seasons(DATA["seasons"])
        self.assertEqual([section["title"] for section in year_split["sections"]], ["Ostara", "Fimbulsumar", "Spooky Season", "Christmas", "Hogmanay"])
        self.assertEqual(year_split["sections"][4]["start"]["description"], "First Sunday after Christmas Day")
        self.assertEqual(year_split["sections"][4]["start"]["rule"], {"kind": "fixed-date", "month": 12, "day": 26, "offsetDays": 0, "snap": {"weekday": "sunday", "direction": "on-or-after"}})
        self.assertEqual([section["startVariant"] for section in year_split["sections"]], ["b", "b", "a", "a", "a"])
        self.assertEqual(year_split["sections"][0]["knownStarts"], {"2026": "2026-03-08"})
        self.assertEqual([section["durationWeeks"] for section in year_split["sections"]],
                         [{"min": 1, "max": 8}, {"min": 22, "max": 24}, {"min": 9, "max": 10}, {"min": 7, "max": 8}, {"min": 10, "max": 11}])
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        answers["yearSplit"] = year_split
        weights = derive(answers)
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok, report.render())
        # JS twin agrees
        if shutil.which("node"):
            script = f"""
                import {{ yearSplitFromSeasons }} from {json.dumps(JAVASCRIPT_MODULE.as_uri())};
                let text = ""; process.stdin.setEncoding("utf8"); for await (const chunk of process.stdin) text += chunk;
                process.stdout.write(JSON.stringify(yearSplitFromSeasons(JSON.parse(text))));
            """
            result = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(DATA["seasons"]), capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), year_split)

    def test_default_year_split_is_the_quarters_template(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertEqual(answers["yearSplit"]["scheme"], "quarters")
        self.assertEqual([section["title"] for section in answers["yearSplit"]["sections"]], ["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(answers["yearSplit"]["sections"][0]["start"]["rule"], {"kind": "fixed-date", "month": 1, "day": 1, "offsetDays": 0, "snap": None})
        self.assertEqual(answers["weekStart"], "sunday")

    def test_year_split_and_seasons_round_trip_losslessly(self):
        seasons = DATA["seasons"]["seasons"]
        rebuilt = seasons_from_year_split(year_split_from_seasons(DATA["seasons"]), "sunday")
        for original, copy in zip(seasons, rebuilt):
            for field in ("id", "name", "startRule", "startDescription", "startDayKey", "durationWeeks", "knownStarts", "gregorianRange"):
                self.assertEqual(copy[field], original[field], field)
        four_holidays = {"scheme": "custom", "sectionLabel": "x", "sections": [{"title": "Holiday", "start": {"marker": "manual", "description": ""}}] * 4}
        self.assertEqual([season["id"] for season in seasons_from_year_split(four_holidays)], ["holiday", "holiday-2", "holiday-3", "holiday-4"])
        by_monday = seasons_from_year_split(year_split_from_seasons(DATA["seasons"]), "monday")
        self.assertEqual([season["startDayKey"] for season in by_monday], ["mon-b", "mon-b", "mon-a", "mon-a", "mon-a"])

    def test_old_shape_answers_still_derive_with_defaults(self):
        answers = load_fixture()
        for section in answers["yearSplit"]["sections"]:
            section["start"] = {"marker": section["start"]["marker"], "description": section["start"]["description"]}
            section.pop("startVariant", None)
            section.pop("knownStarts", None)
        answers.pop("weekStart")
        answers.pop("agendaScope")
        answers.pop("restDays")
        answers.pop("energyPeak")
        answers.pop("context")
        answers["startup"] = {"groupSize": 1, "importJson": ""}
        weights = derive(answers)
        self.assertEqual(weights["weekStart"], "sunday")
        self.assertEqual(weights["agendaScope"], "categories")
        self.assertEqual(weights["restDays"], ["saturday"])
        self.assertEqual(weights["energyPeak"], "varies")
        self.assertEqual(weights["context"], "")
        self.assertEqual(weights["blockFocusGrid"], {})
        self.assertTrue(all(section["start"]["rule"] is None and section["startVariant"] == "a" for section in weights["yearSplit"]["sections"]))
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok, report.render())

    def test_bad_start_rules_and_week_start_are_caught(self):
        answers = load_fixture()
        answers["yearSplit"]["sections"][0]["start"]["rule"] = {"kind": "fixed-date", "month": 13, "day": 1, "offsetDays": 0, "snap": None}
        answers["yearSplit"]["sections"][1]["start"]["rule"] = {"kind": "new-moon", "index": 14, "offsetDays": 0, "snap": None}
        answers["yearSplit"]["sections"][2]["start"]["rule"] = {"kind": "nth-weekday", "month": 9, "weekday": "funday", "occurrence": 0, "offsetDays": 0, "snap": None}
        answers["yearSplit"]["sections"][3]["knownStarts"] = {"2026": "2027-01-01"}
        answers["weekStart"] = "someday"
        weights = derive(answers)
        report = ValidationReport()
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        errors = "\n".join(report.errors)
        for fragment in ("month 13", "index 14", "unknown weekday 'funday'", "occurrence 0", "not in that year", "unknown weekday 'someday'"):
            self.assertIn(fragment, errors)

    def test_meal_preferences_pass_through_and_missing_ones_mean_the_default(self):
        answers = load_fixture()
        for key in ("eaters", "dietaryRules", "cookingSkill", "kitchenKit"):
            self.assertNotIn(key, answers, "the fixture predates the Fork Knife questionnaire")
        weights = derive(answers)  # a pre-release answers file still derives
        self.assertNotIn("cookingSkill", weights["questionnaire"]["answers"])
        defaults = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertEqual(defaults["cookingSkill"], "comfortable")
        self.assertEqual(defaults["dietaryRules"], [])
        self.assertEqual(defaults["eaters"], 1)
        answers.update({"eaters": 2, "dietaryRules": ["vegan"], "favouriteCuisines": ["thai"], "shoppingCadence": "daily", "favouriteDishes": "Pad thai"})
        weights = derive(answers)
        self.assertEqual(weights["questionnaire"]["answers"]["dietaryRules"], ["vegan"])
        self.assertEqual(weights["questionnaire"]["answers"]["favouriteDishes"], "Pad thai")
        # JavaScript: the same defaults, and answersProblem accepts missing keys but rejects unknown option ids.
        if shutil.which("node"):
            script = module_import("weights-rules.js", "answersProblem", "defaultAnswers") + STDIN_PRELUDE + """
                const defaults = defaultAnswers(inputs.questionnaire, inputs.categories);
                const { cookingSkill, dietaryRules, eaters, ...legacy } = defaults;
                process.stdout.write(JSON.stringify({
                  defaults: { cookingSkill: defaults.cookingSkill, dietaryRules: defaults.dietaryRules, eaters: defaults.eaters, shoppingCadence: defaults.shoppingCadence },
                  legacy: answersProblem(legacy, inputs.questionnaire, inputs.categories),
                  badSkill: answersProblem({ ...defaults, cookingSkill: "chef" }, inputs.questionnaire, inputs.categories),
                  badRule: answersProblem({ ...defaults, dietaryRules: ["vegan", "carnivore"] }, inputs.questionnaire, inputs.categories),
                  badEaters: answersProblem({ ...defaults, eaters: 0 }, inputs.questionnaire, inputs.categories),
                  fine: answersProblem({ ...defaults, dietaryRules: ["vegan"], kitchenKit: ["oven"], favouriteDishes: "Soup" }, inputs.questionnaire, inputs.categories),
                }));
            """
            result = run_node(script, {"questionnaire": DATA["questionnaire"], "categories": DATA["categories"]})
            self.assertEqual(result["defaults"], {"cookingSkill": "comfortable", "dietaryRules": [], "eaters": 1, "shoppingCadence": "weekly"})
            self.assertIsNone(result["legacy"])
            self.assertIn("chef", result["badSkill"])
            self.assertIn("carnivore", result["badRule"])
            self.assertIn("Eaters", result["badEaters"])
            self.assertIsNone(result["fine"])

    def test_select_question_defaults_must_be_members_of_their_option_list(self):
        data = copy.deepcopy(DATA)
        data["questionnaire"]["defaultAnswers"]["cookingSkill"] = "chef"
        data["questionnaire"]["defaultAnswers"]["kitchenKit"] = ["oven", "campfire"]
        report = validate_data(data)
        self.assertTrue(any("cookingSkill" in error and "chef" in error for error in report.errors), report.render())
        self.assertTrue(any("kitchenKit" in error and "campfire" in error for error in report.errors), report.render())
        data = copy.deepcopy(DATA)
        data["questionnaire"]["sections"][-1]["questions"][2]["options"] = "noSuchList"
        report = validate_data(data)
        self.assertTrue(any("noSuchList" in error for error in report.errors), report.render())

    def test_bad_meals_and_weekday_are_caught(self):
        data = copy.deepcopy(DATA)
        profile = derive(load_fixture())
        profile["meals"]["meals"][0]["slots"] = []  # fewer than 1 slot
        profile["standingAppointments"][0]["weekdays"] = ["funday"]
        data["weightsProfiles"] = {"sample": profile}
        report = validate_data(data)
        self.assertFalse(report.ok)
        self.assertTrue(any("funday" in error for error in report.errors), report.render())
        profile["standingAppointments"][0]["weekdays"] = ["tuesday"]
        report = validate_data(data)
        self.assertTrue(any("meals.meals[0]" in error for error in report.errors), report.render())


class TypicalDefaultsTests(unittest.TestCase):
    def test_defaults_are_the_typical_person(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertTrue(answers["subjectTime"]["decoration"]["peripheral"])
        self.assertFalse(answers["subjectTime"]["public-relations-management"]["peripheral"])  # includes social media
        self.assertFalse(answers["subjectTime"]["coaching-mentoring"]["peripheral"])  # includes parenting
        self.assertEqual(answers["subjectTime"]["cooking"]["minutesPerDay"], DATA["questionnaire"]["subjectSliders"]["cooking"]["default"])
        self.assertEqual(answers["essential"], ["health", "working"])
        self.assertEqual(answers["sentiment"], {"working": "struggle", "friends-family": "enjoy"})
        self.assertEqual(answers["delegable"], ["meals"])
        self.assertNotIn("wantMore", answers)
        self.assertEqual(answers["agendaScope"], "categories")
        self.assertIsNone(answers["startup"]["import"])
        weights = derive(answers, activities=())
        self.assertEqual([block["key"] for block in weights["blocks"]], ["unscheduled", "early", "midday", "late"])
        self.assertEqual(weights["subjects"]["decoration"]["peripheral"], True)
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok and not report.warnings, report.render())  # submittable untouched

    def test_default_outside_bounds_is_caught(self):
        data = copy.deepcopy(DATA)
        data["questionnaire"]["subjectSliders"]["cooking"]["default"] = {"min": 0, "max": 999}
        report = validate_data(data)
        self.assertTrue(any("cooking: default" in error for error in report.errors), report.render())


class WeightsValidationTests(unittest.TestCase):
    def test_derived_weights_validate(self):
        weights = derive(load_fixture())
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        self.assertTrue(report.ok, report.render())
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertEqual(report.warnings, [], report.render())

    def test_baseline_still_validates_and_questionnaire_is_loaded(self):
        self.assertIsNotNone(DATA["questionnaire"])
        for data_set in (DATA, WORKBOOK_DATA):
            report = validate_data(data_set)
            self.assertTrue(report.ok, report.render())

    def test_unknown_subject_in_profile_is_caught(self):
        data = copy.deepcopy(DATA)
        profile = derive(load_fixture())
        profile["subjects"]["nope"] = {"minutesPerDay": {"min": 0, "max": 1}, "peripheral": False}
        data["weightsProfiles"] = {"sample": profile}
        report = validate_data(data)
        self.assertFalse(report.ok)
        self.assertTrue(any("weights.sample.subjects: unknown subject nope" in error for error in report.errors), report.render())

    def test_preferred_block_outside_the_profile_blocks_is_caught(self):
        data = copy.deepcopy(DATA)
        profile = derive(load_fixture())
        profile["categories"]["meals"]["preferredBlocks"] = ["midday"]  # this profile only has early/late
        data["weightsProfiles"] = {"sample": profile}
        report = validate_data(data)
        self.assertTrue(any("preferredBlocks 'midday'" in error for error in report.errors), report.render())

    def test_essential_count_out_of_bounds_warns(self):
        answers = load_fixture()
        answers["essential"] = []
        report = ValidationReport()
        check_weights_references(derive(answers), set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(any("essential" in warning for warning in report.warnings), report.render())

    def test_questionnaire_slider_for_unknown_subject_is_caught(self):
        data = copy.deepcopy(DATA)
        data["questionnaire"]["subjectSliders"]["nope"] = {"minutesPerDay": {"min": 0, "max": 60}, "moreMax": 120}
        report = validate_data(data)
        self.assertFalse(report.ok)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class JavaScriptParityTests(unittest.TestCase):
    def test_javascript_port_matches_python(self):
        answers = load_fixture()
        self.assert_parity(answers, WORKBOOK_DATA["activities"]["activities"])

    def test_javascript_port_matches_python_with_the_workbook_import(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        answers["startup"]["import"] = default_import_document(WORKBOOK_DATA)
        answers["startup"]["import"]["blockFocusGrid"]["mon-b"]["late"] = "napping"
        answers["standingAppointments"] = load_fixture()["standingAppointments"]
        self.assert_parity(answers, [])

    def test_javascript_port_matches_python_on_an_under_declared_day(self):
        """The branch where shares stop inflating: a day with room left over."""
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        for subject_answer in answers["subjectTime"].values():
            minutes = subject_answer["minutesPerDay"]
            subject_answer["minutesPerDay"] = {"min": minutes["min"] // 4, "max": minutes["max"] // 4}
        self.assert_parity(answers, [])

    def assert_parity(self, answers, activities):
        expected = derive(answers, activities=activities, resolve_day_key=person_first_resolver(answers))
        inputs = {
            "answers": answers, "categories": DATA["categories"], "questionnaire": DATA["questionnaire"],
            "activities": activities, "days": DATA["days"], "seasons": DATA["seasons"],
        }
        script = f"""
            import {{ weightsFromAnswers, personDayKeyResolver }} from {json.dumps(JAVASCRIPT_MODULE.as_uri())};
            let inputText = "";
            process.stdin.setEncoding("utf8");
            for await (const chunk of process.stdin) inputText += chunk;
            const inputs = JSON.parse(inputText);
            const bundle = {{ seasons: inputs.seasons, days: inputs.days, questionnaire: inputs.questionnaire, categories: inputs.categories }};
            const weights = weightsFromAnswers(inputs.answers, inputs.categories, inputs.questionnaire,
                {{ weightsId: "sample", answeredAt: "2026-08-15", activities: inputs.activities, days: inputs.days,
                   resolveDayKey: personDayKeyResolver(inputs.answers, bundle) }});
            process.stdout.write(JSON.stringify(weights));
        """
        result = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(inputs), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)


if __name__ == "__main__":
    unittest.main()
