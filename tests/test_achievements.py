"""The site-wide achievements core: registry, store, prompt gating.

`src/lib/achievements.js` is not one of the fk_core twins — the achievement stores are the site's
own, with no Python counterpart. It is driven through node the same way the twins are (see
test_games_achievements.py's header: tsconfig.json excludes `src/lib` from `astro check`, so these
tests are its only safety net), with localStorage stubbed in-memory because the store and the
settings record are the module's whole input.

The first-achievement dialog (askProfileName) needs a real <dialog> and cannot run under node, so
the prompt's tests target the exported gating predicate shouldPromptForProfile() — the part that
must be provably right — plus maybePromptForProfile()'s promise that it never throws, dialog or no.
"""
import json
import shutil
import unittest

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

ACHIEVEMENTS_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "achievements.js").as_uri()

SITE_KEY = "beinsiculous.achievements"
PROMPT_KEY = "beinsiculous.achievements.profile-prompt"
SETTINGS_KEY = "fortknight.user-settings"

# An in-memory localStorage: the module under test reads the store, the settings record and the
# prompt flag through it, exactly as the browser would.
STORAGE_STUB = """
const store = new Map();
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => { store.set(key, String(value)); },
  removeItem: (key) => { store.delete(key); },
  clear: () => { store.clear(); },
};
"""

# Storage that refuses everything, as a privacy mode's does: every method throws.
REFUSING_STORAGE_STUB = """
globalThis.localStorage = {
  getItem: () => { throw new Error("refused"); },
  setItem: () => { throw new Error("refused"); },
  removeItem: () => { throw new Error("refused"); },
};
"""


