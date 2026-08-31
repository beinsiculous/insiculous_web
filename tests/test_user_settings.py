"""The settings migration (src/lib/shared/user-settings.js) and the profile-name generator
(src/lib/shared/profile-names.js), driven through node.

Split out of tests/test_workspace_docs.py on 2026-08-30: that file also covered
src/lib/shared/workspace-docs.js, which was removed with the creation chain (preserved at the tag
`creation-chain-parked`). These two classes came across unchanged, except that the import rejection
below gained a meal-plan case — see the note on it. Python has no twin of these modules."""
import json
import shutil
import unittest

from tests.helpers import REPOSITORY_ROOT, STDIN_PRELUDE, module_import, run_node


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class SettingsMigrationTests(unittest.TestCase):
    def test_v1_settings_keep_their_profiles_and_lose_the_secrets(self):
        v1_text = (REPOSITORY_ROOT / "tests" / "fixtures" / "user-settings.v1.sample.json").read_text(encoding="utf-8")
        script = module_import("user-settings.js", "migrateSettings", "importSettings", "USER_WEIGHTS_ID") + STDIN_PRELUDE + """
            const migrated = migrateSettings(JSON.parse(inputs.text));
            const future = migrateSettings({ schemaVersion: 4, weightsProfiles: {}, futureField: 1 });
            const imported = importSettings(inputs.text);
            let rejected = null;
            try { importSettings(JSON.stringify({ schemaVersion: 1, source: { kind: "photo" } })); } catch (error) { rejected = error.message; }
            // A meal-plan document carries an integer schemaVersion with no source and no cycleLengthDays,
            // so the settings test alone would take it (meal-plan.schema.json requires only
            // schemaVersion/kind/items). classifyAssistantDocument used to return "meal-plan" first;
            // isUserSettingsDocument keeps that branch order, and this is what holds it there.
            let rejectedMealPlan = null;
            try { importSettings(JSON.stringify({ schemaVersion: 1, kind: "meal-plan", items: [{ id: "tea--sun-a", meal: "tea", dish: "x", days: ["sun-a"] }] })); } catch (error) { rejectedMealPlan = error.message; }
            let rejectedWeights = null;
            try { importSettings(JSON.stringify({ schemaVersion: 1, id: "u", source: "questionnaire", cycleLengthDays: 14, categories: {} })); } catch (error) { rejectedWeights = error.message; }
            process.stdout.write(JSON.stringify({ migrated, imported, rejected, rejectedMealPlan, rejectedWeights, future, weightsId: USER_WEIGHTS_ID }));
        """
        result = run_node(script, {"text": v1_text})
        migrated = result["migrated"]
        self.assertEqual(migrated["schemaVersion"], 3)
        self.assertNotIn("aiProvider", migrated)
        self.assertNotIn("weights", migrated)
        self.assertNotIn("sk-not-real", json.dumps(migrated))
        self.assertEqual(sorted(migrated["weightsProfiles"]), ["family", "solo"], "v1 profiles are kept, none collapsed")
        self.assertEqual(migrated["activeWeightsId"], "family")
        self.assertEqual(migrated["weightsProfiles"]["family"]["questionnaire"]["answers"]["startup"]["groupSize"], 4)
        self.assertIsNone(migrated["epochOverride"], "an impossible date is dropped")
        self.assertEqual(migrated["theme"], "hidden-fort")  # kept for compatibility, ignored by the app
        self.assertEqual(result["imported"], migrated)
        self.assertIn("Not a FortKnight user-settings file", result["rejected"])
        self.assertIn("Not a FortKnight user-settings file", result["rejectedMealPlan"],
                      "a meal-plan document must not be migrated into the device's settings")
        self.assertIn("Not a FortKnight user-settings file", result["rejectedWeights"],
                      "a weights file must not be migrated into the device's settings")
        self.assertNotIn("futureField", result["future"], "unknown keys are dropped in memory (never written back for newer records)")
        self.assertEqual(result["weightsId"], "username")

    def test_v2_settings_become_one_profile_and_recover_parked_ones(self):
        v2_text = (REPOSITORY_ROOT / "tests" / "fixtures" / "user-settings.v2.sample.json").read_text(encoding="utf-8")
        script = module_import("user-settings.js", "migrateSettings", "defaultSettings") + STDIN_PRELUDE + """
            const plain = migrateSettings(JSON.parse(inputs.text));
            const recovered = migrateSettings(JSON.parse(inputs.text), { solo: { id: "solo", questionnaire: { answers: {} } }, "my-weights": { id: "my-weights", questionnaire: { answers: { startup: { groupSize: 99 } } } } });
            const unnamed = migrateSettings({ schemaVersion: 2, weights: { questionnaire: { answers: {} } } });
            const empty = migrateSettings({ schemaVersion: 2, weights: null });
            const staleActive = migrateSettings({ schemaVersion: 3, weightsProfiles: { a: { id: "a" } }, activeWeightsId: "gone" });
            const oddNames = migrateSettings({ schemaVersion: 3, weightsProfiles: { "My Profile": { id: "whatever" } }, activeWeightsId: "My Profile" });
            const collision = migrateSettings({ schemaVersion: 1, weightsProfiles: { "my-profile": { id: "my-profile", tag: 1 }, "My Profile": { id: "x", tag: 2 }, "my profile": { id: "y", tag: 3 } }, activeWeightsId: "My Profile" });
            process.stdout.write(JSON.stringify({ plain, recovered, unnamed, empty, staleActive, oddNames, collision, defaults: defaultSettings() }));
        """
        result = run_node(script, {"text": v2_text})
        self.assertEqual(list(result["plain"]["weightsProfiles"]), ["my-weights"])
        self.assertEqual(result["plain"]["activeWeightsId"], "my-weights")
        self.assertEqual(result["plain"]["weightsProfiles"]["my-weights"]["questionnaire"]["answers"]["startup"]["groupSize"], 2)
        self.assertEqual(sorted(result["recovered"]["weightsProfiles"]), ["my-weights", "solo"], "parked v1 profiles come back")
        self.assertEqual(result["recovered"]["weightsProfiles"]["my-weights"]["questionnaire"]["answers"]["startup"]["groupSize"], 2, "the live record wins over the backup")
        self.assertEqual(result["recovered"]["activeWeightsId"], "my-weights")
        self.assertEqual(list(result["unnamed"]["weightsProfiles"]), ["username"])
        self.assertEqual(result["unnamed"]["weightsProfiles"]["username"]["id"], "username")
        self.assertEqual((result["empty"]["weightsProfiles"], result["empty"]["activeWeightsId"]), ({}, "username"))
        self.assertEqual(result["staleActive"]["activeWeightsId"], "gone", "an active id that names no saved profile survives (a profile started and not saved yet)")
        self.assertEqual(result["defaults"]["activeWeightsId"], "username")
        self.assertEqual((list(result["oddNames"]["weightsProfiles"]), result["oddNames"]["weightsProfiles"]["my-profile"]["id"], result["oddNames"]["activeWeightsId"]), (["my-profile"], "my-profile", "my-profile"), "profile keys are kebab-case ids")
        collision = result["collision"]
        self.assertEqual({key: profile["tag"] for key, profile in collision["weightsProfiles"].items()}, {"my-profile": 1, "my-profile-2": 2, "my-profile-3": 3}, "keys that slugify alike keep every profile")
        self.assertEqual(collision["activeWeightsId"], "my-profile-2", "the active id follows its renamed profile")

    def test_imported_settings_merge_profiles(self):
        script = module_import("user-settings.js", "mergeImportedSettings") + STDIN_PRELUDE + """
            const current = { schemaVersion: 3, timezone: "Europe/London", weightsProfiles: { work: { id: "work", tag: "old" }, home: { id: "home" } }, activeWeightsId: "home" };
            const narrower = { schemaVersion: 3, timezone: null, weightsProfiles: { work: { id: "work", tag: "new" } }, activeWeightsId: "work" };
            const extrasOnly = { schemaVersion: 3, timezone: "Asia/Tokyo", weightsProfiles: {}, activeWeightsId: "my-weights" };
            process.stdout.write(JSON.stringify({ merged: mergeImportedSettings(current, narrower), extras: mergeImportedSettings(current, extrasOnly) }));
        """
        result = run_node(script, {})
        merged = result["merged"]
        self.assertEqual(sorted(merged["weightsProfiles"]), ["home", "work"], "a narrower file drops nothing")
        self.assertEqual(merged["weightsProfiles"]["work"]["tag"], "new")
        self.assertEqual((merged["activeWeightsId"], merged["timezone"]), ("work", None), "the file's active profile and device extras win")
        extras = result["extras"]
        self.assertEqual((sorted(extras["weightsProfiles"]), extras["activeWeightsId"], extras["timezone"]), (["home", "work"], "home", "Asia/Tokyo"), "an extras-only file keeps the device's profiles and active id")

    def test_profile_operations(self):
        script = module_import("user-settings.js", "defaultSettings", "createProfile", "duplicateProfile", "deleteProfile", "renameProfile", "switchProfile", "setActiveWeights", "profileIds", "activeWeights") + STDIN_PRELUDE + """
            const out = {};
            const settings = defaultSettings();
            out.unsavedActive = activeWeights(settings);
            setActiveWeights(settings, { id: "my-weights", questionnaire: { answers: { startup: { groupSize: 1 } } } });
            createProfile(settings, "Family Time");
            out.afterCreate = [settings.activeWeightsId, profileIds(settings), activeWeights(settings)];
            const errors = {};
            try { createProfile(settings, "family time"); } catch (error) { errors.duplicateUnsaved = error.message; }
            try { createProfile(settings, "  "); } catch (error) { errors.blank = error.message; }
            try { duplicateProfile(settings, "family-time", "x"); } catch (error) { errors.duplicateUnsavedSource = error.message; }
            setActiveWeights(settings, { id: "family-time", questionnaire: { answers: { startup: { groupSize: 4 } } } });
            duplicateProfile(settings, "family-time", "Family B");
            out.afterDuplicate = [settings.activeWeightsId, profileIds(settings), activeWeights(settings).questionnaire.answers.startup.groupSize];
            settings.weightsProfiles["family-b"].questionnaire.answers.startup.groupSize = 5;
            out.copyIsDeep = settings.weightsProfiles["family-time"].questionnaire.answers.startup.groupSize;
            renameProfile(settings, "family-b", "Family C");
            out.afterRename = [settings.activeWeightsId, profileIds(settings), settings.weightsProfiles["family-c"].id, settings.weightsProfiles["family-c"].questionnaire.answers.startup.groupSize];
            try { renameProfile(settings, "family-c", "family time"); } catch (error) { errors.renameTaken = error.message; }
            renameProfile(settings, "family-c", "Family B");
            switchProfile(settings, "my-weights");
            deleteProfile(settings, "family-b");
            out.afterDeleteOther = [settings.activeWeightsId, profileIds(settings)];
            deleteProfile(settings, "my-weights");
            out.afterDeleteActive = [settings.activeWeightsId, profileIds(settings)];
            deleteProfile(settings, "family-time");
            out.afterDeleteLast = [settings.activeWeightsId, profileIds(settings), activeWeights(settings)];
            out.errors = errors;
            process.stdout.write(JSON.stringify(out));
        """
        result = run_node(script, {})
        self.assertIsNone(result["unsavedActive"])
        self.assertEqual(result["afterCreate"], ["family-time", ["my-weights"], None], "a new profile is active but unsaved")
        self.assertIn("already a profile", result["errors"]["duplicateUnsaved"])
        self.assertIn("needs a name", result["errors"]["blank"])
        self.assertIn("not been saved yet", result["errors"]["duplicateUnsavedSource"])
        self.assertEqual(result["afterDuplicate"], ["family-b", ["my-weights", "family-time", "family-b"], 4])
        self.assertEqual(result["copyIsDeep"], 4)
        self.assertEqual(result["afterRename"], ["family-c", ["my-weights", "family-time", "family-c"], "family-c", 5], "rename moves the profile under the new id and the active id follows")
        self.assertIn("already a profile", result["errors"]["renameTaken"])
        self.assertEqual(result["afterDeleteOther"], ["my-weights", ["my-weights", "family-time"]])
        self.assertEqual(result["afterDeleteActive"], ["family-time", ["family-time"]])
        self.assertEqual(result["afterDeleteLast"], ["username", [], None], "the last profile can go too; the device is back to a blank default")

    def test_migrated_settings_satisfy_the_schema(self):
        from fk_core.validate import ValidationReport, check_against_schema_file
        v1_text = (REPOSITORY_ROOT / "tests" / "fixtures" / "user-settings.v1.sample.json").read_text(encoding="utf-8")
        v2_text = (REPOSITORY_ROOT / "tests" / "fixtures" / "user-settings.v2.sample.json").read_text(encoding="utf-8")
        script = module_import("user-settings.js", "migrateSettings", "defaultSettings") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify([migrateSettings(JSON.parse(inputs.v1)), migrateSettings(JSON.parse(inputs.v2)), defaultSettings()]));"
        for settings in run_node(script, {"v1": v1_text, "v2": v2_text}):
            report = ValidationReport()
            check_against_schema_file(settings, "user-settings", report)
            self.assertTrue(report.ok, report.render())


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ProfileNamesTests(unittest.TestCase):
    """src/lib/shared/profile-names.js: a device's first profile is named adjective-noun-title."""

    WEIGHTS_ID_PATTERN = json.loads(
        (REPOSITORY_ROOT / "data" / "schema" / "weights.schema.json").read_text(encoding="utf-8")
    )["properties"]["id"]["pattern"]

    def tables(self):
        script = module_import("profile-names.js", "ADJECTIVES", "NOUNS", "TITLES") + \
            "process.stdout.write(JSON.stringify({ADJECTIVES, NOUNS, TITLES}));"
        return run_node(script, {})

    def test_every_word_is_a_valid_id_fragment(self):
        tables = self.tables()
        self.assertEqual([len(tables["ADJECTIVES"]), len(tables["NOUNS"]), len(tables["TITLES"])], [30, 28, 30])
        for table_name, words in tables.items():
            self.assertEqual(len(set(words)), len(words), f"{table_name} has a duplicate")
            for word in words:
                # Every word must already be id-shaped: a generated name is used without slugifying.
                self.assertRegex(word, self.WEIGHTS_ID_PATTERN, f"{table_name}: {word}")

    def test_generated_names_span_the_tables_and_stay_valid_ids(self):
        script = module_import("profile-names.js", "randomProfileName") + """
            const names = [];
            for (let step = 0; step < 200; step += 1) names.push(randomProfileName(() => step / 200));
            process.stdout.write(JSON.stringify({
                lowest: randomProfileName(() => 0),
                highest: randomProfileName(() => 0.9999999999),  // must not run off the end of a table
                names,
            }));
        """
        result = run_node(script, {})
        self.assertEqual(result["lowest"], "humorous-library-poet", "random() -> 0 takes the first of each table")
        self.assertEqual(result["highest"], "super-obligation-employee", "random() just under 1 takes the last")
        for name in result["names"]:
            self.assertRegex(name, self.WEIGHTS_ID_PATTERN, name)

    def test_unused_name_avoids_taken_ids_and_falls_back_to_a_suffix(self):
        script = module_import("profile-names.js", "unusedProfileName") + """
            // A random() pinned to one name: every roll collides, so the suffix loop is the only way out —
            // the callers hand the result to newProfileId, which throws on a name already taken.
            const pinned = () => 0;
            process.stdout.write(JSON.stringify({
                free: unusedProfileName([], pinned),
                skipped: unusedProfileName(["humorous-library-poet"], pinned),
                twice: unusedProfileName(["humorous-library-poet", "humorous-library-poet-2"], pinned),
                noTaken: unusedProfileName(null, pinned),
            }));
        """
        result = run_node(script, {})
        self.assertEqual(result["free"], "humorous-library-poet")
        self.assertEqual(result["skipped"], "humorous-library-poet-2", "an exhausted roll gets a suffix, never a collision")
        self.assertEqual(result["twice"], "humorous-library-poet-3")
        self.assertEqual(result["noTaken"], "humorous-library-poet", "no taken list is not an error")
        for name in result.values():
            self.assertRegex(name, self.WEIGHTS_ID_PATTERN, name)


if __name__ == "__main__":
    unittest.main()
