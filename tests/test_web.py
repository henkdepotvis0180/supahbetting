import tempfile
import unittest
from pathlib import Path
from supahbetting.web import analyze, paper_summary


class DashboardTests(unittest.TestCase):
    def test_analyze(self):
        result = analyze({"event": "A - B", "home_xg": 1.6, "away_xg": 1.1,
                          "odds": {"home": 2.1, "draw": 3.4, "away": 3.6}})
        self.assertAlmostEqual(sum(x["probability"] for x in result["markets"].values()), 1)

    def test_bad_odds(self):
        with self.assertRaises(ValueError):
            analyze({"home_xg": 1.6, "away_xg": 1.1,
                     "odds": {"home": 1, "draw": 3, "away": 3}})

    def test_empty_paper(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(paper_summary(Path(directory) / "bets.jsonl")["count"], 0)


if __name__ == "__main__":
    unittest.main()
