"""Public, source-attributed optional football context: NEVER invent player facts.

Signals are stored as evidence, not plugged into predictions until a
chronological feature-ablation study proves they add out-of-sample value.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

from .research_data import atomic_json, LOCAL

EVIDENCE_PATH = LOCAL / "verified_context.json"
CATEGORIES = {
    "squad_availability",  # Only officially public 'available/doubtful/out'; no diagnosis.
    "announced_lineup",    # Official announced pre-match lineup.
    "public_transfer",     # Confirmed official signing only, no rumors.
    "player_attack",       # Licensed verified post-match event summaries.
    "player_defense",
    "team_style",
    "fixture_rest",
    "venue_surface",       # Verified grass/artificial surface metadata.
    "venue_condition",     # Official pre-match pitch inspection, if available.
    "weather_forecast",    # The forecast available before kickoff, not hindsight weather.
    "referee_appointment",
    "manager_change",
}
METRIC_FIELDS = {
    "shots", "shots_on_target", "goals", "assists", "key_passes",
    "progressive_passes", "dribbles", "xg", "xa",
    "tackles", "interceptions", "clearances", "blocks", "aerial_duels",
    "pressures", "passes_completed", "passes_attempted",
    "recoveries", "duels_won", "yellow_cards", "red_cards",
    "days_rest", "travel_km", "temperature_c", "wind_kmh",
    "rainfall_mm", "surface_quality_score",
}
STATUS = {"available", "doubtful", "out", "unknown"}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Tijdstip vereist")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Tijdstip vereist tijdzone")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("Ongeldig UTC tijdstip") from exc


def validate_evidence(item, *, now=None):
    if not isinstance(item, dict):
        raise ValueError("Context moet een object zijn")
    category = item.get("category")
    if category not in CATEGORIES:
        raise ValueError("Onbekende of niet-toegestane broncategorie")
    url = item.get("source_url")
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        raise ValueError("Ongeldige bronverwijzing") from None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Bron moet een publieke HTTPS URL zijn")
    if len(url) > 512:
        raise ValueError("URL te lang")
    provider = item.get("publisher")
    if not isinstance(provider, str) or not (2 <= len(provider) <= 100):
        raise ValueError("Publisher ontbreekt")
    if item.get("verification") not in ("official", "licensed_statistics"):
        raise ValueError("Geen verifieerbare broncategorie")
    observed = _timestamp(item.get("observed_at"))
    now = now or datetime.now(timezone.utc)
    if observed > now:
        raise ValueError("Feit kan niet in de toekomst zijn vastgesteld")
    match_date = item.get("match_date")
    try:
        match_day = date.fromisoformat(match_date)
    except (TypeError, ValueError):
        raise ValueError("Veld match_date verplicht") from None
    if match_day.year < 2016:
        raise ValueError("Wedstrijddatum buiten bereik")
    team = item.get("team")
    if not isinstance(team, str) or not (1 <= len(team) <= 120):
        raise ValueError("Clubnaam ontbreekt")
    # Source attribute must be clear; do not propagate medical details,
    # accusations of bribery, private diets or speculative wellbeing.
    forbidden = {"diagnosis", "medical_record", "medical_details", "diet",
                 "bribery", "matchfixing", "rumor", "private_health",
                 "family", "criminal_allegation", "financial_details"}
    if forbidden.intersection(item):
        raise ValueError("Gevoelige of onbevestigde kenmerken niet toegestaan")
    player = item.get("player")
    if player is not None and (not isinstance(player, str) or len(player) > 120):
        raise ValueError("Ongeldige spelernaam")
    value = item.get("status")
    if category == "squad_availability" and value not in STATUS:
        raise ValueError("Alleen publiek bekende beschikbaarheidsstatus")
    if category == "squad_availability" and not player:
        raise ValueError("Speler bij beschikbaarheidsstatus verplicht")
    metrics = item.get("metrics", {})
    if not isinstance(metrics, dict) or (set(metrics) - METRIC_FIELDS):
        raise ValueError("Onbekende statistiek")
    for number in metrics.values():
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError("Statistiek moet eindig numeriek zijn")
    if category in ("player_attack", "player_defense") and not player:
        raise ValueError("Speler bij spelerstatistieken verplicht")
    if category in ("player_attack", "player_defense") and observed.date() < match_day:
        raise ValueError("Post-matchstatistieken mogen niet vooraf bekend zijn")
    if category == "public_transfer" and item.get("verification") != "official":
        raise ValueError("Transfer moet officieel bevestigd zijn")
    # Preserve only the allowlisted fields, not arbitrary private source payload.
    cleaned = {
        "category": category, "source_url": url,
        "publisher": provider, "verification": item["verification"],
        "observed_at": observed.isoformat(),
        "match_date": match_date, "team": team,
        "player": player, "status": value if category == "squad_availability" else None,
        "metrics": metrics,
        # No free-text notes: prevents accidental medical details or rumors.
    }
    fingerprint = hashlib.sha256(json.dumps(
        cleaned, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return {"evidence_id": fingerprint, **cleaned}


def known_before_match(evidence, match_date):
    """Without kickoff time, require the source to predate the match *day*."""
    try:
        day = date.fromisoformat(match_date)
        observed = _timestamp(evidence["observed_at"])
    except (TypeError, ValueError, KeyError):
        return False
    return observed.date() < day


def import_evidence(items, path=EVIDENCE_PATH):
    path = Path(path)
    if not isinstance(items, list) or len(items) > 3000:
        raise ValueError("Verwacht beperkte lijst van bronbewijzen")
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema_version": 1, "evidence": []
    }
    indexed = {row["evidence_id"]: row for row in existing["evidence"]}
    added = 0
    for raw in items:
        record = validate_evidence(raw)
        if record["evidence_id"] not in indexed:
            indexed[record["evidence_id"]] = record
            added += 1
    atomic_json(path, {"schema_version": 1, "evidence": list(indexed.values())})
    return {"added": added, "total": len(indexed)}


def coverage_report(path=EVIDENCE_PATH):
    path = Path(path)
    rows = json.loads(path.read_text(encoding="utf-8"))["evidence"] if path.exists() else []
    categories = {
        key: {"records": sum(row["category"] == key for row in rows),
              "training_enabled": False}
        for key in sorted(CATEGORIES)
    }
    return {
        "records": len(rows), "categories": categories,
        "no_fake_facts": True, "no_unverified_allegations": True,
        "readiness": "Evidence can be collected; no causal validation yet.",
        "warning": "Only pre-match known features may enter future prediction training.",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-json", type=Path,
                        help="Import allowlisted attributed public context records")
    args = parser.parse_args()
    if args.import_json:
        items = json.loads(args.import_json.read_text(encoding="utf-8"))
        print(json.dumps(import_evidence(items), indent=2))
    print(json.dumps(coverage_report(), indent=2))


if __name__ == "__main__":
    main()
