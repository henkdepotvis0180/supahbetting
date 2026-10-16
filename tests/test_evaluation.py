import math
import unittest

from supahbetting.evaluation import score_settled_matches


def m(h, a):
    return {
        "home_team": "A", "away_team": "B",
        "result_home": h, "result_away": a,
        "home_xg": 1.4, "away_xg": 1.0,
        "odds_home": 2.2, "odds_draw": 3.2, "odds_away": 3.6,
    }


class EvaluationTests(unittest.TestCase):
    def test_empty(self):
        x = score_settled_matches([])
        self.assertEqual(x["evaluated_matches"], 0)
        self.assertIsNone(x["model_brier"])
        self.assertFalse(x["is_sufficient_sample"])

    def test_proper_scores_and_skip_unfinished(self):
        x = score_settled_matches([m(2, 1), m(0, 0), m(None, None)])
        self.assertEqual(x["evaluated_matches"], 2)
        self.assertTrue(math.isfinite(x["model_brier"]))
        self.assertGreaterEqual(x["model_brier"], 0)
        self.assertLessEqual(x["model_brier"], 2)
        self.assertGreaterEqual(x["market_brier"], 0)
        self.assertTrue(math.isfinite(x["model_log_loss"]))

    def test_sample_threshold(self):
        x = score_settled_matches([m(1, 0)] * 100)
        self.assertTrue(x["is_sufficient_sample"])


if __name__ == "__main__":
    unittest.main()
