"""Tests for the announce tree parser, universal accessibility rules, and sentinels."""
import json
import shutil
import unittest
from pathlib import Path

from helpers import REPOSITORY_ROOT, STDIN_PRELUDE, run_node

ANNOUNCE_TREE_MODULE = (REPOSITORY_ROOT / "scripts" / "lib" / "announce-tree.mjs").as_uri()
ACHIEVEMENTS_FIXTURE = (REPOSITORY_ROOT / "tests" / "fixtures" / "aria" / "achievements.snapshot.yaml").read_text(encoding="utf-8")
FIXKNITT_FIXTURE = (REPOSITORY_ROOT / "tests" / "fixtures" / "aria" / "fixknitt-peripheral-open.snapshot.yaml").read_text(encoding="utf-8")


def announce_script(body):
    return (
        f'import {{ parseAriaSnapshot, announceFindings, missingSentinels }} from {json.dumps(ANNOUNCE_TREE_MODULE)};'
        + STDIN_PRELUDE
        + body
    )


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class ParseAriaSnapshotTests(unittest.TestCase):
    """The pure ariaSnapshot parser over real captures and format edge cases."""

    def parse(self, text):
        script = announce_script(
            "const nodes = parseAriaSnapshot(inputs.text);"
            "process.stdout.write(JSON.stringify(nodes));"
        )
        return run_node(script, {"text": text})

    def test_parses_achievements_fixture_cleanly(self):
        nodes = self.parse(ACHIEVEMENTS_FIXTURE)

        # 9 headings: one h1 and eight h2s
        headings = [node for node in nodes if node["role"] == "heading"]
        self.assertEqual(len(headings), 9)
        self.assertEqual(headings[0]["attributes"]["level"], 1)
        self.assertEqual(headings[0]["name"], "Achievements")
        for heading in headings[1:]:
            self.assertEqual(heading["attributes"]["level"], 2)

        # Four landmarks present
        roles = {node["role"] for node in nodes}
        self.assertIn("banner", roles)
        self.assertIn("navigation", roles)
        self.assertIn("main", roles)
        self.assertIn("contentinfo", roles)

        # Every link is named
        links = [node for node in nodes if node["role"] == "link"]
        self.assertTrue(len(links) > 0)
        for link in links:
            self.assertTrue(len(link["name"].strip()) > 0)

        # /url and text lines are ignored
        self.assertFalse(any(node["role"] == "/url" or node["role"] == "text" for node in nodes))

    def test_parses_fixknitt_fixture_cleanly(self):
        nodes = self.parse(FIXKNITT_FIXTURE)
        headings = [node for node in nodes if node["role"] == "heading"]
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0]["attributes"]["level"], 1)
        self.assertEqual(headings[0]["name"], "Fix Knitt")

    def test_parses_various_node_shapes(self):
        sample = "\n".join([
            "- banner:",
            '  - heading "Keep" [level=1]',
            '  - link "x" [expanded]:',
            '  - \'link "Achievements" [expanded]\':',
            '  - heading "A \\"quoted\\" title and \\\\" [level=2]',
            "- group: Peripheral",
        ])
        nodes = self.parse(sample)
        self.assertEqual(len(nodes), 6)

        # Container form
        self.assertEqual(nodes[0]["role"], "banner")
        self.assertEqual(nodes[0]["name"], "")

        # Heading with attributes and no colon
        self.assertEqual(nodes[1]["role"], "heading")
        self.assertEqual(nodes[1]["name"], "Keep")
        self.assertEqual(nodes[1]["attributes"]["level"], 1)

        # Node with expanded attribute
        self.assertEqual(nodes[2]["role"], "link")
        self.assertEqual(nodes[2]["name"], "x")
        self.assertEqual(nodes[2]["attributes"]["expanded"], True)

        # Single-quoted key enclosing attributes
        self.assertEqual(nodes[3]["role"], "link")
        self.assertEqual(nodes[3]["name"], "Achievements")
        self.assertEqual(nodes[3]["attributes"]["expanded"], True)

        # Escaped quotes and backslashes in name
        self.assertEqual(nodes[4]["role"], "heading")
        self.assertEqual(nodes[4]["name"], 'A "quoted" title and \\')
        self.assertEqual(nodes[4]["attributes"]["level"], 2)

        # group: Peripheral form
        self.assertEqual(nodes[5]["role"], "group")
        self.assertEqual(nodes[5]["name"], "")

    def test_continuation_lines_fold_into_previous_node(self):
        sample = "\n".join([
            '- link "Line one',
            '  line two":',
        ])
        nodes = self.parse(sample)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Line one line two")

    def test_errors_on_unrecognized_line_shape(self):
        sample = "- 12345 invalid line"
        with self.assertRaises(AssertionError) as ctx:
            self.parse(sample)
        self.assertIn("Unrecognized ariaSnapshot line", str(ctx.exception))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class AnnounceFindingsTests(unittest.TestCase):
    """Universal accessibility rules for landmarks, headings, controls and regions."""

    def findings(self, text):
        script = announce_script(
            "const nodes = parseAriaSnapshot(inputs.text);"
            "const findings = announceFindings(nodes);"
            "process.stdout.write(JSON.stringify(findings));"
        )
        return run_node(script, {"text": text})

    def test_clean_captures_report_no_findings(self):
        self.assertEqual(self.findings(ACHIEVEMENTS_FIXTURE), [])
        self.assertEqual(self.findings(FIXKNITT_FIXTURE), [])

    def test_reports_second_main_landmark(self):
        sample = ACHIEVEMENTS_FIXTURE + "\n- main:\n  - paragraph: extra main"
        findings = self.findings(sample)
        self.assertTrue(any("expected exactly one main landmark, found 2" in finding for finding in findings))

    def test_reports_missing_contentinfo(self):
        # Remove contentinfo from fixture
        lines = [line for line in ACHIEVEMENTS_FIXTURE.splitlines() if "contentinfo" not in line and "Accessibility" not in line]
        findings = self.findings("\n".join(lines))
        self.assertTrue(any("missing contentinfo landmark" in finding for finding in findings))

    def test_reports_two_h1_headings(self):
        sample = ACHIEVEMENTS_FIXTURE + '\n  - heading "Duplicate H1" [level=1]'
        findings = self.findings(sample)
        self.assertTrue(any("expected exactly one level-1 heading, found 2" in finding for finding in findings))

    def test_reports_h2_before_h1(self):
        sample = '\n'.join([
            '- banner:',
            '- navigation "Main":',
            '  - link "Home":',
            '- heading "Early H2" [level=2]',
            '- main:',
            '  - heading "Title" [level=1]',
            '- contentinfo:',
        ])
        findings = self.findings(sample)
        self.assertTrue(any("first heading must be level 1, found level 2" in finding for finding in findings))

    def test_reports_skipped_heading_level(self):
        sample = '\n'.join([
            '- banner:',
            '- navigation "Main":',
            '  - link "Home":',
            '- main:',
            '  - heading "Title" [level=1]',
            '  - heading "Skipped H3" [level=3]',
            '- contentinfo:',
        ])
        findings = self.findings(sample)
        self.assertTrue(any("skipped level 3" in finding for finding in findings))

    def test_reports_bare_button_unnamed_control(self):
        sample = ACHIEVEMENTS_FIXTURE + "\n  - button"
        findings = self.findings(sample)
        self.assertTrue(any('bare role "button" has no accessible name' in finding for finding in findings))

    def test_reports_nameless_region(self):
        sample = ACHIEVEMENTS_FIXTURE + "\n- region:"
        findings = self.findings(sample)
        self.assertTrue(any('named regions and dialogs: "region" has no accessible name' in finding for finding in findings))


