"""Reproducible, dependency-free historical-goals football baseline.

Training data: real completed league results from openfootball/football.json
(CC0 1.0 Universal). No bets, odds, shot xG, betting labels or random samples.

Algorithm: online exponential-smoothing estimates of team attack/defence, a
league-specific empirically estimated home advantage, Bayesian shrinkage and an
independent Poisson goal process. Hyperparameters selected ONLY on 2024-25.
2025-26 and 2026-27 are chronologically scored before updating ratings;
2026-27 is never used for hyperparameter selection. Matches on the same date are predicted BEFORE
any scores from that date update the model (reduces intraday leakage).

This is an experimental score-based model, NOT trained shot-level xG, and it
has not been proven profitable compared with bookmaker prices.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path("data/historical")
MODEL_FILE = Path(__file__).parent / "models" / "baseline.json"
TRAINING_VERSION = "0.10.0"
EARLY_SEASONS = ("2017-18", "2018-19", "2019-20")
CURRENT_SEASON = "2026-27"
VALIDATION_SEASON = "2024-25"
TEST_SEASON = "2025-26"
LEAGUES = {
    "nl.1": "Eredivisie",
    "be.1": "Belgische Pro League",
    "en.1": "Premier League",
    "de.1": "Bundesliga",
    "es.1": "La Liga",
    "it.1": "Serie A",
    "fr.1": "Ligue 1",
}

# Public league shortcuts to the exact football.json competition IDs.
PROVIDER_LEAGUES = {
    "sportsdb": {
        "4337": "nl.1", "4338": "be.1", "4328": "en.1",
        "4331": "de.1", "4335": "es.1", "4332": "it.1", "4334": "fr.1",
    },
    "football-data": {
        "DED": "nl.1", "PL": "en.1", "BL1": "de.1",
        "PD": "es.1", "SA": "it.1", "FL1": "fr.1",
    },
    "openliga": {"bl1": "de.1", "la1": "es.1", "pl": "en.1"},
}
# Explicit, reviewed aliases. No automatic fuzzy team matching.
TEAM_ALIASES = {
    "nl.1": {
        "ajax": "AFC Ajax", "ajax amsterdam": "AFC Ajax",
        "feyenoord": "Feyenoord Rotterdam", "psv eindhoven": "PSV",
        "nec nijmegen": "NEC", "sc heerenveen": "SC Heerenveen",
        "excelsior": "SBV Excelsior",
    },
    "en.1": {
        "manchester city": "Manchester City FC",
        "manchester united": "Manchester United FC",
        "liverpool": "Liverpool FC", "arsenal": "Arsenal FC",
        "tottenham hotspur": "Tottenham Hotspur FC",
        "chelsea": "Chelsea FC", "newcastle united": "Newcastle United FC",
        "brighton": "Brighton & Hove Albion FC",
    },
    "de.1": {
        "bayern munich": "FC Bayern München",
        "bayern munchen": "FC Bayern München",
        "borussia dortmund": "Borussia Dortmund",
        "bayer leverkusen": "Bayer 04 Leverkusen",
        "rb leipzig": "RB Leipzig",
    },
    "es.1": {"real madrid": "Real Madrid CF",
             "barcelona": "FC Barcelona",
             "atletico madrid": "Club Atlético de Madrid"},
    "it.1": {"inter milan": "FC Internazionale Milano",
             "inter": "FC Internazionale Milano",
             "juventus": "Juventus FC",
             "ac milan": "AC Milan"},
    "fr.1": {"paris saint germain": "Paris Saint-Germain FC",
             "psg": "Paris Saint-Germain FC",
             "marseille": "Olympique de Marseille"},
}


class TrainingError(ValueError):
    pass


def norm(value):
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value.strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def load_matches(folder=DATA_DIR):
    """Only strict dated final scores, deduplicated. Never use scheduled games."""
    rows = []
    folder = Path(folder)
    for league in LEAGUES:
        path = folder / (league + ".csv")
        if not path.is_file():
            raise TrainingError("Historische competitie ontbreekt: " + league)
        with path.open("r", newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not all(field in (reader.fieldnames or ()) for field in
                       ("league", "season", "date", "home", "away",
                        "home_goals", "away_goals")):
                raise TrainingError("Historische dataset heeft verkeerde kolommen")
            for row in reader:
                if row["league"] != league:
                    raise TrainingError("Competitiecode wijkt af")
                try:
                    day = date.fromisoformat(row["date"])
                    goals_h, goals_a = int(row["home_goals"]), int(row["away_goals"])
                except (ValueError, TypeError):
                    raise TrainingError("Ongeldige eindstand of wedstrijddatum") from None
                if (goals_h < 0 or goals_a < 0 or goals_h > 20 or goals_a > 20
                        or not row["home"] or not row["away"]
                        or row["home"] == row["away"]):
                    raise TrainingError("Onrealistische wedstrijduitslag")
                season = row["season"]
                match = re.fullmatch(r"(20[0-3][0-9])-([0-9]{2})", season)
                if (not match or int(match.group(1)) < 2017 or
                        int(match.group(2)) != (int(match.group(1)) + 1) % 100 or
                        day.year not in (int(match.group(1)),
                                         int(match.group(1)) + 1)):
                    raise TrainingError("Onverwacht historisch seizoen of datum")
                rows.append({
                    "league": league, "season": row["season"],
                    "date": day.isoformat(), "home": row["home"],
                    "away": row["away"], "hg": goals_h, "ag": goals_a,
                })
    unique = {}
    for match in rows:
        key = (match["league"], match["date"], match["home"], match["away"])
        if key in unique:
            if unique[key] != match:
                raise TrainingError("Tegenstrijdige uitslagen voor één wedstrijd")
            continue
        unique[key] = match
    return sorted(unique.values(), key=lambda r: (r["date"], r["league"],
                                                   r["home"], r["away"]))


def poisson(goals, limit=19):
    if not math.isfinite(goals) or goals < 0:
        raise TrainingError("Ongeldige doelpuntverwachting")
    values = [math.exp(-goals)]
    for i in range(1, limit + 1):
        values.append(values[-1] * goals / i)
    total = sum(values)
    return [v / total for v in values]


def outcome_probabilities(home_goals, away_goals):
    h = poisson(home_goals)
    a = poisson(away_goals)
    less_away = 0.0
    home_win = tie = 0.0
    for i, ph in enumerate(h):
        home_win += ph * less_away
        tie += ph * a[i]
        less_away += a[i]
    away_win = max(0.0, 1 - home_win - tie)
    total = home_win + tie + away_win
    return {"home": home_win / total,
            "draw": tie / total, "away": away_win / total}


class LeagueRatings:
    """Sequential learned attack/defence estimates, fixed global hyperparameters."""

    def __init__(self, alpha=0.15, prior_matches=8):
        self.alpha = float(alpha)
        self.prior_matches = float(prior_matches)
        self.teams = {}
        self.games = 0
        self.goals_home = 0
        self.goals_away = 0
        self.outcomes = Counter()
        self.season = None
        self.last_match_date = ""

    def season_boundary(self, new_season):
        if new_season != self.season:
            if self.season is not None:
                # Dynamic team ratings regress after each missed or completed season.
                years = max(1, int(new_season[:4]) - int(self.season[:4]))
                factor = 0.70 ** years
                for state in self.teams.values():
                    state["attack"] = 1.33 + (state["attack"] - 1.33) * factor
                    state["defence"] = 1.33 + (state["defence"] - 1.33) * factor
                    state["appearances"] *= factor
            self.season = new_season

    def averages(self):
        # Pseudo-counts prevent a noisy first month from setting league bias.
        home = (self.goals_home + 1.50 * 80) / (self.games + 80)
        away = (self.goals_away + 1.18 * 80) / (self.games + 80)
        return home, away

    def predict_goals(self, home, away):
        base_home, base_away = self.averages()

        def influence(team, axis):
            state = self.teams.get(team)
            if state is None:
                return 1.0
            weight = state["appearances"] / (
                state["appearances"] + self.prior_matches
            )
            return max(.45, min(1.95,
                1.0 + weight * (state[axis] / 1.33 - 1.0)
            ))

        home_expected = (base_home * influence(home, "attack")
                        * influence(away, "defence"))
        away_expected = (base_away * influence(away, "attack")
                        * influence(home, "defence"))
        return (max(.12, min(4.5, home_expected)),
                max(.12, min(4.5, away_expected)))

    def predict(self, home, away):
        gh, ga = self.predict_goals(home, away)
        return outcome_probabilities(gh, ga)

    def reference_probs(self):
        total = sum(self.outcomes.values()) + 3
        return {
            "home": (self.outcomes["home"] + 1) / total,
            "draw": (self.outcomes["draw"] + 1) / total,
            "away": (self.outcomes["away"] + 1) / total,
        }

    def update(self, match):
        home, away = match["home"], match["away"]
        hg, ag = match["hg"], match["ag"]
        for team, scored, conceded in ((home, hg, ag), (away, ag, hg)):
            state = self.teams.setdefault(team, {
                "attack": 1.33, "defence": 1.33, "appearances": 0.0,
                "matches_total": 0,
            })
            alpha = self.alpha
            state["attack"] = state["attack"] * (1 - alpha) + scored * alpha
            state["defence"] = state["defence"] * (1 - alpha) + conceded * alpha
            state["appearances"] += 1
            state["matches_total"] += 1
        self.games += 1
        self.goals_home += hg
        self.goals_away += ag
        winner = "home" if hg > ag else "draw" if hg == ag else "away"
        self.outcomes[winner] += 1
        self.last_match_date = match["date"]

    def serialize(self):
        h, a = self.averages()
        return {
            "home_goal_mean": round(h, 6),
            "away_goal_mean": round(a, 6),
            "training_matches": self.games,
            "last_result_date": self.last_match_date,
            "teams": {
                team: {
                    "attack": round(st["attack"], 8),
                    "defence": round(st["defence"], 8),
                    "appearances": round(st["appearances"], 6),
                    "matches_total": st["matches_total"],
                }
                for team, st in sorted(self.teams.items())
            },
        }


def label(match):
    return "home" if match["hg"] > match["ag"] else (
        "away" if match["hg"] < match["ag"] else "draw"
    )


def score(probs, result):
    klass = label(result)
    brier = sum(
        (probs[k] - (1.0 if k == klass else 0.0)) ** 2
        for k in ("home", "draw", "away")
    )
    logloss = -math.log(max(1e-12, probs[klass]))
    return brier, logloss


def season_groups(matches):
    group = []
    last = None
    for match in matches:
        date_key = (match["date"], match["league"])
        if group and date_key != last:
            yield group
            group = []
        group.append(match)
        last = date_key
    if group:
        yield group


def run_sequential(matches, alpha, prior_matches, evaluate_seasons):
    """Every event is scored with only *earlier-date* results in its league."""
    states = {k: LeagueRatings(alpha, prior_matches) for k in LEAGUES}
    metrics = defaultdict(lambda: {
        "n": 0, "brier_sum": 0.0, "log_sum": 0.0,
        "ref_brier_sum": 0.0, "ref_log_sum": 0.0
    })
    by_league = defaultdict(lambda: {
        "n": 0, "brier_sum": 0.0, "log_sum": 0.0,
        "ref_brier_sum": 0.0, "ref_log_sum": 0.0
    })
    for group in season_groups(matches):
        league = group[0]["league"]
        state = states[league]
        state.season_boundary(group[0]["season"])
        before = []
        for match in group:
            predicted = state.predict(match["home"], match["away"])
            base = state.reference_probs()
            if match["season"] in evaluate_seasons:
                metric = metrics[match["season"]]
                league_metric = by_league[(match["season"],league)]
                a, b = score(predicted, match)
                c, d = score(base, match)
                for target in (metric, league_metric):
                    target["n"] += 1
                    target["brier_sum"] += a
                    target["log_sum"] += b
                    target["ref_brier_sum"] += c
                    target["ref_log_sum"] += d
            before.append(match)
        for match in before:
            state.update(match)
    return states, metrics, by_league


def summarize(metric):
    n = metric["n"]
    if not n:
        return {"matches": 0}
    return {
        "matches": n,
        "model_brier": round(metric["brier_sum"] / n, 5),
        "model_logloss": round(metric["log_sum"] / n, 5),
        "reference_brier": round(metric["ref_brier_sum"] / n, 5),
        "reference_logloss": round(metric["ref_log_sum"] / n, 5),
        "beats_reference_logloss": metric["log_sum"] < metric["ref_log_sum"],
    }


def train(data_dir=DATA_DIR, output=MODEL_FILE):
    matches = load_matches(data_dir)
    development = [r for r in matches if r["season"] <= VALIDATION_SEASON]
    validation_count = sum(r["season"] == VALIDATION_SEASON for r in matches)
    test_count = sum(r["season"] == TEST_SEASON for r in matches)
    if validation_count < 700 or test_count < 700:
        raise TrainingError("Te weinig onafhankelijke historische validatie/testwedstrijden")
    candidates = []
    for alpha in (.07, .12, .19):
        for prior in (4, 9, 16):
            _, metrics, _ = run_sequential(
                development, alpha, prior, {VALIDATION_SEASON}
            )
            candidates.append((metrics[VALIDATION_SEASON]["log_sum"] /
                               metrics[VALIDATION_SEASON]["n"], alpha, prior))
    best_loss, alpha, prior = min(candidates)
    # 2026/27 is a prospective continuation: no parameter is selected on it.
    current_count = sum(r["season"] == CURRENT_SEASON for r in matches)
    states, pooled, league_scores = run_sequential(
        matches, alpha, prior, {VALIDATION_SEASON, TEST_SEASON, CURRENT_SEASON}
    )
    seasons_count = {
        league: {
            season: sum(r["league"] == league and r["season"] == season
                        for r in matches)
            for season in EARLY_SEASONS + ("2020-21","2021-22","2022-23",
                                   "2023-24","2024-25","2025-26","2026-27")
        }
        for league in LEAGUES
    }
    diagnostics = {}
    for league in LEAGUES:
        counts = seasons_count[league]
        latest = counts[TEST_SEASON]
        prev = counts[VALIDATION_SEASON]
        diagnostics[league] = {
            "league_name": LEAGUES[league],
            "season_matches": counts,
            "validation": summarize(league_scores[(VALIDATION_SEASON, league)]),
            "test": summarize(league_scores[(TEST_SEASON, league)]),
            "prospective_2026_27": summarize(league_scores[(CURRENT_SEASON, league)]),
            "prospective_partial": counts[CURRENT_SEASON] < 100,
            "test_coverage_vs_previous_season": round(latest / prev, 3) if prev else None,
            "test_incomplete_or_stale": not bool(
                prev and latest / prev >= .97 and
                counts["2021-22"] and counts["2022-23"] and counts["2023-24"]
            ),
        }
    model = {
        "schema_version": 1,
        "model_type": "online_empirical_bayes_poisson",
        "version": TRAINING_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "project": "openfootball/football.json",
            "older_season_provenance_file": "data/historical/provenance_pre2020.json",
            "homepage": "https://github.com/openfootball/football.json",
            "license": "CC0 1.0 Universal",
            "source_is_real_historical_results": True,
            "uses_bookmaker_odds": False,
            "uses_shot_xg": False,
        },
        "parameters": {
            "alpha": alpha, "prior_matches": prior,
            "goal_model": "independent Poisson",
            "parameter_selection": "2024-25 log-loss only",
            "holdout_season": TEST_SEASON,
            "prospective_season": CURRENT_SEASON,
            "prospective_not_used_in_selection": True,
        },
        "evaluation": {
            "validation": summarize(pooled[VALIDATION_SEASON]),
            "test": summarize(pooled[TEST_SEASON]),
            "prospective_2026_27": summarize(pooled[CURRENT_SEASON]),
            "prospective_coverage_note": (
                "2026/27 bevat alleen geregistreerde eindstanden tot de jongste "
                "ingelezen datum; België heeft nog geen 2026/27 dataset. "
                "De parameters zijn NIET op 2026/27 gekozen."
            ),
            "by_league": diagnostics,
            "test_warning": (
                "Chronologische pre-match evaluatie van gedateerde "
                "wedstrijden uit 2025-26; sommige competities hebben "
                "onvolledige resultaten. Geen onafhankelijk bewijs van "
                "rendement ten opzichte van bookmakerprijzen."
            ),
        },
        "training_matches": len(matches),
        "added_older_results": sum(r["season"] in EARLY_SEASONS for r in matches),
        "training_start_date": min(r["date"] for r in matches),
        "last_observed_result_date": max(match["date"] for match in matches),
        "prospective_matches": current_count,
        "leagues": {league: state.serialize() for league, state in states.items()},
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return model


def load_pretrained(path=MODEL_FILE):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise TrainingError("Getraind basismodel ontbreekt; start train_model.bat")
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise TrainingError("Getraind modelbestand is ongeldig") from None
    if (not isinstance(model, dict) or model.get("schema_version") != 1
            or model.get("model_type") != "online_empirical_bayes_poisson"
            or not isinstance(model.get("leagues"), dict)):
        raise TrainingError("Onbekende modelversie")
    return model


def _lookup_team(league, name, teams):
    if not isinstance(name, str) or len(name) > 100:
        raise TrainingError("Ongeldige teamnaam")
    normalized = norm(name)
    matches = {norm(team): team for team in teams}
    if normalized in matches:
        return matches[normalized]
    alias = TEAM_ALIASES.get(league, {}).get(normalized)
    if alias is not None and alias in teams:
        return alias
    raise TrainingError(
        "Team niet bekend in de historische training. "
        "Controleer de schrijfwijze of voeg nieuwe uitslagen toe en train opnieuw."
    )


def predict_trained(model, league, home, away):
    """Predict match solely with pre-trained historical score estimates."""
    if league not in LEAGUES or league not in model["leagues"]:
        raise TrainingError("Competitie is nog niet getraind")
    state = model["leagues"][league]
    teams = state["teams"]
    home_actual = _lookup_team(league, home, teams)
    away_actual = _lookup_team(league, away, teams)
    if home_actual == away_actual:
        raise TrainingError("Teams moeten verschillen")
    prior = float(model["parameters"]["prior_matches"])

    def influence(team, axis):
        item = teams[team]
        weight = item["appearances"] / (item["appearances"] + prior)
        return max(.45, min(1.95,
            1.0 + weight * (item[axis] / 1.33 - 1.0)
        ))

    h = max(.12, min(4.5,
        state["home_goal_mean"] * influence(home_actual, "attack")
        * influence(away_actual, "defence")
    ))
    a = max(.12, min(4.5,
        state["away_goal_mean"] * influence(away_actual, "attack")
        * influence(home_actual, "defence")
    ))
    appearances = min(
        teams[home_actual]["appearances"], teams[away_actual]["appearances"]
    )
    return {
        "league": league,
        "league_name": LEAGUES[league],
        "home_team": home_actual,
        "away_team": away_actual,
        "expected_goals_home": round(h, 4),
        "expected_goals_away": round(a, 4),
        "probabilities": {
            k: round(v, 6) for k, v in outcome_probabilities(h, a).items()
        },
        "confidence": ("zeer laag" if appearances < 4 else
                       "laag" if appearances < 12 else "experimenteel"),
        "data_through": state["last_result_date"],
        "model_version": model["version"],
        "disclaimer": (
            "Geschatte verwachte doelpunten UIT HISTORISCHE SCORES "
            "(geen schot-xG, live blessure-/opstellingsdata of actuele odds). "
            "Model niet bewezen winstgevend."
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Hertrain SupahBetting op historische echte voetbaluitslagen."
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=MODEL_FILE)
    args = parser.parse_args()
    try:
        result = train(args.data_dir, args.output)
    except TrainingError as exc:
        parser.error(str(exc))
    print("SupahBetting baseline: getraind op", result["training_matches"], "uitslagen")
    print("Geselecteerde parameters:", result["parameters"])
    print("2024-25 VALIDATIE:", result["evaluation"]["validation"])
    print("2025-26 TEST:", result["evaluation"]["test"])
    print("2026-27 PROSPECTIEVE TEST:", result["evaluation"]["prospective_2026_27"])
    print("LAATSTE WERKELIJKE UITSLAG:", result["last_observed_result_date"])
    for league, report in result["evaluation"]["by_league"].items():
        print(league, report["league_name"],
              "| test:", report["test"]["matches"],
              "| mogelijk onvolledig:", report["test_incomplete_or_stale"])
    print("Lokaal model opgeslagen:", args.output)


if __name__ == "__main__":
    main()
