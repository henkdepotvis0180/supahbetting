"""Build a separate reproducible experimental Poisson model from a verified local run.

The original production model remains unchanged. Ratings are completely
replayed from historical scores with the selected hyperparameters; simply
editing the baseline JSON parameters would yield invalid predictions.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .local_optimizer import fingerprint
from .trained_model import (
    CURRENT_SEASON, TEST_SEASON, VALIDATION_SEASON, LEAGUES, MODEL_FILE,
    load_matches, run_sequential, summarize, predict_trained, TrainingError,
)

EXPERIMENTAL_FILE = Path(__file__).parent / "models" / "baseline_v0.11.0_experimental.json"
SOURCE_REPORT = Path("training_reports/local_runs/latest_complete.json")
EXPERIMENT_VERSION = "0.11.0-experimental"


def _equal_metric(actual, expected, description):
    if not isinstance(expected, dict) or actual["matches"] != expected.get("matches"):
        raise TrainingError("Verschillende aantallen wedstrijden: " + description)
    for key in ("model_brier", "model_logloss", "reference_brier", "reference_logloss"):
        if key in expected and not math.isclose(
            actual[key], expected[key], rel_tol=0, abs_tol=0.000011
        ):
            raise TrainingError("Trainingsrapport komt niet overeen: " + description + "/" + key)


def _selected_candidate(snapshot):
    if snapshot.get("schema_version") != 1 or snapshot.get("kind") != "completed_local_training_report":
        raise TrainingError("Onbekend experimenteel trainingsrapport")
    if snapshot.get("production_model_modified") is not False:
        raise TrainingError("Trainingsrapport mag productiemodel niet wijzigen")
    candidates = snapshot.get("candidate_results")
    if not isinstance(candidates, list) or len(candidates) != 64:
        raise TrainingError("Alle 64 experimentele kandidaten zijn vereist")
    try:
        keyed = [(float(c["alpha"]), int(c["prior_matches"])) for c in candidates]
        selected = min(
            candidates,
            key=lambda c: (c["validation"]["model_logloss"],
                           c["validation"]["model_brier"],
                           c["alpha"], c["prior_matches"]),
        )
        best = snapshot["best_validation_candidate"]
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise TrainingError("Trainingsrapport mist geldige kandidaatresultaten") from exc
    if len(set(keyed)) != 64 or selected != best:
        raise TrainingError("Gekozen model is niet de beste validatiekandidaat")
    alpha, prior = float(best["alpha"]), int(best["prior_matches"])
    if not (0 < alpha < 1 and 1 <= prior <= 100 and math.isfinite(alpha)):
        raise TrainingError("Trainingsparameters buiten veilig bereik")
    return alpha, prior, best["validation"]


def build_experimental_model(
    data_dir=Path("data/historical"), baseline_path=MODEL_FILE, report_path=SOURCE_REPORT
):
    snapshot = json.loads(Path(report_path).read_text(encoding="utf-8"))
    alpha, prior, expected_validation = _selected_candidate(snapshot)
    matches = load_matches(data_dir)
    digest = fingerprint(matches)
    if digest != snapshot.get("dataset_sha256"):
        raise TrainingError("Historische data komen niet overeen met gepubliceerde training")
    latest = max(m["date"] for m in matches)
    if latest != snapshot.get("last_result_date"):
        raise TrainingError("Laatste uitslagdatum komt niet overeen")
    base = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    if (base.get("model_type") != "online_empirical_bayes_poisson"
            or base.get("version") != "0.10.0"
            or base.get("training_matches") != len(matches)
            or base.get("last_observed_result_date") != latest):
        raise TrainingError("Onjuiste of niet bijpassende productie-baseline")
    states, pooled, by_league = run_sequential(
        matches, alpha, prior, {VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON}
    )
    summaries = {
        "validation": summarize(pooled[VALIDATION_SEASON]),
        "test": summarize(pooled[TEST_SEASON]),
        "prospective_2026_27": summarize(pooled[CURRENT_SEASON]),
    }
    _equal_metric(summaries["validation"], expected_validation, "validatie")
    published_holdouts = snapshot.get("holdouts", {})
    if not isinstance(published_holdouts, dict):
        raise TrainingError("Holdoutmetingen ontbreken")
    _equal_metric(summaries["test"], published_holdouts.get(TEST_SEASON), "test")
    _equal_metric(summaries["prospective_2026_27"],
                  published_holdouts.get(CURRENT_SEASON), "2026/27")

    candidate = deepcopy(base)
    candidate["version"] = EXPERIMENT_VERSION
    candidate["trained_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    candidate["experimental"] = True
    candidate["parameters"]["alpha"] = alpha
    candidate["parameters"]["prior_matches"] = prior
    candidate["parameters"]["parameter_selection"] = (
        "64 kandidaatcombinaties, geselecteerd op alleen 2024/25 log loss"
    )
    candidate["evaluation"].update(summaries)
    for league in LEAGUES:
        candidate["leagues"][league] = states[league].serialize()
        stats = candidate["evaluation"]["by_league"][league]
        stats["validation"] = summarize(by_league[(VALIDATION_SEASON, league)])
        stats["test"] = summarize(by_league[(TEST_SEASON, league)])
        stats["prospective_2026_27"] = summarize(by_league[(CURRENT_SEASON, league)])
    candidate["experiment_provenance"] = {
        "published_training_report": SOURCE_REPORT.as_posix(),
        "dataset_sha256": digest,
        "selected_on": VALIDATION_SEASON,
        "replayed_historical_scores": True,
        "productiemodel_gewijzigd": False,
        "note": (
            "Retrospectieve vergelijking. Oudere holdoutresultaten zijn al bekeken; "
            "nieuwe toekomstige wedstrijden zijn nodig voor onafhankelijke bevestiging. "
            "Geen bewezen positieve ROI tegen bookmakerprijzen."
        ),
    }
    # Ensure the normal dashboard predictor can consume the whole reconstructed model.
    league = "nl.1"
    teams = list(candidate["leagues"][league]["teams"])
    if len(teams) < 2:
        raise TrainingError("Onvoldoende teamratings in het nieuwe model")
    prediction = predict_trained(candidate, league, teams[0], teams[1])
    if not math.isclose(sum(prediction["probabilities"].values()), 1, abs_tol=0.00001):
        raise TrainingError("Kansberekeningen van experimenteel model zijn ongeldig")
    return candidate


def write_experimental_model(output=EXPERIMENTAL_FILE):
    output = Path(output)
    if output.resolve() == MODEL_FILE.resolve():
        raise TrainingError("Productie-basismodel overschrijven is niet toegestaan")
    candidate = build_experimental_model()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    return output, candidate


def main():
    output, model = write_experimental_model()
    print("Experimenteel model gereconstrueerd:", output)
    print("Parameters:", model["parameters"]["alpha"], model["parameters"]["prior_matches"])
    for period in ("validation", "test", "prospective_2026_27"):
        print(period, model["evaluation"][period])
    print("Productiemodel blijft ongewijzigd:", MODEL_FILE)


if __name__ == "__main__":
    main()
