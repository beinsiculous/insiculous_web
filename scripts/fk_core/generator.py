"""Weights -> a proposed blockFocusGrid (roadmap 2, first half; docs/generator.md).

The rule, in one place (mirrored exactly by src/lib/shared/generator-rules.js — keep both in sync):
  1. Every (day key x focus block) cell gives its whole duration to one focus, so a category's target is
     share x the focus minutes of the fortnight; `flexible` gets flexibleShare. Targets stay in minutes
     because cells are unequal (the workbook's are 180/240/180, a profile's cuts are wherever they fell).
  2. Pass 1 pins: a rest day's cells are `flexible`; a cell whose anchors (imported fixed activities,
     standing appointments) of one category cover at least `anchorPinCoverage` of the block is pinned to
     that category. Pooled anchors (no day key) and unscheduled-block anchors never pin.
  3. Pass 2 fills the other cells in a fixed order (day-key order x block order) by sequential
     apportionment: a category is eligible while taking the cell keeps it within `overshootSlackCells`
     cells of its target; among the eligible the highest score wins — relative deficit after taking the
     cell, plus soft bonuses for the category's preferredBlocks, the energy-peak block for a category the
     person struggles with, the current season's focus list, and a small penalty for repeating the same
     focus in the same block on the other variant of the weekday (A/B alternation). Ties keep candidate
     order (categories, then flexible). When nobody is eligible the largest absolute deficit takes the cell.
  4. Every cell carries a short reason; warnings name shares too small for a cell, rest days pushing
     flexible past its share, and unknown season focus ids. The appointment blocks do not dictate focus.
  5. Activities inside the cells (generate_activities): subject sessions sized from the Focus-1 hours so a
     category's sessions add up to its minutesPerCycle, one short daily activity per practice, one activity per
     meal at its slot; anchors already in a cell eat its capacity; leftovers spill into flexible cells.
Tunables live in data/questionnaire.json -> `generator`.
"""
import math

from . import keys
from .meal_plan import day_label, menu_for_day
from .timeconv import MINUTES_PER_DAY, minutes_to_time_string, time_string_to_minutes

REST_DAY_REASON = "rest day"
OVER_SHARE_REASON = "over share"
PROPOSED_SOURCE = "proposed"
SPIRITUALITY_CATEGORY = "spirituality-development"
DEFAULT_GENERATOR = {
    "anchorPinCoverage": 0.5,
    "overshootSlackCells": 0.5,
    "preferredBlockWeight": 0.2,
    "energyPeakWeight": 0.15,
    "seasonFocusWeight": 0.1,
    "alternationWeight": 0.1,
    "energyPeakBlock": {"morning": "first", "midday": "middle", "evening": "last", "varies": None},
    "sessionGridMinutes": 5,
    "maxSessionMinutes": 120,
    "practiceMinutes": 15,
    "mealMinutes": 30,
    "mealSlotTimes": {"early-morning": "07:00", "mid-morning": "10:00", "afternoon": "13:00", "evening": "18:00", "late-evening": "21:00", "anytime": None},
}


def _round_half_up(value):
    return int(math.floor(value + 0.5))


def generator_settings(questionnaire):
    """The `generator` tunables of a questionnaire file, defaults filled in."""
    return {**DEFAULT_GENERATOR, **((questionnaire or {}).get("generator") or {})}


def focus_blocks_of(weights, fallback_blocks=None):
    """The profile's focus blocks in order; a thin weights file without `blocks` (the baseline) falls back to
    a data set's blocks.json (`fallback_blocks`)."""
    blocks = [block for block in weights.get("blocks", []) if block.get("carriesFocus")]
    if blocks or not fallback_blocks:
        return [dict(block) for block in blocks]
    return [{"key": key, **{field: fallback_blocks["blocks"][key][field] for field in ("start", "end", "durationMinutes", "carriesFocus")}}
            for key in fallback_blocks["order"] if fallback_blocks["blocks"][key].get("carriesFocus")]


def other_variant_day_key(day_key):
    """sun-a <-> sun-b: the same weekday in the other week."""
    weekday, variant = day_key.split("-")
    return f"{weekday}-{'b' if variant == 'a' else 'a'}"


