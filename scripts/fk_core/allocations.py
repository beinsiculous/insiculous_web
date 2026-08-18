"""Time groupings per category — the numeric heart of FortKnight.

Two complementary views of one fortnight:
  byBlockFocus   every focus-carrying block (early/midday/late × 14 days) contributes its full
                 duration to the category it is focused on ("flexible" is tracked separately).
  byActivities   timed activities contribute their measured duration; untimed activities split
                 the minutes left in their block evenly. Multi-category activities split evenly.

Both roll up by category, day key, block, and category × block, and produce shares of the
focus-carrying window (08:00-18:00 = 600 minutes/day = 8400 minutes/fortnight).
The byBlockFocus shares are what analyze_allocations.py exports as the baseline weights.
"""
from . import keys
from .derive import block_focus_grid


def _empty_category_totals(include_flexible):
    totals = {category: 0 for category in keys.CATEGORY_KEY_ORDER}
    if include_flexible:
        totals[keys.FLEXIBLE_FOCUS] = 0
    return totals


def _shares(totals):
    grand_total = sum(totals.values())
    return {key: (round(value / grand_total, 4) if grand_total else 0) for key, value in totals.items()}


def focus_window(blocks):
    focus_blocks = [blocks["blocks"][block_key] for block_key in keys.FOCUS_BLOCK_KEYS]
    minutes_per_day = sum(block["durationMinutes"] for block in focus_blocks)
    return {
        "start": focus_blocks[0]["start"],
        "end": focus_blocks[-1]["end"],
        "minutesPerDay": minutes_per_day,
        "minutesPerCycle": minutes_per_day * len(keys.DAY_KEY_ORDER),
    }


def allocate_by_block_focus(days, blocks):
    by_category = _empty_category_totals(include_flexible=True)
    by_day = {}
    by_block = {block_key: _empty_category_totals(True) for block_key in keys.FOCUS_BLOCK_KEYS}
    by_category_and_block = {category: {block_key: 0 for block_key in keys.FOCUS_BLOCK_KEYS} for category in by_category}
    for day_key in days["order"]:
        day = days["days"][day_key]
        by_day[day_key] = _empty_category_totals(True)
        for block_key in keys.FOCUS_BLOCK_KEYS:
            focus = (day.get("blockFocus") or {}).get(block_key, keys.FLEXIBLE_FOCUS)  # an unassigned block is flexible time
            minutes = blocks["blocks"][block_key]["durationMinutes"]
            by_category[focus] += minutes
            by_day[day_key][focus] += minutes
            by_block[block_key][focus] += minutes
            by_category_and_block[focus][block_key] += minutes
    return {
        "method": "Each early/midday/late block gives its full duration to its focus; flexible blocks are counted as 'flexible'.",
        "byCategory": by_category,
        "shareByCategory": _shares(by_category),
        "byDay": by_day,
        "byBlock": by_block,
        "byCategoryAndBlock": by_category_and_block,
    }


def _group_activities(activities):
    grouped = {}
    for activity in activities["activities"]:
        grouped.setdefault((activity["dayKey"], activity["block"]), []).append(activity)
    return grouped


def allocate_by_activities(activities, blocks):
    by_category = _empty_category_totals(include_flexible=False)
    by_day = {}
    by_block = {block_key: _empty_category_totals(False) for block_key in keys.BLOCK_KEY_ORDER}
    by_category_and_block = {category: {block_key: 0 for block_key in keys.BLOCK_KEY_ORDER} for category in by_category}
    per_activity = {}
    for (day_key, block_key), group in _group_activities(activities).items():
        block_minutes = blocks["blocks"][block_key]["durationMinutes"]
        timed = [activity for activity in group if activity["timing"]]
        untimed = [activity for activity in group if not activity["timing"]]
        timed_minutes = sum(activity["timing"]["durationMinutes"] + activity["timing"]["prepMinutes"] for activity in timed)
        remaining_minutes = max(block_minutes - timed_minutes, 0)
        untimed_share = round(remaining_minutes / len(untimed)) if untimed else 0
        for activity in group:
            if activity["timing"]:
                minutes = activity["timing"]["durationMinutes"] + activity["timing"]["prepMinutes"]
                method = "measured"
            else:
                minutes = untimed_share
                method = "block-remainder-split"
            per_activity[activity["id"]] = {"minutes": minutes, "method": method}
            by_day.setdefault(day_key, _empty_category_totals(False))
            per_category_minutes = minutes / len(activity["categories"])
            for category in activity["categories"]:
                by_category[category] += per_category_minutes
                by_day[day_key][category] += per_category_minutes
                by_block[block_key][category] += per_category_minutes
                by_category_and_block[category][block_key] += per_category_minutes
    rounded = lambda mapping: {key: round(value) for key, value in mapping.items()}  # noqa: E731
    return {
        "method": "Timed activities count duration + prep minutes; untimed activities split the block's remaining minutes evenly; multi-category activities split evenly across categories.",
        "byCategory": rounded(by_category),
        "shareByCategory": _shares(by_category),
        "byDay": {day_key: rounded(totals) for day_key, totals in by_day.items()},
        "byBlock": {block_key: rounded(totals) for block_key, totals in by_block.items()},
        "byCategoryAndBlock": {category: rounded(totals) for category, totals in by_category_and_block.items()},
        "perActivity": per_activity,
    }


def compute_allocations(data):
    return {
        "focusWindow": focus_window(data["blocks"]),
        "byBlockFocus": allocate_by_block_focus(data["days"], data["blocks"]),
        "byActivities": allocate_by_activities(data["activities"], data["blocks"]),
    }


def preferred_blocks_for_category(by_category_and_block, category):
    """Blocks ordered by how much of the category's time they carry (ties keep block order)."""
    minutes_by_block = by_category_and_block.get(category, {})
    return [block_key for block_key, minutes in sorted(minutes_by_block.items(), key=lambda pair: (-pair[1], keys.FOCUS_BLOCK_KEYS.index(pair[0]))) if minutes > 0]


def weights_from_allocations(allocations, days, weights_id="baseline"):
    """Express the byBlockFocus view in the weights (questionnaire) contract."""
    block_focus = allocations["byBlockFocus"]
    categories = {}
    for category in keys.CATEGORY_KEY_ORDER:
        categories[category] = {
            "share": block_focus["shareByCategory"][category],
            "minutesPerCycle": block_focus["byCategory"][category],
            "preferredBlocks": preferred_blocks_for_category(block_focus["byCategoryAndBlock"], category),
        }
    return {
        "$schema": "./schema/weights.schema.json",
        "schemaVersion": 1,
        "id": weights_id,
        "source": "baseline",
        "cycleLengthDays": len(keys.DAY_KEY_ORDER),
        "wakingWindow": allocations["focusWindow"],
        "categories": categories,
        "flexibleShare": block_focus["shareByCategory"][keys.FLEXIBLE_FOCUS],
        "blockFocusGrid": block_focus_grid(days),
        "notes": [
            "Derived from the data set's per-block focus grid by scripts/analyze_allocations.py (the workbook example set gives the historical baseline).",
            "The questionnaire will eventually produce a file of this same shape; a generator will turn it into a schedule.",
        ],
    }
