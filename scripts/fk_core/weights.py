"""Questionnaire answers -> weights (the questionnaire contract, docs/weights.md).

The rule, in one place (mirrored exactly by src/lib/shared/weights-rules.js — keep both in sync):
  1. Every subject contributes the midpoint of its chosen minutes-per-day range — the slider always means
     one day. A subject that is not everyday contributes that midpoint on the days it happens
     (`daysPerPeriod / 14` for the fortnight cadence); one on the section cadence, and one marked
     peripheral ("not often"), contribute 0 and are done in flexible time (keys.subject_daily_minutes).
  2. A category's raw minutes are the sum of its subjects, multiplied by the questionnaire's
     wantMoreMultiplier when any of its subjects is marked as a goal (the category "wants more").
  3. A category's share is its raw minutes as a fraction of the waking window, rounded to 4 places; what
     the categories do not claim is flexibleShare, the fortnight's open time (1 when everything is
     peripheral). Only when the declared minutes exceed the window do shares scale down to fit it, and
     then flexibleShare is 0 — shares never inflate to fill a window nobody asked to fill.
  4. The unscheduled block (start + length) sets the waking window — the agenda's scope;
     minutesPerCycle = share x the waking window's minutesPerCycle.
  5. Block split: categories whose share is >= standoutMultiplier x the mean non-peripheral share
     each earn a focus block (capped; none -> one "flexible" block, i.e. a 2-block day); Agenda
     scope "categories" (the default) adds one more focus block, still capped. Cuts start from an
     even split of the waking window and snap onto a grid, preferring the edges of fixed activities
     (anchors) and softly avoiding straddling them. Anchors then vote for each category's
     preferredBlocks.
  6. Anchors are the applied import document's fixedActivities (answers.startup.import, source
     "import") plus the profile's standing appointments — never the workbook's own activities
     unless the person imported a document that carries them (e.g. the workbook example's, build/examples/workbook/derived/defaultImport.json).
  7. The person's own grid (answers.blockFocusGrid — an adopted proposal) or, without one, the import
     document's blockFocusGrid, restricted to this profile's focus blocks, becomes the weights'
     blockFocusGrid (what FortKnight's Overview shows); the import's appointmentBlocks pass through.
  8. Sentiment / delegable / essential flags and the per-subject ranges pass straight through;
     the raw answers are kept under `questionnaire.answers`.
  9. The generator (fk_core/generator.py) proposes a grid from the finished weights for the season the
     caller names (`season_focus`, `season_id`); it rides along as `proposal` with a diff against
     `blockFocusGrid`.
Answers shape: see docs/questionnaire.md ("Answers file").
"""
import json
import math

from . import keys
from .timeconv import MINUTES_PER_DAY, minutes_to_time_string, round_up_to_grid, time_string_to_minutes

SHARE_DECIMALS = 4
UNSCHEDULED_BLOCK_KEY = "unscheduled"
FLEXIBLE_BLOCK_KEY = "flexible"  # the single focus block of a 2-block day (a block key, not the "flexible" focus)
DEFAULT_AGENDA_SCOPE = "categories"
DEFAULT_ENERGY_PEAK = "varies"
IMPORT_ANCHOR_SOURCE = "import"


def round_half_up(value, decimals=0):
    """Deterministic rounding shared with the JavaScript port (Python's round() is banker's rounding)."""
    factor = 10 ** decimals
    rounded = math.floor(value * factor + 0.5) / factor
    return int(rounded) if decimals == 0 else rounded


