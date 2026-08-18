#!/usr/bin/env python3
"""Compute time groupings per category for the fortnight and (optionally) the baseline weights.

    python scripts/analyze_allocations.py                       # print a summary
    python scripts/analyze_allocations.py --json                # print full allocations JSON
    python scripts/analyze_allocations.py --overlay examples/workbook --weights-out examples/workbook/weights.baseline.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core import keys  # noqa: E402
from fk_core.allocations import compute_allocations, weights_from_allocations  # noqa: E402
from fk_core.json_io import DATA_DIRECTORY, load_data_directory, write_json  # noqa: E402


def render_summary(allocations):
    lines = [f"focus window {allocations['focusWindow']['start']}-{allocations['focusWindow']['end']}: "
             f"{allocations['focusWindow']['minutesPerCycle']} minutes per fortnight", ""]
    for view_name in ("byBlockFocus", "byActivities"):
        view = allocations[view_name]
        lines.append(f"{view_name}: {view['method']}")
        for category, minutes in view["byCategory"].items():
            share = view["shareByCategory"][category]
            label = keys.CATEGORY_LABELS.get(category, category.capitalize())
            lines.append(f"  {label:<28} {minutes:>6} min  {share:>6.1%}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over --data (e.g. examples/workbook)")
    parser.add_argument("--json", action="store_true", help="print the full allocations object as JSON")
    parser.add_argument("--weights-out", help="write baseline weights (questionnaire contract) to this path")
    arguments = parser.parse_args(argv)

    data = load_data_directory(arguments.data, arguments.overlay)
    allocations = compute_allocations(data)
    if arguments.json:
        print(json.dumps(allocations, indent=2))
    else:
        print(render_summary(allocations))
    if arguments.weights_out:
        write_json(arguments.weights_out, weights_from_allocations(allocations, data["days"]))
        print(f"wrote: {arguments.weights_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
