"""Refuse to let a person's schedule into this repository.

This repository is public and holds nobody's schedule (CLAUDE.md, README.md, docs/thesis.md). Until now
that was a sentence; this makes it a check. What it guards against is one tired commit — dropping a
keep into `public/` to try it on the TV, or a `champion_keep.json` next to the scripts that read it.
Either one deploys a household's fortnight to a public website, and git history makes it painful to undo.

The shapes it knows, and why they are that specific:

  * `meta.format == "keep"` — a keep, exported by the phone app. It says what it is.
  * `meta.format == "myfort"` — a keep under the format's pre-2026-08-28 name. The validator stopped
    reading this string when the format was renamed, but this guard never does: old exports exist on
    the household's devices, and the keep deliberately omits `calendar` and `tasks`, so the shape
    below cannot catch one. The one place "myfort" stays alive, on purpose.
  * `meta`, `calendar`, `days` and `tasks` ALL present — a `champion_keep.json`.

A bare `tasks` or `days` key is NOT the test, and that is the whole subtlety. `data/questionnaire.json`
carries `tasks`, and `data/days.json` and `examples/workbook/days.json` carry `days` — committed files
that a naive marker would refuse, blocking every build from the day the guard landed. (The built bundle
carried both `days` and `meta` and was another; it was removed on 2026-08-30 with the creation chain.)
Requiring all four together separates a keep from every legitimate file here; verified against every JSON
in the repository, which trips none.

What this does NOT cover: `examples/workbook/` is workbook-derived reference data that would not match
these shapes, and whether it belongs in a public repository is an older question this guard does not
settle. It is about keeps.
"""
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: Never walked: generated, vendored, or not ours.
SKIPPED_DIRECTORIES = {".git", ".astro", "node_modules", "dist", "__pycache__", "source"}

#: Config files that are JSONC — JSON with comments — and so never parse as JSON. `tsconfig.json` is one
#: and has been since before this guard existed. They are exempt from the unreadable-file report below, and
#: ONLY from that: a file with one of these names that does parse is still checked like anything else.
#: This is a statement about tooling formats, not a permission for anything to hide in them.
JSONC_CONFIG_NAMES = {"tsconfig.json", "jsconfig.json"}

#: The fabricated fixtures allowed to look like a keep. `keep.sample.json` is loaded into the browser by
#: scripts/a11y-check.mjs so axe audits the Keep page with fourteen real panels rather than an empty file
#: picker — the page's one hard requirement is being legible, and a gate that only ever sees the empty state
#: checks nothing. `keep.other-household.json` is a second invented household, read by the rendering tests
#: and by that same gate's second pass over the keep-fed pages: the year wheel's colours are assigned
#: positionally, and proving that takes a keep whose season ids are NOT the ones the original palette was
#: keyed to — the a11y pass is what certifies the palette's contrast on such a keep.
#:
#: An earlier version listed the sample's path BEFORE the fixture existed, which was a pre-approved hole at
#: exactly the path and name a real export would be given by someone trying the import flow. Each entry is
#: here now because the file is here and something reads it, and tests assert both: that the exemptions are
#: exactly these paths, and that every file they name is invented rather than anybody's.
ALLOWED_FIXTURES = {"tests/fixtures/keep.sample.json", "tests/fixtures/keep.other-household.json"}


def describe_schedule_document(parsed):
    """Why this parsed JSON looks like somebody's schedule, or None when it does not."""
    if not isinstance(parsed, dict):
        return None
    meta = parsed.get("meta")
    if isinstance(meta, dict) and meta.get("format") in ("keep", "myfort"):
        return f"a keep (meta.format is \"{meta.get('format')}\")"
    if {"meta", "calendar", "days", "tasks"} <= set(parsed):
        return "a Fort Knight champion keep (meta, calendar, days and tasks together)"
    return None


def find_schedule_documents(root=REPOSITORY_ROOT):
    """Every JSON file under `root` that looks like a person's schedule, as [(relative path, reason)].

    Sorted, so the report is the same on every machine.
    """
    root = Path(root)
    found = []
    # Case-insensitive: rglob("*.json") never sees SEED.JSON on a case-sensitive filesystem, and a guard
    # against one tired commit should not depend on the commit being tidy.
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        relative = path.relative_to(root)
        if SKIPPED_DIRECTORIES & set(relative.parts):
            continue
        if relative.as_posix() in ALLOWED_FIXTURES:
            continue
        try:
            # utf-8-sig, because a keep saved by Notepad carries a BOM and json.loads refuses it outright.
            parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError, OSError) as error:
            if path.name in JSONC_CONFIG_NAMES:
                continue
            # NOT skipped in silence. A file this cannot read is a file it cannot clear, and the whole
            # value of the guard is never being quietly wrong: a UTF-16 keep dropped in public/ would
            # otherwise be reported as a clean repository. Only data/ has a validator that would complain
            # about it separately; nothing speaks for the rest of the checkout.
            found.append((relative.as_posix(), f"unreadable JSON ({type(error).__name__}), so it cannot be "
                                               "shown not to be a schedule"))
            continue
        reason = describe_schedule_document(parsed)
        if reason:
            found.append((relative.as_posix(), reason))
    return sorted(found)
