"""Import document version 2: readable commitments/tasks -> canonical records, in Python and JavaScript alike."""
import copy
import json
import re
import shutil
import unittest

from tests.helpers import DATA, REPOSITORY_ROOT, STDIN_PRELUDE, module_import, run_node

from fk_core import keys
from fk_core.derive import default_import_document
from fk_core.import_document import (describe_cadence, import_review_rows, normalize_import_document, parse_clock_time, parse_duration, parse_repeats,
                                     resolve_category, resolve_weekday)
from fk_core.validate import ValidationReport, check_import_document

V2_FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "import.v2.sample.json"
V1_FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "import.sample.json"


def load(path):
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


class ReadableFieldTests(unittest.TestCase):
    def test_repeats_phrases(self):
        self.assertEqual(parse_repeats("every week"), {"cadence": {"kind": "weekly"}})
        self.assertEqual(parse_repeats("Every other week from 2026-09-02"), {"cadence": {"kind": "every-other-week", "firstDate": "2026-09-02"}})
        self.assertEqual(parse_repeats("monthly on the 2nd Tuesday"), {"cadence": {"kind": "monthly-nth-weekday", "nth": 2}, "weekdays": ["tuesday"]})
        self.assertEqual(parse_repeats("monthly on the last friday"), {"cadence": {"kind": "monthly-nth-weekday", "nth": -1}, "weekdays": ["friday"]})
        self.assertEqual(parse_repeats("monthly on day 15"), {"cadence": {"kind": "monthly-date", "dayOfMonth": 15}})
        self.assertEqual(parse_repeats("monthly on the 1st"), {"cadence": {"kind": "monthly-date", "dayOfMonth": 1}})
        self.assertEqual(parse_repeats("once on 2026-10-14"), {"cadence": {"kind": "one-off", "date": "2026-10-14"}})
        self.assertIn("problem", parse_repeats("every other week"))
        self.assertIn("problem", parse_repeats("whenever"))
        self.assertIn("problem", parse_repeats("monthly on day 40"))

    def test_clock_times_and_durations(self):
        self.assertEqual([parse_clock_time(text) for text in ("2:00 PM", "2 pm", "14:00", "9:30am", "12:00 AM", "12:15 pm", "00:05")], ["14:00", "14:00", "14:00", "09:30", "00:00", "12:15", "00:05"])
        self.assertEqual([parse_clock_time(text) for text in ("14", "25:00", "13 pm", "noon", "")], [None] * 5)
        self.assertEqual([parse_duration(text) for text in ("2 h 15 min", "90 min", "1 h", "1.5 h", "45", 45, "10 minutes", "2 hours 5 mins")], [135, 90, 60, 90, 45, 45, 10, 125])
        self.assertEqual([parse_duration(text) for text in ("soon", "", None, "2 x")], [None] * 4)

    def test_weekdays_and_categories(self):
        self.assertEqual([resolve_weekday(text) for text in ("Mon", "tuesday", "Wednesdays", "thu", "Fr", "someday")], ["monday", "tuesday", "wednesday", "thursday", None, None])
        self.assertEqual(resolve_category("Spirituality & Development", DATA["categories"]), "spirituality-development")
        self.assertEqual(resolve_category("friends and family", DATA["categories"]), "friends-family")
        self.assertEqual(resolve_category("health", DATA["categories"]), "health")
        self.assertIsNone(resolve_category("napping", DATA["categories"]))

    def test_cadence_described_back(self):
        self.assertEqual(describe_cadence({"kind": "weekly"}, ["monday", "thursday"]), "every week on Mondays and Thursdays")
        self.assertEqual(describe_cadence({"kind": "monthly-nth-weekday", "nth": -1}, ["friday"]), "monthly on the last Friday")
        self.assertEqual(describe_cadence({"kind": "one-off", "date": "2026-10-14"}), "once on 2026-10-14")


