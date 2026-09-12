"""src/lib/shared/clock.js, driven through node, and its block rule held against the Python twin.

The block rule — which of the four blocks holds a wall time, with too-dark wrapping midnight — is the one
piece of shared/clock.js the resolver depends on (src/lib/champion/resolve.js), so it is compared to
tests/champion_reference.py's block_key_for_time over every minute of the day. This is the clock pair's
parity check (beinsiculous/insiculous_web#10 recorded that nothing exercised it).
"""
import unittest

import champion_reference as reference
from champion_fixture import build_champion_keep
from helpers import STDIN_PRELUDE, module_import, run_node

CHAMPION = build_champion_keep()


class ClockTests(unittest.TestCase):
    def call(self, symbol, arguments):
        script = module_import("clock.js", symbol) + STDIN_PRELUDE + \
            f"process.stdout.write(JSON.stringify({symbol}(...inputs)));"
        return run_node(script, arguments)

    def test_clock_times_are_shown_to_people_in_twelve_hour_form(self):
        self.assertEqual(self.call("formatClockTime", ["22:00"]), "10:00 PM")
        self.assertEqual(self.call("formatClockTime", ["00:30"]), "12:30 AM")
        self.assertEqual(self.call("formatClockTime", ["12:00"]), "12:00 PM")
        self.assertEqual(self.call("formatClockTime", ["not a time"]), "not a time")
        self.assertEqual(self.call("formatClockRange", ["18:00", "08:00"]), "6:00 PM–8:00 AM")

    def test_the_block_for_a_wall_time_wraps_past_midnight(self):
        expected = {"08:00": "early", "10:59": "early", "11:00": "midday", "14:59": "midday",
                    "15:00": "late", "17:59": "late", "18:00": "too-dark", "23:59": "too-dark",
                    "00:00": "too-dark", "07:59": "too-dark"}
        for wall_time, block_key in expected.items():
            self.assertEqual(self.call("blockKeyForTime", [CHAMPION["blocks"], wall_time]), block_key, wall_time)

    def test_the_four_blocks_cover_the_whole_day_and_both_ports_agree_on_every_minute(self):
        """Every minute of the day belongs to exactly one block, and the twin says the same block."""
        script = module_import("clock.js", "blockKeyForTime") + STDIN_PRELUDE + \
            "process.stdout.write(JSON.stringify(inputs.times.map((time) => blockKeyForTime(inputs.blocks, time))));"
        times = [f"{minutes // 60:02d}:{minutes % 60:02d}" for minutes in range(24 * 60)]
        resolved = run_node(script, {"blocks": CHAMPION["blocks"], "times": times})
        self.assertEqual([time for time, block_key in zip(times, resolved) if block_key is None], [],
                         "these minutes belong to no block")
        self.assertEqual(set(resolved), {block["key"] for block in CHAMPION["blocks"]}, "every block owns some minute")
        self.assertEqual(resolved, [reference.block_key_for_time(CHAMPION["blocks"], time) for time in times])
