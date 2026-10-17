"""Explicit recency, completeness and initial-backfill auditing.

Successful downloads are NOT proof that results are up to date.  Always display
the latest actual score date separately from the source fetch timestamp.
"""
from __future__ import annotations

from datetime import date
from .trained_model import LEAGUES


def _days_ago(value, today):
    try:
        if not value:
            return None
        difference = (today - date.fromisoformat(value)).days
        return max(0, difference)
    except (ValueError, TypeError):
        return None


def audit_quality(inventory, *, today=None):
    """Pure snapshot summary; no provider calls, no undocumented assumptions."""
    today = today or date.today()
    matches = inventory.get("matches", [])
    if not isinstance(matches, list):
        raise ValueError("Ongeldige wedstrijddataset")
    missing = [x["key"] for x in inventory.get("coverage", [])
               if x.get("state") == "not_published" and isinstance(x.get("key"), str)]
    fetched = inventory.get("fetched_at_utc")
    overall_age = _days_ago(inventory.get("latest_result_date"), today)
    by_league = {}
    alerts = []
    for league, name in LEAGUES.items():
        most_recent = max(
            (m.get("date", "") for m in matches
             if m.get("league") == league and isinstance(m.get("date"), str)),
            default=None,
        )
        age = _days_ago(most_recent, today)
        issues = [key for key in missing if key.endswith("/" + league)]
        if age is None:
            state = "no_results"
        elif age >= 90:
            state = "severely_stale"
        elif age >= 14:
            state = "stale"
        else:
            state = "recent"
        if state in ("no_results", "severely_stale", "stale"):
            alerts.append({
                "kind": "stale_league",
                "league": league, "name": name, "days": age, "state": state,
            })
        by_league[league] = {
            "name": name, "latest_result_date": most_recent,
            "days_since_last_result": age, "freshness": state,
            "missing_source_files": issues,
        }
    if overall_age is not None and overall_age >= 14:
        alerts.insert(0, {
            "kind": "stale_global_results",
            "days": overall_age, "state": "stale",
            "latest_result_date": inventory.get("latest_result_date"),
        })
    if missing:
        alerts.append({"kind": "source_gaps", "count": len(missing)})
    if inventory.get("failed_sources"):
        alerts.append({"kind": "fetch_failures",
                       "count": len(inventory["failed_sources"])})
    return {
        "checked_at_utc": fetched,
        "latest_result_date": inventory.get("latest_result_date"),
        "days_since_latest_result": overall_age,
        "is_stale": overall_age is None or overall_age >= 14,
        "new_results_since_previous_scan": len(inventory.get("new_final_match_ids", [])),
        "first_import_at_utc": inventory.get("first_import_at_utc"),
        "initial_backfill_matches": inventory.get("initial_backfill_matches"),
        "is_initial_import": bool(inventory.get("is_initial_import")),
        "missing_source_file_count": len(missing),
        "missing_source_keys": missing,
        "leagues": by_league, "alerts": alerts,
        "warning": (
            "Een recente broncontrole betekent niet dat de wedstrijduitslagen "
            "recent zijn. De nieuwste eindstand is het echte ijkpunt."
        ),
    }
