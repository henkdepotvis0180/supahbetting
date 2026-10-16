import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from supahbetting.server import make_handler, preview
from supahbetting.domain import ValidationError
from supahbetting.store import Store


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name) / "data.sqlite3")
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.store))
        cls.httpd.daemon_threads = True
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.root = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        options = {"headers": headers or {}}
        if payload is not None:
            options["data"] = json.dumps(payload).encode("utf-8")
            options["headers"] = {**options["headers"], "Content-Type": "application/json"}
            options["method"] = "POST"
        request = Request(self.root + path, **options)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_health_and_assets(self):
        status, data, _ = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)["live_odds"])
        status, data, hdr = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Combinatie", data)
        self.assertIn("Content-Security-Policy", hdr)
        status, js, _ = self.request("/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"updateQuote", js)

    def test_create_quote_and_slip(self):
        data = {
            "home_team": "Blue", "away_team": "Red", "source": "Test",
            "home_xg": 1.5, "away_xg": 1.1,
            "odds_home": 2.1, "odds_draw": 3.4, "odds_away": 3.5,
        }
        status, raw, _ = self.request("/api/matches", data)
        self.assertEqual(status, 201)
        mid = json.loads(raw)["match"]["id"]
        self.assertGreater(mid, 0)
        status, raw, _ = self.request("/api/slips/quote", {
            "legs": [{"match_id": mid, "market": "home"}], "stake": 5,
        })
        self.assertEqual(status, 200)
        self.assertAlmostEqual(json.loads(raw)["quote"]["combined_odds"], 2.1)
        status, raw, _ = self.request("/api/slips", {
            "legs": [{"match_id": mid, "market": "home", "decimal_odds": 99}], "stake": 5,
        })
        self.assertEqual(status, 201)
        self.assertAlmostEqual(json.loads(raw)["slip"]["combined_odds"], 2.1)
        status, raw, _ = self.request(f"/api/matches/{mid}/settle", {
            "home_goals": 0, "away_goals": 1,
        })
        self.assertEqual(status, 200)
        status, raw, _ = self.request("/api/stats")
        self.assertEqual(status, 200)
        self.assertAlmostEqual(json.loads(raw)["realized_profit"], -5)

    def test_reject_bad_host(self):
        status, data, _ = self.request("/api/health", headers={"Host": "attacker.invalid"})
        self.assertEqual(status, 400)
        self.assertIn(b"Host", data)

    def test_reject_bad_origin(self):
        status, _, _ = self.request("/api/demo", {}, headers={"Origin": "https://foreign.invalid"})
        self.assertEqual(status, 400)

    def test_reject_json_invalid_data(self):
        status, _, _ = self.request("/api/matches", {
            "home_team": "A", "away_team": "A",
            "home_xg": 1, "away_xg": 1, "odds_home": 2, "odds_draw": 3,
            "odds_away": 3, "source": "Test",
        })
        self.assertEqual(status, 400)

    def test_local_static_routes_are_allowlisted(self):
        status, _, _ = self.request("/../../AGENTS.md")
        self.assertNotEqual(status, 200)

    def test_duplicate_choice_quote_rejected(self):
        match = self.store.add_match({
            "home_team": "Test 1", "away_team": "Test 2", "source": "Test",
            "home_xg": 1.2, "away_xg": 1, "odds_home": 2,
            "odds_draw": 3.3, "odds_away": 3.7
        })
        with self.assertRaises(ValidationError):
            preview(self.store, {
                "legs": [{"match_id": match["id"], "market": "home"},
                         {"match_id": match["id"], "market": "draw"}],
                "stake": 5
            })


if __name__ == "__main__":
    unittest.main()
