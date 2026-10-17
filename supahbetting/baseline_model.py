"""Portable baseline 1X2 football model (pure standard library at runtime).

The model JSON contains trained multinomial logistic regression coefficients,
training-only scaler statistics, post-hoc temperature, and historical team
ratings. No pickle, joblib or remote model code is loaded by SupahBetting.

Probabilities are research estimates, NOT bookmaker odds, and cannot establish
a betting advantage without a separate, independent odds benchmark.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

MODEL_FILE = Path(__file__).resolve().parent.parent / "models" / "baseline_v1.json"
FEATURES = (
    "elo_difference",
    "recent_points_difference",
    "goals_scored_difference",
    "goals_allowed_difference",
    "home_points_recent",
    "away_points_recent",
    "home_experience",
    "away_experience",
)
CLASS_NAMES = ("home", "draw", "away")
MAX_MODEL_BYTES = 4_000_000
LEAGUE_ALIASES = {
    "bl1": "D1", "bl2": "D2", "bl3": "D3",
    "pl": "E0", "la1": "SP1", "ffb1": "D-F",
    "4337": "N1", "4641": "N2", "4338": "B1",
    "4328": "E0", "4329": "E1", "4331": "D1", "4332": "I1",
    "4334": "F1", "4335": "SP1", "4346": "USA",
    "DED": "N1", "PL": "E0", "PD": "SP1",
    "BL1": "D1", "SA": "I1", "FL1": "F1",
}


class BaselineError(ValueError):
    """Safe user-facing explanation without raw model or data contents."""


def team_key(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        return ""
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return " ".join(re.findall("[a-z0-9]+", normalized))


def empty_team():
    return {"elo": 1500.0, "games": 0, "recent": []}


def _avg(history, index, default):
    if not history:
        return default
    return sum(float(entry[index]) for entry in history) / len(history)


def feature_vector(home_state, away_state):
    home_recent = home_state.get("recent", [])
    away_recent = away_state.get("recent", [])
    hp = _avg(home_recent, 0, 1.3)
    ap = _avg(away_recent, 0, 1.3)
    hgf = _avg(home_recent, 1, 1.4)
    agf = _avg(away_recent, 1, 1.4)
    hga = _avg(home_recent, 2, 1.3)
    aga = _avg(away_recent, 2, 1.3)
    return [
        (float(home_state.get("elo", 1500)) - float(away_state.get("elo", 1500)) + 60) / 400,
        (hp - ap) / 3,
        (hgf - agf) / 3,
        (hga - aga) / 3,
        hp / 3,
        ap / 3,
        math.log1p(min(int(home_state.get("games", 0)), 500)) / 6,
        math.log1p(min(int(away_state.get("games", 0)), 500)) / 6,
    ]


def update_ratings(home_state, away_state, home_goals, away_goals):
    if home_goals > away_goals:
        outcome, hp, ap = 1.0, 3.0, 0.0
    elif home_goals < away_goals:
        outcome, hp, ap = 0.0, 0.0, 3.0
    else:
        outcome, hp, ap = 0.5, 1.0, 1.0
    diff = float(home_state["elo"]) - float(away_state["elo"]) + 60
    expected = 1 / (1 + 10 ** (-diff / 400))
    delta = 24 * (outcome - expected)
    home_state["elo"] = round(float(home_state["elo"]) + delta, 5)
    away_state["elo"] = round(float(away_state["elo"]) - delta, 5)
    for state, pts, scored, allowed in (
        (home_state, hp, home_goals, away_goals),
        (away_state, ap, away_goals, home_goals),
    ):
        state["games"] = int(state.get("games", 0)) + 1
        recent = state.setdefault("recent", [])
        recent.append([pts, scored, allowed])
        del recent[:-7]


def softmax(logits):
    largest = max(logits)
    exps = [math.exp(min(100, value - largest)) for value in logits]
    den = sum(exps)
    return [value / den for value in exps]


def _validated_model(payload):
    if not isinstance(payload, dict) or payload.get("schema") != "supahbetting-baseline-v1":
        raise BaselineError("Onbekend modelbestand of schemaversie")
    if tuple(payload.get("features", [])) != FEATURES:
        raise BaselineError("Modelkenmerken komen niet overeen")
    if payload.get("classes") != list(CLASS_NAMES):
        raise BaselineError("Modelklassen komen niet overeen")
    if not isinstance(payload.get("teams"), dict):
        raise BaselineError("Model mist de historische teamsterkte")
    transform = payload.get("scaler", {})
    learned = payload.get("weights", {})
    if not isinstance(transform, dict) or not isinstance(learned, dict):
        raise BaselineError("Modelparameters zijn ongeldig")
    if len(transform.get("mean", [])) != len(FEATURES) or len(transform.get("scale", [])) != len(FEATURES):
        raise BaselineError("Modelnormalisatie is ongeldig")
    if len(learned.get("coef", [])) != 3 or len(learned.get("intercept", [])) != 3:
        raise BaselineError("Modelparameters hebben onjuiste dimensies")
    for row in learned["coef"]:
        if not isinstance(row, list) or len(row) != len(FEATURES):
            raise BaselineError("Modelparameters hebben onjuiste dimensies")
    nums = (transform["mean"] + transform["scale"] +
            learned["intercept"] + [x for row in learned["coef"] for x in row] +
            [payload.get("temperature")])
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) for x in nums):
        raise BaselineError("Modelparameters bevatten ongeldige getallen")
    if min(transform["scale"]) <= 0 or not (0.3 <= payload["temperature"] <= 3):
        raise BaselineError("Modelschaling is ongeldig")
    return payload


def load_baseline(path=MODEL_FILE):
    path = Path(path)
    if not path.is_file():
        raise BaselineError("Geen voorgetraind model aanwezig; gebruik de GitHub-baseline")
    if path.stat().st_size > MAX_MODEL_BYTES:
        raise BaselineError("Modelbestand is te groot")
    try:
        with path.open("r", encoding="utf-8") as handle:
            model = json.load(handle)
    except (OSError, ValueError, UnicodeError):
        raise BaselineError("Kon getraind model niet lezen") from None
    return _validated_model(model)


def _find_teams(model, home, away, league):
    teams = model["teams"]
    hk, ak = team_key(home), team_key(away)
    if not hk or not ak or hk == ak:
        raise BaselineError("Geef twee verschillende, geldige teamnamen op")
    code = LEAGUE_ALIASES.get(str(league), str(league or "")).upper()
    if code and code in teams:
        current = teams[code]
        return code, current.get(hk), current.get(ak)
    # Only infer league when *both* team names uniquely match an existing league.
    matched = [code for code, entrants in teams.items() if hk in entrants and ak in entrants]
    if len(matched) == 1:
        name = matched[0]
        return name, teams[name][hk], teams[name][ak]
    return code or "ONBEKEND", None, None


def predict(model, home_team, away_team, league=""):
    """Score a fixture from *trained historic* results, without making up odds."""
    code, home, away = _find_teams(model, home_team, away_team, league)
    known = [home is not None, away is not None]
    feat = feature_vector(home or empty_team(), away or empty_team())
    scal = model["scaler"]
    z = [(x - m) / s for x, m, s in zip(feat, scal["mean"], scal["scale"])]
    parameters = model["weights"]
    temp = model["temperature"]
    logits = [(b + sum(x * v for x, v in zip(row, z))) / temp
              for row, b in zip(parameters["coef"], parameters["intercept"])]
    probs = softmax(logits)
    last = model.get("data_until", "")
    age_days = None
    try:
        age_days = (datetime.now(timezone.utc).date() - date.fromisoformat(last)).days
    except (TypeError, ValueError):
        pass
    notes = [
        "Op historische uitslagen getraind; geen live-opstellingen, transfers, blessures of bookmakerodds."
    ]
    if not all(known):
        notes.append("Een of beide teams ontbreken in deze competitiehistorie: beperkte betrouwbaarheid.")
    if age_days is not None and age_days > 90:
        notes.append("Historische training is meer dan 90 dagen oud: model opnieuw trainen.")
    return {
        "home_team": home_team, "away_team": away_team, "league": code,
        "probabilities": dict(zip(CLASS_NAMES, [round(p, 6) for p in probs])),
        "teams_in_history": dict(zip(("home", "away"), known)),
        "model_trained_until": last, "data_age_days": age_days,
        "last_test_metrics": model.get("metrics", {}).get("holdout"),
        "model_name": "Historisch Elo + vorm / multinomiale logistische regressie",
        "model_type": "trained_statistical_baseline",
        "model_validated_profit": False,
        "warning": " ".join(notes),
    }


def public_status(model):
    return {
        "available": True, "name": "Elo + recente vorm (1X2)",
        "trained_until": model.get("data_until"),
        "training_matches": model.get("training_matches"),
        "teams": sum(len(t) for t in model.get("teams", {}).values()),
        "leagues": sorted(model.get("teams", {}).keys()),
        "model_type": "trained_statistical_baseline",
        "source": model.get("source"),
        "metrics": model.get("metrics"),
        "independent_betting_advantage": False,
        "warning": (
            "Dit model is getraind op historische wedstrijden en chronologisch getest. "
            "Het is niet bewezen winstgevend en levert geen live bookmakerquoteringen."
        ),
    }
