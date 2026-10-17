"""Leakage-safe experimental calibration utilities for score-model evaluation.

No future outcomes are used to fit a calibrator. This module does not replace
production parameters or claim betting profitability.
"""
from __future__ import annotations
import math


def temperature_scale(probabilities, temperature):
    """Apply a positive temperature to a three-way probability forecast."""
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be positive and finite")
    keys = ("home", "draw", "away")
    values = [float(probabilities[k]) for k in keys]
    if any(not math.isfinite(v) or v < 0 for v in values) or sum(values) <= 0:
        raise ValueError("invalid probabilities")
    logits = [math.log(max(v, 1e-12)) / temperature for v in values]
    maximum = max(logits)
    weights = [math.exp(v - maximum) for v in logits]
    total = sum(weights)
    return dict(zip(keys, (v / total for v in weights)))


def fit_temperature(validation_forecasts, candidates=(0.8, 0.9, 1.0, 1.1, 1.2)):
    """Fit only on explicit historical validation forecasts, never holdouts.

    Each record is (probabilities, actual_label). Callers must enforce a
    chronological split before passing data into this function.
    """
    records = list(validation_forecasts)
    if not records:
        raise ValueError("validation forecasts are required")
    if any(label not in ("home", "draw", "away") for _, label in records):
        raise ValueError("invalid outcome label")
    def loss(t):
        return sum(-math.log(max(temperature_scale(p, t)[label], 1e-12))
                   for p, label in records) / len(records)
    return min(candidates, key=lambda t: (loss(t), abs(t - 1.0)))
