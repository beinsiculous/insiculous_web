import unittest

from helpers import REPOSITORY_ROOT  # noqa: F401  (sets sys.path)
from fk_core import timeconv


class TimeConversionTests(unittest.TestCase):
    def test_fraction_to_time_string(self):
        self.assertEqual(timeconv.fraction_to_time_string(0.3333333333333333), "08:00")
        self.assertEqual(timeconv.fraction_to_time_string(0.4583333333333333), "11:00")
        self.assertEqual(timeconv.fraction_to_time_string(0.6145833333333334), "14:45")
        self.assertEqual(timeconv.fraction_to_time_string(0.4236111111111111), "10:10")

    def test_round_trip_minutes(self):
        self.assertEqual(timeconv.time_string_to_minutes("24:00"), 1440)
        self.assertEqual(timeconv.minutes_to_time_string(1440), "24:00")
        self.assertEqual(timeconv.duration_minutes("08:00", "11:00"), 180)

    def test_rejects_bad_time(self):
        with self.assertRaises(ValueError):
            timeconv.time_string_to_minutes("8:00")


if __name__ == "__main__":
    unittest.main()
