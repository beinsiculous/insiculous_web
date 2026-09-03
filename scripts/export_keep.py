#!/usr/bin/env python3
"""Write the web keep — the file beinsiculous.com/fortknight/ draws — from a Champion's keep kept elsewhere.

    python3 scripts/export_keep.py --champion ../fortknight/keep/champion_keep.json --out ../fortknight/keep/m.keep.json
    python3 scripts/export_keep.py --champion ../fortknight/keep/champion_keep.json --date 2026-08-27 --check

A Champion's keep is a real household's schedule and this repository holds nobody's, so both paths are
refused if they resolve to anywhere inside the checkout — except source/, which is gitignored for exactly
this. The output is validated against data/schema/keep.schema.json before it is written, and written
whole (temp file, then rename), so a refused or failed run leaves nothing behind. Needs node: the writer
is src/lib/champion/keep-writer.js.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fk_core.web_keep import REPOSITORY_ROOT, WriterUnavailable, build_web_keep, check_web_keep  # noqa: E402

ALLOWED_INSIDE = REPOSITORY_ROOT / "source"
ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def inside_checkout(path):
    """True when a path resolves (symlinks included) to somewhere in this repository other than source/."""
    resolved = Path(path).resolve()
    return resolved.is_relative_to(REPOSITORY_ROOT.resolve()) and not resolved.is_relative_to(ALLOWED_INSIDE.resolve())


def write_whole(path, text):
    """Write the file in one move: a partial file is worse than no file, because a reader would trust it."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, target)
    finally:
        # A failed write must not leave a keep-shaped temp file behind — least of all inside a checkout.
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--champion", required=True, help="the Champion's keep to build from (outside this checkout)")
    parser.add_argument("--date", default=datetime.date.today().isoformat(),
                        help="the ISO date the season card and year wheel are snapshots of (default: today, local)")
    parser.add_argument("--exported-at", default=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                        help="the UTC stamp the file carries (default: now)")
    parser.add_argument("--out", help="where to write the keep (outside this checkout, or under source/)")
    parser.add_argument("--check", action="store_true", help="build and validate, write nothing")
    arguments = parser.parse_args(argv)

    if not arguments.check and not arguments.out:
        parser.error("say where the keep goes (--out PATH), or --check to validate without writing")
    if inside_checkout(arguments.champion):
        print(f"refused: {arguments.champion} is inside this repository, which holds nobody's schedule; "
              "keep the Champion's keep outside the checkout (or under source/, which is ignored)", file=sys.stderr)
        return 2
    if arguments.out and inside_checkout(arguments.out):
        print(f"refused: {arguments.out} is inside this repository; write the keep outside the checkout "
              "(or under source/, which is ignored). Nothing was written.", file=sys.stderr)
        return 2
    if arguments.out and Path(arguments.out).is_dir():
        print(f"refused: {arguments.out} is a directory; name the file to write. Nothing was written.", file=sys.stderr)
        return 2
    if not ISO_DATE.match(arguments.date):
        print(f"refused: --date must be YYYY-MM-DD, not {arguments.date!r}", file=sys.stderr)
        return 2

    champion_path = Path(arguments.champion)
    if not champion_path.is_file():
        print(f"no Champion's keep at {champion_path}", file=sys.stderr)
        return 2
    champion = json.loads(champion_path.read_text(encoding="utf-8"))
    try:
        web_keep = build_web_keep(champion, arguments.date, arguments.exported_at)
    except WriterUnavailable as error:
        print(str(error), file=sys.stderr)
        return 1
    report = check_web_keep(web_keep)
    if not report.ok:
        print(f"the keep built for {arguments.date} does not conform to data/schema/keep.schema.json; nothing written:",
              file=sys.stderr)
        print(report.render(), file=sys.stderr)
        return 1
    season = web_keep["season"]["key"] if web_keep.get("season") else None
    if season is None:
        calendar = champion.get("calendar") or []
        span = f"{calendar[0]['date']} to {calendar[-1]['date']}" if calendar else "an empty calendar"
        print(f"warning: {arguments.date} is outside the Champion's keep's calendar ({span}), so this keep "
              "carries no season card and no year wheel; the fourteen days are unaffected", file=sys.stderr)
    if arguments.check:
        print(f"ok: the keep for {arguments.date} conforms (season {season})")
        return 0
    write_whole(arguments.out, json.dumps(web_keep, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {arguments.out} — {len(web_keep['days'])} days, season {season}, exported {web_keep['meta']['exportedAt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
