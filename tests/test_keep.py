"""The keep reader: what this page accepts, and what it says when it does not.

`src/lib/keep.js` is not one of the fk_core twins — it has no Python counterpart, because it implements
no rule that exists twice. It is driven through node the same way the twins are, which is what keeps it
tested at all: tsconfig.json excludes `src/lib` from `astro check`, so these tests are its only safety net.

The two that matter most are the tolerance pair. Focus Key and this website ship on different cadences, and the
person holding the phone cannot redeploy the site — so an unknown field must not be refused, and a seed
from a newer format must be refused with a message that names the real remedy.
"""
import json
import re
import shutil
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

KEEP_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "keep.js").as_uri()
KEEP_VIEW_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "keep-view.js").as_uri()
KEEP_ACCESS_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "keep-access.js").as_uri()

VALIDATE = (f'import {{ validateKeep }} from {json.dumps(KEEP_MODULE)};' + STDIN_PRELUDE
            + "process.stdout.write(JSON.stringify(inputs.map((candidate) => {"
              "const result = validateKeep(candidate);"
              "return result.ok ? { ok: true } : { ok: false, reason: result.reason };"
              "})));")

# Boot, driven with a stub localStorage: `inputs.stored` is what getItem returns (null = nothing stored),
# and the stub records whether removeItem was called, because the cleared/kept split IS whether storage
# was touched. The dynamic import runs after the stub exists, so the module never sees a real localStorage.
READ_STORED = (STDIN_PRELUDE
               + "globalThis.localStorage = {"
                 "  cleared: false,"
                 "  getItem() { return inputs.stored; },"
                 "  setItem() {},"
                 "  removeItem() { this.cleared = true; },"
                 "};"
                 f"const {{ readStoredKeep }} = await import({json.dumps(KEEP_ACCESS_MODULE)});"
                 "const result = readStoredKeep();"
                 "process.stdout.write(JSON.stringify({ status: result.status, reason: result.reason ?? null,"
                 "  hasSeed: Boolean(result.seed), cleared: globalThis.localStorage.cleared }));")

