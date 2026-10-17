"""HTTP error reporting: numeric status, no opaque 30-route retries."""
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from supahbetting.external_feeds import (
    ProviderHTTPFailure, fetch_bounded_json, normalize_sportsdb
)


class ProviderHTTPDiagnosticsTests(unittest.TestCase):
    def _simulate(self, status):
        class Broken:
            def open(self, req, timeout=None):
                raise HTTPError(req.full_url, status, "Denied", {}, None)
        with patch("supahbetting.external_feeds.build_opener",return_value=Broken()):
            return fetch_bounded_json(
                "/api/v1/json/123/eventsnextleague.php?id=4328","sportsdb"
            )

    def test_403_exposes_only_http_status_and_provider(self):
        with self.assertRaises(ProviderHTTPFailure) as raised:
            self._simulate(403)
        self.assertEqual(raised.exception.status_code,403)
        self.assertEqual(raised.exception.provider,"sportsdb")
        self.assertIn("HTTP 403",str(raised.exception))
        self.assertNotIn("https://",str(raised.exception))

    def test_sportsdb_explicit_soccer_timestamp_gets_safe_utc(self):
        match = {
            "idEvent": "2494060",
            "idLeague": "4328",
            "strSport": "Soccer",
            "strStatus": "NS",
            "strHomeTeam": "Newcastle United",
            "strAwayTeam": "Aston Villa",
            "dateEvent": "2026-10-17",
            "strTimestamp": "2026-10-17T16:30:00",
        }
        result = normalize_sportsdb(match, "4328")
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["kickoff"], "2026-10-17T16:30:00+00:00")

    def test_no_timezone_assumption_for_other_sports(self):
        match = {
            "idEvent": "2494060", "idLeague": "4328",
            "strSport": "Baseball", "strStatus": "NS",
            "strHomeTeam": "A", "strAwayTeam": "B",
            "dateEvent": "2026-10-17",
            "strTimestamp": "2026-10-17T16:30:00",
        }
        result = normalize_sportsdb(match, "4328")
        self.assertEqual(result["kickoff"], "")

    def test_429_exposes_throttling_status(self):
        with self.assertRaises(ProviderHTTPFailure) as raised:
            self._simulate(429)
        self.assertEqual(raised.exception.status_code,429)


if __name__=="__main__":
    unittest.main()
