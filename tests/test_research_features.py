"""Evidence quality gate for player, pitch and transfer features."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from supahbetting.research_features import (
    coverage_report, import_evidence, known_before_match, validate_evidence
)


def evidence(**updates):
    item = {
        "category": "squad_availability", "source_url": "https://example.org/club",
        "publisher": "Club statement", "verification": "official",
        "observed_at": "2026-10-16T12:00:00+00:00",
        "match_date": "2026-10-18", "team": "Alpha",
        "player": "Alex Example", "status": "doubtful",
    }
    item.update(updates)
    return item


NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class ResearchFeaturesTests(unittest.TestCase):
    def test_auditable_public_availability_only(self):
        row = validate_evidence(evidence(), now=NOW)
        self.assertEqual(row["status"], "doubtful")
        self.assertTrue(known_before_match(row, "2026-10-18"))
        self.assertFalse(known_before_match(row, "2026-10-16"))

    def test_no_diagnoses_private_diet_or_bribery_allegations(self):
        for key in ("diagnosis", "diet", "bribery", "medical_record",
                    "rumor", "private_health"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_evidence(evidence(**{key: "unverified"}), now=NOW)

    def test_no_unofficial_squad_predictions_or_transfer_rumors(self):
        with self.assertRaises(ValueError):
            validate_evidence(evidence(verification="rumor"), now=NOW)
        with self.assertRaises(ValueError):
            validate_evidence(evidence(category="public_transfer",
                                       verification="licensed_statistics"), now=NOW)

    def test_no_future_source_dates(self):
        with self.assertRaises(ValueError):
            validate_evidence(evidence(observed_at="2026-10-19T12:00:00+00:00"), now=NOW)

    def test_postmatch_stats_cannot_appear_before_game(self):
        with self.assertRaises(ValueError):
            validate_evidence(evidence(
                category="player_attack", status=None,
                observed_at="2026-10-16T12:00:00+00:00",
                metrics={"shots": 3}
            ), now=NOW)

    def test_unlicensed_fields_rejected(self):
        with self.assertRaises(ValueError):
            validate_evidence(evidence(metrics={"unverified_influence": 15}), now=NOW)

    def test_local_aggregation_never_trains_from_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "context.json"
            # Live clock is after 2026-10-16.
            result = import_evidence([evidence()], path=path)
            self.assertEqual(result["added"], 1)
            next_result = import_evidence([evidence()], path=path)
            self.assertEqual(next_result["added"], 0)
            covered = coverage_report(path)
            self.assertEqual(covered["records"], 1)
            self.assertFalse(covered["categories"]["squad_availability"]["training_enabled"])


if __name__ == "__main__":
    unittest.main()
