"""Which devlog posts the site shows (src/lib/devlog-posts.js), driven through node the same way
tests/test_user_settings.py drives the settings store, plus the content checks over
the real entries in src/content/devlog/.

The rule, stated once here so a change to it has to come through this file: a post with
`draft: true` is held back — no listing entry, no page of its own, no feed item — and what is left
comes out newest first. Four call sites share the one function, so a regression here hides or
reveals a post in all four places at once, and a partial hide would ship as a silent 404.
A published post cannot be dated in the future relative to now. A YYYY-MM-DD date is UTC
midnight, so "today" is valid once it is today in UTC.

Only Jesse and M write here; an agent never drafts, edits or comments on a post.
"""
from datetime import datetime, timezone
import json
import shutil
import unittest

from tests.helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

MODULE_URI = json.dumps((REPOSITORY_ROOT / "src" / "lib" / "devlog-posts.js").as_uri())

TODAY = "2026-08-19"

# Astro hands the function collection entries, so the fixtures are shaped like them: an id and a
# `data` object whose pubDate is a real Date.
PUBLISHED_SCRIPT = (
    f"import {{ publishedPosts }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "const entries = inputs.entries.map((entry) => ({"
    + "  id: entry.id,"
    + "  data: {"
    + "    ...entry,"
    + "    pubDate: new Date(entry.pubDate),"
    + "  }"
    + "}));"
    + "process.stdout.write(JSON.stringify(publishedPosts(entries, inputs.now).map((entry) => entry.id)));"
)


def published(entries, now=TODAY):
    return run_node(PUBLISHED_SCRIPT, {"entries": entries, "now": now})


def entry(identifier, pub_date, draft=None):
    made = {"id": identifier, "pubDate": pub_date}
    if draft is not None:
        made["draft"] = draft
    return made


AUTHORS = ("Jesse", "M")
DEVLOG_DIRECTORY = REPOSITORY_ROOT / "src" / "content" / "devlog"


def unquoted(value):
    value = value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    return value


def parse_devlog_frontmatter(path):
    """The scalar fields of one entry's frontmatter, without a YAML dependency: every field the site
    renders is a single line, and comment lines are skipped."""
    frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
    parsed = {}
    for line in frontmatter.splitlines():
        if line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = unquoted(value)
    return parsed


def real_entries():
    return sorted(DEVLOG_DIRECTORY.glob("*.md"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PublishedPostsTests(unittest.TestCase):
    def test_a_draft_is_held_back(self):
        self.assertEqual(published([entry("shown", "2026-08-19"), entry("held", "2026-08-21", True)]), ["shown"])

    def test_a_post_without_the_key_is_published(self):
        """The schema defaults `draft` to false, but the schema only runs at build time — the
        function must not need it to have been filled in."""
        self.assertEqual(published([entry("no-key", "2026-08-19")]), ["no-key"])

    def test_draft_false_is_published(self):
        self.assertEqual(published([entry("explicit", "2026-08-19", False)]), ["explicit"])

    def test_newest_first(self):
        entries = [entry("middle", "2026-08-19"), entry("oldest", "2026-07-29"), entry("newest", "2026-08-21")]
        self.assertEqual(published(entries, now="2026-08-21"), ["newest", "middle", "oldest"])

    def test_holding_everything_leaves_an_empty_devlog_rather_than_an_error(self):
        """The listing, the feed and the game pages all render an empty list; none of them may throw."""
        self.assertEqual(published([entry("held", "2026-08-21", True)]), [])

    def test_a_post_dated_in_the_future_fails_the_build(self):
        with self.assertRaises(AssertionError):
            published([entry("future", "2026-08-20")], now="2026-08-19")

    def test_a_post_dated_today_is_published(self):
        self.assertEqual(published([entry("today", "2026-08-19")], now="2026-08-19"), ["today"])

    def test_a_future_dated_draft_is_left_alone(self):
        self.assertEqual(published([entry("future-draft", "2026-08-20", draft=True)], now="2026-08-19"), [])



@unittest.skipIf(shutil.which("node") is None, "node not installed")
class RealDevlogPostsTests(unittest.TestCase):
    def test_every_published_real_post_passes_the_future_guard_with_utc_today(self):
        """Run every real entry through publishedPosts using UTC today: a YYYY-MM-DD date is UTC
        midnight, so 'today' is valid once it is today in UTC."""
        entries = []
        for path in real_entries():
            parsed = parse_devlog_frontmatter(path)
            entries.append(entry(path.stem, parsed["pubDate"], draft=parsed.get("draft") == "true"))

        today = datetime.now(timezone.utc).date().isoformat()
        published_ids = published(entries, now=today)
        expected_ids = [made["id"] for made in entries if not made.get("draft", False)]
        self.assertTrue(expected_ids)
        self.assertEqual(sorted(published_ids), sorted(expected_ids))


class DevlogContentTests(unittest.TestCase):
    def test_every_post_declares_one_of_the_two_authors(self):
        """The frontmatter schema requires it, but the schema only runs at build time — this fails
        the data suite too, where the loop is fast."""
        for path in real_entries():
            with self.subTest(post=path.name):
                frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
                authors = [line for line in frontmatter.splitlines() if line.startswith("author:")]
                self.assertEqual(len(authors), 1, "exactly one author: line")
                self.assertIn(parse_devlog_frontmatter(path)["author"], AUTHORS)

    def test_rendered_frontmatter_strings_have_no_straight_apostrophes(self):
        """`title` and `description` render through {expressions}, which Markdown's smart quotes
        never touch, so a straight apostrophe in either fails the prose gate at build time."""
        for path in real_entries():
            with self.subTest(post=path.name):
                parsed = parse_devlog_frontmatter(path)
                for field in ("title", "description"):
                    self.assertNotRegex(parsed[field], r"\w'\w", f"straight apostrophe in {field} of {path.name}")


if __name__ == "__main__":
    unittest.main()

