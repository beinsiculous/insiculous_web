"""The Python twin of src/lib/champion/resolve.js: the same resolution rules, written independently.

DELIBERATE TWIN of src/lib/champion/resolve.js. test_champion_resolve.py runs both over every date in
the fixture's calendar and asserts they agree, which is what makes the resolver's "no calendar math" rule
checkable rather than merely stated. Never change one of the pair alone. `block_key_for_time` below is
also the twin of src/lib/shared/clock.js's blockKeyForTime, held by test_clock.py.

Like its twin this does no calendar math: it looks dates up in `calendar` and joins rows by day key. It
came here with the resolver from the Fort Knight phone app's tests/reference.py on 2026-09-02.
"""

MEAL_FIELD_BY_NAME = {"brunch": "brunch", "snack": "snack", "dinner": "dinner"}
MINUTES_PER_DAY = 24 * 60


def time_string_to_minutes(time_string):
    hours, minutes = (int(part) for part in time_string.split(":"))
    return hours * 60 + minutes


def block_key_for_time(blocks, time_string):
    """Which block contains this wall time; too-dark wraps past midnight. None when no block does."""
    minutes = time_string_to_minutes(time_string)
    for block in blocks:
        start = time_string_to_minutes(block["start"])
        end = time_string_to_minutes(block["end"])
        if end <= start:
            end += MINUTES_PER_DAY
        if start <= minutes < end or start <= minutes + MINUTES_PER_DAY < end:
            return block["key"]
    return None


def calendar_range(keep):
    return {"first": keep["calendar"][0]["date"], "last": keep["calendar"][-1]["date"]}


def calendar_entry_for_date(keep, iso_date):
    for entry in keep["calendar"]:
        if entry["date"] == iso_date:
            return entry
    return None


def season_by_key(keep, season_key):
    for season in keep["seasons"]:
        if season["key"] == season_key:
            return season
    return None


def season_name(keep, season_key):
    season = season_by_key(keep, season_key)
    return season["name"] if season else season_key


def day_by_key(keep, day_key):
    for day in keep["days"]:
        if day["dayKey"] == day_key:
            return day
    return None


def category_label(keep, category_key):
    for category in keep["categories"]:
        if category["key"] == category_key:
            return category["label"]
    return category_key[:1].upper() + category_key[1:] if category_key else ""


def rows_for_season(rows, season_key):
    """Twin of rowsForSeason: the rows tagged with season_key and the rows tagged with nothing; every row
    when there is no season key."""
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    if season_key is None:
        return rows
    return [row for row in rows if row.get("season") is None or row.get("season") == season_key]


def timed_blocks(keep, season_key):
    """Twin of timedBlocks: blocks with start, end and wrapsMidnight resolved from the season's blockStarts."""
    season = season_by_key(keep, season_key)
    block_starts = (season or {}).get("blockStarts")
    blocks = keep.get("blocks") or []
    if not block_starts or not isinstance(block_starts, dict):
        return [{
            "key": block["key"],
            "label": block["label"],
            "start": block.get("start"),
            "end": block.get("end"),
            "wrapsMidnight": default_to(block.get("wrapsMidnight"), False),
            "mealPrimary": block.get("mealPrimary"),
            "mealSecondary": block.get("mealSecondary"),
            "sourceRow": block.get("sourceRow"),
        } for block in blocks]
    result = []
    for index, block in enumerate(blocks):
        next_block = blocks[(index + 1) % len(blocks)] if blocks else None
        start = default_to(block_starts.get(block["key"]), block.get("start"))
        end = default_to(block_starts.get(next_block["key"]), next_block.get("start")) if next_block else None
        wraps_midnight = (end <= start) if (start and end) else False
        result.append({
            "key": block["key"],
            "label": block["label"],
            "start": start,
            "end": end,
            "wrapsMidnight": wraps_midnight,
            "mealPrimary": block.get("mealPrimary"),
            "mealSecondary": block.get("mealSecondary"),
            "sourceRow": block.get("sourceRow"),
        })
    return result


