"""The meal plan: the fortnight menu (docs/meal-plan.md), mirrored exactly by src/lib/shared/meal-plan.js.

For each meal the questionnaire names (Breakfast, Lunch, Dinner, …) the person lists dishes and the day(s)
they are eaten: the first day is the fresh serving, an optional second day is leftovers. Rules:
  - a second serving is never the next day and at most three days after the first, cyclic over the fortnight
    (Saturday B -> Monday B is two days later): allowed = first + 2, + 3, + 4 (mod 14);
  - leftovers may cross meals: from an afternoon/evening/late-evening meal to an early-morning/mid-morning/afternoon
    meal (dinner Sunday A -> breakfast Tuesday A), the same day rules applying (`leftoversMeal`);
  - one dish per meal per day;
  - item id = <meal slug>--<first day>[--<second day>] (kebab-case like every other id), e.g. lunch--sun-a--wed-b.
A meal-plan *document* (meal-plan.schema.json) names meals by their questionnaire name and days by key or name;
normalizing it yields the stored shape (answers.mealPlan = {items: [...]}) plus a list of readable problems.
"""
import re

from . import keys

MEAL_PLAN_SCHEMA_VERSION = 1
MEAL_PLAN_KIND = "meal-plan"
SECOND_DAY_OFFSETS = (2, 3, 4)
# Leftovers may cross meals: a dish eaten at a later-day meal can return at an earlier-day meal (dinner -> breakfast).
LEFTOVER_SOURCE_SLOTS = ("afternoon", "evening", "late-evening")
LEFTOVER_TARGET_SLOTS = ("early-morning", "mid-morning", "afternoon")


def meal_slug(name):
    """A meal's name as an id fragment: 'Lunch' -> 'lunch', 'Late snack' -> 'late-snack' (JS twin: mealSlug)."""
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def day_key_from_text(text):
    """A day key from 'sun-a', 'Sunday A', 'sunday-a' or 'Sun_A'; None when unreadable."""
    words = [word for word in re.split(r"[\s_\-]+", str(text or "").strip().lower()) if word]
    if len(words) != 2 or words[1] not in ("a", "b"):
        return None
    weekday = next((name for name in keys.WEEKDAY_NAMES if name == words[0] or name.startswith(words[0])), None)
    return f"{weekday[:3]}-{words[1]}" if weekday else None


def day_label(day_key):
    """'sun-a' -> 'Sunday A'."""
    weekday, variant = day_key.split("-")
    return f"{next(name for name in keys.WEEKDAY_NAMES if name.startswith(weekday)).capitalize()} {variant.upper()}"


def allowed_second_days(first_day_key):
    """The days a first serving's leftovers may be eaten: 2, 3 or 4 days later, wrapping around the fortnight."""
    index = keys.DAY_KEY_INDEX[first_day_key]
    return [keys.DAY_KEY_ORDER[(index + offset) % len(keys.DAY_KEY_ORDER)] for offset in SECOND_DAY_OFFSETS]


def step_override(value):
    """A dish's own answer to "does this one need prepping / cooking?": True or False override the meal, anything else
    (absent, None) means follow the meal. Kept tri-state so an override reads as an override, never as a "no" flag."""
    return value if isinstance(value, bool) else None


def item_id(meal, days, leftovers_meal=None):
    """dinner--sun-a--wed-b; across meals: dinner--sun-a--breakfast--tue-a."""
    if len(days) == 2 and leftovers_meal and leftovers_meal != meal:
        return "--".join([meal, days[0], leftovers_meal, days[1]])
    return "--".join([meal, *days])


def can_take_leftovers(source_meal, target_meal):
    """May `target_meal` eat `source_meal`'s leftovers? The same meal always; another meal when the source has an
    afternoon/evening/late-evening slot and the target an early-morning/mid-morning/afternoon slot."""
    if meal_slug(source_meal.get("name", "")) == meal_slug(target_meal.get("name", "")):
        return True
    return any(slot in LEFTOVER_SOURCE_SLOTS for slot in source_meal.get("slots", [])) and any(slot in LEFTOVER_TARGET_SLOTS for slot in target_meal.get("slots", []))


