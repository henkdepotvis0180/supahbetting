"""Live scores are tested offline using synthetic OpenLigaDB responses."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from supahbetting.live_scores import (
    LiveScores, LiveDataUnavailable, InvalidLiveRequest, LEAGUES,
    approved_broadcast, normalize_detail, normalize_match,
)
from supahbetting.server import make_handler
from supahbetting.store import Store


def upstream_match(match_id=345678):
    return {
        "matchID": match_id,
        "leagueShortcut": "bl1",
        "leagueName": "Bundesliga",
        "matchDateTimeUTC": "2099-10-17T14:30:00Z",
        "matchIsFinished": False,
        "group": {"groupName": "7. Spieltag"},
        "team1": {"teamName": "Team Alpha"},
        "team2": {"teamName": "Team Beta"},
        "matchResults": [],
        "goals": [],
    }


def finished_match():
    value = upstream_match()
    value["matchIsFinished"] = True
    value["goals"] = [
        {"matchMinute": 23, "goalGetterName": "Speler A", "scoreTeam1": 1,
         "scoreTeam2": 0, "isPenalty": True, "isOwnGoal": False},
        {"matchMinute": 75, "goalGetterName": "Speler B", "scoreTeam1": 1,
         "scoreTeam2": 1, "isPenalty": False, "isOwnGoal": False},
    ]
    value["matchResults"] = [
        {"resultTypeID": 1, "resultOrderID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
        {"resultTypeID": 2, "resultOrderID": 2, "pointsTeam1": 2, "pointsTeam2": 1},
    ]
    return value


class LiveNormalizationTests(unittest.TestCase):
    def test_upcoming_fixture(self):
        item = normalize_match(upstream_match())
        self.assertEqual(item["id"], 345678)
        self.assertEqual(item["league"], "bl1")
        self.assertEqual(item["status"], "scheduled")
        self.assertIsNone(item["score_home"])
        self.assertEqual(item["home_team"], "Team Alpha")
        self.assertEqual(item["round"], "7. Spieltag")

    def test_score_uses_fulltime_not_halftime_or_last_goal(self):
        match = normalize_detail(finished_match())
        self.assertEqual(match["status"], "finished")
        self.assertEqual((match["score_home"], match["score_away"]), (2, 1))
        self.assertEqual(match["timeline"][0]["minute"], 23)
        self.assertEqual(match["timeline"][0]["score_home"], 1)
        self.assertTrue(match["timeline"][0]["is_penalty"])

    def test_goals_in_progress_score(self):
        match = finished_match()
        match["matchIsFinished"] = False
        match["matchResults"] = [
            {"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0}
        ]
        normalized = normalize_match(match)
        self.assertEqual((normalized["score_home"], normalized["score_away"]), (1, 1))

    def test_reject_missing_data(self):
        with self.assertRaises(InvalidLiveRequest):
            normalize_match({"matchID": 1, "team1": {"teamName": "X"}})

    def test_bad_timestamps_are_not_reinterpreted_as_utc(self):
        fixture = upstream_match()
        fixture["matchDateTimeUTC"] = None
        fixture["matchDateTime"] = "2099-10-17T16:30:00"
        match = normalize_match(fixture)
        self.assertEqual(match["kickoff"], "")
        self.assertEqual(match["kickoff_source_local"], "2099-10-17T16:30:00")

    def test_unsupported_league_rejected(self):
        with self.assertRaises(InvalidLiveRequest):
            LiveScores(fetcher=lambda _: []).list_matches("https://localhost")


class LiveCacheTests(unittest.TestCase):
    def setUp(self):
        self.fake_now = 0.0
        self.calls = []
        self.fail = False
        self.payload = [upstream_match()]

        def fetch(path):
            self.calls.append(path)
            if self.fail:
                raise LiveDataUnavailable("uitgevallen")
            if path.startswith("/getmatchdata/bl"):
                return self.payload
            return upstream_match()

        self.service = LiveScores(
            fetcher=fetch, clock=lambda: self.fake_now,
        )

    def test_list_caches_for_90_seconds(self):
        first = self.service.list_matches("bl1")
        self.fake_now = 50
        second = self.service.list_matches("bl1")
        self.assertFalse(first["stale"])
        self.assertFalse(second["stale"])
        self.assertEqual(self.calls, ["/getmatchdata/bl1"])
        self.fake_now = 95
        self.service.list_matches("bl1")
        self.assertEqual(len(self.calls), 2)

    def test_stale_when_upstream_unavailable_and_backoff(self):
        self.service.list_matches("bl1")
        self.fake_now = 91
        self.fail = True
        stale = self.service.list_matches("bl1")
        self.assertTrue(stale["stale"])
        self.assertEqual(len(stale["matches"]), 1)
        self.assertIn("Bron tijdelijk", stale["warning"])
        self.fake_now = 101
        again = self.service.list_matches("bl1")
        self.assertTrue(again["stale"])
        self.assertEqual(len(self.calls), 2)

    def test_no_stale_cache_returns_error(self):
        self.fail = True
        with self.assertRaises(LiveDataUnavailable):
            self.service.list_matches("bl1")
        self.fake_now = 20
        with self.assertRaises(LiveDataUnavailable):
            self.service.list_matches("bl1")
        self.assertEqual(len(self.calls), 1)

    def test_detail_stores_goal_feed(self):
        detail = self.service.match_detail(345678, "bl1")
        self.assertEqual(detail["id"], 345678)
        self.assertIn("video_embed_url", detail)
        self.assertIsNone(detail["video_embed_url"])
        self.assertEqual(self.calls[-1], "/getmatchdata/345678")

    def test_mismatched_league_rejected(self):
        with self.assertRaises(InvalidLiveRequest):
            self.service.match_detail(345678, "bl2")

    def test_ids_must_be_numeric(self):
        for value in (True, 0, -1, "123", 10**12):
            with self.subTest(value=value), self.assertRaises(InvalidLiveRequest):
                self.service.match_detail(value, "bl1")

    def test_bad_payload(self):
        self.payload = {"oops": "not list"}
        with self.assertRaises(LiveDataUnavailable):
            self.service.list_matches("bl1")


class OfficialVideoTests(unittest.TestCase):
    def test_opt_in_only_https_youtube_nocookie(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "broadcasts.json"
            file.write_text(json.dumps({"bl1:345678":
                "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
            }), encoding="utf-8")
            self.assertEqual(
                approved_broadcast(file, "bl1", 345678),
                "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
            )
            file.write_text(json.dumps({"bl1:345678":
                "https://bad.site/embed/dQw4w9WgXcQ"
            }), encoding="utf-8")
            self.assertIsNone(approved_broadcast(file, "bl1", 345678))
            file.write_text("not json", encoding="utf-8")
            self.assertIsNone(approved_broadcast(file, "bl1", 345678))


class LiveApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        store = Store(Path(cls.temp.name) / "data.sqlite3")
        def fetch(path):
            if path.startswith("/getmatchdata/bl"):
                return [finished_match()]
            return finished_match()
        cls.provider = LiveScores(fetcher=fetch)
        cls.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(store, cls.provider)
        )
        cls.httpd.daemon_threads = True
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.root = "http://127.0.0.1:" + str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def get(self, path):
        try:
            with urlopen(self.root + path, timeout=5) as r:
                return r.status, r.read(), r.headers
        except HTTPError as e:
            return e.code, e.read(), e.headers

    def test_leagues(self):
        status, data, _ = self.get("/api/live/leagues")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(data)["leagues"]), len(LEAGUES))

    def test_live_list_and_detail(self):
        status, raw, _ = self.get("/api/live/matches?league=bl1")
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["score_home"], 2)
        status, raw, _ = self.get("/api/live/matches/345678?league=bl1")
        self.assertEqual(status, 200)
        detail = json.loads(raw)
        self.assertEqual(len(detail["timeline"]), 2)
        self.assertEqual(detail["score_home"], 2)

    def test_all_and_bad_league(self):
        status, raw, _ = self.get("/api/live/matches?league=all")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["league"], "all")
        status, raw, _ = self.get("/api/live/matches?league=unknown")
        self.assertEqual(status, 400)

    def test_live_script_and_csp(self):
        status, data, headers = self.get("/live.js")
        self.assertEqual(status, 200)
        self.assertIn(b"liveLoadDetail", data)
        self.assertIn("youtube-nocookie.com", headers.get("Content-Security-Policy"))

    def test_bad_id_path(self):
        status, _, _ = self.get("/api/live/matches/-1?league=bl1")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
