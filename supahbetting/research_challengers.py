"""Independent Dixon-Coles challenger, not a silently fused production model.

Compares two *fixed* mathematical forecasting rules on the SAME sequential,
chronologically honest matches. Selection or model fusion is not authorized
by retrospective metrics; genuine future pre-kickoff grading must follow.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .research_data import LOCAL, atomic_json
from .research_model import _data_matches
from .trained_model import (
    LEAGUES, LeagueRatings, season_groups,
    outcome_probabilities, score, VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON,
)

CHALLENGER_FILE=LOCAL / "model_challengers.json"
RHO=-0.13


def dixon_coles_probs(home_expected, away_expected, rho=RHO):
    """Low-score correlation correction for independent Poisson 1X2."""
    if not (math.isfinite(home_expected) and math.isfinite(away_expected)
            and 0.1 <= home_expected <= 4.5 and 0.1 <= away_expected <= 4.5):
        raise ValueError("Invalid expected-goal inputs")
    if not -0.14 <= rho <= 0.12:
        raise ValueError("Rho outside bounded calibration range")
    original=outcome_probabilities(home_expected,away_expected)
    base=math.exp(-(home_expected+away_expected))*home_expected*away_expected
    correction = -rho*base
    candidate = {
        "home": original["home"]-correction,
        "draw": original["draw"]+2*correction,
        "away": original["away"]-correction,
    }
    if min(candidate.values()) <= 0:
        raise ValueError("Dixon-Coles correction leaves non-positive probability")
    total=sum(candidate.values())
    return {k:val/total for k,val in candidate.items()}


def compare_models(matches, *, alpha=.04, prior=3, rho=RHO):
    """Historical walk-forward diagnostic, not fresh independent live testing."""
    states={league:LeagueRatings(alpha,prior) for league in LEAGUES}
    counts=defaultdict(lambda:{"n":0, "base_brier":0.0,"dc_brier":0.0,
                               "base_logloss":0.0,"dc_logloss":0.0})
    for group in season_groups(_data_matches({"matches":matches})):
        league=group[0]["league"]
        state=states[league]
        state.season_boundary(group[0]["season"])
        for match in group:
            season=match["season"]
            if season not in (VALIDATION_SEASON,TEST_SEASON,CURRENT_SEASON):
                continue
            x,y=state.predict_goals(match["home"],match["away"])
            basic=outcome_probabilities(x,y)
            candidate=dixon_coles_probs(x,y,rho)
            b,bl=score(basic,match)
            d,dl=score(candidate,match)
            st=counts[season]
            st["n"]+=1
            st["base_brier"]+=b
            st["dc_brier"]+=d
            st["base_logloss"]+=bl
            st["dc_logloss"]+=dl
        for match in group:
            state.update(match)
    metrics={}
    for season in (VALIDATION_SEASON,TEST_SEASON,CURRENT_SEASON):
        item=counts[season]
        n=item["n"]
        metrics[season]={
            "matches":n,
            "poisson_logloss":round(item["base_logloss"]/n,6) if n else None,
            "dixon_coles_logloss":round(item["dc_logloss"]/n,6) if n else None,
            "poisson_brier":round(item["base_brier"]/n,6) if n else None,
            "dixon_coles_brier":round(item["dc_brier"]/n,6) if n else None,
        }
    return {
        "experiment":"dixon_coles_low_score_correlation_vs_independent_poisson",
        "alpha":alpha,"prior_matches":prior,"rho":rho,
        "evaluated_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "periods":metrics,
        "selection_policy":"NO_MODEL_FUSION_OR_PROMOTION",
        "external_candidate_reference":"https://github.com/Hicruben/theopenmodel",
        "license_note":"External repository MIT code / CC BY 4.0 forecast data; not imported as training truth.",
        "decision":(
            "Uitsluitend retrospectieve vergelijking. Ongezien toekomstige "
            "voorspellingen en verantwoord bron-/licentieonderzoek zijn nog nodig."
        ),
    }


def main():
    path=LOCAL / "inventory.json"
    if not path.exists():
        print("Geen complete lokale CC0-database. Start eerst de Research Monitor.")
        return 1
    inventory=json.loads(path.read_text(encoding="utf-8"))
    result=compare_models(inventory["matches"])
    atomic_json(CHALLENGER_FILE,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
