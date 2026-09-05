"""The face nav, pinned at the source for what no gate can see.

This file holds the sprint *Focus in the Bar*’s pins: the fold boundary, the category mapping on
`faceNav()` — each stone’s path to its category key, and the labels against `data/categories.json` —
and the `focusCategoryKeys` keep reader against the keep fixtures. FaceNav’s own pins are here.

The fold in src/styles/faces.css between the flat bar and the ☰ menu must have no overlap and no gap
at 40rem. The layout gate’s shots run at 390px, 641px and 1440px, never at 640px, so a boundary where
both queries match — or neither does — is invisible to every gate; #25 measured a 495px header at
exactly 640px behind a green pipeline. Range syntax (`width >= 40rem` / `width < 40rem`) is the one
form that is an exact complement at every width, fractional ones included, so the pin is that each
fold is written that way and the legacy pair is gone. The studio twin in src/layouts/BaseLayout.astro
folds at 66rem the same way and is pinned here too — that is the layout the double-match was first
measured on. Comments are stripped before asserting: both files narrate the old pair in their prose.
"""
import json
import re
import shutil
import unittest

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

FACES_CSS = REPOSITORY_ROOT / "src" / "styles" / "faces.css"
BASE_LAYOUT = REPOSITORY_ROOT / "src" / "layouts" / "BaseLayout.astro"
FACE_NAV = REPOSITORY_ROOT / "src" / "components" / "FaceNav.astro"
FACE_LAYOUT = REPOSITORY_ROOT / "src" / "layouts" / "FaceLayout.astro"
KEEP_PAGE = REPOSITORY_ROOT / "src" / "pages" / "fortknight" / "keep.astro"

KEEP_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "keep.js").as_uri()
FACES_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "faces.js").as_uri()

SAMPLE_KEEP_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "keep.sample.json"
OTHER_HOUSEHOLD_KEEP_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "keep.other-household.json"
CATEGORIES_JSON_PATH = REPOSITORY_ROOT / "data" / "categories.json"

FOCUS_CATEGORY_KEYS = (
    f"import {{ focusCategoryKeys }} from {json.dumps(KEEP_MODULE)};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(inputs.map((candidate) => focusCategoryKeys(candidate))));"
)

FACE_NAV_ITEMS = (
    f"import {{ faceNav }} from {json.dumps(FACES_MODULE)};"
    + STDIN_PRELUDE
    + "process.stdout.write(JSON.stringify(faceNav()));"
)


def without_comments(source):
    """The source with every `/* … */` block removed, so a comment that quotes the old syntax is not a fold."""
    return re.sub(r"/\*.*?\*/", "", source, flags=re.S)


