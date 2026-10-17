"""Research v0.13 regression: real-only fixtures, explanations, fresh scores and audit."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from supahbetting.research_readiness import audit_startup
from supahbetting.research_challengers import dixon_coles_probs, compare_models
from supahbetting.research_rationale import reasoning
from supahbetting.research_daily_results import (
    collect_verified_finals, merge_verified_locally, rebuild_augmented_if_needed
)
from supahbetting.research_upcoming import build_upcoming, PUBLISHED_MODEL
from supahbetting.trained_model import load_pretrained, predict_trained


NOW=datetime(2026,10,17,14,0,tzinfo=timezone.utc)
MODEL=load_pretrained(PUBLISHED_MODEL)


def event(*, home="Ajax", away="PSV", status="scheduled",
          kickoff="2026-10-18T12:00:00+00:00", hg=None, ag=None,
          provider="sportsdb", identity="12345"):
    return {
        "provider": provider, "source_id": identity, "league": "nl.1",
        "league_name": "Eredivisie", "home": home,"away":away,
        "date": kickoff[:10], "kickoff": kickoff,
        "source_confirmed":True, "status":status,
        "hg":hg,"ag":ag,"source_url":"https://www.thesportsdb.com/",
    }


class SeriousResearchTests(unittest.TestCase):
    def test_readiness_checks_ten_year_bundled_model(self):
        with tempfile.TemporaryDirectory() as temp:
            state=audit_startup(folder=temp,now=NOW,model=MODEL)
        self.assertTrue(state["available"])
        self.assertTrue(state["ten_year_history"])
        self.assertTrue(state["historical_test_available"])
        self.assertFalse(state["is_prospectively_validated"])
        self.assertFalse(state["is_profitable_vs_bookmaker_prices"])
        self.assertGreater(state["model_age_days"],14)

    def test_explanation_uses_only_true_model_data(self):
        prediction=predict_trained(MODEL,"nl.1","Ajax","PSV")
        prediction["model_age_days"]=27
        result=reasoning(MODEL,prediction,now=NOW)
        self.assertTrue(result["reasons"])
        self.assertIn("Doelpuntenraming",result["reasons"][0])
        self.assertFalse(result["eligible_for_highlight"])
        self.assertTrue(result["model_reasons_only"])
        self.assertIn("bookmaker",result["risk_note"])
        self.assertNotIn("omgekocht",json.dumps(result))

    def test_real_fixtures_only_and_actual_recent_results(self):
        with tempfile.TemporaryDirectory() as temp:
            archived={"id":"archive","date":"2026-10-18","league":"nl.1",
                      "season":"2026-27","home":"Ajax","away":"PSV"}
            played=event(status="finished",kickoff="2026-10-16T18:00:00+00:00",
                         hg=2,ag=1,identity="oldgame")
            result=build_upcoming(
                model=MODEL,now=NOW,
                inventory={"fixtures":[archived]},
                fetched=[event(),played],
                forecast_log=Path(temp)/"forecast.json",
                output=Path(temp)/"upcoming.json",
            )
            self.assertEqual(result["schedule_count"],1)
            self.assertEqual(result["recent_results_count"],1)
            self.assertEqual(result["recent_results"][0]["hg"],2)
            self.assertEqual(result["fixtures"][0]["provider"],"sportsdb")
            self.assertEqual(result["predicted_count"],1)
            self.assertIsNotNone(result["fixtures"][0]["model_preference"])

    def test_none_predictable_game_does_not_crash_ranking(self):
        with tempfile.TemporaryDirectory() as temp:
            no_team=event(home="Invented Club FC",identity="unknown")
            result=build_upcoming(
                model=MODEL, now=NOW, fetched=[no_team],
                forecast_log=Path(temp)/"log.json",output=Path(temp)/"rows.json",
            )
            self.assertEqual(result["predicted_count"],0)
            self.assertIsNone(result["fixtures"][0]["model_preference"])
            self.assertIsNotNone(result["fixtures"][0]["prediction_unavailable_reason"])

    def test_local_verified_final_deduplicated_and_quarantined(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"finals.json"
            row=event(status="finished",kickoff="2026-10-16T18:00:00+00:00",
                      hg=2,ag=1)
            first=collect_verified_finals([row],MODEL,now=NOW,path=file)
            self.assertEqual(first["new"],1)
            replay=collect_verified_finals([row],MODEL,now=NOW,path=file)
            self.assertEqual(replay["new"],0)
            changed={**row,"hg":4,"provider":"football-data","source_id":"456"}
            quarantine=collect_verified_finals([changed],MODEL,now=NOW,path=file)
            self.assertEqual(quarantine["conflicted"],1)
            self.assertEqual(quarantine["finished_count"],0)
            self.assertEqual(quarantine["conflict_count"],1)

    def test_no_fabricated_old_or_unfinished_score(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"finals.json"
            stale=event(status="finished",kickoff="2026-09-01T15:00:00+00:00",
                        hg=3,ag=1)
            scoreless=event(status="finished",kickoff="2026-10-16T15:00:00+00:00")
            planned=event(status="scheduled",hg=2,ag=0)
            done=collect_verified_finals([stale,scoreless,planned],
                                         MODEL,now=NOW,path=file)
            self.assertEqual(done["finished_count"],0)

    def test_dixon_coles_probability_mass_without_auto_promotion(self):
        probs=dixon_coles_probs(1.5,1.2,-.13)
        self.assertAlmostEqual(sum(probs.values()),1.0,places=8)
        self.assertTrue(all(0<p<1 for p in probs.values()))
        with self.assertRaises(ValueError):
            dixon_coles_probs(1.5,1.2,-.5)

    def test_html_has_no_demo_button_and_real_fixtures_first(self):
        html=Path("supahbetting/static/index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="demo-button"',html)
        self.assertLess(html.index('id="research-upcoming"'),
                        html.index('id="trained"'))
        self.assertIn('id="research-readiness"',html)
        self.assertIn('id="research-recent-results"',html)
        self.assertIn('id="research-legacy"',html)


if __name__=="__main__":
    unittest.main()
