"""The resolver (src/lib/champion/resolve.js) driven through node, and checked date-for-date against its Python twin.

The parity test is the point: it runs both implementations over every date the keep can answer for, so a
change to either half that alters what a day renders fails here rather than on the face. The keep is the
invented Champion's keep tests/champion_fixture.py builds — a real one never enters this repository.
"""
import copy
import unittest

import champion_reference as reference
from champion_fixture import (A_DATE_IN_CALENDAR, DATE_BEFORE_CALENDAR, DATE_IN_YEAR_PAST_CALENDAR,
                              DATE_PAST_CALENDAR, FIRST_DATE, LAST_DATE, build_champion_keep)
from helpers import STDIN_PRELUDE, champion_import as module_import, run_node

KEEP = build_champion_keep()

# Times chosen to land in each of the four blocks, including both sides of the midnight wrap.
SAMPLE_TIMES = ["09:30", "12:00", "16:45", "20:00", "03:15"]


class ResolveParityTests(unittest.TestCase):
    def test_every_date_in_the_calendar_resolves_identically_in_both_ports(self):
        dates = [entry["date"] for entry in KEEP["calendar"]]
        # One wall time per date, cycling the samples, so every block wins "current" across the sweep.
        pairs = [(date, SAMPLE_TIMES[index % len(SAMPLE_TIMES)]) for index, date in enumerate(dates)]
        script = module_import("resolve.js", "resolveDay") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.pairs.map(([date, time]) => resolveDay(inputs.keep, date, time))));"
        from_javascript = run_node(script, {"keep": KEEP, "pairs": pairs})
        self.assertEqual(len(from_javascript), len(pairs))
        for (date, time), resolved in zip(pairs, from_javascript):
            with self.subTest(date=date):
                self.assertEqual(resolved, reference.resolve_day(KEEP, date, time))

    def test_dates_outside_the_calendar_expire_identically(self):
        dates = [DATE_BEFORE_CALENDAR, DATE_PAST_CALENDAR, "1999-06-01"]
        script = module_import("resolve.js", "resolveDay") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.dates.map((date) => resolveDay(inputs.keep, date))));"
        from_javascript = run_node(script, {"keep": KEEP, "dates": dates})
        self.assertEqual(from_javascript, [reference.resolve_day(KEEP, date) for date in dates])

    def test_the_menu_and_the_seasons_match_their_twins(self):
        script = module_import("resolve.js", "resolveMenu", "resolveSeasons") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify({menu: resolveMenu(inputs.keep), seasons: resolveSeasons(inputs.keep, inputs.date)}));"
        from_javascript = run_node(script, {"keep": KEEP, "date": A_DATE_IN_CALENDAR})
        self.assertEqual(from_javascript["menu"], reference.resolve_menu(KEEP))
        self.assertEqual(from_javascript["seasons"], reference.resolve_seasons(KEEP, A_DATE_IN_CALENDAR))

    def test_the_year_wheel_matches_its_twin(self):
        dates = [entry["date"] for entry in KEEP["calendar"]][::29] + [
            FIRST_DATE, LAST_DATE,
            DATE_IN_YEAR_PAST_CALENDAR,  # inside a covered year, outside the calendar
            DATE_BEFORE_CALENDAR, DATE_PAST_CALENDAR, None,
        ]
        script = module_import("resolve.js", "resolveYear") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.dates.map((date) => resolveYear(inputs.keep, date))));"
        from_javascript = run_node(script, {"keep": KEEP, "dates": dates})
        self.assertEqual(from_javascript, [reference.resolve_year(KEEP, date) for date in dates])

    def test_the_year_wheel_matches_its_twin_on_keeps_the_exporter_would_never_write(self):
        """The injuries an import can carry. `??` and `or` disagree on 0 and False, and a numeric year would
        stringify differently in the two languages — neither shows up on a healthy keep, and nothing else in
        the suite would catch either."""
        candidates = []
        for injure in (
            lambda keep: keep.pop("years"),
            lambda keep: keep.__setitem__("years", []),
            lambda keep: keep["years"].__setitem__(0, {"year": "2026"}),
            lambda keep: keep["years"][0].update(daysInYear=None, daysCovered=None, coversWholeYear=None,
                                                 firstDate=None, lastDate=None),
            lambda keep: keep["years"][0]["slices"][0].update(days=None, percent=None, startDegree=None,
                                                             sweepDegree=None),
            lambda keep: keep["years"][0].__setitem__("year", 2026),
            lambda keep: keep["years"][0]["slices"][0].__setitem__("key", "not-a-season"),
        ):
            candidate = copy.deepcopy(KEEP)
            injure(candidate)
            candidates.append(candidate)
        script = module_import("resolve.js", "resolveYear") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.keeps.map((keep) => resolveYear(keep, inputs.date))));"
        from_javascript = run_node(script, {"keeps": candidates, "date": A_DATE_IN_CALENDAR})
        self.assertEqual(from_javascript, [reference.resolve_year(keep, A_DATE_IN_CALENDAR) for keep in candidates])

    def test_a_malformed_serving_resolves_identically_in_both_ports(self):
        """The injuries a hand-edited keep can carry inside `serves`: a null entry, and one with no day key.
        JavaScript would drop an undefined label from the JSON where Python writes null; both ports now say
        null. Adversarial review of the move, F5."""
        injured = copy.deepcopy(KEEP)
        prep = next(task for task in injured["tasks"] if task["serves"])
        prep["serves"] = [None, {"role": "cook"}, prep["serves"][0]]
        script = module_import("resolve.js", "taskGroupsFor") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(taskGroupsFor(inputs.keep, inputs.dayKey, inputs.block)));"
        from_javascript = run_node(script, {"keep": injured, "dayKey": prep["dayKey"], "block": prep["block"]})
        self.assertEqual(from_javascript, reference.task_groups_for(injured, prep["dayKey"], prep["block"]))

    def test_a_season_with_no_focus_resolves_identically_in_both_ports(self):
        """resolveDay already tolerated a season without `focus`; resolveSeasons threw. Both ports now
        degrade to an empty list, and the writer's season card survives. Adversarial review of the move, F6."""
        injured = copy.deepcopy(KEEP)
        del injured["seasons"][0]["focus"]
        script = module_import("resolve.js", "resolveSeasons", "resolveDay") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify({seasons: resolveSeasons(inputs.keep, inputs.date), day: resolveDay(inputs.keep, inputs.date, '12:00')}));"
        from_javascript = run_node(script, {"keep": injured, "date": A_DATE_IN_CALENDAR})
        self.assertEqual(from_javascript["seasons"], reference.resolve_seasons(injured, A_DATE_IN_CALENDAR))
        self.assertEqual(from_javascript["day"], reference.resolve_day(injured, A_DATE_IN_CALENDAR, "12:00"))
        self.assertEqual(from_javascript["seasons"][0]["focus"], [])

    def test_carried_tasks_match_their_twin(self):
        """The carry-over list: both ports over a spread of dates, with an empty store and a fixture one."""
        fixture = {CarryOverTests.date_for("wed-b"): [CarryOverTests.task_id("wed-b", "Example scrub the sink")],
                   CarryOverTests.date_for("fri-a"): [CarryOverTests.task_id("fri-a", "Example tidy Friday A")]}
        dates = [entry["date"] for entry in KEEP["calendar"]][::17]
        script = module_import("resolve.js", "carriedTasksFor") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.dates.map((date) => carriedTasksFor(inputs.keep, inputs.checkoffs, date))));"
        for checkoffs in ({}, fixture):
            from_javascript = run_node(script, {"keep": KEEP, "checkoffs": checkoffs, "dates": dates})
            self.assertEqual(from_javascript,
                             [reference.carried_tasks_for(KEEP, checkoffs, date) for date in dates])


