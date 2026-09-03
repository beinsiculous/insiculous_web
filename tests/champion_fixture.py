"""An invented Champion's keep, built fresh on every call, for the resolver and writer suites.

A Champion's keep is a fort's complete file — a real household's schedule — and this repository holds
nobody's (scripts/fk_core/no_schedules.py refuses one, and tests/test_no_schedules.py holds the two
exemptions to exactly two invented WEB keeps). The resolver and the writer still need a Champion's keep
to run over, so this module BUILDS one, deterministically, with every name carrying "Example": nothing
schedule-shaped is committed, no exemption is added, and no test can pass on a stale golden.

THIS FILE DOES CALENDAR MATH ON PURPOSE. It stands in for the mason (fortknight/keep/scripts/
slabs_to_keep.py), which is the one place calendar math belongs; the resolver under test does none, and
the point of the parity suite is to prove it. Nothing here is a rule a page or a reader should copy.

The shape is the champion keep schema's (fortknight/keep/champion_keep.schema.json, schemaVersion 6):
twelve sections, every stone declared in meta.stones with four of them foci, the fourteen canonical
day keys, four blocks, five seasons in wheel order, a calendar
with two transition weeks and one season split either side of a year boundary the way Hogmanay is, and
one `years` row whose numbers are pinned as literals (see YEARS below). The cases the suites need are
built in and named as constants at the bottom.
"""
import datetime

import helpers  # noqa: F401 — puts scripts/ on the path so fk_core imports, whoever imports this first
from fk_core.keys import CATEGORY_KEY_ORDER, CATEGORY_LABELS, DAY_KEY_ORDER, slugify

WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
BLOCK_KEYS = ["early", "midday", "late", "too-dark"]

# The wheel, in order. The first segment of the calendar is deep winter's tail — the previous
# year's run of the same season, which is how Hogmanay sits either side of New Year.
SEASONS = [
    ("thaw", "Thaw"),
    ("longlight", "Longlight"),
    ("harvesttide", "Harvesttide"),
    ("firstfrost", "First Frost"),
    ("deepwinter", "Deep Winter"),
]

# (season key, whole weeks). Every segment starts on a Sunday that is `sun-a`; a segment with an odd
# number of weeks spends its last week as a transition week (dayKey null) handing over to the next.
CALENDAR_SEGMENTS = [
    ("deepwinter", 4),   # 2025-12-28 .. 2026-01-24, clipped to open on 2026-01-01 (a thu-a)
    ("thaw", 3),         # 2026-01-25 .. 2026-02-14, transition week 02-08 .. 02-14 -> longlight
    ("longlight", 4),    # 2026-02-15 .. 2026-03-14
    ("harvesttide", 5),  # 2026-03-15 .. 2026-04-18, transition week 04-12 .. 04-18 -> firstfrost
    ("firstfrost", 4),   # 2026-04-19 .. 2026-05-16
    ("deepwinter", 2),   # 2026-05-17 .. 2026-05-30, the season's next run
]
ANCHOR_SUNDAY = datetime.date(2025, 12, 28)
FIRST_DATE = "2026-01-01"
LAST_DATE = "2026-05-30"

# The `years` row, pinned rather than computed. The counts are the calendar's days per season in wheel
# order (21, 28, 35, 28, 38 — 150 in all); the percents and degrees follow the mason's `apportion`
# rule (largest remainder, integers only, equal counts get equal shares — fortknight/keep/scripts/
# slabs_to_keep.py). They are literals here so the fixture carries no second implementation of that
# rule: test_champion_fixture.py checks they still sum and still match the calendar it builds.
YEARS = [{
    "year": "2026",
    "daysInYear": 365,
    "daysCovered": 150,
    "coversWholeYear": False,
    "firstDate": FIRST_DATE,
    "lastDate": LAST_DATE,
    "slices": [
        {"key": "thaw", "days": 21, "percent": 14, "startDegree": 0, "sweepDegree": 51},
        {"key": "longlight", "days": 28, "percent": 19, "startDegree": 51, "sweepDegree": 67},
        {"key": "harvesttide", "days": 35, "percent": 23, "startDegree": 118, "sweepDegree": 84},
        {"key": "firstfrost", "days": 28, "percent": 19, "startDegree": 202, "sweepDegree": 67},
        {"key": "deepwinter", "days": 38, "percent": 25, "startDegree": 269, "sweepDegree": 91},
    ],
}]


