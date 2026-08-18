"""Tests for the adversarial-review hook scripts (scripts/*-review-hook.sh).

Each test runs the script as a subprocess with a fabricated hook payload on
stdin, in a throwaway git repository under tmp. The scripts gate on a repo
marker (`.kimi-code/skills/adversarial-review/SKILL.md` or the `.claude`
equivalent) because kimi's hooks are registered globally.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMMIT_HOOK = REPOSITORY_ROOT / "scripts" / "commit-review-hook.sh"
PLAN_HOOK = REPOSITORY_ROOT / "scripts" / "plan-review-hook.sh"
MARKER = Path(".kimi-code/skills/adversarial-review/SKILL.md")

BIG_LINES = 120  # threshold in commit-review-hook.sh is 100


def run_git(repository, *args):
    subprocess.run(["git", *args], cwd=repository, check=True,
                   capture_output=True, text=True)


def make_repository(root, with_marker=True):
    run_git(root, "init", "-q")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "config", "user.name", "Test")
    run_git(root, "config", "commit.gpgsign", "false")
    if with_marker:
        marker = root / MARKER
        marker.parent.mkdir(parents=True)
        marker.write_text("marker\n")
    (root / "seed.txt").write_text("seed\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-qm", "seed")


def stage_changes(repository, line_count):
    (repository / "change.txt").write_text("line\n" * line_count)
    run_git(repository, "add", "change.txt")


def run_hook(script, harness, command, cwd):
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [str(script), f"--harness={harness}"],
        input=payload, cwd=cwd, capture_output=True, text=True,
    )


@unittest.skipUnless(shutil.which("git") and shutil.which("jq"), "needs git and jq")
class CommitReviewHookTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name)
        make_repository(self.repository)

    def test_non_commit_command_passes(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git status", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_small_commit_passes(self):
        stage_changes(self.repository, 10)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'small'", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_big_commit_denied_kimi(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("adversarial CODE review", result.stderr)
        self.assertIn("--reviewer=claude", result.stderr)

    def test_big_commit_denied_claude(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "claude", "git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("--reviewer=kimi", decision["permissionDecisionReason"])

    def test_adv_reviewed_bypass_passes(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "ADV_REVIEWED=1 git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_bypass_inside_commit_message_does_not_count(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'ADV_REVIEWED=1 was set'", self.repository)
        self.assertEqual(result.returncode, 2)

    def test_unmarked_repo_passes(self):
        shutil.rmtree(self.repository / ".kimi-code")
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_non_git_directory_passes(self):
        with tempfile.TemporaryDirectory() as outside:  # genuinely outside any repo
            result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", Path(outside))
        self.assertEqual(result.returncode, 0)

    def test_unknown_argument_fails_loudly(self):
        result = subprocess.run(
            [str(COMMIT_HOOK), "--harness=bogus"],
            input="{}", capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)


@unittest.skipUnless(shutil.which("git") and shutil.which("jq"), "needs git and jq")
class PlanReviewHookTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name)
        make_repository(self.repository)

    def test_kimi_prints_routing_instruction(self):
        result = run_hook(PLAN_HOOK, "kimi", "", self.repository)
        self.assertEqual(result.returncode, 0)
        self.assertIn("review/plan.md", result.stdout)
        self.assertIn("--reviewer=claude", result.stdout)

    def test_claude_prints_additional_context_json(self):
        result = run_hook(PLAN_HOOK, "claude", "", self.repository)
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("--reviewer=kimi", context)

    def test_unmarked_repo_silent(self):
        shutil.rmtree(self.repository / ".kimi-code")
        result = run_hook(PLAN_HOOK, "kimi", "", self.repository)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
