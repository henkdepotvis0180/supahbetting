"""Regressions for v0.14 user logs: DED route guard, 429, and startup survival."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from supahbetting import external_feeds
from supahbetting.external_feeds import (
    FootballData, ProviderHTTPFailure, fetch_bounded_json,
    provider_cooldown_seconds, provider_cooldown_status,
)
from supahbetting.live_scores import InvalidLiveRequest, LiveDataUnavailable
from supahbetting.research_nl_api import refresh_nl_api
from supahbetting.research_upcoming import (
    PUBLISHED_MODEL, fetch_provider_schedules, refresh_upcoming,
)
from supahbetting.trained_model import load_pretrained


NOW=datetime(2026,10,17,17,45,tzinfo=timezone.utc)
MODEL=load_pretrained(PUBLISHED_MODEL)


class StubResult:
    status=200
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,limit):
        return b'{"competition":{"code":"DED"},"matches":[]}'


class StubOpener:
    def __init__(self,code=None):
        self.code=code
        self.paths=[]
    def open(self,req,timeout):
        self.paths.append(req.full_url)
        if self.code:
            raise HTTPError(req.full_url,self.code,"blocked",{"Retry-After":"50"},None)
        return StubResult()


class RouteAndRetryTests(unittest.TestCase):
    def setUp(self):
        with external_feeds._PROVIDER_COOLDOWN_LOCK:
            external_feeds._PROVIDER_COOLDOWN.clear()
    def tearDown(self):
        with external_feeds._PROVIDER_COOLDOWN_LOCK:
            external_feeds._PROVIDER_COOLDOWN.clear()

    def test_legitimate_ded_season_request_passes_fixed_url_guard(self):
        opener=StubOpener()
        with patch("supahbetting.external_feeds.build_opener",return_value=opener):
            response=fetch_bounded_json(
                "/v4/competitions/DED/matches?season=2026",
                "football-data","secret-do-not-log",
            )
        self.assertEqual(response["competition"]["code"],"DED")
        self.assertEqual(len(opener.paths),1)
        self.assertEqual(opener.paths[0],
            "https://api.football-data.org/v4/competitions/DED/matches?season=2026")
        self.assertNotIn("secret-do-not-log",opener.paths[0])

    def test_path_guard_rejects_arbitrary_query_and_dangerous_path(self):
        for path in (
            "/v4/competitions/DED/matches?season=2026&extra=1",
            "/v4/competitions/DED/matches?season=abc",
            "/v4/competitions/DED/matches?season=2026%26foo",
            "/v4/competitions/../../secret?season=2026",
            "/v4/competitions/DED/matches?season=1999",
        ):
            with self.subTest(path=path),self.assertRaises(InvalidLiveRequest):
                fetch_bounded_json(path,"football-data","test-token")

    def test_rate_limit_status_and_retry_after_blocks_second_http_call(self):
        opener=StubOpener(code=429)
        with patch("supahbetting.external_feeds.build_opener",return_value=opener):
            with self.assertRaises(ProviderHTTPFailure) as first:
                fetch_bounded_json("/v4/competitions/DED/matches?season=2026",
                                   "football-data","local-test-token")
            self.assertEqual(first.exception.status_code,429)
            self.assertEqual(provider_cooldown_status("football-data"),429)
            self.assertGreaterEqual(provider_cooldown_seconds("football-data"),250)
            with self.assertRaises(ProviderHTTPFailure) as second:
                fetch_bounded_json("/v4/competitions/DED/matches?season=2026",
                                   "football-data","local-test-token")
            self.assertEqual(second.exception.status_code,429)
        self.assertEqual(len(opener.paths),1,"No new request during 429 cooldown")

    def test_live_cache_preserves_original_http_error_status(self):
        def exhausted(path):
            raise ProviderHTTPFailure("football-data",429)
        feed=FootballData(token="dummy",fetcher=exhausted)
        with self.assertRaises(ProviderHTTPFailure) as caught:
            feed._cached("/v4/competitions/DED/matches?season=2026",1800)
        self.assertEqual(caught.exception.status_code,429)

    def test_nl_refresh_never_crashes_on_live_data_unavailable(self):
        def offline(path):
            raise LiveDataUnavailable("No network")
        feed=FootballData(token="dummy",fetcher=offline)
        with tempfile.TemporaryDirectory() as tmp:
            state=refresh_nl_api(now=NOW,data_dir=tmp,provider=feed,
                                 model=MODEL,inventory={"matches":[]})
            self.assertEqual(state["status"],"provider_unavailable")
            self.assertFalse((Path(tmp)/"provider_finals_local.json").exists())
            self.assertTrue((Path(tmp)/"nl_update_status.json").exists())

    def test_nl_refresh_reports_throttled_not_crashed_and_keeps_data(self):
        def throttled(path):
            raise ProviderHTTPFailure("football-data",429)
        feed=FootballData(token="dummy",fetcher=throttled)
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/"provider_finals_local.json"
            original.write_text('{"finished":[],"conflicts":[]}',encoding="utf-8")
            state=refresh_nl_api(now=NOW,data_dir=tmp,provider=feed,
                                 model=MODEL,inventory={"matches":[]})
            self.assertEqual(state["status"],"rate_limited")
            self.assertEqual(state["http_status"],429)
            self.assertEqual(json.loads(original.read_text())["finished"],[])


class ScheduleFailoverTests(unittest.TestCase):
    def test_throttle_does_not_probe_six_more_competitions(self):
        paths=[]
        class LimitedFootball:
            enabled=True
            def list_matches(self,code):
                paths.append(code)
                raise ProviderHTTPFailure("football-data",429)
        class Openliga:
            def __init__(self):
                self.called=[]
            def list_matches(self,code):
                self.called.append(code)
                return {"matches":[]}
        openliga=Openliga()
        def empty_sportsdb(path):
            return {"events":[]}
        knvb={"provider":"knvb","source_id":"123","league":"nl.1",
            "league_name":"Eredivisie","home":"Ajax","away":"PSV",
            "status":"scheduled","source_confirmed":True,"date":"2026-10-18",
            "kickoff":"2026-10-18T12:00:00+00:00","hg":None,"ag":None,
            "source_url":"https://www.knvb.nl/competities/eredivisie/programma"}
        fetched,warnings=fetch_provider_schedules(
            now=NOW,football_data=LimitedFootball(),
            sports_fetcher=empty_sportsdb,openliga=openliga,
            knvb_fetcher=lambda **kwargs:([knvb],[]),pause=0
        )
        self.assertEqual(paths,["DED"])
        self.assertEqual(len(openliga.called),3)
        self.assertTrue(any("football-data HTTP 429" in x for x in warnings))
        self.assertTrue(any(item["provider"]=="knvb" for item in fetched))

    def test_background_fixture_refresh_survives_nl_updater_exception(self):
        knvb={"provider":"knvb","source_id":"123","league":"nl.1",
            "league_name":"Eredivisie","home":"Ajax","away":"PSV",
            "status":"scheduled","source_confirmed":True,"date":"2026-10-18",
            "kickoff":"2026-10-18T12:00:00+00:00","hg":None,"ag":None,
            "source_url":"https://www.knvb.nl/competities/eredivisie/programma"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch("supahbetting.research_upcoming.fetch_provider_schedules",
                       return_value=([knvb],[])),patch(
                       "supahbetting.research_nl_api.refresh_nl_api",
                       side_effect=LiveDataUnavailable("upstream 429")):
                saved=refresh_upcoming(data_dir=tmp,now=NOW,model=MODEL,
                                       inventory={"fixtures":[]})
            self.assertEqual(saved["nl_result_source"]["status"],"error")
            self.assertEqual(saved["schedule_count"],1)
            self.assertEqual(saved["fixtures"][0]["home"],"Ajax")
            self.assertTrue(any("Nederlandse uitslagencontrole" in err
                                for err in saved["provider_warnings"]))
            self.assertTrue((Path(tmp)/"upcoming_predictions.json").exists())


if __name__=="__main__":
    unittest.main()
