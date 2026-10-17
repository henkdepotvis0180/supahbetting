"""HTTP integration checks: production remains default; v0.11 only compares."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from supahbetting.experimental_model import EXPERIMENTAL_FILE
from supahbetting.server import make_handler
from supahbetting.store import Store
from supahbetting.trained_model import MODEL_FILE, load_pretrained


class ExperimentalComparisonApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load_pretrained(MODEL_FILE)
        cls.new = load_pretrained(EXPERIMENTAL_FILE)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(Store(Path(cls.tmp.name) / "compare.sqlite3"),
                         trained=cls.old, experimental=cls.new),
        )
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def api(self, path, body=None):
        kwargs = {}
        if body is not None:
            kwargs = {
                "data": json.dumps(body).encode("utf-8"),
                "headers": {"Content-Type": "application/json"},
                "method": "POST",
            }
        with urlopen(Request(self.origin + path, **kwargs), timeout=10) as response:
            self.assertEqual(response.status, 200)
            return json.load(response)

    def test_both_statuses_are_distinct(self):
        original = self.api("/api/trained/status")
        candidate = self.api("/api/trained/experimental/status")
        self.assertEqual(original["version"], "0.10.0")
        self.assertEqual(candidate["version"], "0.11.0-experimental")
        self.assertTrue(candidate["production_unchanged"])
        self.assertEqual(candidate["evaluation"]["test"]["model_logloss"], 0.97725)

    def test_predict_remains_original_and_comparison_shows_both(self):
        match = {"league": "nl.1", "home_team": "Ajax", "away_team": "PSV"}
        original = self.api("/api/trained/predict", match)
        compared = self.api("/api/trained/compare", match)
        self.assertEqual(original, compared["baseline"])
        self.assertEqual(compared["experimental"]["model_version"],
                         "0.11.0-experimental")
        self.assertEqual(compared["baseline"]["model_version"], "0.10.0")
        self.assertNotEqual(
            compared["baseline"]["expected_goals_home"],
            compared["experimental"]["expected_goals_home"],
        )
        for key in ("home", "draw", "away"):
            self.assertAlmostEqual(
                compared["experimental"]["probabilities"][key] -
                compared["baseline"]["probabilities"][key],
                compared["probability_difference"][key],
                places=6,
            )


if __name__ == "__main__":
    unittest.main()
