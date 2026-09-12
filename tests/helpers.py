"""Shared test setup: make scripts/ importable, load the data sets once, drive the JavaScript modules through node."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from fk_core.json_io import WORKBOOK_EXAMPLE_DIRECTORY, load_data_directory  # noqa: E402

DATA = load_data_directory(REPOSITORY_ROOT / "data")  # the neutral canonical set: no activities, no menus, empty grid
WORKBOOK_DATA = load_data_directory(REPOSITORY_ROOT / "data", WORKBOOK_EXAMPLE_DIRECTORY)  # the workbook example laid over it

SHARED_DIRECTORY = REPOSITORY_ROOT / "src" / "lib" / "shared"
CHAMPION_DIRECTORY = REPOSITORY_ROOT / "src" / "lib" / "champion"  # the resolver and the web-keep writer

# ----- driving the canonical JavaScript modules (src/lib/shared/) through node -----

STDIN_PRELUDE = """
let inputText = "";
process.stdin.setEncoding("utf8");
for await (const chunk of process.stdin) inputText += chunk;
const inputs = JSON.parse(inputText);
"""


def module_import(name, *symbols):
    """An import line for symbols of a src/lib/shared module."""
    return f"import {{ {', '.join(symbols)} }} from {json.dumps((SHARED_DIRECTORY / name).as_uri())};"


def champion_import(name, *symbols):
    """An import line for symbols of a src/lib/champion module — the code whose input is a Champion's keep."""
    return f"import {{ {', '.join(symbols)} }} from {json.dumps((CHAMPION_DIRECTORY / name).as_uri())};"


def run_node(script, inputs, environment=None):
    """Run an ES-module script in node with `inputs` on stdin (JSON) and return its stdout parsed as JSON."""
    result = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(inputs), capture_output=True, text=True,
                            cwd=REPOSITORY_ROOT, env={**os.environ, **(environment or {})}, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)
