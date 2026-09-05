"""The prose rules of the build gate (scripts/lib/prose-check.mjs), driven through node the same way
tests/test_devlog_posts.py drives the devlog listing.

The rule, stated once here so a change to it has to come through this file: a word must not run
into an inline tag. Astro drops the newline + indentation between a word and an inline tag that sit
on different lines of the .astro source, so "it is a\n<a>proving ground</a>" ships as
"it is a<a>proving ground</a>". Whitespace on the same source line always survives.

The exclusions are the false-positive budget and are pinned here too: markup that is glued on
purpose (aria-hidden decoration, visually-hidden screen-reader text, empty elements) and ordinary
punctuation after a closing tag must stay quiet, or the gate gets loosened the first time it cries
wolf and stops guarding anything.

The second rule is typographic: the site's prose uses curly apostrophes, because Markdown content
gets them from smartypants and the .astro pages have to match or the two look different side by side
on the same page.
"""
import json
import unittest

from tests.helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

MODULE_URI = json.dumps((REPOSITORY_ROOT / "scripts" / "lib" / "prose-check.mjs").as_uri())

GLUE_SCRIPT = (
    f"import {{ findGluedBoundaries }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(inputs.pages.map((page) => findGluedBoundaries(page))));"
)


APOSTROPHE_SCRIPT = (
    f"import {{ findStraightApostrophes }} from {MODULE_URI};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(inputs.pages.map((page) => findStraightApostrophes(page))));"
)


def boundaries(html):
    return run_node(GLUE_SCRIPT, {"pages": [html]})[0]


def straight_apostrophes(html):
    return run_node(APOSTROPHE_SCRIPT, {"pages": [html]})[0]


class GlueRuleFires(unittest.TestCase):
    """The shapes the gate exists to catch."""

    def test_word_before_an_opening_link(self):
        found = boundaries('<p>it is a<a href="/engine/">proving ground</a></p>')
        self.assertEqual([boundary["kind"] for boundary in found], ["before-open"])

    def test_word_after_a_closing_tag(self):
        found = boundaries("<p>an escalating <em>chaos mode</em>that bends the rules</p>")
        self.assertEqual([boundary["kind"] for boundary in found], ["after-close"])

    def test_comma_before_an_opening_tag(self):
        # The engine crate list: "<code>ecs</code>,<code>renderer</code>" renders as "ecs,renderer".
        self.assertEqual(len(boundaries("<p><code>ecs</code>,<code>renderer</code></p>")), 1)

    def test_exclamation_and_question_marks_count(self):
        # These are the characters v1 of the rule whitelisted away, so the bug passed silently.
        self.assertEqual(len(boundaries("<p>really!<em>wow</em></p>")), 1)
        self.assertEqual(len(boundaries("<p>really?<em>wow</em></p>")), 1)

    def test_every_boundary_on_a_page_is_reported(self):
        found = boundaries("<p>run on<strong>Insiculous 2D</strong>and<em>six games</em></p>")
        self.assertEqual(len(found), 3)


class GlueRuleStaysQuiet(unittest.TestCase):
    """Markup that is glued on purpose, and ordinary prose."""

    def test_a_space_is_enough(self):
        self.assertEqual(boundaries('<p>it is a <a href="/engine/">proving ground</a> — real work</p>'), [])

    def test_aria_hidden_decoration(self):
        # The be_insiculous▌ wordmark cursor sits tight against the word by design.
        self.assertEqual(boundaries('<a class="wordmark">be_insiculous<span class="cursor" aria-hidden="true">▌</span></a>'), [])

    def test_visually_hidden_screen_reader_text(self):
        # "NEW" + " — Claude's post" reads as one phrase to a screen reader; a space would show.
        self.assertEqual(boundaries('<span class="status">NEW<span class="visually-hidden"> — still waiting</span></span>'), [])

    def test_empty_element(self):
        self.assertEqual(boundaries('<div class="day-label"><span>Sunday A<span class="day-tags"></span></span></div>'), [])

    def test_punctuation_after_a_closing_tag_is_normal_typography(self):
        self.assertEqual(boundaries('<p>see the <a href="/engine/">engine</a>, then the games.</p>'), [])
        self.assertEqual(boundaries('<p>see the <a href="/engine/">engine</a>.</p>'), [])

    def test_html_entity_before_a_tag(self):
        # Every entity ends in ";", which is in the rule's character class — the guard is what
        # keeps "&hellip;<a>" from reading as a glued word.
        self.assertEqual(boundaries('<p>and so on&hellip;<a href="/games/">the games</a></p>'), [])

    def test_script_and_style_bodies_are_not_prose(self):
        self.assertEqual(boundaries('<script type="module">const x = "a<a>b";</script>'), [])
        self.assertEqual(boundaries('<style>.a<b{color:red}</style>'), [])

    def test_html_comments_are_not_prose(self):
        self.assertEqual(boundaries("<!-- a<a>note</a> to self --><p>fine here</p>"), [])


class ApostropheRule(unittest.TestCase):
    """Straight apostrophes in prose, and the places they legitimately survive."""

    def test_a_straight_apostrophe_in_prose_is_reported(self):
        self.assertEqual(len(straight_apostrophes("<p>the engine's web export</p>")), 1)

    def test_a_curly_apostrophe_is_the_house_style(self):
        self.assertEqual(straight_apostrophes("<p>the engine\u2019s web export</p>"), [])

    def test_attributes_are_not_prose(self):
        self.assertEqual(straight_apostrophes("<p data-note=\"it's fine\">nothing here</p>"), [])

    def test_script_bodies_are_not_prose(self):
        self.assertEqual(straight_apostrophes("<script>const x = \"it's fine\";</script>"), [])


if __name__ == "__main__":
    unittest.main()
