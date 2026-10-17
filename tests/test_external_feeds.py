"""Offline verification of the TheSportsDB/football-data.org provider integrations."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from supahbetting.external_feeds import (
    FootballData, ProviderHub, SportsDB, fetch_bounded_json,
    normalize_football_data, normalize_sportsdb,
)
from supahbetting.live_scores import (
    InvalidLiveRequest, LiveDataUnavailable, LiveScores,
)
from supahbetting.server import make_handler
from supahbetting.store import Store


def sportsdb_event(match_id="2030101", status="Match Finished"):
    return {
        "idEvent": match_id, "idLeague": "4337", "strEvent": "Ajax vs PSV",
        "strHomeTeam": "Ajax", "strAwayTeam": "PSV",
        "dateEvent": "2026-10-17", "strTimestamp": "2026-10-17T18:00:00+00:00",
        "strStatus": status, "intHomeScore": "2", "intAwayScore": "1",
    }


def football_data_event(match_id=500100, status="FINISHED"):
    return {
        "id": match_id, "competition": {"code": "DED"},
        "homeTeam": {"name": "FC Utrecht"}, "awayTeam": {"name": "AZ"},
        "utcDate": "2026-10-17T18:00:00Z", "matchday": 9,
        "status": status,
        "score": {"fullTime": {"home": 2, "away": 1}},
        "goals": [
            {
                "minute": 50, "type": "REGULAR",
                "scorer": {"name": "Speler U"},
                "score": {"home": 1, "away": 0},
            },
            {
                "minute": 75, "type": "PENALTY",
                "scorer": {"name": "Speler Z"},
                "score": {"home": 2, "away": 1},
            },
        ],
    }


class NormalizerTests(unittest.TestCase):
    def test_sportsdb_free_is_not_live(self):
        item = normalize_sportsdb(sportsdb_event(), "4337")
        self.assertEqual(item["home_team"], "Ajax")
        self.assertEqual(item["score_home"], 2)
        self.assertEqual(item["status"], "finished")
        self.assertEqual(item["feed_kind"], "schedule_only")
        self.assertEqual(item["timeline"], [])

    def test_sportsdb_unknown_status_never_infers_live(self):
        raw = sportsdb_event(status="")
        self.assertEqual(normalize_sportsdb(raw, "4337")["status"], "unknown")
        with self.assertRaises(InvalidLiveRequest):
            normalize_sportsdb(raw, "4641")

    def test_football_data_delayed_scores_and_goals(self):
        match = normalize_football_data(football_data_event(), "DED")
        self.assertEqual(match["league"], "DED")
        self.assertEqual(match["feed_kind"], "delayed")
        self.assertEqual(match["status"], "finished")
        self.assertEqual(match["score_home"], 2)
        self.assertEqual(len(match["timeline"]), 2)
        self.assertEqual(match["timeline"][1]["minute"], 75)
        self.assertTrue(match["timeline"][1]["is_penalty"])

    def test_football_data_free_in_play_not_labeled_live(self):
        match = normalize_football_data(football_data_event(status="IN_PLAY"), "DED")
        self.assertEqual(match["status"], "unknown")
        self.assertIn("vertraagd", match["status_label"])

    def test_unknown_ids_rejected(self):
        with self.assertRaises(InvalidLiveRequest):
            normalize_football_data({"id": 12, "homeTeam": {"name": "A"}}, "DED")
        with self.assertRaises(InvalidLiveRequest):
            normalize_sportsdb({"idEvent": 12}, "4337")

    def test_safety_blocks_arbitrary_http_requests(self):
        with self.assertRaises(InvalidLiveRequest):
            fetch_bounded_json("/api/v1/json/123/search.php?u=https://evil.invalid", "sportsdb")
        with self.assertRaises(InvalidLiveRequest):
            fetch_bounded_json("/v4/competitions/../../secret", "football-data", "token")
        with self.assertRaises(InvalidLiveRequest):
            fetch_bounded_json("/v4/matches/123", "unknown", "token")
        with self.assertRaises(LiveDataUnavailable):
            fetch_bounded_json("/v4/matches/123", "football-data")


class SportsDBTests(unittest.TestCase):
    def setUp(self):
        self.paths = []

        def fetch(path):
            self.paths.append(path)
            if "eventsnextleague" in path:
                return {"events": [sportsdb_event()]}
            if "eventspastleague" in path:
                return {"events": [sportsdb_event("2030102")]}
            if "eventsday" in path:
                return {"events": [sportsdb_event(), sportsdb_event("2030103")]}
            return {"events": [sportsdb_event()]}

        self.feed = SportsDB(fetcher=fetch, today=lambda: date(2026, 10, 17))

    def test_free_calls_and_deduplicated_results(self):
        data = self.feed.list_matches("4337")
        self.assertEqual(len(data["matches"]), 3)
        self.assertEqual(len(self.paths), 3)
        self.assertIn("GEEN live", data["coverage_note"])
        self.assertFalse(data["stale"])
        again = self.feed.list_matches("4337")
        self.assertEqual(len(again["matches"]), 3)
        self.assertEqual(len(self.paths), 3)

    def test_match_detail(self):
        item = self.feed.match_detail(2030101, "4337")
        self.assertEqual(item["home_team"], "Ajax")
        self.assertFalse(item["timeline"])
        self.assertIsNone(item["video_embed_url"])

    def test_bad_competition(self):
        with self.assertRaises(InvalidLiveRequest):
            self.feed.list_matches("127.0.0.1")
        with self.assertRaises(InvalidLiveRequest):
            self.feed.match_detail(2030101, "invalid")


class FootballDataTests(unittest.TestCase):
    def setUp(self):
        self.paths = []

        def fetch(path):
            self.paths.append(path)
            if path.startswith("/v4/competitions/"):
                return {"matches": [football_data_event()]}
            return football_data_event()

        self.feed = FootballData(token="test-token", fetcher=fetch,
                                 today=lambda: date(2026, 10, 17))

    def test_date_window_and_cache(self):
        data = self.feed.list_matches("DED")
        self.assertEqual(len(data["matches"]), 1)
        self.assertIn("vertraag", data["coverage_note"].lower())
        self.assertEqual(
            self.paths[0],
            "/v4/competitions/DED/matches?dateFrom=2026-10-14&dateTo=2026-11-01",
        )
        self.feed.list_matches("DED")
        self.assertEqual(len(self.paths), 1)

    def test_goal_details_and_correct_league(self):
        data = self.feed.match_detail(500100, "DED")
        self.assertEqual(len(data["timeline"]), 2)
        with self.assertRaises(InvalidLiveRequest):
            self.feed.match_detail(500100, "PL")

    def test_missing_token_reports_configuration(self):
        feed = FootballData(token="", fetcher=lambda path: football_data_event())
        self.assertFalse(feed.enabled)
        with self.assertRaisesRegex(LiveDataUnavailable, "FOOTBALL_DATA_API_KEY"):
            feed.list_matches("DED")
        with self.assertRaisesRegex(LiveDataUnavailable, "FOOTBALL_DATA_API_KEY"):
            feed.match_detail(500100, "DED")


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        store = Store(Path(cls.temp.name) / "data.sqlite3")
        cls.hub = ProviderHub(
            openliga=LiveScores(fetcher=lambda path: []),
            sportsdb=SportsDB(
                fetcher=lambda path: {"events": [sportsdb_event()]},
                today=lambda: date(2026, 10, 17),
            ),
            football_data=FootballData(
                token="mock",
                fetcher=lambda path: (
                    {"matches": [football_data_event()]}
                    if "competitions/" in path else football_data_event()
                ),
                today=lambda: date(2026, 10, 17),
            ),
        )
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(store, provider_hub=cls.hub)
        )
        cls.server.daemon_threads = True
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.root = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=5)
        cls.temp.cleanup()

    def get(self, route):
        try:
            with urlopen(self.root + route, timeout=10) as r:
                return r.status, json.loads(r.read())
        except HTTPError as r:
            return r.code, json.loads(r.read())

    def test_catalog(self):
        status, data = self.get("/api/live/providers")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["providers"]), 3)
        self.assertIn("Eredivisie",
                      [x["name"] for x in data["providers"][1]["leagues"]])
        self.assertTrue(data["providers"][2]["enabled"])

    def test_eredivisie_via_sportsdb(self):
        status, data = self.get("/api/live/matches?provider=sportsdb&league=4337")
        self.assertEqual(status, 200)
        self.assertEqual(data["matches"][0]["home_team"], "Ajax")
        status, detail = self.get(
            "/api/live/matches/2030101?provider=sportsdb&league=4337"
        )
        self.assertEqual(status, 200)
        self.assertIn("geen doelpuntenfeed", detail["timeline_note"])

    def test_eredivisie_via_football_data(self):
        status, data = self.get("/api/live/matches?provider=football-data&league=DED")
        self.assertEqual(status, 200)
        self.assertEqual(data["feed_kind"], "delayed")
        status, detail = self.get(
            "/api/live/matches/500100?provider=football-data&league=DED"
        )
        self.assertEqual(status, 200)
        self.assertEqual(detail["timeline"][0]["player"], "Speler U")

    def test_bad_provider_and_all_guard(self):
        self.assertEqual(
            self.get("/api/live/matches?provider=evil&league=4337")[0], 400
        )
        self.assertEqual(
            self.get("/api/live/matches?provider=sportsdb&league=all")[0], 400
        )
        self.assertEqual(
            self.get("/api/live/matches?provider=football-data&league=127.0.0.1")[0], 400
        )


if __name__ == "__main__":
    unittest.main()
