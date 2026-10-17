"""Read-only fixture dashboard integration: no upstream network on page GET."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from supahbetting import server
from supahbetting.store import Store


class ResearchUpcomingApiTests(unittest.TestCase):
    def test_dashboard_contains_fixture_list(self):
        html=Path("supahbetting/static/index.html").read_text(encoding="utf-8")
        self.assertIn('id="research-fixture-list"', html)
        self.assertIn('id="research-fixture-league"', html)
        self.assertIn('src="/research_fixtures.js"', html)

    def test_local_fixture_api_requires_no_network_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            with patch.object(server, "RESEARCH_LOCAL", folder):
                service=ThreadingHTTPServer(("127.0.0.1",0),
                    server.make_handler(Store(folder/"paper.sqlite3")))
                service.daemon_threads=True
                thread=threading.Thread(target=service.serve_forever,daemon=True)
                thread.start()
                url="http://127.0.0.1:"+str(service.server_port)
                try:
                    with urlopen(url+"/api/research/upcoming",timeout=5) as res:
                        missing=json.load(res)
                    self.assertFalse(missing["available"])
                    payload={
                        "schema_version":1,"schedule_count":1,
                        "confirmed_schedule_count":1,"predicted_count":0,
                        "fixtures":[{"home":"Alpha","away":"Beta",
                                     "source_confirmed":True}]
                    }
                    (folder/"upcoming_predictions.json").write_text(
                        json.dumps(payload),encoding="utf-8")
                    with urlopen(url+"/api/research/upcoming",timeout=5) as res:
                        loaded=json.load(res)
                    self.assertTrue(loaded["available"])
                    self.assertEqual(loaded["fixtures"][0]["home"],"Alpha")
                    with urlopen(url+"/research_fixtures.js",timeout=5) as res:
                        self.assertEqual(res.status,200)
                        self.assertIn(b"research-fixture-list",res.read())
                finally:
                    service.shutdown()
                    service.server_close()
                    thread.join(timeout=5)


if __name__=="__main__":
    unittest.main()
