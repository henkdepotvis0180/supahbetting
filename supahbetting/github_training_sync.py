"""Upload ONLY validated aggregate training results to the experimental GitHub branch.

Works with a downloaded ZIP (no .git directory needed). Never uploads
API keys, local config files, hardware inventory, raw datasets or models.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPOSITORY = "henkdepotvis0180/supahbetting"
BRANCH = "feature/model-v0.11.0"
REMOTE_PATH = "training_reports/local_runs/latest_complete.json"
DEFAULT_REPORT = Path("training_reports/local_optimizer_report.json")
METRIC_KEYS = ("matches", "model_brier", "model_logloss",
               "reference_brier", "reference_logloss",
               "beats_reference_logloss")


class SyncError(ValueError):
    """Safe error text; does not include credentials or response bodies."""


def _metric_summary(data):
    if not isinstance(data, dict):
        raise SyncError("Ongeldige evaluatiemetrieken")
    if not isinstance(data.get("matches"), int) or data["matches"] < 0:
        raise SyncError("Ongeldig wedstrijdtotaal")
    output = {"matches": data["matches"]}
    for key in METRIC_KEYS[1:-1]:
        if key in data:
            val = data[key]
            if isinstance(val, bool) or not isinstance(val, (float, int)) or not math.isfinite(val):
                raise SyncError("Ongeldige evaluatiescore")
            output[key] = val
    if "beats_reference_logloss" in data:
        if not isinstance(data["beats_reference_logloss"], bool):
            raise SyncError("Ongeldige evaluatie-uitkomst")
        output["beats_reference_logloss"] = data["beats_reference_logloss"]
    return output


def _candidate(data):
    if not isinstance(data, dict):
        raise SyncError("Ongeldige kandidaat")
    try:
        alpha = float(data["alpha"])
        prior = int(data["prior_matches"])
    except (KeyError, ValueError, TypeError, OverflowError):
        raise SyncError("Ongeldige kandidaatparameters") from None
    if not math.isfinite(alpha) or not (0 < alpha < 1) or not (1 <= prior <= 100):
        raise SyncError("Ongeldige kandidaatparameters")
    if isinstance(data["prior_matches"], bool) or prior != data["prior_matches"]:
        raise SyncError("Ongeldige prior")
    metrics = _metric_summary(data.get("validation"))
    if not metrics["matches"] or "model_logloss" not in metrics:
        raise SyncError("Validatiegegevens ontbreken")
    return {"alpha": alpha, "prior_matches": prior, "validation": metrics}


def make_snapshot(report):
    """Strict field allowlist; prevents accidental publication of local secrets."""
    if not isinstance(report, dict):
        raise SyncError("Ongeldig trainingsrapport")
    if report.get("complete") is not True or report.get("quick") is not False:
        raise SyncError("Alleen een volledig afgeronde uitgebreide training wordt geüpload")
    candidates = report.get("candidate_results")
    if not isinstance(candidates, list) or len(candidates) != 64:
        raise SyncError("Niet alle 64 kandidaten zijn afgerond")
    if report.get("requested") != 64 or report.get("completed") != 64:
        raise SyncError("De trainingsrun is niet volledig")
    digest = report.get("dataset_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SyncError("Ongeldige datasetvingerafdruk")
    date = report.get("last_result_date")
    if not isinstance(date, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", date):
        raise SyncError("Ongeldige datum van laatste wedstrijduitslag")
    if report.get("production_model_modified") is not False:
        raise SyncError("Productiemodel mag niet zijn gewijzigd")
    rows = [_candidate(row) for row in candidates]
    if len({(row["alpha"], row["prior_matches"]) for row in rows}) != len(rows):
        raise SyncError("Dubbele kandidaatparameters")
    best = _candidate(report.get("best_validation_candidate"))
    if best not in rows:
        raise SyncError("Beste kandidaat ontbreekt in de trainingsresultaten")
    holdouts = report.get("holdouts")
    if not isinstance(holdouts, dict) or not all(
        season in holdouts for season in ("2025-26", "2026-27")
    ):
        raise SyncError("Onafhankelijke testresultaten ontbreken")
    return {
        "schema_version": 1,
        "kind": "completed_local_training_report",
        "published_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_sha256": digest,
        "last_result_date": date,
        "selection_season": "2024-25",
        "completed_candidates": 64,
        "production_model_modified": False,
        "best_validation_candidate": best,
        "candidate_results": rows,
        "holdouts": {
            season: _metric_summary(holdouts[season])
            for season in ("2025-26", "2026-27")
        },
        "warning": "Experimentele backtest, geen bewijs voor positieve betting-ROI.",
    }


def obtain_token():
    token = os.environ.get("SUPAHBETTING_GITHUB_TOKEN", "").strip()
    if not token:
        try:
            proc = subprocess.run(["gh", "auth", "token", "--hostname", "github.com"],
                                  capture_output=True, text=True, timeout=10, check=False)
            if proc.returncode == 0:
                token = proc.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    if len(token) < 12 or any(c.isspace() for c in token):
        raise SyncError(
            "Geen GitHub-toegang: gebruik 'gh auth login' via GitHub CLI "
            "of stel SUPAHBETTING_GITHUB_TOKEN lokaal in. "
            "Het provider-API-token is hiervoor niet bruikbaar."
        )
    return token


def publish_snapshot(snapshot, token):
    """Update exactly one fixed allowlisted path, via GitHub's contents API."""
    url = ("https://api.github.com/repos/" + REPOSITORY +
           "/contents/" + REMOTE_PATH)
    common_headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SupahBetting-training-sync",
    }
    branch_query = quote(BRANCH, safe="")
    current_sha = None
    req = Request(url + "?ref=" + branch_query, headers=common_headers)
    try:
        with urlopen(req, timeout=30) as response:
            data = json.load(response)
            current_sha = data["sha"]
    except HTTPError as error:
        if error.code != 404:
            raise SyncError("GitHub kan huidig rapport niet lezen (HTTP " +
                            str(error.code) + ")") from None
    except (URLError, OSError, ValueError, KeyError):
        raise SyncError("GitHub-verbinding of bestaand rapport ongeldig") from None

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    body = {
        "message": "data: update completed local training report [skip ci]",
        "content": base64.b64encode(payload.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if current_sha is not None:
        body["sha"] = current_sha
    req = Request(url, data=json.dumps(body).encode("utf-8"),
                  headers={**common_headers, "Content-Type": "application/json"},
                  method="PUT")
    try:
        with urlopen(req, timeout=45) as response:
            data = json.load(response)
        return data["content"]["html_url"]
    except HTTPError as error:
        raise SyncError("Upload geweigerd (HTTP " + str(error.code) +
                        "). Controleer Contents: Read and write en de branch.") from None
    except (URLError, OSError, ValueError, KeyError):
        raise SyncError("Upload kon niet worden bevestigd") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publiceer gevalideerd trainingsrapport naar experimentele GitHub-branch")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        snapshot = make_snapshot(report)
        if args.dry_run:
            print("Rapport geldig; zou publiceren naar", REPOSITORY, BRANCH, REMOTE_PATH)
            return 0
        url = publish_snapshot(snapshot, obtain_token())
        print("Training en evaluatie veilig gepubliceerd:", url)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, SyncError):
            print("GitHub-upload niet uitgevoerd:", error)
        else:
            print("GitHub-upload niet uitgevoerd: trainingsrapport ontbreekt of is ongeldig")
        print("De lokale trainingsresultaten blijven behouden.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
