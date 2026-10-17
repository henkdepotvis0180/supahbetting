"""KNVB live schedule parsing and dated, genuine official fallback tests."""
from __future__ import annotations

from datetime import datetime, timezone, date, timedelta
import unittest

from supahbetting.research_knvb import (
    OFFICIAL_URL, get_eredivisie, kickoff_utc, parse_knvb_schedule,
)
from supahbetting.research_upcoming import (
    _evaluate, _load_model, build_upcoming, fetch_provider_schedules
)

NOW = datetime(2026,10,17,15,41,0,tzinfo=timezone.utc)
MODEL = _load_model("supahbetting/models/research_v0.12.0_experimental.json")
HTML = """
<html lang="nl"><head><title>Programma Eredivisie | KNVB</title></head>
<body><main><h1>Programma Eredivisie</h1>
<h2>zaterdag 17 oktober 2026</h2>
<div><span>ADO Den Haag</span><span>16:30</span><span>PSV</span></div>
<div><span>Telstar</span><span>20:00</span><span>Feyenoord</span></div>
<div><span>Sparta Rotterdam</span><span>21:00</span><span>Willem II</span></div>
<h2>zondag 18 oktober 2026</h2>
<div><span>FC Groningen</span><span>16:45</span><span>Ajax</span></div>
<div><span>FC Twente</span><span>20:00</span><span>FC Utrecht</span></div>
</main></body></html>"""


class KNVBScheduleTests(unittest.TestCase):
    def test_real_official_dated_fixture_fallback_is_not_demo(self):
        rows,warnings = get_eredivisie(now=NOW,network=False)
        self.assertGreaterEqual(len(rows),20)
        today = [row for row in rows if row["date"]=="2026-10-17"]
        self.assertEqual(len(today),2)  # ADO-PSV already kicked off.
        self.assertEqual({(r["home"],r["away"]) for r in today},
                         {("Telstar","Feyenoord"),
                          ("Sparta Rotterdam","Willem II")})
        self.assertTrue(all(row["provider"]=="knvb" for row in rows))
        self.assertTrue(all(row["source_url"]==OFFICIAL_URL for row in rows))
        self.assertTrue(all(row["source_confirmed"] for row in rows))
        self.assertTrue(all(row["source_method"]=="dated_official_snapshot" for row in rows))

    def test_official_live_html_is_preferred_to_archive_snapshot(self):
        fixtures,warnings=get_eredivisie(now=NOW,fetch_html=lambda:HTML)
        self.assertEqual(len(fixtures),4)  # Played 16:30 fixture must disappear.
        self.assertTrue(all(r["source_method"]=="official_page_live" for r in fixtures))
        self.assertTrue(all(r["source_confirmed"] for r in fixtures))
        self.assertTrue(any(r["home"]=="FC Groningen" and r["away"]=="Ajax"
                            for r in fixtures))

    def test_http_denial_uses_official_backup_without_fabricating(self):
        def denied():
            raise OSError("KNVB page unavailable")
        rows,warnings=get_eredivisie(now=NOW,fetch_html=denied)
        self.assertTrue(rows)
        self.assertTrue(any("snapshot" in w for w in warnings))
        self.assertTrue(any(r["home"]=="Telstar" for r in rows))
        self.assertTrue(all(r["source_method"]=="dated_official_snapshot" for r in rows))

    def test_expired_snapshot_is_not_claimed_fresh(self):
        old=NOW + timedelta(days=9)
        rows,warnings=get_eredivisie(now=old,network=False)
        self.assertTrue(rows)
        self.assertTrue(all(not r["source_confirmed"] for r in rows))
        self.assertTrue(any("herbevestiging" in warning for warning in warnings))

    def test_official_parser_ignores_random_page_text_and_incomplete_matches(self):
        extra="""
        <p>Andere wedstrijden staan elders; Ajax kwam voorbij in een advertentie.</p>
        <h2>maandag 19 oktober 2026</h2>
        <div>Onbekende club 15:00 Nijmegen</div>
        <div>PSV zonder tijd tegen Feyenoord</div>
        <script>zaterdag 17 oktober 2026 Telstar 22:00 Ajax</script>
        """
        rows=parse_knvb_schedule(HTML+extra,today=NOW.date(),days=15)
        self.assertEqual(len(rows),5)
        self.assertFalse(any(r["away"]=="Nijmegen" for r in rows))

    def test_eu_summer_winter_time_switch(self):
        self.assertEqual(kickoff_utc("2026-10-17","20:00"),
                         "2026-10-17T18:00:00+00:00")
        self.assertEqual(kickoff_utc("2026-10-25","14:30"),
                         "2026-10-25T13:30:00+00:00")

    def test_real_eredivisie_probabilities_and_no_unverified_team_guess(self):
        rows,_=get_eredivisie(now=NOW,network=False)
        for fixture in rows:
            prediction,reason = _evaluate(fixture,MODEL,NOW)
            # Every verified club in our official snapshot must be recognized
            # by the historic model; unknown clubs are never silently guessed.
            self.assertIsNotNone(prediction,
                "Missing alias for "+fixture["home"]+" – "+fixture["away"]+": "+str(reason))
            self.assertAlmostEqual(sum(prediction["probabilities"].values()),1.0,places=4)
            self.assertIn("model_age_days",prediction)

    def test_knvb_is_available_even_when_sportsdb_immediately_refuses(self):
        from supahbetting.external_feeds import ProviderHTTPFailure
        class DisabledFootball:
            enabled=False
        class EmptyOpenliga:
            def list_matches(self,league):
                return {"matches":[]}
        attempts=[]
        def sportsdb(route):
            attempts.append(route)
            raise ProviderHTTPFailure("sportsdb",403)
        fetched,warnings=fetch_provider_schedules(
            now=NOW,football_data=DisabledFootball(),sports_fetcher=sportsdb,
            openliga=EmptyOpenliga(),knvb_fetcher=lambda **kw:
                get_eredivisie(now=NOW,network=False),pause=0,
        )
        self.assertEqual(len(attempts),1)
        self.assertTrue(any(x["league"]=="nl.1" and x["provider"]=="knvb"
                            for x in fetched))
        self.assertTrue(any("HTTP 403" in w for w in warnings))


if __name__=="__main__":
    unittest.main()