def default_answers(questionnaire, categories):
    """A typical person's answers: each subject at its `default` range with `peripheralByDefault`,
    the questionnaire's pre-ticked category boxes, and the default unscheduled block."""
    subject_time = {}
    for subject_id in categories["subjects"]:
        slider = questionnaire["subjectSliders"][subject_id]
        cadence = slider.get("cadenceByDefault")
        subject_time[subject_id] = {"minutesPerDay": dict(slider["default"]), "peripheral": bool(slider.get("peripheralByDefault")), "more": False, "goal": False, "everyday": not cadence}
        if cadence:
            subject_time[subject_id].update({"cadence": cadence["cadence"], "daysPerPeriod": cadence["daysPerPeriod"]})
    preset = questionnaire.get("defaultAnswers", {})
    return {
        "startup": {"groupSize": 1, "importJson": "", "import": None},
        "subjectTime": subject_time,
        "sentiment": dict(preset.get("sentiment", {})),
        "delegable": list(preset.get("delegable", [])),
        "essential": list(preset.get("essential", [])),
        "wakingWindow": dict(questionnaire["wakingWindow"]["default"]),
        "meals": _copy(preset.get("meals", {"perDay": questionnaire["mealsPerDay"]["default"], "meals": []})),
        "yearSplit": year_split_from_scheme(questionnaire, preset.get("yearSplitScheme", "quarters")),
        "weekStart": preset.get("weekStart", DEFAULT_WEEK_START),
        "standingAppointments": _copy(preset.get("standingAppointments", [])),
        "tasks": _copy(preset.get("tasks", [])),
        "appointmentWeekdays": list(preset.get("appointmentWeekdays", [])),
        "practices": list(preset.get("practices", [])),
        "agendaScope": preset.get("agendaScope", DEFAULT_AGENDA_SCOPE),
        "restDays": list(preset.get("restDays", [])),
        "energyPeak": preset.get("energyPeak", DEFAULT_ENERGY_PEAK),
        "context": preset.get("context", ""),
        # ForkKnife's questionnaire (docs/meal-plan.md): the assistant prompt embeds these; nothing here moves shares.
        "eaters": preset.get("eaters", 1),
        "dietaryRules": list(preset.get("dietaryRules", [])),
        "allergiesAndDislikes": preset.get("allergiesAndDislikes", ""),
        "favouriteCuisines": list(preset.get("favouriteCuisines", [])),
        "favouriteDishes": preset.get("favouriteDishes", ""),
        "cookingSkill": preset.get("cookingSkill", "comfortable"),
        "foodBudget": preset.get("foodBudget", "moderate"),
        "kitchenKit": list(preset.get("kitchenKit", [])),
        "shoppingCadence": preset.get("shoppingCadence", "weekly"),
    }


def meals_with_defaults(meals_answer, questionnaire):
    """Each meal filled out: name, slots, needsPrepped/needsCooked and the prep/cook minutes — the shape weights.meals
    carries and the meal plan keys off. A meal saved before these fields existed takes the questionnaire's default meal
    at the same position (Breakfast / Dinner / Snack), else "Meal n" and the mealPrep defaults."""
    meal_prep = questionnaire.get("mealPrep") or {"defaultPrepMinutes": 0, "defaultCookMinutes": 0}
    presets = ((questionnaire.get("defaultAnswers") or {}).get("meals") or {}).get("meals", [])
    meals = []
    for index, meal in enumerate((meals_answer or {}).get("meals", [])):
        preset = presets[index] if index < len(presets) else {}
        meals.append({
            "name": str(meal.get("name") or preset.get("name") or f"Meal {index + 1}").strip(),
            "slots": list(meal.get("slots", [])),
            "needsPrepped": bool(meal.get("needsPrepped", preset.get("needsPrepped", False))),
            "needsCooked": bool(meal.get("needsCooked", preset.get("needsCooked", False))),
            "prepMinutes": round_up_to_grid(int(meal.get("prepMinutes", preset.get("prepMinutes", meal_prep["defaultPrepMinutes"])))),
            "cookMinutes": round_up_to_grid(int(meal.get("cookMinutes", preset.get("cookMinutes", meal_prep["defaultCookMinutes"])))),
        })
    return {"perDay": (meals_answer or {}).get("perDay", len(meals)), "meals": meals}


def import_document_from_answers(answers):
    """The applied import document (Assistant page; shown in Startup 2), or {} when none was applied."""
    return (answers.get("startup") or {}).get("import") or {}


def imported_anchor_activities(import_document):
    """The import document's fixed activities as anchor candidates (source "import")."""
    return [{**activity, "source": IMPORT_ANCHOR_SOURCE} for activity in import_document.get("fixedActivities", [])]


