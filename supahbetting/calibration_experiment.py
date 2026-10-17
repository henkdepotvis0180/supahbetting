"""Chronological offline calibration experiment; never changes production model.

Fit temperature on 2024-25 only, score 2025-26 and 2026-27 without
seeing their outcomes before the respective predictions.
"""
from __future__ import annotations
import json
import math
from collections import defaultdict
from pathlib import Path
from supahbetting.model_calibration import fit_temperature, temperature_scale
from supahbetting.trained_model import (
    LEAGUES, LeagueRatings, load_matches, season_groups, label,
    score, VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON,
)


def evaluate(data_dir="data/historical", model_path="supahbetting/models/baseline.json"):
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    alpha = model["parameters"]["alpha"]
    prior = model["parameters"]["prior_matches"]
    states = {league: LeagueRatings(alpha, prior) for league in LEAGUES}
    forecasts = defaultdict(list)
    for group in season_groups(load_matches(data_dir)):
        state = states[group[0]["league"]]
        state.season_boundary(group[0]["season"])
        # Predict every fixture before incorporating any result from that day.
        for match in group:
            if match["season"] in (VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON):
                forecasts[match["season"]].append((state.predict(match["home"], match["away"]), match))
        for match in group:
            state.update(match)
    validation = [(p, label(m)) for p, m in forecasts[VALIDATION_SEASON]]
    temperature = fit_temperature(validation)
    result = {
        "source": "OpenFootball historical CSV (locally checked in)",
        "training_model_version": model["version"],
        "last_observed_result_date": model["last_observed_result_date"],
        "temperature_fit_season": VALIDATION_SEASON,
        "temperature": temperature,
        "production_model_modified": False,
        "periods": {},
    }
    for season in (VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON):
        rows = forecasts[season]
        if not rows:
            continue
        base = [score(p, m) for p, m in rows]
        calibrated = [score(temperature_scale(p, temperature), m) for p, m in rows]
        result["periods"][season] = {
            "matches": len(rows),
            "baseline_brier": round(sum(x[0] for x in base)/len(rows), 6),
            "candidate_brier": round(sum(x[0] for x in calibrated)/len(rows), 6),
            "baseline_logloss": round(sum(x[1] for x in base)/len(rows), 6),
            "candidate_logloss": round(sum(x[1] for x in calibrated)/len(rows), 6),
        }
    return result


def main():
    report = evaluate()
    print(json.dumps(report, indent=2))
    output = Path("training_reports/calibration_experiment_v0.11.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
