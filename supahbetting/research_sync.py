"""Safe, resumable GitHub publication from a downloaded ZIP.

Publishes only audited public CC0 results, experimental model and a summary
to feature/research-data-v0.12.0. Never writes production or main.
"""
from __future__ import annotations

import base64
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .github_training_sync import obtain_token, SyncError
from .research_model import CANDIDATE_PATH, REPORT_PATH
from .research_data import LOCAL
from .trained_model import LEAGUES

REPO = "henkdepotvis0180/supahbetting"
BRANCH = "feature/research-data-v0.12.0"
MODEL_REMOTE = "supahbetting/models/research_v0.12.0_experimental.json"
REPORT_REMOTE = "training_reports/research_live/latest.json"
SCORES_PREFIX = "data/research/verified"
MAX_UPLOAD_BYTES = 900_000


def safe_scores(matches, league):
    """Explicit field whitelist to keep private/local data out of GitHub."""
    if league not in LEAGUES:
        raise SyncError("Onbekende competitie")
    records = []
    for m in matches:
        if m["league"] != league:
            continue
        if any(k not in m for k in ("id", "season", "date", "home", "away", "hg", "ag")):
            raise SyncError("Ongeldige wedstrijduitslag")
        if (type(m["hg"]) is not int or type(m["ag"]) is not int
                or not 0 <= m["hg"] <= 20 or not 0 <= m["ag"] <= 20):
            raise SyncError("Ongeldige eindstand")
        records.append({k: m[k] for k in (
            "id", "season", "date", "home", "away", "hg", "ag"
        )})
    return {"schema_version": 1, "league": league, "license": "CC0-1.0",
            "source": "openfootball/football.json", "matches": records}


def safe_report(report):
    if not isinstance(report, dict) or report.get("mode") != "research_only":
        raise SyncError("Onjuist onderzoeksrapport")
    if not isinstance(report.get("training_matches"), int) or report["training_matches"] < 1:
        raise SyncError("Onderzoeksrapport zonder wedstrijden")
    if not isinstance(report.get("model_candidate"), dict):
        raise SyncError("Experimenteel model ontbreekt")
    keys = (
        "schema_version", "mode", "source", "last_checked_at_utc",
        "last_verified_result_date", "training_matches", "first_match_date",
        "requested_seasons", "competitions", "missing_sources",
        "retrieval_failures", "source_coverage", "upcoming_fixtures",
        "latest_finished_matches", "derived_team_form_preview", "historical_metrics", "model_candidate",
        "source_quality", "new_finished_results_since_last_check", "initial_backfill_matches",
        "shadow_forecast_evaluation", "data_availability", "disclaimer"
    )
    return {key: report[key] for key in keys if key in report}


def safe_model(model):
    if (not isinstance(model, dict) or model.get("version") != "0.12.0-research-experimental"
            or model.get("experimental") is not True
            or model.get("model_type") != "online_empirical_bayes_poisson"):
        raise SyncError("Alleen het experimentele onderzoeksmodel mag worden geüpload")
    if model["parameters"]["alpha"] != .04 or model["parameters"]["prior_matches"] != 3:
        raise SyncError("Onverwachte onderzoeksparameters")
    return model


def prepare_payloads(inventory, report, model):
    if len(inventory["matches"]) != report["training_matches"]:
        raise SyncError("Rapport en brondata komen niet overeen")
    if model["training_matches"] != report["training_matches"]:
        raise SyncError("Model en rapport komen niet overeen")
    if model["research_provenance"]["dataset_sha256"] != report["model_candidate"]["dataset_sha256"]:
        raise SyncError("Datasetvingerafdruk komt niet overeen")
    files = {}
    for league in LEAGUES:
        files[f"{SCORES_PREFIX}/{league}.json"] = safe_scores(inventory["matches"], league)
    files[MODEL_REMOTE] = safe_model(model)
    files[REPORT_REMOTE] = safe_report(report)
    return files


def _send_one(path, payload, token, *, remote_open=urlopen):
    if not (path.startswith(SCORES_PREFIX + "/") or path in (MODEL_REMOTE, REPORT_REMOTE)):
        raise SyncError("GitHub-bestand valt buiten toegestane paden")
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise SyncError("Bronbestand te groot voor veilige GitHub-contents-upload: " + path)
    url = "https://api.github.com/repos/" + REPO + "/contents/" + quote(path, safe="/")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SupahBetting-research-sync",
    }
    sha = None
    try:
        with remote_open(Request(url + "?ref=" + quote(BRANCH, safe=""),
                                 headers=headers), timeout=30) as reply:
            existing = json.load(reply)
            sha = existing["sha"]
            if existing.get("encoding") == "base64" and existing.get("content"):
                old = base64.b64decode(existing["content"])
                if old == raw:
                    return "unchanged"
    except HTTPError as error:
        if error.code != 404:
            raise SyncError("GitHub rapportcontrole mislukt: HTTP " + str(error.code)) from None
    except (ValueError, OSError, URLError, KeyError):
        raise SyncError("GitHub kon bestaand onderzoeksbestand niet verifiëren") from None
    body = {
        "message": "data(research): refresh verified CC0 results and experimental evidence [skip ci]",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": BRANCH,
    }
    if sha is not None:
        body["sha"] = sha
    try:
        with remote_open(
            Request(url, data=json.dumps(body).encode("utf-8"),
                    headers={**headers, "Content-Type": "application/json"},
                    method="PUT"), timeout=45
        ) as reply:
            result = json.load(reply)
        if not result.get("commit", {}).get("sha"):
            raise SyncError("GitHub bevestigde het opslaan niet")
        return "updated"
    except HTTPError as exc:
        raise SyncError("Upload mislukt (HTTP " + str(exc.code) + "): " + path) from None
    except (ValueError, OSError, URLError):
        raise SyncError("Upload niet bevestigd voor: " + path) from None


def publish(inventory, report, model, token=None):
    files = prepare_payloads(inventory, report, model)
    token = token or obtain_token()
    results = {}
    # Manifest/report LAST. Interrupted sync can safely retry unchanged files.
    for path, payload in files.items():
        results[path] = _send_one(path, payload, token)
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        inventory = json.loads((LOCAL / "inventory.json").read_text(encoding="utf-8"))
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        model = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
        files = prepare_payloads(inventory, report, model)
        if args.dry_run:
            print("Veilige bestanden geselecteerd:", list(files))
            return 0
        uploaded = publish(inventory, report, model)
        print("GitHub branch:", BRANCH)
        print(json.dumps(uploaded, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Onderzoeksdata niet gepubliceerd:", str(exc) if isinstance(exc, SyncError)
              else "Ontbrekende of ongeldige lokale bestanden")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