class ResolveRuleTests(unittest.TestCase):
    """What the resolver must do, stated once against the Python twin (the parity test binds the JS to it)."""

    def test_a_transition_week_renders_only_its_headline(self):
        transition_dates = [entry["date"] for entry in KEEP["calendar"] if entry["transition"]]
        self.assertTrue(transition_dates, "the keep should contain at least one transition week")
        for date in transition_dates:
            resolved = reference.resolve_day(KEEP, date, "12:00")
            self.assertEqual(resolved["status"], "transition")
            self.assertNotIn("blocks", resolved, "a transition week shows no blocks, tasks or meals")
            self.assertNotIn("meals", resolved)
            self.assertRegex(resolved["headline"], r"^.+ Transitioning to .+$")  # season names are display text; spaces allowed

    def test_a_transition_week_carries_no_day_key(self):
        for entry in KEEP["calendar"]:
            if entry["transition"]:
                self.assertIsNone(entry["dayKey"], entry["date"])
                self.assertIsNotNone(entry["transitionTo"], entry["date"])

    def test_past_the_calendar_it_expires_rather_than_computing(self):
        resolved = reference.resolve_day(KEEP, DATE_PAST_CALENDAR)
        self.assertEqual(resolved["status"], "expired")
        self.assertEqual(resolved["range"], {"first": KEEP["calendar"][0]["date"], "last": KEEP["calendar"][-1]["date"]})

    def test_the_current_block_follows_the_wall_clock_and_wraps_midnight(self):
        date = A_DATE_IN_CALENDAR  # an ordinary day
        expected = {"09:30": "early", "12:00": "midday", "16:45": "late", "20:00": "too-dark", "03:15": "too-dark"}
        for wall_time, block_key in expected.items():
            resolved = reference.resolve_day(KEEP, date, wall_time)
            self.assertEqual(resolved["currentBlock"], block_key, wall_time)
            self.assertEqual([block["key"] for block in resolved["blocks"] if block["isCurrent"]], [block_key])

    def test_without_a_wall_time_no_block_is_current(self):
        resolved = reference.resolve_day(KEEP, A_DATE_IN_CALENDAR)
        self.assertIsNone(resolved["currentBlock"])
        self.assertEqual([block["key"] for block in resolved["blocks"] if block["isCurrent"]], [])

    def test_the_slabs_words_render_verbatim(self):
        """FLEXIBLE and OUT are real values; nothing normalizes them."""
        spoken = {meals[slot] for meals in KEEP["meals"] for slot in ("brunch", "snack", "dinner")}
        self.assertIn("FLEXIBLE", spoken)
        self.assertTrue(any("OUT" in dish for dish in spoken))
        sunday_a = reference.resolve_day(KEEP, self.a_date_for("sun-a"), "12:00")
        self.assertEqual(sunday_a["day"]["mainFocusLabel"], "MEALS")
        self.assertEqual(sunday_a["meals"]["brunch"], "FLEXIBLE")
        midday = next(block for block in sunday_a["blocks"] if block["key"] == "midday")
        self.assertEqual(midday["meal"], {"name": "Brunch", "dish": "FLEXIBLE"})

    def test_each_meal_of_the_day_lands_on_exactly_one_block(self):
        """brunch, snack and dinner appear once each; early's Breakfast has no column on the Meals sheet."""
        for day in KEEP["days"]:
            resolved = reference.resolve_day(KEEP, self.a_date_for(day["dayKey"]), "12:00")
            named = [block["meal"]["name"] for block in resolved["blocks"] if block["meal"]]
            self.assertEqual(named, ["Brunch", "Snack", "Dinner"], day["dayKey"])
            dishes = {block["meal"]["name"]: block["meal"]["dish"] for block in resolved["blocks"] if block["meal"]}
            meals = reference.meals_for_day_key(KEEP, day["dayKey"])
            self.assertEqual(dishes, {"Brunch": meals["brunch"], "Snack": meals["snack"], "Dinner": meals["dinner"]})

    def test_every_task_and_appointment_of_a_day_key_is_reachable_on_some_block(self):
        for day in KEEP["days"]:
            day_key = day["dayKey"]
            resolved = reference.resolve_day(KEEP, self.a_date_for(day_key), "12:00")
            rendered_tasks = {task["id"] for block in resolved["blocks"]
                              for group in block["taskGroups"] for task in group["tasks"]}
            self.assertEqual(rendered_tasks, {task["id"] for task in KEEP["tasks"] if task["dayKey"] == day_key}, day_key)
            rendered_appointments = {appointment["id"] for block in resolved["blocks"]
                                     for appointment in block["appointments"]}
            self.assertEqual(rendered_appointments,
                             {appointment["id"] for appointment in KEEP["appointments"] if appointment["dayKey"] == day_key}, day_key)

    def test_task_ids_for_a_day_key_are_the_rendered_order(self):
        for day in KEEP["days"]:
            resolved = reference.resolve_day(KEEP, self.a_date_for(day["dayKey"]), "12:00")
            rendered = [task["id"] for block in resolved["blocks"]
                        for group in block["taskGroups"] for task in group["tasks"]]
            self.assertEqual(reference.task_ids_for_day_key(KEEP, day["dayKey"]), rendered, day["dayKey"])

    def test_appointments_come_out_earliest_first(self):
        for day in KEEP["days"]:
            resolved = reference.resolve_day(KEEP, self.a_date_for(day["dayKey"]), "12:00")
            for block in resolved["blocks"]:
                starts = [appointment["timing"]["estimatedStart"] for appointment in block["appointments"]]
                self.assertEqual(starts, sorted(starts), (day["dayKey"], block["key"]))

    def test_a_seasons_produce_comes_out_ranked_most_important_first(self):
        """FolkKnowledgeSlab holds produce as {vegetables: {hero, secondary, ...}} — a shape no screen should read."""
        for season in reference.resolve_seasons(KEEP, A_DATE_IN_CALENDAR):
            self.assertTrue(season["produce"], f"{season['key']} lost its produce")
            for group in season["produce"]:
                ranks = [item["rank"] for item in group["items"]]
                self.assertEqual(ranks, reference.PRODUCE_RANKS[:len(ranks)],
                                 f"{season['key']} {group['group']} is out of rank order")
                self.assertEqual(ranks[0], "hero")
                for item in group["items"]:
                    self.assertTrue(item["name"], f"{season['key']} {group['group']} {item['rank']} is empty")
            self.assertEqual([group["label"] for group in season["produce"]], ["Vegetables", "Fruit"], season["key"])

    def test_a_seasons_meal_ideas_come_out_as_named_lines(self):
        for season in reference.resolve_seasons(KEEP, A_DATE_IN_CALENDAR):
            self.assertTrue(season["mealIdeas"], f"{season['key']} lost its meal ideas")
            for idea in season["mealIdeas"]:
                self.assertTrue(idea["name"])
                self.assertIsInstance(idea["text"], str)
                self.assertTrue(idea["text"])

    def test_a_group_with_no_produce_is_dropped_rather_than_rendered_empty(self):
        self.assertEqual(reference.produce_lists({"produce": {"vegetables": {}, "fruit": {"hero": "Mango"}}}),
                         [{"group": "fruit", "label": "Fruit", "items": [{"rank": "hero", "name": "Mango"}]}])
        self.assertEqual(reference.produce_lists({}), [])
        self.assertEqual(reference.meal_idea_lists({"mealIdeas": {"Desserts": "", "Salads": "Caesar"}}),
                         [{"name": "Salads", "text": "Caesar"}])

    def test_outside_the_calendar_no_season_is_marked_current(self):
        self.assertEqual([season["isCurrent"] for season in reference.resolve_seasons(KEEP, DATE_PAST_CALENDAR)],
                         [False] * 5)
        self.assertEqual([season["isCurrent"] for season in reference.resolve_seasons(KEEP)], [False] * 5)

    def test_a_meal_prep_task_says_when_what_it_makes_gets_eaten(self):
        [task] = [task for group in reference.task_groups_for(KEEP, "thu-a", "early")
                  for task in group["tasks"] if task["step"] == "Example smoothies"]
        self.assertEqual(task["serves"], [
            {"role": "cook", "dayKey": "fri-b", "label": "Friday B", "daysAfter": 1},
            {"role": "leftovers", "dayKey": "sun-b", "label": "Sunday B", "daysAfter": 3},
        ])

    def test_only_meal_prep_tasks_carry_serve_days(self):
        by_id = {task["id"]: task for task in KEEP["tasks"]}
        seen_prep_with_serves = False
        for day in KEEP["days"]:
            for block in KEEP["blocks"]:
                for group in reference.task_groups_for(KEEP, day["dayKey"], block["key"]):
                    for task in group["tasks"]:
                        if by_id[task["id"]]["group"] == "Meal Prep & Store":
                            seen_prep_with_serves = seen_prep_with_serves or bool(task["serves"])
                        else:
                            self.assertEqual(task["serves"], [], task["id"])
        self.assertTrue(seen_prep_with_serves)

    def test_a_serving_is_never_before_the_prep_that_makes_it(self):
        """The gap runs forward around the fortnight, so a prep late in the cycle serving early in the next
        reads as "in 2 days" rather than as a negative number or a year of waiting."""
        order = [day["dayKey"] for day in KEEP["days"]]
        for task in KEEP["tasks"]:
            for serving in task["serves"]:
                self.assertEqual(serving["daysAfter"],
                                 (order.index(serving["dayKey"]) - order.index(task["dayKey"])) % 14, task["id"])
                self.assertLess(serving["daysAfter"], 14)

    def test_a_years_slices_are_the_five_seasons_in_wheel_order(self):
        wheel = reference.resolve_year(KEEP, A_DATE_IN_CALENDAR)
        self.assertEqual(wheel["status"], "year")
        self.assertEqual([entry["key"] for entry in wheel["slices"]], [season["key"] for season in KEEP["seasons"]])
        self.assertEqual([entry["name"] for entry in wheel["slices"]], [season["name"] for season in KEEP["seasons"]])

    def test_every_calendar_year_has_a_wheel(self):
        for year in sorted({entry["date"][:4] for entry in KEEP["calendar"]}):
            first = next(entry["date"] for entry in KEEP["calendar"] if entry["date"].startswith(year))
            self.assertEqual(reference.resolve_year(KEEP, first)["status"], "year", year)

    def test_a_years_percents_sum_to_one_hundred_and_its_degrees_to_a_full_circle(self):
        for row in KEEP["years"]:
            wheel = reference.resolve_year(KEEP, row["firstDate"])
            for entry in wheel["slices"]:
                for field in ("days", "percent", "startDegree", "sweepDegree"):
                    # Not merely "a number": a float here means somebody started dividing, and the two ports
                    # would round the halves apart.
                    self.assertIsInstance(entry[field], int, f"{row['year']} {entry['key']} {field}")
            self.assertEqual(sum(entry["percent"] for entry in wheel["slices"]), 100, row["year"])
            self.assertEqual(sum(entry["sweepDegree"] for entry in wheel["slices"]), 360, row["year"])

    def test_a_slice_starts_where_the_one_before_it_ended(self):
        for row in KEEP["years"]:
            running = 0
            for entry in reference.resolve_year(KEEP, row["firstDate"])["slices"]:
                self.assertEqual(entry["startDegree"], running, f"{row['year']} {entry['key']}")
                running += entry["sweepDegree"]
            self.assertEqual(running, 360, row["year"])

    def test_seasons_with_the_same_number_of_days_show_the_same_share(self):
        """The fixture's Longlight and First Frost are both 28 days. Rounding each cumulative boundary
        instead of apportioning by largest remainder can give two rows of the same length different
        numbers, which is what this guards against."""
        for row in KEEP["years"]:
            by_days = {}
            for entry in reference.resolve_year(KEEP, row["firstDate"])["slices"]:
                shares = by_days.setdefault(entry["days"], set())
                shares.add((entry["percent"], entry["sweepDegree"]))
            for days, shares in by_days.items():
                self.assertEqual(len(shares), 1, f"{row['year']}: {days} days shown as {shares}")

    def test_a_bigger_season_never_shows_a_smaller_share(self):
        for row in KEEP["years"]:
            slices = reference.resolve_year(KEEP, row["firstDate"])["slices"]
            ranked = sorted(slices, key=lambda entry: entry["days"])
            for smaller, bigger in zip(ranked, ranked[1:]):
                self.assertLessEqual(smaller["percent"], bigger["percent"], row["year"])
                self.assertLessEqual(smaller["sweepDegree"], bigger["sweepDegree"], row["year"])

    def test_only_the_season_containing_the_date_is_marked_current(self):
        date = A_DATE_IN_CALENDAR
        current = [entry["key"] for entry in reference.resolve_year(KEEP, date)["slices"] if entry["isCurrent"]]
        self.assertEqual(current, [reference.calendar_entry_for_date(KEEP, date)["season"]])

    def test_a_date_inside_a_covered_year_but_past_the_calendar_marks_nothing_current(self):
        """The year has a wheel, but the calendar stops before its end. The last day of that year is in
        the year and out of the calendar, and the wheel must draw without claiming a season."""
        wheel = reference.resolve_year(KEEP, DATE_IN_YEAR_PAST_CALENDAR)
        self.assertEqual(wheel["status"], "year")
        self.assertEqual([entry["isCurrent"] for entry in wheel["slices"]], [False] * 5)

    def test_a_year_the_keep_does_not_carry_comes_back_missing_rather_than_computed(self):
        self.assertEqual(reference.resolve_year(KEEP, DATE_PAST_CALENDAR),
                         {"status": "missing", "year": DATE_PAST_CALENDAR[:4], "daysInYear": None, "daysCovered": 0,
                          "coversWholeYear": False, "firstDate": None, "lastDate": None, "slices": []})
        self.assertEqual(reference.resolve_year(KEEP)["year"], "")

    def test_a_keep_with_no_year_wheels_does_not_throw(self):
        """An older keep has no `years` at all. validateKeep resolves before it accepts, so a resolver that
        threw on the missing section would refuse the keep rather than degrade."""
        older = {key: value for key, value in KEEP.items() if key != "years"}
        self.assertEqual(reference.resolve_year(older, A_DATE_IN_CALENDAR)["status"], "missing")

    def test_a_sparse_year_row_still_resolves(self):
        sparse = dict(KEEP, years=[{"year": "2026"}])
        wheel = reference.resolve_year(sparse, A_DATE_IN_CALENDAR)
        self.assertEqual((wheel["status"], wheel["daysInYear"], wheel["daysCovered"]), ("year", None, 0))
        self.assertEqual((wheel["coversWholeYear"], wheel["slices"]), (False, []))

    @staticmethod
    def a_date_for(day_key):
        """The first date in the calendar carrying this day key — every day key occurs many times."""
        return next(entry["date"] for entry in KEEP["calendar"] if entry["dayKey"] == day_key)


