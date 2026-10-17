"""Offline tests: no external datasets, account keys or ML runtime packages."""
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

from supahbetting.baseline_model import (
    BaselineError, FEATURES, CLASS_NAMES,
    empty_team, feature_vector, update_ratings,
    load_baseline, predict, public_status, team_key,
)
from supahbetting.train_baseline import (
    _date, _goals, _split_dates, make_examples, read_historical_csv,
)
from supahbetting.store import Store
from supahbetting.server import make_handler


def sample_artifact():
    return {
        "schema": "supahbetting-baseline-v1",
        "version": "0.7.0",
        "features": list(FEATURES),
        "classes": list(CLASS_NAMES),
        "scaler": {"mean": [0.0] * len(FEATURES),
                   "scale": [1.0] * len(FEATURES)},
        "weights": {
            "coef": [[0.4] + [0.0] * (len(FEATURES)-1),
                     [0.0] * len(FEATURES),
                     [-0.4] + [0.0] * (len(FEATURES)-1)],
            "intercept": [0.2, -0.1, -0.1],
        },
        "temperature": 1.0,
        "data_until": "2024-06-02",
        "training_matches": 1000,
        "teams": {
            "E0": {
                "arsenal": {"elo": 1600.0, "games": 25, "recent": [[3,2,0]]*7},
                "chelsea": {"elo": 1500.0, "games": 25, "recent": [[1,1,1]]*7},
            }
        },
        "metrics": {"holdout": {
            "games": 200, "accuracy": .52, "log_loss": 1.02,
            "brier_multiclass": .61,
        }},
        "source": "fictieve test",
    }


class HistoricalDataTests(unittest.TestCase):
    def test_parse_dates_and_goal_validation(self):
        self.assertEqual(_date("2026-10-16"),date(2026,10,16))
        self.assertEqual(_date("16/10/2026"),date(2026,10,16))
        self.assertIsNone(_date("not a date"))
        self.assertIsNone(_goals(99))
        self.assertIsNone(_goals("nan"))
        self.assertEqual(_goals("2.0"),2)

    def test_same_date_scores_not_in_pre_match_features(self):
        games=[
            (date(2024,1,1),"E0","arsenal","chelsea",3,0),
            (date(2024,1,1),"E0","arsenal","liverpool",0,3),
            (date(2024,1,2),"E0","arsenal","chelsea",2,1),
        ]
        x,y,days,states=make_examples(games)
        self.assertEqual(len(x),3)
        self.assertEqual(x[0],x[1])
        self.assertNotEqual(x[0],x[2])
        self.assertEqual(states["E0"]["arsenal"]["games"],3)

    def test_chronological_split_does_not_share_dates(self):
        days=[date(2024,1,1)+__import__("datetime").timedelta(days=i//4)
              for i in range(480)]
        train,val,test=_split_dates(days)
        self.assertTrue(max(days[i] for i in train)<min(days[i] for i in val))
        self.assertTrue(max(days[i] for i in val)<min(days[i] for i in test))

    def test_csv_training_input_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"training.csv"
            rows=["date,home_team,away_team,home_score,away_score,competition_code"]
            # 520 unique matches over 260 dates, plus a duplicate.
            for i in range(520):
                day=date(2023,1,1)+__import__("datetime").timedelta(days=i//2)
                rows.append(f"{day.isoformat()},A{i%4},B{i%5},2,1,E0")
            rows.append(rows[-1])
            file.write_text("\n".join(rows)+"\n",encoding="utf-8")
            matches,meta=read_historical_csv(file)
            self.assertEqual(len(matches),520)
            self.assertEqual(meta["duplicates"],1)
            self.assertTrue(all(m[1]=="E0" for m in matches))


class BaselineInferenceTests(unittest.TestCase):
    def test_valid_probabilities_and_known_teams(self):
        out=predict(sample_artifact(),"Arsenal","Chelsea","PL")
        self.assertTrue(all(out["teams_in_history"].values()))
        self.assertAlmostEqual(sum(out["probabilities"].values()),1,places=5)
        self.assertGreater(out["probabilities"]["home"],out["probabilities"]["away"])
        self.assertFalse(out["model_validated_profit"])
        self.assertIn("oud",out["warning"])

    def test_missing_team_is_explicit(self):
        result=predict(sample_artifact(),"Unknown AFC","Chelsea","PL")
        self.assertFalse(result["teams_in_history"]["home"])
        self.assertIn("ontbreken",result["warning"])

    def test_invalid_team_and_corrupted_json(self):
        with self.assertRaises(BaselineError):
            predict(sample_artifact(),"Arsenal","Arsenal","PL")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"model.json"
            path.write_text('{"schema":"supahbetting-baseline-v1"}',encoding="utf-8")
            with self.assertRaises(BaselineError):
                load_baseline(path)
            path.write_text(json.dumps(sample_artifact()),encoding="utf-8")
            loaded=load_baseline(path)
            self.assertEqual(public_status(loaded)["training_matches"],1000)

    def test_safe_runtime_model_has_no_import_of_sklearn(self):
        import sys
        import supahbetting.baseline_model
        self.assertFalse(hasattr(supahbetting.baseline_model,"LogisticRegression"))


class BaselineHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/"data.sqlite3"
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Store(self.db),baseline=sample_artifact()))
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def call(self,route,body=None):
        opts={}
        if body is not None:
            opts["data"]=json.dumps(body).encode("utf-8")
            opts["headers"]={"Content-Type":"application/json"}
            opts["method"]="POST"
        try:
            with urlopen(Request(self.url+route,**opts),timeout=5) as response:
                return response.status,json.loads(response.read())
        except HTTPError as e:
            return e.code,json.loads(e.read())

    def test_trained_model_status_and_prediction(self):
        status,payload=self.call("/api/model/status")
        self.assertEqual(status,200)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["trained_until"],"2024-06-02")
        status,payload=self.call("/api/model/predict",{
            "home_team":"Arsenal","away_team":"Chelsea","league":"PL"
        })
        self.assertEqual(status,200)
        self.assertIn("home",payload["probabilities"])
        self.assertEqual(payload["model_type"],"trained_statistical_baseline")

    def test_invalid_prediction_name(self):
        status,_=self.call("/api/model/predict",{
            "home_team":"A"*150,"away_team":"B","league":"PL"
        })
        self.assertEqual(status,400)
        status,_=self.call("/api/model/predict",{
            "home_team":"Arsenal","away_team":"Arsenal","league":"PL"
        })
        self.assertEqual(status,400)


if __name__=="__main__":
    unittest.main()
