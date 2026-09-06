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
import re
import shutil
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

ACHIEVEMENTS_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "games-achievements.js").as_uri()
CATALOG_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "games-catalog.js").as_uri()

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


STORAGE_STUB = """
const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => { store.set(key, String(value)); },
  removeItem: (key) => { store.delete(key); },
  clear: () => { store.clear(); },
};
"""

REFUSING_STORAGE_STUB = """
globalThis.localStorage = {
  getItem: () => { throw new Error("refused"); },
  setItem: () => { throw new Error("refused"); },
  removeItem: () => { throw new Error("refused"); },
};
"""


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class LoadGameUnlocksTests(unittest.TestCase):
    def test_missing_key_returns_empty_list(self):
        script = (
            f'import {{ loadGameUnlocks }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + STORAGE_STUB
            + 'process.stdout.write(JSON.stringify(loadGameUnlocks("pong")));'
        )
        self.assertEqual(run_node(script, []), [])

    def test_refusing_storage_returns_empty_list(self):
        script = (
            f'import {{ loadGameUnlocks }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + REFUSING_STORAGE_STUB
            + 'process.stdout.write(JSON.stringify(loadGameUnlocks("pong")));'
        )
        self.assertEqual(run_node(script, []), [])

    def test_valid_save_loads_unlocks(self):
        save = json.dumps({"unlocks": {"beat_cpu_easy": {"unlocked_at": 1_756_252_800}}})
        script = (
            f'import {{ loadGameUnlocks }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + STORAGE_STUB
            + f'store.set("beinsiculous.games.pong.achievements", {json.dumps(save)});'
            + 'const unlocks = loadGameUnlocks("pong").map(({ id, unlockedAt }) =>'
            + '  ({ id, unlockedAt: unlockedAt ? unlockedAt.toISOString() : null }));'
            + 'process.stdout.write(JSON.stringify(unlocks));'
        )
        result = run_node(script, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "beat_cpu_easy")
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class GameAchievementsPinsTests(unittest.TestCase):
    """The two pins: GAMES equals content collection order, and every committed manifest parses."""
    def test_games_slugs_equal_content_ids_in_order(self):
        script = (
            f'import {{ GAMES }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + 'process.stdout.write(JSON.stringify(GAMES));'
        )
        games_from_code = run_node(script, [])
        code_slugs = [game["slug"] for game in games_from_code]

        content_games_dir = REPOSITORY_ROOT / "src" / "content" / "games"
        content_games = []
        for file_path in content_games_dir.glob("*.md"):
            text = file_path.read_text(encoding="utf-8")
            frontmatter_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            self.assertIsNotNone(frontmatter_match, f"No frontmatter in {file_path}")
            frontmatter = frontmatter_match.group(1)
            order_match = re.search(r"^order:\s*(\d+)", frontmatter, re.MULTILINE)
            order = int(order_match.group(1)) if order_match else 0
            content_games.append({"slug": file_path.stem, "order": order})

        expected_slugs = [game["slug"] for game in sorted(content_games, key=lambda game: game["order"])]
        self.assertEqual(code_slugs, expected_slugs)

    def test_every_committed_manifest_parses_under_parse_game_catalog(self):
        content_games_dir = REPOSITORY_ROOT / "src" / "content" / "games"
        public_dir = REPOSITORY_ROOT / "public"

        for file_path in sorted(content_games_dir.glob("*.md")):
            text = file_path.read_text(encoding="utf-8")
            frontmatter_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            self.assertIsNotNone(frontmatter_match, f"No frontmatter in {file_path}")
            frontmatter = frontmatter_match.group(1)

            wasm_match = re.search(r"^wasm:\s*['\"]([^'\"]+)['\"]", frontmatter, re.MULTILINE)
            if not wasm_match:
                continue

            wasm_path = wasm_match.group(1)
            relative_dir = Path(wasm_path.lstrip("/")).parent
            manifest_path = public_dir / relative_dir / "achievements.json"

            self.assertTrue(manifest_path.is_file(), f"Manifest missing at {manifest_path}")
            manifest_text = manifest_path.read_text(encoding="utf-8")

            script = (
                f'import {{ parseGameCatalog }} from {json.dumps(CATALOG_MODULE)};'
                + STDIN_PRELUDE
                + 'try {\n'
                + '  const achievements = parseGameCatalog(inputs.text, inputs.slug);\n'
                + '  process.stdout.write(JSON.stringify({ ok: true, count: achievements.length }));\n'
                + '} catch (error) {\n'
                + '  process.stdout.write(JSON.stringify({ ok: false, error: error.message }));\n'
                + '}\n'
            )
            outcome = run_node(script, {"text": manifest_text, "slug": file_path.stem})
            self.assertTrue(outcome["ok"], f"Failed to parse {manifest_path}: {outcome.get('error')}")
            self.assertGreater(outcome["count"], 0)


if __name__ == "__main__":
    unittest.main()