class CarryOverTests(unittest.TestCase):
    """Jesse's carry-over rules, stated against the Python twin (the parity test binds the JS to it):
    unchecked when its day passes = skipped; a skip rides every later Flexible-focus block of the
    fortnight until checked, until the task repeats, or until the fortnight ends."""

    @staticmethod
    def first_full_fortnight():
        """The dates of the first complete fortnight in the calendar — the calendar opens mid-cycle
        (the fixture's first date is a thu-a), so the earliest dates of several day keys belong to that
        clipped fortnight, not this one."""
        start = next(index for index, entry in enumerate(KEEP["calendar"]) if entry["dayKey"] == "sun-a")
        return [entry["date"] for entry in KEEP["calendar"][start:start + 14]]

    @classmethod
    def date_for(cls, day_key):
        """The date carrying this day key in the first full fortnight (day 1 = index 0)."""
        index = next(day["index"] for day in KEEP["days"] if day["dayKey"] == day_key)
        return cls.first_full_fortnight()[index - 1]

    @staticmethod
    def task_id(day_key, step):
        return next(task["id"] for task in KEEP["tasks"]
                    if task["dayKey"] == day_key and task["step"] == step)

    def test_a_skipped_task_surfaces_in_later_flexible_blocks(self):
        """"Example back yard" is assigned mon-b (day 2) and mon-a (day 9); before day 9 arrives, the
        unchecked mon-b instance rides the flex blocks."""
        carried = reference.carried_tasks_for(KEEP, {}, self.date_for("sun-b"))
        task_id = self.task_id("mon-b", "Example back yard")
        entry = next((task for task in carried if task["id"] == task_id), None)
        self.assertIsNotNone(entry, "the skipped mon-b task should be carried on sun-b")
        self.assertEqual(entry["fromWeekday"], "Monday")

    def test_a_checked_task_does_not_surface(self):
        task_id = self.task_id("mon-b", "Example back yard")
        checkoffs = {self.date_for("mon-b"): [task_id]}
        carried = reference.carried_tasks_for(KEEP, checkoffs, self.date_for("sun-b"))
        self.assertNotIn(task_id, [task["id"] for task in carried])

    def test_a_check_from_any_day_in_the_fortnight_counts(self):
        """Checked in a flex block = checked everywhere: the check may be stored under a LATER date
        than the task's own day, and the task still stops resurfacing."""
        task_id = self.task_id("mon-b", "Example back yard")
        checkoffs = {self.date_for("sun-b"): [task_id]}  # checked from sun-b's flex block
        carried = reference.carried_tasks_for(KEEP, checkoffs, self.date_for("tue-b"))
        self.assertNotIn(task_id, [task["id"] for task in carried])

    def test_a_repeat_supersedes_the_skip(self):
        """The sink is assigned wed-b (day 4) and wed-a (day 11): the skipped wed-b instance rides
        until wed-a, then the fresh assignment takes over and the skip is cleared."""
        task_id = self.task_id("wed-b", "Example scrub the sink")
        before = reference.carried_tasks_for(KEEP, {}, self.date_for("tue-b"))
        self.assertIn(task_id, [task["id"] for task in before])
        on_the_repeat = reference.carried_tasks_for(KEEP, {}, self.date_for("wed-a"))
        self.assertNotIn(task_id, [task["id"] for task in on_the_repeat])

    def test_checking_one_instance_leaves_the_repeat_unchecked(self):
        """wed-b's instance checked; wed-a's is a separate id and owes its own check-off."""
        wed_b = self.task_id("wed-b", "Example scrub the sink")
        wed_a = self.task_id("wed-a", "Example scrub the sink")
        self.assertNotEqual(wed_b, wed_a)
        checkoffs = {self.date_for("wed-b"): [wed_b]}
        carried = reference.carried_tasks_for(KEEP, checkoffs, self.date_for("wed-a"))
        self.assertNotIn(wed_b, [task["id"] for task in carried])
        self.assertNotIn(wed_a, [task["id"] for task in carried],
                         "a task assigned today is a row of the day, not a carried one")

    def test_nothing_carries_across_the_fortnight_boundary(self):
        """sun-a opens a new fortnight: with an empty store there is nothing earlier in the window,
        and last fortnight's skips are cleared."""
        fortnight = self.first_full_fortnight()
        self.assertEqual(reference.carried_tasks_for(KEEP, {}, fortnight[0]), [])
        # and a skip from the fortnight's last day does not cross into the next one
        last_day_sat_b = self.task_id("sat-b", "Example fold and put away")
        checkoffs = {}
        next_sun_a = next(entry["date"] for entry in KEEP["calendar"]
                          if entry["date"] > fortnight[-1] and entry["dayKey"] == "sun-a")
        carried = reference.carried_tasks_for(KEEP, checkoffs, next_sun_a)
        self.assertNotIn(last_day_sat_b, [task["id"] for task in carried])

    def test_the_fortnight_window_anchors_on_sun_a_and_clips_to_the_calendar(self):
        fortnight = self.first_full_fortnight()
        self.assertEqual(reference.fortnight_window_for(KEEP, fortnight[10]),  # wed-a, day 11
                         [fortnight[0], fortnight[10]])
        first = KEEP["calendar"][0]["date"]
        self.assertEqual(reference.fortnight_window_for(KEEP, first), [first, first])
