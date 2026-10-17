"""Quality indicators must represent source freshness, not fetch success."""
import unittest
from datetime import date
from supahbetting.research_quality import audit_quality


class ResearchQualityTests(unittest.TestCase):
    def fixture(self):
        return {
            "matches": [
                {"id":"n","league":"nl.1","date":"2026-09-20",
                 "season":"2026-27","home":"A","away":"B","hg":1,"ag":0},
                {"id":"b","league":"be.1","date":"2025-11-02",
                 "season":"2025-26","home":"C","away":"D","hg":1,"ag":0},
            ],
            "coverage": [{"key":"2026-27/be.1","state":"not_published"}],
            "latest_result_date":"2026-09-20",
            "new_final_match_ids": [],
            "initial_backfill_matches": 22665,
            "first_import_at_utc":"2026-10-17T12:00:00+00:00",
            "fetched_at_utc":"2026-10-17T13:00:00+00:00",
            "failed_sources":[],
        }

    def test_recent_download_does_not_hide_old_scores(self):
        state=audit_quality(self.fixture(),today=date(2026,10,17))
        self.assertTrue(state["is_stale"])
        self.assertEqual(state["days_since_latest_result"],27)
        self.assertEqual(state["new_results_since_previous_scan"],0)
        self.assertEqual(state["initial_backfill_matches"],22665)
        self.assertEqual(state["leagues"]["nl.1"]["days_since_last_result"],27)
        self.assertEqual(state["leagues"]["nl.1"]["freshness"],"stale")
        self.assertEqual(state["leagues"]["be.1"]["freshness"],"severely_stale")
        self.assertEqual(state["missing_source_file_count"],1)

    def test_fresh_scores_are_distinct_from_fetch_timestamp(self):
        data=self.fixture()
        data["latest_result_date"]="2026-10-16"
        data["matches"][0]["date"]="2026-10-16"
        data["new_final_match_ids"]=["n"]
        state=audit_quality(data,today=date(2026,10,17))
        self.assertFalse(state["is_stale"])
        self.assertEqual(state["days_since_latest_result"],1)
        self.assertEqual(state["new_results_since_previous_scan"],1)
        self.assertEqual(state["leagues"]["be.1"]["freshness"],"severely_stale")

    def test_unknown_coverage_is_not_assumed_current(self):
        state=audit_quality({"matches":[],"coverage":[],"failed_sources":[]},
                            today=date(2026,10,17))
        self.assertTrue(state["is_stale"])
        self.assertIsNone(state["days_since_latest_result"])
        self.assertEqual(state["leagues"]["nl.1"]["freshness"],"no_results")


if __name__=="__main__":
    unittest.main()