class FoldBoundaryTests(unittest.TestCase):
    """Each nav fold is one range-syntax pair, and the min/max pair that double-matched is gone."""

    def assert_folds_with_range_syntax(self, path, rem):
        code = without_comments(path.read_text(encoding="utf-8"))
        self.assertIn(f"(width >= {rem}rem)", code, path.name)
        self.assertIn(f"(width < {rem}rem)", code, path.name)
        self.assertNotIn(f"(min-width: {rem}rem)", code, path.name)
        self.assertNotIn(f"(max-width: {rem}rem)", code, path.name)

    def test_the_face_folds_at_40rem_with_range_syntax(self):
        self.assert_folds_with_range_syntax(FACES_CSS, 40)

    def test_the_studio_folds_at_66rem_with_range_syntax(self):
        self.assert_folds_with_range_syntax(BASE_LAYOUT, 66)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class FocusCategoryKeysTests(unittest.TestCase):
    """The focusCategoryKeys reader extracts season focus keys in order, defensively."""

    def read_keys(self, candidate):
        return run_node(FOCUS_CATEGORY_KEYS, [candidate])[0]

    def test_sample_fixture_focus_keys_in_order(self):
        fixture = json.loads(SAMPLE_KEEP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.read_keys(fixture), ["meals", "cleaning", "working", "health"])

    def test_other_household_fixture_focus_keys_in_order(self):
        fixture = json.loads(OTHER_HOUSEHOLD_KEEP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.read_keys(fixture), ["meals", "working"])

    def test_null_season_returns_empty_list(self):
        self.assertEqual(self.read_keys({"season": None}), [])

    def test_absent_season_returns_empty_list(self):
        self.assertEqual(self.read_keys({}), [])

    def test_season_without_focus_returns_empty_list(self):
        self.assertEqual(self.read_keys({"season": {}}), [])

    def test_focus_not_an_array_returns_empty_list(self):
        self.assertEqual(self.read_keys({"season": {"focus": "meals"}}), [])
        self.assertEqual(self.read_keys({"season": {"focus": 123}}), [])
        self.assertEqual(self.read_keys({"season": {"focus": {"key": "meals"}}}), [])

    def test_entries_without_key_are_skipped(self):
        self.assertEqual(
            self.read_keys({"season": {"focus": [{"label": "Meals"}, {"key": "cleaning"}]}}),
            ["cleaning"],
        )

    def test_non_string_keys_are_skipped(self):
        self.assertEqual(
            self.read_keys({
                "season": {
                    "focus": [
                        {"key": 123},
                        {"key": None},
                        {"key": ["meals"]},
                        {"key": "working"},
                    ]
                }
            }),
            ["working"],
        )

    def test_duplicate_keys_deduped_keeping_first_position(self):
        self.assertEqual(
            self.read_keys({
                "season": {
                    "focus": [
                        {"key": "meals"},
                        {"key": "working"},
                        {"key": "meals"},
                        {"key": "cleaning"},
                        {"key": "working"},
                    ]
                }
            }),
            ["meals", "working", "cleaning"],
        )


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class FaceNavMappingTests(unittest.TestCase):
    """faceNav() maps each stone entry to its category, pinned to data/categories.json."""

    def get_nav(self):
        return run_node(FACE_NAV_ITEMS, None)

    def test_paths_in_order_are_unchanged(self):
        items = self.get_nav()
        expected_paths = [
            "",
            "keep/",
            "forkknife/",
            "freshkeep/",
            "folkknowledge/",
            "fixknitt/",
            "foekiss/",
            "funknee/",
            "fretknot/",
            "achievements/",
        ]
        self.assertEqual([item["path"] for item in items], expected_paths)

    def test_overview_keep_and_achievements_have_no_category(self):
        items = self.get_nav()
        non_stone_paths = {"", "keep/", "achievements/"}
        for item in items:
            if item["path"] in non_stone_paths:
                self.assertNotIn("category", item, f"{item['path']} must carry no category")

    def test_no_entry_carries_short_label(self):
        items = self.get_nav()
        for item in items:
            self.assertNotIn("shortLabel", item, f"{item['path']} must not carry shortLabel")

    # Which stone is which category is the whole payload of #30, so it is pinned path by path — a
    # transposition of two stones would otherwise pass every set-based check and promote the wrong
    # stone into the bar (kimi, batch 2 code review, F1). The labels are pinned against the shipped
    # default in data/categories.json, the one place they are authored; faces.js carries a copy because
    # nothing under src/ reads data/ (CLAUDE.md).
    STONE_CATEGORY_KEY_BY_PATH = {
        "forkknife/": "meals",
        "freshkeep/": "cleaning",
        "folkknowledge/": "friends-family",
        "fixknitt/": "operations",
        "foekiss/": "spirituality-development",
        "funknee/": "health",
        "fretknot/": "working",
    }

    def test_each_stone_carries_its_own_category_and_the_shipped_label(self):
        categories_data = json.loads(CATEGORIES_JSON_PATH.read_text(encoding="utf-8"))
        shipped_labels = {key: categories_data["categories"][key]["label"] for key in categories_data["order"]}
        stone_items = [item for item in self.get_nav() if item["path"] in self.STONE_CATEGORY_KEY_BY_PATH]
        self.assertEqual([item["path"] for item in stone_items], list(self.STONE_CATEGORY_KEY_BY_PATH))
        self.assertEqual(
            {item["path"]: item["category"] for item in stone_items},
            {path: {"key": key, "label": shipped_labels[key]} for path, key in self.STONE_CATEGORY_KEY_BY_PATH.items()},
        )
        # The seven stones cover the seven categories exactly once each.
        self.assertEqual(sorted(self.STONE_CATEGORY_KEY_BY_PATH.values()), sorted(categories_data["order"]))


class FaceNavComponentTests(unittest.TestCase):
    """Source-level pins for FaceNav: imports, non-destructive reads, markup, and layout integration."""

    @classmethod
    def setUpClass(cls):
        cls.face_nav_source = FACE_NAV.read_text(encoding="utf-8")
        cls.face_layout_source = FACE_LAYOUT.read_text(encoding="utf-8")
        cls.keep_page_source = KEEP_PAGE.read_text(encoding="utf-8")

    def test_facenav_imports_and_event_listener(self):
        self.assertIn("loadKeep", self.face_nav_source)
        self.assertIn("validateKeep", self.face_nav_source)
        self.assertIn("focusCategoryKeys", self.face_nav_source)
        self.assertIn("KEEP_CHANGED_EVENT", self.face_nav_source)
        self.assertNotIn("readStoredKeep", self.face_nav_source)
        self.assertNotIn("clearKeep", self.face_nav_source)
        self.assertIn("addEventListener(KEEP_CHANGED_EVENT", self.face_nav_source)

    def test_facenav_emits_data_category_from_the_entry_and_the_default_has_seven(self):
        self.assertIn("data-category={item.category.key}", self.face_nav_source)
        categories_data = json.loads(CATEGORIES_JSON_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(categories_data["order"]), 7)

    def test_details_nav_peripheral_carries_no_open(self):
        self.assertIn('<details class="nav-peripheral">', self.face_nav_source)
        self.assertNotIn('<details class="nav-peripheral" open', self.face_nav_source)

    def test_summary_text_is_peripheral_with_nav_current_section_span(self):
        self.assertIn("Peripheral", self.face_nav_source)
        self.assertIn("nav-current-section", self.face_nav_source)
        self.assertIn(", current section", self.face_nav_source)

    def test_face_layout_renders_facenav_once_and_no_longer_maps_facenav(self):
        self.assertEqual(self.face_layout_source.count("<FaceNav"), 1)
        self.assertNotIn("faceNav().map", self.face_layout_source)

    def test_keep_page_imports_store_keep_and_no_longer_calls_set_item(self):
        self.assertIn("storeKeep", self.keep_page_source)
        self.assertNotIn("localStorage.setItem", self.keep_page_source)


if __name__ == "__main__":
    unittest.main()