def restricted_block_focus_grid(source_grid, focus_block_keys, allowed_focus, source_name="blockFocusGrid"):
    """A grid (the person's own or an import's) restricted to this profile's focus blocks: (grid, warnings)."""
    source_grid = source_grid or {}
    grid, warnings, unmatched = {}, [], []
    for day_key in keys.DAY_KEY_ORDER:
        if day_key not in source_grid:
            continue
        cells = {}
        for block_key, focus in source_grid[day_key].items():
            if block_key not in focus_block_keys:
                if block_key not in unmatched:
                    unmatched.append(block_key)
                continue
            if focus not in allowed_focus:
                warnings.append(f"{source_name}: {day_key}.{block_key} has unknown focus {focus!r}; dropped")
                continue
            cells[block_key] = focus
        grid[day_key] = cells
    if unmatched:
        warnings.insert(0, f"{source_name}: focus for {'block' if len(unmatched) == 1 else 'blocks'} {', '.join(unmatched)} does not match this profile's blocks ({', '.join(focus_block_keys)}); dropped")
    return grid, warnings


def person_block_focus_grid(answers, import_document, focus_block_keys, allowed_focus):
    """The grid the weights show: the person's own (answers.blockFocusGrid, an adopted proposal) when present,
    else the applied import's; either restricted to this profile's focus blocks. Returns (grid, warnings)."""
    if answers.get("blockFocusGrid"):
        return restricted_block_focus_grid(answers["blockFocusGrid"], focus_block_keys, allowed_focus, "blockFocusGrid (your own)")
    return restricted_block_focus_grid(import_document.get("blockFocusGrid"), focus_block_keys, allowed_focus, "blockFocusGrid (imported)")


def _copy(value):
    return json.loads(json.dumps(value))


DEFAULT_WEEK_START = "sunday"
DEFAULT_START_VARIANT = "a"


def year_split_from_seasons(seasons, scheme="custom"):
    """The baseline's seasons (data/seasons.json) as year-split sections — the 'custom' scheme's starting point.
    Lossless with seasons_from_year_split: the start rule, its words, the start half and knownStarts survive."""
    sections = []
    for season in seasons["seasons"]:
        section = {
            "title": season["name"],
            "kind": season["seasonMode"],
            "gregorianEquivalent": season["gregorianRange"],
            "durationWeeks": dict(season["durationWeeks"]),
            "start": {"marker": "rule", "description": season["startDescription"], "rule": _copy(season["startRule"])},
            "startVariant": season["startDayKey"].split("-")[1],
        }
        if season.get("knownStarts"):
            section["knownStarts"] = dict(season["knownStarts"])
        sections.append(section)
    return {"scheme": scheme, "sectionLabel": "season", "sections": sections}


DAYS_PER_YEAR = 365.25
# The longest a subject note may run — the person is writing for their assistant, not filling a diary.
SUBJECT_NOTE_MAX_LENGTH = 300


def section_days_from_year_split(year_split):
    """How many days one of the person's year-split sections lasts on average: the year shared evenly between
    them. This is the period a `section` cadence counts against ("2 days per quarter"). Sections' own
    `durationWeeks` are a rough label from their scheme (gregorian-months says 4 weeks for a 30-day month), so
    the year is divided instead — deterministic, and right for schemes whose sections are unequal."""
    section_count = len((year_split or {}).get("sections") or [])
    return DAYS_PER_YEAR / section_count if section_count else DAYS_PER_YEAR


def year_split_from_scheme(questionnaire, scheme_id):
    """A preset scheme's template as a year split (the read-only presets; presets carry rules only where the marker is exact)."""
    scheme = next(candidate for candidate in questionnaire["options"]["yearSplitSchemes"] if candidate["id"] == scheme_id)
    return {"scheme": scheme_id, "sectionLabel": scheme["sectionLabel"], "sections": _copy(scheme["template"])}


