"""Deterministic, network-free upcoming match + pre-match forecast integration."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from supahbetting.external_feeds import ProviderHTTPFailure

from supahbetting.research_upcoming import (
    _normalize, _evaluate, _from_archived_fixture, _merge_key, build_upcoming,
    fetch_provider_schedules, refresh_upcoming, _load_model,
)

NOW = datetime(2026,10,17,13,0,0,tzinfo=timezone.utc)
KICKOFF = (NOW+timedelta(days=2)).isoformat(timespec="seconds")
RAW_MODEL = _load_model("supahbetting/models/research_v0.12.0_experimental.json")


def fixture(name="Ajax", away="PSV", provider="football-data", identifier="1212"):
    return {
        "provider":provider,"source_id":identifier,"league":"nl.1",
        "league_name":"Eredivisie","home":name,"away":away,
        "date":"2026-10-19","kickoff":KICKOFF,
        "source_confirmed":True,"status":"scheduled",
        "hg":None,"ag":None,
        "source_url":"https://www.football-data.org/"
    }


class UpcomingTests(unittest.TestCase):
    def test_active_research_model_is_valid(self):
        self.assertIsNotNone(RAW_MODEL)
        self.assertEqual(RAW_MODEL["version"], "0.12.0-research-experimental")

    def test_confirmed_future_kickoff_has_1x2_probabilities(self):
        pred, reason=_evaluate(fixture(),RAW_MODEL,NOW)
        self.assertIsNone(reason)
        self.assertEqual(pred["model_version"],"0.12.0-research-experimental")
        self.assertAlmostEqual(sum(pred["probabilities"].values()),1,places=4)
        self.assertEqual(pred["data_through"],"2026-09-20")
        self.assertGreater(pred["model_age_days"],20)
        self.assertIn("achterstand",pred["data_warning"])

    def test_no_guessed_club_or_started_match(self):
        future=fixture(name="Nonexistent Football XI")
        pred, why=_evaluate(future,RAW_MODEL,NOW)
        self.assertIsNone(pred)
        self.assertIn("niet betrouwbaar",why)
        old=fixture()
        old["kickoff"]=(NOW-timedelta(seconds=10)).isoformat()
        pred, why=_evaluate(old,RAW_MODEL,NOW)
        self.assertIsNone(pred)

    def test_archived_schedule_never_claimed_confirmed(self):
        archive={"id":"old","league":"nl.1","season":"2026-27",
                 "date":"2026-10-20","home":"Ajax","away":"PSV"}
        normalized=_from_archived_fixture(archive,NOW,15)
        self.assertFalse(normalized["source_confirmed"])
        pred, why=_evaluate(normalized,RAW_MODEL,NOW)
        self.assertIsNone(pred)
        self.assertIn("archiefschema",why)

    def test_no_same_day_prediction_without_kickoff(self):
        raw={"status":"scheduled","id":1,"home_team":"Ajax",
             "away_team":"PSV","kickoff":None,
             "kickoff_source_local":"2026-10-17 20:00"}
        self.assertIsNone(_normalize(raw,"sportsdb","nl.1",NOW))
        raw["kickoff_source_local"]="2026-10-19 20:00"
        self.assertIsNotNone(_normalize(raw,"sportsdb","nl.1",NOW))

    def test_rejects_bogus_finished_score_or_unverified_match(self):
        raw={"status":"finished","id":1,"home_team":"Ajax",
             "away_team":"PSV",
             "kickoff":(NOW-timedelta(days=1)).isoformat(),
             "score_home":None,"score_away":2}
        self.assertIsNone(_normalize(raw,"sportsdb","nl.1",NOW))
        raw["score_home"]=2
        self.assertEqual(_normalize(raw,"sportsdb","nl.1",NOW)["hg"],2)

    def test_provider_priority_avoids_duplicates_for_exact_verified_teams(self):
        with tempfile.TemporaryDirectory() as d:
            a=fixture(provider="sportsdb")
            a["source_url"]="https://www.thesportsdb.com/"
            b=fixture(provider="football-data",identifier="99")
            report=build_upcoming(
                model=RAW_MODEL,now=NOW,fetched=[a,b],
                inventory={"fixtures":[]},
                output=Path(d)/"upcoming.json",
                forecast_log=Path(d)/"frozen.json",
            )
            self.assertEqual(report["schedule_count"],1)
            self.assertEqual(report["fixtures"][0]["provider"],"football-data")
            self.assertEqual(report["predicted_count"],1)
            self.assertEqual(report["prospective_evaluation"]["new_snapshots"],1)

    def test_forecast_is_frozen_then_graded_only_after_real_result(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/"log.json"
            out=Path(d)/"upcoming.json"
            prepared=build_upcoming(
                model=RAW_MODEL,now=NOW,fetched=[fixture()],inventory={"fixtures":[]},
                output=out, forecast_log=log,
            )
            self.assertEqual(prepared["prospective_evaluation"]["graded_total"],0)
            snap=json.loads(log.read_text())["forecasts"]["football-data/1212"]
            finished={**fixture(),"status":"finished","hg":1,"ag":0}
            future=NOW+timedelta(days=3)
            latest=build_upcoming(
                model=RAW_MODEL,now=future,fetched=[finished],inventory={"fixtures":[]},
                output=out,forecast_log=log
            )
            self.assertEqual(latest["prospective_evaluation"]["graded_total"],1)
            archived=json.loads(log.read_text())["forecasts"]["football-data/1212"]
            self.assertEqual(snap["created_at_utc"],archived["created_at_utc"])
            self.assertEqual(snap["prediction"],archived["prediction"])
            self.assertGreater(archived["result"]["logloss"],0)

    def test_reschedule_does_not_grade_old_forecast(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/"log.json"
            output=Path(d)/"view.json"
            build_upcoming(model=RAW_MODEL,now=NOW,fetched=[fixture()],
                           inventory={"fixtures":[]},output=output,forecast_log=log)
            final={**fixture(),"status":"finished","hg":3,"ag":2,
                   "kickoff":(NOW+timedelta(days=4)).isoformat()}
            state=build_upcoming(
                model=RAW_MODEL,now=NOW+timedelta(days=6),fetched=[final],
                inventory={"fixtures":[]},output=output,forecast_log=log)
            self.assertEqual(state["prospective_evaluation"]["graded_total"],0)
            self.assertEqual(state["prospective_evaluation"]["new_void"],1)

    def test_provider_scan_respects_throttled_five_requests_per_active_league(self):
        requests=[]
        class DisabledFootball:
            enabled=False
        class EmptyOpenliga:
            def list_matches(self,league):
                return {"matches":[]}
        def source(path):
            requests.append(path)
            return {"events":[]}
        items,warnings=fetch_provider_schedules(
            now=NOW,football_data=DisabledFootball(),
            sports_fetcher=source,openliga=EmptyOpenliga(),pause=0,knvb_fetcher=lambda **kw:([],[]))
        self.assertEqual(items,[])
        self.assertEqual(len(requests),30)
        self.assertTrue(any("API-token" in warning for warning in warnings))

    def test_sportsdb_403_stops_immediately_but_openliga_fallback_continues(self):
        called=[]
        class DisabledFootball:
            enabled=False
        class StubOpenliga:
            def __init__(self):
                self.called=[]
            def list_matches(self,league):
                self.called.append(league)
                return {"matches":[]}
        independent=StubOpenliga()
        def block(route):
            called.append(route)
            raise ProviderHTTPFailure("sportsdb", 403)
        items,warnings=fetch_provider_schedules(
            now=NOW, football_data=DisabledFootball(),sports_fetcher=block,
            openliga=independent,pause=0,knvb_fetcher=lambda **kw:([],[])
        )
        self.assertEqual(items,[])
        self.assertEqual(len(called),1,"No 30-request storm after HTTP denial")
        self.assertGreater(len(independent.called),0,
                           "Independent provider must still be queried")
        self.assertTrue(any("HTTP 403" in value for value in warnings))
        self.assertTrue(any("volgende ronde" in value for value in warnings))

    def test_sportsdb_429_is_rate_limited_without_extra_calls(self):
        called=[]
        class DisabledFootball:
            enabled=False
        class StubOpenliga:
            def list_matches(self,league):
                return {"matches":[]}
        def throttle(route):
            called.append(route)
            raise ProviderHTTPFailure("sportsdb",429)
        _, warnings=fetch_provider_schedules(
            now=NOW, football_data=DisabledFootball(),
            sports_fetcher=throttle,openliga=StubOpenliga(),pause=0,knvb_fetcher=lambda **kw:([],[])
        )
        self.assertEqual(len(called),1)
        self.assertTrue(any("HTTP 429" in value for value in warnings))
        self.assertTrue(any("rate limit" in value for value in warnings))

    def test_sportsdb_offline_network_error_stops_quickly(self):
        called=[]
        class DisabledFootball:
            enabled=False
        class StubOpenliga:
            def list_matches(self,league):
                return {"matches":[]}
        def offline(route):
            called.append(route)
            raise OSError("network unavailable")
        _,warnings=fetch_provider_schedules(
            now=NOW,football_data=DisabledFootball(),
            sports_fetcher=offline,openliga=StubOpenliga(),pause=0,knvb_fetcher=lambda **kw:([],[])
        )
        self.assertEqual(len(called),1)
        self.assertTrue(any("TheSportsDB" in value for value in warnings))

    def test_archive_fixtures_are_not_misrepresented_as_real_upcoming_games(self):
        with tempfile.TemporaryDirectory() as d:
            data={"fixtures":[{"id":"archive-1","league":"nl.1",
               "date":"2026-10-20","season":"2026-27","home":"Ajax","away":"PSV"}]}
            result=refresh_upcoming(
                inventory=data,data_dir=d,now=NOW,model=RAW_MODEL,
                provider_fetcher=lambda **kw:([],["provider not available"]))
            self.assertEqual(result["schedule_count"],0)
            self.assertEqual(result["predicted_count"],0)
            self.assertEqual(result["provider_warnings"],["provider not available"])
            self.assertTrue((Path(d)/"upcoming_predictions.json").is_file())


if __name__=="__main__":
    unittest.main()
