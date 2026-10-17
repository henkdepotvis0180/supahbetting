"""Offline native export format tests against observed upstream field names."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from supahbetting.fork_bridge import (
    BridgeError, canonical_team, load_export, normalize_export,
    numeric, parse_date, read_rows,
)


class BridgeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def _file(self, filename, content):
        path = self.dir / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_prophitbet_actual_fixtures_export_columns(self):
        # Exact fields from ProphitBet src/gui/windows/models/fixtures.py.
        file = self._file("fixtures.csv",
            "Home Team,Away Team,1,X,2,Predicted,Prob(1),Prob(X),Prob(2)\n"
            "Ajax,PSV,2.10,3.40,3.60,1,0.49,0.27,0.24\n")
        result = load_export(file, "prophitbet")
        self.assertEqual(result["rejected_rows"], 0)
        self.assertEqual(len(result["observations"]), 6)
        rows = result["observations"]
        self.assertEqual([x["market"] for x in rows if x["kind"] == "prediction"],
                         ["home", "draw", "away"])
        self.assertEqual([x["value"] for x in rows if x["kind"] == "odds"],
                         [2.1, 3.4, 3.6])
        self.assertEqual(rows[0]["event_key"], rows[-1]["event_key"])
        self.assertIn("undated:prophitbet:", rows[0]["event_key"])
        self.assertEqual(rows[3]["bookmaker"], "ProphitBet invoer (bookmaker onbekend)")
        self.assertEqual(rows[3]["observed_at"], "")

    def test_prophitbet_actual_manual_prediction_columns(self):
        file = self._file("manual.csv",
            "Date,Season,Week,Home,Away,1,X,2,Predicted,Prob(1),Prob(X),Prob(2)\n"
            "2026-10-19,2026,42,Feyenoord,AZ,1.80,3.70,4.20,1,0.52,0.26,0.22\n")
        result = load_export(file, "prophitbet")
        self.assertEqual(result["rejected_rows"], 0)
        self.assertEqual(result["observations"][0]["kickoff_date"], "2026-10-19")

    def test_odds_harvester_bookmakers_from_native_json(self):
        file = self._file("odds.json", json.dumps([{
            "match_date": "2026-10-19T20:00:00+02:00",
            "scraped_date": "2026-10-17T09:00:00+00:00",
            "home_team": "Ajax", "away_team": "PSV",
            "1x2_market": [
                {"bookmaker_name": "Bet A", "period": "FullTime",
                 "1": "2.10", "X": "3.40", "2": "3.60"},
                {"bookmaker_name": "Bet B", "period": "FullTime",
                 "1": "2.15", "X": "3.35", "2": "3.50",
                 "blocked_outcomes": ["2"]},
                {"bookmaker_name": "Half", "period": "FirstHalf",
                 "1": "1.8", "X": "3.1", "2": "4.2"},
            ],
        }]))
        result = load_export(file, "oddsharvester")
        self.assertEqual(result["rejected_rows"], 0)
        self.assertEqual(len(result["observations"]), 5)
        self.assertEqual(
            {x["bookmaker"] for x in result["observations"]},
            {"Bet A", "Bet B"}
        )
        self.assertEqual(result["observations"][0]["kickoff_date"], "2026-10-19")
        self.assertTrue(result["observations"][0]["observed_at"].endswith("+00:00"))

    def test_odds_harvester_csv_python_repr_nested_market(self):
        # LocalDataStorage serializes structured cells to text in a CSV.
        file = self.dir / "odds.csv"
        with file.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=[
                "match_date","scraped_date","home_team","away_team","1x2_market"
            ])
            writer.writeheader()
            writer.writerow({
                "match_date":"2026-10-19T18:00:00Z",
                "scraped_date":"2026-10-17T09:15:00Z",
                "home_team":"Ajax","away_team":"PSV",
                "1x2_market":repr([
                    {"bookmaker_name":"Quote X","period":"FullTime",
                     "1":"2.0","X":"3.0","2":"4.0"}
                ]),
            })
        result = load_export(file, "oddsharvester")
        self.assertEqual(len(result["observations"]), 3)

    def test_prediict_value_bets_csv_single_market(self):
        # Native columns from upstream data/value_bets_*.csv.
        file = self._file("value_bets.csv",
            "match,home_team,away_team,date,outcome,model_probability,bookmaker_odds,bookmaker_probability,edge,expected_value,kelly_stake_pct,confidence\n"
            "Ajax vs PSV,Ajax,PSV,2026-10-19 16:00:00+00:00,Home Win,0.51,2.15,0.46,0.05,0.09,2.0,0.51\n")
        out = load_export(file, "prediict")
        self.assertEqual(out["rejected_rows"], 0)
        self.assertEqual(len(out["observations"]), 2)
        self.assertEqual(out["observations"][0]["market"], "home")
        self.assertEqual(out["observations"][1]["bookmaker"],
                         "Prediict export (bookmaker niet gespecificeerd)")

    def test_prediict_full_model_probabilities(self):
        data = {
            "home_team":"FC Utrecht","away_team":"AZ",
            "date":"2026-10-20T18:00:00Z",
            "home_win_prob":0.5,"draw_prob":0.3,"away_win_prob":0.2
        }
        result = normalize_export("prediict",data,digest="abc",index=1,filename="pred.csv")
        self.assertEqual(len(result),3)
        self.assertAlmostEqual(sum(x["value"] for x in result),1.0)

    def test_wrong_probabilities_and_non_1x2_rejected(self):
        for raw in [
            {"Home Team":"A","Away Team":"B","Prob(1)":0.9,
             "Prob(X)":0.9,"Prob(2)":0.9},
            {"Home Team":"A","Away Team":"B","Prob(U)":0.4,"Prob(O)":0.6},
        ]:
            with self.subTest(raw=raw),self.assertRaises(BridgeError):
                normalize_export("prophitbet",raw,digest="abc",index=1,filename="f.csv")

    def test_csv_formula_in_team_is_text_not_executed(self):
        raw={"Home Team":"=HYPERLINK(1,2)", "Away Team":"PSV",
             "Prob(1)":0.5,"Prob(X)":0.25,"Prob(2)":0.25}
        rows=normalize_export("prophitbet",raw,digest="abc",index=1,filename="f.csv")
        self.assertIn("hyperlink",rows[0]["home_key"])
        self.assertEqual(rows[0]["kind"],"prediction")

    def test_invalid_market_string_cannot_execute_code(self):
        invalid="__import__('os').system('echo should_never_execute')"
        raw={"home_team":"A","away_team":"B","1x2_market":invalid}
        with self.assertRaises(BridgeError):
            normalize_export("oddsharvester",raw,digest="abc",index=1,filename="bad.csv")

    def test_utc_timezone_and_name_normalization(self):
        self.assertEqual(canonical_team("  Atlético   Madrid  "), "atletico madrid")
        self.assertEqual(parse_date("2026-10-19T01:00:00+02:00")[0],"2026-10-18")
        self.assertEqual(parse_date("19 oktober 2026"), ("",""))
        self.assertIsNone(numeric(float("nan")))

    def test_reject_oversized_unknown_formats(self):
        invalid=self._file("unknown.exe","hello")
        with self.assertRaises(BridgeError):
            read_rows(invalid)
        huge=self._file("huge.csv","A" * (3_000_000+1))
        with self.assertRaises(BridgeError):
            read_rows(huge)

    def test_json_bad_root_and_partial_rows(self):
        file=self._file("broken.json", json.dumps([{
            "home_team":"A","away_team":"B","outcome":"home win",
            "model_probability":0.55,"bookmaker_odds":2.0
        },{
            "home_team":"A","away_team":"A","outcome":"Draw",
            "model_probability":0.5,"bookmaker_odds":3.1
        }]))
        result=load_export(file,"prediict")
        self.assertEqual(result["rows"],2)
        self.assertEqual(result["rejected_rows"],1)
        self.assertEqual(len(result["observations"]),2)


if __name__=="__main__":
    unittest.main()