def seasons_from_year_split(year_split, week_start=DEFAULT_WEEK_START):
    """A person's year split as seasons.json-shaped seasons (in-memory only; the date resolver reads
    startRule / startDayKey / knownStarts). Duplicate titles get -2, -3 suffixes."""
    seasons = []
    used_ids = set()
    for section in year_split.get("sections", []):
        base_id = keys.slugify(section["title"]) or "section"
        season_id, suffix = base_id, 2
        while season_id in used_ids:
            season_id, suffix = f"{base_id}-{suffix}", suffix + 1
        used_ids.add(season_id)
        start = section.get("start", {})
        seasons.append({
            "id": season_id,
            "name": section["title"],
            "gregorianRange": section.get("gregorianEquivalent"),
            "durationWeeks": _copy(section.get("durationWeeks")),
            "startRule": _copy(start.get("rule")),
            "startDescription": start.get("description", ""),
            "startDayKey": keys.day_key_from_weekday_and_variant(week_start, section.get("startVariant", DEFAULT_START_VARIANT)),
            "seasonMode": "mixed",
            "outdoorWindow": {"uvAbove4": None},
            "focus": [],
            "menuId": None,
            "knownStarts": dict(section.get("knownStarts") or {}),
        })
    return seasons


def _year_split_with_defaults(year_split, week_start=DEFAULT_WEEK_START):
    """A copy with every section carrying start.rule (null when absent) and startVariant (default a);
    a rule that snaps always snaps to the person's week start (the snap weekday is never stored stale)."""
    year_split = _copy(year_split)
    for section in year_split.get("sections", []):
        section.setdefault("start", {"marker": "manual", "description": ""})
        section["start"].setdefault("rule", None)
        section.setdefault("startVariant", DEFAULT_START_VARIANT)
        rule = section["start"]["rule"]
        if rule and rule.get("snap"):
            rule["snap"]["weekday"] = week_start
    return year_split


def seasons_for_answers(answers, questionnaire, categories):
    """The seasons a person's answers imply (their year split + week start), for date resolution."""
    defaults = default_answers(questionnaire, categories)
    week_start = answers.get("weekStart", defaults["weekStart"])
    return seasons_from_year_split(_year_split_with_defaults(answers.get("yearSplit", defaults["yearSplit"]), week_start), week_start)


def standing_appointment_activities(standing_appointments, days, resolve_day_key=None):
    """Standing appointments as pseudo-activities so they anchor the block split like fixed activities.
    weekly -> every listed weekday, both fortnight day keys; every-other-week -> the variant (A/B) that
    `firstDate` resolves to (both + warning without a resolver); monthly-* / one-off -> pooled, no day key.
    Returns (activities, warnings)."""
    day_keys_by_weekday = {}
    for day_key in days["order"]:
        day = days["days"][day_key]
        day_keys_by_weekday.setdefault(day["weekday"], {})[day["variant"].lower()] = day_key
    activities, warnings = [], []
    for index, appointment in enumerate(standing_appointments):
        start_minutes = time_string_to_minutes(appointment["start"])
        end = minutes_to_time_string(min(start_minutes + appointment["durationMinutes"], MINUTES_PER_DAY))
        cadence = appointment["cadence"]
        kind = cadence["kind"]
        identifier = f"standing--{keys.slugify(appointment['title']) or 'appointment'}--{index + 1}"
        weekdays = list(appointment.get("weekdays", []))
        day_keys = []
        if kind == "weekly":
            for weekday in weekdays:
                variants = day_keys_by_weekday.get(weekday, {})
                day_keys += [variants.get("a"), variants.get("b")]
        elif kind == "every-other-week":
            resolved_variant = None
            if resolve_day_key and cadence.get("firstDate"):
                resolved_day_key = resolve_day_key(cadence["firstDate"])
                resolved_variant = days["days"][resolved_day_key]["variant"].lower() if resolved_day_key else None
            if resolved_variant is None:
                warnings.append(f"{identifier}: every-other-week could not be placed on week A or B (no date resolver); counted in both weeks")
            for weekday in weekdays:
                variants = day_keys_by_weekday.get(weekday, {})
                day_keys += [variants.get(resolved_variant)] if resolved_variant else [variants.get("a"), variants.get("b")]
        else:
            day_keys = [None] * max(1, len(weekdays))
        for day_key in day_keys:
            activities.append({
                "id": identifier,
                "dayKey": day_key,
                "priority": 1,
                "flexibility": "no",
                "categories": [appointment["category"]],
                "timing": {"estimatedStart": appointment["start"], "estimatedEnd": end},
                "source": "standing-appointment",
            })
    return activities, warnings


