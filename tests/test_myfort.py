"""The My Fort seed reader: what this page accepts, and what it says when it does not.

`src/lib/myfort.js` is not one of the fk_core twins — it has no Python counterpart, because it implements
no rule that exists twice. It is driven through node the same way the twins are, which is what keeps it
tested at all: tsconfig.json excludes `src/lib` from `astro check`, so these tests are its only safety net.

The two that matter most are the tolerance pair. Keep and this website ship on different cadences, and the
person holding the phone cannot redeploy the site — so an unknown field must not be refused, and a seed
from a newer format must be refused with a message that names the real remedy.
"""
import json
import re
import shutil
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

MYFORT_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "myfort.js").as_uri()

VALIDATE = (f'import {{ validateMyFortSeed }} from {json.dumps(MYFORT_MODULE)};' + STDIN_PRELUDE
            + "process.stdout.write(JSON.stringify(inputs.map((candidate) => {"
              "const result = validateMyFortSeed(candidate);"
              "return result.ok ? { ok: true } : { ok: false, reason: result.reason };"
              "})));")

FIXTURE = json.loads((REPOSITORY_ROOT / "tests" / "fixtures" / "myfort.sample.json").read_text(encoding="utf-8"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ValidateMyFortSeedTests(unittest.TestCase):
    def validate(self, candidates):
        return run_node(VALIDATE, candidates)

    def test_the_fixture_the_accessibility_gate_renders_is_acceptable(self):
        self.assertEqual(self.validate([FIXTURE]), [{"ok": True}])

    def test_it_accepts_an_additive_version_carrying_fields_it_does_not_know(self):
        """The tolerance the two release cadences depend on: Keep can add a field and the deployed page
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
        self.assertIn("Keep's own seed", result["reason"])

    def test_a_fortknight_profile_is_refused(self):
        [result] = self.validate([{"schemaVersion": 2, "activeWeightsId": "x", "weightsProfiles": {}}])
        self.assertFalse(result["ok"])
        self.assertIn("not a My Fort seed", result["reason"])

    def test_anything_that_is_not_a_document_is_refused(self):
        for result in self.validate([None, 7, "a string", ["an", "array"]]):
            self.assertFalse(result["ok"])
            self.assertIn("not a My Fort seed", result["reason"])

    def test_a_seed_with_no_version_is_refused_rather_than_guessed_at(self):
        [result] = self.validate([{"meta": {"format": "myfort"}, "days": [{"dayKey": "sun-a"}]}])
        self.assertFalse(result["ok"])
        self.assertIn("does not say which format", result["reason"])

    def test_a_seed_with_no_days_has_no_fortnight_to_show(self):
        for empty in ({"meta": {"format": "myfort", "version": 1}, "days": []},
                      {"meta": {"format": "myfort", "version": 1}, "days": [{"label": "no key"}]},
                      {"meta": {"format": "myfort", "version": 1}}):
            with self.subTest(document=sorted(empty)):
                [result] = self.validate([empty])
                self.assertFalse(result["ok"])
                self.assertIn("no days", result["reason"])

    def test_a_sparse_day_is_still_a_day(self):
        """A day needs a key to be a panel. Everything else on it degrades to nothing rather than refusing
        the whole fortnight — the line is what can be drawn, not what is complete."""
        sparse = {"meta": {"format": "myfort", "version": 1},
                  "days": [{"dayKey": "sun-a"}, {"dayKey": "mon-b", "meals": None, "blocks": None}]}
        self.assertEqual(self.validate([sparse]), [{"ok": True}])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ExportAgeTests(unittest.TestCase):
    def describe(self, seed, today):
        script = (f'import {{ describeExportAge }} from {json.dumps(MYFORT_MODULE)};' + STDIN_PRELUDE
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


class PageStyleScopingTests(unittest.TestCase):
    """The one thing about this page that no gate can see.

    Astro scopes a plain <style> by stamping the template's elements with a data-astro-cid attribute.
    Everything below #myFortBody is built with document.createElement, so it never carries that attribute
    and no scoped rule matches it: the year wheel renders 876x0 — invisible — and every size falls back to
    the browser's, which is the opposite of "readable across a room". The accessibility gate passes
    regardless, because axe checks the contrast of rendered text, not font sizes or zero-area divs. So this
    is asserted at the source, because there is nowhere else to assert it.
    """

    def test_the_pages_styles_are_global_because_its_dom_is_built_in_script(self):
        page = (REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "myfort.astro").read_text(encoding="utf-8")
        # Opening tags only, and only at the start of a line: the prose inside the block explains the trap
        # and names `<style>` while doing it.
        openings = re.findall(r"^\s*<style[^>]*>", page, flags=re.MULTILINE)
        self.assertTrue(openings, "the page should have a style block")
        for opening in openings:
            self.assertIn("is:global", opening, f"{opening.strip()} is scoped; its rules cannot reach the built DOM")

    def test_every_selector_it_makes_global_is_namespaced(self):
        """The cost of is:global is that these leak site-wide, so they all carry one prefix."""
        page = (REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "myfort.astro").read_text(encoding="utf-8")
        style = page.split("<style is:global>", 1)[1].split("</style>", 1)[0]
        selectors = [line.split("{", 1)[0].strip() for line in style.splitlines() if "{" in line]
        for selector in selectors:
            for part in selector.replace(",", " ").split():
                if part.startswith("."):
                    self.assertTrue(part.startswith(".myfort-"), f"{part} is global but not namespaced")
