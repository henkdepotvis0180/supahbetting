"""Experimental full-history research model and genuine pre-match shadow log.

Goal-only Poisson until richer publicly verified covariates have demonstrated
out-of-sample value. Recorded forecasts are immutable and never backfilled.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .research_data import LOCAL, atomic_json
from .trained_model import (
    LEAGUES, CURRENT_SEASON, TEST_SEASON, VALIDATION_SEASON, MODEL_FILE,
    LeagueRatings, run_sequential, score, summarize,
)

CANDIDATE_PATH = LOCAL / "candidate_model.json"
SHADOW_PATH = LOCAL / "shadow_predictions.json"
REPORT_PATH = LOCAL / "research_report.json"
ALPHA = 0.04
PRIOR = 3


def _data_matches(inventory):
    rows = inventory["matches"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Geen wedstrijduitslagen")
    seen = set()
    for row in rows:
        if row["league"] not in LEAGUES or not all(
            isinstance(row.get(k), str) for k in ("date", "season", "home", "away", "id")
        ):
            raise ValueError("Ongeldige wedstrijd")
        if (type(row.get("hg")) is not int or type(row.get("ag")) is not int
                or not (0 <= row["hg"] <= 20 and 0 <= row["ag"] <= 20)):
            raise ValueError("Ongeldige eindstand")
        if row["id"] in seen:
            raise ValueError("Dubbele uitslag")
        seen.add(row["id"])
    return sorted(rows, key=lambda r: (r["date"], r["league"], r["home"], r["away"]))


def _history_digest(matches):
    return hashlib.sha256(json.dumps(
        matches, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def train_candidate(inventory, baseline_path=MODEL_FILE):
    matches = _data_matches(inventory)
    states, metrics, by_league = run_sequential(
        matches, ALPHA, PRIOR, {VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON}
    )
    template = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    if template.get("model_type") != "online_empirical_bayes_poisson":
        raise ValueError("Ongeldig sjabloon voor model")
    candidate = deepcopy(template)
    candidate["version"] = "0.12.0-research-experimental"
    candidate["experimental"] = True
    candidate["trained_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    candidate["parameters"]["alpha"] = ALPHA
    candidate["parameters"]["prior_matches"] = PRIOR
    candidate["parameters"]["parameter_selection"] = (
        "v0.11 previously selected parameters; NOT reselected on new results"
    )
    candidate["training_matches"] = len(matches)
    candidate["training_start_date"] = matches[0]["date"]
    candidate["last_observed_result_date"] = matches[-1]["date"]
    candidate["added_older_results"] = sum(m["season"] == "2016-17" for m in matches)
    candidate["prospective_matches"] = sum(
        m["season"] == CURRENT_SEASON for m in matches
    )
    periods = (
        ("validation", VALIDATION_SEASON),
        ("test", TEST_SEASON),
        ("prospective_2026_27", CURRENT_SEASON),
    )
    for name, season in periods:
        candidate["evaluation"][name] = summarize(metrics[season])
    for league in LEAGUES:
        candidate["leagues"][league] = states[league].serialize()
        for name, season in periods:
            candidate["evaluation"]["by_league"][league][name] = summarize(
                by_league[(season, league)]
            )
    candidate["source"] = {
        "project": "openfootball/football.json",
        "homepage": "https://github.com/openfootball/football.json",
        "license": "CC0 1.0 Universal",
        "source_is_real_historical_results": True,
        "uses_bookmaker_odds": False,
        "uses_shot_xg": False,
    }
    candidate["research_provenance"] = {
        "dataset_sha256": _history_digest(matches),
        "season_range_requested": inventory["season_range"],
        "source_coverage": inventory["coverage"],
        "additional_variables_used": [],
        "warning": (
            "Public source may be incomplete or delayed. Retrospective periods are "
            "not new unseen prospective performance. No evidence of betting ROI."
        ),
    }
    return candidate, states


def update_shadow(inventory, states, shadow_path=SHADOW_PATH, today=None, now=None):
    """Generate strictly future-date forecasts and evaluate previous committed ones."""
    from .trained_model import label
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    shadow_path = Path(shadow_path)
    previous = json.loads(shadow_path.read_text(encoding="utf-8")) if shadow_path.exists() else {}
    records = previous.get("predictions", {})
    finished = {m["id"]: m for m in inventory["matches"]}
    graded = 0
    for identifier, saved in records.items():
        if saved.get("actual") is not None:
            continue
        match = finished.get(identifier)
        if match is None:
            continue
        # Strict anti-leakage, including rescheduling; never validate a later prediction.
        if (saved["forecast_created_at"][:10] >= match["date"]
                or saved["scheduled_date"] != match["date"]):
            saved["void_reason"] = "fixture_rescheduled_or_no_lead_time"
            continue
        brier, logloss = score(saved["probabilities"], match)
        saved["actual"] = {"outcome": label(match), "date": match["date"],
                           "brier": round(brier, 8), "logloss": round(logloss, 8)}
        graded += 1
    added = 0
    for fixture in inventory.get("fixtures", []):
        if fixture["date"] <= today.isoformat() or fixture["id"] in records:
            continue
        state = deepcopy(states[fixture["league"]])
        state.season_boundary(fixture["season"])
        probs = state.predict(fixture["home"], fixture["away"])
        records[fixture["id"]] = {
            "fixture_id": fixture["id"], "league": fixture["league"],
            "season": fixture["season"], "home": fixture["home"],
            "away": fixture["away"], "scheduled_date": fixture["date"],
            "forecast_created_at": now.isoformat(timespec="seconds"),
            "as_of_latest_result": inventory.get("latest_result_date"),
            "model": "0.12.0-research-experimental",
            "probabilities": probs, "actual": None,
        }
        added += 1
    if added or graded or not shadow_path.exists():
        atomic_json(shadow_path, {"schema_version": 1, "predictions": records})
    observed = [v["actual"] for v in records.values() if v.get("actual")]
    return {
        "issued_before_match": len(records),
        "new_predictions": added,
        "new_graded": graded,
        "graded_predictions": len(observed),
        "prospective_brier": (
            round(sum(v["brier"] for v in observed) / len(observed), 6)
            if observed else None
        ),
        "prospective_logloss": (
            round(sum(v["logloss"] for v in observed) / len(observed), 6)
            if observed else None
        ),
        "note": "Only forecasts saved BEFORE the match date count as genuine prospective.",
    }


def build_research_report(inventory, candidate, shadow):
    matches = inventory["matches"]
    by_league = {}
    for league, name in LEAGUES.items():
        played = [m for m in matches if m["league"] == league]
        by_league[league] = {
            "name": name, "finished": len(played),
            "last_result_date": max((m["date"] for m in played), default=None),
            "scheduled": sum(f["league"] == league for f in inventory["fixtures"]),
        }
    return {
        "schema_version": 1,
        "mode": "research_only", "source": "OpenFootball CC0",
        "last_checked_at_utc": inventory["fetched_at_utc"],
        "last_verified_result_date": inventory["latest_result_date"],
        "source_date_is_not_today_guarantee": True,
        "training_matches": len(matches),
        "first_match_date": min(m["date"] for m in matches),
        "requested_seasons": inventory["season_range"],
        "competitions": by_league,
        "missing_sources": [v["key"] for v in inventory["coverage"]
                            if v["state"] == "not_published"],
        "retrieval_failures": inventory.get("failed_sources", []),
        "source_coverage": inventory["coverage"],
        "upcoming_fixtures": inventory["fixtures"][:60],
        "new_finished_matches": [
            {k: m[k] for k in ("id", "league", "date", "home", "away", "hg", "ag")}
            for m in matches if m["id"] in set(inventory["new_final_match_ids"])
        ][:120],
        "latest_finished_matches": matches[-35:],
        "historical_metrics": {
            key: candidate["evaluation"][key]
            for key in ("validation", "test", "prospective_2026_27")
        },
        "model_candidate": {
            "version": candidate["version"],
            "parameters": candidate["parameters"],
            "dataset_sha256": candidate["research_provenance"]["dataset_sha256"],
            "trained_on_matches": candidate["training_matches"],
        },
        "shadow_forecast_evaluation": shadow,
        "data_availability": {
            "score_result": "available_when_published",
            "lineups": "not_connected",
            "player_attack_defense_events": "not_connected",
            "confirmed_public_squad_availability": "not_connected",
            "transfers": "not_connected",
            "weather_venue_pitch": "not_connected",
            "individual_private_information": "excluded",
        },
        "disclaimer": (
            "Results may be delayed; no fabricated squad/medical/integrity features. "
            "Historical model scores are not live unseen predictions. "
            "No demonstrated bookmaker profitability."
        ),
    }


def run(inventory, *, candidate_path=CANDIDATE_PATH,
        report_path=REPORT_PATH, shadow_path=SHADOW_PATH, today=None):
    candidate, states = train_candidate(inventory)
    shadow = update_shadow(inventory, states, shadow_path=shadow_path, today=today)
    report = build_research_report(inventory, candidate, shadow)
    atomic_json(candidate_path, candidate)
    atomic_json(report_path, report)
    return report


def main():
    inventory = json.loads((LOCAL / "inventory.json").read_text(encoding="utf-8"))
    report = run(inventory)
    print(json.dumps({
        "training_matches": report["training_matches"],
        "last_verified_result": report["last_verified_result_date"],
        "historical_test": report["historical_metrics"]["test"],
        "prospective_shadow": report["shadow_forecast_evaluation"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
