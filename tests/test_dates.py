import datetime
import json
import shutil
import subprocess
import unittest

from helpers import DATA, REPOSITORY_ROOT
from fk_core import astronomy, dates, keys
from fk_core.json_io import read_json
from fk_core.weights import seasons_from_year_split, year_split_from_seasons

RULES_MODULE = REPOSITORY_ROOT / "src" / "lib" / "shared" / "fortknight-rules.js"
ASTRONOMY_MODULE = REPOSITORY_ROOT / "src" / "lib" / "shared" / "astronomy.js"
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "data" / "schema"


def rule(kind, **fields):
    return {"kind": kind, "offsetDays": 0, "snap": None, **fields}


def iso(date):
    return date.isoformat() if date else None


class SeasonRuleTests(unittest.TestCase):
    def test_2026_workbook_season_starts(self):
        expected = {"ostara": "2026-03-08", "fimbulsumar": "2026-04-05", "spooky-season": "2026-09-06", "christmas": "2026-11-01", "hogmanay": "2026-12-27"}
        for season in DATA["seasons"]["seasons"]:
            self.assertEqual(iso(dates.season_start_date(season, 2026)), expected[season["id"]], season["id"])
            self.assertEqual(season["knownStarts"]["2026"], expected[season["id"]])

    def test_easter_known_years(self):
        self.assertEqual(dates.easter_sunday(2024), datetime.date(2024, 3, 31))
        self.assertEqual(dates.easter_sunday(2025), datetime.date(2025, 4, 20))
        self.assertEqual(dates.easter_sunday(2027), datetime.date(2027, 3, 28))

    def test_all_workbook_season_starts_are_sundays(self):
        for year in (2025, 2026, 2027, 2028):
            for start_date, _season in dates.season_starts_for_year(DATA["seasons"]["seasons"], year):
                self.assertEqual(dates.weekday_number_of(start_date), 0, start_date)

    def test_rule_kinds(self):
        self.assertEqual(iso(dates.start_date_for_rule(rule("nth-weekday", month=3, weekday="sunday", occurrence=-1), 2026)), "2026-03-29")
        self.assertEqual(iso(dates.start_date_for_rule(rule("nth-weekday", month=3, weekday="sunday", occurrence=2), 2026)), "2026-03-08")
        self.assertIsNone(dates.start_date_for_rule(rule("fixed-date", month=2, day=29), 2026))
        self.assertEqual(iso(dates.start_date_for_rule(rule("fixed-date", month=2, day=29), 2028)), "2028-02-29")
        self.assertIsNone(dates.start_date_for_rule(rule("fixed-date", month=2, day=30), 2028))
        # snapping can cross the year boundary; the start still counts as that year's
        boxing_day_sunday = rule("fixed-date", month=12, day=26, snap={"weekday": "sunday", "direction": "on-or-after"})
        self.assertEqual(iso(dates.start_date_for_rule(boxing_day_sunday, 2022)), "2023-01-01")
        # offset -1 on Labor Day == the Sunday before it
        labor_day = rule("nth-weekday", month=9, weekday="monday", occurrence=1)
        self.assertEqual(iso(dates.start_date_for_rule({**labor_day, "offsetDays": -1}, 2026)), "2026-09-06")
        self.assertEqual(iso(dates.start_date_for_rule({**labor_day, "snap": {"weekday": "sunday", "direction": "on-or-before"}}, 2026)), "2026-09-06")
        self.assertEqual(iso(dates.start_date_for_rule(rule("easter", snap={"weekday": "monday", "direction": "on-or-after"}), 2026)), "2026-04-06")
        self.assertEqual(iso(dates.start_date_for_rule(rule("manual"), 2026, {"2026": "2026-04-05"})), "2026-04-05")
        self.assertIsNone(dates.start_date_for_rule(rule("manual"), 2027, {"2026": "2026-04-05"}))
        self.assertIsNone(dates.start_date_for_rule(None, 2026))

    def test_solar_terms_match_published_dates(self):
        expected = {
            2025: ["2025-03-20", "2025-06-21", "2025-09-22", "2025-12-21"],
            2026: ["2026-03-20", "2026-06-21", "2026-09-23", "2026-12-21"],
            2027: ["2027-03-20", "2027-06-21", "2027-09-23", "2027-12-22"],
        }
        for year, terms in expected.items():
            self.assertEqual([iso(astronomy.solar_term_date(term, year)) for term in astronomy.SOLAR_TERM_ORDER], terms, year)
        self.assertEqual(iso(dates.start_date_for_rule(rule("solar", term="spring-equinox"), 2026)), "2026-03-20")

    def test_new_moons_match_published_dates(self):
        expected_2026 = ["2026-01-18", "2026-02-17", "2026-03-19", "2026-04-17", "2026-05-16", "2026-06-15",
                         "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-10", "2026-11-09", "2026-12-09"]
        self.assertEqual([iso(date) for date in astronomy.new_moon_dates_in_year(2026)], expected_2026)
        for index, expected in enumerate(expected_2026, start=1):
            self.assertEqual(iso(dates.start_date_for_rule(rule("new-moon", index=index), 2026)), expected)
        self.assertIsNone(dates.start_date_for_rule(rule("new-moon", index=13), 2026))
        moons_2027 = [iso(date) for date in astronomy.new_moon_dates_in_year(2027)]
        self.assertEqual(len(moons_2027), 13)
        self.assertEqual(moons_2027[3], "2027-04-06")  # 23:51 UTC — the tightest real case
        self.assertEqual(moons_2027[12], "2027-12-27")
        self.assertEqual([iso(date) for date in astronomy.new_moon_dates_in_year(2025)][:2], ["2025-01-29", "2025-02-28"])


