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


TONG_KEY = "beinsiculous.games.tong.achievements"
PONG_KEY = "beinsiculous.games.pong.achievements"  # tong's former slug's key, which old bundles wrote

# Seeds the stub store from inputs.store ({key: raw string}) and prints loadGameUnlocks(inputs.slug).
LOAD_SEEDED = (
    f'import {{ loadGameUnlocks }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
    + STORAGE_STUB
    + STDIN_PRELUDE
    + 'for (const [key, value] of Object.entries(inputs.store)) store.set(key, value);'
    + 'const unlocks = loadGameUnlocks(inputs.slug).map(({ id, unlockedAt }) =>'
    + '  ({ id, unlockedAt: unlockedAt ? unlockedAt.toISOString() : null }));'
    + 'process.stdout.write(JSON.stringify(unlocks));'
)


def save_file(unlocks):
    """The engine's save file as the key holds it: {"unlocks": {id: {"unlocked_at": seconds}}}, as a string."""
    return json.dumps({"unlocks": {achievement_id: ({} if seconds is None else {"unlocked_at": seconds})
                                   for achievement_id, seconds in unlocks.items()}})


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class LoadGameUnlocksTests(unittest.TestCase):
    def load(self, store, slug="tong"):
        return run_node(LOAD_SEEDED, {"store": store, "slug": slug})

    def test_missing_key_returns_empty_list(self):
        self.assertEqual(self.load({}), [])

    def test_refusing_storage_returns_empty_list(self):
        script = (
            f'import {{ loadGameUnlocks }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + REFUSING_STORAGE_STUB
            + 'process.stdout.write(JSON.stringify(loadGameUnlocks("tong")));'
        )
        self.assertEqual(run_node(script, []), [])

    def test_valid_save_loads_unlocks(self):
        result = self.load({TONG_KEY: save_file({"beat_cpu_easy": 1_756_252_800})})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "beat_cpu_easy")
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))

    def test_unlocks_under_the_former_key_alone_are_read(self):
        """A browser that only ever ran the old bundle holds its unlocks under pong's key."""
        result = self.load({PONG_KEY: save_file({"beat_cpu_easy": 1_756_252_800})})
        self.assertEqual([entry["id"] for entry in result], ["beat_cpu_easy"])

    def test_the_former_slug_reads_its_own_key_alone(self):
        """The reader takes the current slug: "pong" has no row, so it is not answered with tong's key."""
        result = self.load({TONG_KEY: save_file({"win_normal": 1_756_252_800})}, slug="pong")
        self.assertEqual(result, [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class FormerKeyUnionTests(unittest.TestCase):
    """loadGameUnlocks for a renamed game: the in-memory union of its key and its former slug's key."""
    def load(self, store):
        return run_node(LOAD_SEEDED, {"store": store, "slug": "tong"})

    def test_the_two_keys_union_and_a_shared_id_keeps_its_earliest_date(self):
        result = self.load({
            TONG_KEY: save_file({"beat_cpu_easy": 1_756_339_200, "win_normal": 1_756_512_000}),
            PONG_KEY: save_file({"beat_cpu_easy": 1_756_252_800, "hat_trick": 1_756_425_600}),
        })
        self.assertEqual([entry["id"] for entry in result], ["beat_cpu_easy", "hat_trick", "win_normal"])
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))

    def test_the_earlier_date_wins_whichever_key_holds_it(self):
        result = self.load({
            TONG_KEY: save_file({"beat_cpu_easy": 1_756_252_800}),
            PONG_KEY: save_file({"beat_cpu_easy": 1_756_339_200}),
        })
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))

    def test_a_dated_record_supersedes_an_undated_one(self):
        for store in ({TONG_KEY: save_file({"win_normal": None}), PONG_KEY: save_file({"win_normal": 1_756_252_800})},
                      {TONG_KEY: save_file({"win_normal": 1_756_252_800}), PONG_KEY: save_file({"win_normal": None})}):
            with self.subTest(store=store):
                [result] = self.load(store)
                self.assertTrue(result["unlockedAt"].startswith("2025-08-27"))

    def test_undated_unlocks_sort_after_dated_ones_across_the_two_keys(self):
        result = self.load({TONG_KEY: save_file({"undated": None}), PONG_KEY: save_file({"dated": 1_756_252_800})})
        self.assertEqual([entry["id"] for entry in result], ["dated", "undated"])

    def test_a_proto_id_is_keyed_and_displayed(self):
        """serde stores `__proto__` as an ordinary id; an object-keyed union would swallow it."""
        result = self.load({TONG_KEY: '{"unlocks": {"__proto__": {"unlocked_at": 1756252800}}}',
                            PONG_KEY: save_file({"win_normal": 1_756_339_200})})
        self.assertEqual([entry["id"] for entry in result], ["__proto__", "win_normal"])

    def test_one_malformed_half_does_not_hide_the_other(self):
        for store in ({TONG_KEY: "{ not json", PONG_KEY: save_file({"win_normal": 1_756_252_800})},
                      {TONG_KEY: save_file({"win_normal": 1_756_252_800}), PONG_KEY: "{ not json"}):
            with self.subTest(store=store):
                self.assertEqual([entry["id"] for entry in self.load(store)], ["win_normal"])

    def test_clear_removes_both_keys_of_every_game(self):
        script = (
            f'import {{ GAMES, clearGameAchievements }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + STORAGE_STUB
            + 'for (const { slug, formerSlug } of GAMES) {'
            + '  store.set(`beinsiculous.games.${slug}.achievements`, "{}");'
            + '  if (formerSlug) store.set(`beinsiculous.games.${formerSlug}.achievements`, "{}");'
            + '}'
            + 'store.set("beinsiculous.achievements", "{}");'
            + 'clearGameAchievements();'
            + 'process.stdout.write(JSON.stringify([...store.keys()]));'
        )
        self.assertEqual(run_node(script, []), ["beinsiculous.achievements"])


