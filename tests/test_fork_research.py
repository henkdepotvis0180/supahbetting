"""Research storage and HTTP integration: cannot silently conflate matches."""
import csv
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from supahbetting.fork_bridge import BridgeError
from supahbetting.fork_research import ResearchStore
from supahbetting.server import make_handler
from supahbetting.store import Store


def odds_record(*, day="2026-10-19", h="Ajax", a="PSV", bookmaker="Bet A",
                timestamp="2026-10-17T09:00:00Z"):
    return {
        "home_team":h,"away_team":a,
        "match_date":day+"T20:00:00Z",
        "scraped_date":timestamp,
        "1x2_market":[{"bookmaker_name":bookmaker,"period":"FullTime",
                       "1":"2.20","X":"3.30","2":"3.60"}]
    }


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"data.sqlite3"
        self.research=ResearchStore(self.db)
        self.research.make_inbox()

    def _write(self, provider, filename, content):
        path=self.research.inbox/provider/filename
        path.write_text(content,encoding="utf-8")
        return path

    def test_empty(self):
        status=self.research.status()
        self.assertEqual(status["predictions"],0)
        self.assertEqual(status["odds"],0)
        self.assertEqual(self.research.opportunities()["opportunities"],[])

    def test_zero_model_probability_can_be_stored_without_aborting(self):
        path=self._write("prophitbet","certain.csv",
            "Home Team,Away Team,1,X,2,Prob(1),Prob(X),Prob(2)\n"
            "Ajax,PSV,2.2,3.0,3.5,0.0,0.5,0.5\n")
        result=self.research.ingest(path,"prophitbet")
        self.assertEqual(result["imported"],6)
        opps=self.research.opportunities()["opportunities"]
        self.assertTrue(any(x["probability"] == 0.0 and
                            x["fair_odds"] is None for x in opps))

    def test_prophitbet_six_observations_and_dedup(self):
        path=self._write("prophitbet","fixtures.csv",
            "Home Team,Away Team,1,X,2,Prob(1),Prob(X),Prob(2)\n"
            "Ajax,PSV,2.1,3.4,3.6,0.50,0.25,0.25\n")
        imported=self.research.ingest(path,"prophitbet")
        self.assertEqual(imported["imported"],6)
        again=self.research.ingest(path,"prophitbet")
        self.assertTrue(again["skipped"])
        self.assertEqual(again["imported"],0)
        status=self.research.status()
        self.assertEqual(status["predictions"],3)
        self.assertEqual(status["odds"],3)
        bets=self.research.opportunities(now=datetime(2026,10,17,tzinfo=timezone.utc))
        self.assertEqual(len(bets["opportunities"]),3)
        self.assertTrue(all(row["freshness"]=="tijd_onbekend" for row in bets["opportunities"]))
        self.assertTrue(all(not row["is_recommendation"] for row in bets["opportunities"]))

    def test_exact_date_match_crosses_sources_without_fuzzy_substrings(self):
        pred=self._write("prediict","pred.csv",
            "home_team,away_team,date,home_win_prob,draw_prob,away_win_prob\n"
            "Ajax,PSV,2026-10-19T20:00:00Z,0.50,0.27,0.23\n")
        odds=self._write("oddsharvester","odds.json",json.dumps([
            odds_record(),odds_record(h="Ajax Reserves"),
        ]))
        self.research.ingest(pred,"prediict")
        self.research.ingest(odds,"oddsharvester")
        scan=self.research.opportunities(now=datetime(2026,10,17,10,tzinfo=timezone.utc))
        self.assertEqual(len(scan["opportunities"]),3)
        self.assertEqual({r["home_team"] for r in scan["opportunities"]},{"Ajax"})
        self.assertEqual({r["bookmaker"] for r in scan["opportunities"]},{"Bet A"})
        self.assertTrue(all(r["freshness"]=="max_24_uur_oud" for r in scan["opportunities"]))

    def test_same_teams_on_different_dates_do_not_match(self):
        pred=self._write("prediict","pred.csv",
            "home_team,away_team,date,home_win_prob,draw_prob,away_win_prob\n"
            "Ajax,PSV,2026-10-18T20:00:00Z,0.50,0.27,0.23\n")
        self.research.ingest(pred,"prediict")
        self.research.ingest(self._write(
            "oddsharvester","odds.json",json.dumps([odds_record(day="2026-10-19")])
        ),"oddsharvester")
        self.assertEqual(self.research.opportunities()["opportunities"],[])

    def test_undated_prophitbet_does_not_join_other_file(self):
        self.research.ingest(self._write("prophitbet","fixtures.csv",
            "Home Team,Away Team,1,X,2,Prob(1),Prob(X),Prob(2)\n"
            "Ajax,PSV,2.1,3.4,3.6,0.50,0.25,0.25\n"),"prophitbet")
        self.research.ingest(self._write("oddsharvester","odds.json",
            json.dumps([odds_record()])),"oddsharvester")
        scan=self.research.opportunities()
        self.assertEqual(len(scan["opportunities"]),3)
        self.assertTrue(all(
            r["odds_source"]=="prophitbet" for r in scan["opportunities"]
        ))

    def test_stale_and_historical_prices_labeled(self):
        self.research.ingest(self._write("prediict","past.csv",
            "match,home_team,away_team,date,outcome,model_probability,bookmaker_odds\n"
            "Ajax vs PSV,Ajax,PSV,2026-05-24T15:00:00Z,Home Win,0.9,3.7\n"),"prediict")
        scan=self.research.opportunities(now=datetime(2026,10,17,tzinfo=timezone.utc))
        self.assertEqual(scan["opportunities"][0]["freshness"],"historisch")
        self.assertGreater(scan["opportunities"][0]["expected_roi"],0)
        self.assertFalse(scan["opportunities"][0]["is_recommendation"])

    def test_scan_inbox_increments_only_once(self):
        self._write("prophitbet","models.csv",
            "Date,Home,Away,1,X,2,Prob(1),Prob(X),Prob(2)\n"
            "2026-10-19,Ajax,PSV,2.1,3.4,3.6,0.50,0.25,0.25\n")
        first=self.research.scan_inbox()
        second=self.research.scan_inbox()
        self.assertEqual(first["files_imported"],1)
        self.assertEqual(second["files_imported"],0)
        self.assertEqual(self.research.status()["predictions"],3)

    def test_bad_export_does_not_break_healthy_provider(self):
        self._write("prophitbet","broken.csv","Home Team,Away Team\nInvalid,File\n")
        self._write("prediict","valid.csv",
            "home_team,away_team,date,outcome,model_probability,bookmaker_odds\n"
            "Ajax,PSV,2026-10-19T20:00:00Z,Home Win,0.55,2.0\n")
        result=self.research.scan_inbox()
        self.assertEqual(result["files_imported"],1)
        self.assertEqual(len(result["errors"]),1)
        self.assertEqual(self.research.status()["predictions"],1)

    def test_symlink_input_not_followed(self):
        path=self.root/"elsewhere.csv"
        path.write_text(
            "home_team,away_team,date,outcome,model_probability,bookmaker_odds\n"
            "A,B,2026-10-19,Draw,0.4,3.3\n",encoding="utf-8"
        )
        shortcut=self.research.inbox/"prediict"/"not-followed.csv"
        try:
            shortcut.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink not supported on this platform")
        self.research.scan_inbox()
        self.assertEqual(self.research.status()["predictions"],0)

    def test_unsafe_provider_id_rejected(self):
        with self.assertRaises(BridgeError):
            self.research.ingest(self.root/"nothing.csv","../../secret")


class ResearchAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/"d.sqlite3"
        self.research=ResearchStore(self.db)
        self.research.make_inbox()
        file=self.research.inbox/"prophitbet"/"export.csv"
        file.write_text(
            "Home Team,Away Team,1,X,2,Prob(1),Prob(X),Prob(2)\n"
            "A,B,2,3,4,0.5,0.3,0.2\n",encoding="utf-8"
        )
        self.httpd=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Store(self.db),research_hub=self.research))
        self.httpd.daemon_threads=True
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:"+str(self.httpd.server_port)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def get(self,route,body=None):
        headers={}
        kwargs={}
        if body is not None:
            kwargs["data"]=json.dumps(body).encode("utf-8")
            kwargs["method"]="POST"
            headers["Content-Type"]="application/json"
        req=Request(self.url+route,headers=headers,**kwargs)
        try:
            with urlopen(req,timeout=5) as r:
                return r.status,r.read(),r.headers
        except HTTPError as e:
            return e.code,e.read(),e.headers

    def test_import_scan_status_and_prices(self):
        status,raw,_=self.get("/api/research/imports/scan",{})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)["files_imported"],1)
        status,raw,_=self.get("/api/research/status")
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)["predictions"],3)
        status,raw,_=self.get("/api/research/opportunities")
        self.assertEqual(status,200)
        self.assertEqual(len(json.loads(raw)["opportunities"]),3)
        status,js,_=self.get("/research.js")
        self.assertEqual(status,200)
        self.assertIn(b"researchImport",js)

    def test_no_arbitrary_file_import_endpoint(self):
        status,raw,_=self.get("/api/research/import?path=../../secrets",{})
        self.assertEqual(status,404)


if __name__=="__main__":
    unittest.main()
