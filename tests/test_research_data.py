"""Offline tests for verifiable research ingestion from 2016 onward."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from supahbetting.research_data import (
    atomic_json, parse_source, refresh, seasons, valid_score,
)
from supahbetting.trained_model import LEAGUES


def game(day="2016-08-12", ft=(2, 1), home="Alpha", away="Beta"):
    return {"date": day, "team1": home, "team2": away,
            "score": {"ft": list(ft)} if ft is not None else {}}


class ResearchDataTests(unittest.TestCase):
    def test_2016_and_current_season_included(self):
        years = seasons(date(2026, 10, 17))
        self.assertEqual(years[0], "2016-17")
        self.assertEqual(years[-1], "2026-27")
        self.assertEqual(len(years), 11)

    def test_strict_goals(self):
        self.assertEqual(valid_score([2, 0]), [2, 0])
        for score in ([True, 1], ["1", 2], [30, 0], [-1, 2], [1]):
            self.assertIsNone(valid_score(score))

    def test_only_finished_and_truly_future_eligible(self):
        today = date(2026, 10, 17)
        sample = {"matches": [
            game("2026-10-16", (2, 1)),
            game("2026-10-18", None, "C", "D"),
            game("2026-10-17", None, "E", "F"),
            game("2026-10-18", (1, 0), "G", "H"),  # impossible future final
        ]}
        finished, future = parse_source(sample, "nl.1", "2026-27", today)
        self.assertEqual(len(finished), 1)
        self.assertEqual(len(future), 1)
        self.assertEqual(future[0]["home"], "C")

    def test_playoff_rematches_different_days_permitted(self):
        source = {"matches": [
            game("2025-08-01", (1, 0)),
            game("2025-10-01", (3, 2)),
        ]}
        done, _ = parse_source(source, "be.1", "2025-26", date(2026, 10, 17))
        self.assertEqual(len(done), 2)
        self.assertNotEqual(done[0]["id"], done[1]["id"])

    def test_duplicate_fixture_same_day_is_rejected(self):
        source = {"matches": [game(), game()]}
        with self.assertRaises(ValueError):
            parse_source(source, "nl.1", "2016-17", date(2026, 10, 17))

    def test_first_full_then_incremental_without_new_games(self):
        today = date(2026, 10, 17)
        calls = []
        def fake_fetch(league, season):
            calls.append((league, season))
            if (league, season) == ("nl.1", "2016-17"):
                return {"matches": [game()]}, "mocked", "https://example.org/old"
            if (league, season) == ("nl.1", "2026-27"):
                return {"matches": [game("2026-10-16", (2, 0), "C", "D")]}, "mocked", "https://example.org/current"
            return None, "not_published", "https://example.org/unavailable"
        with tempfile.TemporaryDirectory() as temp:
            first = refresh(directory=temp, full=True, fetcher=fake_fetch, delay=0, today=today)
            self.assertEqual(len(first["matches"]), 2)
            self.assertEqual(len(first["new_final_match_ids"]), 2)
            self.assertEqual(len(calls), 11 * len(LEAGUES))
            calls.clear()
            second = refresh(directory=temp, fetcher=fake_fetch, delay=0, today=today)
            self.assertEqual(len(calls), 2 * len(LEAGUES))
            self.assertEqual(len(second["new_final_match_ids"]), 0)
            self.assertEqual(len(second["matches"]), 2)
            self.assertEqual(second["season_range"], ["2016-17", "2026-27"])
            self.assertEqual(
                len(json.loads((Path(temp) / "inventory.json").read_text())["matches"]), 2
            )

    def test_source_truncation_never_wipes_history(self):
        today = date(2026, 10, 17)
        matches = [
            game(f"2026-08-{d:02d}", (1, 1), f"A{d}", f"B{d}")
            for d in range(1, 14)
        ]
        small = [matches[0]]
        current = [matches]
        def fetch(league, season):
            if league == "nl.1" and season == "2026-27":
                return {"matches": current[0]}, "mocked", "https://example.org/scores"
            return None, "not_published", "https://example.org/404"
        with tempfile.TemporaryDirectory() as temp:
            initial = refresh(directory=temp, full=True, fetcher=fetch, delay=0, today=today)
            self.assertEqual(len(initial["matches"]), 13)
            current[0] = small
            revised = refresh(directory=temp, fetcher=fetch, delay=0, today=today)
            self.assertEqual(len(revised["matches"]), 13)
            self.assertTrue(any(x["key"] == "2026-27/nl.1" for x in revised["failed_sources"]))


if __name__ == "__main__":
    unittest.main()
