"""Tests for the adversarial-review hook scripts (scripts/*-review-hook.sh).

Each test runs the script as a subprocess with a fabricated hook payload on
stdin, in a throwaway git repository under tmp. The scripts gate on a repo
marker (`.kimi-code/skills/adversarial-review/SKILL.md` or the `.claude`
equivalent) because kimi's hooks are registered globally.

Twin note: the scripts under test are this repo's COPIES. The canonical pair
lives in `beinsiculous/insiculous`, which carries no test suite of its own
(`beinsiculous/insiculous#23`), and `scripts/check-skill-parity.sh` there is
what holds every copy byte-identical to it. So this file is the whole org's
coverage of those two hooks, and it is coverage of the canonical only while
that parity check is green. The adversarial-review SKILL.md names this file
from the other side of the pair.
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


def dirty_without_staging(repository, line_count):
    """A tracked file with `line_count` changed lines in the WORKING TREE and an empty index.

    This is the shape that named-path commits take content from, and the shape that sizing the
    index alone reports as zero.
    """
    (repository / "change.txt").write_text("original\n")
    run_git(repository, "add", "change.txt")
    run_git(repository, "commit", "-qm", "add change.txt")
    (repository / "change.txt").write_text("line\n" * line_count)


def run_hook(script, harness, command, cwd):
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [str(script), f"--harness={harness}"],
        input=payload, cwd=cwd, capture_output=True, text=True,
    )


@unittest.skipUnless(shutil.which("git") and shutil.which("jq"), "needs git and jq")
class NestedWorkingSetTest(unittest.TestCase):
    """The admin-repo layout: project repos cloned inside a parent repo.

    The commit is issued from the parent, so the repository being committed to
    is not the one the hook stands in. Sizing the parent's diff there finds
    nothing and waves a big commit through — silently, which is the worst way
    for a gate to fail. Anything the hook cannot reduce to one repository is
    denied rather than guessed.
    """

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.parent = Path(self.temporary_directory.name) / "admin"
        self.parent.mkdir()
        make_repository(self.parent)
        self.nested = self.parent / "nested"
        self.nested.mkdir()
        make_repository(self.nested)
        stage_changes(self.nested, BIG_LINES)
        self.small = self.parent / "small"
        self.small.mkdir()
        make_repository(self.small)
        stage_changes(self.small, 3)

    def assert_denied(self, command):
        result = run_hook(COMMIT_HOOK, "claude", command, self.parent)
        self.assertIn('"deny"', result.stdout, f"expected a denial for: {command}")

    def assert_allowed(self, command):
        result = run_hook(COMMIT_HOOK, "claude", command, self.parent)
        self.assertNotIn('"deny"', result.stdout, f"expected no denial for: {command}")

    def test_dash_c_into_a_big_nested_repo_is_denied(self):
        """The headline case: `git commit` is not even a substring of this."""
        self.assert_denied("git -C nested commit -m x")

    def test_dash_c_without_a_space_is_denied(self):
        self.assert_denied("git -Cnested commit -m x")

    def test_cd_into_a_big_nested_repo_is_denied(self):
        self.assert_denied("cd nested && git commit -m x")

    def test_git_dir_is_denied_as_unresolvable(self):
        self.assert_denied("git --git-dir=nested/.git commit -m x")

    def test_git_dir_environment_variable_is_denied_as_unresolvable(self):
        self.assert_denied("GIT_DIR=nested/.git git commit -m x")

    def test_subshell_is_denied_as_unresolvable(self):
        self.assert_denied("(cd nested && git commit -m x)")

    def test_quoted_target_is_denied_as_unresolvable(self):
        """Quoted segments are stripped before matching, so the path is gone."""
        self.assert_denied('git -C "nested" commit -m x')

    def test_chained_directory_changes_compose_to_the_real_target(self):
        """`cd nested && cd ..` lands back in the parent, so the parent is sized.

        Composing is better than refusing: the gate ends up measuring the repo
        the commit truly lands in rather than denying a legitimate command.
        """
        self.assert_allowed("cd nested && cd .. && git commit -m x")   # parent has nothing staged
        stage_changes(self.parent, BIG_LINES)
        self.assert_denied("cd nested && cd .. && git commit -m x")

    def test_a_relative_dash_c_is_resolved_against_the_directory_the_cds_reached(self):
        """The silent bypass: -C is relative to where the walked `cd`s got to, not to the cwd.

        `cd nested && git -C . commit` used to resolve `.` against the ADMIN repo, find nothing
        staged there, and wave a commit of any size through. Reproduced at 9,675 staged lines.
        """
        self.assert_denied("cd nested && git -C . commit -m x")

    def test_a_relative_dash_c_composes_with_the_cd_rather_than_being_taken_alone(self):
        """`cd nested && git -C ../small` really does mean small, and small is under threshold."""
        self.assert_allowed("cd nested && git -C ../small commit -m x")
        self.assert_denied("cd small && git -C ../nested commit -m x")

    def test_an_absolute_dash_c_ignores_the_cds_before_it(self):
        self.assert_denied(f"cd small && git -C {self.nested} commit -m x")

    def test_a_dash_c_belonging_to_another_command_does_not_redirect_the_gate(self):
        """Code review F1: `git -C small status; git commit` sized `small`.

        The -C belonged to a different git call, so the gate measured the wrong
        repository, found nothing, and let the real commit land unreviewed.
        """
        stage_changes(self.parent, BIG_LINES)
        self.assert_denied("git -C small status; git commit -m x")

    def test_committing_to_two_repos_in_one_command_is_denied(self):
        """Code review F3: only the last -C was sized, so the first went ungated."""
        self.assert_denied("git -C nested commit -m a && git -C small commit -m b")

    def test_commit_tree_is_not_a_commit(self):
        """Code review F4: `\\bcommit\\b` matched commit-tree and commit-graph."""
        stage_changes(self.parent, BIG_LINES)
        self.assert_allowed("git commit-tree abc123 -m x")

    def test_a_variable_target_is_denied_rather_than_guessed(self):
        self.assert_denied("git -C $PROJECT commit -m x")

    def test_dash_c_into_a_small_repo_still_passes(self):
        self.assert_allowed("git -C small commit -m x")

    def test_a_message_mentioning_the_flags_is_not_a_redirect(self):
        self.assert_allowed("git commit -m 'mentions -C and cd in the text'")

    def test_reading_commands_are_not_commits(self):
        """`git log --grep=commit` must not be mistaken for a commit."""
        self.assert_allowed("git log --grep=commit")

    def test_an_unmarked_parent_stays_silent(self):
        plain = Path(self.temporary_directory.name) / "plain"
        plain.mkdir()
        make_repository(plain, with_marker=False)
        nested = plain / "nested"
        nested.mkdir()
        make_repository(nested)
        stage_changes(nested, BIG_LINES)
        result = run_hook(COMMIT_HOOK, "claude", "git --git-dir=nested/.git commit -m x", plain)
        self.assertEqual(result.stdout, "")


@unittest.skipUnless(shutil.which("git") and shutil.which("jq"), "needs git and jq")
class NamedPathTest(unittest.TestCase):
    """Naming a path takes the working tree, whatever the index holds.

    Sizing only the index reported zero for this shape and let any amount of unstaged work land
    with no review and no trace — reproduced at 800 changed lines. The controls matter as much as
    the bypasses: a flag's value must never be mistaken for a path, or ordinary commits are denied.
    """

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name) / "repo"
        self.repository.mkdir()
        make_repository(self.repository)
        dirty_without_staging(self.repository, BIG_LINES)

    def assert_denied(self, command):
        result = run_hook(COMMIT_HOOK, "claude", command, self.repository)
        self.assertIn('"deny"', result.stdout, f"expected a denial for: {command}")

    def assert_allowed(self, command):
        result = run_hook(COMMIT_HOOK, "claude", command, self.repository)
        self.assertNotIn('"deny"', result.stdout, f"expected no denial for: {command}")

    def test_a_named_path_with_an_empty_index_is_sized_and_denied(self):
        self.assert_denied("git commit change.txt -m x")

    def test_only_and_a_named_path_is_denied(self):
        self.assert_denied("git commit --only change.txt -m x")
        self.assert_denied("git commit -o change.txt -m x")

    def test_paths_after_a_double_dash_are_denied(self):
        self.assert_denied("git commit -m x -- change.txt")

    def test_a_named_path_is_still_denied_when_redirected(self):
        result = run_hook(COMMIT_HOOK, "claude", "git -C repo commit change.txt -m x",
                          self.repository.parent)
        self.assertIn('"deny"', result.stdout)

    def test_paths_taken_from_a_file_are_denied_in_every_spelling(self):
        """--pathspec-from-file names paths as surely as writing them out.

        All three forms passed silently at 400 unstaged lines. Listing the option among the
        value-taking flags was worse than omitting it: the separate form then swallowed its own
        filename and reported no paths at all. Anyone who met the denial once could route around
        it permanently with a documented flag.
        """
        (self.repository / "paths.txt").write_text("change.txt\n")
        self.assert_denied("git commit --pathspec-from-file=paths.txt -m x")
        self.assert_denied("git commit --pathspec-from-file paths.txt -m x")
        self.assert_denied("git commit --pathspec-from-file=- -m x")

    def test_a_flag_value_is_not_mistaken_for_a_path(self):
        """-F's argument is a message file, not something to commit. Reading it as a path would
        size the whole working tree and deny an ordinary commit that stages nothing."""
        (self.repository / "msg.txt").write_text("a message\n")
        self.assert_allowed("git commit -F msg.txt")
        self.assert_allowed("git commit --file=msg.txt")
        self.assert_allowed("git commit --author=Someone --date=2026-01-01 --amend --no-edit")
        self.assert_allowed("git commit --cleanup=strip --amend --no-edit")

    def test_a_cluster_of_short_flags_does_not_read_its_message_as_a_path(self):
        """`git commit -qm "msg"` is routine, and it names no path.

        A cluster ends in the flag that takes the value, so -qm/-sm/-vm all carry a message. Read
        as paths, they sized the whole working tree and denied an ordinary commit on a dirty tree
        — the exact case the placeheld-token design exists to protect.
        """
        for command in ['git commit -qm "msg"', 'git commit -sm "msg"', 'git commit -vm "msg"']:
            self.assert_allowed(command)

    def test_a_cluster_ending_in_a_value_flag_still_sees_a_path_after_its_value(self):
        """Consuming the value must not consume the path that follows it."""
        self.assert_denied('git commit -qm "msg" change.txt')

    def test_naming_no_path_leaves_an_empty_index_sized_at_zero(self):
        self.assert_allowed("git commit --amend --no-edit")
        self.assert_allowed("git commit -m x")

    def test_a_small_working_tree_still_passes_when_a_path_is_named(self):
        small = Path(self.temporary_directory.name) / "small"
        small.mkdir()
        make_repository(small)
        dirty_without_staging(small, 3)
        result = run_hook(COMMIT_HOOK, "claude", "git commit change.txt -m x", small)
        self.assertNotIn('"deny"', result.stdout)


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
