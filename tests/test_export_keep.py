"""scripts/export_keep.py — the one command that turns a Champion's keep into the file the face draws.

Run over the invented Champion's keep, written to a temporary directory: the script refuses anything
inside this checkout, and this is where that refusal is proved.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from champion_fixture import A_DATE_IN_CALENDAR, DATE_PAST_CALENDAR, build_champion_keep
from helpers import REPOSITORY_ROOT

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
from fk_core.web_keep import check_web_keep  # noqa: E402

SCRIPT = REPOSITORY_ROOT / "scripts" / "export_keep.py"
PINNED_EXPORTED_AT = "2026-08-27T18:00:00+00:00"


def run_script(*arguments):
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, timeout=300)


class ExportKeepTests(unittest.TestCase):
    def test_it_writes_a_conforming_keep_outside_the_checkout(self):
        with tempfile.TemporaryDirectory() as scratch:
            champion = Path(scratch) / "champion.json"
            champion.write_text(json.dumps(build_champion_keep()), encoding="utf-8")
            out = Path(scratch) / "keep.json"
            result = run_script("--champion", str(champion), "--date", A_DATE_IN_CALENDAR,
                                "--exported-at", PINNED_EXPORTED_AT, "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(check_web_keep(written).ok)
            self.assertEqual(written["meta"]["exportedAt"], PINNED_EXPORTED_AT)
            self.assertIsNotNone(written["season"])
            self.assertEqual(len(written["days"]), 14)
            checked = run_script("--champion", str(champion), "--date", A_DATE_IN_CALENDAR, "--check")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("conforms", checked.stdout)
            # Past the calendar the keep still conforms, and the script says what it is missing.
            past = run_script("--champion", str(champion), "--date", DATE_PAST_CALENDAR, "--check")
            self.assertEqual(past.returncode, 0, past.stderr)
            self.assertIn("outside", past.stderr)

    def test_it_refuses_to_write_inside_this_repository_and_writes_nothing(self):
        inside = REPOSITORY_ROOT / "data" / "example-keep-that-must-not-exist.json"
        with tempfile.TemporaryDirectory() as scratch:
            champion = Path(scratch) / "champion.json"
            champion.write_text(json.dumps(build_champion_keep()), encoding="utf-8")
            result = run_script("--champion", str(champion), "--date", A_DATE_IN_CALENDAR, "--out", str(inside))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refused", result.stderr)
            self.assertFalse(inside.exists(), "a keep was written into the repository")
            # And a Champion's keep inside the checkout is refused before anything is read.
            inside_champion = REPOSITORY_ROOT / "tests" / "fixtures" / "keep.sample.json"
            result = run_script("--champion", str(inside_champion), "--check")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refused", result.stderr)
            # A directory is refused before anything is built, so no temp file can be left in it.
            result = run_script("--champion", str(champion), "--date", A_DATE_IN_CALENDAR, "--out", scratch)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("directory", result.stderr)
            self.assertEqual(sorted(Path(scratch).iterdir()), [champion], "a temp file was left behind")
            # And a date that is not a date is refused rather than exported season-less.
            result = run_script("--champion", str(champion), "--date", "2026-2-18", "--check")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("YYYY-MM-DD", result.stderr)
