"""The devlog comment badge (src/lib/devlog-status.js), driven through node the same way
tests/test_workspace_docs.py drives the assistant-workspace contract.

The rule, stated once here so a change to it has to come through this file:
one comment from anyone on the roster (Claude, Kimi, Gemini, Jesse, M) other than the post's author
completes the post; the author’s own comment never counts; still waiting -> "NEW" (<= 7 days) or "OLD"
in the author's colour; commented on -> plain green "NEW" for 7 days counted from the qualifying
comment that completed it, and then nothing at all.
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
ROSTER = ["claude", "kimi", "gemini", "jesse", "m"]
AGENTS = ["claude", "kimi", "gemini"]
DEVELOPERS = ["jesse", "m"]


def status(post, now=TODAY):
    return run_node(STATUS_SCRIPT, {"posts": [post], "now": now})[0]


def still_new(posts, now=TODAY):
    return run_node(STILL_NEW_SCRIPT, {"posts": posts, "now": now})


def post(author, pub_date, comments=()):
    return {"author": author, "pubDate": pub_date, "comments": [{"author": who, "date": when} for who, when in comments]}


def parse_devlog_frontmatter(path):
    parts = path.read_text(encoding="utf-8").split("---", 2)
    if len(parts) < 3:
        return {}
    fm_lines = parts[1].splitlines()
    data = {"path": path, "comments": []}
    in_comment_body = False
    current_body_lines = []

    for line in fm_lines:
        stripped = line.strip()
        if in_comment_body:
            if line.startswith("    ") or stripped == "":
                if stripped and not stripped.startswith("#"):
                    current_body_lines.append(stripped)
                continue
            else:
                if current_body_lines:
                    data["comments"].append("\n".join(current_body_lines))
                    current_body_lines = []
                in_comment_body = False

        if line.startswith("#"):
            continue

        if line.startswith("title:"):
            v = line.split(":", 1)[1].strip()
            data["title"] = v[1:-1] if (v.startswith(("\'", '"')) and v.endswith(("\'", '"'))) else v
        elif line.startswith("description:"):
            v = line.split(":", 1)[1].strip()
            data["description"] = v[1:-1] if (v.startswith(("\'", '"')) and v.endswith(("\'", '"'))) else v
        elif line.startswith("prompt:"):
            v = line.split(":", 1)[1].strip()
            data["prompt"] = v[1:-1] if (v.startswith(("\'", '"')) and v.endswith(("\'", '"'))) else v
        elif line.startswith("author:"):
            v = line.split(":", 1)[1].strip()
            data["author"] = v[1:-1] if (v.startswith(("\'", '"')) and v.endswith(("\'", '"'))) else v
        elif line.startswith("pubDate:"):
            v = line.split(":", 1)[1].strip()
            data["pubDate"] = v[1:-1] if (v.startswith(("\'", '"')) and v.endswith(("\'", '"'))) else v
        elif "body: |" in line or (line.strip().startswith("body:") and not line.strip().startswith("#")):
            in_comment_body = True
            body_val = line.split("body:", 1)[1].strip()
            if body_val and body_val != "|":
                current_body_lines.append(body_val)

    if in_comment_body and current_body_lines:
        data["comments"].append("\n".join(current_body_lines))

    return data


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class DevlogStatusTests(unittest.TestCase):
    def test_uncommented_agent_post_wears_its_author_colour(self):
        for author in AGENTS:
            with self.subTest(author=author):
                result = status(post(author, "2026-08-15"))
                self.assertEqual((result["label"], result["tone"]), ("NEW", author))
                self.assertNotIn("awaiting", result)

    def test_seven_days_is_still_new_and_eight_is_old(self):
        self.assertEqual(status(post("kimi", "2026-08-12"))["label"], "NEW")  # exactly 7 days
        self.assertEqual(status(post("kimi", "2026-08-11"))["label"], "OLD")  # 8
        self.assertEqual(status(post("kimi", "2026-08-11"))["tone"], "kimi")  # the colour survives the word

    def test_one_comment_from_anyone_else_completes_it(self):
        """Every author on the roster can be completed by any other person on the roster (20 combinations)."""
        for author in ROSTER:
            for commenter in ROSTER:
                if commenter == author:
                    continue
                with self.subTest(author=author, commenter=commenter):
                    result = status(post(author, "2026-08-15", [(commenter, "2026-08-16")]))
                    self.assertTrue(result["complete"])
                    self.assertEqual((result["label"], result["tone"]), ("NEW", "complete"))

    def test_completing_an_old_post_restarts_the_countdown(self):
        """A months-old post that finally gets a qualifying comment is green "NEW" again, dated from that
        comment — the restart the badge rules promise."""
        result = status(post("kimi", "2026-01-05", [("m", "2026-08-18")]))
        self.assertEqual((result["label"], result["tone"], result["ageDays"]), ("NEW", "complete", 1))

    def test_green_expires_into_no_badge(self):
        result = status(post("kimi", "2026-01-05", [("m", "2026-08-11")]))
        self.assertIsNone(result["label"])
        self.assertIsNone(result["tone"])
        self.assertTrue(result["complete"])

    def test_the_earliest_comment_from_anyone_else_is_the_one_that_counts(self):
        """A later comment from another person must not push the countdown forward — otherwise a post could be kept
        green indefinitely by whoever talks the most."""
        result = status(post("claude", "2026-07-01", [("jesse", "2026-07-02"), ("m", "2026-07-03"), ("m", "2026-08-19")]))
        self.assertIsNone(result["label"])

    def test_a_developer_post_wears_the_developer_look(self):
        for author in DEVELOPERS:
            with self.subTest(author=author):
                result = status(post(author, "2026-08-15"))
                self.assertEqual((result["label"], result["tone"]), ("NEW", "developer"))
                self.assertNotIn("awaiting", result)

    def test_an_agent_comment_completes_a_developer_post(self):
        result = status(post("m", "2026-08-15", [("gemini", "2026-08-16")]))
        self.assertTrue(result["complete"])
        self.assertEqual((result["label"], result["tone"]), ("NEW", "complete"))

    def test_an_author_cannot_complete_their_own_post(self):
        for author in ROSTER:
            with self.subTest(author=author):
                result = status(post(author, "2026-08-15", [(author, "2026-08-16")]))
                self.assertFalse(result["complete"])
                self.assertEqual(result["ageDays"], 4)

    def test_a_comment_predating_the_post_cannot_pull_the_countdown_backwards(self):
        """Defensive: the anchor is never earlier than publication, however the dates were typed."""
        result = status(post("claude", "2026-08-18", [("jesse", "2026-01-01")]))
        self.assertEqual(result["ageDays"], 1)

    def test_an_unknown_author_is_a_build_failure_not_a_missing_badge(self):
        with self.assertRaises(AssertionError):
            status(post("someone-else", "2026-08-18"))

    def test_the_hidden_description_states_waiting_or_completing_commenter(self):
        """The colour alone must not be the only carrier of meaning (WCAG 1.4.1) — the badge ships
        this sentence to screen readers."""
        waiting = status(post("claude", "2026-08-18"))
        self.assertEqual(waiting["description"], "Claude’s post, still waiting on its first comment from someone else")
        self.assertNotIn("awaitingNames", waiting)

        complete_fresh = status(post("claude", "2026-08-18", [("m", "2026-08-18")]))
        self.assertEqual(complete_fresh["description"], "commented on by M")

        complete_stale = status(post("claude", "2026-08-01", [("m", "2026-08-02")]))
        self.assertEqual(complete_stale["description"], "")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PostsStillNewTests(unittest.TestCase):
    """What the publish warning on /devlog/ counts. More than one of these and a new post would
    take the listing from a post nobody has commented on yet."""

    def test_only_the_fresh_ones_come_back(self):
        self.assertEqual(still_new([post("claude", "2026-08-18"), post("kimi", "2026-08-11")]), ["claude"])

    def test_green_counts_too_because_it_still_reads_new(self):
        """A post that just went green is having its turn on the listing as much as a red one —
        the word on the badge is NEW either way, so the warning must see it."""
        green = post("claude", "2026-08-15", [("m", "2026-08-17")])
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
                self.assertIn(authors[0], ROSTER)

    def test_rendered_frontmatter_strings_have_no_straight_apostrophes(self):
        """Rendered frontmatter strings (title, description, prompt, comment bodies) obey the prose gate:
        no \\w'\\w straight apostrophes allowed."""
        for path in sorted((REPOSITORY_ROOT / "src" / "content" / "devlog").glob("*.md")):
            with self.subTest(post=path.name):
                parsed = parse_devlog_frontmatter(path)
                for field in ("title", "description", "prompt"):
                    if field in parsed:
                        self.assertNotRegex(
                            parsed[field],
                            r"\w'\w",
                            f"Straight apostrophe found in {field} of {path.name}",
                        )
                for index, body in enumerate(parsed["comments"]):
                    self.assertNotRegex(
                        body,
                        r"\w'\w",
                        f"Straight apostrophe found in comment body #{index} of {path.name}",
                    )

    def test_prompt_field_validation(self):
        """S9 prompt validation:
        - Present: non-empty, at most 280 characters, no straight apostrophe.
        - Required on every agent-authored entry dated on or after 2026-09-04.
        - Developer posts may carry one and are never required to."""
        for path in sorted((REPOSITORY_ROOT / "src" / "content" / "devlog").glob("*.md")):
            with self.subTest(post=path.name):
                parsed = parse_devlog_frontmatter(path)
                author = parsed.get("author")
                pub_date = parsed.get("pubDate", "")
                prompt = parsed.get("prompt")

                if prompt is not None:
                    self.assertTrue(prompt.strip(), f"prompt in {path.name} cannot be empty")
                    self.assertLessEqual(
                        len(prompt.strip()),
                        280,
                        f"prompt in {path.name} exceeds 280 characters ({len(prompt.strip())} chars)",
                    )
                    self.assertNotRegex(
                        prompt,
                        r"\w'\w",
                        f"Straight apostrophe found in prompt of {path.name}",
                    )

                if author in AGENTS and pub_date >= "2026-09-04":
                    self.assertIsNotNone(
                        prompt,
                        f"{path.name} is an agent post on or after 2026-09-04 and must carry prompt:",
                    )


if __name__ == "__main__":
    unittest.main()

