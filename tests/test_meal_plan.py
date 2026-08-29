"""The meal plan (Fork Knife): rules, normalisation of a meal-plan document, coverage, menus, and Python/JavaScript parity."""
import json
import re
import shutil
import unittest

from tests.helpers import DATA, REPOSITORY_ROOT, STDIN_PRELUDE, module_import, run_node

from fk_core import keys
from fk_core.meal_plan import allowed_second_days, can_take_leftovers, coverage, day_key_from_text, day_label, fork_knife_import_document, meal_plan_problem, meal_slug, menu_for_day, merge_meal_plan, normalize_meal_plan, retag_meal_plan, tasks_from_meal_plan
from fk_core.validate import ValidationReport, check_against_schema_file, check_import_document, check_weights_references
from fk_core.weights import default_answers, weights_from_answers

MEALS = [  # an explicit meal set (the questionnaire's defaults are Breakfast / Dinner / Snack)
    {"name": "Breakfast", "slots": ["early-morning"], "needsPrepped": True, "needsCooked": False, "prepMinutes": 15, "cookMinutes": 30},
    {"name": "Lunch", "slots": ["afternoon"], "needsPrepped": True, "needsCooked": True, "prepMinutes": 15, "cookMinutes": 30},
    {"name": "Dinner", "slots": ["evening"], "needsPrepped": True, "needsCooked": True, "prepMinutes": 15, "cookMinutes": 45},
]
DATES = {day_key: f"2026-09-{index + 1:02d}" for index, day_key in enumerate(keys.DAY_KEY_ORDER)}  # any date per day key
DOCUMENT = {
    "schemaVersion": 1, "kind": "meal-plan", "source": {"kind": "test"},
    "items": [
        {"meal": "Lunch", "dish": "Lentil soup", "days": ["Sunday A", "wed-b"], "notes": "double batch"},
        {"meal": "lunch", "dish": "Tacos", "days": ["sat-b", "mon-b"]},
        {"meal": "Lunch", "dish": "Next day", "days": ["mon-a", "tue-b"]},
        {"meal": "Lunch", "dish": "Too late", "days": ["mon-a", "sat-b"]},
        {"meal": "Lunch", "dish": "Overlap", "days": ["Sun_A"]},
        {"meal": "Tea", "dish": "x", "days": ["sun-a"]},
        {"meal": "Dinner", "dish": "", "days": ["sun-a"]},
        {"meal": "Dinner", "dish": "Stew", "days": ["funday-a"]},
        {"meal": "Dinner", "dish": "Curry", "days": ["fri-a", "sun-b", "mon-a"]},
        {"meal": "Breakfast", "dish": "Oats", "days": ["Sunday A"]},
    ],
}