def normalize_meal_plan(document, meals):
    """A meal-plan document (or an already-stored plan) -> (normalized {items}, problems).
    `meals` = the profile's questionnaire meals (answers.meals.meals: [{name, ...}])."""
    slugs = {meal_slug(meal.get("name", "")): meal.get("name", "") for meal in (meals or [])}
    meals_by_slug = {meal_slug(meal.get("name", "")): meal for meal in (meals or [])}
    items, problems = [], []
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        return {"items": []}, ["a meal plan needs an items list"]
    for index, item in enumerate(document["items"]):
        label = f"item #{index + 1}"
        if not isinstance(item, dict):
            problems.append(f"{label}: not an object")
            continue
        slug = meal_slug(item.get("meal", ""))
        dish = str(item.get("dish", "") or "").strip()
        label = f'{label} "{dish}"' if dish else label
        if not slug or slug not in slugs:
            problems.append(f"{label}: unknown meal {item.get('meal')!r} (your meals: {', '.join(slugs.values()) or 'none'})")
            continue
        if not dish:
            problems.append(f"{label}: needs a dish")
            continue
        raw_days = item.get("days")
        if not isinstance(raw_days, list) or not 1 <= len(raw_days) <= 2:
            problems.append(f"{label}: days must list the first serving and optionally the leftovers day")
            continue
        days = [day_key_from_text(day) for day in raw_days]
        if any(day is None for day in days):
            problems.append(f"{label}: cannot read day {raw_days[days.index(None)]!r} (use sun-a … sat-b or Sunday A … Saturday B)")
            continue
        if len(days) == 2 and days[1] not in allowed_second_days(days[0]):
            allowed = ", ".join(day_label(day) for day in allowed_second_days(days[0]))
            problems.append(f"{label}: leftovers on {day_label(days[1])} — after {day_label(days[0])} they may be eaten on {allowed} (never the next day, at most three days later)")
            continue
        leftovers_meal = None
        if len(days) == 2 and item.get("leftoversMeal"):
            leftovers_meal = meal_slug(item["leftoversMeal"])
            if leftovers_meal not in slugs:
                problems.append(f"{label}: unknown leftovers meal {item.get('leftoversMeal')!r} (your meals: {', '.join(slugs.values()) or 'none'})")
                continue
            if leftovers_meal == slug:
                leftovers_meal = None
            elif not can_take_leftovers(meals_by_slug[slug], meals_by_slug[leftovers_meal]):
                problems.append(f"{label}: {slugs[slug]} leftovers cannot be {slugs[leftovers_meal]} — leftovers move from an afternoon/evening/late-evening meal to an early-morning/mid-morning/afternoon meal")
                continue
        notes = item.get("notes")
        items.append({"id": item_id(slug, days, leftovers_meal), "meal": slug, "dish": dish, "days": days, "leftoversMeal": leftovers_meal, "notes": str(notes).strip() if notes else None, "needsPrepped": step_override(item.get("needsPrepped")), "needsCooked": step_override(item.get("needsCooked"))})
    # One dish per meal per day: a later item that lands on a taken (meal, day) is reported and dropped (nothing invalid is stored).
    seen, kept = {}, []
    for item in items:
        servings = item_servings(item)
        clash = next(((meal, day, seen[(meal, day)]) for meal, day in servings if (meal, day) in seen), None)
        if clash:
            problems.append(f'"{item["dish"]}" and "{clash[2]}" are both {slugs[clash[0]]} on {day_label(clash[1])} — one dish per meal per day; "{item["dish"]}" not applied')
            continue
        for meal, day in servings:
            seen[(meal, day)] = item["dish"]
        kept.append(item)
    return {"items": kept}, problems