def _iso(date):
    return date.isoformat()


def _day_key_parts(day_key):
    weekday_short, variant = day_key.split("-")
    weekday = next(name for name in WEEKDAY_NAMES if name.lower().startswith(weekday_short))
    return weekday, variant.upper()


def _task_id(day_key, block_key, step):
    return f"{day_key}-{block_key}-{slugify(step)}"


def _blocks():
    rows = [
        ("early", "Early", "08:00", "11:00", "Breakfast", "Brunch"),
        ("midday", "Midday", "11:00", "15:00", "Brunch", "Snack"),
        ("late", "Late", "15:00", "18:00", "Snack", "Dinner"),
        ("too-dark", "Too dark", "18:00", "08:00", "Dinner", "Breakfast"),
    ]
    return [{
        "key": key, "label": label, "start": start, "end": end,
        "wrapsMidnight": end <= start, "mealPrimary": primary, "mealSecondary": secondary,
        "sourceRow": index + 2,
    } for index, (key, label, start, end, primary, secondary) in enumerate(rows)]


def _days():
    days = []
    for index, day_key in enumerate(DAY_KEY_ORDER, start=1):
        weekday, variant = _day_key_parts(day_key)
        main_focus = "flexible" if index == 8 else CATEGORY_KEY_ORDER[(index - 1) % 7]
        main_focus_label = "FLEXIBLE" if main_focus == "flexible" else CATEGORY_LABELS[main_focus].upper()
        block_focus = {"early": "Example prep", "midday": main_focus_label.title(), "late": "Example wind-down"}
        if index == 3:
            block_focus["late"] = None
        if index == 8:
            block_focus = {"early": "Flexible", "midday": "Flexible", "late": "Flexible"}
        days.append({
            "index": index, "dayKey": day_key, "weekday": weekday, "variant": variant,
            "mainFocus": main_focus, "mainFocusLabel": main_focus_label,
            "blockFocus": block_focus, "sourceRow": index + 1,
        })
    return days


def _seasons():
    seasons = []
    for index, (key, name) in enumerate(SEASONS):
        foci = [CATEGORY_KEY_ORDER[(index + offset) % 7] for offset in range(4)]
        seasons.append({
            "key": key, "name": name,
            "gregorianRange": f"Example range {index + 1}",
            "durationText": None,
            "startDescription": f"Example rule for {name}",
            "startRule": {"kind": "nth-weekday", "nth": 1, "weekday": "sunday", "month": index + 1},
            "startDayKey": "sun-a",
            "safeOutsidePercent": 20 * (index + 1),
            "focus": foci,
            "typed": {},
            "produce": {
                "vegetables": {"hero": f"Example root {index}", "secondary": f"Example leaf {index}",
                               "tertiary": f"Example pod {index}", "quaternary": f"Example bulb {index}"},
                "fruit": {"hero": f"Example berry {index}", "secondary": f"Example stone fruit {index}",
                          "tertiary": f"Example citrus {index}"},
            },
            "mealIdeas": {"Example feast": f"Example roast {index}", "Desserts": f"Example tart {index}"},
            "sourceRow": index + 3,
        })
    return seasons


def _calendar():
    """Every date from FIRST_DATE to LAST_DATE: its season, week, day key (null in a transition week)."""
    rows = []
    cursor = ANCHOR_SUNDAY
    for segment_index, (season_key, weeks) in enumerate(CALENDAR_SEGMENTS):
        next_season = CALENDAR_SEGMENTS[segment_index + 1][0] if segment_index + 1 < len(CALENDAR_SEGMENTS) else None
        transition_week = weeks if weeks % 2 == 1 else None
        for day_offset in range(weeks * 7):
            date = cursor + datetime.timedelta(days=day_offset)
            week = day_offset // 7 + 1
            in_transition = transition_week is not None and week == transition_week
            rows.append({
                "date": _iso(date),
                "dayKey": None if in_transition else DAY_KEY_ORDER[day_offset % 14],
                "season": season_key,
                "weekOfSeason": week,
                "transition": in_transition,
                "transitionTo": next_season if in_transition else None,
            })
        cursor = cursor + datetime.timedelta(days=weeks * 7)
    return [row for row in rows if FIRST_DATE <= row["date"] <= LAST_DATE]


