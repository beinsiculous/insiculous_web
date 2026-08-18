#!/usr/bin/env python3
"""Turn a questionnaire answers file into a weights file (the questionnaire contract).

    python scripts/questionnaire_to_weights.py answers.json --id username            # print
    python scripts/questionnaire_to_weights.py answers.json --id username --out data/weights.username.json
    python scripts/questionnaire_to_weights.py --defaults --id defaults               # answers = slider defaults

The answers shape is documented in docs/questionnaire.md; the rule lives in fk_core/weights.py.
The output is validated against weights.schema.json before it is written.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core import keys  # noqa: E402
from fk_core.dates import day_key_for_date_person_first, parse_iso_date, season_for_date_person_first  # noqa: E402
from fk_core.json_io import DATA_DIRECTORY, dumps_json, load_data_directory, read_json, write_json  # noqa: E402
from fk_core.validate import ValidationReport, check_against_schema_file, check_weights_references  # noqa: E402
from fk_core.weights import default_answers, seasons_for_answers, weights_from_answers  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("answers", nargs="?", help="answers JSON file (omit with --defaults)")
    parser.add_argument("--defaults", action="store_true", help="use the questionnaire's default answers")
    parser.add_argument("--id", required=True, help="weights id (lowercase kebab-case)")
    parser.add_argument("--answered-at", default=date.today().isoformat(), help="ISO date recorded in the output")
    parser.add_argument("--date", default=date.today().isoformat(), help="ISO date whose season the grid proposal is made for (default today)")
    parser.add_argument("--data", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over --data (e.g. examples/workbook)")
    parser.add_argument("--out", help="write here instead of printing")
    arguments = parser.parse_args(argv)
    if bool(arguments.answers) == arguments.defaults:
        parser.error("give an answers file or --defaults (not both)")

    data = load_data_directory(arguments.data, arguments.overlay)
    if data["questionnaire"] is None:
        print("data/questionnaire.json is missing", file=sys.stderr)
        return 1
    answers = default_answers(data["questionnaire"], data["categories"]) if arguments.defaults else read_json(arguments.answers)
    person_seasons = seasons_for_answers(answers, data["questionnaire"], data["categories"])
    season = season_for_date_person_first(parse_iso_date(arguments.date), person_seasons, data["seasons"]["seasons"])
    weights = weights_from_answers(
        answers, data["categories"], data["questionnaire"],
        weights_id=arguments.id, answered_at=arguments.answered_at,
        days=data["days"],  # anchors come from the answers (applied import + standing appointments), not the workbook
        resolve_day_key=lambda iso_date: day_key_for_date_person_first(parse_iso_date(iso_date), person_seasons, data["seasons"]["seasons"]),
        season_focus=season["focus"] if season else None, season_id=season["id"] if season else None,
    )
    report = ValidationReport()
    check_against_schema_file(weights, "weights", report)
    if report.ok:
        check_weights_references(weights, set(keys.CATEGORY_KEY_ORDER), set(data["categories"]["subjects"]), data["questionnaire"], report)
    if report.errors or report.warnings:
        print(report.render(), file=sys.stderr)
    if not report.ok:
        return 1
    if arguments.out:
        write_json(arguments.out, weights)
        print(f"wrote: {arguments.out}")
    else:
        sys.stdout.write(dumps_json(weights))
    return 0


if __name__ == "__main__":
    sys.exit(main())
