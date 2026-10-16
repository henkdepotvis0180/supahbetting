import json
import tempfile
import unittest
from pathlib import Path

from supahbetting.domain import ValidationError
from supahbetting.importers import import_matches
from supahbetting.store import Store


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.store = Store(self.directory / "db.sqlite3")

    def test_json_import_and_bad_row(self):
        path = self.directory / "matches.json"
        path.write_text(json.dumps([
            {"home_team": "A", "away_team": "B", "kickoff": "",
             "home_xg": 1.5, "away_xg": 1.2,
             "odds_home": 2.2, "odds_draw": 3.3, "odds_away": 3.6,
             "source": "test"},
            {"home_team": "Missing", "away_team": "NoData"}
        ]), encoding="utf-8")
        result = import_matches(self.store, path)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(len(self.store.list_matches()), 1)

    def test_csv_import(self):
        path = self.directory / "matches.csv"
        path.write_text("home_team,away_team,kickoff,home_xg,away_xg,odds_home,odds_draw,odds_away,source\n"
                        "C,D,,1.3,1.1,2.2,3.2,3.5,manual\n", encoding="utf-8")
        result = import_matches(self.store, path)
        self.assertEqual(result["imported"], 1)

    def test_unknown_extension(self):
        path = self.directory / "matches.txt"
        path.write_text("not-csv", encoding="utf-8")
        with self.assertRaises(ValidationError):
            import_matches(self.store, path)


if __name__ == "__main__":
    unittest.main()
