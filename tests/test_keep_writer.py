"""The web-keep writer (src/lib/champion/keep-writer.js): the narrow fortnight beinsiculous.com/fortknight/keep draws.

Driven through node like the rest of src/lib/, over the invented Champion's keep tests/champion_fixture.py
builds. There is no Python twin here and that is deliberate: the twin convention exists where a RULE is
written twice (resolve.js and champion_reference.py), and this module writes no rules — it joins rows the
resolver already resolves.

The test that matters most is test_the_household_s_chores_do_not_travel: the file goes to a public website,
so "no tasks, no calendar, no check-offs" has to be a check rather than a comment. And because the input
here is invented, the conformance test can run in this public repository without ever printing a real
household's schedule into a log.
"""
import json
import sys
import unittest

import champion_reference as reference
from champion_fixture import (A_DATE_IN_CALENDAR, DATE_IN_YEAR_PAST_CALENDAR, DATE_PAST_CALENDAR, LAST_DATE,
                              build_champion_keep)
from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, champion_import as module_import, run_node

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
from fk_core.web_keep import check_web_keep  # noqa: E402

KEEP = build_champion_keep()

# The date the keep is built for: a wed-b inside the calendar.
SAMPLE_DATE = A_DATE_IN_CALENDAR
SAMPLE_EXPORTED_AT = "2026-08-27T18:00:00+00:00"

BUILD_SCRIPT = module_import("keep-writer.js", "buildKeep") + STDIN_PRELUDE + \
    "process.stdout.write(JSON.stringify(buildKeep(inputs.keep, inputs.date, inputs.exportedAt)));"


def build(keep=None, date=SAMPLE_DATE, exported_at=SAMPLE_EXPORTED_AT):
    return run_node(BUILD_SCRIPT, {"keep": keep if keep is not None else KEEP,
                                  "date": date, "exportedAt": exported_at})


class KeepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = build()

    def test_it_names_its_own_format_and_version(self):
        self.assertEqual(self.built["meta"]["format"], "keep")
        self.assertEqual(self.built["meta"]["version"], 1)
        self.assertEqual(self.built["meta"]["exportedAt"], SAMPLE_EXPORTED_AT)

    def test_the_household_s_chores_do_not_travel(self):
        """The file goes to a public website. It carries what is eaten and what is booked; it does not
        carry the chores, the check-offs, the 1095-row calendar or the slab's row numbers."""
        text = json.dumps(self.built)
        for absent in ("tasks", "taskGroups", "calendar", "cleaningAreas", "serves", "sourceRow",
                       "checkoffs", "safeOutsideRaw"):
            self.assertNotIn(f'"{absent}"', text, f"{absent} reached the keep")

    def test_it_is_the_fourteen_day_keys_once_each_in_order(self):
        self.assertEqual([day["dayKey"] for day in self.built["days"]],
                         [day["dayKey"] for day in KEEP["days"]])

    def test_a_day_carries_its_label_week_and_focus(self):
        [thursday] = [day for day in self.built["days"] if day["dayKey"] == "thu-a"]
        self.assertEqual(thursday["label"], "Thursday A")
        self.assertEqual(thursday["week"], 1)
        self.assertEqual(thursday["mainFocus"], reference.day_by_key(KEEP, "thu-a")["mainFocus"])
        self.assertEqual(thursday["mainFocusLabel"], reference.day_by_key(KEEP, "thu-a")["mainFocusLabel"])
        self.assertEqual([day["week"] for day in self.built["days"]], [1] * 7 + [2] * 7)

    def test_every_day_carries_the_four_blocks_in_order_with_their_focus_and_dish(self):
        for day in self.built["days"]:
            self.assertEqual([block["key"] for block in day["blocks"]],
                             [block["key"] for block in KEEP["blocks"]])
            source = reference.day_by_key(KEEP, day["dayKey"])
            for block in day["blocks"]:
                self.assertEqual(block["focus"], source["blockFocus"].get(block["key"]))
                self.assertEqual(block["meal"], reference.meal_for_block(
                    KEEP, day["dayKey"], next(b for b in KEEP["blocks"] if b["key"] == block["key"])))

    def test_the_dishes_are_the_slabs_words(self):
        """FLEXIBLE and OUT are answers, not gaps."""
        for day in self.built["days"]:
            row = reference.meals_for_day_key(KEEP, day["dayKey"])
            self.assertEqual(day["meals"],
                             {"brunch": row["brunch"], "snack": row["snack"], "dinner": row["dinner"]})
        served = {day["meals"]["dinner"] for day in self.built["days"]}
        self.assertTrue(any("OUT" in dish for dish in served), "the keep should still contain an OUT dinner")

    def test_appointments_come_out_flat_in_block_order(self):
        """The order the day happens in — which is block order, not estimated start: an estimated start is
        when to start moving and routinely precedes its own block, and too-dark wraps midnight.

        The expectation carries the same withholding the keep does. Without it this test fails the day
        anything is marked, and "fixing" it by hard-coding would stop it checking the order at all."""
        for day in self.built["days"]:
            expected = [appointment["id"] for block in KEEP["blocks"]
                        for appointment in reference.appointments_for(KEEP, day["dayKey"], block["key"])
                        if not appointment.get("omitFromKeep")]
            self.assertEqual([appointment["id"] for appointment in day["appointments"]], expected)

    def test_a_marked_appointment_is_withheld_and_the_rest_are_not(self):
        """Both directions, because one is not enough. Asserting only that the marked row is gone lets an
        inverted filter — one `!` — withhold every UNMARKED row while keeping the marked one, with this
        suite green and the public page empty. Adversarial review, round 1, F1.

        Invented rather than Jesse's data: the slab column may not exist yet when this runs, and the
        withholding has to be provable before it is ever relied on."""
        marked = json.loads(json.dumps(KEEP))
        victim = next(appointment for appointment in marked["appointments"] if not appointment["omitFromKeep"])
        victim["omitFromKeep"] = True
        survivors = {appointment["id"] for appointment in marked["appointments"] if not appointment["omitFromKeep"]}
        already_marked = [appointment for appointment in KEEP["appointments"] if appointment["omitFromKeep"]]
        self.assertTrue(already_marked, "the fixture carries a marked row of its own")

        built = build(keep=marked)
        kept = {appointment["id"] for day in built["days"] for appointment in day["appointments"]}

        self.assertNotIn(victim["id"], kept, "a marked appointment reached the keep")
        self.assertNotIn(victim["title"], json.dumps(built), "a marked appointment's title reached the keep")
        self.assertEqual(kept, survivors, "the unmarked appointments must all survive")
        for appointment in already_marked:
            self.assertNotIn(appointment["title"], json.dumps(self.built), "the fixture's own marked row reached the keep")

    def test_an_unmarked_keep_keeps_every_appointment(self):
        """The durable half of "the feature changes nothing until you use it".

        An earlier version asserted that nothing in the real slab is marked — a claim about today's
        data dressed as a test of behaviour, which would have gone red on the first legitimate use of
        the feature and invited someone to delete it in the same commit. So: an explicitly unmarked
        keep, which stays true forever."""
        unmarked = json.loads(json.dumps(KEEP))
        for appointment in unmarked["appointments"]:
            appointment["omitFromKeep"] = False
        built = build(keep=unmarked)
        kept = {appointment["id"] for day in built["days"] for appointment in day["appointments"]}
        self.assertEqual(kept, {appointment["id"] for appointment in unmarked["appointments"]})

    def test_a_keep_with_no_menu_exports_an_empty_menu_not_three_empty_slots(self):
        """The empty state has to be reachable from the writer, or the absent-versus-empty distinction
        this whole change is built on is unreachable in practice. resolveMenu always returns its three
        slots, so without this a household with no menu exports something every reader counts as three."""
        no_menu = json.loads(json.dumps(KEEP))
        no_menu["menu"] = []
        self.assertEqual(build(keep=no_menu)["menu"], [])

    def test_an_appointment_keeps_the_timings_the_page_shows_and_nothing_else(self):
        booked = [appointment for day in self.built["days"] for appointment in day["appointments"]]
        self.assertTrue(booked)
        for appointment in booked:
            self.assertEqual(sorted(appointment), ["category", "id", "timing", "title"])

    def test_the_season_and_the_year_are_snapshots_of_the_date_it_was_exported_for(self):
        self.assertEqual(self.built["season"]["key"],
                         reference.calendar_entry_for_date(KEEP, SAMPLE_DATE)["season"])
        self.assertTrue(self.built["season"]["isCurrent"])
        self.assertEqual(self.built["year"]["year"], SAMPLE_DATE[:4])
        self.assertEqual(len(self.built["year"]["slices"]), 5)

    def test_a_date_the_calendar_cannot_answer_yields_no_season_and_no_year(self):
        """The fourteen days are unaffected: they never depended on a date.

        The last day of a covered year is the case that matters and the one an obvious test misses: the
        calendar stops before it, but `years` carries that year's row and resolveYear matches a year by
        its first four characters — so that day has a wheel and no season unless the two are tied."""
        for date in (DATE_PAST_CALENDAR, DATE_IN_YEAR_PAST_CALENDAR):
            with self.subTest(date=date):
                built = build(date=date)
                self.assertIsNone(built["season"])
                self.assertIsNone(built["year"])
                self.assertEqual(len(built["days"]), 14)
        # The calendar's last day is inside it and keeps both.
        answerable = build(date=LAST_DATE)
        self.assertIsNotNone(answerable["season"])
        self.assertEqual(answerable["year"]["year"], LAST_DATE[:4])

    def test_a_sparse_keep_degrades_rather_than_throwing(self):
        sparse = json.loads(json.dumps(KEEP))
        del sparse["meals"][5]
        sparse["appointments"] = []
        built = build(keep=sparse)
        self.assertEqual(len(built["days"]), 14)
        self.assertIn(None, [day["meals"] for day in built["days"]])
        self.assertEqual([appointment for day in built["days"] for appointment in day["appointments"]], [])


