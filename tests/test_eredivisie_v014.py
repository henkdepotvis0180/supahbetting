"""v0.14 offline Eredivisie score, historical CSV and model-integrity gates."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from supahbetting.research_nl_api import (
    season_year,validate_eredivisie_payload,confirmed_results,refresh_nl_api,
)
from supahbetting.research_nl_csv import parse_csv,import_local_csv
from supahbetting.research_nl_bootstrap import bootstrap
from supahbetting.research_daily_results import merge_verified_locally
from supahbetting.research_upcoming import PUBLISHED_MODEL
from supahbetting.trained_model import load_pretrained

NOW=datetime(2026,10,17,17,30,tzinfo=timezone.utc)
MODEL=load_pretrained(PUBLISHED_MODEL)


def entry(match_id,day="2026-10-16T18:00:00Z",home="Ajax",away="PSV",
          hg=2,ag=1,status="FINISHED"):
    return {
        "id":match_id,"utcDate":day,"status":status,"competition":{"code":"DED"},
        "homeTeam":{"name":home},"awayTeam":{"name":away},
        "score":{"fullTime":{"home":hg,"away":ag}},
    }


def source(*records):
    return {"competition":{"code":"DED"},"matches":list(records)}


def csv_text(*rows):
    return ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"+
            "\n".join(",".join(map(str,row)) for row in rows)+"\n").encode()


class FakeProvider:
    enabled=True
    def __init__(self,reply,stale=False):
        self.reply=reply
        self.stale=stale
        self.requested=[]
    def _cached(self,path,ttl):
        self.requested.append((path,ttl))
        return self.reply,"2026-10-17T17:30:00Z",self.stale,None


class MissingProvider:
    enabled=False
    def _cached(self,path,ttl):
        raise AssertionError("Must not call private API without a token")


class DutchApiTests(unittest.TestCase):
    def test_2026_27_api_request_is_full_season(self):
        self.assertEqual(season_year(NOW),2026)
        with tempfile.TemporaryDirectory() as tmp:
            result=refresh_nl_api(now=NOW,data_dir=tmp,provider=MissingProvider())
            self.assertEqual(result["status"],"no_api_key")
            self.assertEqual(result["code"],"DED")
            self.assertEqual(json.loads((Path(tmp)/"nl_update_status.json").read_text())["status"],
                             "no_api_key")

    def test_only_real_finished_results_after_kickoff(self):
        data=source(
            entry(101),
            entry(102,day="2026-10-18T14:00:00Z",status="SCHEDULED"),
            entry(103,day="2026-10-17T17:00:00Z"),
            entry(104,hg="3",ag=1),
            entry(105,hg=None,ag=None),
        )
        parsed=confirmed_results(data,now=NOW,season=2026)
        self.assertEqual(len(parsed),1)
        self.assertEqual(parsed[0]["source_id"],"101")
        self.assertTrue(parsed[0]["source_confirmed"])
        self.assertEqual([parsed[0]["hg"],parsed[0]["ag"]],[2,1])

    def test_rejects_other_competitions_and_wrong_season(self):
        with self.assertRaises(ValueError):
            confirmed_results(
                {"competition":{"code":"PL"},"matches":[entry(1)]},
                now=NOW,season=2026)
        with self.assertRaises(ValueError):
            confirmed_results(
                source(entry(1,day="2024-10-16T18:00:00Z")),
                now=NOW,season=2026)

    def test_stale_api_never_trains_or_imports(self):
        class Bad:
            enabled=True
            def _cached(self,p,t):
                return source(entry(101)),"old",True,"provider timeout"
        with tempfile.TemporaryDirectory() as tmp:
            state=refresh_nl_api(now=NOW,data_dir=tmp,provider=Bad(),
                                 inventory={"matches":[]},model=MODEL)
            self.assertEqual(state["status"],"stale_api_cache")
            self.assertFalse((Path(tmp)/"provider_finals_local.json").exists())

    def test_full_season_result_goes_into_validated_local_retrain(self):
        matches=[{
            "id":"sample-"+str(i),"league":"nl.1","season":"2025-26",
            "date":"2025-09-01","home":"Ajax","away":"PSV","hg":1,"ag":0
        } for i in range(1001)]
        fake=FakeProvider(source(entry(333)))
        with tempfile.TemporaryDirectory() as tmp:
            def collect(items,model,now,path,max_age_days):
                self.assertEqual(max_age_days,380)
                self.assertEqual(len(items),1)
                self.assertEqual(items[0]["source_id"],"333")
                return {"new":1,"conflicted":0}
            def rebuilt(inventory,folder):
                return MODEL,{"retrained":True,"provider_conflicts_with_cc0":0}
            with patch("supahbetting.research_nl_api.collect_verified_finals",collect),patch(
                    "supahbetting.research_nl_api.rebuild_augmented_if_needed",rebuilt):
                state=refresh_nl_api(
                    now=NOW,data_dir=tmp,provider=fake,model=MODEL,
                    inventory={"matches":matches})
            self.assertEqual(fake.requested,
                [("/v4/competitions/DED/matches?season=2026",1800)])
            self.assertEqual(state["new_confirmed"],1)
            self.assertTrue(state["model_retrained"])


class DutchCSVTests(unittest.TestCase):
    def test_2016_results_and_only_valid_scores(self):
        data=csv_text(
            ("N1","17/01/2016","Ajax","PSV",2,1,"H"),
            ("N1","17/10/2026","Ajax","PSV",0,1,"A"), # same-day unverified
            ("N1","16/10/2026","Ajax","PSV",2,1,"A"), # mismatched FTR
            ("E0","16/10/2026","Chelsea","Arsenal",2,1,"H"),
            ("N1","16/10/2026","Ajax","PSV",3,0,"H"),
        )
        rows,skipped=parse_csv(data,now=NOW)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["date"],"2016-01-17")
        self.assertEqual(rows[0]["season"],"2015-16")
        self.assertEqual(rows[1]["date"],"2026-10-16")
        self.assertEqual(rows[1]["home"],"AFC Ajax")
        self.assertGreaterEqual(skipped["outside_date"],1)
        self.assertGreaterEqual(skipped["not_full_time"],1)

    def test_no_network_used_and_files_stay_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"inbox"
            folder.mkdir()
            source_path=folder/"N1-2016-17.csv"
            source_path.write_bytes(csv_text(
                ("N1","21/08/2016","Twente","Feyenoord",1,2,"A")))
            result=import_local_csv(
                folder=folder,output=Path(tmp)/"local_data.json",now=NOW)
            self.assertEqual(result["imported_matches"],1)
            saved=json.loads((Path(tmp)/"local_data.json").read_text())
            self.assertEqual(saved["matches"][0]["home"],"FC Twente '65")
            self.assertEqual(saved["matches"][0]["away"],"Feyenoord Rotterdam")
            self.assertEqual(saved["sources"][0]["source_claim"],
                             "user_supplied_csv; origin not independently proven")
            self.assertNotIn("api_key",json.dumps(saved))

    def test_score_conflict_between_csvs_is_quarantined(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"files"
            folder.mkdir()
            (folder/"a.csv").write_bytes(csv_text(
                ("N1","21/08/2016","Twente","Feyenoord",1,2,"A")))
            (folder/"b.csv").write_bytes(csv_text(
                ("N1","21/08/2016","Twente","Feyenoord",0,3,"A")))
            out=Path(tmp)/"merged.json"
            state=import_local_csv(folder=folder,output=out,now=NOW)
            self.assertGreater(state.get("conflicts",0),0)

    def test_model_merge_no_double_count_and_cross_source_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=[{
                "id":str(i),"league":"nl.1","season":"2018-19",
                "date":"2018-08-10","home":f"Club A{i}",
                "away":f"Club B{i}","hg":1,"ag":0
            } for i in range(1001)]
            manual={
                "matches":[
                    {**base[0],"home":"Club A0","away":"Club B0"},  # exact duplicate
                    {"id":"older","league":"nl.1","season":"2015-16",
                     "date":"2016-01-17","home":"Ajax","away":"PSV",
                     "hg":2,"ag":1},
                ],
            }
            csv_file=Path(tmp)/"csv.json"
            csv_file.write_text(json.dumps(manual))
            api_file=Path(tmp)/"api.json"
            api_file.write_text(json.dumps({"finished":[
                {"id":"conflict","league":"nl.1","season":"2015-16",
                 "date":"2016-01-17","home":"Ajax","away":"PSV",
                 "hg":3,"ag":1}
            ]}))
            merged,coverage=merge_verified_locally(
                {"matches":base},finals_path=api_file,csv_path=csv_file)
            self.assertEqual(len(merged["matches"]),len(base))
            self.assertEqual(coverage["provider_quarantined_matches"],1)
            self.assertEqual(coverage["manual_csv_extra_matches"],0)
            self.assertEqual(coverage["duplicate_scores_skipped"],1)

    def test_reject_missing_fields_and_future(self):
        with self.assertRaises(ValueError):
            parse_csv(b"Date,HomeTeam,AwayTeam\n17/01/2016,A,B\n",now=NOW)
        scores,skipped=parse_csv(
            csv_text(("N1","18/10/2026","Ajax","PSV",1,0,"H")),now=NOW)
        self.assertEqual(scores,[])
        self.assertEqual(skipped["outside_date"],1)


class BootstrapTests(unittest.TestCase):
    def test_checked_in_licensed_verified_files_bootstrap_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=bootstrap(directory=tmp)
            self.assertEqual(result["state"],"created")
            self.assertGreater(result["matches"],12000)
            repeated=bootstrap(directory=tmp)
            self.assertEqual(repeated["state"],"existing")
            snapshot=json.loads((Path(tmp)/"inventory.json").read_text())
            self.assertEqual(snapshot["license"],"CC0-1.0")
            self.assertGreater(len(snapshot["matches"]),12000)


if __name__=="__main__":
    unittest.main()
