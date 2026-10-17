"""Fast local start-up audit for the experimental research model.

Never downloads data during HTTP GET; never claims a stale model is current.
Checks the ten-year baseline, real data provenance and release compatibility.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
import json
from pathlib import Path

from .research_data import LOCAL
from .research_model import _history_digest
from .research_upcoming import RESEARCH_MODEL, PUBLISHED_MODEL
from .trained_model import LEAGUES, load_pretrained, TrainingError


def audit_startup(*, folder=LOCAL, now=None, model=None):
    now = now or datetime.now(timezone.utc)
    folder = Path(folder)
    inventory_path = folder / "inventory.json"
    local_model = folder / "candidate_model.json"
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        inventory = None
    if model is None:
        try:
            augmented = folder / "augmented_model_local.json"
            chosen = augmented if augmented.exists() else (
                local_model if local_model.is_file() else PUBLISHED_MODEL
            )
            model = load_pretrained(chosen)
        except (TrainingError, ValueError, OSError):
            model = None
    if model and model.get("version") not in (
        "0.12.0-research-experimental", "0.13.0-local-augmented"
    ):
        model = None
    rows = inventory.get("matches", []) if isinstance(inventory, dict) else []
    earliest = min((m.get("date", "") for m in rows if isinstance(m, dict)), default=None)
    latest = max((m.get("date", "") for m in rows if isinstance(m, dict)), default=None)
    model_date = model.get("last_observed_result_date") if model else None
    active_seasons = {
        m.get("season") for m in rows if isinstance(m, dict) and m.get("season")
    }
    try:
        age_days = (now.date() - date.fromisoformat(model_date)).days if model_date else None
    except (ValueError, TypeError):
        age_days = None
    enough_years = (
        bool(earliest and latest and earliest <= "2016-12-31" and
             len(active_seasons) >= 10)
        if rows else
        bool(model and model.get("training_start_date", "9999") <= "2016-12-31"
             and model.get("training_matches", 0) >= 15000)
    )
    # Overall ten-year coverage must NOT be confused with coverage for each
    # league: OpenFootball's Dutch results currently begin only in 2018/19.
    league_coverage={}
    for league in LEAGUES:
        if league=="be.1":
            continue
        league_rows=[row for row in rows if row.get("league")==league]
        if league_rows:
            first=min(row["date"] for row in league_rows)
            last=max(row["date"] for row in league_rows)
            observed_seasons=len({row["season"] for row in league_rows})
            games=len(league_rows)
        elif model is not None:
            diagnostic=model.get("evaluation",{}).get("by_league",{}).get(league,{})
            counts=diagnostic.get("season_matches",{})
            known=[season for season,num in counts.items() if num]
            first=min(known)+"-01-01" if known else None
            last=model.get("leagues",{}).get(league,{}).get("last_result_date")
            observed_seasons=len(known)
            games=model.get("leagues",{}).get(league,{}).get("training_matches",0)
        else:
            first=last=None
            observed_seasons=games=0
        league_coverage[league]={
            "league":league,
            "season_count":observed_seasons,
            "at_least_10_seasons":observed_seasons>=10,
            "earliest":first,
            "latest":last,
            "match_count":games,
        }
    ten_year_leagues=sum(cov["at_least_10_seasons"]
                        for cov in league_coverage.values())
    source_drift = None
    if inventory and model and rows and model.get("research_provenance"):
        # A historical inventory and locally trained model must match exactly.
        if model.get("version") == "0.13.0-local-augmented":
            try:
                from .research_daily_results import merge_verified_locally
                merged, _ = merge_verified_locally(
                    inventory, finals_path=folder / "provider_finals_local.json")
                expected_digest = _history_digest(merged["matches"])
            except (OSError, ValueError, KeyError):
                expected_digest = None
        else:
            expected_digest = _history_digest(rows)
        source_drift = (
            expected_digest is None or
            model["research_provenance"].get("dataset_sha256") != expected_digest
        )
    available = model is not None
    holdout = (model or {}).get("evaluation", {}).get("test", {})
    validation = isinstance(holdout.get("model_logloss"), (float, int)) and holdout.get("matches",0) >= 1000
    warning = (
        "Model ontbreekt; lokale training of ingebouwd onderzoeksmodel nodig"
        if not available else
        "Geen voldoende grote chronologische modeltoets beschikbaar"
        if not validation else
        "Minder dan tien seizoenen bronhistorie beschikbaar"
        if not enough_years else
        "Historische data veranderd: onderzoeksmodel moet opnieuw worden getraind"
        if source_drift else
        "Laatste modeluitslag is ernstig verouderd"
        if age_days is None or age_days >= 90 else
        "Laatste modeluitslag loopt achter; controle van gisteren/vandaag nodig"
        if age_days >= 2 else
        "Model is aanwezig en uitslagen zijn recent; toekomstprestaties onbewezen"
    )
    return {
        "available": available,
        "level": "missing" if not available else
                 "degraded" if not validation or not enough_years or source_drift or age_days is None or age_days >= 14 else
                 "caution" if age_days >= 2 else "ready",
        "ten_year_history": enough_years,
        "historical_test_available": validation,
        "historical_test_match_count": holdout.get("matches"),
        "historical_test_logloss": holdout.get("model_logloss"),
        "observed_seasons": len(active_seasons),
        "leagues_with_10_seasons": ten_year_leagues,
        "active_league_count":len(league_coverage),
        "league_history":league_coverage,
        "local_scores": len(rows),
        "model_matches": model.get("training_matches") if model else None,
        "earliest_local_date": earliest,
        "model_data_through": model_date,
        "model_age_days": age_days,
        "historical_data_changed": source_drift,
        "model_version": model.get("version") if model else None,
        "warn": warning,
        "last_audit_at_utc": now.isoformat(timespec="seconds"),
        "is_prospectively_validated": False,
        "is_profitable_vs_bookmaker_prices": False,
        "message": (
            "Historische kalibratie kan worden beoordeeld; echte toekomstige "
            "prestaties en bookmaker-waarde moeten apart worden bewezen."
        ),
    }


def main():
    status = audit_startup()
    print("SupahBetting Research v0.13 · lokale startcontrole")
    print("Model:", status["model_version"] or "ontbreekt")
    print("Historische basis (>=10 seizoenen):", "ja" if status["ten_year_history"] else "niet bevestigd")
    print("Recentste uitslag:", status["model_data_through"] or "onbekend")
    print("Status:", status["level"], "|", status["warn"])
    print("Website blijft altijd bereikbaar. Bron- en modelvernieuwing loopt in de monitor.")


if __name__ == "__main__":
    main()