def item_servings(item):
    """[(meal slug, day key)] the item occupies: the first serving at its meal, the leftovers at leftoversMeal or the same meal."""
    servings = [(item["meal"], item["days"][0])]
    if len(item["days"]) == 2:
        servings.append((item.get("leftoversMeal") or item["meal"], item["days"][1]))
    return servings


def merge_meal_plan(existing_items, new_items):
    """New items replace existing ones with the same id; the rest are kept, in stored order then new order."""
    by_id = {item["id"]: item for item in existing_items}
    for item in new_items:
        by_id[item["id"]] = item
    return list(by_id.values())


def coverage(items, slug):
    """How the plan covers a meal: {dishes (first servings), covered (incl. leftovers it receives), missing[]}."""
    covered = set()
    dishes = 0
    for item in items:
        if item["meal"] == slug:
            dishes += 1
        covered.update(day for meal, day in item_servings(item) if meal == slug)
    return {"dishes": dishes, "covered": len(covered), "missing": [day for day in keys.DAY_KEY_ORDER if day not in covered]}


def menu_for_day(plan, meals, day_key):
    """The day's menu in meal order: [{meal (name), slug, dish|None, leftovers}]."""
    items = (plan or {}).get("items", [])
    menu = []
    for index, meal in enumerate(meals or []):
        name = meal.get("name") or f"Meal {index + 1}"  # weights saved before meals had names
        slug = meal_slug(name)
        entry = {"meal": name, "slug": slug, "dish": None, "leftovers": False, "itemId": None}
        for item in items:
            served = next((index for index, (meal, day) in enumerate(item_servings(item)) if meal == slug and day == day_key), None)
            if served is not None:
                entry.update({"dish": item["dish"], "leftovers": served == 1, "itemId": item["id"]})
                break
        menu.append(entry)
    return menu


# The meal slot ids (questionnaire.options.mealSlots) as the tasks' time-of-day words (import_document.TIME_OF_DAY_WORDS).
SLOT_TIME_OF_DAY = {"early-morning": "morning", "mid-morning": "morning", "afternoon": "afternoon", "evening": "evening", "late-evening": "night", "anytime": "anytime"}
PREP_TIME_OF_DAY = "evening"
# What Fork Knife writes into an import document's `source.kind`. Renamed from "forkknife" on
# 2026-08-29 with the rest of the naming sweep. The schema still ACCEPTS the old value, because the
# file set that documents it is downloaded into a person's own AI workspace by hand and never
# re-syncs — an assistant working from a copy taken before the rename goes on emitting the old
# string indefinitely. We write the new one; we refuse neither.
FORK_KNIFE_SOURCE_KIND = "fork-knife"


def previous_day_key(day_key):
    return keys.DAY_KEY_ORDER[(keys.DAY_KEY_INDEX[day_key] - 1) % len(keys.DAY_KEY_ORDER)]


def weekday_of(day_key):
    short = day_key.split("-")[0]
    return next(name for name in keys.WEEKDAY_NAMES if name.startswith(short))


def slugs_to_names(meals):
    return {meal_slug(meal.get("name", "")): meal.get("name", "") for meal in meals or []}


