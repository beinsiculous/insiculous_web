"""The invented Champion's keep holds the shape the resolver and writer suites lean on.

These are self-tests of tests/champion_fixture.py: the builder does calendar math on the mason's behalf,
so what it builds is checked here the way the mason's self-checks check the real keep — contiguity,
Sundays on `sun-a`, the pinned year wheel against the calendar it describes.
"""
import datetime
import unittest

from champion_fixture import (DAY_KEY_ORDER, FIRST_DATE, FIRST_SUN_A, LAST_DATE, SEASONS, YEARS,
                              build_champion_keep)

SECTION_KEYS = {
    "meta": {"sourceSlabs", "stones", "foci", "generatedBy", "schemaVersion", "exportedAt", "seasonNote", "assumptions"},
    "categories": {"key", "label", "subjects"},
    "blocks": {"key", "label", "start", "end", "wrapsMidnight", "mealPrimary", "mealSecondary", "sourceRow"},
    "days": {"index", "dayKey", "weekday", "variant", "mainFocus", "mainFocusLabel", "blockFocus", "sourceRow"},
    "seasons": {"key", "name", "gregorianRange", "durationText", "startDescription", "startRule", "startDayKey",
                "safeOutsidePercent", "focus", "typed", "produce", "mealIdeas", "sourceRow"},
    "tasks": {"id", "group", "step", "dayKey", "block", "category", "serves", "sourceRow"},
    "appointments": {"id", "title", "dayKey", "block", "flexibility", "timing", "category", "link", "omitFromKeep", "sourceRow"},
    "menu": {"mealKey", "slot", "cookDay", "leftoversDay", "menu", "cookExtra", "cookExtraNote", "sourceRow"},
    "meals": {"dayKey", "brunch", "snack", "dinner", "sourceRow"},
    "cleaningAreas": {"area", "bagua", "room", "sourceRow"},
    "calendar": {"date", "dayKey", "season", "weekOfSeason", "transition", "transitionTo"},
    "years": {"year", "daysInYear", "daysCovered", "coversWholeYear", "firstDate", "lastDate", "slices"},
}


class ChampionFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keep = build_champion_keep()

    def test_it_carries_the_twelve_sections_with_the_schemas_row_keys(self):
        self.assertEqual(set(self.keep), set(SECTION_KEYS))
        for section, keys in SECTION_KEYS.items():
            rows = [self.keep[section]] if section == "meta" else self.keep[section]
            self.assertTrue(rows, section)
            for row in rows:
                self.assertEqual(set(row), keys, section)
        self.assertEqual([day["dayKey"] for day in self.keep["days"]], DAY_KEY_ORDER)
        self.assertEqual([season["key"] for season in self.keep["seasons"]], [key for key, _ in SEASONS])
        self.assertTrue(any(appointment["omitFromKeep"] for appointment in self.keep["appointments"]),
                        "the writer's withholding needs a marked row to prove itself on")
        self.assertTrue(all(self.keep["meals"][index][slot] for index in range(14) for slot in ("brunch", "snack", "dinner")),
                        "every meal cell is explained by a menu row")

    def test_the_calendar_is_contiguous_and_every_sunday_is_sun_a_or_a_transition(self):
        calendar = self.keep["calendar"]
        self.assertEqual((calendar[0]["date"], calendar[-1]["date"]), (FIRST_DATE, LAST_DATE))
        previous = None
        weekday_names = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
        for entry in calendar:
            date = datetime.date.fromisoformat(entry["date"])
            if previous is not None:
                self.assertEqual(date - previous, datetime.timedelta(days=1), entry["date"])
            previous = date
            if entry["dayKey"] is None:
                self.assertTrue(entry["transition"] and entry["transitionTo"], entry["date"])
                continue
            self.assertFalse(entry["transition"])
            self.assertEqual(entry["dayKey"].split("-")[0], weekday_names[date.isoweekday() % 7], entry["date"])
        self.assertEqual(next(entry["date"] for entry in calendar if entry["dayKey"] == "sun-a"), FIRST_SUN_A)
        self.assertEqual(sum(1 for entry in calendar if entry["transition"]), 14, "two transition weeks")

    def test_the_pinned_year_wheel_matches_the_calendar_it_describes(self):
        [row] = self.keep["years"]
        calendar = self.keep["calendar"]
        self.assertEqual(row, YEARS[0])
        self.assertEqual(row["daysCovered"], len(calendar))
        for slice_row in row["slices"]:
            self.assertEqual(slice_row["days"], sum(1 for entry in calendar if entry["season"] == slice_row["key"]), slice_row["key"])
        self.assertEqual(sum(slice_row["percent"] for slice_row in row["slices"]), 100)
        self.assertEqual(sum(slice_row["sweepDegree"] for slice_row in row["slices"]), 360)
        running = 0
        for slice_row in row["slices"]:
            self.assertEqual(slice_row["startDegree"], running)
            running += slice_row["sweepDegree"]
        # Equal counts wear equal numbers — the largest-remainder property the mason's apportion guarantees.
        by_days = {}
        for slice_row in row["slices"]:
            by_days.setdefault(slice_row["days"], set()).add((slice_row["percent"], slice_row["sweepDegree"]))
        self.assertTrue(all(len(shares) == 1 for shares in by_days.values()), by_days)

    def test_a_serving_counts_forward_around_the_fortnight(self):
        order = DAY_KEY_ORDER
        for task in self.keep["tasks"]:
            for serving in task["serves"]:
                self.assertEqual(serving["daysAfter"], (order.index(serving["dayKey"]) - order.index(task["dayKey"])) % 14, task["id"])
        self.assertTrue(any(task["serves"] for task in self.keep["tasks"]))

    def test_every_call_builds_a_fresh_object(self):
        first, second = build_champion_keep(), build_champion_keep()
        self.assertEqual(first, second)
        self.assertIsNot(first["calendar"], second["calendar"])