class DayKeyResolutionTests(unittest.TestCase):
    def test_season_anchored_matches_workbook_start_days(self):
        seasons = DATA["seasons"]["seasons"]
        expectations = {
            "2026-03-08": "sun-b", "2026-04-05": "sun-b", "2026-09-06": "sun-a",
            "2026-11-01": "sun-a", "2026-12-27": "sun-a",
        }
        for iso_date, expected_day_key in expectations.items():
            day_key, _start, _season = dates.day_key_for_date_in_season(datetime.date.fromisoformat(iso_date), seasons)
            self.assertEqual(day_key, expected_day_key, iso_date)

    def test_cycle_wraps_every_fourteen_days(self):
        epoch = datetime.date(2026, 9, 6)
        self.assertEqual(dates.day_key_for_date(epoch + datetime.timedelta(days=14), epoch, "sun-a"), "sun-a")
        self.assertEqual(dates.day_key_for_date(epoch + datetime.timedelta(days=1), epoch, "sun-a"), "mon-b")
        self.assertEqual(dates.day_key_for_date(epoch - datetime.timedelta(days=1), epoch, "sun-a"), "sat-b")

    def test_season_lookup_crosses_year_boundary(self):
        _start, season = dates.season_for_date(DATA["seasons"]["seasons"], datetime.date(2027, 1, 10))
        self.assertEqual(season["id"], "hogmanay")

    def test_person_seasons_skip_unresolvable_years_and_fall_back(self):
        year_split = {"scheme": "custom", "sectionLabel": "era", "sections": [
            {"title": "Spring", "start": {"marker": "date", "description": "", "rule": rule("fixed-date", month=3, day=1)}, "startVariant": "a"},
            {"title": "Rest", "start": {"marker": "manual", "description": "", "rule": rule("manual")}, "startVariant": "b", "knownStarts": {"2026": "2026-11-15"}},
            {"title": "Words only", "start": {"marker": "weather", "description": "first snow", "rule": None}, "startVariant": "a"},
        ]}
        seasons = seasons_from_year_split(year_split, "sunday")
        # the manual section runs from its 2026 date...
        _start, season = dates.season_for_date(seasons, datetime.date(2026, 12, 1))
        self.assertEqual(season["id"], "rest")
        # ...and in 2027 (no typed date) Spring simply continues past November; "Words only" is never current
        _start, season = dates.season_for_date(seasons, datetime.date(2027, 12, 1))
        self.assertEqual(season["id"], "spring")
        self.assertTrue(all(dates.season_for_date(seasons, datetime.date(2027, month, 15))[1]["id"] != "words-only" for month in range(1, 13)))
        # nothing resolvable at all -> None, and the person-first resolver falls back to the workbook
        only_words = seasons_from_year_split({"scheme": "custom", "sectionLabel": "x", "sections": year_split["sections"][2:]}, "sunday")
        self.assertIsNone(dates.season_for_date(only_words, datetime.date(2026, 6, 1)))
        self.assertIsNone(dates.day_key_for_date_in_season(datetime.date(2026, 6, 1), only_words))
        self.assertEqual(dates.day_key_for_date_person_first(datetime.date(2026, 6, 1), only_words, DATA["seasons"]["seasons"]),
                         dates.day_key_for_date_in_season(datetime.date(2026, 6, 1), DATA["seasons"]["seasons"])[0])

    def test_two_sections_on_the_same_date_the_later_one_wins(self):
        year_split = {"scheme": "custom", "sectionLabel": "x", "sections": [
            {"title": "First", "start": {"marker": "date", "description": "", "rule": rule("fixed-date", month=1, day=1)}},
            {"title": "Second", "start": {"marker": "date", "description": "", "rule": rule("fixed-date", month=1, day=1)}},
        ]}
        _start, season = dates.season_for_date(seasons_from_year_split(year_split), datetime.date(2026, 3, 1))
        self.assertEqual(season["id"], "second")

    def test_mid_week_start_keeps_calendar_weekdays_aligned_with_day_keys(self):
        # A Wednesday start with startDayKey mon-a: the fortnight is anchored on the Monday before (mon-a),
        # so that Wednesday is wed-a (two days after mon-a) — never "Monday A" on a Wednesday.
        season = {"id": "x", "name": "x", "startRule": rule("fixed-date", month=3, day=11), "startDayKey": "mon-a", "seasonMode": "mixed", "focus": []}
        self.assertEqual(dates.weekday_number_of(datetime.date(2026, 3, 11)), 3)  # a Wednesday
        day_key, start, _season = dates.day_key_for_date_in_season(datetime.date(2026, 3, 11), [season])
        self.assertEqual((iso(start), day_key), ("2026-03-11", "wed-a"))
        self.assertEqual(iso(dates.season_anchor_date(start, "mon-a")), "2026-03-09")
        self.assertEqual(dates.day_key_for_date_in_season(datetime.date(2026, 3, 16), [season])[0], "mon-b")

    def test_day_key_order_rotation_and_variant_helper(self):
        rotated = keys.day_key_order_starting_on("monday")
        self.assertEqual(rotated[0], "mon-b")
        self.assertEqual(sorted(rotated), sorted(keys.DAY_KEY_ORDER))
        self.assertEqual(rotated[13], "sun-a")
        self.assertEqual(keys.day_key_order_starting_on("sunday"), keys.DAY_KEY_ORDER)
        self.assertEqual(keys.day_key_from_weekday_and_variant("thursday", "b"), "thu-b")
        self.assertEqual(keys.weekday_number("saturday"), 6)


