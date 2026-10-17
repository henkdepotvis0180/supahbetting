"""Leakage-safe team form / fixture congestion signals from verified scores.

No invented xG, player injury or turf quality. These are *descriptive*
explanatory variables, not automatically enabled predictive features.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import groupby


def _team_form(history, fixture_date):
    game_day = date.fromisoformat(fixture_date)
    recent = history[-5:]
    if history:
        latest_date = date.fromisoformat(history[-1]["date"])
        rest = (game_day - latest_date).days
        if rest <= 0:
            raise ValueError("Temporal leakage: team result on/after fixture date")
    else:
        rest = None
    last14 = sum(
        0 < (game_day - date.fromisoformat(row["date"])).days <= 14
        for row in history
    )
    n = len(recent)
    return {
        "previous_sample": n,
        "rest_days": rest,
        "matches_previous_14_days": last14,
        "goals_for_last_5_mean": round(sum(x["gf"] for x in recent) / n, 4) if n else None,
        "goals_against_last_5_mean": round(sum(x["ga"] for x in recent) / n, 4) if n else None,
        "win_rate_last_5": round(sum(x["gf"] > x["ga"] for x in recent) / n, 4) if n else None,
        "clean_sheet_rate_last_5": round(sum(x["ga"] == 0 for x in recent) / n, 4) if n else None,
        "source": "derived_from_verified_final_scores",
        "xg_available": False,
    }


def fixture_signals(matches, fixtures):
    """Compute pre-date statistics; same-day results cannot influence features."""
    completed = sorted(matches, key=lambda m: (m["date"], m["league"], m["home"]))
    upcoming = sorted(fixtures, key=lambda m: (m["date"], m["league"], m["home"]))
    history = defaultdict(list)
    index = 0
    results = []
    for day, group in groupby(upcoming, lambda m: m["date"]):
        # Move only strictly *earlier date* completed matches into state.
        while index < len(completed) and completed[index]["date"] < day:
            m = completed[index]
            history[(m["league"], m["home"])].append({
                "date": m["date"], "gf": m["hg"], "ga": m["ag"]
            })
            history[(m["league"], m["away"])].append({
                "date": m["date"], "gf": m["ag"], "ga": m["hg"]
            })
            index += 1
        for fixture in group:
            results.append({
                "fixture_id": fixture["id"],
                "league": fixture["league"],
                "date": day,
                "home": fixture["home"], "away": fixture["away"],
                "home_form": _team_form(
                    history[(fixture["league"], fixture["home"])], day
                ),
                "away_form": _team_form(
                    history[(fixture["league"], fixture["away"])], day
                ),
                "training_enabled": False,
                "note": "Alleen historische scores vóór deze speeldag; nog geen gevalideerd extra model.",
            })
    return results


if __name__ == "__main__":
    import json
    from .research_data import LOCAL
    inventory=json.loads((LOCAL/"inventory.json").read_text(encoding="utf-8"))
    print(json.dumps(fixture_signals(inventory["matches"],inventory["fixtures"])[:10],
                     ensure_ascii=False,indent=2))
