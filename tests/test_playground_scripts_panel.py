"""Exercise the Scripts panel's real listeners against a minimal DOM and file bridge."""
import subprocess
import unittest
from pathlib import Path


class PlaygroundScriptsPanelTests(unittest.TestCase):
    def test_mutation_guard_keeps_the_script_and_save_target_consistent(self):
        repository = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", "tests/playground_scripts_panel.mjs"],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("10 scenarios passed", result.stdout)