def task_groups_for(keep, day_key, block_key, season_key=None):
    """Tasks for a day key and block, in slab order, grouped by Description with first-appearance order."""
    groups = []
    for task in keep.get("tasks") or []:
        if task.get("dayKey") != day_key or task.get("block") != block_key:
            continue
        group = next((candidate for candidate in groups if candidate["group"] == task.get("group")), None)
        if group is None:
            group = {"group": task.get("group"), "category": task.get("category"), "tasks": []}
            groups.append(group)
        matching_servings = rows_for_season(task.get("serves"), season_key)
        group["tasks"].append({
            "id": task["id"],
            "step": task["step"],
            "category": task["category"],
            "serves": [{
                "role": (serving or {}).get("role"),
                "dayKey": (serving or {}).get("dayKey"),
                "label": day_label(keep, (serving or {}).get("dayKey")),
                "daysAfter": default_to((serving or {}).get("daysAfter"), 0),
            } for serving in matching_servings],
        })
    return groups


def appointments_for(keep, day_key, block_key):
    matching = [appointment for appointment in keep.get("appointments") or []
                if appointment.get("dayKey") == day_key and appointment.get("block") == block_key]
    return sorted(matching, key=lambda appointment: (appointment["timing"]["estimatedStart"], appointment["title"]))


def meals_for_day_key(keep, day_key, season_key=None):
    for meals in rows_for_season(keep.get("meals"), season_key):
        if meals.get("dayKey") == day_key:
            return meals
    return None


def meal_name_for_block(block):
    """Twin of mealNameForBlock: the block's meal option when the Meals sheet has a column for it, else None."""
    primary = block.get("mealPrimary")
    return primary if primary and MEAL_FIELD_BY_NAME.get(primary.lower()) else None


def meal_for_block(keep, day_key, block, season_key=None):
    name = meal_name_for_block(block)
    if name is None:
        return None
    meals = meals_for_day_key(keep, day_key, season_key)
    if meals is None:
        return None
    return {"name": name, "dish": meals.get(MEAL_FIELD_BY_NAME[name.lower()])}


def task_ids_for_day_key(keep, day_key):
    return [task["id"] for block in keep["blocks"]
            for group in task_groups_for(keep, day_key, block["key"]) for task in group["tasks"]]


def fortnight_window_for(keep, iso_date):
    """The fortnight containing iso_date as [first_date, iso_date]: from the latest sun-a at or before
    it (transition weeks carry null day keys; the window clips to the calendar's first date when today
    predates any in-range sun-a — the calendar opens mid-fortnight). ISO dates compare as strings.
    Twin of fortnightWindowFor."""
    start = None
    for entry in keep["calendar"]:
        if entry["date"] > iso_date:
            break
        if entry["dayKey"] == "sun-a":
            start = entry["date"]
    if start is None:
        start = keep["calendar"][0]["date"]
    return [start, iso_date]


def carried_tasks_for(keep, checkoffs, iso_date):
    """Skipped (never-checked) tasks from earlier days of this fortnight, not superseded by a later
    assignment of the same step — the catch-up list the Flexible-focus blocks show. In assignment
    order, with the origin attached. Twin of carriedTasksFor."""
    start, _ = fortnight_window_for(keep, iso_date)
    checked_ids = {task_id for date, task_ids in checkoffs.items()
                   if start <= date <= iso_date for task_id in task_ids}
    carried = []
    for entry in keep["calendar"]:
        if entry["date"] < start or entry["date"] >= iso_date or not entry["dayKey"]:
            continue
        for task in keep["tasks"]:
            if task["dayKey"] != entry["dayKey"] or task["id"] in checked_ids:
                continue
            superseded = any(
                entry["date"] < later["date"] <= iso_date and later["dayKey"] is not None
                and any(candidate["dayKey"] == later["dayKey"] and candidate["step"] == task["step"]
                        for candidate in keep["tasks"])
                for later in keep["calendar"])
            if superseded:
                continue
            carried.append({
                "id": task["id"],
                "step": task["step"],
                "category": task["category"],
                "group": task["group"],
                "fromDayKey": entry["dayKey"],
                "fromWeekday": day_by_key(keep, entry["dayKey"])["weekday"],
                "fromDate": entry["date"],
            })
    return carried


