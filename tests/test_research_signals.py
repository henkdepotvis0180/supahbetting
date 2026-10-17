"""Match-derived signals are computed from strictly earlier dates only."""
import unittest
from supahbetting.research_signals import fixture_signals


def fixture(identifier, day, home="Alpha", away="Beta"):
    return {"id": identifier, "date": day, "league": "nl.1",
            "season": "2026-27", "home": home, "away": away}


class ResearchSignalsTests(unittest.TestCase):
    def test_no_same_day_result_leakage(self):
        past=[{**fixture("first","2026-10-12"),"hg":3,"ag":1},
              {**fixture("today","2026-10-17"),"hg":7,"ag":0}]
        target=fixture("future","2026-10-17","Alpha","Gamma")
        row=fixture_signals(past,[target])[0]
        self.assertEqual(row["home_form"]["goals_for_last_5_mean"],3)
        self.assertEqual(row["home_form"]["rest_days"],5)
        self.assertEqual(row["home_form"]["previous_sample"],1)
        self.assertFalse(row["training_enabled"])

    def test_defensive_record_and_congestion(self):
        matches=[
            {**fixture("first","2026-10-01"),"hg":1,"ag":0},
            {**fixture("second","2026-10-09", "Gamma","Alpha"),"hg":2,"ag":2},
        ]
        row=fixture_signals(matches,[fixture("next","2026-10-12")])[0]
        self.assertEqual(row["home_form"]["matches_previous_14_days"],2)
        self.assertEqual(row["home_form"]["goals_for_last_5_mean"],1.5)
        self.assertEqual(row["home_form"]["goals_against_last_5_mean"],1)
        self.assertEqual(row["home_form"]["rest_days"],3)
        self.assertEqual(row["away_form"]["previous_sample"],1)
        self.assertTrue(row["home_form"]["source"].startswith("derived_"))

    def test_teams_without_history_are_unknown_not_fabricated(self):
        row=fixture_signals([], [fixture("future","2026-10-23")])[0]
        self.assertIsNone(row["home_form"]["rest_days"])
        self.assertIsNone(row["away_form"]["goals_for_last_5_mean"])
        self.assertEqual(row["home_form"]["matches_previous_14_days"],0)


if __name__ == "__main__":
    unittest.main()
