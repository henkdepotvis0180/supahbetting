"""Deterministic, dependency-free odds and prediction research utilities."""
from dataclasses import dataclass
from math import exp, factorial
from typing import Optional


def poisson(k: int, expected: float) -> float:
    if k < 0 or expected < 0:
        raise ValueError("Goals and expected goals must be nonnegative")
    return exp(-expected) * expected ** k / factorial(k)


def match_probabilities(home_xg: float, away_xg: float, max_goals: int = 12) -> dict:
    """Independent Poisson baseline; tail mass is normalized, not silently lost."""
    if min(home_xg, away_xg) < 0 or max_goals < 1:
        raise ValueError("Invalid xG or max_goals")
    home = [poisson(i, home_xg) for i in range(max_goals + 1)]
    away = [poisson(i, away_xg) for i in range(max_goals + 1)]
    result = {"home": 0.0, "draw": 0.0, "away": 0.0, "over_2_5": 0.0}
    total = 0.0
    for h, ph in enumerate(home):
        for a, pa in enumerate(away):
            p = ph * pa
            total += p
            result["home" if h > a else "away" if h < a else "draw"] += p
            if h + a > 2:
                result["over_2_5"] += p
    return {key: value / total for key, value in result.items()}


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must exceed 1")
    return 1 / decimal_odds


def expected_value(probability: float, decimal_odds: float) -> float:
    if not 0 <= probability <= 1:
        raise ValueError("Probability must be in [0,1]")
    return probability * decimal_odds - 1 if decimal_odds > 1 else _invalid_odds()


def _invalid_odds():
    raise ValueError("Decimal odds must exceed 1")


def no_vig_probabilities(odds: dict) -> dict:
    raw = {name: implied_probability(value) for name, value in odds.items()}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


@dataclass(frozen=True)
class Pick:
    event: str
    market: str
    probability: float
    decimal_odds: float

    @property
    def edge(self) -> float:
        return expected_value(self.probability, self.decimal_odds)

    @property
    def fair_odds(self) -> float:
        if self.probability <= 0:
            return float("inf")
        return 1 / self.probability
