"""No-network GitHub publishing tests; never expose secrets or production."""
import base64
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from supahbetting.research_sync import (
    BRANCH, MODEL_REMOTE, REPORT_REMOTE, SCORES_PREFIX,
    _send_one, prepare_payloads, safe_report, safe_scores, safe_model,
)
from supahbetting.github_training_sync import SyncError
from supahbetting.trained_model import LEAGUES


class Response:
    def __init__(self, data):
        self.stream = io.BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):
        return self.stream
    def __exit__(self, *args):
        self.stream.close()


class ResearchSyncTests(unittest.TestCase):
    def test_score_allowlist(self):
        row = {
            "id":"fixed-1","league":"nl.1","season":"2026-27",
            "date":"2026-10-16","home":"Alpha","away":"Beta",
            "hg":1,"ag":0,"private_token":"DO_NOT_UPLOAD",
            "private_health":"DO_NOT_UPLOAD",
        }
        output=safe_scores([row],"nl.1")
        self.assertEqual(len(output["matches"]),1)
        self.assertNotIn("DO_NOT_UPLOAD", json.dumps(output))

    def test_report_only_public_summary(self):
        report={"mode":"research_only","training_matches":1,
                "model_candidate":{"dataset_sha256":"a"*64},
                "private_paths":"DO_NOT_UPLOAD", "token":"DO_NOT_UPLOAD"}
        output=safe_report(report)
        self.assertNotIn("DO_NOT_UPLOAD", json.dumps(output))

    def test_publish_targets_only_new_experimental_branch(self):
        self.assertEqual(BRANCH,"feature/research-data-v0.12.0")
        self.assertTrue(MODEL_REMOTE.endswith("research_v0.12.0_experimental.json"))
        self.assertNotEqual(MODEL_REMOTE,"supahbetting/models/baseline.json")
        self.assertTrue(REPORT_REMOTE.startswith("training_reports/research_live/"))

    def test_no_upload_to_arbitrary_paths(self):
        with self.assertRaises(SyncError):
            _send_one("supahbetting/models/baseline.json",{}, "fake-token")

    def test_contents_api_creates_and_uses_experimental_branch(self):
        requests=[]
        def remote(req,timeout=None):
            requests.append(req)
            if req.get_method() == "GET":
                raise HTTPError(req.full_url,404,"not found",{},None)
            body=json.loads(req.data)
            self.assertEqual(body["branch"],BRANCH)
            self.assertNotIn("sha",body)
            stored=json.loads(base64.b64decode(body["content"]).decode())
            self.assertEqual(stored["source"],"openfootball/football.json")
            return Response({"commit":{"sha":"created-sha"}})
        result=_send_one(
            f"{SCORES_PREFIX}/nl.1.json",
            {"source":"openfootball/football.json"},
            "fake-token",remote_open=remote
        )
        self.assertEqual(result,"updated")
        self.assertEqual([r.get_method() for r in requests],["GET","PUT"])

    def test_existing_file_is_not_committed_twice(self):
        payload={"source":"openfootball/football.json"}
        raw=(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n").encode()
        def remote(req,timeout=None):
            if req.get_method()=="GET":
                return Response({"sha":"oldsha","encoding":"base64",
                                 "content":base64.b64encode(raw).decode()})
            self.fail("Unchanged content must not be pushed")
        self.assertEqual(_send_one(f"{SCORES_PREFIX}/nl.1.json",
                                   payload,"fake-token",remote_open=remote),"unchanged")

    def test_rejects_wrong_model_version(self):
        with self.assertRaises(SyncError):
            safe_model({"version":"0.10.0","experimental":False,
                        "model_type":"online_empirical_bayes_poisson"})


if __name__=="__main__":
    unittest.main()
