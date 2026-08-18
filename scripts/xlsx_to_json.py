#!/usr/bin/env python3
"""Convert the FortKnight workbook into the JSON shape of the workbook example set (examples/workbook/).

    python scripts/xlsx_to_json.py --xlsx source/FortKnight.xlsx [--out examples/workbook/] [--dry-run]

Kept for reference: it produced the example set once. Never point --out at data/ — the canonical data
is person-neutral (CLAUDE.md "Source of truth"); a person's schedule enters the app as an import
document (docs/importers.md). Every record keeps its raw cell text ("raw") and spreadsheet row ("sourceRow").
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core import keys, timeconv  # noqa: E402
from fk_core.dates import start_date_for_rule  # noqa: E402
from fk_core.json_io import DATA_DIRECTORY, SOURCE_DIRECTORY, WORKBOOK_EXAMPLE_DIRECTORY, dumps_json, write_json  # noqa: E402
from fk_core.parse import parse_detail  # noqa: E402
from fk_core.xlsx import read_workbook, rows_as_records  # noqa: E402

SCHEMA_VERSION = 1
DEFAULT_TIMEZONE = "America/Phoenix"

# The workbook anchors 2026: Spooky Season starts Sunday 2026-09-06 on "Sunday A".
EPOCH_SEASON_ID = "spooky-season"
EPOCH_YEAR = 2026

# The sheet's "Season Start - Sunday" text -> computable start rule (fk_core/dates.py start_date_for_rule) + words.
SEASON_START_RULE_BY_TEXT = {
    "Daylight Savings Starts": ({"kind": "nth-weekday", "month": 3, "weekday": "sunday", "occurrence": 2, "offsetDays": 0, "snap": None},
                                "Second Sunday of March (US daylight saving time begins)"),
    "Easter": ({"kind": "easter", "offsetDays": 0, "snap": None}, "Easter Sunday (Gregorian computus)"),
    "Before Labor Day": ({"kind": "nth-weekday", "month": 9, "weekday": "monday", "occurrence": 1, "offsetDays": 0,
                          "snap": {"weekday": "sunday", "direction": "on-or-before"}},
                         "Sunday before Labor Day (first Monday of September)"),
    "Daylight Savings Ends": ({"kind": "nth-weekday", "month": 11, "weekday": "sunday", "occurrence": 1, "offsetDays": 0, "snap": None},
                              "First Sunday of November (US daylight saving time ends)"),
    "After Christmas": ({"kind": "fixed-date", "month": 12, "day": 26, "offsetDays": 0,
                         "snap": {"weekday": "sunday", "direction": "on-or-after"}},
                        "First Sunday after Christmas Day"),
}
# Norse-wheel outside/inside seasons, flipped for Arizona (Fimbulsumar is the harsh indoor season).
SEASON_MODE_BY_ID = {
    "ostara": "outdoor",
    "fimbulsumar": "indoor",
    "spooky-season": "mixed",
    "christmas": "outdoor",
    "hogmanay": "outdoor",
}
APPOINTMENT_BLOCK_BY_WEEK = {1: "midday", 2: "early"}
FLEXIBILITY_VALUES = {"no": "no", "some": "some", "yes": "yes"}


def text(cell):
    return cell.as_text().strip() if cell is not None else ""


def number(cell):
    return cell.as_float() if cell is not None and cell.kind == "number" else None


def parse_duration_weeks(duration_text):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*weeks?\s*$", duration_text)
    return {"min": int(match.group(1)), "max": int(match.group(2))} if match else None


def season_start_rule(rule_text):
    """Match the sheet's start-rule text case/whitespace-insensitively; fail with the allowed values."""
    normalized = " ".join(rule_text.split()).lower()
    for known_text, rule in SEASON_START_RULE_BY_TEXT.items():
        if " ".join(known_text.split()).lower() == normalized:
            return rule
    allowed = ", ".join(repr(known) for known in SEASON_START_RULE_BY_TEXT)
    raise ValueError(f"unknown season start rule {rule_text!r}; expected one of: {allowed}")


def convert_meta():
    return {
        "$schema": "./schema/meta.schema.json",
        "schemaVersion": SCHEMA_VERSION,
        "cycleLengthDays": len(keys.DAY_KEY_ORDER),
        "epoch": {
            "date": start_date_for_rule(SEASON_START_RULE_BY_TEXT["Before Labor Day"][0], EPOCH_YEAR).isoformat(),
            "dayKey": "sun-a",
            "note": "Fallback anchor only. Default resolution is season-anchored: each season restarts the "
                    "fortnight on its startDayKey (seasons.json). This epoch is Spooky Season 2026 = Sunday A.",
        },
        "timezone": DEFAULT_TIMEZONE,
    }