def tasks_from_meal_plan(plan, meals, dates_by_day_key):
    """The menu's prep and cook tasks as import-document (version 2) tasks — what the menu editor creates for the
    person to paste into Apply from assistant. Per item: the meal needs cooking -> "Cook <dish> (<Meal>)" on the
    first serving at the meal's slot; needs prepping -> "Prep <dish> (<Meal>)" the day before, in the evening —
    unless the dish itself opted out (`needsCooked` / `needsPrepped` False on the item, the editor's "no cooking /
    no prep needed"), which drops that task and its review line together;
    each repeats every other week from the next date of that day key (`dates_by_day_key`: day key -> ISO date),
    so the app's cadence lands it on the right A/B week. Returns (tasks, review_lines)."""
    by_slug = {meal_slug(meal.get("name", "")): meal for meal in meals or []}
    tasks, review = [], []
    for item in (plan or {}).get("items", []):
        meal = by_slug.get(item["meal"])
        if not meal:
            continue
        name = meal.get("name", item["meal"])
        first_day = item["days"][0]
        if meal.get("needsCooked") and meal.get("cookMinutes", 0) > 0 and item.get("needsCooked") is not False:
            slots = meal.get("slots") or []
            when = SLOT_TIME_OF_DAY.get(slots[0], "anytime") if slots else "anytime"
            tasks.append({"title": f"Cook {item['dish']} ({name})", "weekdays": [weekday_of(first_day)], "repeats": f"every other week from {dates_by_day_key[first_day]}", "when": when, "lasts": f"{meal['cookMinutes']} min", "category": "meals"})
            leftovers_words = f"; leftovers {day_label(item['days'][1])}" + (f" as {slugs_to_names(meals).get(item['leftoversMeal'], item['leftoversMeal'])}" if item.get("leftoversMeal") else "") if len(item["days"]) == 2 else ""
            review.append(f"Cook {item['dish']} for {name} on {day_label(first_day)} ({meal['cookMinutes']} min, {when}){leftovers_words}")
        if meal.get("needsPrepped") and meal.get("prepMinutes", 0) > 0 and item.get("needsPrepped") is not False:
            prep_day = previous_day_key(first_day)
            tasks.append({"title": f"Prep {item['dish']} ({name})", "weekdays": [weekday_of(prep_day)], "repeats": f"every other week from {dates_by_day_key[prep_day]}", "when": PREP_TIME_OF_DAY, "lasts": f"{meal['prepMinutes']} min", "category": "meals"})
            review.append(f"Prep {item['dish']} for {name} on {day_label(prep_day)} evening ({meal['prepMinutes']} min), the day before {day_label(first_day)}")
    return tasks, review


def fork_knife_import_document(plan, meals, dates_by_day_key, description="Meal prep and cooking tasks from the fortnight menu"):
    """The whole import document (version 2) the menu editor creates: the tasks, a readable review, and the menu itself."""
    tasks, review = tasks_from_meal_plan(plan, meals, dates_by_day_key)
    return {
        "schemaVersion": 2,
        "source": {"kind": FORK_KNIFE_SOURCE_KIND, "description": description},
        "commitments": [],
        "tasks": tasks,
        "skipped": [],
        "review": review,
        "mealPlan": {"items": [{"meal": item["meal"], "dish": item["dish"], "days": list(item["days"]), "leftoversMeal": item.get("leftoversMeal"), "notes": item.get("notes"), "needsPrepped": step_override(item.get("needsPrepped")), "needsCooked": step_override(item.get("needsCooked"))} for item in (plan or {}).get("items", [])]},
    }


def retag_meal_plan(plan, renames):
    """Meals renamed in the questionnaire keep their dishes: items of an old slug move to the new one (ids follow).
    `renames` = {old slug: new slug}."""
    items = []
    for item in (plan or {}).get("items", []):
        meal = renames.get(item["meal"], item["meal"])
        leftovers_meal = renames.get(item.get("leftoversMeal"), item.get("leftoversMeal")) if item.get("leftoversMeal") else None
        if meal == item["meal"] and leftovers_meal == item.get("leftoversMeal"):
            items.append(item)
        else:
            items.append({**item, "meal": meal, "leftoversMeal": leftovers_meal, "id": item_id(meal, item["days"], leftovers_meal)})
    return {"items": items}


def meal_plan_problem(plan, meals):
    """The stored plan re-checked against the profile's meals (renamed meals orphan items): first problem or None."""
    if plan is None:
        return None
    _, problems = normalize_meal_plan(plan, meals)
    return problems[0] if problems else None