class RuleTests(unittest.TestCase):
    def test_slugs_and_day_keys(self):
        self.assertEqual(meal_slug("Late Snack!"), "late-snack")
        self.assertEqual([day_key_from_text(text) for text in ("sun-a", "Sunday A", "sunday-a", "Sun_A", "SATURDAY b", "monday", "fun-a", "")], ["sun-a", "sun-a", "sun-a", "sun-a", "sat-b", None, None, None])
        self.assertEqual(day_label("wed-b"), "Wednesday B")

    def test_second_serving_is_two_to_four_days_later_and_wraps(self):
        self.assertEqual(allowed_second_days("sun-a"), ["tue-a", "wed-b", "thu-a"])
        self.assertEqual(allowed_second_days("sat-b"), ["mon-b", "tue-a", "wed-b"])
        self.assertEqual(allowed_second_days("fri-a"), ["sun-a", "mon-b", "tue-a"])  # wraps into week 1
        for first in keys.DAY_KEY_ORDER:
            self.assertNotIn(keys.DAY_KEY_ORDER[(keys.DAY_KEY_INDEX[first] + 1) % 14], allowed_second_days(first))

    def test_normalize_keeps_the_good_items_and_names_every_problem(self):
        normalized, problems = normalize_meal_plan(DOCUMENT, MEALS)
        self.assertEqual([item["id"] for item in normalized["items"]], ["lunch--sun-a--wed-b", "lunch--sat-b--mon-b", "breakfast--sun-a"])
        self.assertEqual(normalized["items"][0], {"id": "lunch--sun-a--wed-b", "meal": "lunch", "dish": "Lentil soup", "days": ["sun-a", "wed-b"], "leftoversMeal": None, "notes": "double batch", "needsPrepped": None, "needsCooked": None})
        self.assertEqual(len(problems), 7)
        self.assertIn('item #3 "Next day": leftovers on Tuesday B — after Monday A they may be eaten on Wednesday A, Thursday B, Friday A (never the next day, at most three days later)', problems)
        self.assertIn("item #6 \"x\": unknown meal 'Tea' (your meals: Breakfast, Lunch, Dinner)", problems)
        self.assertIn("item #7: needs a dish", problems)
        self.assertIn("item #8 \"Stew\": cannot read day 'funday-a' (use sun-a … sat-b or Sunday A … Saturday B)", problems)
        self.assertIn('item #9 "Curry": days must list the first serving and optionally the leftovers day', problems)
        self.assertIn('"Overlap" and "Lentil soup" are both Lunch on Sunday A — one dish per meal per day; "Overlap" not applied', problems)
        self.assertEqual(normalize_meal_plan({"items": "no"}, MEALS), ({"items": []}, ["a meal plan needs an items list"]))

    def test_coverage_menu_and_merge(self):
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        cover = coverage(normalized["items"], "lunch")
        self.assertEqual((cover["dishes"], cover["covered"]), (2, 4))
        self.assertNotIn("sun-a", cover["missing"])
        menu = menu_for_day(normalized, MEALS, "wed-b")
        self.assertEqual([(entry["meal"], entry["dish"], entry["leftovers"]) for entry in menu], [("Breakfast", None, False), ("Lunch", "Lentil soup", True), ("Dinner", None, False)])
        merged = merge_meal_plan(normalized["items"], [{"id": "lunch--sun-a--wed-b", "meal": "lunch", "dish": "Minestrone", "days": ["sun-a", "wed-b"], "notes": None}, {"id": "dinner--fri-a", "meal": "dinner", "dish": "Curry", "days": ["fri-a"], "notes": None}])
        self.assertEqual([item["dish"] for item in merged], ["Minestrone", "Tacos", "Oats", "Curry"])
        self.assertIsNone(meal_plan_problem(None, MEALS))
        self.assertIsNone(meal_plan_problem(normalized, MEALS))
        self.assertTrue(meal_plan_problem(normalized, [{"name": "Breakfast"}]).startswith('item #1 "Lentil soup": unknown meal'))

    def test_tasks_from_the_menu_cook_on_the_first_serving_and_prep_the_day_before(self):
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        tasks, review = tasks_from_meal_plan(normalized, MEALS, DATES)
        self.assertEqual([(task["title"], task["weekdays"], task["when"], task["lasts"]) for task in tasks], [
            ("Cook Lentil soup (Lunch)", ["sunday"], "afternoon", "30 min"),
            ("Prep Lentil soup (Lunch)", ["saturday"], "evening", "15 min"),       # Saturday B, the day before Sunday A: the fortnight wraps
            ("Cook Tacos (Lunch)", ["saturday"], "afternoon", "30 min"),
            ("Prep Tacos (Lunch)", ["friday"], "evening", "15 min"),
            ("Prep Oats (Breakfast)", ["saturday"], "evening", "15 min"),         # Breakfast is prepped only: no cook task
        ])
        self.assertEqual(tasks[0]["repeats"], f"every other week from {DATES['sun-a']}")
        self.assertEqual(tasks[1]["repeats"], f"every other week from {DATES['sat-b']}")
        self.assertTrue(all(task["category"] == "meals" for task in tasks))
        self.assertEqual(review[0], "Cook Lentil soup for Lunch on Sunday A (30 min, afternoon); leftovers Wednesday B")
        # Nothing to do on a leftovers day; a meal that needs neither yields no tasks.
        neither = [{**meal, "needsPrepped": False, "needsCooked": False} for meal in MEALS]
        self.assertEqual(tasks_from_meal_plan(normalized, neither, DATES), ([], []))

    def test_a_dish_can_opt_out_of_its_meals_prep_or_cooking(self):
        """needsPrepped / needsCooked false on an item drop that task — and its review line — for that dish alone."""
        document = {"schemaVersion": 1, "kind": "meal-plan", "items": [
            {"meal": "Dinner", "dish": "Stew", "days": ["sun-a"]},                                 # follows the meal
            {"meal": "Dinner", "dish": "Cheese board", "days": ["mon-b"], "needsPrepped": False},   # no prep, still cooked
            {"meal": "Dinner", "dish": "Salad", "days": ["tue-a"], "needsCooked": False},           # no cooking, still prepped
            {"meal": "Dinner", "dish": "Crackers", "days": ["wed-b"], "needsPrepped": False, "needsCooked": False},
        ]}
        normalized, problems = normalize_meal_plan(document, MEALS)
        self.assertEqual(problems, [])
        self.assertEqual([(item["needsPrepped"], item["needsCooked"]) for item in normalized["items"]],
                         [(None, None), (False, None), (None, False), (False, False)])
        tasks, review = tasks_from_meal_plan(normalized, MEALS, DATES)
        self.assertEqual([task["title"] for task in tasks], [
            "Cook Stew (Dinner)", "Prep Stew (Dinner)",
            "Cook Cheese board (Dinner)",   # opted out of prep only
            "Prep Salad (Dinner)",          # opted out of cooking only
        ])                                   # Crackers opted out of both and yields nothing
        # The review never disagrees with the tasks: one line per task, in the same order.
        self.assertEqual(len(review), len(tasks))
        self.assertTrue(all(line.startswith(task["title"].split(" ")[0]) for task, line in zip(tasks, review)))
        # An explicit true is just "as the meal says", and cannot add a step the meal does not have.
        opted_in = {"schemaVersion": 1, "kind": "meal-plan", "items": [
            {"meal": "Breakfast", "dish": "Oats", "days": ["sun-a"], "needsCooked": True},
        ]}
        opted_in_normalized, _ = normalize_meal_plan(opted_in, MEALS)
        opted_in_tasks, _ = tasks_from_meal_plan(opted_in_normalized, MEALS, DATES)
        self.assertEqual([task["title"] for task in opted_in_tasks], ["Prep Oats (Breakfast)"])  # Breakfast never cooks

    def test_the_opt_out_survives_the_fork_knife_document_round_trip(self):
        """The document Fork Knife writes carries the overrides, so re-applying it does not resurrect the tasks."""
        document = {"schemaVersion": 1, "kind": "meal-plan", "items": [
            {"meal": "Dinner", "dish": "Crackers", "days": ["wed-b"], "needsPrepped": False, "needsCooked": False},
        ]}
        normalized, _ = normalize_meal_plan(document, MEALS)
        written = fork_knife_import_document(normalized, MEALS, DATES)
        self.assertEqual(written["tasks"], [])
        self.assertEqual(written["mealPlan"]["items"][0]["needsPrepped"], False)
        self.assertEqual(written["mealPlan"]["items"][0]["needsCooked"], False)
        report = ValidationReport()
        check_import_document(written, set(keys.CATEGORY_KEY_ORDER), report, DATA["categories"])
        self.assertTrue(report.ok, report.render())
        again, _ = normalize_meal_plan(written["mealPlan"], MEALS)
        self.assertEqual(tasks_from_meal_plan(again, MEALS, DATES), ([], []))

    def test_the_fork_knife_document_is_a_valid_import_document(self):
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        document = fork_knife_import_document(normalized, MEALS, DATES)
        self.assertEqual((document["schemaVersion"], document["source"]["kind"], len(document["tasks"]), len(document["mealPlan"]["items"])), (2, "fork-knife", 5, 3))
        report = ValidationReport()
        check_import_document(document, set(keys.CATEGORY_KEY_ORDER), report, DATA["categories"])
        self.assertTrue(report.ok, report.render())

    def test_renamed_meals_keep_their_dishes_and_unnamed_meals_read_as_meal_n(self):
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        retagged = retag_meal_plan(normalized, {"lunch": "brunch"})
        self.assertEqual([item["id"] for item in retagged["items"]], ["brunch--sun-a--wed-b", "brunch--sat-b--mon-b", "breakfast--sun-a"])
        self.assertEqual(retagged["items"][0]["meal"], "brunch")
        self.assertEqual(retag_meal_plan(normalized, {}), normalized)
        # A profile saved before meals had names: derivation takes the default meal at the same position (Breakfast,
        # Dinner, Snack, then "Meal n"); a raw weights file without names reads as "Meal n".
        old_meals = [{"slots": ["early-morning"]}, {"slots": ["afternoon"]}, {"slots": ["evening"]}, {"slots": ["anytime"]}]
        self.assertEqual([entry["meal"] for entry in menu_for_day({"items": []}, old_meals[:2], "sun-a")], ["Meal 1", "Meal 2"])
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        answers["meals"] = {"perDay": 4, "meals": old_meals}
        weights = weights_from_answers(answers, DATA["categories"], DATA["questionnaire"], weights_id="old", days=DATA["days"])
        self.assertEqual([(meal["name"], meal["needsPrepped"], meal["needsCooked"]) for meal in weights["meals"]["meals"]], [("Breakfast", False, True), ("Dinner", True, True), ("Snack", True, False), ("Meal 4", False, False)])
        old_meals = old_meals[:2]
        report = ValidationReport()
        check_against_schema_file({**weights, "meals": {"perDay": 2, "meals": old_meals}}, "weights", report)  # a file written before names
        check_weights_references({**weights, "meals": {"perDay": 2, "meals": old_meals}}, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok, report.render())

    def test_leftovers_may_move_from_a_later_meal_to_an_earlier_one(self):
        meals = DATA["questionnaire"]["defaultAnswers"]["meals"]["meals"]  # Breakfast early-morning, Dinner evening, Snack afternoon
        breakfast, dinner, snack = meals
        self.assertTrue(can_take_leftovers(dinner, breakfast))
        self.assertTrue(can_take_leftovers(dinner, snack))
        self.assertTrue(can_take_leftovers(snack, breakfast))   # afternoon -> early morning
        self.assertFalse(can_take_leftovers(breakfast, dinner))  # a morning meal's leftovers do not move on
        self.assertTrue(can_take_leftovers(breakfast, breakfast))
        document = {"schemaVersion": 1, "kind": "meal-plan", "items": [
            {"meal": "Dinner", "dish": "Curry", "days": ["sun-a", "tue-a"], "leftoversMeal": "Breakfast"},
            {"meal": "Dinner", "dish": "Stew", "days": ["mon-b", "wed-b"], "leftoversMeal": "dinner"},      # same meal spelled out: plain leftovers
            {"meal": "Breakfast", "dish": "Oats", "days": ["thu-a", "sat-a"], "leftoversMeal": "Dinner"},   # refused
            {"meal": "Breakfast", "dish": "Eggs", "days": ["tue-a"]},                                       # taken by Curry's leftovers
            {"meal": "Snack", "dish": "Nuts", "days": ["fri-b", "sun-b"], "leftoversMeal": "Tea"},          # unknown
        ]}
        normalized, problems = normalize_meal_plan(document, meals)
        self.assertEqual([item["id"] for item in normalized["items"]], ["dinner--sun-a--breakfast--tue-a", "dinner--mon-b--wed-b"])
        self.assertEqual(normalized["items"][0]["leftoversMeal"], "breakfast")
        self.assertIsNone(normalized["items"][1]["leftoversMeal"])
        self.assertEqual(len(problems), 3)
        self.assertTrue(problems[0].startswith('item #3 "Oats": Breakfast leftovers cannot be Dinner'))
        self.assertTrue(problems[1].startswith('item #5 "Nuts": unknown leftovers meal'))
        self.assertIn('"Eggs" and "Curry" are both Breakfast on Tuesday A', problems[2])
        self.assertEqual(coverage(normalized["items"], "breakfast"), {"dishes": 0, "covered": 1, "missing": [day for day in keys.DAY_KEY_ORDER if day != "tue-a"]})
        self.assertEqual([(entry["dish"], entry["leftovers"]) for entry in menu_for_day(normalized, meals, "tue-a")], [("Curry", True), (None, False), (None, False)])
        retagged = retag_meal_plan(normalized, {"breakfast": "brekkie"})
        self.assertEqual(retagged["items"][0]["id"], "dinner--sun-a--brekkie--tue-a")
        _, review = tasks_from_meal_plan(normalized, meals, DATES)
        self.assertEqual(review[0], "Cook Curry for Dinner on Sunday A (45 min, evening); leftovers Tuesday A as Breakfast")

    def test_the_docs_worked_example_is_a_valid_document(self):
        text = (REPOSITORY_ROOT / "docs" / "meal-plan.md").read_text(encoding="utf-8")
        example = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
        report = ValidationReport()
        check_against_schema_file(example, "meal-plan", report)
        self.assertTrue(report.ok, report.render())
        normalized, problems = normalize_meal_plan(example, MEALS)
        self.assertEqual(problems, [])
        self.assertEqual(len(normalized["items"]), 5)

    def test_weights_carry_meals_with_names_and_the_plan_and_validate(self):
        answers = default_answers(DATA["questionnaire"], DATA["categories"])
        self.assertEqual([(meal["name"], meal["needsPrepped"], meal["needsCooked"]) for meal in answers["meals"]["meals"]], [("Breakfast", False, True), ("Dinner", True, True), ("Snack", True, False)])
        answers["meals"] = {"perDay": 3, "meals": MEALS}
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        answers["mealPlan"] = normalized
        weights = weights_from_answers(answers, DATA["categories"], DATA["questionnaire"], weights_id="sample", days=DATA["days"])
        self.assertEqual([meal["name"] for meal in weights["meals"]["meals"]], ["Breakfast", "Lunch", "Dinner"])
        self.assertEqual(weights["meals"]["meals"][0], {"name": "Breakfast", "slots": ["early-morning"], "needsPrepped": True, "needsCooked": False, "prepMinutes": 15, "cookMinutes": 30})
        self.assertEqual(weights["mealPlan"], normalized)
        report = ValidationReport()
        check_against_schema_file(weights, "weights", report)
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(report.ok, report.render())
        # A renamed meal orphans its items; a duplicate name is an error.
        weights["meals"]["meals"][1]["name"] = "Brunch"
        report = ValidationReport()
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(any("mealPlan" in error and "unknown meal 'lunch'" in error for error in report.errors), report.render())
        weights["meals"]["meals"][1]["name"] = "breakfast"
        report = ValidationReport()
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(DATA["categories"]["subjects"]), DATA["questionnaire"], report)
        self.assertTrue(any("already used" in error for error in report.errors), report.render())


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class JavaScriptParityTests(unittest.TestCase):
    def test_normalize_coverage_menu_and_allowed_days_match(self):
        script = module_import("meal-plan.js", "normalizeMealPlan", "allowedSecondDays", "coverage", "menuForDay", "mergeMealPlan", "mealPlanProblem") + STDIN_PRELUDE + """
            const { normalized, problems } = normalizeMealPlan(inputs.document, inputs.meals);
            process.stdout.write(JSON.stringify({ normalized, problems, allowed: ["sun-a", "sat-b", "fri-a"].map(allowedSecondDays), coverage: coverage(normalized.items, "lunch"),
              menu: menuForDay(normalized, inputs.meals, "wed-b"), merged: mergeMealPlan(normalized.items, inputs.extra), problem: mealPlanProblem(normalized, [{ name: "Breakfast" }]) }));"""
        extra = [{"id": "lunch--sun-a--wed-b", "meal": "lunch", "dish": "Minestrone", "days": ["sun-a", "wed-b"], "notes": None}]
        javascript = run_node(script, {"document": DOCUMENT, "meals": MEALS, "extra": extra})
        normalized, problems = normalize_meal_plan(DOCUMENT, MEALS)
        self.assertEqual(javascript["normalized"], normalized)
        self.assertEqual(javascript["problems"], problems)
        self.assertEqual(javascript["allowed"], [allowed_second_days(day) for day in ("sun-a", "sat-b", "fri-a")])
        self.assertEqual(javascript["coverage"], coverage(normalized["items"], "lunch"))
        self.assertEqual(javascript["menu"], menu_for_day(normalized, MEALS, "wed-b"))
        self.assertEqual(javascript["merged"], merge_meal_plan(normalized["items"], extra))
        self.assertEqual(javascript["problem"], meal_plan_problem(normalized, [{"name": "Breakfast"}]))

    def test_tasks_and_the_fork_knife_document_match(self):
        script = module_import("meal-plan.js", "normalizeMealPlan", "tasksFromMealPlan", "forkKnifeImportDocument") + STDIN_PRELUDE + """
            const { normalized } = normalizeMealPlan(inputs.document, inputs.meals);
            process.stdout.write(JSON.stringify({ tasks: tasksFromMealPlan(normalized, inputs.meals, inputs.dates), document: forkKnifeImportDocument(normalized, inputs.meals, inputs.dates) }));"""
        javascript = run_node(script, {"document": DOCUMENT, "meals": MEALS, "dates": DATES})
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        tasks, review = tasks_from_meal_plan(normalized, MEALS, DATES)
        self.assertEqual(javascript["tasks"], {"tasks": tasks, "review": review})
        self.assertEqual(javascript["document"], fork_knife_import_document(normalized, MEALS, DATES))

    def test_apply_import_document_merges_the_menu(self):
        script = module_import("weights-rules.js", "applyImportDocument", "defaultAnswers") + module_import("meal-plan.js", "normalizeMealPlan", "forkKnifeImportDocument") + STDIN_PRELUDE + """
            const answers = defaultAnswers(inputs.questionnaire, inputs.categories);
            answers.meals = { perDay: 3, meals: inputs.meals };
            const { normalized } = normalizeMealPlan(inputs.document, inputs.meals);
            const importDocument = forkKnifeImportDocument(normalized, inputs.meals, inputs.dates);
            const weekdays = inputs.questionnaire.options.weekdays.map((weekday) => weekday.id);
            const first = applyImportDocument(answers, importDocument, inputs.categories.order, weekdays, null, inputs.categories, inputs.questionnaire);
            const second = applyImportDocument(answers, importDocument, inputs.categories.order, weekdays, null, inputs.categories, inputs.questionnaire);
            process.stdout.write(JSON.stringify({ tasks: answers.tasks.length, plan: answers.mealPlan.items.map((item) => item.id), applied: [first.mealPlanApplied, second.mealPlanApplied], added: [first.tasks.length, second.tasks.length] }));"""
        result = run_node(script, {"document": DOCUMENT, "meals": MEALS, "dates": DATES, "questionnaire": DATA["questionnaire"], "categories": DATA["categories"]})
        self.assertEqual(result["tasks"], 5)
        self.assertEqual(result["plan"], ["lunch--sun-a--wed-b", "lunch--sat-b--mon-b", "breakfast--sun-a"])
        self.assertEqual(result["applied"], [3, 3])
        self.assertEqual(result["added"], [5, 5], "applying twice adds nothing (tasks dedupe on title + time of day + weekdays)")

    def test_retag_and_cross_meal_leftovers_match(self):
        meals = DATA["questionnaire"]["defaultAnswers"]["meals"]["meals"]
        cross = {"schemaVersion": 1, "kind": "meal-plan", "items": [
            {"meal": "Dinner", "dish": "Curry", "days": ["sun-a", "tue-a"], "leftoversMeal": "Breakfast"},
            {"meal": "Breakfast", "dish": "Oats", "days": ["thu-a", "sat-a"], "leftoversMeal": "Dinner"},
            {"meal": "Breakfast", "dish": "Eggs", "days": ["tue-a"]},
        ]}
        script = module_import("meal-plan.js", "normalizeMealPlan", "retagMealPlan", "menuForDay", "coverage", "tasksFromMealPlan", "canTakeLeftovers") + STDIN_PRELUDE + """
            const { normalized } = normalizeMealPlan(inputs.document, inputs.meals);
            const crossResult = normalizeMealPlan(inputs.cross, inputs.defaults);
            process.stdout.write(JSON.stringify({ retagged: retagMealPlan(normalized, { lunch: "brunch" }), oldMenu: menuForDay({ items: [] }, [{ slots: ["early-morning"] }], "sun-a"),
              cross: crossResult, crossCoverage: coverage(crossResult.normalized.items, "breakfast"), crossMenu: menuForDay(crossResult.normalized, inputs.defaults, "tue-a"),
              crossTasks: tasksFromMealPlan(crossResult.normalized, inputs.defaults, inputs.dates), crossRetag: retagMealPlan(crossResult.normalized, { breakfast: "brekkie" }),
              can: [canTakeLeftovers(inputs.defaults[1], inputs.defaults[0]), canTakeLeftovers(inputs.defaults[0], inputs.defaults[1])] }));"""
        result = run_node(script, {"document": DOCUMENT, "meals": MEALS, "cross": cross, "defaults": meals, "dates": DATES})
        normalized, _ = normalize_meal_plan(DOCUMENT, MEALS)
        self.assertEqual(result["retagged"], retag_meal_plan(normalized, {"lunch": "brunch"}))
        self.assertEqual(result["oldMenu"], menu_for_day({"items": []}, [{"slots": ["early-morning"]}], "sun-a"))
        cross_normalized, cross_problems = normalize_meal_plan(cross, meals)
        self.assertEqual(result["cross"], {"normalized": cross_normalized, "problems": cross_problems})
        self.assertEqual(result["crossCoverage"], coverage(cross_normalized["items"], "breakfast"))
        self.assertEqual(result["crossMenu"], menu_for_day(cross_normalized, meals, "tue-a"))
        tasks, review = tasks_from_meal_plan(cross_normalized, meals, DATES)
        self.assertEqual(result["crossTasks"], {"tasks": tasks, "review": review})
        self.assertEqual(result["crossRetag"], retag_meal_plan(cross_normalized, {"breakfast": "brekkie"}))
        self.assertEqual(result["can"], [True, False])

    def test_classifier_and_answers_problem_know_meal_plans(self):
        script = module_import("workspace-docs.js", "classifyAssistantDocument") + module_import("weights-rules.js", "answersProblem", "defaultAnswers") + STDIN_PRELUDE + """
            const answers = defaultAnswers(inputs.questionnaire, inputs.categories);
            answers.meals = { perDay: 3, meals: inputs.meals };
            const fine = answersProblem(answers, inputs.questionnaire, inputs.categories);
            const oldProfile = answersProblem({ ...answers, meals: { perDay: 2, meals: [{ slots: ["early-morning"] }, { slots: ["evening"] }] } }, inputs.questionnaire, inputs.categories);
            answers.meals.meals[1].name = "Breakfast";
            const duplicate = answersProblem(answers, inputs.questionnaire, inputs.categories);
            answers.meals.meals[1].name = "Lunch";
            answers.mealPlan = { items: [{ id: "tea--sun-a", meal: "tea", dish: "x", days: ["sun-a"], notes: null }] };
            const orphan = answersProblem(answers, inputs.questionnaire, inputs.categories);
            process.stdout.write(JSON.stringify({ kind: classifyAssistantDocument(inputs.document), settings: classifyAssistantDocument({ schemaVersion: 3, weightsProfiles: {} }), fine, oldProfile, duplicate, orphan }));"""
        result = run_node(script, {"document": DOCUMENT, "meals": MEALS, "questionnaire": DATA["questionnaire"], "categories": DATA["categories"]})
        self.assertEqual(result["kind"], "meal-plan")
        self.assertEqual(result["settings"], "user-settings")
        self.assertIsNone(result["fine"])
        self.assertIsNone(result["oldProfile"], "a profile saved before meals had names still derives")
        self.assertEqual(result["duplicate"], "Meal 2: the name Breakfast is already used by another meal.")
        self.assertTrue(result["orphan"].startswith("Meal plan: item #1"))


if __name__ == "__main__":
    unittest.main()
