"""Train and evaluate a reproducible leakage-aware 1X2 baseline.

Run: python -m supahbetting.train_baseline --input historical.csv
Only this training module needs scikit-learn and numpy. The server uses safe
plain JSON coefficients via baseline_model.py, never joblib or pickle.

Research only; no outcome is guaranteed and no bet is executed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from .baseline_model import (
    CLASS_NAMES, FEATURES, MODEL_FILE, LEAGUE_ALIASES, empty_team,
    feature_vector, team_key, update_ratings,
)

MIN_MATCHES = 500
LABELS = ("H", "D", "A")
RESULT_INDEX = {name: index for index, name in enumerate(LABELS)}

DIVISION_NAMES = {
    "E0": "E0", "E1": "E1", "D1": "D1", "D2": "D2", "D3": "D3",
    "SP1": "SP1", "SP2": "SP2", "I1": "I1", "I2": "I2",
    "F1": "F1", "F2": "F2", "N1": "N1", "N2": "N2",
    "B1": "B1", "P1": "P1", "SC0": "SC0", "SC1": "SC1",
    "PL": "E0", "BUNDESLIGA": "D1", "LALIGA": "SP1",
    "SERIEA": "I1", "LIGUE1": "F1", "EREDIVISIE": "N1",
    "PREMIER LEAGUE": "E0", "LA LIGA": "SP1", "SERIE A": "I1",
    "LIGUE 1": "F1",
}


def _date(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _goals(value):
    try:
        float_goals = float(value)
        if math.isfinite(float_goals) and float_goals.is_integer() and 0 <= float_goals <= 18:
            return int(float_goals)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _choose(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def read_historical_csv(path):
    """Normalize historical game results from prediict/football-data.co.uk files.

    Never use odds, derived statistics, results or goals as prediction features.
    They are read exclusively to build *past* rolling state and train labels.
    """
    path = Path(path)
    if path.stat().st_size > 30_000_000:
        raise ValueError("Historisch CSV groter dan 30 MB; splits per seizoen")
    seen = set()
    data, invalid, conflicts = [], 0, 0
    limit_date = datetime.now(timezone.utc).date()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV heeft geen kolomnamen")
        for row in reader:
            day = _date(_choose(row, "date", "Date", "match_date"))
            home = _choose(row, "home_team", "HomeTeam", "Home", "home")
            away = _choose(row, "away_team", "AwayTeam", "Away", "away")
            hk, ak = team_key(home), team_key(away)
            hg = _goals(_choose(row, "home_score", "FTHG", "home_goals"))
            ag = _goals(_choose(row, "away_score", "FTAG", "away_goals"))
            league_raw = _choose(row, "league", "league_code", "Div", "division", "competition")
            league = DIVISION_NAMES.get(league_raw.upper(), league_raw.upper() or "GLOBAL")
            if not (day and hk and ak and hk != ak and hg is not None and ag is not None):
                invalid += 1
                continue
            if day > limit_date:
                invalid += 1
                continue
            identity = (league, day, hk, ak)
            if identity in seen:
                conflicts += 1
                continue
            seen.add(identity)
            data.append((day, league, hk, ak, hg, ag))
    data.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    if len(data) < MIN_MATCHES:
        raise ValueError(f"Te weinig volledige wedstrijden ({len(data)}; minimaal {MIN_MATCHES})")
    return data, {"invalid": invalid, "duplicates": conflicts}


def make_examples(matches):
    """Construct feature vectors before each date's matches update team state.

    Match events on the SAME date share a pre-match state. Labels, goals and
    all future data are never features. A later test match may legally use
    the results of a prior completed test date in a walk-forward evaluation.
    """
    teams = defaultdict(dict)
    xs, ys, ds = [], [], []
    group, current_day = [], None

    def flush(pending):
        for day, league, home, away, hg, ag in pending:
            league_state = teams[league]
            home_state = league_state.setdefault(home, empty_team())
            away_state = league_state.setdefault(away, empty_team())
            update_ratings(home_state, away_state, hg, ag)

    for match in matches:
        day, league, home, away, hg, ag = match
        if current_day != day:
            if group:
                flush(group)
                group = []
            current_day = day
        league_state = teams[league]
        h = league_state.get(home) or empty_team()
        a = league_state.get(away) or empty_team()
        xs.append(feature_vector(h, a))
        ys.append(0 if hg > ag else 1 if hg == ag else 2)
        ds.append(day)
        group.append(match)
    if group:
        flush(group)
    return xs, ys, ds, dict(teams)


def _split_dates(days):
    unique = sorted(set(days))
    if len(unique) < 25:
        raise ValueError("Training vereist ten minste 25 afzonderlijke speeldagen")
    n = len(unique)
    valid_start = unique[int(n * .68)]
    test_start = unique[int(n * .82)]
    train_ids = [i for i, d in enumerate(days) if d < valid_start]
    valid_ids = [i for i, d in enumerate(days) if valid_start <= d < test_start]
    test_ids = [i for i, d in enumerate(days) if d >= test_start]
    if min(map(len, (train_ids, valid_ids, test_ids))) < 50:
        raise ValueError("Onvoldoende wedstrijden per chronologische periode")
    return train_ids, valid_ids, test_ids


def _metrics(y_true, probabilities):
    from sklearn.metrics import accuracy_score, log_loss
    import numpy as np
    y = np.asarray(y_true)
    p = np.asarray(probabilities)
    one_hot = np.eye(3)[y]
    return {
        "games": len(y),
        "accuracy": round(float(accuracy_score(y, p.argmax(axis=1))), 5),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1, 2])), 5),
        "brier_multiclass": round(float(np.mean(np.sum((p - one_hot) ** 2, axis=1))), 5),
    }


def _temperature(probs, t):
    import numpy as np
    probs = np.asarray(probs).clip(1e-8, 1)
    power = probs ** (1 / t)
    return power / power.sum(axis=1, keepdims=True)


def train(input_path, output_path=MODEL_FILE):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    input_path, output_path = Path(input_path), Path(output_path)
    matches, skipped = read_historical_csv(input_path)
    x, y, dates, team_states = make_examples(matches)
    train_idx, val_idx, test_idx = _split_dates(dates)
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=int)

    def train_candidate(ids, c):
        scal = StandardScaler()
        scaled = scal.fit_transform(x[ids])
        clf = LogisticRegression(C=c, max_iter=700, random_state=42)
        clf.fit(scaled, y[ids])
        return scal, clf

    best = None
    for c in (0.05, 0.2, 1.0):
        scaler, clf = train_candidate(train_idx, c)
        valid = clf.predict_proba(scaler.transform(x[val_idx]))
        for temp in (0.80, 0.95, 1.0, 1.1, 1.25, 1.45):
            prediction = _temperature(valid, temp)
            score = _metrics(y[val_idx], prediction)["log_loss"]
            if best is None or score < best[0]:
                best = (score, c, temp)
    _, regularization, temp = best
    pretest = train_idx + val_idx
    eval_scaler, eval_model = train_candidate(pretest, regularization)
    eval_probs = _temperature(
        eval_model.predict_proba(eval_scaler.transform(x[test_idx])), temp
    )
    seen_prior = np.bincount(y[pretest], minlength=3).astype(float)
    seen_prior /= seen_prior.sum()
    constant_baseline = np.repeat(seen_prior[None, :], len(test_idx), axis=0)
    metric_holdout = _metrics(y[test_idx], eval_probs)
    metric_prior = _metrics(y[test_idx], constant_baseline)
    metric_holdout["period_from"] = dates[test_idx[0]].isoformat()
    metric_holdout["period_to"] = dates[test_idx[-1]].isoformat()
    metric_prior["period_from"] = metric_holdout["period_from"]
    metric_prior["period_to"] = metric_holdout["period_to"]

    # Refit on all available history after the test report is locked. This
    # creates a starting model up to the dataset's most recent match. Test
    # metrics refer only to the earlier pretest snapshot, NOT refit weights.
    final_scaler, final_model = train_candidate(list(range(len(y))), regularization)
    mapping = {int(label): index for index, label in enumerate(final_model.classes_)}
    if set(mapping) != {0, 1, 2}:
        raise ValueError("Dataset bevat niet alle 1X2-uitkomsten")
    weights = [final_model.coef_[mapping[i]].tolist() for i in range(3)]
    bias = [float(final_model.intercept_[mapping[i]]) for i in range(3)]
    compact_teams = {
        league: {
            team: {
                "elo": state["elo"], "games": state["games"],
                "recent": state["recent"],
            }
            for team, state in members.items()
        }
        for league, members in team_states.items()
    }
    raw = input_path.read_bytes()
    data_hash = hashlib.sha256(raw).hexdigest()
    artifact = {
        "schema": "supahbetting-baseline-v1",
        "version": "0.7.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Historical CSV from user's Prediict fork; original data not redistributed",
        "source_data_sha256": data_hash,
        "features": list(FEATURES), "classes": list(CLASS_NAMES),
        "scaler": {
            "mean": final_scaler.mean_.tolist(),
            "scale": final_scaler.scale_.tolist(),
        },
        "weights": {"coef": weights, "intercept": bias},
        "temperature": temp, "regularization_C": regularization,
        "training_matches": len(matches), "data_from": dates[0].isoformat(),
        "data_until": dates[-1].isoformat(),
        "skipped_rows": skipped,
        "teams": compact_teams,
        "metrics": {
            "method": "Chronological rolling features; train/validation/test by date",
            "train_games": len(train_idx), "validation_games": len(val_idx),
            "holdout": metric_holdout,
            "constant_class_prior": metric_prior,
            "better_than_constant_prior_log_loss":
                metric_holdout["log_loss"] < metric_prior["log_loss"],
            "test_snapshot_refit_after_evaluation": True,
            "caution": (
                "Results are out-of-sample for the pretest model. Published "
                "JSON weights are refit on all history and were NOT independently "
                "tested. No profit, calibration, or bookmaker-beating guarantee."
            ),
        }
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False)+"\n",
                   encoding="utf-8")
    tmp.replace(output_path)
    return {
        "data_until": artifact["data_until"],
        "matches": len(matches), "leagues": len(compact_teams),
        "teams": sum(len(v) for v in compact_teams.values()),
        "holdout": metric_holdout, "prior": metric_prior,
        "training_source_sha256": data_hash,
        "file_bytes": output_path.stat().st_size,
        "saved_to": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="SupahBetting: 1X2-basismodel trainen")
    parser.add_argument("--input", required=True, type=Path,
                        help="Historische CSV met datum/teams/einduitslag")
    parser.add_argument("--output", type=Path, default=MODEL_FILE,
                        help="JSON-modelbestand (niet pickle/joblib)")
    args = parser.parse_args()
    try:
        result = train(args.input, args.output)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Training mislukt: {exc}\n")


if __name__ == "__main__":
    main()
