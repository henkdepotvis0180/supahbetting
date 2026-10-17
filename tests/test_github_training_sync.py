"""No-network unit tests for safe upload of completed training reports."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from supahbetting.github_training_sync import (
    BRANCH, REMOTE_PATH, SyncError, main, make_snapshot, obtain_token,
    publish_snapshot,
)


def sample_report():
    candidates = [
        {"alpha": round(.04 + i * .002, 4), "prior_matches": 4,
         "validation": {
             "matches": 2351, "model_brier": .59,
             "model_logloss": round(.95 + i * .002, 4),
             "reference_brier": .64,
             "reference_logloss": 1.08,
             "beats_reference_logloss": True,
             "secret_local_field": "NEVER_UPLOAD",
         }}
        for i in range(64)
    ]
    return {
        "complete": True, "quick": False,
        "requested": 64, "completed": 64,
        "dataset_sha256": "a" * 64,
        "last_result_date": "2026-09-20",
        "production_model_modified": False,
        "best_validation_candidate": candidates[0],
        "candidate_results": candidates,
        "holdouts": {
            "2025-26": {"matches": 2037, "model_brier": .59,
                        "model_logloss": .98},
            "2026-27": {"matches": 295, "model_brier": .58,
                        "model_logloss": .97},
        },
        "api_token": "NEVER_UPLOAD",
        "hardware": {"private_path": "NEVER_UPLOAD"},
    }


class FakeResponse:
    def __init__(self, value):
        self.data = io.BytesIO(json.dumps(value).encode("utf-8"))

    def __enter__(self):
        return self.data

    def __exit__(self, *args):
        self.data.close()


class GithubTrainingSyncTests(unittest.TestCase):
    def test_snapshot_contains_only_allowlisted_fields(self):
        snapshot = make_snapshot(sample_report())
        encoded = json.dumps(snapshot)
        self.assertNotIn("NEVER_UPLOAD", encoded)
        self.assertNotIn("hardware", encoded)
        self.assertEqual(snapshot["completed_candidates"], 64)
        self.assertFalse(snapshot["production_model_modified"])

    def test_incomplete_or_quick_runs_never_publish(self):
        for change in ({"complete": False}, {"quick": True},
                       {"completed": 63}, {"requested": 60},
                       {"holdouts": {}}, {"production_model_modified": True}):
            row = sample_report()
            row.update(change)
            with self.subTest(change=change), self.assertRaises(SyncError):
                make_snapshot(row)

    def test_duplicate_candidates_rejected(self):
        report = sample_report()
        report["candidate_results"][1] = report["candidate_results"][0]
        with self.assertRaises(SyncError):
            make_snapshot(report)

    def test_dry_run_never_reads_token_or_connects(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_text(json.dumps(sample_report()), encoding="utf-8")
            with patch("supahbetting.github_training_sync.obtain_token") as token:
                with patch("supahbetting.github_training_sync.urlopen") as call:
                    result = main(["--dry-run", "--report", str(path)])
            self.assertEqual(result, 0)
            token.assert_not_called()
            call.assert_not_called()

    def test_update_existing_report_only(self):
        snapshot = make_snapshot(sample_report())
        requests = []
        def fake_urlopen(request, timeout=None):
            requests.append(request)
            if request.get_method() == "GET":
                return FakeResponse({"sha": "old-content-sha"})
            body = json.loads(request.data)
            self.assertEqual(body["branch"], BRANCH)
            self.assertEqual(body["sha"], "old-content-sha")
            self.assertEqual(body["message"].endswith("[skip ci]"), True)
            uploaded = base64.b64decode(body["content"]).decode("utf-8")
            self.assertNotIn("NEVER_UPLOAD", uploaded)
            self.assertEqual(json.loads(uploaded)["completed_candidates"], 64)
            return FakeResponse({"content": {"html_url": "https://github.com/demo/report"}})
        with patch("supahbetting.github_training_sync.urlopen", side_effect=fake_urlopen):
            url = publish_snapshot(snapshot, "fake-secret-token")
        self.assertEqual(url, "https://github.com/demo/report")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1].get_method(), "PUT")
        self.assertIn(REMOTE_PATH, requests[1].full_url)

    def test_create_report_when_remote_missing(self):
        def fake_urlopen(req, timeout=None):
            if req.get_method() == "GET":
                raise HTTPError(req.full_url, 404, "Not Found", {}, None)
            body = json.loads(req.data)
            self.assertNotIn("sha", body)
            return FakeResponse({"content": {"html_url": "https://github.com/demo/new"}})
        with patch("supahbetting.github_training_sync.urlopen", side_effect=fake_urlopen):
            result = publish_snapshot(make_snapshot(sample_report()), "fake-secret-token")
        self.assertEqual(result, "https://github.com/demo/new")

    def test_token_environment_takes_precedence(self):
        with patch.dict("os.environ", {"SUPAHBETTING_GITHUB_TOKEN": "test-secret-token-123"}):
            with patch("supahbetting.github_training_sync.subprocess.run") as cmd:
                self.assertEqual(obtain_token(), "test-secret-token-123")
        cmd.assert_not_called()


if __name__ == "__main__":
    unittest.main()
