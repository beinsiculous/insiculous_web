"""Which devlog posts the site shows (src/lib/devlog-posts.js), driven through node the same way
tests/test_devlog_status.py drives the badge.

The rule, stated once here so a change to it has to come through this file: a post with
`draft: true` is held back — no listing entry, no page of its own, no feed item — and what is left
comes out newest first. Four call sites share the one function, so a regression here hides or
reveals a post in all four places at once, and a partial hide would ship as a silent 404.
Published posts and comments cannot be dated in the future relative to now. A YYYY-MM-DD date
is UTC midnight, so "today" is valid once it is today in UTC.
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
    + "    comments: (entry.comments || []).map((c) => ({ ...c, date: new Date(c.date) }))"
    + "  }"
    + "}));"
    + "process.stdout.write(JSON.stringify(publishedPosts(entries, inputs.now).map((entry) => entry.id)));"
)


def published(entries, now=TODAY):
    return run_node(PUBLISHED_SCRIPT, {"entries": entries, "now": now})


def entry(identifier, pub_date, draft=None, comments=()):
    made = {"id": identifier, "pubDate": pub_date}
    if draft is not None:
        made["draft"] = draft
    if comments:
        made["comments"] = [{"author": who, "date": when} for who, when in comments]
    return made


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

    def test_a_future_comment_date_fails_the_build(self):
        with self.assertRaises(AssertionError):
            published([entry("good", "2026-08-18", comments=[("jesse", "2026-08-20")])], now="2026-08-19")

    def test_a_comment_dated_before_its_post_fails_the_build(self):
        with self.assertRaises(AssertionError):
            published([entry("good", "2026-08-18", comments=[("jesse", "2026-08-17")])], now="2026-08-19")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class RealDevlogPostsTests(unittest.TestCase):
    def test_every_published_real_post_passes_future_guard_with_utc_today(self):
        """Run every real entry from src/content/devlog/ through publishedPosts using UTC today.
        A YYYY-MM-DD date is UTC midnight, so 'today' is valid once it is today in UTC."""
        entries = []
        for path in sorted((REPOSITORY_ROOT / "src" / "content" / "devlog").glob("*.md")):
            frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
            e = {"id": path.stem, "comments": []}
            in_comment_body = False
            for line in frontmatter.splitlines():
                stripped = line.strip()
                if in_comment_body:
                    if line.startswith("    ") or stripped == "":
                        continue
                    in_comment_body = False

                if line.startswith("#") or stripped.startswith("#"):
                    continue

                if line.startswith("pubDate:"):
                    v = line.split(":", 1)[1].strip()
                    e["pubDate"] = v[1:-1] if (v.startswith(("'", '"')) and v.endswith(("'", '"'))) else v
                elif line.startswith("draft:"):
                    e["draft"] = line.split(":", 1)[1].strip() == "true"
                elif stripped.startswith("- "):
                    e["comments"].append({})
                    rest = stripped[2:].strip()
                    if rest.startswith("author:"):
                        v = rest.split(":", 1)[1].strip()
                        e["comments"][-1]["author"] = v[1:-1] if (v.startswith(("'", '"')) and v.endswith(("'", '"'))) else v
                    elif rest.startswith("date:"):
                        v = rest.split(":", 1)[1].strip()
                        e["comments"][-1]["date"] = v[1:-1] if (v.startswith(("'", '"')) and v.endswith(("'", '"'))) else v
                    elif "body: |" in rest or (rest.startswith("body:") and not rest.startswith("#")):
                        in_comment_body = True
                elif stripped.startswith("author:") and e["comments"]:
                    v = stripped.split(":", 1)[1].strip()
                    e["comments"][-1]["author"] = v[1:-1] if (v.startswith(("'", '"')) and v.endswith(("'", '"'))) else v
                elif stripped.startswith("date:") and e["comments"]:
                    v = stripped.split(":", 1)[1].strip()
                    e["comments"][-1]["date"] = v[1:-1] if (v.startswith(("'", '"')) and v.endswith(("'", '"'))) else v
                elif "body: |" in stripped or (stripped.startswith("body:") and not stripped.startswith("#")):
                    in_comment_body = True
            entries.append(e)

        today = datetime.now(timezone.utc).date().isoformat()
        published_ids = published(entries, now=today)
        expected_ids = [e["id"] for e in entries if not e.get("draft", False)]
        self.assertTrue(expected_ids)
        for expected_id in expected_ids:
            self.assertIn(expected_id, published_ids)
        self.assertEqual(len(published_ids), len(expected_ids))


if __name__ == "__main__":
    unittest.main()