# The cadence rule lives in keys.py (the generator reads it too); re-exported here for existing importers.
subject_daily_minutes = keys.subject_daily_minutes
SUBJECT_CADENCES = keys.SUBJECT_CADENCES


# ---------- waking window and block split ----------

def waking_window_from_answer(waking_window):
    """The answered waking window {start, end} with its length; wraps midnight when end < start (end == start is a full day)."""
    start_minutes = time_string_to_minutes(waking_window["start"])
    end_minutes = time_string_to_minutes(waking_window["end"])
    minutes_per_day = (end_minutes - start_minutes) % MINUTES_PER_DAY or MINUTES_PER_DAY
    return {
        "start": minutes_to_time_string(start_minutes),
        "end": minutes_to_time_string(end_minutes),
        "minutesPerDay": minutes_per_day,
        "minutesPerCycle": minutes_per_day * len(keys.DAY_KEY_ORDER),
    }


def unscheduled_block_from_window(waking_window):
    """The unscheduled block (wind-down + sleep + wake-up): the complement of the waking window."""
    return {"start": waking_window["end"], "end": waking_window["start"], "minutes": MINUTES_PER_DAY - waking_window["minutesPerDay"]}


def standout_categories(weights_categories, raw_minutes, block_split):
    """Categories whose share stands above the mean non-peripheral share, best first, capped."""
    considered = [category_key for category_key in keys.CATEGORY_KEY_ORDER if raw_minutes[category_key] > 0]
    if not considered:
        return []
    mean_share = sum(weights_categories[category_key]["share"] for category_key in considered) / len(considered)
    threshold = block_split["standoutMultiplier"] * mean_share
    standouts = [category_key for category_key in considered if weights_categories[category_key]["share"] >= threshold]
    standouts.sort(key=lambda category_key: (-weights_categories[category_key]["share"], keys.CATEGORY_KEY_ORDER.index(category_key)))
    return standouts[:block_split["maxFocusBlocks"]]


def is_anchor(activity):
    return bool(activity.get("timing")) and (activity.get("priority") == 1 or activity.get("flexibility") == "no")


def anchor_offsets(activities, waking_window):
    """Fixed activities as offsets (minutes since the waking window starts); flags out-of-scope ones."""
    waking_start = time_string_to_minutes(waking_window["start"])
    waking_minutes = waking_window["minutesPerDay"]
    anchors, warnings = [], []
    for activity in activities:
        if not is_anchor(activity):
            continue
        timing = activity["timing"]
        start_offset = (time_string_to_minutes(timing["estimatedStart"]) - waking_start) % MINUTES_PER_DAY
        duration = time_string_to_minutes(timing["estimatedEnd"]) - time_string_to_minutes(timing["estimatedStart"])
        end_offset = start_offset + duration
        anchor = {"activityId": activity["id"], "dayKey": activity["dayKey"], "start": timing["estimatedStart"], "end": timing["estimatedEnd"], "categories": list(activity["categories"]), "source": activity.get("source", "activity")}
        if start_offset >= waking_minutes:
            warnings.append(f"{activity['id']} starts inside the unscheduled block ({timing['estimatedStart']})")
            anchor["block"] = None
            anchors.append(anchor)
            continue
        if end_offset > waking_minutes:
            warnings.append(f"{activity['id']} runs into the unscheduled block (ends {timing['estimatedEnd']})")
            end_offset = waking_minutes
        anchor["startOffset"] = start_offset
        anchor["endOffset"] = end_offset
        anchors.append(anchor)
    return anchors, warnings


