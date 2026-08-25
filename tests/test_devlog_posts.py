"""Which devlog posts the site shows (src/lib/devlog-posts.js), driven through node the same way
tests/test_devlog_status.py drives the badge.

The rule, stated once here so a change to it has to come through this file: a post with
`draft: true` is held back — no listing entry, no page of its own, no feed item — and what is left
comes out newest first. Four call sites share the one function, so a regression here hides or
reveals a post in all four places at once, and a partial hide would ship as a silent 404.
"""
import json
import shutil
import unittest

from tests.helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

MODULE_URI = json.dumps((REPOSITORY_ROOT / "src" / "lib" / "devlog-posts.js").as_uri())

# Astro hands the function collection entries, so the fixtures are shaped like them: an id and a
# `data` object whose pubDate is a real Date.
PUBLISHED_SCRIPT = (
    f"import {{ publishedPosts }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "const entries = inputs.entries.map((entry) => ({ id: entry.id, data: { ...entry, pubDate: new Date(entry.pubDate) } }));"
    + "process.stdout.write(JSON.stringify(publishedPosts(entries).map((entry) => entry.id)));"
)


def published(entries):
    return run_node(PUBLISHED_SCRIPT, {"entries": entries})


def entry(identifier, pub_date, draft=None):
    made = {"id": identifier, "pubDate": pub_date}
    if draft is not None:
        made["draft"] = draft
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
        self.assertEqual(published(entries), ["newest", "middle", "oldest"])

    def test_holding_everything_leaves_an_empty_devlog_rather_than_an_error(self):
        """The listing, the feed and the game pages all render an empty list; none of them may throw."""
        self.assertEqual(published([entry("held", "2026-08-21", True)]), [])


if __name__ == "__main__":
    unittest.main()
