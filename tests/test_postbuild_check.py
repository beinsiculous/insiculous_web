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

The third is the redirect rule (scripts/lib/redirects-check.mjs, check 9): a renamed game's former
paths each redirect to the page under its new slug with the one expected code, and no rule in
_redirects sends a visitor to something dist/ does not hold.
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


REDIRECTS_MODULE_URI = json.dumps((REPOSITORY_ROOT / "scripts" / "lib" / "redirects-check.mjs").as_uri())

# isFile answers from inputs.files, the dist/-relative paths the fake dist/ holds.
REDIRECTS_SCRIPT = (
    f"import {{ findRedirectProblems }} from {REDIRECTS_MODULE_URI};"
    + STDIN_PRELUDE
    + "const files = new Set(inputs.files);"
    + "process.stdout.write(JSON.stringify(findRedirectProblems({ text: inputs.text,"
    + "  renamedGames: inputs.renamedGames, expectedCode: inputs.expectedCode,"
    + "  isFile: (relativePath) => files.has(relativePath) })));"
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


RENAMED = {"entry": "src/content/games/new-name.md", "slug": "new-name", "formerSlug": "old-name",
           "sections": ["games", "playground"]}
RENAMED_WITHOUT_EDITOR = {**RENAMED, "sections": ["games"]}
BUILT_PAGES = ["games/new-name/index.html", "playground/new-name/index.html"]
RENAMED_LINES = """# a comment, then a blank line

/games/old-name/ /games/new-name/ 302
/games/old-name /games/new-name/ 302
/playground/old-name/ /playground/new-name/ 302
/playground/old-name /playground/new-name/ 302
"""


def redirect_problems(text, renamed_games=(RENAMED,), files=BUILT_PAGES, expected_code=302):
    return run_node(REDIRECTS_SCRIPT, {"text": text, "renamedGames": list(renamed_games),
                                       "files": list(files), "expectedCode": expected_code})


class RedirectRule(unittest.TestCase):
    """Check 9: the four lines a renamed game owes, and destinations that resolve in dist/."""

    def test_the_four_lines_with_resolving_destinations_pass(self):
        self.assertEqual(redirect_problems(RENAMED_LINES), [])

    def test_a_missing_line_is_reported(self):
        text = RENAMED_LINES.replace("/playground/old-name /playground/new-name/ 302\n", "")
        [problem] = redirect_problems(text)
        self.assertIn('needs the line "/playground/old-name /playground/new-name/ 302"', problem)

    def test_a_permanent_code_fails_while_the_expected_code_is_temporary(self):
        [problem] = redirect_problems(RENAMED_LINES.replace("/games/old-name/ /games/new-name/ 302", "/games/old-name/ /games/new-name/ 301"))
        self.assertIn('should read "/games/old-name/ /games/new-name/ 302"', problem)

    def test_a_line_without_a_code_fails_for_a_renamed_game(self):
        [problem] = redirect_problems(RENAMED_LINES.replace("/games/old-name /games/new-name/ 302", "/games/old-name /games/new-name/"))
        self.assertIn('should read "/games/old-name /games/new-name/ 302"', problem)

    def test_a_destination_with_no_page_in_dist_is_reported(self):
        problems = redirect_problems(RENAMED_LINES, files=["games/new-name/index.html"])
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("has no page or file in dist/" in problem for problem in problems))

    def test_a_slashless_destination_resolves_only_as_a_file(self):
        self.assertEqual(redirect_problems("/old.png /images/new.png 302\n", renamed_games=(),
                                           files=["images/new.png"]), [])
        [problem] = redirect_problems("/old /games/new-name 302\n", renamed_games=())
        self.assertIn("has no page or file in dist/", problem)

    def test_an_external_destination_cannot_resolve(self):
        [problem] = redirect_problems("/old https://example.com/ 302\n", renamed_games=())
        self.assertIn("has no page or file in dist/", problem)

    def test_a_repeated_source_is_reported(self):
        [problem] = redirect_problems(RENAMED_LINES + "/games/old-name/ /games/new-name/ 302\n")
        self.assertIn("repeats the source /games/old-name/", problem)

    def test_a_malformed_line_is_reported(self):
        [problem] = redirect_problems(RENAMED_LINES + "/games/lonely\n")
        self.assertIn("is not", problem)

    def test_a_game_without_an_editor_owes_only_its_page_lines(self):
        page_lines = "/games/old-name/ /games/new-name/ 302\n/games/old-name /games/new-name/ 302\n"
        self.assertEqual(redirect_problems(page_lines, renamed_games=(RENAMED_WITHOUT_EDITOR,),
                                           files=["games/new-name/index.html"]), [])

    def test_a_splat_under_the_former_slug_is_reported(self):
        [problem] = redirect_problems(RENAMED_LINES + "/playground/old-name/* /playground/new-name/ 302\n")
        self.assertIn("is a splat under the former slug 'old-name'", problem)
        [problem] = redirect_problems(RENAMED_LINES + "/games/old-name/:version /games/new-name/ 302\n")
        self.assertIn("is a splat under the former slug 'old-name'", problem)
        [problem] = redirect_problems(RENAMED_LINES + "/playground/old-name* /playground/new-name/ 302\n")
        self.assertIn("is a splat under the former slug 'old-name'", problem)

    def test_a_splat_under_a_slug_that_merely_shares_the_prefix_is_not_the_former_slug(self):
        self.assertEqual(redirect_problems(RENAMED_LINES + "/games/old-name-two/* /games/new-name/ 302\n"), [])

    def test_a_file_with_no_renamed_games_and_no_rules_passes(self):
        self.assertEqual(redirect_problems("# nothing renamed yet\n", renamed_games=()), [])


if __name__ == "__main__":
    unittest.main()