def choose_cuts(waking_minutes, focus_block_count, anchors, block_split):
    """Even split, each cut snapped to the grid point (within the search window) with the lowest cost."""
    grid = block_split["cutGridMinutes"]
    search = block_split["cutSearchMinutes"]
    straddle_penalty = block_split.get("straddlePenalty", 0)
    edge_bonus = block_split.get("edgeBonus", 0)
    in_scope = [anchor for anchor in anchors if "startOffset" in anchor]
    cuts = []
    previous = 0
    for cut_index in range(1, focus_block_count):
        ideal = waking_minutes * cut_index / focus_block_count
        best = None
        lowest = math.floor((ideal - search) / grid) * grid
        highest = math.ceil((ideal + search) / grid) * grid
        for candidate in range(lowest, highest + 1, grid):
            if candidate <= previous or candidate >= waking_minutes or abs(candidate - ideal) > search:
                continue
            straddles = sum(1 for anchor in in_scope if anchor["startOffset"] < candidate < anchor["endOffset"])
            edges = sum(1 for anchor in in_scope if candidate in (anchor["startOffset"], anchor["endOffset"]))
            # All three terms are minutes, so the grid can be made finer without re-tuning the penalties.
            cost = abs(candidate - ideal) + straddle_penalty * straddles - edge_bonus * edges
            ranking = (cost, abs(candidate - ideal), candidate)
            if best is None or ranking < best[0]:
                best = (ranking, candidate)
        chosen = best[1] if best else int(round_half_up(ideal))
        cuts.append(chosen)
        previous = chosen
    return cuts


def blocks_from_cuts(waking_window, unscheduled_block, cuts, focus_block_keys):
    waking_start = time_string_to_minutes(waking_window["start"])
    waking_minutes = waking_window["minutesPerDay"]
    boundaries = [0, *cuts, waking_minutes]
    blocks = [{"key": UNSCHEDULED_BLOCK_KEY, "start": unscheduled_block["start"], "end": waking_window["start"], "durationMinutes": unscheduled_block["minutes"], "carriesFocus": False}]
    for index, key in enumerate(focus_block_keys):
        start_offset, end_offset = boundaries[index], boundaries[index + 1]
        blocks.append({
            "key": key,
            "start": minutes_to_time_string((waking_start + start_offset) % MINUTES_PER_DAY),
            "end": minutes_to_time_string((waking_start + end_offset) % MINUTES_PER_DAY),
            "durationMinutes": end_offset - start_offset,
            "carriesFocus": True,
        })
    return blocks


def assign_anchor_blocks(anchors, cuts, focus_block_keys, waking_minutes):
    boundaries = [0, *cuts, waking_minutes]
    for anchor in anchors:
        if "startOffset" not in anchor:
            continue
        anchor["block"] = focus_block_keys[-1]
        for index in range(len(focus_block_keys)):
            if boundaries[index] <= anchor["startOffset"] < boundaries[index + 1]:
                anchor["block"] = focus_block_keys[index]
                break


def preferred_blocks_from_anchors(anchors, focus_block_keys):
    """Blocks ordered by how many anchors of the category start there (ties keep block order)."""
    votes = {category_key: {block_key: 0 for block_key in focus_block_keys} for category_key in keys.CATEGORY_KEY_ORDER}
    for anchor in anchors:
        if anchor.get("block") is None:
            continue
        for category_key in anchor["categories"]:
            if category_key in votes:
                votes[category_key][anchor["block"]] += 1
    preferred = {}
    for category_key, block_votes in votes.items():
        ranked = sorted(block_votes.items(), key=lambda pair: (-pair[1], focus_block_keys.index(pair[0])))
        preferred[category_key] = [block_key for block_key, count in ranked if count > 0]
    return preferred


