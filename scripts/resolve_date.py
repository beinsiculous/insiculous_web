#!/usr/bin/env python3
"""Resolve a calendar date to its fortnight day key, season, and (optionally) that day's plan.

    python scripts/resolve_date.py 2026-10-14 [--json] [--plan]
    python scripts/resolve_date.py 2026-10-14 --answers answers.json   # by that person's own seasons (year split + week start)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core.dates import cycle_index_for_date, day_key_for_date, day_key_for_date_in_season, parse_iso_date, season_anchor_date, season_for_date  # noqa: E402
from fk_core.derive import plan_by_day  # noqa: E402
from fk_core.json_io import DATA_DIRECTORY, load_data_directory, read_json  # noqa: E402
from fk_core.weights import seasons_for_answers  # noqa: E402


def resolve(data, date, epoch_override=None, seasons=None):
    """Default: season-anchored (each season restarts the cycle on its startDayKey) — by the person's own
    `seasons` when given and one of them has started by `date`, else by the workbook seasons.
    With epoch_override={"date","dayKey"} the cycle is anchored there instead (user setting)."""
    season_source = "workbook"
    season_list = data["seasons"]["seasons"]
    if seasons and season_for_date(seasons, date) is not None:
        season_source, season_list = "person", seasons
    if epoch_override:
        anchor_date, anchor_day_key = parse_iso_date(epoch_override["date"]), epoch_override["dayKey"]
        season_start, season = season_for_date(season_list, date)
        day_key = day_key_for_date(date, anchor_date, anchor_day_key)
        anchor = "epoch-override"
    else:
        day_key, season_start, season = day_key_for_date_in_season(date, season_list)
        anchor_date, anchor_day_key = season_anchor_date(season_start, season["startDayKey"]), season["startDayKey"]
        anchor = "season-start"
    return {
        "date": date.isoformat(),
        "weekday": date.strftime("%A"),
        "dayKey": day_key,
        "dayLabel": data["days"]["days"][day_key]["label"],
        "cycleIndex": cycle_index_for_date(date, anchor_date, anchor_day_key),
        "anchor": anchor,
        "seasonSource": season_source,
        "week": data["days"]["days"][day_key]["week"],
        "season": {"id": season["id"], "name": season["name"], "startDate": season_start.isoformat(),
                   "seasonMode": season["seasonMode"], "focus": season["focus"]},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("date", help="YYYY-MM-DD")
    parser.add_argument("--data", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over --data (e.g. examples/workbook)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--plan", action="store_true", help="include that day's full plan")
    parser.add_argument("--answers", help="questionnaire answers file: resolve by that person's own seasons")
    arguments = parser.parse_args(argv)

    data = load_data_directory(arguments.data, arguments.overlay)
    seasons = seasons_for_answers(read_json(arguments.answers), data["questionnaire"], data["categories"]) if arguments.answers else None
    result = resolve(data, parse_iso_date(arguments.date), seasons=seasons)
    if arguments.plan:
        menu = data["menus"].get(result["season"]["id"]) or next(iter(data["menus"].values()), None)  # None: no menus in this data set
        result["plan"] = plan_by_day(data, menu)[result["dayKey"]]
    if arguments.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['date']} ({result['weekday']}) -> {result['dayLabel']} [{result['dayKey']}], "
              f"cycle index {result['cycleIndex']}, week {result['week']}, "
              f"season {result['season']['name']} (since {result['season']['startDate']}, {result['season']['seasonMode']}, {result['seasonSource']} seasons)")
        if arguments.plan:
            for block in result["plan"]["blocks"]:
                titles = ", ".join(activity["title"] for activity in block["activities"]) or "-"
                print(f"  {block['label']:<9} {block['start']}-{block['end']} focus={block['focus'] or '-':<26} {titles}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
