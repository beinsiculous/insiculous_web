"""Tests for games-catalog.js and games-catalog-files.js."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

CATALOG_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "games-catalog.js").as_uri()
CATALOG_FILES_MODULE = (REPOSITORY_ROOT / "src" / "lib" / "games-catalog-files.js").as_uri()


def parse_catalog_node(text, slug):
    script = (
        f'import {{ parseGameCatalog }} from {json.dumps(CATALOG_MODULE)};\n'
        + STDIN_PRELUDE
        + 'try {\n'
        + '  const result = parseGameCatalog(inputs.text, inputs.slug);\n'
        + '  process.stdout.write(JSON.stringify({ ok: true, result }));\n'
        + '} catch (error) {\n'
        + '  process.stdout.write(JSON.stringify({ ok: false, error: error.message }));\n'
        + '}\n'
    )
    return run_node(script, {"text": text, "slug": slug})


def read_catalogs_node(games, public_directory):
    script = (
        f'import {{ readGameCatalogs }} from {json.dumps(CATALOG_FILES_MODULE)};\n'
        + STDIN_PRELUDE
        + 'try {\n'
        + '  const result = readGameCatalogs(inputs.games, inputs.publicDirectory);\n'
        + '  process.stdout.write(JSON.stringify({ ok: true, result }));\n'
        + '} catch (error) {\n'
        + '  process.stdout.write(JSON.stringify({ ok: false, error: error.message }));\n'
        + '}\n'
    )
    return run_node(script, {"games": games, "publicDirectory": str(public_directory)})


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ParseGameCatalogTests(unittest.TestCase):
    def test_accepts_valid_manifest(self):
        manifest = [
            {"id": "win", "name": "Winner", "description": "Win the game.", "hidden": False},
            {"id": "secret", "name": "Secret", "description": "Find the secret.", "hidden": True},
        ]
        outcome = parse_catalog_node(json.dumps(manifest), "pong")
        self.assertTrue(outcome["ok"])
        self.assertEqual(outcome["result"], manifest)

    def test_refuses_invalid_json_naming_slug(self):
        outcome = parse_catalog_node("{ not json", "pong")
        self.assertFalse(outcome["ok"])
        self.assertIn("pong", outcome["error"])

    def test_refuses_non_array_naming_slug(self):
        for bad in [{}, "text", 123, True, None]:
            outcome = parse_catalog_node(json.dumps(bad), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_empty_array_naming_slug(self):
        outcome = parse_catalog_node("[]", "pong")
        self.assertFalse(outcome["ok"])
        self.assertIn("pong", outcome["error"])

    def test_refuses_non_object_entry_naming_slug(self):
        for bad_entry in ["not-an-object", 42, None, [1, 2]]:
            outcome = parse_catalog_node(json.dumps([bad_entry]), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_missing_or_empty_id_naming_slug(self):
        for bad_id in [None, "", "   ", 123, True]:
            entry = {"id": bad_id, "name": "Name", "description": "Desc", "hidden": False}
            outcome = parse_catalog_node(json.dumps([entry]), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_missing_or_empty_name_naming_slug(self):
        for bad_name in [None, "", "   ", 123, True]:
            entry = {"id": "win", "name": bad_name, "description": "Desc", "hidden": False}
            outcome = parse_catalog_node(json.dumps([entry]), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_missing_or_non_string_description_naming_slug(self):
        for bad_desc in [None, 123, True, []]:
            entry = {"id": "win", "name": "Name", "description": bad_desc, "hidden": False}
            outcome = parse_catalog_node(json.dumps([entry]), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_non_boolean_hidden_naming_slug(self):
        for bad_hidden in [None, "false", 0, 1, []]:
            entry = {"id": "win", "name": "Name", "description": "Desc", "hidden": bad_hidden}
            outcome = parse_catalog_node(json.dumps([entry]), "pong")
            self.assertFalse(outcome["ok"])
            self.assertIn("pong", outcome["error"])

    def test_refuses_duplicate_id_naming_slug(self):
        manifest = [
            {"id": "win", "name": "Winner", "description": "Win once.", "hidden": False},
            {"id": "win", "name": "Winner Again", "description": "Win twice.", "hidden": False},
        ]
        outcome = parse_catalog_node(json.dumps(manifest), "pong")
        self.assertFalse(outcome["ok"])
        self.assertIn("pong", outcome["error"])
        self.assertIn("duplicate", outcome["error"].lower())


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ReadEmbeddedCatalogsTests(unittest.TestCase):
    """The client-side half: the board element's data-catalogs attribute, or [] with a console
    warning when it is missing or does not parse — never a throw on a page that is about to draw."""
    def read(self, element_json):
        script = (
            f'import {{ readEmbeddedCatalogs }} from {json.dumps(CATALOG_MODULE)};\n'
            + STDIN_PRELUDE
            + 'const warnings = [];\n'
            + 'console.warn = (...parts) => warnings.push(String(parts[0]));\n'
            + 'const catalogs = readEmbeddedCatalogs(inputs.element);\n'
            + 'process.stdout.write(JSON.stringify({ catalogs, warnings }));\n'
        )
        return run_node(script, {"element": element_json})

    def test_parses_the_attribute(self):
        catalogs = [{"slug": "pong", "title": "Insiculous Pong", "achievements": []}]
        outcome = self.read({"dataset": {"catalogs": json.dumps(catalogs)}})
        self.assertEqual(outcome, {"catalogs": catalogs, "warnings": []})

    def test_missing_element_or_attribute_is_empty_and_silent(self):
        self.assertEqual(self.read(None), {"catalogs": [], "warnings": []})
        self.assertEqual(self.read({"dataset": {}}), {"catalogs": [], "warnings": []})

    def test_malformed_attribute_is_empty_and_warns(self):
        outcome = self.read({"dataset": {"catalogs": "{ not json"}})
        self.assertEqual(outcome["catalogs"], [])
        self.assertEqual(len(outcome["warnings"]), 1)
        self.assertIn("unlocks only", outcome["warnings"][0])

    def test_a_non_array_attribute_is_empty(self):
        self.assertEqual(self.read({"dataset": {"catalogs": "{\"slug\": \"pong\"}"}})["catalogs"], [])


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ReadGameCatalogsTests(unittest.TestCase):
    def test_reads_in_order_and_skips_unplayable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            alpha_dir = temp_path / "games" / "alpha" / "v1"
            beta_dir = temp_path / "games" / "beta" / "v2"
            alpha_dir.mkdir(parents=True)
            beta_dir.mkdir(parents=True)

            alpha_manifest = [{"id": "a1", "name": "Alpha 1", "description": "First", "hidden": False}]
            beta_manifest = [{"id": "b1", "name": "Beta 1", "description": "Second", "hidden": False}]
            (alpha_dir / "achievements.json").write_text(json.dumps(alpha_manifest), encoding="utf-8")
            (beta_dir / "achievements.json").write_text(json.dumps(beta_manifest), encoding="utf-8")

            games = [
                {"id": "beta", "data": {"title": "Beta Game", "order": 2, "wasm": "/games/beta/v2/game.js"}},
                {"id": "unreleased", "data": {"title": "Unreleased", "order": 0}},
                {"id": "alpha", "data": {"title": "Alpha Game", "order": 1, "wasm": "/games/alpha/v1/game.js"}},
            ]

            outcome = read_catalogs_node(games, temp_path)
            self.assertTrue(outcome["ok"])
            self.assertEqual(
                outcome["result"],
                [
                    {"slug": "alpha", "title": "Alpha Game", "achievements": alpha_manifest},
                    {"slug": "beta", "title": "Beta Game", "achievements": beta_manifest},
                ],
            )

    def test_missing_file_throws_with_slug_path_and_fix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            games = [
                {"id": "pong", "data": {"title": "Pong", "order": 1, "wasm": "/games/pong/v2/game.js"}},
            ]
            outcome = read_catalogs_node(games, temp_path)
            self.assertFalse(outcome["ok"])
            error_message = outcome["error"]
            self.assertIn("pong", error_message)
            self.assertIn(str(temp_path / "games" / "pong" / "v2" / "achievements.json"), error_message)
            self.assertIn("--achievements-manifest", error_message)
            self.assertIn("build_wasm.sh", error_message)


if __name__ == "__main__":
    unittest.main()
