"""The guard that keeps a person's schedule out of a public repository.

Two halves, and the second is the one that matters day to day: it must refuse a keep, and it must NOT
refuse the six committed files a naive marker would have caught. A guard that blocks every build gets
deleted, and then nothing is guarding anything.
"""
import json
import unittest
from pathlib import Path

# helpers puts scripts/ on sys.path; without it this module imports fk_core only when discovery happens to
# load an alphabetically earlier test first, which made the whole suite depend on file names.
from helpers import REPOSITORY_ROOT as CHECKOUT_ROOT
from fk_core.no_schedules import (
    ALLOWED_FIXTURES,
    REPOSITORY_ROOT,
    describe_schedule_document,
    find_schedule_documents,
)

# A pre-rename export (format "myfort"): the validator no longer reads this string, the guard
# catches it forever — old exports exist on the household's devices (F1, review 2026-08-28).
LEGACY_KEEP = {"meta": {"format": "myfort", "version": 1, "exportedAt": "2026-08-27T18:00:00+00:00"},
               "days": [], "season": None, "year": None}

KEEP_SEED = {"meta": {"schemaVersion": 5}, "calendar": [], "days": [], "tasks": [],
             "appointments": [], "meals": []}


class DescribeScheduleDocumentTests(unittest.TestCase):
    def test_it_names_a_my_fort_keep(self):
        self.assertIn("a keep", describe_schedule_document(LEGACY_KEEP))

    def test_a_current_format_keep_is_recognised(self):
        current = dict(LEGACY_KEEP, meta={"format": "keep", "version": 1})
        self.assertIn("a keep", describe_schedule_document(current))
        self.assertIn('"keep"', describe_schedule_document(current))

    def test_it_names_a_champion_keep(self):
        self.assertIn("Fort Knight champion keep", describe_schedule_document(KEEP_SEED))

    def test_a_bare_tasks_or_days_key_is_not_a_schedule(self):
        """The subtlety the guard exists around: data/questionnaire.json carries `tasks`, days.json carries
        `days`, and the built bundle carries `days` and `meta`. Marking on any one of those would refuse
        six committed files and block every build."""
        for harmless in ({"tasks": []}, {"days": []}, {"meta": {}, "days": []},
                         {"meta": {}, "days": [], "tasks": []},          # three of the four is not enough
                         {"calendar": [], "days": [], "tasks": []}):     # nor is a different three
            with self.subTest(document=sorted(harmless)):
                self.assertIsNone(describe_schedule_document(harmless))

    def test_it_ignores_what_is_not_an_object(self):
        for value in ([], "a string", 7, None):
            self.assertIsNone(describe_schedule_document(value))