def convert_seasons(records):
    seasons = []
    for record in records:
        name = text(record["Season"])
        season_id = keys.slugify(name)
        start_rule, rule_description = season_start_rule(text(record["Season Start - Sunday"]))
        seasons.append({
            "id": season_id,
            "name": name,
            "gregorianRange": text(record["Georgian Equivalent"]),
            "durationWeeks": parse_duration_weeks(text(record["Duration"])),
            "startRule": start_rule,
            "startDescription": rule_description,
            "startDayKey": keys.day_key_from_label(text(record["2026 Start Day"])),
            "seasonMode": SEASON_MODE_BY_ID[season_id],
            "outdoorWindow": {"uvAbove4": None},
            "focus": [
                keys.category_key_from_label(text(record[column]))[0]
                for column in ("Main Focus", "Secondary Focus", "Tertiary Focus", "Quaternary Focus")
            ],
            "menuId": season_id if season_id == EPOCH_SEASON_ID else None,
            "knownStarts": {str(EPOCH_YEAR): start_date_for_rule(start_rule, EPOCH_YEAR).isoformat()},
            "raw": {header: text(cell) for header, cell in record.items() if header != "_row_number"},
            "sourceRow": record["_row_number"],
        })
    return {"$schema": "./schema/seasons.schema.json", "seasons": seasons}


def convert_days(records):
    days = {}
    for record in records:
        label = text(record["Day Key"])
        day_key = keys.day_key_from_label(label)
        index = keys.DAY_KEY_INDEX[day_key]
        weekday, variant = label.split()
        week = 1 if index < 7 else 2
        days[day_key] = {
            "index": index,
            "week": week,
            "weekday": weekday.lower(),
            "variant": variant,
            "label": label,
            "shortKey": keys.short_key_from_day_key(day_key),
            "mainFocus": keys.focus_key_from_label(text(record["Main Focus"])),
            "mainFocusLabel": text(record["Main Focus"]),
            "blockFocus": {
                "early": keys.focus_key_from_label(text(record["Early Block's Focus"])),
                "midday": keys.focus_key_from_label(text(record["Midday Block's Focus"])),
                "late": keys.focus_key_from_label(text(record["Late Block's Focus"])),
            },
            "blockFocusLabels": {
                "early": text(record["Early Block's Focus"]),
                "midday": text(record["Midday Block's Focus"]),
                "late": text(record["Late Block's Focus"]),
            },
            "appointmentBlock": APPOINTMENT_BLOCK_BY_WEEK[week],
            "sourceRow": record["_row_number"],
        }
    ordered_days = {day_key: days[day_key] for day_key in keys.DAY_KEY_ORDER}
    return {"$schema": "./schema/days.schema.json", "order": list(keys.DAY_KEY_ORDER), "days": ordered_days}


def convert_blocks(records):
    blocks = {}
    for record in records:
        label = text(record["Block Description"])
        block_key = keys.slugify(label)
        start_cell, end_cell = record["Start"], record["End"]
        start = "00:00" if text(start_cell) == "MIDNIGHT" else timeconv.fraction_to_time_string(number(start_cell))
        end = "24:00" if text(end_cell) == "MIDNIGHT" else timeconv.fraction_to_time_string(number(end_cell))
        blocks[block_key] = {
            "label": label,
            "start": start,
            "end": end,
            "durationMinutes": timeconv.duration_minutes(start, end),
            "mealPrimary": keys.MEAL_HINT_KEYS[text(record["Meal Primary"])],
            "mealSecondary": keys.MEAL_HINT_KEYS[text(record["Meal Secondary"])],
            "carriesFocus": block_key in keys.FOCUS_BLOCK_KEYS,
            "sourceRow": record["_row_number"],
        }
    ordered = {block_key: blocks[block_key] for block_key in keys.BLOCK_KEY_ORDER}
    return {"$schema": "./schema/blocks.schema.json", "order": list(keys.BLOCK_KEY_ORDER), "blocks": ordered}


def convert_categories(records):
    categories = {
        key: {"label": keys.CATEGORY_LABELS[key], "subjects": []} for key in keys.CATEGORY_KEY_ORDER
    }
    subjects = {}
    for record in records:
        subject_label = text(record["Subjects"])
        subject_key = keys.slugify(subject_label)
        category_key = keys.category_key_from_label(text(record["Category"]))[0]
        subjects[subject_key] = {"label": subject_label, "category": category_key, "sourceRow": record["_row_number"]}
        categories[category_key]["subjects"].append(subject_key)
    return {
        "$schema": "./schema/categories.schema.json",
        "order": list(keys.CATEGORY_KEY_ORDER),
        "categories": categories,
        "flexibleFocus": {
            "key": keys.FLEXIBLE_FOCUS,
            "label": "Flexible",
            "note": "Pseudo-focus used by days/blocks that are intentionally unassigned; not a category.",
        },
        "subjects": subjects,
    }


def convert_timing(record):
    estimated_start_cell = record["Estimated Start"]
    if estimated_start_cell is None or estimated_start_cell.kind != "number":
        return None
    estimated_end_cell = record["Estimated End"]
    return {
        "estimatedStart": timeconv.fraction_to_time_string(number(estimated_start_cell)),
        "travelPrepComplete": timeconv.fraction_to_time_string(number(record["Travel/Prep Complete"])),
        "timeStart": timeconv.fraction_to_time_string(number(record["Time Start"])),
        "timeFinished": timeconv.fraction_to_time_string(number(record["Time Finished"])),
        "estimatedEnd": timeconv.fraction_to_time_string(number(estimated_end_cell)),
        "estimatedEndSource": "formula" if estimated_end_cell.formula else "literal",
        "durationMinutes": timeconv.fraction_to_minutes(number(record["Time Finished"]))
        - timeconv.fraction_to_minutes(number(record["Time Start"])),
        "prepMinutes": timeconv.fraction_to_minutes(number(record["Travel/Prep Complete"]))
        - timeconv.fraction_to_minutes(number(estimated_start_cell)),
    }


