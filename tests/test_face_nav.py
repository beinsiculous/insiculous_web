"""The face nav, pinned at the source for what no gate can see.

Today this file holds the fold boundary; it grows with the sprint *Focus in the Bar* (the category
mapping and the focus reader join in later batches).

The fold in src/styles/faces.css between the flat bar and the ☰ menu must have no overlap and no gap
at 40rem. The layout gate’s shots run at 390px, 641px and 1440px, never at 640px, so a boundary where
both queries match — or neither does — is invisible to every gate; #25 measured a 495px header at
exactly 640px behind a green pipeline. Range syntax (`width >= 40rem` / `width < 40rem`) is the one
form that is an exact complement at every width, fractional ones included, so the pin is that each
fold is written that way and the legacy pair is gone. The studio twin in src/layouts/BaseLayout.astro
folds at 66rem the same way and is pinned here too — that is the layout the double-match was first
measured on. Comments are stripped before asserting: both files narrate the old pair in their prose.
"""
import re
import unittest

from helpers import REPOSITORY_ROOT

FACES_CSS = REPOSITORY_ROOT / "src" / "styles" / "faces.css"
BASE_LAYOUT = REPOSITORY_ROOT / "src" / "layouts" / "BaseLayout.astro"


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


if __name__ == "__main__":
    unittest.main()
