"""Integrity tests for experimental score model and production isolation."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supahbetting.experimental_model import (
    EXPERIMENTAL_FILE, SOURCE_REPORT, _selected_candidate,
    build_experimental_model, write_experimental_model,
)
from supahbetting.trained_model import MODEL_FILE, TrainingError, predict_trained


class ExperimentalModelTests(unittest.TestCase):
    def test_source_report_is_a_complete_real_run(self):
        report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["completed_candidates"], 64)
        self.assertEqual(len(report["candidate_results"]), 64)
        self.assertEqual(_selected_candidate(report)[:2], (0.04, 3))

    def test_rejects_higher_loss_as_winner(self):
        report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
        report["best_validation_candidate"] = report["candidate_results"][-1]
        with self.assertRaises(TrainingError):
            _selected_candidate(report)

    def test_rejects_duplicates(self):
        report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
        report["candidate_results"][1] = report["candidate_results"][0]
        with self.assertRaises(TrainingError):
            _selected_candidate(report)

    def test_actual_replay_matches_published_scores_and_does_not_change_baseline(self):
        before = hashlib.sha256(MODEL_FILE.read_bytes()).digest()
        model = build_experimental_model()
        self.assertEqual(before, hashlib.sha256(MODEL_FILE.read_bytes()).digest())
        self.assertEqual(model["version"], "0.11.0-experimental")
        self.assertTrue(model["experimental"])
        self.assertEqual(model["parameters"]["alpha"], 0.04)
        self.assertEqual(model["parameters"]["prior_matches"], 3)
        self.assertEqual(model["training_matches"], 19884)
        self.assertEqual(model["last_observed_result_date"], "2026-09-20")
        self.assertEqual(model["evaluation"]["test"]["model_logloss"], 0.97725)
        self.assertEqual(model["evaluation"]["prospective_2026_27"]["model_logloss"], 0.9776)
        result = predict_trained(model, "nl.1", "Ajax", "PSV")
        self.assertAlmostEqual(sum(result["probabilities"].values()), 1, places=5)

    def test_bad_data_fingerprint_is_rejected(self):
        report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
        report["dataset_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wrong-report.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(TrainingError):
                build_experimental_model(report_path=path)

    def test_cannot_write_production_model(self):
        with self.assertRaises(TrainingError):
            write_experimental_model(output=MODEL_FILE)

    def test_experimental_output_has_distinct_path(self):
        self.assertNotEqual(EXPERIMENTAL_FILE.resolve(), MODEL_FILE.resolve())


if __name__ == "__main__":
    unittest.main()
