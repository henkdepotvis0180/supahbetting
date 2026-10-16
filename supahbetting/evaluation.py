"""Prospective model quality metrics on manually settled matches.

These metrics are descriptive; without independent out-of-sample data, they are
NOT evidence of a profitable forecasting strategy.
"""
from __future__ import annotations

from math import log

from .domain import MARKETS, match_analysis


def score_settled_matches(matches):
    """Multiclass Brier and log loss, comparing xG baseline with no-vig market odds."""
    model_brier = market_brier = model_loss = market_loss = 0.0
    n = 0
    for match in matches:
        if match.get("result_home") is None or match.get("result_away") is None:
            continue
        outcome = (
            "home" if match["result_home"] > match["result_away"]
            else "away" if match["result_home"] < match["result_away"] else "draw"
        )
        analysis = match_analysis(match)
        p_model = {k: analysis["markets"][k]["probability"] for k in MARKETS}
        p_market = {k: analysis["markets"][k]["no_vig_probability"] for k in MARKETS}
        actual = {k: 1.0 if k == outcome else 0.0 for k in MARKETS}
        model_brier += sum((p_model[k] - actual[k]) ** 2 for k in MARKETS)
        market_brier += sum((p_market[k] - actual[k]) ** 2 for k in MARKETS)
        model_loss -= log(max(1e-12, p_model[outcome]))
        market_loss -= log(max(1e-12, p_market[outcome]))
        n += 1
    return {
        "evaluated_matches": n,
        "model_brier": model_brier / n if n else None,
        "market_brier": market_brier / n if n else None,
        "model_log_loss": model_loss / n if n else None,
        "market_log_loss": market_loss / n if n else None,
        "lower_is_better": True,
        "is_sufficient_sample": n >= 100,
        "warning": (
            "Minder dan 100 afgehandelde wedstrijden. Trek geen conclusies."
            if n < 100 else
            "Beschrijvende cijfers uit handmatige data; geen onafhankelijke backtest."
        ),
    }