def resolve_day(keep, iso_date, wall_time=None):
    """One date resolved for the screen: expired, transition, or an ordinary day. Twin of resolveDay."""
    entry = calendar_entry_for_date(keep, iso_date)
    if entry is None:
        return {"status": "expired", "date": iso_date, "range": calendar_range(keep)}

    season = season_by_key(keep, entry["season"])
    season_view = {
        "key": entry["season"],
        "name": season_name(keep, entry["season"]),
        "weekOfSeason": entry["weekOfSeason"],
        "focus": [{"key": key, "label": category_label(keep, key)} for key in (season or {}).get("focus", [])],
    }

    if entry["transition"] or entry["dayKey"] is None:
        transition_to = entry["transitionTo"]
        return {
            "status": "transition",
            "date": iso_date,
            "season": season_view,
            "transitionTo": {"key": transition_to, "name": season_name(keep, transition_to)} if transition_to else None,
            "headline": (f"{season_view['name']} Transitioning to {season_name(keep, transition_to)}"
                         if transition_to else f"{season_view['name']} Transitioning"),
        }

    day = day_by_key(keep, entry["dayKey"])
    blocks = timed_blocks(keep, entry["season"])
    current_block_key = block_key_for_time(blocks, wall_time) if wall_time else None

    return {
        "status": "day",
        "date": iso_date,
        "season": season_view,
        "day": {
            "index": day["index"],
            "dayKey": day["dayKey"],
            "weekday": day["weekday"],
            "variant": day["variant"],
            "label": f"{day['weekday']} {day['variant']}",
            "week": 1 if day["index"] <= 7 else 2,
            "mainFocus": day["mainFocus"],
            "mainFocusLabel": day["mainFocusLabel"],
        },
        "currentBlock": current_block_key,
        "meals": meals_for_day_key(keep, entry["dayKey"], entry["season"]),
        "blocks": [{
            "key": block["key"],
            "label": block["label"],
            "start": block["start"],
            "end": block["end"],
            "wrapsMidnight": block["wrapsMidnight"],
            "focus": day["blockFocus"].get(block["key"]),
            "isCurrent": block["key"] == current_block_key,
            "meal": meal_for_block(keep, entry["dayKey"], block, entry["season"]),
            "appointments": appointments_for(keep, entry["dayKey"], block["key"]),
            "taskGroups": task_groups_for(keep, entry["dayKey"], block["key"], entry["season"]),
        } for block in blocks],
    }


def day_label(keep, day_key):
    day = day_by_key(keep, day_key)
    return f"{day['weekday']} {day['variant']}" if day else day_key


def resolve_menu(keep, season_key=None):
    """Twin of resolveMenu: the fortnight menu grouped by slot."""
    seasonal_menu = rows_for_season(keep.get("menu"), season_key)

    slots = (("brunch", "Brunch"), ("snack", "Snack"), ("dinner", "Dinner"))
    result = []
    for slot, label in slots:
        entries = []
        for entry in seasonal_menu:
            if entry.get("slot") != slot:
                continue
            item = {
                "mealKey": entry["mealKey"],
                "menu": entry["menu"],
                "cookDay": entry["cookDay"],
                "cookDayLabel": day_label(keep, entry["cookDay"]),
                "leftoversDay": entry.get("leftoversDay"),
                "leftoversDayLabel": day_label(keep, entry["leftoversDay"]) if entry.get("leftoversDay") else None,
                "cookExtra": entry["cookExtra"],
                "cookExtraNote": entry.get("cookExtraNote"),
            }
            if "prepDay" in entry:
                item["prepDay"] = entry["prepDay"]
                item["prepDayLabel"] = day_label(keep, entry["prepDay"]) if entry["prepDay"] else None
            if "prepBlock" in entry:
                item["prepBlock"] = entry["prepBlock"]
            if "foodGroups" in entry:
                item["foodGroups"] = entry["foodGroups"]
            if "recipeLink" in entry:
                item["recipeLink"] = entry["recipeLink"]
            if "ingredients" in entry:
                item["ingredients"] = [{key: value for key, value in (ingredient or {}).items() if key != "sourceRow"}
                                       for ingredient in (entry["ingredients"] or [])]
            entries.append(item)
        result.append({"slot": slot, "label": label, "entries": entries})
    return result


