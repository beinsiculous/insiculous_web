#!/usr/bin/env python3
"""Validate the canonical JSON in data/ (schemas + referential rules). Exit 1 on errors.

    python scripts/validate.py [data-directory] [--overlay examples/workbook]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core.json_io import DATA_DIRECTORY, load_data_directory  # noqa: E402
from fk_core.validate import validate_data  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data_directory", nargs="?", default=str(DATA_DIRECTORY))
    parser.add_argument("--overlay", help="sample data set laid over the data directory (e.g. examples/workbook)")
    arguments = parser.parse_args(argv)
    report = validate_data(load_data_directory(arguments.data_directory, arguments.overlay))
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
