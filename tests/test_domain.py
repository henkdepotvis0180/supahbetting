import math
import unittest

from supahbetting.domain import (
    ValidationError, finite_number, match_analysis, model_probabilities,
    parse_kickoff, quote_slip, validate_match,
)


def fixture():
    return {
        "home_team": "Ajax", "away_team": "PSV",
        "home_xg": 1.6, "away_xg": 1.2,
        "odds_home": 2.1, "odds_draw": 3.4, "odds_away": 3.6,
        "source": "Handmatig",
    }


class DomainTests(unittest.TestCase):
    def test_probabilities_sum_and_symmetry(self):
        m = model_probabilities(1.5, 1.5)
        self.assertAlmostEqual(m["home"], m["away"], places=10)
        self.assertAlmostEqual(sum(m[k] for k in ("home", "draw", "away")), 1.0, places=10)

    def test_zero_expected_goals(self):
        m = model_probabilities(0, 0)
        self.assertAlmostEqual(m["draw"], 1.0)
        self.assertAlmostEqual(m["home"], 0)
        self.assertAlmostEqual(m["away"], 0)

    def test_goal_totals_against_closed_formula(self):
        m = model_probabilities(1.2, 0.9)
        total = 2.1
        expected = 1 - math.exp(-total) * (1 + total + total * total / 2)
        self.assertAlmostEqual(m["over_2_5"], expected, places=10)
        self.assertAlmostEqual(m["btts"], (1 - math.exp(-1.2)) * (1 - math.exp(-0.9)), places=10)

    def test_high_allowed_goals(self):
        m = model_probabilities(8, 8)
        self.assertAlmostEqual(sum(m[k] for k in ("home", "draw", "away")), 1, places=10)

    def test_price_analysis(self):
        m = match_analysis(validate_match(fixture()))
        self.assertAlmostEqual(m["markets"]["home"]["expected_roi"],
                               m["markets"]["home"]["probability"] * 2.1 - 1.0)

    def test_reject_invalid_numerics(self):
        for value in [float("nan"), float("inf"), float("-inf"), True, "abc", None]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                finite_number(value, "test", 0, 100)

    def test_reject_invalid_match(self):
        for field, value in [
            ("home_team", "PSV"), ("home_xg", float("nan")),
            ("odds_home", 1.0), ("odds_draw", "oops"),
        ]:
            data = fixture()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_match(data)

    def test_kickoff_requires_timezone(self):
        with self.assertRaises(ValidationError):
            parse_kickoff("2026-11-01T20:00:00")
        self.assertIn("+02:00", parse_kickoff("2026-11-01T20:00:00+02:00"))

    def test_two_leg_accumulator(self):
        legs = [
            {"match_id": 1, "market": "home", "probability": 0.5, "decimal_odds": 2.0},
            {"match_id": 2, "market": "draw", "probability": 0.4, "decimal_odds": 3.0},
        ]
        q = quote_slip(legs, 10)
        self.assertEqual(q["combined_odds"], 6)
        self.assertAlmostEqual(q["combined_probability"], 0.2)
        self.assertAlmostEqual(q["gross_payout"], 60)
        self.assertAlmostEqual(q["expected_roi"], 0.2)

    def test_same_match_is_rejected(self):
        legs = [
            {"match_id": 1, "market": "home", "probability": .5, "decimal_odds": 2},
            {"match_id": 1, "market": "draw", "probability": .2, "decimal_odds": 5},
        ]
        with self.assertRaisesRegex(ValidationError, "dezelfde wedstrijd"):
            quote_slip(legs, 10)

    def test_invalid_stake_and_leg_count(self):
        with self.assertRaises(ValidationError):
            quote_slip([], 5)
        with self.assertRaises(ValidationError):
            quote_slip([{"match_id": 1, "market": "home", "probability": .5,
                         "decimal_odds": 2}], float("nan"))


if __name__ == "__main__":
    unittest.main()
