import unittest
from supahbetting.core import match_probabilities, expected_value, implied_probability, no_vig_probabilities


class CoreTests(unittest.TestCase):
    def test_probability_sum(self):
        result = match_probabilities(1.5, 1.1)
        self.assertAlmostEqual(sum(result[k] for k in ("home", "draw", "away")), 1, places=8)

    def test_equal_teams(self):
        result = match_probabilities(1.2, 1.2)
        self.assertAlmostEqual(result["home"], result["away"])

    def test_ev(self):
        self.assertAlmostEqual(expected_value(.6, 2.0), .2)

    def test_vig(self):
        self.assertAlmostEqual(sum(no_vig_probabilities({"home": 2, "away": 2}).values()), 1)

    def test_invalid_odds(self):
        with self.assertRaises(ValueError):
            implied_probability(1.0)


if __name__ == "__main__":
    unittest.main()
