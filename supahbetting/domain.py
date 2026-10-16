"""Validated betting research calculations.

Every figure is theoretical. A positive model edge is not evidence of real profitability.
Same-event combinations are rejected: multiplying dependent outcome probabilities is invalid.
"""
from __future__ import annotations

from math import exp, isfinite, prod
from datetime import datetime
import re

MARKETS = ("home", "draw", "away")
MARKET_LABELS = {"home": "Thuis", "draw": "Gelijk", "away": "Uit"}


class ValidationError(ValueError):
    """Invalid user or imported data."""


def finite_number(value, label, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValidationError(f"{label}: geen geldig getal")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValidationError(f"{label}: geen geldig getal") from None
    if not isfinite(result) or (minimum is not None and result < minimum) or (
        maximum is not None and result > maximum
    ):
        raise ValidationError(f"{label}: buiten toegestaan bereik")
    return result


def clean_text(value, label, limit=100):
    if not isinstance(value, str):
        raise ValidationError(f"{label}: tekst vereist")
    text = " ".join(value.strip().split())
    if not text or len(text) > limit or any(ord(c) < 32 for c in text):
        raise ValidationError(f"{label}: verplicht, maximaal {limit} tekens")
    return text


def parse_kickoff(value):
    """Require timezone-aware ISO 8601; blank kickoff is allowed."""
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or len(value) > 40:
        raise ValidationError("Ongeldige aftraptijd")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError("Ongeldige aftraptijd") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValidationError("Aftraptijd moet een tijdzone bevatten")
    return dt.isoformat()


def validate_match(raw):
    if not isinstance(raw, dict):
        raise ValidationError("Wedstrijd moet een object zijn")
    home = clean_text(raw.get("home_team"), "Thuisteam", 70)
    away = clean_text(raw.get("away_team"), "Uitteam", 70)
    if home.casefold() == away.casefold():
        raise ValidationError("Thuis- en uitteam moeten verschillend zijn")
    data = {
        "home_team": home,
        "away_team": away,
        "kickoff": parse_kickoff(raw.get("kickoff")),
        "home_xg": finite_number(raw.get("home_xg"), "xG thuis", 0, 8),
        "away_xg": finite_number(raw.get("away_xg"), "xG uit", 0, 8),
        "odds_home": finite_number(raw.get("odds_home"), "Odds thuis", 1.01, 100),
        "odds_draw": finite_number(raw.get("odds_draw"), "Odds gelijk", 1.01, 100),
        "odds_away": finite_number(raw.get("odds_away"), "Odds uit", 1.01, 100),
        "source": clean_text(raw.get("source", "Handmatig"), "Bron", 80),
    }
    return data


def poisson_distribution(expected, cap=35):
    """Calculate the probability mass via a stable recurrence, including near-all tail."""
    expected = finite_number(expected, "xG", 0, 8)
    probs = [exp(-expected)]
    for goals in range(1, cap + 1):
        probs.append(probs[-1] * expected / goals)
    total = sum(probs)
    return [p / total for p in probs]


def model_probabilities(home_xg, away_xg):
    home = poisson_distribution(home_xg)
    away = poisson_distribution(away_xg)
    p_home = p_draw = p_away = p_over = p_btts = 0.0
    for h, ph in enumerate(home):
        for a, pa in enumerate(away):
            p = ph * pa
            if h > a:
                p_home += p
            elif h == a:
                p_draw += p
            else:
                p_away += p
            if h + a >= 3:
                p_over += p
            if h >= 1 and a >= 1:
                p_btts += p
    outcomes = {"home": p_home, "draw": p_draw, "away": p_away}
    total = sum(outcomes.values())
    return {
        "home": p_home / total,
        "draw": p_draw / total,
        "away": p_away / total,
        "over_2_5": p_over,
        "btts": p_btts,
    }


def match_analysis(record):
    p = model_probabilities(record["home_xg"], record["away_xg"])
    odds = {key: record["odds_" + key] for key in MARKETS}
    raw_implied = {key: 1.0 / val for key, val in odds.items()}
    total_implied = sum(raw_implied.values())
    return {
        "probabilities": p,
        "market_margin": total_implied - 1.0,
        "markets": {
            key: {
                "label": MARKET_LABELS[key],
                "probability": p[key],
                "decimal_odds": odds[key],
                "fair_odds": 1.0 / p[key] if p[key] else None,
                "no_vig_probability": raw_implied[key] / total_implied,
                "expected_roi": p[key] * odds[key] - 1.0,
            }
            for key in MARKETS
        },
        "model": "Poisson-baseline (niet gekalibreerd)",
    }


def quote_slip(legs, stake):
    stake = finite_number(stake, "Inzet", 0.01, 10_000)
    if not isinstance(legs, list) or not 1 <= len(legs) <= 8:
        raise ValidationError("Een betslip vereist 1 tot 8 selecties")
    seen = set()
    probabilities = []
    odds = []
    for leg in legs:
        if not isinstance(leg, dict):
            raise ValidationError("Ongeldige selectie")
        identifier = leg.get("match_id")
        if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier < 1:
            raise ValidationError("Ongeldige wedstrijd-ID")
        if identifier in seen:
            raise ValidationError(
                "Selecties uit dezelfde wedstrijd mogen niet in één combinatie: kansen zijn afhankelijk"
            )
        seen.add(identifier)
        if leg.get("market") not in MARKETS:
            raise ValidationError("Onbekende markt")
        probabilities.append(finite_number(leg.get("probability"), "Kans", 0, 1))
        odds.append(finite_number(leg.get("decimal_odds"), "Odds", 1.01, 100))
    combined_odds = prod(odds)
    combined_probability = prod(probabilities)
    gross_payout = stake * combined_odds
    expected_roi = combined_probability * combined_odds - 1.0
    return {
        "stake": stake,
        "leg_count": len(legs),
        "combined_odds": combined_odds,
        "combined_probability": combined_probability,
        "gross_payout": gross_payout,
        "potential_profit": gross_payout - stake,
        "expected_roi": expected_roi,
        "expected_profit": stake * expected_roi,
        "calculation": "Onafhankelijkheid verondersteld bij verschillende wedstrijden",
    }