# The slugs the six games were first published under. Once their entries were renamed nothing else
# on the tree knows these names, so a typo'd or dropped formerSlug would pass every other gate and
# silently orphan a browser's unlocks under a key nobody reads; the rows must carry exactly this set.
FORMER_SLUGS = {"pong", "breakout", "invaders", "snake", "asteroids", "frogger"}


def frontmatter_field(frontmatter, field):
    """A quoted (or bare) scalar frontmatter value, or None when the field is absent."""
    match = re.search(rf"^{field}:\s*['\"]?(.*?)['\"]?\s*$", frontmatter, re.MULTILINE)
    return match.group(1) if match else None


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class GameAchievementsPinsTests(unittest.TestCase):
    """The two pins: GAMES equals the content collection, and every committed manifest parses."""
    def test_games_rows_equal_content_entries_in_order(self):
        script = (
            f'import {{ GAMES }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + 'process.stdout.write(JSON.stringify(GAMES));'
        )
        games_from_code = run_node(script, [])

        content_games_dir = REPOSITORY_ROOT / "src" / "content" / "games"
        content_games = []
        for file_path in content_games_dir.glob("*.md"):
            text = file_path.read_text(encoding="utf-8")
            frontmatter_match = re.search(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            self.assertIsNotNone(frontmatter_match, f"No frontmatter in {file_path}")
            frontmatter = frontmatter_match.group(1)
            order_match = re.search(r"^order:\s*(\d+)", frontmatter, re.MULTILINE)
            order = int(order_match.group(1)) if order_match else 0
            row = {"slug": file_path.stem, "title": frontmatter_field(frontmatter, "title")}
            former_slug = frontmatter_field(frontmatter, "formerSlug")
            if former_slug is not None:
                row["formerSlug"] = former_slug
            content_games.append((order, row))

        expected_rows = [row for _, row in sorted(content_games, key=lambda pair: pair[0])]
        self.assertEqual(games_from_code, expected_rows)

    def test_every_former_slug_is_a_published_one_and_unique(self):
        script = (
            f'import {{ GAMES }} from {json.dumps(ACHIEVEMENTS_MODULE)};'
            + 'process.stdout.write(JSON.stringify(GAMES));'
        )
        former_slugs = [game["formerSlug"] for game in run_node(script, []) if "formerSlug" in game]
        self.assertEqual(set(former_slugs), FORMER_SLUGS)
        self.assertEqual(len(former_slugs), len(FORMER_SLUGS))

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
