#!/usr/bin/env python3
"""Propose a block focus grid for a weights file (the generator, roadmap 2; docs/generator.md).

    python scripts/generate_grid.py examples/workbook/weights.baseline.json --overlay examples/workbook
    python scripts/generate_grid.py build/weights.username.json --date 2026-10-14   # the season of that date
    python scripts/generate_grid.py answers-derived.json --answers answers.json          # season by that person's year split

Prints the proposal (grid, per-cell reasons, warnings, the season it was made for, and the diff against the
file's own blockFocusGrid) as JSON; --table prints the grid as text instead. The rule lives in
fk_core/generator.py (mirrored by src/lib/shared/generator-rules.js); this script only orchestrates.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core import keys  # noqa: E402
from fk_core.dates import parse_iso_date, season_for_date_person_first  # noqa: E402
from fk_core.generator import proposal_from_weights  # noqa: E402
from fk_core.json_io import DATA_DIRECTORY, dumps_json, load_data_directory, read_json  # noqa: E402
from fk_core.weights import seasons_for_answers  # noqa: E402


def render_table(proposal, weights, blocks):
    focus_block_keys = [block["key"] for block in weights.get("blocks", []) if block.get("carriesFocus")] or [key for key in blocks["order"] if blocks["blocks"][key]["carriesFocus"]]
    width = max(len(focus) for focus in keys.CATEGORY_KEY_ORDER + [keys.FLEXIBLE_FOCUS]) + 1
    lines = [f"season: {proposal['seasonId']}", "day    " + " ".join(key.ljust(width) for key in focus_block_keys)]
    for day_key in keys.DAY_KEY_ORDER:
        cells = proposal["blockFocusGrid"].get(day_key, {})
        before = (weights.get("blockFocusGrid") or {}).get(day_key, {})
        lines.append(day_key.ljust(7) + " ".join((cells.get(key, "—") + ("*" if before.get(key) not in (None, cells.get(key)) else "")).ljust(width) for key in focus_block_keys))
    counts = proposal["diff"]["counts"]
    lines.append(f"* differs from the file's grid — {counts['changed']} changed, {counts['added']} added, {counts['removed']} removed, {counts['same']} same")
    lines += [f"warning: {warning}" for warning in proposal["warnings"]]
    if proposal["activities"]:
        lines.append("")
        lines.append(f"proposed activities ({len(proposal['activities'])}):")
        for day_key in keys.DAY_KEY_ORDER:
            for block_key in focus_block_keys:
                cell = [activity for activity in proposal["activities"] if activity["dayKey"] == day_key and activity["block"] == block_key]
                if cell:
                    lines.append(f"  {day_key} {block_key}: " + "; ".join(f"{activity['title']} {activity['minutes']} min" + (f" @{activity['timing']['estimatedStart']}" if activity["timing"] else "") for activity in cell))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("weights", help="weights JSON file (weights.schema.json)")
    parser.add_argument("--date", default=date.today().isoformat(), help="ISO date whose season the proposal is made for (default today)")
    parser.add_argument("--answers", help="questionnaire answers file: the season by that person's own year split")
    parser.add_argument("--data", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over --data (e.g. examples/workbook)")
    parser.add_argument("--table", action="store_true", help="print the grid as text instead of JSON")
    arguments = parser.parse_args(argv)

    data = load_data_directory(arguments.data, arguments.overlay)
    weights = read_json(arguments.weights)
    answers = read_json(arguments.answers) if arguments.answers else (weights.get("questionnaire") or {}).get("answers")
    person_seasons = seasons_for_answers(answers, data["questionnaire"], data["categories"]) if answers else None
    season = season_for_date_person_first(parse_iso_date(arguments.date), person_seasons, data["seasons"]["seasons"])
    proposal = proposal_from_weights(weights, data["questionnaire"], data["categories"], season["focus"] if season else None, season["id"] if season else None, data["blocks"])
    if arguments.table:
        print(render_table(proposal, weights, data["blocks"]))
    else:
        sys.stdout.write(dumps_json(proposal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
