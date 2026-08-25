"""The devlog comment badge (src/lib/devlog-status.js), driven through node the same way
tests/test_workspace_docs.py drives the assistant-workspace contract.

The rule, stated once here so a change to it has to come through this file:
an agent's post needs a comment from both developers, a developer's post needs one from the other
developer; still waiting -> "NEW" (<= 7 days) or "OLD" in the author's colour; fully commented ->
plain green "NEW" for 7 days counted from the comment that completed it, and then nothing at all.
"""
import json
import shutil
import unittest

from tests.helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

MODULE_URI = json.dumps((REPOSITORY_ROOT / "src" / "lib" / "devlog-status.js").as_uri())

STATUS_SCRIPT = (
    f"import {{ statusFor }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(inputs.posts.map((post) => statusFor(post, inputs.now))));"
)

STILL_NEW_SCRIPT = (
    f"import {{ postsStillNew }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(postsStillNew(inputs.posts, inputs.now).map((post) => post.author)));"
)

TODAY = "2026-08-19"


def status(post, now=TODAY):
    return run_node(STATUS_SCRIPT, {"posts": [post], "now": now})[0]


def still_new(posts, now=TODAY):
    return run_node(STILL_NEW_SCRIPT, {"posts": posts, "now": now})


def post(author, pub_date, comments=()):
    return {"author": author, "pubDate": pub_date, "comments": [{"author": who, "date": when} for who, when in comments]}


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class DevlogStatusTests(unittest.TestCase):
    def test_uncommented_agent_post_wears_its_author_colour(self):
        for author, tone in (("claude", "claude"), ("kimi", "kimi")):
            with self.subTest(author=author):
                result = status(post(author, "2026-08-15"))
                self.assertEqual((result["label"], result["tone"]), ("NEW", tone))
                self.assertEqual(result["awaiting"], ["jesse", "m"])

    def test_one_developer_comment_is_not_enough(self):
        """Both developers are needed: a single comment leaves the badge in the author's colour."""
        result = status(post("claude", "2026-08-15", [("jesse", "2026-08-16")]))
        self.assertEqual((result["label"], result["tone"]), ("NEW", "claude"))
        self.assertEqual(result["awaiting"], ["m"])

    def test_seven_days_is_still_new_and_eight_is_old(self):
        self.assertEqual(status(post("kimi", "2026-08-12"))["label"], "NEW")  # exactly 7 days
        self.assertEqual(status(post("kimi", "2026-08-11"))["label"], "OLD")  # 8
        self.assertEqual(status(post("kimi", "2026-08-11"))["tone"], "kimi")  # the colour survives the word

    def test_both_comments_turn_it_green(self):
        result = status(post("claude", "2026-08-15", [("jesse", "2026-08-16"), ("m", "2026-08-17")]))
        self.assertEqual((result["label"], result["tone"]), ("NEW", "complete"))
        self.assertTrue(result["complete"])
        self.assertEqual(result["awaiting"], [])

    def test_completing_an_old_post_restarts_the_countdown(self):
        """A months-old post that finally gets both comments is green "NEW" again, dated from the
        second comment — the restart the badge rules promise."""
        result = status(post("kimi", "2026-01-05", [("jesse", "2026-01-06"), ("m", "2026-08-18")]))
        self.assertEqual((result["label"], result["tone"], result["ageDays"]), ("NEW", "complete", 1))

    def test_green_expires_into_no_badge(self):
        result = status(post("kimi", "2026-01-05", [("jesse", "2026-01-06"), ("m", "2026-08-11")]))
        self.assertIsNone(result["label"])
        self.assertIsNone(result["tone"])
        self.assertTrue(result["complete"])

    def test_the_earliest_comment_from_each_person_is_the_one_that_counts(self):
        """Commenting twice must not push the countdown forward — otherwise a post could be kept
        green indefinitely by whoever talks the most."""
        result = status(post("claude", "2026-07-01", [("jesse", "2026-07-02"), ("m", "2026-07-03"), ("m", "2026-08-19")]))
        self.assertIsNone(result["label"])

    def test_a_developer_post_waits_on_the_other_developer_only(self):
        for author, other in (("jesse", "m"), ("m", "jesse")):
            with self.subTest(author=author):
                result = status(post(author, "2026-08-15"))
                self.assertEqual((result["label"], result["tone"]), ("NEW", "developer"))
                self.assertEqual(result["awaiting"], [other])

    def test_agent_comments_never_gate_a_developer_post(self):
        waiting = status(post("jesse", "2026-08-15", [("claude", "2026-08-16"), ("kimi", "2026-08-16")]))
        self.assertEqual((waiting["label"], waiting["tone"], waiting["awaiting"]), ("NEW", "developer", ["m"]))
        done = status(post("jesse", "2026-08-15", [("m", "2026-08-16")]))
        self.assertEqual((done["label"], done["tone"]), ("NEW", "complete"))

    def test_a_developer_cannot_complete_their_own_post(self):
        result = status(post("m", "2026-08-15", [("m", "2026-08-16")]))
        self.assertEqual(result["awaiting"], ["jesse"])

    def test_a_comment_predating_the_post_cannot_pull_the_countdown_backwards(self):
        """Defensive: the anchor is never earlier than publication, however the dates were typed."""
        result = status(post("claude", "2026-08-18", [("jesse", "2026-01-01"), ("m", "2026-01-02")]))
        self.assertEqual(result["ageDays"], 1)

    def test_an_unknown_author_is_a_build_failure_not_a_missing_badge(self):
        with self.assertRaises(AssertionError):
            status(post("someone-else", "2026-08-18"))

    def test_the_hidden_description_names_who_is_still_owed(self):
        """The colour alone must not be the only carrier of meaning (WCAG 1.4.1) — the badge ships
        this sentence to screen readers."""
        result = status(post("claude", "2026-08-18", [("jesse", "2026-08-18")]))
        self.assertEqual(result["description"], "Claude’s post, still waiting on a comment from M")
        self.assertEqual(result["awaitingNames"], "M")

    def test_awaiting_names_are_pre_joined_for_the_pages(self):
        self.assertEqual(status(post("kimi", "2026-08-18"))["awaitingNames"], "Jesse and M")
        self.assertEqual(status(post("kimi", "2026-08-18", [("jesse", "2026-08-18"), ("m", "2026-08-18")]))["awaitingNames"], "")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PostsStillNewTests(unittest.TestCase):
    """What the publish warning on /devlog/ counts. More than one of these and a new post would
    take the listing from a post nobody has commented on yet."""

    def test_only_the_fresh_ones_come_back(self):
        self.assertEqual(still_new([post("claude", "2026-08-18"), post("kimi", "2026-08-11")]), ["claude"])

    def test_green_counts_too_because_it_still_reads_new(self):
        """A post that just went green is having its turn on the listing as much as a red one —
        the word on the badge is NEW either way, so the warning must see it."""
        green = post("claude", "2026-08-15", [("jesse", "2026-08-16"), ("m", "2026-08-17")])
        self.assertEqual(still_new([green]), ["claude"])

    def test_a_quiet_devlog_comes_back_empty(self):
        """OLD posts and posts whose green has expired are done having their turn."""
        expired = post("jesse", "2026-01-05", [("m", "2026-01-06")])
        self.assertEqual(still_new([post("kimi", "2026-08-11"), expired]), [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class DevlogContentTests(unittest.TestCase):
    def test_every_post_declares_an_author(self):
        """The frontmatter schema requires it, but the schema only runs at build time — this fails
        the data suite too, where the loop is fast."""
        for path in sorted((REPOSITORY_ROOT / "src" / "content" / "devlog").glob("*.md")):
            with self.subTest(post=path.name):
                frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
                authors = [line.split(":", 1)[1].strip() for line in frontmatter.splitlines() if line.startswith("author:")]
                self.assertEqual(len(authors), 1, "exactly one top-level author: line")
                self.assertIn(authors[0], ["claude", "kimi", "jesse", "m"])


if __name__ == "__main__":
    unittest.main()
