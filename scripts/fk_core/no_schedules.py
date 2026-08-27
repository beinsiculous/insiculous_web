"""Refuse to let a person's schedule into this repository.

This repository is public and holds nobody's schedule (CLAUDE.md, README.md, docs/thesis.md). Until now
that was a sentence; this makes it a check. What it guards against is one tired commit — dropping a
`myfort` seed into `public/` to try it on the TV, or a `keep_seed.json` next to the scripts that read it.
Either one deploys a household's fortnight to a public website, and git history makes it painful to undo.

The shapes it knows, and why they are that specific:

  * `meta.format == "myfort"` — a My Fort seed, exported by the Focus Key app. It says what it is.
  * `meta`, `calendar`, `days` and `tasks` ALL present — a `keep_seed.json`.

A bare `tasks` or `days` key is NOT the test, and that is the whole subtlety. `data/questionnaire.json`
carries `tasks`, `data/days.json` and `examples/workbook/days.json` carry `days`, and
`build/fortknight.bundle.json` carries both `days` and `meta` — six committed files that a naive marker
would refuse, blocking every build from the day the guard landed. Requiring all four together separates a
seed from every legitimate file here; verified against every JSON in the repository, which trips none.

What this does NOT cover: `examples/workbook/` is workbook-derived reference data that would not match
these shapes, and whether it belongs in a public repository is an older question this guard does not
settle. It is about seed files.
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

#: The one fabricated fixture allowed to look like a seed: scripts/a11y-check.mjs loads it into the browser
#: so axe audits a My Fort page with fourteen real panels rather than an empty file picker — the page's one
#: hard requirement is being legible, and a gate that only ever sees the empty state checks nothing.
#:
#: An earlier version listed this path BEFORE the fixture existed, which was a pre-approved hole at exactly
#: the path and name a real export would be given by someone trying the import flow. It is here now because
#: the file is here and something reads it, and tests assert both: that it is the only exemption, and that
#: the file it names is invented rather than anybody's.
ALLOWED_FIXTURES = {"tests/fixtures/myfort.sample.json"}


def describe_schedule_document(parsed):
    """Why this parsed JSON looks like somebody's schedule, or None when it does not."""
    if not isinstance(parsed, dict):
        return None
    meta = parsed.get("meta")
    if isinstance(meta, dict) and meta.get("format") == "myfort":
        return "a My Fort seed (meta.format is \"myfort\")"
    if {"meta", "calendar", "days", "tasks"} <= set(parsed):
        return "a Focus Key seed (meta, calendar, days and tasks together)"
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
            # utf-8-sig, because a seed saved by Notepad carries a BOM and json.loads refuses it outright.
            parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError, OSError) as error:
            if path.name in JSONC_CONFIG_NAMES:
                continue
            # NOT skipped in silence. A file this cannot read is a file it cannot clear, and the whole
            # value of the guard is never being quietly wrong: a UTF-16 seed dropped in public/ would
            # otherwise be reported as a clean repository. Only data/ has a validator that would complain
            # about it separately; nothing speaks for the rest of the checkout.
            found.append((relative.as_posix(), f"unreadable JSON ({type(error).__name__}), so it cannot be "
                                               "shown not to be a schedule"))
            continue
        reason = describe_schedule_document(parsed)
        if reason:
            found.append((relative.as_posix(), reason))
    return sorted(found)