PRODUCE_RANKS = ["hero", "secondary", "tertiary", "quaternary"]


def produce_lists(season):
    """Twin of produceLists: a season's produce as ordered [{group, label, items: [{rank, name}]}]."""
    groups = []
    for group, ranked in (season.get("produce") or {}).items():
        items = [{"rank": rank, "name": (ranked or {}).get(rank)}
                 for rank in PRODUCE_RANKS if (ranked or {}).get(rank)]
        if items:
            groups.append({"group": group, "label": group[:1].upper() + group[1:], "items": items})
    return groups


def meal_idea_lists(season):
    """Twin of mealIdeaLists: a season's meal ideas as [{name, text}] in slab order."""
    return [{"name": name, "text": text}
            for name, text in (season.get("mealIdeas") or {}).items()
            if isinstance(text, str) and text]


def resolve_seasons(keep, iso_date=None):
    """Twin of resolveSeasons: the five seasons, with the one containing iso_date marked current."""
    entry = calendar_entry_for_date(keep, iso_date) if iso_date else None
    current_key = entry["season"] if entry else None
    result = []
    for season in keep.get("seasons") or []:
        item = {
            "key": season["key"],
            "name": season["name"],
            "isCurrent": season["key"] == current_key,
            "gregorianRange": season.get("gregorianRange"),
            "startDescription": season.get("startDescription"),
            "safeOutsidePercent": season.get("safeOutsidePercent"),
            "focus": [{"key": key, "label": category_label(keep, key)} for key in default_to(season.get("focus"), [])],
            "produce": produce_lists(season),
            "mealIdeas": meal_idea_lists(season),
        }
        if "blockStarts" in season:
            item["blockStarts"] = season["blockStarts"]
        if "themes" in season:
            item["themes"] = season["themes"]
        if "heroes" in season:
            item["heroes"] = season["heroes"]
        result.append(item)
    return result


def default_to(value, fallback):
    """The twin of JavaScript's `??`: fall back only on absent, never on 0 or False.

    Python's `or` falls back on every falsy value, so `row.get("days") or 0` and `row.days ?? 0` agree only
    while the fallback happens to BE the falsy value. Spelled out here so the next default that is not zero
    does not drift the twins apart in silence.
    """
    return fallback if value is None else value


def resolve_year(keep, iso_date=None):
    """Twin of resolveYear: one calendar year's wheel slices, straight off the exporter's numbers.

    No arithmetic at all — the days, percents and degrees are integers the exporter apportioned once, which
    is what makes this comparable to the JavaScript at all.
    """
    year = (iso_date or "")[:4]
    rows = default_to(keep.get("years"), [])
    row = next((entry for entry in rows if isinstance(entry, dict) and entry.get("year") == year), None)
    entry = calendar_entry_for_date(keep, iso_date) if iso_date else None
    current_season_key = entry["season"] if entry else None
    if row is None:
        return {"status": "missing", "year": year, "daysInYear": None, "daysCovered": 0,
                "coversWholeYear": False, "firstDate": None, "lastDate": None, "slices": []}
    return {
        "status": "year",
        "year": year,
        "daysInYear": row.get("daysInYear"),
        "daysCovered": default_to(row.get("daysCovered"), 0),
        "coversWholeYear": default_to(row.get("coversWholeYear"), False),
        "firstDate": row.get("firstDate"),
        "lastDate": row.get("lastDate"),
        "slices": [{
            "key": slice_row.get("key"),
            "name": season_name(keep, slice_row.get("key")),
            "days": default_to(slice_row.get("days"), 0),
            "percent": default_to(slice_row.get("percent"), 0),
            "startDegree": default_to(slice_row.get("startDegree"), 0),
            "sweepDegree": default_to(slice_row.get("sweepDegree"), 0),
            "isCurrent": slice_row.get("key") == current_season_key,
        } for slice_row in default_to(row.get("slices"), [])],
    }
