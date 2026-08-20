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

# A well-formed signed skip: a reason over ten characters and a name behind it.
SIGNED_SKIP = (
    "big\n"
    "\n"
    "Adversarial-Review-Skipped: the reviewer is offline and the demo is tonight\n"
    "Skip-Signed-Off-By: M"
)


def commit_with(message):
    """A commit whose message really does span lines, as a trailer must."""
    return f"git commit -m '{message}'"


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
        """ADV_REVIEWED=1 asserts the review HAPPENED — it is no longer a way to skip one."""
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "ADV_REVIEWED=1 git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_bypass_inside_commit_message_does_not_count(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'ADV_REVIEWED=1 was set'", self.repository)
        self.assertEqual(result.returncode, 2)

    # ---- the signed skip: the only way past the gate without a review -------

    def test_signed_skip_passes(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(SIGNED_SKIP), self.repository)
        self.assertEqual(result.returncode, 0)

    def test_any_reason_over_ten_characters_is_accepted(self):
        """The hook does not judge the reason: 'just because' is twelve characters and fine."""
        stage_changes(self.repository, BIG_LINES)
        message = "big\n\nAdversarial-Review-Skipped: just because\nSkip-Signed-Off-By: M"
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 0)

    def test_reason_of_exactly_ten_characters_is_rejected(self):
        stage_changes(self.repository, BIG_LINES)
        message = "big\n\nAdversarial-Review-Skipped: 1234567890\nSkip-Signed-Off-By: M"
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("10 characters", result.stderr)

    def test_reason_without_a_signature_is_rejected(self):
        stage_changes(self.repository, BIG_LINES)
        message = "big\n\nAdversarial-Review-Skipped: shipping this before the demo"
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("nobody signed it", result.stderr)

    def test_signature_without_a_reason_is_rejected(self):
        stage_changes(self.repository, BIG_LINES)
        message = "big\n\nSkip-Signed-Off-By: M"
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("sign a reason", result.stderr)

    def test_skip_trailers_are_read_from_a_message_file(self):
        """-F <file>: the trailers live on disk, not in the command string."""
        stage_changes(self.repository, BIG_LINES)
        (self.repository / "msg.txt").write_text(SIGNED_SKIP + "\n")
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -F msg.txt", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_plain_big_commit_is_told_how_to_skip(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Adversarial-Review-Skipped", result.stderr)
        self.assertIn("Skip-Signed-Off-By", result.stderr)

    def test_denial_says_how_to_recover_an_editor_message(self):
        """review-1 F4: trailers typed in $EDITOR are invisible here; say where they landed."""
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", self.repository)
        self.assertIn("COMMIT_EDITMSG", result.stderr)

    def test_documentation_quoting_the_trailers_is_not_a_skip(self):
        """review-1 F2: this fired for real on the command that wrote the skip docs.

        A commit whose *body* quotes the trailer format — as this repo's own
        documentation does — must still be gated. Only the last lines count.
        """
        stage_changes(self.repository, BIG_LINES)
        message = (
            "document the skip convention\n"
            "\n"
            "Adversarial-Review-Skipped: <reason, more than 10 characters>\n"
            "Skip-Signed-Off-By: <the developer name>\n"
            "\n"
            "...and that is how the trailers work. More prose follows, so the quoted\n"
            "format sits well outside the tail the hook actually reads.\n"
            "one\ntwo\nthree\nfour\nfive\nsix\nseven\neight\nnine\nten\neleven\ntwelve"
        )
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 2)

    def test_message_file_is_found_in_every_spelling(self):
        """review-1 F3: -F path, -Fpath, --file=path, --file path, and quoted paths."""
        stage_changes(self.repository, BIG_LINES)
        (self.repository / "msg.txt").write_text(SIGNED_SKIP + "\n")
        (self.repository / "my message.txt").write_text(SIGNED_SKIP + "\n")
        for command in (
            "git commit -F msg.txt",
            "git commit -Fmsg.txt",
            "git commit --file=msg.txt",
            "git commit --file msg.txt",
            "git commit -F 'my message.txt'",
        ):
            with self.subTest(command=command):
                result = run_hook(COMMIT_HOOK, "kimi", command, self.repository)
                self.assertEqual(result.returncode, 0)

    def test_missing_message_file_denies_rather_than_erroring(self):
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -F nowhere.txt", self.repository)
        self.assertEqual(result.returncode, 2)

    def test_quoted_template_in_the_final_lines_is_not_a_skip(self):
        """review-2 F1: the tail window alone wasn't enough — the template is not a reason.

        A commit that documents this convention naturally *ends* with the
        example, putting both placeholders inside the tail. The reason
        '<reason, more than 10 characters>' is 33 characters and would sail
        through the length check, signing a skip in a placeholder's name.
        """
        stage_changes(self.repository, BIG_LINES)
        message = (
            "document the skip convention\n"
            "\n"
            "The trailers go at the end of the message, like this:\n"
            "\n"
            "Adversarial-Review-Skipped: <reason, more than 10 characters>\n"
            "Skip-Signed-Off-By: <the developer name>"
        )
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("template", result.stderr)

    def test_the_last_trailer_wins_over_a_quoted_one(self):
        """review-2 F1: quote the format, then sign for real — the signature is what counts."""
        stage_changes(self.repository, BIG_LINES)
        message = (
            "document the convention and skip the review\n"
            "\n"
            "The format is 'Adversarial-Review-Skipped: <reason>', and here is mine:\n"
            "\n"
            "Adversarial-Review-Skipped: the reviewer is offline and the demo is tonight\n"
            "Skip-Signed-Off-By: M"
        )
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 0)

    def test_a_signer_may_carry_an_email_in_angle_brackets(self):
        """Only a value that OPENS with '<' is the template; a signed name with an address is not."""
        stage_changes(self.repository, BIG_LINES)
        message = (
            "big\n"
            "\n"
            "Adversarial-Review-Skipped: the reviewer is offline and the demo is tonight\n"
            "Skip-Signed-Off-By: M <m@example.com>"
        )
        result = run_hook(COMMIT_HOOK, "kimi", commit_with(message), self.repository)
        self.assertEqual(result.returncode, 0)

    def test_message_quoting_the_editor_recovery_hint_does_not_read_that_file(self):
        """review-2 F2: COMMIT_EDITMSG holds the PREVIOUS attempt, trailers and all.

        The denial hands out the string '-F .git/COMMIT_EDITMSG'. A commit that
        quotes that advice inside its own -m message must not cause the stale
        file to be read as this commit's message.
        """
        stage_changes(self.repository, BIG_LINES)
        (self.repository / ".git" / "COMMIT_EDITMSG").write_text(SIGNED_SKIP + "\n")
        command = "git commit -m 'hook: explain the -F .git/COMMIT_EDITMSG retry path'"
        result = run_hook(COMMIT_HOOK, "kimi", command, self.repository)
        self.assertEqual(result.returncode, 2)

    def test_an_explicit_editor_message_file_is_still_honoured(self):
        """The F4 recovery path itself keeps working: -F before any -m, so it is the message."""
        stage_changes(self.repository, BIG_LINES)
        (self.repository / ".git" / "COMMIT_EDITMSG").write_text(SIGNED_SKIP + "\n")
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -F .git/COMMIT_EDITMSG", self.repository)
        self.assertEqual(result.returncode, 0)

    def test_denial_names_the_directory_message_files_are_read_from(self):
        """review-2 F3: `git -C elsewhere` fails closed, so say where we looked."""
        stage_changes(self.repository, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "kimi", "git commit -m 'big'", self.repository)
        self.assertIn("message files are read from", result.stderr)

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
