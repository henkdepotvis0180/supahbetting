import json
import tempfile
import unittest
from pathlib import Path

from supahbetting.local_optimizer import (
    candidate_grid, choose_best, fingerprint, optimize, save_json,
)


class LocalOptimizerTests(unittest.TestCase):
    def test_grid_is_bounded(self):
        self.assertEqual(len(candidate_grid()), 64)
        self.assertEqual(len(set(candidate_grid())), 64)

    def test_selection_uses_validation_only(self):
        candidates = [
            {"alpha": .1, "prior_matches": 4,
             "validation": {"model_logloss": 1.0, "model_brier": .6}},
            {"alpha": .2, "prior_matches": 4,
             "validation": {"model_logloss": 1.1, "model_brier": .5}},
        ]
        self.assertEqual(choose_best(candidates)["alpha"], .1)

    def test_fingerprint_changes_with_data(self):
        row = {"date": "2024-01-01", "hg": 1}
        self.assertNotEqual(fingerprint([row]), fingerprint([{**row, "hg": 2}]))

    def test_atomic_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            save_json(path, {"completed": 3})
            self.assertEqual(json.loads(path.read_text())["completed"], 3)
            self.assertFalse(Path(str(path) + ".tmp").exists())

    def test_limits(self):
        with self.assertRaises(ValueError):
            optimize([{"date": "2024-01-01"}], workers=17)
        with self.assertRaises(ValueError):
            optimize([{"date": "2024-01-01"}], hours=5)


if __name__ == "__main__":
    unittest.main()
