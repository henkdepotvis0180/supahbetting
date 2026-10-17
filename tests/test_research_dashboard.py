"""Read-only research dashboard stays local and reports absence without fabrication."""
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


class ResearchDashboardTests(unittest.TestCase):
    def test_research_page_elements_and_script_are_present(self):
        html=Path("supahbetting/static/index.html").read_text(encoding="utf-8")
        self.assertIn('id="research-data-summary"',html)
        self.assertIn('id="research-data-factors"',html)
        self.assertIn('src="/research_data.js"',html)
        self.assertIn("Geen",Path("supahbetting/static/research_data.js").read_text(encoding="utf-8"))

    def test_read_only_endpoint_with_and_without_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(server,"RESEARCH_LOCAL",Path(tmp)):
                httpd=ThreadingHTTPServer(
                    ("127.0.0.1",0),
                    server.make_handler(Store(Path(tmp)/"store.sqlite3"))
                )
                httpd.daemon_threads=True
                thread=threading.Thread(target=httpd.serve_forever,daemon=True)
                thread.start()
                try:
                    base="http://127.0.0.1:"+str(httpd.server_port)
                    with urlopen(base+"/api/research/data/status",timeout=5) as response:
                        pending=json.load(response)
                    self.assertFalse(pending["available"])
                    (Path(tmp)/"research_report.json").write_text(
                        json.dumps({"mode":"research_only","training_matches":2}),
                        encoding="utf-8"
                    )
                    with urlopen(base+"/api/research/data/status",timeout=5) as response:
                        ready=json.load(response)
                    self.assertTrue(ready["available"])
                    self.assertEqual(ready["report"]["training_matches"],2)
                    self.assertEqual(ready["context"]["records"],0)
                    with urlopen(base+"/research_data.js",timeout=5) as response:
                        self.assertEqual(response.status,200)
                        self.assertIn(b"research-data-summary",response.read())
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