def weekday_of_day_key(day_key):
    short = day_key.split("-")[0]
    return next(name for name in keys.WEEKDAY_NAMES if name.startswith(short))


def peak_block_index(energy_peak, focus_block_count, settings):
    """Which focus block (index) carries the demanding focus for this energy peak, or None."""
    position = settings["energyPeakBlock"].get(energy_peak)
    if position is None or focus_block_count == 0:
        return None
    return {"first": 0, "middle": (focus_block_count - 1) // 2, "last": focus_block_count - 1}[position]


def anchor_coverage_by_category(anchors, day_key, block, waking_start_minutes):
    """Minutes each category's anchors overlap `block` on `day_key`, in category order (offsets from the
    waking window's start, so blocks and anchors that wrap midnight measure the same way)."""
    block_start = (time_string_to_minutes(block["start"]) - waking_start_minutes) % MINUTES_PER_DAY
    block_end = block_start + block["durationMinutes"]
    coverage = {}
    for anchor in anchors:
        if anchor.get("dayKey") != day_key or anchor.get("block") is None:
            continue
        start = (time_string_to_minutes(anchor["start"]) - waking_start_minutes) % MINUTES_PER_DAY
        end = start + (time_string_to_minutes(anchor["end"]) - time_string_to_minutes(anchor["start"])) % MINUTES_PER_DAY
        overlap = min(end, block_end) - max(start, block_start)
        if overlap <= 0:
            continue
        for category_key in anchor.get("categories", []):
            if category_key in keys.CATEGORY_KEY_ORDER:
                coverage.setdefault(category_key, {"minutes": 0, "activityIds": []})
                coverage[category_key]["minutes"] += overlap
                if anchor["activityId"] not in coverage[category_key]["activityIds"]:
                    coverage[category_key]["activityIds"].append(anchor["activityId"])
    return coverage


def generate_block_focus_grid(weights, questionnaire, season_focus=None, fallback_blocks=None):
    """A proposed blockFocusGrid for a weights object: {blockFocusGrid, reasons, warnings}."""
    settings = generator_settings(questionnaire)
    focus_blocks = focus_blocks_of(weights, fallback_blocks)
    candidates = keys.CATEGORY_KEY_ORDER + [keys.FLEXIBLE_FOCUS]
    warnings = []
    season_focus = list(season_focus or [])
    for focus in season_focus:
        if focus not in keys.CATEGORY_KEY_ORDER:
            warnings.append(f"seasonFocus: unknown category {focus!r}; ignored")
    season_focus = [focus for focus in season_focus if focus in keys.CATEGORY_KEY_ORDER]

    total_minutes = sum(block["durationMinutes"] for block in focus_blocks) * len(keys.DAY_KEY_ORDER)
    categories = weights.get("categories", {})
    target = {category_key: categories.get(category_key, {}).get("share", 0) * total_minutes for category_key in keys.CATEGORY_KEY_ORDER}
    target[keys.FLEXIBLE_FOCUS] = weights.get("flexibleShare", 0) * total_minutes
    delivered = {candidate: 0 for candidate in candidates}
    smallest_cell = min((block["durationMinutes"] for block in focus_blocks), default=0)
    unschedulable = [category_key for category_key in keys.CATEGORY_KEY_ORDER if 0 < target[category_key] < (1 - settings["overshootSlackCells"]) * smallest_cell]
    for category_key in unschedulable:
        warnings.append(f"{category_key}: share {categories[category_key]['share']} ({_round_half_up(target[category_key])} min per fortnight) is less than a block can carry; not scheduled")

    waking_start = time_string_to_minutes((weights.get("wakingWindow") or {}).get("start") or (focus_blocks[0]["start"] if focus_blocks else "00:00"))
    anchors = (weights.get("blockSplit") or {}).get("anchors", [])
    rest_days = set(weights.get("restDays", []))
    peak_index = peak_block_index(weights.get("energyPeak"), len(focus_blocks), settings)

    grid = {day_key: {} for day_key in keys.DAY_KEY_ORDER}
    reasons = {day_key: {} for day_key in keys.DAY_KEY_ORDER}
    # Pass 1: pins.
    for day_key in keys.DAY_KEY_ORDER:
        for block in focus_blocks:
            if weekday_of_day_key(day_key) in rest_days:
                grid[day_key][block["key"]] = keys.FLEXIBLE_FOCUS
                reasons[day_key][block["key"]] = REST_DAY_REASON
                delivered[keys.FLEXIBLE_FOCUS] += block["durationMinutes"]
                continue
            coverage = anchor_coverage_by_category(anchors, day_key, block, waking_start)
            if not coverage:
                continue
            best_key = max(coverage, key=lambda category_key: (coverage[category_key]["minutes"], -keys.CATEGORY_KEY_ORDER.index(category_key)))
            fraction = coverage[best_key]["minutes"] / block["durationMinutes"]
            if fraction >= settings["anchorPinCoverage"]:
                grid[day_key][block["key"]] = best_key
                reasons[day_key][block["key"]] = f"anchor: {', '.join(coverage[best_key]['activityIds'])} covers {_round_half_up(fraction * 100)}%"
                delivered[best_key] += block["durationMinutes"]
    if delivered[keys.FLEXIBLE_FOCUS] > target[keys.FLEXIBLE_FOCUS] and rest_days:
        warnings.append(f"rest days give flexible {delivered[keys.FLEXIBLE_FOCUS]} min, beyond its {_round_half_up(target[keys.FLEXIBLE_FOCUS])} min share")

    # Pass 2: fill.
    for day_key in keys.DAY_KEY_ORDER:
        twin_day_key = other_variant_day_key(day_key)
        for block_index, block in enumerate(focus_blocks):
            block_key = block["key"]
            if block_key in grid[day_key]:
                continue
            minutes = block["durationMinutes"]
            best, best_score, best_tags = None, None, []
            for candidate in candidates:
                if target[candidate] <= 0 or delivered[candidate] + minutes > target[candidate] + settings["overshootSlackCells"] * minutes:
                    continue
                score = (target[candidate] - delivered[candidate] - minutes) / target[candidate]
                tags = []
                preferred = categories.get(candidate, {}).get("preferredBlocks", []) if candidate != keys.FLEXIBLE_FOCUS else []
                if block_key in preferred:
                    score += settings["preferredBlockWeight"] * (len(preferred) - preferred.index(block_key)) / len(preferred)
                    tags.append("preferred block")
                if peak_index == block_index and candidate != keys.FLEXIBLE_FOCUS and categories.get(candidate, {}).get("sentiment") == "struggle":
                    score += settings["energyPeakWeight"]
                    tags.append("energy peak")
                if candidate in season_focus:
                    score += settings["seasonFocusWeight"] * (len(season_focus) - season_focus.index(candidate)) / len(season_focus)
                    tags.append(f"season focus #{season_focus.index(candidate) + 1}")
                if grid[twin_day_key].get(block_key) == candidate:
                    score -= settings["alternationWeight"]
                    tags.append(f"alternates with {twin_day_key}")
                if best_score is None or score > best_score:
                    best, best_score, best_tags = candidate, score, tags
            if best is None:
                scheduled = [candidate for candidate in candidates if target[candidate] > 0 and candidate not in unschedulable] or [keys.FLEXIBLE_FOCUS]
                best = max(scheduled, key=lambda candidate: (target[candidate] - delivered[candidate], -candidates.index(candidate)))
                primary = OVER_SHARE_REASON
            else:
                primary = f"behind share ({_round_half_up(delivered[best])}/{_round_half_up(target[best])} min)"
            grid[day_key][block_key] = best
            reasons[day_key][block_key] = "; ".join([primary, *best_tags])
            delivered[best] += minutes
    return {"blockFocusGrid": grid, "reasons": reasons, "warnings": warnings}


def diff_block_focus_grid(imported, proposed):
    """Cell-by-cell comparison of two grids: {changes: [{dayKey, block, imported, proposed}], counts}."""
    imported = imported or {}
    proposed = proposed or {}
    changes = []
    counts = {"same": 0, "changed": 0, "added": 0, "removed": 0}
    for day_key in keys.DAY_KEY_ORDER:
        proposed_cells = proposed.get(day_key) or {}
        imported_cells = imported.get(day_key) or {}
        block_keys = list(proposed_cells) + [block_key for block_key in imported_cells if block_key not in proposed_cells]
        for block_key in block_keys:
            before, after = imported_cells.get(block_key), proposed_cells.get(block_key)
            if before == after:
                counts["same"] += 1
                continue
            counts["changed" if before is not None and after is not None else "added" if before is None else "removed"] += 1
            changes.append({"dayKey": day_key, "block": block_key, "imported": before, "proposed": after})
    return {"changes": changes, "counts": counts}


# ---------- activities inside the cells ----------

def block_key_for_time(blocks, time):
    """Which of `blocks` ({key, start, end}) contains the wall time (HH:MM); wraps past midnight. None when none.
    Twin of src/lib/shared/day-plan.js blockKeyForTime."""
    minutes = time_string_to_minutes(time)
    for block in blocks:
        start = time_string_to_minutes(block["start"])
        end = time_string_to_minutes(block["end"])
        if end <= start:
            end += MINUTES_PER_DAY  # a block that runs past midnight
        if start <= minutes < end:
            return block["key"]
        if start <= minutes + MINUTES_PER_DAY < end:
            return block["key"]
    return None


def all_blocks_of(weights, fallback_blocks=None):
    """Every block of the profile (unscheduled included), for placing clock times; the baseline falls back to blocks.json."""
    blocks = list(weights.get("blocks", []))
    if blocks or not fallback_blocks:
        return blocks
    return [{"key": key, **{field: fallback_blocks["blocks"][key][field] for field in ("start", "end", "durationMinutes", "carriesFocus")}} for key in fallback_blocks["order"]]


def anchor_minutes_in_block(anchors, day_key, block, waking_start_minutes):
    """Minutes of `block` on `day_key` taken by anchors (each anchor once, whatever its categories)."""
    block_start = (time_string_to_minutes(block["start"]) - waking_start_minutes) % MINUTES_PER_DAY
    block_end = block_start + block["durationMinutes"]
    taken = 0
    for anchor in anchors:
        if anchor.get("dayKey") != day_key or anchor.get("block") is None:
            continue
        start = (time_string_to_minutes(anchor["start"]) - waking_start_minutes) % MINUTES_PER_DAY
        end = start + (time_string_to_minutes(anchor["end"]) - time_string_to_minutes(anchor["start"])) % MINUTES_PER_DAY
        taken += max(0, min(end, block_end) - max(start, block_start))
    return taken


def subject_pools(weights, categories):
    """Per category (in order): the subjects that carry daily time, in categories.json order, with the minutes each
    contributes per day (keys.subject_daily_minutes — the same weight that built the category's share). Subjects
    that contribute nothing — peripheral, or on the section cadence — are done in flexible time, not in cells."""
    subjects = weights.get("subjects") or {}
    pools = {}
    for category_key in keys.CATEGORY_KEY_ORDER:
        pool = []
        for subject_id in categories["categories"][category_key]["subjects"]:
            subject = subjects.get(subject_id)
            if not subject or not subject.get("minutesPerDay"):
                continue
            daily_minutes = keys.subject_daily_minutes(subject)
            if daily_minutes <= 0:
                continue
            pool.append((subject_id, daily_minutes))
        pools[category_key] = pool
    return pools


def generate_activities(weights, grid, questionnaire, categories, fallback_blocks=None):
    """Proposed activities inside the cells of `grid` (the person's own or the proposal's):
    {activities, placedMinutes, warnings}. See the module docstring, rule 5, and docs/generator.md."""
    settings = generator_settings(questionnaire)
    grid_minutes = settings["sessionGridMinutes"]
    focus_blocks = focus_blocks_of(weights, fallback_blocks)
    all_blocks = all_blocks_of(weights, fallback_blocks)
    grid = grid or {}
    activities, warnings = [], []
    if not focus_blocks:
        return {"activities": [], "placedMinutes": {}, "warnings": ["activities: no focus blocks"]}
    if not weights.get("subjects"):
        return {"activities": [], "placedMinutes": {}, "warnings": ["activities: the weights carry no subjects; nothing to place"]}
    focus_block_keys = [block["key"] for block in focus_blocks]
    waking_start = time_string_to_minutes((weights.get("wakingWindow") or {}).get("start") or focus_blocks[0]["start"])
    anchors = (weights.get("blockSplit") or {}).get("anchors", [])
    rest_days = set(weights.get("restDays", []))
    weights_categories = weights.get("categories") or {}
    subject_labels = {subject_id: subject["label"] for subject_id, subject in categories["subjects"].items()}
    category_labels = {category_key: category["label"] for category_key, category in categories["categories"].items()}
    practice_labels = {option["id"]: option["label"] for option in (questionnaire.get("options") or {}).get("practices", [])}

    def focus_of(day_key, block_key):
        return (grid.get(day_key) or {}).get(block_key) or keys.FLEXIBLE_FOCUS

    capacity = {day_key: {block["key"]: max(0, block["durationMinutes"] - anchor_minutes_in_block(anchors, day_key, block, waking_start)) for block in focus_blocks} for day_key in keys.DAY_KEY_ORDER}
    counts = {}

    def emit(kind, slug, title, day_key, block_key, priority, category_keys, minutes, reason, subject_id=None, timing=None):
        counts_key = (kind, slug, day_key, block_key)
        counts[counts_key] = counts.get(counts_key, 0) + 1
        number = counts[counts_key]
        activities.append({
            "id": f"proposed--{kind}--{slug}--{day_key}--{block_key}" + (f"--{number}" if number > 1 else ""),
            "title": title + (f" ({number})" if number > 1 else ""),
            "kind": kind,
            "dayKey": day_key,
            "block": block_key,
            "priority": priority,
            "categories": list(category_keys),
            "subjectId": subject_id,
            "timing": timing,
            "minutes": minutes,
            "reason": reason,
            "source": PROPOSED_SOURCE,
        })
        capacity[day_key][block_key] = max(0, capacity[day_key][block_key] - minutes)

    # 1. Practices, 2. meals — per day (they take capacity before the sessions are sized).
    practices = list(weights.get("practices", []))
    meals = (weights.get("meals") or {}).get("meals", [])
    meal_plan = weights.get("mealPlan") or {"items": []}
    meal_warnings = []
    for day_key in keys.DAY_KEY_ORDER:
        practice_block = next((key for key in focus_block_keys if focus_of(day_key, key) == SPIRITUALITY_CATEGORY), focus_block_keys[0])
        for practice_id in practices:
            emit("practice", practice_id, f"Practice: {practice_labels.get(practice_id, practice_id)}", day_key, practice_block, 2, [SPIRITUALITY_CATEGORY], settings["practiceMinutes"], "daily practice")
        menu = menu_for_day(meal_plan, meals, day_key)  # the ForkKnife menu names each meal's dish (its prep/cook tasks arrive as tasks)
        for meal_index, meal in enumerate(meals):
            slots = list(meal.get("slots", []))
            chosen = None
            for slot in slots:
                slot_time = settings["mealSlotTimes"].get(slot)
                if slot_time is None:
                    continue
                block_key = block_key_for_time(all_blocks, slot_time)
                if block_key in focus_block_keys:
                    chosen = (slot, slot_time, block_key)
                    break
            if chosen is None:
                warning = f"activities: meal {meal_index + 1}: {'slot' if len(slots) == 1 else 'slots'} {', '.join(slots) or '(none)'} fall outside the focus blocks; not placed"
                if warning not in meal_warnings:
                    meal_warnings.append(warning)
                continue
            slot, slot_time, block_key = chosen
            end_minutes = (time_string_to_minutes(slot_time) + settings["mealMinutes"]) % MINUTES_PER_DAY
            served = menu[meal_index] if meal_index < len(menu) else None
            name = meal.get("name") or f"Meal {meal_index + 1}"
            title = f"{name}: {served['dish']}" + (" (leftovers)" if served["leftovers"] else "") if served and served["dish"] else name
            emit("meal", f"meal-{meal_index + 1}", title, day_key, block_key, 2, ["meals"], settings["mealMinutes"], f"meal slot {slot}",
                 timing={"estimatedStart": slot_time, "estimatedEnd": minutes_to_time_string(end_minutes), "durationMinutes": settings["mealMinutes"]})
    warnings += meal_warnings
    # A cell whose anchors leave less room than its practices and meals need: they are still listed (a meal or a
    # daily habit is not optional), but the person should know the block is over-committed.
    over_committed = []
    for day_key in keys.DAY_KEY_ORDER:
        for block in focus_blocks:
            fixed = sum(activity["minutes"] for activity in activities if activity["dayKey"] == day_key and activity["block"] == block["key"])
            free = block["durationMinutes"] - anchor_minutes_in_block(anchors, day_key, block, waking_start)
            if fixed > max(0, free):
                over_committed.append(f"{day_label(day_key)} {block['key']} ({fixed} min of practices/meals, {max(0, free)} min free)")
    if over_committed:
        warnings.append("activities: over-committed by anchors: " + "; ".join(over_committed))

    # 3. Targets per subject: the usable minutes (non-rest cells after anchors, practices and meals) split by
    # category share, then by the subject's range midpoint within its category — multiples of the session grid.
    usable_minutes = sum(capacity[day_key][block_key] for day_key in keys.DAY_KEY_ORDER if weekday_of_day_key(day_key) not in rest_days for block_key in focus_block_keys)
    pools = subject_pools(weights, categories)
    need, target, placed = {}, {}, {}
    for category_key in keys.CATEGORY_KEY_ORDER:
        share = weights_categories.get(category_key, {}).get("share", 0)
        pool = pools[category_key]
        midpoint_total = sum(midpoint for _, midpoint in pool)
        if share > 0 and midpoint_total == 0:
            warnings.append(f"activities: {category_labels.get(category_key, category_key)} has a share of {share} but no subjects to carry it")
            continue
        for subject_id, midpoint in pool:
            minutes = _round_half_up(usable_minutes * share * midpoint / midpoint_total / grid_minutes) * grid_minutes if midpoint_total else 0
            need[subject_id] = target[subject_id] = minutes
            placed[subject_id] = 0

    def place_spillover(day_key, block_key, subject_id, category_key):
        """A spillover session for the neediest subject, at most maxSessionMinutes; the same subject still neediest
        extends its session instead of adding a second record to the cell."""
        minutes = math.floor(min(need[subject_id], capacity[day_key][block_key], settings["maxSessionMinutes"]) / grid_minutes) * grid_minutes
        if minutes <= 0:
            return False  # a maxSessionMinutes below the grid can place nothing: stop the cell rather than loop
        need[subject_id] -= minutes
        placed[subject_id] += minutes
        reason = f"spillover: {category_key} behind by {need[subject_id]} min"
        last = activities[-1] if activities else None
        if last and last["kind"] == "session" and last["subjectId"] == subject_id and last["dayKey"] == day_key and last["block"] == block_key:
            last["minutes"] += minutes
            last["reason"] = reason
            capacity[day_key][block_key] = max(0, capacity[day_key][block_key] - minutes)
            return True
        emit("session", subject_id, subject_labels.get(subject_id, subject_id), day_key, block_key, 4, [category_key], minutes, reason, subject_id=subject_id)
        return True

    def neediest(candidates):
        best = None
        for subject_id, category_key in candidates:
            if need.get(subject_id, 0) <= 0:
                continue
            if best is None or need[subject_id] > need[best[0]]:
                best = (subject_id, category_key)
        return best

    def proportional_split(subject_ids, minutes_available):
        """Split a cell's minutes among subjects in proportion to their remaining need (whole grid units, largest
        remainders first, ties in pool order); nobody gets more than they need."""
        needy = [subject_id for subject_id in subject_ids if need[subject_id] > 0]
        total_need = sum(need[subject_id] for subject_id in needy)
        if not needy or total_need == 0:
            return []
        if total_need <= minutes_available:
            return [(subject_id, need[subject_id]) for subject_id in needy]
        units = minutes_available // grid_minutes
        exact = {subject_id: units * need[subject_id] / total_need for subject_id in needy}
        floors = {subject_id: math.floor(exact[subject_id]) for subject_id in needy}
        leftover = units - sum(floors.values())
        by_remainder = sorted(needy, key=lambda subject_id: (-(exact[subject_id] - floors[subject_id]), needy.index(subject_id)))
        for subject_id in by_remainder[:leftover]:
            floors[subject_id] += 1
        return [(subject_id, floors[subject_id] * grid_minutes) for subject_id in needy if floors[subject_id] > 0]

    # 4. Focus fill: each focus cell's capacity is split among its category's subjects by remaining need.
    for day_key in keys.DAY_KEY_ORDER:
        if weekday_of_day_key(day_key) in rest_days:
            continue
        for block_key in focus_block_keys:
            focus = focus_of(day_key, block_key)
            if focus == keys.FLEXIBLE_FOCUS or focus not in pools or capacity[day_key][block_key] < grid_minutes:
                continue
            for subject_id, minutes in proportional_split([subject_id for subject_id, _ in pools[focus]], capacity[day_key][block_key]):
                need[subject_id] -= minutes
                placed[subject_id] += minutes
                emit("session", subject_id, subject_labels.get(subject_id, subject_id), day_key, block_key, 3, [focus], minutes, f"focus {focus}: {placed[subject_id]}/{target[subject_id]} min", subject_id=subject_id)
    # 5. Spillover into flexible cells.
    all_candidates = [(subject_id, category_key) for category_key in keys.CATEGORY_KEY_ORDER for subject_id, _ in pools[category_key]]
    for day_key in keys.DAY_KEY_ORDER:
        if weekday_of_day_key(day_key) in rest_days:
            continue
        for block_key in focus_block_keys:
            if focus_of(day_key, block_key) != keys.FLEXIBLE_FOCUS:
                continue
            while capacity[day_key][block_key] >= grid_minutes:
                best = neediest(all_candidates)
                if best is None or not place_spillover(day_key, block_key, best[0], best[1]):
                    break
    # 6. Warnings: one line per category whose subjects did not all fit. Not a failure — a category too small to
    # win whole cells (errands twice a fortnight) is done in flexible time; the line says where its minutes went.
    for category_key in keys.CATEGORY_KEY_ORDER:
        short = [(subject_id, need[subject_id]) for subject_id, _ in pools[category_key] if subject_id in need and need[subject_id] >= grid_minutes]
        if short:
            unplaced_total = sum(minutes for _, minutes in short)
            category_target = sum(target[subject_id] for subject_id, _ in pools[category_key] if subject_id in target)
            details = ", ".join(f"{subject_labels.get(subject_id, subject_id)} {minutes}" for subject_id, minutes in short)
            warnings.append(f"activities: {category_labels.get(category_key, category_key)}: {unplaced_total} of {category_target} min left for flexible time — too little to fill a cell of its own ({details})")
    return {"activities": activities, "placedMinutes": {subject_id: {"target": target[subject_id], "placed": placed[subject_id]} for subject_id in target}, "warnings": warnings}


def proposal_from_weights(weights, questionnaire, categories, season_focus=None, season_id=None, fallback_blocks=None):
    """The `proposal` a weights file carries: the generated grid, its reasons and warnings, the season it was
    generated for, the diff against the weights' own blockFocusGrid, and the activities proposed inside the grid."""
    generated = generate_block_focus_grid(weights, questionnaire, season_focus, fallback_blocks)
    activities = generate_activities(weights, generated["blockFocusGrid"], questionnaire, categories, fallback_blocks)
    return {
        "blockFocusGrid": generated["blockFocusGrid"],
        "seasonId": season_id,
        "reasons": generated["reasons"],
        "warnings": generated["warnings"] + activities["warnings"],
        "diff": diff_block_focus_grid(weights.get("blockFocusGrid"), generated["blockFocusGrid"]),
        "activities": activities["activities"],
        "placedMinutes": activities["placedMinutes"],
    }