FIXTURE = json.loads((REPOSITORY_ROOT / "tests" / "fixtures" / "keep.sample.json").read_text(encoding="utf-8"))
OTHER_HOUSEHOLD_FIXTURE = json.loads(
    (REPOSITORY_ROOT / "tests" / "fixtures" / "keep.other-household.json").read_text(encoding="utf-8"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ValidateKeepTests(unittest.TestCase):
    def validate(self, candidates):
        return run_node(VALIDATE, candidates)

    def test_the_fixture_the_accessibility_gate_renders_is_acceptable(self):
        self.assertEqual(self.validate([FIXTURE]), [{"ok": True}])

    def test_the_other_household_fixture_is_acceptable(self):
        """The second invented household: different season ids, same contract. Its exemption in
        no_schedules.py is warranted by these tests reading it."""
        self.assertEqual(self.validate([OTHER_HOUSEHOLD_FIXTURE]), [{"ok": True}])

    def test_it_accepts_an_additive_version_carrying_fields_it_does_not_know(self):
        """The tolerance the two release cadences depend on: Focus Key can add a field and the deployed page
        keeps working, because a bump is reserved for a breaking change."""
        newer = json.loads(json.dumps(FIXTURE))
        newer["meta"]["somethingNew"] = "added later"
        newer["days"][0]["alsoNew"] = ["whatever"]
        newer["inventedSection"] = {"x": 1}
        self.assertEqual(self.validate([newer]), [{"ok": True}])

    def test_a_newer_format_is_refused_with_the_remedy_on_the_right_device(self):
        newer = json.loads(json.dumps(FIXTURE))
        newer["meta"]["version"] = 99
        [result] = self.validate([newer])
        self.assertFalse(result["ok"])
        self.assertIn("99", result["reason"])
        # The fix is a redeploy of the site, which the person holding the phone cannot do. Telling them to
        # re-export would send them round a loop that cannot help.
        self.assertIn("website needs updating", result["reason"])
        self.assertIn("the file is fine", result["reason"])

    def test_keeps_own_seed_is_refused_and_named(self):
        """The likeliest wrong file: the app's full seed rather than the small one it exports for the web."""
        [result] = self.validate([{"meta": {"schemaVersion": 5}, "calendar": [], "days": [], "tasks": []}])
        self.assertFalse(result["ok"])
        self.assertIn("Focus Key's own seed", result["reason"])

    def test_a_fortknight_profile_is_refused(self):
        [result] = self.validate([{"schemaVersion": 2, "activeWeightsId": "x", "weightsProfiles": {}}])
        self.assertFalse(result["ok"])
        self.assertIn("not a keep", result["reason"])

    def test_anything_that_is_not_a_document_is_refused(self):
        for result in self.validate([None, 7, "a string", ["an", "array"]]):
            self.assertFalse(result["ok"])
            self.assertIn("not a keep", result["reason"])

    def test_a_seed_with_no_version_is_refused_rather_than_guessed_at(self):
        [result] = self.validate([{"meta": {"format": "keep"}, "days": [{"dayKey": "sun-a"}]}])
        self.assertFalse(result["ok"])
        self.assertIn("does not say which format", result["reason"])

    def test_a_seed_with_no_days_has_no_fortnight_to_show(self):
        for empty in ({"meta": {"format": "keep", "version": 1}, "days": []},
                      {"meta": {"format": "keep", "version": 1}, "days": [{"label": "no key"}]},
                      {"meta": {"format": "keep", "version": 1}}):
            with self.subTest(document=sorted(empty)):
                [result] = self.validate([empty])
                self.assertFalse(result["ok"])
                self.assertIn("no days", result["reason"])

    def test_a_sparse_day_is_still_a_day(self):
        """A day needs a key to be a panel. Everything else on it degrades to nothing rather than refusing
        the whole fortnight — the line is what can be drawn, not what is complete."""
        sparse = {"meta": {"format": "keep", "version": 1},
                  "days": [{"dayKey": "sun-a"}, {"dayKey": "mon-b", "meals": None, "blocks": None}]}
        self.assertEqual(self.validate([sparse]), [{"ok": True}])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ExportAgeTests(unittest.TestCase):
    def describe(self, seed, today):
        script = (f'import {{ describeExportAge }} from {json.dumps(KEEP_MODULE)};' + STDIN_PRELUDE
                  + "process.stdout.write(JSON.stringify(describeExportAge(inputs.seed, inputs.today)));")
        return run_node(script, {"seed": seed, "today": today})

    def test_a_seed_exported_today_is_not_stale(self):
        seed = {"meta": {"exportedAt": "2026-08-27T18:00:00+00:00"}}
        self.assertEqual(self.describe(seed, "2026-08-27"), {"exportedDay": "2026-08-27", "stale": False})

    def test_an_older_seed_is_stale_without_counting_the_days(self):
        """Stale or not, never how many days — counting them is date arithmetic, and this page does none."""
        seed = {"meta": {"exportedAt": "2026-06-01T00:00:00+00:00"}}
        self.assertEqual(self.describe(seed, "2026-08-27"), {"exportedDay": "2026-06-01", "stale": True})

    def test_a_seed_without_a_timestamp_says_nothing(self):
        for seed in ({"meta": {}}, {"meta": {"exportedAt": "not a date"}}, {}):
            with self.subTest(seed=seed):
                self.assertIsNone(self.describe(seed, "2026-08-27"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SliceColourTests(unittest.TestCase):
    """The year wheel's palette: positional, not keyed to one household's season ids.

    The map this replaced ({ostara: …, fimbulsumar: …, …}) made every other household's wheel grey, and
    keep-view.js is driven through node because tsconfig.json excludes src/lib from astro check — these
    tests are its safety net, same as the validator's above.
    """

    def colours(self, slices):
        script = (f'import {{ sliceColours }} from {json.dumps(KEEP_VIEW_MODULE)};' + STDIN_PRELUDE
                  + "process.stdout.write(JSON.stringify(sliceColours(inputs)));")
        return run_node(script, slices)

    def test_the_palette_is_the_five_values_the_accessibility_gate_certified(self):
        """These are the old household map's values, kept verbatim: axe certified their contrast on the
        rendered page, so a palette change is an accessibility change."""
        script = (f'import {{ SEASON_PALETTE, NEUTRAL_SLICE_COLOUR }} from {json.dumps(KEEP_VIEW_MODULE)};'
                  + "process.stdout.write(JSON.stringify({ SEASON_PALETTE, NEUTRAL_SLICE_COLOUR }));")
        result = run_node(script, None)
        self.assertEqual(result["SEASON_PALETTE"],
                         ["#4d7c0f", "#c2410c", "#6d28d9", "#9f1239", "#1d4ed8"])
        self.assertEqual(result["NEUTRAL_SLICE_COLOUR"], "#78716c")

    def test_colours_follow_position_of_first_appearance_not_season_id(self):
        """The other household's season ids are none of the original map's keys, so a keyed map would paint
        all five grey. Positional assignment gives them the palette in slice order."""
        self.assertEqual(self.colours(OTHER_HOUSEHOLD_FIXTURE["year"]["slices"]),
                         ["#4d7c0f", "#c2410c", "#6d28d9", "#9f1239", "#1d4ed8"])

    def test_beyond_the_palette_is_the_neutral_colour(self):
        slices = [{"key": f"season-{position}", "name": f"Season {position}"} for position in range(7)]
        self.assertEqual(self.colours(slices),
                         ["#4d7c0f", "#c2410c", "#6d28d9", "#9f1239", "#1d4ed8", "#78716c", "#78716c"])

    def test_a_repeated_slice_keeps_its_first_colour(self):
        """First appearance, not each appearance: a slice that shows up twice does not spend a new colour."""
        slices = [{"key": "one", "name": "One"}, {"key": "two", "name": "Two"}, {"key": "one", "name": "One"}]
        self.assertEqual(self.colours(slices), ["#4d7c0f", "#c2410c", "#4d7c0f"])


class PageStyleScopingTests(unittest.TestCase):
    """The one thing about these pages that no gate can see.

    Astro scopes a plain <style> by stamping the template's elements with a data-astro-cid attribute.
    Everything src/lib/keep-view.js builds is made with document.createElement, so it never carries that
    attribute and no scoped rule matches it: the year wheel renders 876x0 — invisible — and every size falls
    back to the browser's, which is the opposite of "readable across a room". The accessibility gate passes
    regardless, because axe checks the contrast of rendered text, not font sizes or zero-area divs. So this
    is asserted at the source, because there is nowhere else to assert it.

    The styles live in src/components/KeepStyles.astro so every seed-fed page can carry them; the page is
    pinned to the component so a future edit cannot drop the styles while keeping the builders.
    """

    STYLES = REPOSITORY_ROOT / "src" / "components" / "KeepStyles.astro"

    def test_the_pages_styles_are_global_because_their_dom_is_built_in_script(self):
        component = self.STYLES.read_text(encoding="utf-8")
        # Opening tags only, and only at the start of a line: the prose inside the block explains the trap
        # and names `<style>` while doing it.
        openings = re.findall(r"^\s*<style[^>]*>", component, flags=re.MULTILINE)
        self.assertTrue(openings, "the component should have a style block")
        for opening in openings:
            self.assertIn("is:global", opening, f"{opening.strip()} is scoped; its rules cannot reach the built DOM")

    def test_every_selector_it_makes_global_is_namespaced(self):
        """The cost of is:global is that these leak site-wide, so they all carry one prefix."""
        component = self.STYLES.read_text(encoding="utf-8")
        style = component.split("<style is:global>", 1)[1].split("</style>", 1)[0]
        selectors = [line.split("{", 1)[0].strip() for line in style.splitlines() if "{" in line]
        for selector in selectors:
            for part in selector.replace(",", " ").split():
                if part.startswith("."):
                    self.assertTrue(part.startswith(".keep-"), f"{part} is global but not namespaced")

    def test_the_keep_page_carries_the_shared_styles(self):
        page = (REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "keep.astro").read_text(encoding="utf-8")
        self.assertIn("KeepStyles", page)


class SeedFedPageTests(unittest.TestCase):
    """The seed-fed FortKnight pages, pinned at the source for what no gate can see.

    Same warrant as PageStyleScopingTests: axe audits the rendered pages, but nothing rendered shows WHY an
    import must never appear — a date-resolution import would look up fine, build fine and audit fine, and
    still be wrong for half the seed's year (this repository's evaluator resolves Ostara and Fimbulsumar on
    sun-b; a keep arrives pre-joined by day key). So the rule "lookup only" is asserted here.
    """

    OVERVIEW = REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "index.astro"
    DAY_PAGE = REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "days" / "[dayKey].astro"

    def import_lines(self, path):
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("import")]

    def test_the_overview_boots_from_the_stored_seed(self):
        source = self.OVERVIEW.read_text(encoding="utf-8")
        self.assertIn("readStoredKeep", source)
        self.assertIn("KeepStyles", source)  # the grid is script-built; scoped styles cannot reach it

    def test_the_overview_offers_profile_creation_as_the_secondary_action(self):
        """Loading a seed is the primary action, but creating a profile is the only creation path on
        production while the questionnaires are placeholders — so it stays, after the seed's button-link."""
        source = self.OVERVIEW.read_text(encoding="utf-8")
        self.assertIn("createProfileButton", source)
        self.assertIn("user-settings", source)
        self.assertLess(source.index("Load your seed"), source.index("createProfileButton"))

    def test_the_seeded_grid_heading_is_not_a_second_h1(self):
        """The prerendered <h1>FortKnight</h1> is the document's one h1 in every state, seeded or not."""
        source = self.OVERVIEW.read_text(encoding="utf-8")
        self.assertIn('element("h2", null, "Your fortnight")', source)
        self.assertNotIn('element("h1"', source)

    def test_the_day_page_draws_with_the_shared_builders(self):
        source = self.DAY_PAGE.read_text(encoding="utf-8")
        self.assertIn("renderDayPanel", source)
        self.assertIn("readStoredKeep", source)
        self.assertIn("KeepStyles", source)

    def test_the_day_page_still_emits_the_fourteen_static_shells(self):
        source = self.DAY_PAGE.read_text(encoding="utf-8")
        self.assertIn("getStaticPaths", source)
        self.assertIn("DAY_KEY_ORDER", source)

    def test_neither_page_resolves_a_date(self):
        """Lookup only. DAY_KEY_ORDER is an ordering, not a calendar — it is allowed; anything that turns a
        date into a day key is not."""
        for page in (self.OVERVIEW, self.DAY_PAGE):
            for line in self.import_lines(page):
                self.assertNotIn("resolve", line.lower(), f"{page.name}: {line}")
            source = page.read_text(encoding="utf-8")
            for symbol in ("cycleIndexForDate", "seasonForDate", "dayKeyForDate", "seasonAnchorDate"):
                self.assertNotIn(symbol, source, f"{page.name} names {symbol}")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class StoredSeedBootTests(unittest.TestCase):
    """readStoredKeep(): the two ways a stored seed cannot be drawn, and why only one deletes.

    Unreadable storage is wreckage and is forgotten, or it sits there failing on every reload of a wall
    display. A readable seed the validator refuses is intact data — the sharpest case being a newer Focus
    Key export, whose remedy is a website deploy the person holding the phone cannot do — so it is KEPT,
    and the reason must say nothing was deleted, because the person cannot see storage to check.
    """

    def boot(self, stored):
        return run_node(READ_STORED, {"stored": stored})

    def test_nothing_stored_is_none_and_untouched(self):
        outcome = self.boot(None)
        self.assertEqual(outcome, {"status": "none", "reason": None, "hasSeed": False, "cleared": False})

    def test_a_valid_stored_seed_is_drawn_and_untouched(self):
        outcome = self.boot(json.dumps(FIXTURE))
        self.assertEqual(outcome["status"], "seed")
        self.assertTrue(outcome["hasSeed"])
        self.assertFalse(outcome["cleared"])

    def test_unreadable_storage_is_cleared(self):
        for stored in ("{not json", "null"):
            with self.subTest(stored=stored):
                outcome = self.boot(stored)
                self.assertEqual(outcome["status"], "cleared")
                self.assertTrue(outcome["cleared"])
                self.assertIn("forgotten", outcome["reason"])

    def test_a_seed_the_validator_refuses_is_kept_not_cleared(self):
        newer = json.loads(json.dumps(FIXTURE))
        newer["meta"]["version"] = 99
        for stored, fragment in ((json.dumps({"not": "a seed"}), "not a keep"),
                                 (json.dumps(newer), "the file is fine")):
            with self.subTest(fragment=fragment):
                outcome = self.boot(stored)
                self.assertEqual(outcome["status"], "kept")
                self.assertFalse(outcome["cleared"])
                self.assertIn(fragment, outcome["reason"])
                self.assertIn("nothing was deleted", outcome["reason"])

    def test_every_seed_fed_page_reports_the_kept_case(self):
        """The split only exists if the pages show it: each consumer must name "kept" alongside "cleared",
        or a kept seed would fall through to whatever the page's default does."""
        for page in ("index.astro", "keep.astro"):
            source = (REPOSITORY_ROOT / "src" / "pages" / "fortknight" / page).read_text(encoding="utf-8")
            self.assertIn('"kept"', source, page)
        day_page = (REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "days" / "[dayKey].astro").read_text(encoding="utf-8")
        self.assertIn('"kept"', day_page)