def convert_activities(records):
    activities = []
    identifier_counts = {}
    for record in records:
        title = text(record["Description"])
        day_key = keys.day_key_from_label(text(record["Day Key"]))
        block = keys.slugify(text(record["Block"]))
        base_identifier = f"{keys.slugify(title)}--{day_key}--{block}"
        identifier_counts[base_identifier] = identifier_counts.get(base_identifier, 0) + 1
        occurrence = identifier_counts[base_identifier]
        identifier = base_identifier if occurrence == 1 else f"{base_identifier}--{occurrence}"
        flexibility_text = text(record["Flexibility"]).lower()
        activities.append({
            "id": identifier,
            "title": title,
            "dayKey": day_key,
            "block": block,
            "priority": int(number(record["Priority"])),
            "categories": keys.category_key_from_label(text(record["Category"])),
            "flexibility": FLEXIBILITY_VALUES.get(flexibility_text),
            "timing": convert_timing(record),
            "detail": parse_detail(text(record["Link/Tasks"])),
            "raw": {header: text(cell) for header, cell in record.items() if header != "_row_number"},
            "sourceRow": record["_row_number"],
        })
    activities.sort(key=lambda activity: (keys.DAY_KEY_INDEX[activity["dayKey"]],
                                          keys.BLOCK_KEY_ORDER.index(activity["block"]),
                                          activity["priority"], activity["sourceRow"]))
    return {"$schema": "./schema/activities.schema.json", "activities": activities}


def convert_menu(rows, season_id):
    notes = [text(cell) for cell in rows[0] if cell is not None and text(cell)]
    records = rows_as_records(rows, header_row_index=1)
    meals = []
    for record in records:
        slot = text(record["Meal"]).lower()
        meal_number = int(number(record["#"]))
        meal_key = keys.normalize_meal_key(text(record["Meal Key"]))
        menu_text = text(record["Menu"])
        meals.append({
            "id": f"{slot}-{meal_number}",
            "slot": slot,
            "number": meal_number,
            "mealKey": meal_key,
            "days": keys.meal_key_days(meal_key),
            "menu": menu_text.lstrip("*").strip(),
            "cookExtra": menu_text.startswith("*"),
            "raw": {"mealKey": record["Meal Key"].as_text(), "menu": record["Menu"].as_text()},
            "sourceRow": record["_row_number"],
        })
    return {"$schema": "../schema/menu.schema.json", "id": season_id, "seasonId": season_id, "notes": notes, "meals": meals}


def convert_workbook(workbook):
    return {
        "meta.json": convert_meta(),
        "seasons.json": convert_seasons(rows_as_records(workbook["Seasons"])),
        "days.json": convert_days(rows_as_records(workbook["Days"])),
        "blocks.json": convert_blocks(rows_as_records(workbook["Blocks"])),
        "categories.json": convert_categories(rows_as_records(workbook["Subjects"])),
        "activities.json": convert_activities(rows_as_records(workbook["Schedule"])),
        "menus/spooky-season.json": convert_menu(workbook["Spooky Season"], "spooky-season"),
    }


def summarize(outputs):
    return (
        f"seasons={len(outputs['seasons.json']['seasons'])} "
        f"days={len(outputs['days.json']['days'])} "
        f"blocks={len(outputs['blocks.json']['blocks'])} "
        f"activities={len(outputs['activities.json']['activities'])} "
        f"meals={len(outputs['menus/spooky-season.json']['meals'])} "
        f"subjects={len(outputs['categories.json']['subjects'])}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xlsx", default=str(SOURCE_DIRECTORY / "FortKnight.xlsx"))
    parser.add_argument("--out", default=str(WORKBOOK_EXAMPLE_DIRECTORY), help="where the converted files go (default: the workbook example set, never data/)")
    parser.add_argument("--dry-run", action="store_true", help="convert and report, write nothing")
    arguments = parser.parse_args(argv)
    if Path(arguments.out).resolve() == DATA_DIRECTORY.resolve():
        parser.error("refusing to write into data/ — the canonical data is person-neutral; convert into examples/<name>/ instead")

    outputs = convert_workbook(read_workbook(arguments.xlsx))
    print(summarize(outputs))
    for relative_path, value in outputs.items():
        target = Path(arguments.out) / relative_path
        if arguments.dry_run:
            existing = target.read_text(encoding="utf-8") if target.exists() else None
            status = "unchanged" if existing == dumps_json(value) else ("would write" if existing is None else "would change")
            print(f"  {status}: {target}")
        else:
            write_json(target, value)
            print(f"  wrote: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