def split_blocks(weights_categories, raw_minutes, waking_window_answer, activities, questionnaire, agenda_scope=DEFAULT_AGENDA_SCOPE):
    """Waking window + block split for a profile. Returns (wakingWindow, unscheduledBlock, blocks, blockSplit, preferredBlocks).
    agenda_scope defaults to "categories" (Focus 6's default), which adds one focus block beyond the standouts;
    pass "subjects" for the standouts-only day."""
    block_split = questionnaire["blockSplit"]
    waking_window = waking_window_from_answer(waking_window_answer)
    unscheduled = unscheduled_block_from_window(waking_window)
    standouts = standout_categories(weights_categories, raw_minutes, block_split)
    focus_block_count = max(1, len(standouts))
    if agenda_scope == "categories":
        focus_block_count = min(block_split["maxFocusBlocks"], focus_block_count + 1)
    focus_block_keys = list(block_split["focusBlockKeys"][str(focus_block_count)])
    anchors, warnings = anchor_offsets(activities, waking_window)
    cuts = choose_cuts(waking_window["minutesPerDay"], focus_block_count, anchors, block_split)
    assign_anchor_blocks(anchors, cuts, focus_block_keys, waking_window["minutesPerDay"])
    blocks = blocks_from_cuts(waking_window, unscheduled, cuts, focus_block_keys)
    anchor_records = [{key: anchor[key] for key in ("activityId", "dayKey", "start", "end", "categories", "block", "source")} for anchor in anchors]
    split = {"standoutCategories": sorted(standouts, key=keys.CATEGORY_KEY_ORDER.index), "focusBlockCount": focus_block_count, "agendaScope": agenda_scope, "anchors": anchor_records, "warnings": warnings}
    return waking_window, unscheduled, blocks, split, preferred_blocks_from_anchors(anchors, focus_block_keys)


# ---------- the whole rule ----------

