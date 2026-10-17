"""True historical training, independent holdout and local model endpoint tests."""
from __future__ import annotations

import json
import math
import tempfile
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from supahbetting.server import make_handler
from supahbetting.store import Store
from supahbetting.trained_model import (
    LEAGUES, MODEL_FILE, PROVIDER_LEAGUES, TrainingError, LeagueRatings,
    label, load_matches, load_pretrained, norm, outcome_probabilities,
    predict_trained, run_sequential, score, season_groups, summarize,
)


class GoalBaselineTests(unittest.TestCase):
    def test_probability_sum_zero_and_normal(self):
        for home,away in [(0,0),(.5,1),(1.7,1.2),(4.5,4.5)]:
            p=outcome_probabilities(home,away)
            self.assertAlmostEqual(sum(p.values()),1,places=10)
            self.assertTrue(all(0 <= x <= 1 for x in p.values()))
        self.assertAlmostEqual(outcome_probabilities(0,0)["draw"],1,places=10)

    def test_home_advantage_and_team_updates(self):
        state=LeagueRatings(alpha=.15,prior_matches=8)
        before=state.predict_goals("A","B")
        self.assertGreater(before[0],before[1])
        state.update({"home":"A","away":"B","hg":4,"ag":0,
                      "date":"2024-01-01"})
        after=state.predict_goals("A","B")
        self.assertGreater(after[0], before[0])
        self.assertLess(after[1], before[1])
        self.assertEqual(state.teams["A"]["matches_total"],1)

    def test_season_regression_after_missing_years(self):
        state=LeagueRatings()
        state.season_boundary("2020-21")
        state.update({"home":"A","away":"B","hg":4,"ag":1,
                      "date":"2020-10-01"})
        old=state.teams["A"]["attack"]
        state.season_boundary("2024-25")
        self.assertLess(state.teams["A"]["attack"],old)
        self.assertGreaterEqual(state.teams["A"]["attack"],1.33)

    def test_simultaneous_matches_are_scored_before_same_day_updates(self):
        data=[
            {"league":"nl.1","season":"2024-25","date":"2024-10-10",
             "home":"Team A","away":"Team B","hg":1,"ag":0},
            {"league":"nl.1","season":"2024-25","date":"2024-10-10",
             "home":"Team A","away":"Team B","hg":0,"ag":1},
        ]
        _,metrics,_=run_sequential(data,.15,9,{"2024-25"})
        initial=outcome_probabilities(1.50,1.18)
        expected=sum(score(initial,m)[0] for m in data)
        self.assertAlmostEqual(metrics["2024-25"]["brier_sum"],expected,places=8)

    def test_scores_are_proper_and_finite(self):
        m={"home":"A","away":"B","hg":0,"ag":1}
        p={"home":.2,"draw":.3,"away":.5}
        brier,loss=score(p,m)
        self.assertAlmostEqual(brier,.38)
        self.assertAlmostEqual(loss,-math.log(.5))
        self.assertEqual(label(m),"away")

    def test_normalization_no_fuzzy_name_matching(self):
        self.assertEqual(norm(" Atlético  Madrid "), "atletico madrid")
        self.assertNotEqual(norm("ajax"),norm("ajax 2"))

    def test_real_public_domain_scores_and_seasons(self):
        data=load_matches()
        self.assertEqual(len(data),19884)
        self.assertEqual({m["league"] for m in data},set(LEAGUES))
        self.assertTrue(all(m["date"]<=date(2026,10,17).isoformat() for m in data))
        self.assertTrue(all(m["hg"]>=0 and m["ag"]>=0 for m in data))
        self.assertEqual(
            sum(x["season"]=="2025-26" for x in data),2037
        )
        self.assertEqual(
            sum(x["season"]=="2026-27" for x in data),295
        )
        self.assertEqual(max(x["date"] for x in data), "2026-09-20")
        # Older seasons extend the training context but never today's data.
        older = [r for r in data if r["season"] in ("2017-18","2018-19","2019-20")]
        self.assertEqual(len(older), 6417)
        self.assertEqual(sum(r["season"]=="2017-18" for r in older),1826)
        provenance=json.loads(Path("data/historical/provenance_pre2020.json").read_text())
        self.assertEqual(provenance["additional_rows"],len(older))
        self.assertEqual(provenance["expected_total_rows"],len(data))
        self.assertEqual(len(provenance["source_files"]),19)
        self.assertTrue(all(m["date"]<="2020-08-31" for m in older))

        self.assertEqual(
            sum(x["season"]=="2026-27" and x["league"]=="nl.1" for x in data),62
        )


    def test_trained_model_contains_real_scores_and_diagnostics(self):
        model=load_pretrained()
        self.assertEqual(model["training_matches"],19884)
        self.assertEqual(model["added_older_results"],6417)
        self.assertEqual(model["source"]["older_season_provenance_file"],
                         "data/historical/provenance_pre2020.json")
        self.assertEqual(model["source"]["license"],"CC0 1.0 Universal")
        self.assertFalse(model["source"]["uses_shot_xg"])
        self.assertEqual(model["parameters"]["holdout_season"],"2025-26")
        self.assertEqual(model["evaluation"]["test"]["matches"],2037)
        self.assertLess(model["evaluation"]["test"]["model_logloss"],1.2)
        self.assertEqual(set(model["leagues"]),set(LEAGUES))
        self.assertTrue(model["evaluation"]["by_league"]["be.1"]["test_incomplete_or_stale"])
        # Never select alpha or shrinkage based on the prospective current season.
        self.assertTrue(model["parameters"]["prospective_not_used_in_selection"])
        self.assertEqual(model["parameters"]["prospective_season"], "2026-27")
        self.assertEqual(model["prospective_matches"], 295)
        self.assertEqual(model["last_observed_result_date"], "2026-09-20")
        self.assertEqual(model["evaluation"]["prospective_2026_27"]["matches"], 295)
        self.assertEqual(
            model["evaluation"]["by_league"]["be.1"]["prospective_2026_27"]["matches"],0
        )

    def test_eredivisie_predictions_and_aliases(self):
        model=load_pretrained()
        x=predict_trained(model,"nl.1","Ajax","PSV")
        self.assertEqual(x["home_team"],"AFC Ajax")
        self.assertEqual(x["away_team"],"PSV")
        self.assertGreater(x["expected_goals_home"],0)
        self.assertAlmostEqual(sum(x["probabilities"].values()),1,places=5)
        self.assertIn("geen schot-xG",x["disclaimer"])
        self.assertTrue(x["data_through"].startswith("2026"))

    def test_unrecognized_teams_and_leagues_are_not_silently_guessed(self):
        model=load_pretrained()
        with self.assertRaises(TrainingError):
            predict_trained(model,"nl.1","Ajax jeugd","PSV")
        with self.assertRaises(TrainingError):
            predict_trained(model,"nl.1","Ajax","Ajax")
        with self.assertRaises(TrainingError):
            predict_trained(model,"does-not-exist","Ajax","PSV")

    def test_live_provider_league_mappings(self):
        self.assertEqual(PROVIDER_LEAGUES["sportsdb"]["4337"],"nl.1")
        self.assertEqual(PROVIDER_LEAGUES["sportsdb"]["4338"],"be.1")
        self.assertEqual(PROVIDER_LEAGUES["football-data"]["DED"],"nl.1")
        self.assertEqual(PROVIDER_LEAGUES["openliga"]["bl1"],"de.1")


class ModelApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory()
        cls.model=load_pretrained()
        cls.httpd=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Store(Path(cls.folder.name)/"data.db"),trained=cls.model))
        cls.httpd.daemon_threads=True
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()
        cls.url="http://127.0.0.1:"+str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.folder.cleanup()

    def query(self,path,payload=None):
        opts={}
        if payload is not None:
            opts["method"]="POST"
            opts["data"]=json.dumps(payload).encode("utf-8")
            opts["headers"]={"Content-Type":"application/json"}
        try:
            with urlopen(Request(self.url+path,**opts),timeout=5) as r:
                return r.status,json.loads(r.read())
        except HTTPError as exc:
            return exc.code,json.loads(exc.read())

    def test_status_exposes_metrics_without_full_team_table(self):
        status,response=self.query("/api/trained/status")
        self.assertEqual(status,200)
        self.assertTrue(response["available"])
        self.assertEqual(response["training_matches"],19884)
        self.assertNotIn("team_records",response["leagues"]["nl.1"])
        self.assertGreater(response["leagues"]["nl.1"]["teams"],10)

    def test_known_teams_return_trained_1x2_probabilities(self):
        status,response=self.query("/api/trained/predict",{
            "provider":"sportsdb","league":"4337",
            "home_team":"Ajax","away_team":"PSV"
        })
        self.assertEqual(status,200)
        self.assertEqual(response["league"],"nl.1")
        self.assertAlmostEqual(sum(response["probabilities"].values()),1,places=5)
        self.assertNotIn("bookmaker_odds",response)

    def test_unknown_teams_and_unmapped_competitions_refused(self):
        for body in (
            {"provider":"sportsdb","league":"4337","home_team":"Imaginary FC","away_team":"Ajax"},
            {"provider":"sportsdb","league":"unknown","home_team":"Ajax","away_team":"PSV"},
            {"league":"nl.1","home_team":"Ajax","away_team":"Ajax"},
        ):
            status,_=self.query("/api/trained/predict",body)
            self.assertEqual(status,400)

if __name__=="__main__":
    unittest.main()