class FindScheduleDocumentsTests(unittest.TestCase):
    def test_this_repository_holds_nobody_s_schedule(self):
        """The claim CLAUDE.md, README.md and docs/thesis.md all make, checked rather than asserted."""
        self.assertEqual(find_schedule_documents(), [])

    def test_it_finds_a_keep_wherever_it_is_dropped(self):
        import tempfile

        for relative in ("public/myfort.json", "data/whatever.json", "stray.json",
                         "src/pages/fortknight/keep.json"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                planted = Path(directory) / relative
                planted.parent.mkdir(parents=True, exist_ok=True)
                planted.write_text(json.dumps(LEGACY_KEEP), encoding="utf-8")
                found = find_schedule_documents(directory)
                self.assertEqual([path for path, _ in found], [relative])

    def test_it_does_not_walk_generated_or_vendored_trees(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            for relative in ("dist/myfort.json", "node_modules/pkg/myfort.json", "source/myfort.json"):
                planted = Path(directory) / relative
                planted.parent.mkdir(parents=True, exist_ok=True)
                planted.write_text(json.dumps(LEGACY_KEEP), encoding="utf-8")
            self.assertEqual(find_schedule_documents(directory), [])

    def test_exactly_the_two_invented_fixtures_are_exempt_and_they_exist(self):
        """An exemption for a file that does not exist is a pre-approved hole at exactly the path a real
        export would be dropped. So the list is named outright, and every entry is on disk."""
        self.assertEqual(ALLOWED_FIXTURES, {"tests/fixtures/keep.sample.json",
                                            "tests/fixtures/keep.other-household.json"})
        for relative in ALLOWED_FIXTURES:
            self.assertTrue((CHECKOUT_ROOT / relative).is_file(), f"{relative} is exempt but missing")

    def test_both_fixtures_are_read_by_the_gate_that_justifies_them(self):
        """The exemptions' whole warrant is that the accessibility gate renders the keep-fed pages
        from each fixture — the sample pass sees fourteen real panels instead of an empty file
        picker, and the other-household pass certifies the positional palette's contrast on a keep
        that is not the original household's. If nothing reads one, its exemption is a hole with a
        story attached."""
        harness = (CHECKOUT_ROOT / "scripts" / "a11y-check.mjs").read_text(encoding="utf-8")
        self.assertIn("keep.sample.json", harness)
        self.assertIn("keep.other-household.json", harness)

    def test_the_other_household_fixture_is_read_by_the_tests_that_justify_it(self):
        """The second fixture also earns its exemption in the rendering tests, which need a keep
        whose season ids are not the ones the original colour map was keyed to. Same rule — an
        exemption nothing reads is a hole with a story attached."""
        rendering_tests = (CHECKOUT_ROOT / "tests" / "test_keep.py").read_text(encoding="utf-8")
        self.assertIn("keep.other-household.json", rendering_tests)

    def test_the_exempt_fixtures_are_invented_rather_than_anybody_s(self):
        """Each is a keep by shape — that is the point — so what makes it safe is that its contents
        are made up. Pinned on the marker names, which no real export would carry."""
        for relative in ALLOWED_FIXTURES:
            fixture = json.loads((CHECKOUT_ROOT / relative).read_text(encoding="utf-8"))
            self.assertIsNotNone(describe_schedule_document(fixture))
            text = json.dumps(fixture)
            self.assertIn("Example", text, f"{relative} should be obviously invented")

    def test_any_other_keep_under_tests_is_still_a_keep(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            planted = Path(directory) / "tests/fixtures/somebody-elses.json"
            planted.parent.mkdir(parents=True, exist_ok=True)
            planted.write_text(json.dumps(LEGACY_KEEP), encoding="utf-8")
            self.assertEqual([path for path, _ in find_schedule_documents(directory)],
                             ["tests/fixtures/somebody-elses.json"])

    def test_a_keep_it_cannot_read_is_reported_rather_than_skipped(self):
        """The guard's only job is never to be quietly wrong. A UTF-16 or malformed file cannot be shown
        NOT to be a schedule, so it is named instead of passed over."""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken.json").write_text("{not json", encoding="utf-8")
            (Path(directory) / "utf16.json").write_bytes(json.dumps(LEGACY_KEEP).encode("utf-16"))
            found = dict(find_schedule_documents(directory))
            self.assertEqual(sorted(found), ["broken.json", "utf16.json"])
            for reason in found.values():
                self.assertIn("unreadable JSON", reason)

    def test_a_jsonc_config_is_not_reported_as_unreadable(self):
        """tsconfig.json is JSON with comments and has never parsed as JSON. Reporting it would have made
        this guard fail every build on the day it landed — which is how guards get deleted."""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "tsconfig.json").write_text('{\n  // a comment\n  "extends": "x"\n}',
                                                           encoding="utf-8")
            self.assertEqual(find_schedule_documents(directory), [])

    def test_the_real_tsconfig_is_the_reason_that_exemption_exists(self):
        """Pinned against the checkout rather than a fixture: if tsconfig ever becomes plain JSON the
        exemption is dead weight, and if another JSONC config appears this test is where it surfaces."""
        self.assertIn("tsconfig.json", {path.name for path in CHECKOUT_ROOT.glob("*.json")})

    def test_a_keep_with_a_byte_order_mark_is_still_caught(self):
        """Notepad writes one by default, and json.loads refuses a BOM outright — so reading as plain
        utf-8 would have skipped a real export in silence."""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "keep.json").write_text(json.dumps(LEGACY_KEEP), encoding="utf-8-sig")
            self.assertEqual([reason for _, reason in find_schedule_documents(directory)],
                             ["a keep (meta.format is \"myfort\")"])

    def test_it_does_not_depend_on_the_file_being_named_tidily(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "SEED.JSON").write_text(json.dumps(LEGACY_KEEP), encoding="utf-8")
            self.assertEqual([path for path, _ in find_schedule_documents(directory)], ["SEED.JSON"])

    def test_the_repository_root_it_defaults_to_is_the_checkout(self):
        self.assertEqual(REPOSITORY_ROOT, CHECKOUT_ROOT)
        self.assertTrue((REPOSITORY_ROOT / "package.json").is_file())
