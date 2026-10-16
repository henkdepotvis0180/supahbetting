import tempfile
import unittest
from pathlib import Path

from supahbetting.domain import ValidationError
from supahbetting.store import Store


def match(name):
    return {
        "home_team": f"{name} thuis", "away_team": f"{name} uit",
        "home_xg": 1.5, "away_xg": 1.0,
        "odds_home": 2.2, "odds_draw": 3.3, "odds_away": 3.4,
        "source": "TEST",
    }


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "db.sqlite3")

    def test_empty_store(self):
        self.assertEqual(self.store.list_matches(), [])
        self.assertEqual(self.store.list_slips(), [])
        self.assertEqual(self.store.stats()["total"], 0)
        self.assertEqual(self.store.stats()["open_stake"], 0)

    def test_demo_is_repeatable(self):
        self.assertEqual(self.store.seed_demo()["created"], 4)
        self.assertEqual(self.store.seed_demo()["created"], 0)
        self.assertEqual(len(self.store.list_matches()), 4)

    def test_single_winning_selection(self):
        m = self.store.add_match(match("Test"))
        slip = self.store.create_slip([{"match_id": m["id"], "market": "home"}], 10)
        self.assertEqual(slip["status"], "open")
        self.assertAlmostEqual(slip["potential_payout"], 22)
        self.store.settle_match(m["id"], 2, 0)
        settled = self.store.get_slip(slip["id"])
        self.assertEqual(settled["status"], "won")
        self.assertAlmostEqual(settled["profit"], 12)
        stats = self.store.stats()
        self.assertAlmostEqual(stats["realized_profit"], 12)
        self.assertAlmostEqual(stats["realized_roi"], 1.2)

    def test_two_leg_winning_accumulator(self):
        m1 = self.store.add_match(match("A"))
        m2 = self.store.add_match(match("B"))
        slip = self.store.create_slip([
            {"match_id": m1["id"], "market": "home"},
            {"match_id": m2["id"], "market": "away"},
        ], 5)
        self.assertAlmostEqual(slip["combined_odds"], 2.2 * 3.4)
        self.assertEqual(slip["status"], "open")
        self.store.settle_match(m1["id"], 1, 0)
        self.assertEqual(self.store.get_slip(slip["id"])["status"], "open")
        self.store.settle_match(m2["id"], 0, 1)
        self.assertEqual(self.store.get_slip(slip["id"])["status"], "won")

    def test_early_losing_accumulator(self):
        m1 = self.store.add_match(match("A"))
        m2 = self.store.add_match(match("B"))
        slip = self.store.create_slip([
            {"match_id": m1["id"], "market": "home"},
            {"match_id": m2["id"], "market": "away"},
        ], 8)
        self.store.settle_match(m1["id"], 0, 1)
        self.assertEqual(self.store.get_slip(slip["id"])["status"], "lost")
        self.assertEqual(self.store.get_slip(slip["id"])["profit"], -8)
        self.store.settle_match(m2["id"], 0, 1)
        self.assertEqual(self.store.get_slip(slip["id"])["status"], "lost")

    def test_slip_snapshots_not_client_prices(self):
        m = self.store.add_match(match("Trusted"))
        s = self.store.create_slip([{"match_id": m["id"], "market": "home",
                                    "decimal_odds": 100, "probability": 1}], 5)
        self.assertAlmostEqual(s["combined_odds"], 2.2)
        self.assertAlmostEqual(s["legs"][0]["odds_snapshot"], 2.2)

    def test_duplicate_match_and_settled_match_rejected(self):
        m = self.store.add_match(match("A"))
        with self.assertRaisesRegex(ValidationError, "dezelfde wedstrijd"):
            self.store.create_slip([
                {"match_id": m["id"], "market": "home"},
                {"match_id": m["id"], "market": "draw"},
            ], 5)
        self.store.settle_match(m["id"], 1, 0)
        with self.assertRaises(ValidationError):
            self.store.create_slip([{"match_id": m["id"], "market": "home"}], 5)
        with self.assertRaises(ValidationError):
            self.store.settle_match(m["id"], 1, 0)

    def test_invalid_goals(self):
        m = self.store.add_match(match("A"))
        for values in [(True, 0), (1.5, 0), (-1, 0), (0, 101)]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.store.settle_match(m["id"], *values)


if __name__ == "__main__":
    unittest.main()