class RuleSchemaTests(unittest.TestCase):
    def test_the_three_rule_schemas_are_identical(self):
        # validate.py has no $ref, so the rule object schema is copied; keep the copies equal (type differs: nullable in sections).
        seasons_rule = read_json(SCHEMA_DIRECTORY / "seasons.schema.json")["properties"]["seasons"]["items"]["properties"]["startRule"]
        questionnaire_rule = read_json(SCHEMA_DIRECTORY / "questionnaire.schema.json")["properties"]["options"]["properties"]["yearSplitSchemes"]["items"]["properties"]["template"]["items"]["properties"]["start"]["properties"]["rule"]
        weights_rule = read_json(SCHEMA_DIRECTORY / "weights.schema.json")["properties"]["yearSplit"]["properties"]["sections"]["items"]["properties"]["start"]["properties"]["rule"]
        strip = lambda schema: {key: value for key, value in schema.items() if key != "type"}
        self.assertEqual(strip(seasons_rule), strip(questionnaire_rule))
        self.assertEqual(strip(seasons_rule), strip(weights_rule))
        self.assertEqual(questionnaire_rule["type"], ["object", "null"])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class JavaScriptParityTests(unittest.TestCase):
    def run_node(self, script, inputs):
        result = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(inputs), capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_astronomy_matches_python_over_a_century_and_a_half(self):
        expected = {str(year): {"solar": [iso(astronomy.solar_term_date(term, year)) for term in astronomy.SOLAR_TERM_ORDER],
                                "moons": [iso(date) for date in astronomy.new_moon_dates_in_year(year)]} for year in range(1950, 2101)}
        script = f"""
            import {{ SOLAR_TERM_ORDER, solarTermDate, newMoonDatesInYear }} from {json.dumps(ASTRONOMY_MODULE.as_uri())};
            const iso = (date) => date.toISOString().slice(0, 10);
            const out = {{}};
            for (let year = 1950; year <= 2100; year += 1) out[String(year)] = {{ solar: SOLAR_TERM_ORDER.map((term) => iso(solarTermDate(term, year))), moons: newMoonDatesInYear(year).map(iso) }};
            process.stdout.write(JSON.stringify(out));
        """
        self.assertEqual(self.run_node(script, {}), expected)

    def test_rules_and_person_seasons_resolve_identically(self):
        rules = [
            rule("fixed-date", month=2, day=29), rule("fixed-date", month=12, day=26, snap={"weekday": "sunday", "direction": "on-or-after"}),
            rule("nth-weekday", month=9, weekday="monday", occurrence=1, snap={"weekday": "sunday", "direction": "on-or-before"}),
            rule("nth-weekday", month=3, weekday="sunday", occurrence=-1), rule("easter", offsetDays=-2),
            rule("solar", term="autumn-equinox", snap={"weekday": "monday", "direction": "on-or-after"}),
            rule("new-moon", index=13), rule("new-moon", index=1, offsetDays=3), rule("manual"),
        ]
        years = [2022, 2024, 2026, 2027, 2028]
        known_starts = {"2026": "2026-04-05"}
        expected_rules = [[iso(dates.start_date_for_rule(candidate, year, known_starts)) for year in years] for candidate in rules]
        person_seasons = seasons_from_year_split(year_split_from_seasons(DATA["seasons"]), "monday")
        sample_dates = [f"2026-{month:02d}-{day:02d}" for month in range(1, 13) for day in (1, 9, 17, 25)] + ["2027-01-03", "2027-01-04"]
        expected_keys = [dates.day_key_for_date_in_season(datetime.date.fromisoformat(text), person_seasons)[0] for text in sample_dates]
        script = f"""
            import {{ startDateForRule, dayKeyForDateInSeason, parseIsoDate, dayKeyOrderStartingOn }} from {json.dumps(RULES_MODULE.as_uri())};
            let text = ""; process.stdin.setEncoding("utf8"); for await (const chunk of process.stdin) text += chunk;
            const inputs = JSON.parse(text);
            const iso = (date) => (date ? date.toISOString().slice(0, 10) : null);
            const rules = inputs.rules.map((candidate) => inputs.years.map((year) => iso(startDateForRule(candidate, year, inputs.knownStarts))));
            const keys = inputs.dates.map((day) => dayKeyForDateInSeason(parseIsoDate(day), inputs.seasons).dayKey);
            process.stdout.write(JSON.stringify({{ rules, keys, rotated: dayKeyOrderStartingOn("monday") }}));
        """
        actual = self.run_node(script, {"rules": rules, "years": years, "knownStarts": known_starts, "seasons": person_seasons, "dates": sample_dates})
        self.assertEqual(actual["rules"], expected_rules)
        self.assertEqual(actual["keys"], expected_keys)
        self.assertEqual(actual["rotated"], keys.day_key_order_starting_on("monday"))


if __name__ == "__main__":
    unittest.main()
