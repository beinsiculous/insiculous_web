"""Build a web keep from a Champion's keep through the writer, and check it against the canonical schema.

The writer is JavaScript — src/lib/champion/keep-writer.js, driven raw by node the way the tests drive
every module under src/lib/. This is the one Python module in fk_core that needs node, and the one
place a clock is read for an export: `exported_at` is an argument, so the writer stays pure.

The Champion's keep is a real household's schedule and never lives in this repository; callers pass
one in from outside the checkout (scripts/export_keep.py, and the working set's
scripts/lib/check_keep_output.py, which runs this over the private keep).
"""
import json
import shutil
import subprocess
from pathlib import Path

from fk_core.validate import ValidationReport, check_schema

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRITER_MODULE = REPOSITORY_ROOT / "src" / "lib" / "champion" / "keep-writer.js"
CANONICAL_SCHEMA = REPOSITORY_ROOT / "data" / "schema" / "keep.schema.json"
NODE_TIMEOUT_SECONDS = 300

BUILD_SCRIPT = (
    f'import {{ buildKeep }} from {json.dumps(WRITER_MODULE.as_uri())};'
    'let inputText = "";'
    'process.stdin.setEncoding("utf8");'
    "for await (const chunk of process.stdin) inputText += chunk;"
    "const inputs = JSON.parse(inputText);"
    "process.stdout.write(JSON.stringify(buildKeep(inputs.champion, inputs.date, inputs.exportedAt)));"
)


class WriterUnavailable(RuntimeError):
    """node is not on PATH, or the writer failed — the message says which, and what to do."""


def build_web_keep(champion_keep, iso_date, exported_at):
    """The web keep the writer builds for `iso_date`, stamped `exported_at` (a UTC ISO string or None)."""
    if shutil.which("node") is None:
        raise WriterUnavailable("node is not on PATH: the keep writer is JavaScript (src/lib/champion/keep-writer.js) "
                                "and needs node to run — install it, or load the version .nvmrc names, and try again")
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", BUILD_SCRIPT],
            input=json.dumps({"champion": champion_keep, "date": iso_date, "exportedAt": exported_at}),
            capture_output=True, text=True, timeout=NODE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise WriterUnavailable(f"the keep writer did not answer within {NODE_TIMEOUT_SECONDS}s for {iso_date}; "
                                "nothing was written") from error
    if result.returncode != 0:
        raise WriterUnavailable(f"the keep writer failed for {iso_date}:\n{result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except ValueError as error:
        raise WriterUnavailable(f"the keep writer produced something that is not JSON for {iso_date}: {error}") from error


def check_web_keep(web_keep):
    """Validate a built keep against the canonical schema. Returns the report; `report.ok` is the verdict."""
    schema = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
    report = ValidationReport()
    check_schema(web_keep, schema, "keep", report)
    return report
