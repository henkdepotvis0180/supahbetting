"""Monitor publishes only changed successfully processed match data."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from supahbetting.research_monitor import cycle


class ResearchMonitorTests(unittest.TestCase):
    def inventory(self, score=2):
        return {
            "matches": [{
                "id": "match-1", "league": "nl.1", "season": "2026-27",
                "date": "2026-10-16", "home": "A", "away": "B",
                "hg": score, "ag": 0
            }],
            "fixtures": [], "latest_result_date": "2026-10-16",
            "new_final_match_ids": ["match-1"],
            "coverage": [{"key": "2026-27/nl.1", "state": "downloaded"}],
            "failed_sources": [],
        }

    def test_only_new_scores_trigger_upload_and_retries_after_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            published = []
            values = [self.inventory(), self.inventory(), self.inventory(3)]
            def refresh_fake(**kwargs):
                return values.pop(0)
            def train_fake(inventory, candidate_path=None,
                           report_path=None, shadow_path=None):
                Path(candidate_path).write_text(json.dumps({"version": "local"}))
                return {"shadow_forecast_evaluation": {"graded_predictions": 0}}
            def publish_fake(inventory, report, model):
                published.append(inventory["matches"][0]["hg"])
            kwargs = {
                "data_dir": temp, "refresh_fn": refresh_fake,
                "research_fn": train_fake, "publish_fn": publish_fake,
            }
            one = cycle(**kwargs)
            self.assertEqual(one["sync_state"], "published")
            two = cycle(**kwargs)
            self.assertEqual(two["sync_state"], "not_required")
            three = cycle(**kwargs)
            self.assertEqual(three["sync_state"], "published")
            self.assertEqual(published, [2, 3])

    def test_upload_disabled_never_reads_github_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            def train_fake(inventory, candidate_path=None,
                           report_path=None, shadow_path=None):
                return {"shadow_forecast_evaluation": {"graded_predictions": 0}}
            def forbid(*args):
                self.fail("Upload must not be attempted")
            result = cycle(
                upload=False, data_dir=temp,
                refresh_fn=lambda **kw: self.inventory(),
                research_fn=train_fake, publish_fn=forbid
            )
            self.assertEqual(result["sync_state"], "disabled")

    def test_failing_upload_does_not_mark_scores_as_synced(self):
        with tempfile.TemporaryDirectory() as temp:
            def train_fake(inventory, candidate_path=None,
                           report_path=None, shadow_path=None):
                Path(candidate_path).write_text(json.dumps({"version":"test"}))
                return {"shadow_forecast_evaluation":{"graded_predictions":0}}
            def forbid(*args):
                raise RuntimeError("mock network error")
            one=cycle(data_dir=temp,
                refresh_fn=lambda **kw:self.inventory(),
                research_fn=train_fake,publish_fn=forbid)
            self.assertEqual(one["sync_state"],"failed:RuntimeError")
            self.assertFalse((Path(temp)/"monitor_state.json").exists())


if __name__=="__main__":
    unittest.main()