CANONICAL_SCHEMA = REPOSITORY_ROOT / "data" / "schema" / "keep.schema.json"


class KeepSchemaTests(unittest.TestCase):
    """What the writer WRITES still matches the schema that describes the format.

    This is the deep half of the format's agreement with its spec. It used to live in the private app
    repository because it validated a keep built from a real household's file, and the checker formats
    offending values into its messages. The input here is invented, so it runs where `npm run verify`
    runs it. Without it, buildKeep could change blocks[].start from "HH:MM" to integer minutes and the
    only documents validated in full would be fixtures a human maintains by hand.
    """

    # Fixed on purpose: one date inside the calendar, one past it, so the null-season path is exercised.
    DATES = (A_DATE_IN_CALENDAR, DATE_PAST_CALENDAR)

    def test_what_the_writer_writes_conforms_to_the_canonical_schema(self):
        for date in self.DATES:
            with self.subTest(date=date):
                report = check_web_keep(build(date=date))
                self.assertTrue(report.ok, report.render())

    def test_the_schema_enum_carries_the_version_the_writer_writes(self):
        """The schema is a third place the format version is written. Asserted on the BUILT keep, not on
        the writer's source text: a bump to KEEP_FORMAT_VERSION that leaves the enum stale fails here."""
        schema = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
        self.assertIn(build()["meta"]["version"], schema["properties"]["meta"]["properties"]["version"]["enum"])

    def test_the_schema_and_the_built_keep_agree_on_the_sections(self):
        """Key names only — a changed field TYPE sails through, which is why the conformance test above
        is the load-bearing one.

        THIS TEST FIRES ON THE ADDITIVE PATH, DELIBERATELY. Adding a section to the keep is not a
        version bump and breaks no reader, so nothing else would notice it — and a format nobody has
        written down is the thing this exists to prevent. So a new section turns this red until the
        schema documents it. If you are here because you added one: add it to data/schema/keep.schema.json
        and docs/keep-format.md, and this goes green. Do not loosen the comparison to a subset check."""
        schema = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
        built = build()
        self.assertEqual(sorted(schema["properties"]), sorted(built))
        day_properties = set(schema["properties"]["days"]["items"]["properties"])
        for day in built["days"]:
            self.assertLessEqual(set(day), day_properties)
