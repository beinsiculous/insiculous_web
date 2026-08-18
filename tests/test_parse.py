import unittest

from helpers import REPOSITORY_ROOT  # noqa: F401
from fk_core import keys
from fk_core.parse import parse_detail


class KeyTests(unittest.TestCase):
    def test_day_key_conversions(self):
        self.assertEqual(keys.day_key_from_label("Sunday A"), "sun-a")
        self.assertEqual(keys.day_key_from_short_key("Thu_B"), "thu-b")
        self.assertEqual(keys.short_key_from_day_key("thu-b"), "Thu_B")
        self.assertEqual(keys.label_from_day_key("thu-b"), "Thursday B")

    def test_meal_key_normalization_sorts_and_strips(self):
        self.assertEqual(keys.normalize_meal_key("Tue_A+Sun_A\t"), "sun-a+tue-a")
        self.assertEqual(keys.normalize_meal_key("Wed_B\t"), "wed-b")

    def test_category_labels(self):
        self.assertEqual(keys.category_key_from_label("Operations/Health"), ["operations", "health"])
        self.assertEqual(keys.category_key_from_label("Spirituality & Development"), ["spirituality-development"])


class DetailParsingTests(unittest.TestCase):
    def test_meal_prep(self):
        detail = parse_detail("Snack Fri_A+Sun_A & Dinner Sun_B+Wed_A")
        self.assertEqual(detail["kind"], "meal-prep")
        self.assertEqual([reference["mealKey"] for reference in detail["mealRefs"]], ["sun-a+fri-a", "sun-b+wed-a"])
        self.assertEqual(detail["mealRefs"][0]["slot"], "snack")

    def test_url_and_text_and_empty(self):
        self.assertEqual(parse_detail("https://example.org/x")["kind"], "url")
        self.assertEqual(parse_detail("Knowledge & Family Baguas")["kind"], "text")
        self.assertEqual(parse_detail("")["kind"], None)


if __name__ == "__main__":
    unittest.main()