def weights_from_answers(answers, categories, questionnaire, *, weights_id, answered_at=None, activities=(), days=None, resolve_day_key=None, season_focus=None, season_id=None):
    """Turn a questionnaire answers object into a weights object (weights.schema.json).
    `season_focus` / `season_id` name the season the proposal is generated for (the current one; a person's own
    sections carry no focus list, so the generator then works from weights and anchors alone)."""
    from .generator import proposal_from_weights  # imported here: generator.py reads finished weights, weights.py builds them
    defaults = default_answers(questionnaire, categories)
    subject_time = {**defaults["subjectTime"], **answers.get("subjectTime", {})}
    # A category "wants more" when any of its subjects is a goal (Focus Q2 was folded into the goal toggle).
    want_more = {
        category_key for category_key in keys.CATEGORY_KEY_ORDER
        if any(subject_time[subject_id].get("goal") for subject_id in categories["categories"][category_key]["subjects"])
    }
    sentiment = answers.get("sentiment", {})
    delegable = set(answers.get("delegable", []))
    essential = set(answers.get("essential", []))
    waking_window_answer = {**defaults["wakingWindow"], **answers.get("wakingWindow", {})}
    multiplier = questionnaire["wantMoreMultiplier"]
    standing_appointments = _copy(answers.get("standingAppointments", defaults["standingAppointments"]))
    standing_activities, standing_warnings = standing_appointment_activities(standing_appointments, days, resolve_day_key) if days else ([], [])
    agenda_scope = answers.get("agendaScope", defaults["agendaScope"])
    import_document = import_document_from_answers(answers)
    all_activities = list(activities) + imported_anchor_activities(import_document) + standing_activities

    raw_minutes = {}
    for category_key in keys.CATEGORY_KEY_ORDER:
        subject_ids = categories["categories"][category_key]["subjects"]
        total = sum(subject_daily_minutes(subject_time[subject_id]) for subject_id in subject_ids)
        raw_minutes[category_key] = total * (multiplier if category_key in want_more else 1)
    grand_total = sum(raw_minutes.values())
    # Shares are what was *declared*, as a fraction of the waking window — not a proportional split of it.
    # A day nobody filled keeps its remainder as flexibleShare; only an over-declared day scales down.
    waking_minutes_per_day = waking_window_from_answer(waking_window_answer)["minutesPerDay"]
    share_denominator = max(grand_total, waking_minutes_per_day)

    weights_categories = {}
    for category_key in keys.CATEGORY_KEY_ORDER:
        share = round_half_up(raw_minutes[category_key] / share_denominator, SHARE_DECIMALS) if share_denominator else 0
        weights_categories[category_key] = {
            "share": share,
            "wantMore": category_key in want_more,
            "sentiment": sentiment.get(category_key, "neutral"),
            "delegable": category_key in delegable,
            "essential": category_key in essential,
        }
    waking_window, unscheduled, blocks, split, preferred_blocks = split_blocks(weights_categories, raw_minutes, waking_window_answer, all_activities, questionnaire, agenda_scope)
    focus_block_keys = [block["key"] for block in blocks if block["carriesFocus"]]
    block_focus_grid, grid_warnings = person_block_focus_grid(answers, import_document, focus_block_keys, keys.CATEGORY_KEY_ORDER + [keys.FLEXIBLE_FOCUS])
    split["warnings"] = standing_warnings + split["warnings"] + grid_warnings
    for category_key, category in weights_categories.items():
        category["minutesPerCycle"] = round_half_up(category["share"] * waking_window["minutesPerCycle"])
        category["preferredBlocks"] = preferred_blocks[category_key]
        weights_categories[category_key] = {key: category[key] for key in ("share", "minutesPerCycle", "preferredBlocks", "wantMore", "sentiment", "delegable", "essential")}
    weights_subjects = {}
    for subject_id in categories["subjects"]:
        subject_answer = subject_time[subject_id]
        goal = bool(subject_answer.get("goal"))
        everyday = bool(subject_answer.get("everyday", True))
        weights_subjects[subject_id] = {
            "minutesPerDay": dict(subject_answer["minutesPerDay"]),
            "peripheral": bool(subject_answer.get("peripheral")),
            "goal": goal,
            "currentMinutesPerDay": subject_answer.get("currentMinutesPerDay") if goal else None,
            "everyday": everyday,
            "cadence": subject_answer.get("cadence") if not everyday else None,
            "daysPerPeriod": subject_answer.get("daysPerPeriod") if not everyday else None,
            # Free text for the person's assistant: when this actually happens, and what "not often" means here.
            "specificDaysNote": subject_answer.get("specificDaysNote") or None,
            "notOftenNote": subject_answer.get("notOftenNote") or None,
        }
    questionnaire_record = {"version": questionnaire["schemaVersion"], "answers": answers}
    if answered_at:
        questionnaire_record = {"version": questionnaire["schemaVersion"], "answeredAt": answered_at, "answers": answers}
    weights = {
        "$schema": "./schema/weights.schema.json",
        "schemaVersion": 1,
        "id": weights_id,
        "source": "questionnaire",
        "cycleLengthDays": len(keys.DAY_KEY_ORDER),
        "wakingWindow": waking_window,
        "categories": weights_categories,
        "subjects": weights_subjects,
        # Not an input: the waking window the categories did not claim — the fortnight's open time (1 when every
        # subject is peripheral, 0 when the day is over-declared), so shares + flexibleShare = 1.
        "flexibleShare": max(0, round_half_up(1 - sum(category["share"] for category in weights_categories.values()), SHARE_DECIMALS)),
        "unscheduledBlock": unscheduled,
        "blocks": blocks,
        "blockSplit": split,
        "blockFocusGrid": block_focus_grid,
        "appointmentBlocks": _copy(import_document.get("appointmentBlocks", {})),
        "agendaScope": agenda_scope,
        "meals": meals_with_defaults(answers.get("meals", defaults["meals"]), questionnaire),
        "mealPlan": _copy(answers.get("mealPlan") or {"items": []}),
        "yearSplit": _year_split_with_defaults(answers.get("yearSplit", defaults["yearSplit"]), answers.get("weekStart", defaults["weekStart"])),
        "weekStart": answers.get("weekStart", defaults["weekStart"]),
        "standingAppointments": standing_appointments,
        "tasks": _copy(answers.get("tasks", defaults["tasks"])),
        "appointmentWeekdays": list(answers.get("appointmentWeekdays", defaults["appointmentWeekdays"])),
        "practices": list(answers.get("practices", defaults["practices"])),
        "restDays": list(answers.get("restDays", defaults["restDays"])),
        "energyPeak": answers.get("energyPeak", defaults["energyPeak"]),
        "context": answers.get("context", defaults["context"]),
        "questionnaire": questionnaire_record,
        "notes": ["Derived from questionnaire answers by the rule in fk_core/weights.py / src/lib/shared/weights-rules.js."],
    }
    weights["proposal"] = proposal_from_weights(weights, questionnaire, categories, season_focus, season_id)
    return weights