@unittest.skipIf(shutil.which("node") is None, "node not installed")
class MissingSentinelsTests(unittest.TestCase):
    """Seed verification: headings expected on seeded pages must exist in the tree."""

    def check(self, route, text, sentinels):
        script = announce_script(
            "const nodes = parseAriaSnapshot(inputs.text);"
            "const missing = missingSentinels(inputs.route, nodes, inputs.sentinels);"
            "process.stdout.write(JSON.stringify(missing));"
        )
        return run_node(script, {"route": route, "text": text, "sentinels": sentinels})

    def test_reports_missing_heading_for_route_in_map(self):
        sentinels = {"/profile/": ["Insiculous Pong — 8 unlocked", "Missing Heading"]}
        sample = '- heading "Insiculous Pong — 8 unlocked" [level=3]'
        missing = self.check("/profile/", sample, sentinels)
        self.assertEqual(missing, ["Missing Heading"])

    def test_reports_nothing_when_all_headings_present(self):
        sentinels = {"/profile/": ["Insiculous Pong — 8 unlocked"]}
        sample = '- heading "Insiculous Pong — 8 unlocked" [level=3]'
        missing = self.check("/profile/", sample, sentinels)
        self.assertEqual(missing, [])

    def test_reports_nothing_for_route_not_in_map(self):
        sentinels = {"/profile/": ["Insiculous Pong — 8 unlocked"]}
        sample = '- heading "Something Else" [level=1]'
        missing = self.check("/other/", sample, sentinels)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