def achievements_script(body, *symbols, storage_stub=STORAGE_STUB):
    names = ", ".join(symbols)
    return (f"import {{ {names} }} from {json.dumps(ACHIEVEMENTS_MODULE)};" + storage_stub
            + STDIN_PRELUDE + body)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class RegistryTests(unittest.TestCase):
    def registry(self):
        return run_node(achievements_script("process.stdout.write(JSON.stringify(ACHIEVEMENTS));", "ACHIEVEMENTS"), [])

    def test_ids_are_unique_and_types_are_valid(self):
        registry = self.registry()
        self.assertEqual([entry["id"] for entry in registry], ["player", "moved-in"])
        for entry in registry:
            self.assertIn(entry["type"], ("insiculous", "fortknight"))
            self.assertTrue(entry["title"])
            self.assertTrue(entry["description"])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class UnlockAchievementTests(unittest.TestCase):
    def test_unlocking_is_idempotent_and_records_unix_seconds(self):
        result = run_node(achievements_script(
            "const first = unlockAchievement('player');"
            "const second = unlockAchievement('player');"
            f"const stored = JSON.parse(store.get({json.dumps(SITE_KEY)}));"
            "process.stdout.write(JSON.stringify({ first, second, stored }));",
            "unlockAchievement"), [])
        self.assertTrue(result["first"])
        self.assertFalse(result["second"])  # already unlocked: not newly unlocked
        self.assertEqual(list(result["stored"]["unlocks"]), ["player"])
        unlocked_at = result["stored"]["unlocks"]["player"]["unlocked_at"]
        self.assertIsInstance(unlocked_at, int)
        self.assertGreater(unlocked_at, 0)

    def test_unknown_ids_are_refused_and_write_nothing(self):
        result = run_node(achievements_script(
            "const refused = unlockAchievement('not-a-real-id');"
            f"process.stdout.write(JSON.stringify({{ refused, stored: store.get({json.dumps(SITE_KEY)}) ?? null }}));",
            "unlockAchievement"), [])
        self.assertFalse(result["refused"])
        self.assertIsNone(result["stored"])

    def test_refusing_storage_means_not_newly_unlocked_never_an_exception(self):
        result = run_node(achievements_script(
            "process.stdout.write(JSON.stringify(unlockAchievement('player')));",
            "unlockAchievement", storage_stub=REFUSING_STORAGE_STUB), [])
        self.assertFalse(result)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class LoadSiteAchievementsTests(unittest.TestCase):
    def load(self, raw_values):
        """loadSiteAchievements() for each raw stored value (None = key absent), Dates as ISO or null."""
        return run_node(achievements_script(
            "const results = inputs.map((raw) => {"
            "  store.clear();"
            f"  if (raw !== null) store.set({json.dumps(SITE_KEY)}, raw);"
            "  return loadSiteAchievements().map(({ id, type, title, description, unlockedAt }) =>"
            "    ({ id, type, title, description, unlockedAt: unlockedAt ? unlockedAt.toISOString() : null }));"
            "});"
            "process.stdout.write(JSON.stringify(results));",
            "loadSiteAchievements"), raw_values)

    def test_malformed_storage_reads_as_empty(self):
        self.assertEqual(self.load([None, "not json {", '"text"', "7", '{"unlocks": ["foo"]}', '{"no_unlocks": {}}']),
                         [[], [], [], [], [], []])

    def test_dated_oldest_first_undated_last(self):
        [result] = self.load([json.dumps({"unlocks": {"later": {"unlocked_at": 1_756_339_200},
                                                     "epoch": {"unlocked_at": 0},
                                                     "earlier": {"unlocked_at": 1_756_252_800}}})])
        self.assertEqual([entry["id"] for entry in result], ["earlier", "later", "epoch"])
        self.assertTrue(result[0]["unlockedAt"].startswith("2025-08-27"))
        self.assertIsNone(result[2]["unlockedAt"])

    def test_out_of_range_timestamps_count_as_undated_matching_the_game_reader(self):
        """Milliseconds where seconds belong, fractions, strings: the game reader's rules, reused."""
        [result] = self.load([json.dumps({"unlocks": {"ms_bug": {"unlocked_at": 1_756_252_800_000},
                                                     "fractional": {"unlocked_at": 12.5},
                                                     "stringly": {"unlocked_at": "12"}}})])
        self.assertEqual([entry["unlockedAt"] for entry in result], [None, None, None])

    def test_known_ids_render_from_the_registry(self):
        [result] = self.load([json.dumps({"unlocks": {"moved-in": {"unlocked_at": 1_756_252_800}}})])
        self.assertEqual(result, [{"id": "moved-in", "type": "fortknight", "title": "Moved In",
                                   "description": "Loaded a keep.", "unlockedAt": "2025-08-27T00:00:00.000Z"}])

    def test_unknown_ids_still_render_prettified(self):
        [result] = self.load([json.dumps({"unlocks": {"future_feat": {"unlocked_at": 1_756_252_800}}})])
        self.assertEqual(result, [{"id": "future_feat", "type": "insiculous", "title": "Future Feat",
                                   "description": "", "unlockedAt": "2025-08-27T00:00:00.000Z"}])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class TotalAchievementCountTests(unittest.TestCase):
    def count(self, site_raw, game_saves):
        return run_node(achievements_script(
            f"if (inputs.site !== null) store.set({json.dumps(SITE_KEY)}, inputs.site);"
            "for (const [slug, raw] of Object.entries(inputs.games))"
            "  store.set(`beinsiculous.games.${slug}.achievements`, raw);"
            "process.stdout.write(JSON.stringify(totalAchievementCount()));",
            "totalAchievementCount"),
            {"site": site_raw, "games": game_saves})

    def test_counts_the_site_store_plus_every_game_save(self):
        site = json.dumps({"unlocks": {"player": {"unlocked_at": 1_756_252_800}, "moved-in": {"unlocked_at": 1_756_252_800}}})
        pong = json.dumps({"unlocks": {"beat_cpu_easy": {"unlocked_at": 1_756_252_800}}})
        self.assertEqual(self.count(site, {"pong": pong}), 3)

    def test_malformed_stores_contribute_nothing(self):
        self.assertEqual(self.count("not json {", {"snake": '{"unlocks": ["foo"]}'}), 0)


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ClearSiteAchievementsTests(unittest.TestCase):
    def test_clearing_removes_the_store_and_survives_refusal(self):
        result = run_node(achievements_script(
            f"store.set({json.dumps(SITE_KEY)}, inputs);"
            "clearSiteAchievements();"
            "process.stdout.write(JSON.stringify(loadSiteAchievements()));",
            "clearSiteAchievements", "loadSiteAchievements"),
            json.dumps({"unlocks": {"player": {"unlocked_at": 1_756_252_800}}}))
        self.assertEqual(result, [])
        # Refusing storage must not throw either (same rule as clearGameAchievements).
        run_node(achievements_script("clearSiteAchievements(); process.stdout.write('null');",
                                     "clearSiteAchievements", storage_stub=REFUSING_STORAGE_STUB), [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class PromptGatingTests(unittest.TestCase):
    """shouldPromptForProfile(): the dialog cannot run under node, so the gating predicate is the
    exported, tested surface — the conditions are where a bug would pester or silence people."""
    SAVED_PROFILE_SETTINGS = json.dumps({"schemaVersion": 3,
                                         "weightsProfiles": {"calm-forest-poet": {"id": "calm-forest-poet"}},
                                         "activeWeightsId": "calm-forest-poet"})
    ONE_SITE_UNLOCK = json.dumps({"unlocks": {"player": {"unlocked_at": 1_756_252_800}}})
    ONE_GAME_UNLOCK = json.dumps({"unlocks": {"beat_cpu_easy": {"unlocked_at": 1_756_252_800}}})

    def gate(self, site=None, game=None, settings=None, flag=None):
        return run_node(achievements_script(
            f"if (inputs.site) store.set({json.dumps(SITE_KEY)}, inputs.site);"
            f"if (inputs.game) store.set('beinsiculous.games.pong.achievements', inputs.game);"
            f"if (inputs.settings) store.set({json.dumps(SETTINGS_KEY)}, inputs.settings);"
            f"if (inputs.flag) store.set({json.dumps(PROMPT_KEY)}, inputs.flag);"
            "process.stdout.write(JSON.stringify(shouldPromptForProfile()));",
            "shouldPromptForProfile"),
            {"site": site, "game": game, "settings": settings, "flag": flag})

    def test_no_achievements_no_prompt(self):
        self.assertFalse(self.gate())

    def test_an_achievement_with_no_profile_and_no_flag_prompts(self):
        self.assertTrue(self.gate(site=self.ONE_SITE_UNLOCK))
        self.assertTrue(self.gate(game=self.ONE_GAME_UNLOCK))  # a game unlock counts too

    def test_a_saved_profile_means_no_prompt(self):
        self.assertFalse(self.gate(site=self.ONE_SITE_UNLOCK, settings=self.SAVED_PROFILE_SETTINGS))

    def test_a_settled_flag_means_no_prompt_created_or_dismissed(self):
        self.assertFalse(self.gate(site=self.ONE_SITE_UNLOCK, flag="created"))
        self.assertFalse(self.gate(site=self.ONE_SITE_UNLOCK, flag="dismissed"))

    def test_maybe_prompt_never_throws_even_with_no_dialog_available(self):
        """node has no document, so askProfileName cannot open: the promise must still resolve
        (false, flag unset) rather than reject — the popup is a nicety, never a failure."""
        result = run_node(achievements_script(
            f"store.set({json.dumps(SITE_KEY)}, inputs);"
            "const resolved = await maybePromptForProfile();"
            f"process.stdout.write(JSON.stringify({{ resolved, flag: store.get({json.dumps(PROMPT_KEY)}) ?? null }}));",
            "maybePromptForProfile"), self.ONE_SITE_UNLOCK)
        self.assertEqual(result, {"resolved": False, "flag": None})


# A minimal DOM for renderAchievementsBoard: the renderer uses document.createElement, textContent,
# className and append only (its header forbids innerHTML), so four properties per fake node suffice.
DOM_STUB = """
globalThis.document = {
  createElement: (tag) => ({
    tag,
    children: [],
    className: "",
    textContent: "",
    append(...nodes) { this.children.push(...nodes); },
  }),
};
const serialize = (node) => ({
  tag: node.tag,
  className: node.className,
  text: node.children.length ? "" : node.textContent,
  children: node.children.map(serialize),
});
"""


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class RenderAchievementsBoardTests(unittest.TestCase):
    """The board renderer under a stub DOM: group shape, the registry spine, and backward
    compatibility for the pages that show unlocked-only."""
    def render(self, options, site=None, game=None):
        return run_node(achievements_script(
            f"if (inputs.site) store.set({json.dumps(SITE_KEY)}, inputs.site);"
            "if (inputs.game) store.set('beinsiculous.games.pong.achievements', inputs.game);"
            "const container = document.createElement('div');"
            "const rendered = renderAchievementsBoard(container, inputs.options);"
            "process.stdout.write(JSON.stringify({ rendered, children: container.children.map(serialize) }));",
            "renderAchievementsBoard", storage_stub=STORAGE_STUB + DOM_STUB),
            {"options": options, "site": site, "game": game})

    @staticmethod
    def items(children):
        """The li (text, className) pairs of the one rendered group's ul."""
        list_element = next(child for child in children if child["tag"] == "ul")
        return [(item["text"], item["className"]) for item in list_element["children"]]

    def test_unlocked_only_is_the_default_and_carries_no_descriptions(self):
        """The other pages' boards must not change: no locked rows, no descriptions, no notes."""
        result = self.render({}, site=json.dumps({"unlocks": {"player": {"unlocked_at": 1_756_425_600}}}),
                             game=json.dumps({"unlocks": {"beat_cpu_easy": {"unlocked_at": 1_756_252_800}}}))
        self.assertTrue(result["rendered"])
        texts = [item["text"] for child in result["children"] if child["tag"] == "ul" for item in child["children"]]
        self.assertEqual(len(texts), 2)
        self.assertTrue(texts[0].startswith("Player — "))
        self.assertNotIn("Opened the games page", texts[0])
        self.assertTrue(all("Locked" not in text for text in texts))
        self.assertNotIn("p", [child["tag"] for child in result["children"]])

    def test_the_spine_renders_locked_entries_below_unlocked_with_descriptions(self):
        result = self.render({"types": ["insiculous"], "includeLocked": True},
                             site=json.dumps({"unlocks": {"secret_thing": {"unlocked_at": 1_756_425_600}}}))
        self.assertTrue(result["rendered"])
        [heading, _, *_] = result["children"]
        self.assertEqual(heading["text"], "Be Insiculous — 1 unlocked")
        [(unlocked_text, unlocked_class), (locked_text, locked_class)] = self.items(result["children"])
        # The unknown unlocked id renders prettified above the locked registry entry.
        self.assertTrue(unlocked_text.startswith("Secret Thing — "))
        self.assertEqual(unlocked_class, "")
        self.assertEqual(locked_text, "Player — Opened the games page. — Locked")
        self.assertEqual(locked_class, "achievement-locked")

    def test_the_spine_counts_only_unlocked_in_the_heading(self):
        result = self.render({"types": ["fortknight"], "includeLocked": True})
        self.assertTrue(result["rendered"])  # the spine always renders, fully locked included
        self.assertEqual(result["children"][0]["text"], "FortKnight — 0 unlocked")
        [(_, locked_class)] = self.items(result["children"])
        self.assertEqual(locked_class, "achievement-locked")

    def test_game_groups_gain_a_note_only_in_spine_mode(self):
        """The engine owns the locked list, so the board says where it lives instead of faking it."""
        game = json.dumps({"unlocks": {"beat_cpu_easy": {"unlocked_at": 1_756_252_800}}})
        with_note = self.render({"types": ["game"], "includeLocked": True}, game=game)
        self.assertEqual(with_note["children"][-1]["tag"], "p")
        self.assertEqual(with_note["children"][-1]["className"], "achievement-note")
        self.assertIn("full achievement list lives in the game", with_note["children"][-1]["text"])
        without_note = self.render({"types": ["game"]}, game=game)
        self.assertNotIn("p", [child["tag"] for child in without_note["children"]])


if __name__ == "__main__":
    unittest.main()
