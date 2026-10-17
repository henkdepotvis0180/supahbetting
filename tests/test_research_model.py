"""Real prospective checks cannot be manufactured from post-match results."""
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from supahbetting.research_model import (
    _history_digest, build_research_report, train_candidate, update_shadow,
)
from supahbetting.trained_model import LEAGUES, LeagueRatings


class ResearchModelTests(unittest.TestCase):
    def base(self):
        row = {"id": "fixture-a", "league": "nl.1", "season": "2026-27",
               "date": "2026-10-19", "home": "Alpha", "away": "Beta"}
        return {
            "matches": [], "fixtures": [row],
            "latest_result_date": "2026-10-16",
        }

    def test_future_fixture_shadow_is_frozen_then_scored(self):
        states = {league: LeagueRatings(.04, 3) for league in LEAGUES}
        now = datetime(2026, 10, 17, 9, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow.json"
            current = self.base()
            first = update_shadow(current, states, shadow_path=path,
                                  today=date(2026,10,17), now=now)
            self.assertEqual(first["new_predictions"],1)
            self.assertEqual(first["graded_predictions"],0)
            original = json.loads(path.read_text())["predictions"]["fixture-a"]
            current["fixtures"] = []
            current["matches"] = [{**self.base()["fixtures"][0], "hg": 2, "ag": 1}]
            second = update_shadow(current, states, shadow_path=path,
                                   today=date(2026,10,20),
                                   now=datetime(2026,10,20,tzinfo=timezone.utc))
            self.assertEqual(second["graded_predictions"],1)
            self.assertGreater(second["prospective_logloss"],0)
            next_row = json.loads(path.read_text())["predictions"]["fixture-a"]
            self.assertEqual(original["probabilities"],next_row["probabilities"])
            self.assertEqual(original["forecast_created_at"],next_row["forecast_created_at"])

    def test_no_backfill_of_already_finished_match(self):
        states = {league: LeagueRatings(.04, 3) for league in LEAGUES}
        inventory = self.base()
        inventory["fixtures"] = []
        inventory["matches"] = [{**self.base()["fixtures"][0], "hg": 1, "ag": 0}]
        with tempfile.TemporaryDirectory() as directory:
            result = update_shadow(inventory, states,
                                   shadow_path=Path(directory)/"shadow.json",
                                   today=date(2026,10,20))
            self.assertEqual(result["graded_predictions"],0)
            self.assertEqual(result["new_predictions"],0)

    def test_rescheduled_fixture_cannot_be_backdated(self):
        states = {league: LeagueRatings(.04, 3) for league in LEAGUES}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"shadow.json"
            inventory = self.base()
            update_shadow(inventory,states,shadow_path=path,
                          today=date(2026,10,17),
                          now=datetime(2026,10,17,tzinfo=timezone.utc))
            inventory["matches"] = [
                {**self.base()["fixtures"][0], "date": "2026-10-20", "hg":1,"ag":1}
            ]
            inventory["fixtures"] = []
            result = update_shadow(inventory,states,shadow_path=path,
                          today=date(2026,10,21),
                          now=datetime(2026,10,21,tzinfo=timezone.utc))
            self.assertEqual(result["graded_predictions"],0)
            row = json.loads(path.read_text())["predictions"]["fixture-a"]
            self.assertEqual(row["void_reason"],"fixture_rescheduled_or_no_lead_time")

    def test_score_digest_changes_after_goal_correction(self):
        row = {**self.base()["fixtures"][0], "hg": 1, "ag": 0}
        self.assertNotEqual(
            _history_digest([row]),
            _history_digest([{**row, "hg": 2}])
        )


if __name__ == "__main__":
    unittest.main()