def _tasks():
    day_index = {day_key: index for index, day_key in enumerate(DAY_KEY_ORDER)}
    rows = []

    def add(day_key, block_key, group, step, category, serves=()):
        rows.append({
            "id": _task_id(day_key, block_key, step), "group": group, "step": step,
            "dayKey": day_key, "block": block_key, "category": category,
            "serves": [{"role": role, "dayKey": serve_day,
                        "daysAfter": (day_index[serve_day] - day_index[day_key]) % 14}
                       for role, serve_day in serves],
            "sourceRow": len(rows) + 2,
        })

    for day_key in DAY_KEY_ORDER:
        weekday, variant = _day_key_parts(day_key)
        add(day_key, "early", "Cleaning", f"Example tidy {weekday} {variant}", "cleaning")
    # Two tasks in one group on one block, so grouping is exercised.
    add("sun-a", "early", "Cleaning", "Example dust", "cleaning")
    # The carry-over cases: a step assigned twice a fortnight (mon-b then mon-a; wed-b then wed-a).
    add("mon-b", "early", "Cleaning", "Example back yard", "cleaning")
    add("mon-a", "early", "Cleaning", "Example back yard", "cleaning")
    add("wed-b", "midday", "Cleaning", "Example scrub the sink", "cleaning")
    add("wed-a", "midday", "Cleaning", "Example scrub the sink", "cleaning")
    # A skip on the fortnight's last day, which must not cross into the next fortnight.
    add("sat-b", "late", "Laundry", "Example fold and put away", "cleaning")
    add("tue-a", "midday", "Open for Appointments", "Example open", "operations")
    # The one meal-prep task, cooked the next day and eaten again three days on.
    add("thu-a", "early", "Meal Prep & Store", "Example smoothies", "meals",
        serves=(("cook", "fri-b"), ("leftovers", "sun-b")))
    return rows


def _timing(estimated_start, time_start, time_finished, estimated_end):
    return {"estimatedStart": estimated_start, "travelPrepComplete": time_start, "timeStart": time_start,
            "timeFinished": time_finished, "estimatedEnd": estimated_end}


def _appointments():
    rows = [
        ("Example piano", "sun-a", "midday", _timing("11:30", "12:00", "13:00", "13:15"), "friends-family", "no", False),
        ("Example choir", "sun-a", "midday", _timing("13:30", "14:00", "14:45", "15:00"), "spirituality-development", "some", False),
        ("Example dentist", "tue-a", "midday", _timing("12:00", "12:30", "13:00", "13:30"), "health", "yes", False),
        ("Example barber", "tue-a", "midday", _timing("12:00", "12:15", "12:45", "13:00"), "health", None, False),
        ("Example night shift", "fri-b", "too-dark", _timing("00:30", "01:00", "05:00", "05:30"), "working", "no", False),
        ("Example private appointment", "thu-a", "late", _timing("15:30", "16:00", "17:00", "17:30"), "operations", "no", True),
    ]
    return [{
        "id": f"{day_key}-{block}-{slugify(title)}", "title": title, "dayKey": day_key, "block": block,
        "flexibility": flexibility, "timing": timing, "category": category, "link": None,
        "omitFromKeep": omit, "sourceRow": index + 2,
    } for index, (title, day_key, block, timing, category, flexibility, omit) in enumerate(rows)]