class NormalizeTests(unittest.TestCase):
    def test_v2_fixture_becomes_canonical_appointments_and_tasks(self):
        normalized, problems = normalize_import_document(load(V2_FIXTURE_PATH), DATA["categories"])
        self.assertEqual(problems, [])
        appointments = normalized["standingAppointments"]
        self.assertEqual([appointment["title"] for appointment in appointments], ["Piano lesson", "Choir", "Book club", "Rent", "Dentist"])
        self.assertEqual(appointments[0], {"title": "Piano lesson", "weekdays": ["friday"], "start": "14:00", "durationMinutes": 135, "category": "spirituality-development", "cadence": {"kind": "weekly"}})
        self.assertEqual((appointments[1]["weekdays"], appointments[1]["category"], appointments[1]["cadence"]), (["wednesday"], "spirituality-development", {"kind": "every-other-week", "firstDate": "2026-09-02"}))
        self.assertEqual((appointments[2]["weekdays"], appointments[2]["cadence"]), (["tuesday"], {"kind": "monthly-nth-weekday", "nth": 2}), "the phrase names the weekday")
        self.assertEqual(appointments[4]["cadence"], {"kind": "one-off", "date": "2026-10-14"})
        self.assertEqual(normalized["tasks"][0], {"title": "Take out the bins", "weekdays": ["tuesday"], "cadence": {"kind": "weekly"}, "category": "cleaning", "durationMinutes": 10, "timeOfDay": "evening"})
        self.assertEqual((normalized["tasks"][1]["timeOfDay"], normalized["tasks"][1]["durationMinutes"]), ("anytime", 0))
        self.assertEqual(normalized["commitments"], load(V2_FIXTURE_PATH)["commitments"], "the readable lists travel along unchanged")

    def test_v1_passes_through(self):
        document = load(V1_FIXTURE_PATH)
        normalized, problems = normalize_import_document(document, DATA["categories"])
        self.assertEqual(problems, [])
        self.assertEqual(normalized["standingAppointments"], document["standingAppointments"])
        self.assertEqual(normalized["tasks"], [])

    def test_bad_items_are_reported_and_left_out(self):
        document = load(V2_FIXTURE_PATH)
        document["commitments"][1]["repeats"] = "sometimes"
        document["commitments"][2]["start"] = "seven-ish"
        document["tasks"][0]["category"] = "napping"
        normalized, problems = normalize_import_document(document, DATA["categories"])
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(problems[0].startswith('commitments #2 "Choir": cannot read "sometimes"'))
        self.assertTrue(problems[1].startswith('commitments #3 "Book club": cannot read the start time'))
        self.assertTrue(problems[2].startswith('tasks #1 "Take out the bins": unknown category'))
        self.assertEqual([appointment["title"] for appointment in normalized["standingAppointments"]], ["Piano lesson", "Rent", "Dentist"])
        self.assertEqual([task["title"] for task in normalized["tasks"]], ["Water the plants"])

    def test_unknown_version_is_a_problem(self):
        _, problems = normalize_import_document({"schemaVersion": 3, "source": {"kind": "other"}}, DATA["categories"])
        self.assertEqual(len(problems), 1)
        self.assertIn("schemaVersion 3 is not supported", problems[0])

    def test_check_import_document_accepts_v1_v2_and_the_defaults_and_catches_bad_phrases(self):
        for document in (load(V1_FIXTURE_PATH), load(V2_FIXTURE_PATH), default_import_document(DATA)):
            report = check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport(), DATA["categories"])
            self.assertTrue(report.ok, report.render())
        broken = load(V2_FIXTURE_PATH)
        broken["commitments"][0]["repeats"] = "every blue moon"
        report = check_import_document(broken, set(keys.CATEGORY_KEY_ORDER), ValidationReport(), DATA["categories"])
        self.assertFalse(report.ok)
        self.assertIn("every blue moon", report.render())
        # A version-2 record with an unknown property fails the schema (kept strict so typos surface).
        broken = load(V2_FIXTURE_PATH)
        broken["commitments"][0]["duration"] = "2 h"
        self.assertFalse(check_import_document(broken, set(keys.CATEGORY_KEY_ORDER), ValidationReport(), DATA["categories"]).ok)

    def test_the_spreadsheet_guides_worked_example_is_a_valid_document(self):
        """docs/import-from-spreadsheet.md ends in a worked example; it must always parse cleanly (the assistant copies it)."""
        guide = (REPOSITORY_ROOT / "docs" / "import-from-spreadsheet.md").read_text(encoding="utf-8")
        fenced = re.findall(r"```json\n(.*?)\n```", guide, flags=re.S)
        self.assertEqual(len(fenced), 1, "exactly one JSON block — the assistant is told to answer with exactly one document")
        document = json.loads(fenced[0])
        self.assertEqual(document["schemaVersion"], 2)
        report = check_import_document(document, set(keys.CATEGORY_KEY_ORDER), ValidationReport(), DATA["categories"])
        self.assertTrue(report.ok, report.render())
        normalized, problems = normalize_import_document(document, DATA["categories"])
        self.assertEqual(problems, [])
        self.assertEqual(len(normalized["standingAppointments"]), len(document["commitments"]))
        self.assertEqual(len(normalized["tasks"]), len(document["tasks"]))
        # every "repeats" phrase in the guide's tables is one the parser reads
        for phrase in ("every week", "every other week from 2026-09-02", "monthly on the 2nd tuesday", "monthly on the last friday", "monthly on day 15", "once on 2026-10-14"):
            self.assertNotIn("problem", parse_repeats(phrase), phrase)

    def test_review_rows_read_like_the_document(self):
        rows = import_review_rows(load(V2_FIXTURE_PATH), DATA["categories"])
        self.assertEqual(rows["commitments"][0], {"title": "Piano lesson", "repeats": "every week on Fridays", "start": "2:00 PM", "lasts": "2 h 15 min", "category": "Spirituality & Development"})
        self.assertEqual(rows["commitments"][2]["repeats"], "monthly on the 2nd Tuesday")
        self.assertEqual(rows["tasks"][0], {"title": "Take out the bins", "repeats": "every week on Tuesdays", "when": "evening", "lasts": "10 min", "category": "Cleaning"})
        self.assertEqual(rows["skipped"][0]["title"], "Mom's birthday")
        self.assertEqual(len(rows["review"]), 2)
        self.assertEqual(rows["problems"], [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class JavaScriptParityTests(unittest.TestCase):
    def test_javascript_normalizer_and_review_match_python(self):
        document = load(V2_FIXTURE_PATH)
        document["commitments"][1]["repeats"] = "sometimes"  # one problem, so the wording is compared too
        script = module_import("import-document.js", "normalizeImportDocument", "importReviewRows") + STDIN_PRELUDE + """
            const normalized = normalizeImportDocument(inputs.document, inputs.categories);
            process.stdout.write(JSON.stringify({ normalized: normalized.document, problems: normalized.problems, review: importReviewRows(inputs.document, inputs.categories) }));"""
        javascript = run_node(script, {"document": document, "categories": DATA["categories"]})
        normalized, problems = normalize_import_document(document, DATA["categories"])
        self.assertEqual(javascript["problems"], problems)
        self.assertEqual(javascript["normalized"], normalized)
        self.assertEqual(javascript["review"], import_review_rows(document, DATA["categories"]))

    def test_apply_merges_commitments_and_tasks_into_the_answers_once(self):
        script = module_import("weights-rules.js", "applyImportDocument") + STDIN_PRELUDE + """
            const answers = { standingAppointments: [], tasks: [{ title: "Take out the bins", weekdays: ["tuesday"], cadence: { kind: "weekly" }, timeOfDay: "evening", durationMinutes: 10, category: "cleaning" }] };
            const first = applyImportDocument(answers, inputs.document, inputs.categories.order, inputs.weekdays, null, inputs.categories);
            const second = applyImportDocument(answers, inputs.document, inputs.categories.order, inputs.weekdays, null, inputs.categories);
            process.stdout.write(JSON.stringify({ first, second, answers }));"""
        result = run_node(script, {"document": load(V2_FIXTURE_PATH), "categories": DATA["categories"], "weekdays": keys.WEEKDAY_NAMES})
        self.assertEqual((result["first"]["listed"], result["first"]["added"], result["first"]["tasksListed"], result["first"]["tasksAdded"]), (5, 5, 2, 1), "the hand-typed bins task is the same as the import's")
        self.assertEqual((result["second"]["added"], result["second"]["tasksAdded"]), (0, 0), "applying twice adds nothing")
        self.assertEqual([task["title"] for task in result["answers"]["tasks"]], ["Take out the bins", "Water the plants"])
        self.assertEqual(len(result["answers"]["standingAppointments"]), 5)
        self.assertEqual(result["answers"]["startup"]["import"]["schemaVersion"], 2)

    def test_retry_message_names_the_problems_and_the_offending_records(self):
        document = load(V2_FIXTURE_PATH)
        document["commitments"][1]["repeats"] = "sometimes"
        document["tasks"][0]["category"] = "napping"
        script = module_import("import-document.js", "normalizeImportDocument") + module_import("import-review.js", "retryMessage") + STDIN_PRELUDE + """
            const { problems } = normalizeImportDocument(inputs.document, inputs.categories);
            process.stdout.write(JSON.stringify(retryMessage(problems, inputs.document)));"""
        message = run_node(script, {"document": document, "categories": DATA["categories"]})
        self.assertIn('- commitments #2 "Choir": cannot read "sometimes"', message)
        self.assertIn('- tasks #1 "Take out the bins": unknown category "napping"', message)
        self.assertIn('commitments: {"title":"Choir"', message)
        self.assertIn('tasks: {"title":"Take out the bins"', message)
        self.assertIn("send me the whole import document again", message)

    def test_javascript_field_parsers_match_python(self):
        samples = {"times": ["2:00 PM", "2 pm", "14:00", "9:30am", "12:00 AM", "14", "25:00", ""], "durations": ["2 h 15 min", "90 min", "1.5 h", 45, "soon", "2 hours 5 mins"],
                   "repeats": ["every week", "monthly on the last friday", "monthly on the 1st", "once on 2026-10-14", "every other week", "whenever"]}
        script = module_import("clock.js", "parseClockTime", "parseDuration") + module_import("import-document.js", "parseRepeats") + STDIN_PRELUDE + """
            process.stdout.write(JSON.stringify({ times: inputs.times.map(parseClockTime), durations: inputs.durations.map(parseDuration), repeats: inputs.repeats.map(parseRepeats) }));"""
        javascript = run_node(script, samples)
        self.assertEqual(javascript["times"], [parse_clock_time(text) for text in samples["times"]])
        self.assertEqual(javascript["durations"], [parse_duration(text) for text in samples["durations"]])
        self.assertEqual(javascript["repeats"], [parse_repeats(text) for text in samples["repeats"]])


if __name__ == "__main__":
    unittest.main()
