#!/usr/bin/env python3
"""Validate data/, derive views, and write build/ (bundle + derived files).

    python scripts/build.py                                                   # the neutral canonical set
    python scripts/build.py --overlay examples/workbook --out build/examples/workbook   # the workbook sample
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core.allocations import compute_allocations  # noqa: E402
from fk_core.derive import default_import_document, menu_by_day, plan_by_day  # noqa: E402
from fk_core.json_io import BUILD_DIRECTORY, DATA_DIRECTORY, DERIVED_DIRECTORY, load_data_directory, write_json  # noqa: E402
from fk_core.validate import ValidationReport, check_import_document, validate_data  # noqa: E402


def strip_schema_pointers(value):
    """Drop "$schema" keys so the bundle is self-contained."""
    if isinstance(value, dict):
        return {key: strip_schema_pointers(item) for key, item in value.items() if key != "$schema"}
    if isinstance(value, list):
        return [strip_schema_pointers(item) for item in value]
    return value


def active_menu_for(data):
    """The menu the derived views use: meta.activeMenuId when it names a loaded menu, else the first menu, else None."""
    if not data["menus"]:
        return None
    return data["menus"].get(data["meta"].get("activeMenuId")) or next(iter(data["menus"].values()))


def build_bundle(data):
    active_menu = active_menu_for(data)
    derived = {
        "menuByDay": menu_by_day(active_menu) if active_menu else {},
        "planByDay": plan_by_day(data, active_menu),
        "allocations": compute_allocations(data),
        "defaultImport": default_import_document(data),
    }
    canonical = {name: strip_schema_pointers(data[name]) for name in ("meta", "seasons", "days", "blocks", "categories", "activities")}
    canonical["menus"] = strip_schema_pointers(data["menus"])
    canonical["weights"] = strip_schema_pointers(data["weights"]) if data.get("weights") else None
    canonical["questionnaire"] = strip_schema_pointers(data["questionnaire"]) if data.get("questionnaire") else None
    content_hash = hashlib.sha256(json.dumps({**canonical, "derived": derived}, sort_keys=True).encode()).hexdigest()[:16]
    built_from = ["meta.json", "seasons.json", "days.json", "blocks.json", "categories.json", "activities.json", "menus/*.json", "questionnaire.json"] + (["weights.baseline.json"] if data.get("weights") else [])
    bundle = {
        "buildInfo": {
            "buildHash": content_hash,
            "schemaVersion": data["meta"]["schemaVersion"],
            "builtFrom": built_from,
        },
        **canonical,
        "derived": derived,
    }
    return bundle, derived


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over --data (e.g. examples/workbook); pair it with --out")
    parser.add_argument("--out", default=str(BUILD_DIRECTORY))
    arguments = parser.parse_args(argv)

    data = load_data_directory(arguments.data, arguments.overlay)
    report = validate_data(data)
    print(report.render())
    if not report.ok:
        return 1
    bundle, derived = build_bundle(data)
    import_report = check_import_document(derived["defaultImport"], set(data["categories"]["order"]), ValidationReport(), data["categories"])
    if not import_report.ok:
        print(import_report.render())
        return 1
    output_directory = Path(arguments.out)
    write_json(output_directory / "fortknight.bundle.json", bundle)
    derived_directory = output_directory / "derived"
    for stale in derived_directory.glob("*.json") if derived_directory.exists() else []:
        if stale.stem not in derived:
            stale.unlink()  # a renamed/removed derived view must not linger as an authoritative-looking file
    for name, value in derived.items():
        write_json(derived_directory / f"{name}.json", value)
    print(f"built {output_directory / 'fortknight.bundle.json'} (hash {bundle['buildInfo']['buildHash']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