def _menu():
    rows = []
    for slot in ("brunch", "snack", "dinner"):
        for number in range(1, 8):
            cook_day = DAY_KEY_ORDER[(number - 1) * 2]
            leftovers_day = DAY_KEY_ORDER[(number - 1) * 2 + 1]
            rows.append({
                "mealKey": f"{slot.title()}{number}", "slot": slot,
                "cookDay": cook_day, "leftoversDay": leftovers_day,
                "menu": f"Example {slot} {number}", "cookExtra": False, "cookExtraNote": None,
                "sourceRow": len(rows) + 3,
            })
    by_key = {row["mealKey"]: row for row in rows}
    by_key["Brunch1"]["menu"] = "FLEXIBLE"                      # a value, not a gap
    by_key["Dinner4"]["menu"] = "Example dinner OUT"            # so is OUT
    by_key["Dinner2"].update(cookExtra=True, cookExtraNote="Example: the extra becomes tacos")
    # A dish eaten once: its leftovers day is null, and its day's second serving is a row of its own.
    by_key["Snack7"]["leftoversDay"] = None
    rows.append({"mealKey": "Snack8", "slot": "snack", "cookDay": DAY_KEY_ORDER[13], "leftoversDay": None,
                 "menu": "Example snack 8", "cookExtra": False, "cookExtraNote": None, "sourceRow": len(rows) + 3})
    return rows


def _meals(menu):
    """The resolved per-day view, inverted from the menu the way the mason does it."""
    rows = []
    for index, day_key in enumerate(DAY_KEY_ORDER):
        row = {"dayKey": day_key, "sourceRow": index + 2}
        for slot in ("brunch", "snack", "dinner"):
            row[slot] = next(entry["menu"] for entry in menu
                             if entry["slot"] == slot and day_key in (entry["cookDay"], entry["leftoversDay"]))
        rows.append(row)
    return rows


def build_champion_keep():
    """A fresh, conforming, invented Champion's keep. Every call returns a new object."""
    menu = _menu()
    return {
        "meta": {
            "sourceSlabs": ["ExampleFortKnightSlab.xlsx", "ExampleForkKnifeSlab.xlsx", "ExampleFreshKeepSlab.xlsx",
                            "ExampleFretKnotSlab.xlsx", "ExampleFoeKissSlab.xlsx", "ExampleFolkKnowledgeSlab.xlsx",
                            "ExampleFunKneeSlab.xlsx", "ExampleFixKnittSlab.xlsx"],
            # Composition (beinsiculous/fortknight#19): every stone, and the four foci the shipped slabs
            # mark — the McIntosh keep's shape, invented content.
            "stones": ["fort-knight", "fork-knife", "fresh-keep", "fret-knot", "foe-kiss", "folk-knowledge",
                       "fun-knee", "fix-knitt"],
            "foci": ["fork-knife", "fresh-keep", "fret-knot", "foe-kiss"],
            "generatedBy": "tests/champion_fixture.py",
            "schemaVersion": 6,
            "exportedAt": "2026-08-27T18:00:00+00:00",
            "seasonNote": "Example: every fortnight starts on Sunday A.",
            "assumptions": [],
        },
        "categories": [{"key": key, "label": CATEGORY_LABELS[key], "subjects": [f"Example {CATEGORY_LABELS[key]} subject"]}
                       for key in CATEGORY_KEY_ORDER],
        "blocks": _blocks(),
        "days": _days(),
        "seasons": _seasons(),
        "tasks": _tasks(),
        "appointments": _appointments(),
        "menu": menu,
        "meals": _meals(menu),
        "cleaningAreas": [{"area": "Example sink", "bagua": "Example north", "room": "Example kitchen", "sourceRow": 2},
                          {"area": "Example floor", "bagua": "Example north", "room": "Example kitchen", "sourceRow": 3},
                          {"area": "Example mirror", "bagua": "Example east", "room": "Example bathroom", "sourceRow": 4}],
        "calendar": _calendar(),
        "years": [dict(row, slices=[dict(slice_row) for slice_row in row["slices"]]) for row in YEARS],
    }


# Dates the suites reach for, named so no test carries a bare literal.
FIRST_SUN_A = "2026-01-11"               # the first full fortnight opens here; 01-01 is a thu-a
A_DATE_IN_CALENDAR = "2026-02-18"        # a wed-b in longlight's first week
A_TRANSITION_DATE = "2026-02-10"         # inside thaw's transition week
DATE_BEFORE_CALENDAR = "2025-12-31"
DATE_IN_YEAR_PAST_CALENDAR = "2026-12-31"  # 2026 has a wheel; the calendar stops on 2026-05-30
DATE_PAST_CALENDAR = "2027-06-01"
