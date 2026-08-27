"""The /profile/ achievements board's reader: what it accepts from a game's save file, and what it refuses.

`src/lib/games-achievements.js` is not one of the fk_core twins — the engine's achievement save format
(`{"unlocks": {"<id>": {"unlocked_at": <unix seconds>}}}`, beinsiculous/insiculous_2d#17) has no Python
counterpart here. It is driven through node the same way the twins are, which is what keeps it tested at
all: tsconfig.json excludes `src/lib` from `astro check`, so these tests are its only safety net.

The shape checks matter because the writer lives in another repository on another cadence: a save that
drifts malformed must degrade to "nothing readable" or "undated", never to "Invalid Date", a 1970 unlock,
or nonsense numeric ids on the board.
"""
import json
import shutil
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

ACHIEVEMENTS_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "games-achievements.js").as_uri()

UNLOCKS = (f'import {{ unlocksFromSaveFile }} from {json.dumps(ACHIEVEMENTS_MODULE)};' + STDIN_PRELUDE
           + "process.stdout.write(JSON.stringify(inputs.map((saveFile) =>"
             "unlocksFromSaveFile(saveFile).map(({ id, unlockedAt }) =>"
             "({ id, unlockedAt: unlockedAt ? unlockedAt.toISOString() : null })))));")

TITLES = (f'import {{ achievementTitleFromId }} from {json.dumps(ACHIEVEMENTS_MODULE)};' + STDIN_PRELUDE
          + "process.stdout.write(JSON.stringify(inputs.map(achievementTitleFromId)));")


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class UnlocksFromSaveFileTests(unittest.TestCase):
    def unlocks(self, save_files):
        return run_node(UNLOCKS, save_files)

    def test_a_valid_save_file_orders_unlocks_oldest_first(self):
        [result] = self.unlocks([{"unlocks": {"later": {"unlocked_at": 1_756_339_200},
                                              "earlier": {"unlocked_at": 1_756_252_800}}}])
        self.assertEqual([entry["id"] for entry in result], ["earlier", "later"])
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))

    def test_an_unlocks_array_is_refused_not_rendered_as_numeric_ids(self):
        """{"unlocks": ["foo"]} passes a bare typeof-object check and would render an achievement "0"."""
        [result] = self.unlocks([{"unlocks": ["foo", "bar"]}])
        self.assertEqual(result, [])

    def test_non_object_save_files_yield_nothing(self):
        self.assertEqual(self.unlocks([None, "text", 7, ["unlocks"], {"no_unlocks": {}}]), [[], [], [], [], []])

    def test_out_of_range_timestamps_count_as_undated_never_invalid_date(self):
        """The likeliest engine-side bug: milliseconds written where seconds belong. Finite, so a bare
        isFinite check would build an invalid Date and the board would print "Invalid Date"."""
        [result] = self.unlocks([{"unlocks": {"ms_bug": {"unlocked_at": 1_756_252_800_000},
                                              "fractional": {"unlocked_at": 12.5},
                                              "stringly": {"unlocked_at": "12"}}}])
        self.assertEqual([entry["unlockedAt"] for entry in result], [None, None, None])

    def test_epoch_and_negative_timestamps_are_undated_and_sort_last(self):
        """Zero or negative seconds are not real unlock dates — and an undated unlock must not claim
        the "oldest" slot by sorting as 1970."""
        [result] = self.unlocks([{"unlocks": {"epoch": {"unlocked_at": 0},
                                              "negative": {"unlocked_at": -5},
                                              "real": {"unlocked_at": 1_756_252_800}}}])
        self.assertEqual(result[0]["id"], "real")
        self.assertEqual([entry["unlockedAt"] for entry in result[1:]], [None, None])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class AchievementTitleTests(unittest.TestCase):
    def test_ids_prettify_across_both_separator_styles(self):
        self.assertEqual(run_node(TITLES, ["beat_cpu_easy", "win-normal", "solo"]),
                         ["Beat Cpu Easy", "Win Normal", "Solo"])


if __name__ == "__main__":
    unittest.main()
