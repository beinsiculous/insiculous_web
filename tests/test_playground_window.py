"""Exercise the editor window's two scripts — the project lock and the move — over fakes."""
import subprocess
import unittest
from pathlib import Path


class PlaygroundWindowTests(unittest.TestCase):
    def run_scenarios(self, script):
        repository = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ["node", script],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_one_page_per_project_by_a_lock_never_queued(self):
        self.assertIn("Project lock: 10 scenarios passed", self.run_scenarios("tests/playground_project_lock.mjs"))

    def test_the_move_runs_its_four_steps_in_order_and_stops_safely(self):
        self.assertIn("Editor window: 10 scenarios passed", self.run_scenarios("tests/playground_window.mjs"))


if __name__ == "__main__":
    unittest.main()
