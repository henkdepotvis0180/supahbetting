"""Native *export* adapters for the three upstream GitHub projects.

The original applications run independently. No ProphitBet classifiers, Prediict
joblib files or OddsHarvester scraping code is executed inside SupahBetting.

ProphitBet's GUI fixture export (src/gui/windows/models/fixtures.py):
 Home Team,Away Team,1,X,2,Predicted,Prob(1),Prob(X),Prob(2)
 The manual Prediction table also has Date,Home,Away,Prob(1),...

OddsHarvester's native JSON record (odds_portal_market_extractor.py):
 match_date,home_team,away_team,scraped_date,
 "1x2_market": [{"1": "2.1", "X": "3.3", "2": "3.5",
                "bookmaker_name": "...", "period": "..."}]

Prediict's CSV value-bets export:
 home_team,away_team,date,outcome,model_probability,bookmaker_odds,...
Its full probability CSV (predictor.py) has home_win_prob/draw_prob/away_win_prob.

Exports are unverified and *not* calibrated. No real-money betting is enabled.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

PROVIDERS = ("prophitbet", "oddsharvester", "prediict")
MAX_FILE_SIZE = 3_000_000
MAX_RECORDS = 1000
MAX_BOOKMAKERS = 60
MARKETS = ("home", "draw", "away")
MARKET_FROM_TEXT = {
    "1": "home", "home": "home", "home win": "home", "home_win": "home",
    "thuis": "home", "x": "draw", "draw": "draw", "gelijk": "draw",
    "2": "away", "away": "away", "away win": "away", "away_win": "away",
    "uit": "away",
}


class BridgeError(ValueError):
    """Import error deliberately containing no secrets or raw provider input."""


def text(value, limit=105):
    if not isinstance(value, str):
        return ""
    result = " ".join(value.strip().split())
    if len(result) > limit or any(ord(ch) < 32 or ord(ch) == 127 for ch in result):
        return ""
    return result


def canonical_team(value):
    value = text(value, 105)
    normalized = unicodedata.normalize("NFKD", value).casefold()
    # Deliberately conservative: no fuzzy substrings or country-specific aliases.
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def numeric(value, *, low=0.0, high=1.0):
    import math
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and low <= number <= high else None


def parse_date(value):
    """Returns (ISO date, timezone-aware timestamp if present).

    Ambiguous or unrecognized formats are left undated instead of guessed.
    """
    value = text(value, 70)
    if not value:
        return "", ""
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is not None and result.utcoffset() is not None:
            iso = result.astimezone(timezone.utc).isoformat()
            return iso[:10], iso
        return result.date().isoformat(), ""
    except ValueError:
        return "", ""


def _read_file(path):
    path = Path(path)
    if path.suffix.lower() not in (".csv", ".json", ".jsonl", ".ndjson"):
        raise BridgeError("Alleen CSV, JSON of NDJSON wordt ondersteund; gebruik CSV in ProphitBet")
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_SIZE:
            raise BridgeError("Importbestand ontbreekt of is te groot (max 3 MB)")
        raw = path.read_bytes()
        data = raw.decode("utf-8-sig")
    except (OSError, UnicodeError):
        raise BridgeError("Importbestand is niet leesbaar als UTF-8") from None
    return data, hashlib.sha256(raw).hexdigest()


def read_rows(path):
    data, digest = _read_file(path)
    suffix = Path(path).suffix.lower()
    try:
        if suffix == ".csv":
            rows = list(csv.DictReader(io.StringIO(data, newline="")))
        elif suffix in (".jsonl", ".ndjson"):
            rows = [json.loads(line) for line in data.splitlines() if line.strip()]
        else:
            payload = json.loads(data)
            # Both the normal list export and a root list under a records key.
            if isinstance(payload, dict):
                rows = payload.get("matches") or payload.get("data") or payload.get("results")
            else:
                rows = payload
    except (ValueError, csv.Error, TypeError):
        raise BridgeError("Ongeldige CSV/JSON-indeling; controleer het bronbestand") from None
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise BridgeError("Vereist een lijst met maximaal 1000 records")
    return rows, digest


def _base(raw, *, source, digest, index):
    if not isinstance(raw, dict):
        raise BridgeError("Rij moet een object zijn")
    home = text(raw.get("home_team") or raw.get("Home Team") or raw.get("Home") or raw.get("home"))
    away = text(raw.get("away_team") or raw.get("Away Team") or raw.get("Away") or raw.get("away"))
    hk, ak = canonical_team(home), canonical_team(away)
    if not hk or not ak or hk == ak:
        raise BridgeError("Ontbrekende of gelijke teamnamen")
    date, kickoff = parse_date(
        raw.get("match_date") or raw.get("Date") or raw.get("date") or raw.get("kickoff")
    )
    # Undated rows only match prediction/odds from the same source file row.
    event_key = f"{hk}|{ak}|{date}" if date else f"undated:{source}:{digest}:{index}"
    return {
        "event_key": event_key, "home_team": home, "away_team": away,
        "home_key": hk, "away_key": ak, "kickoff_date": date,
        "kickoff": kickoff, "source": source,
    }


def _source_record(base, *, kind, market, value, bookmaker="", observed_at="",
                   source_file="", row=0, note=""):
    return {
        **base, "kind": kind, "market": market, "value": value,
        "bookmaker": bookmaker, "observed_at": observed_at,
        "source_file": source_file, "source_row": row, "note": note,
    }


def _triple(raw, columns):
    p = [numeric(raw.get(column)) for column in columns]
    if any(x is None for x in p):
        return None
    total = sum(p)
    if not 0.92 <= total <= 1.08 or total <= 0:
        # Small rounding deviations are okay; no silently accepting nonsense.
        raise BridgeError("1X2-modelkansen moeten samen ongeveer 100% zijn")
    return tuple(value / total for value in p)


def _outcome(raw):
    label = str(raw).strip().casefold().replace("_", " ")
    return MARKET_FROM_TEXT.get(label)


def _odds_triple(raw, keys):
    found = [numeric(raw.get(column), low=1.01, high=1000.0) for column in keys]
    return tuple(found) if all(v is not None for v in found) else None


def _extract_nested(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or len(value) > 32_000:
        return []
    try:
        obj = json.loads(value)
    except (ValueError, TypeError):
        # The upstream CSV serializer writes Python repr with single quotes.
        # ast.literal_eval never executes arbitrary Python expressions.
        try:
            obj = ast.literal_eval(value)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return []
    return obj if isinstance(obj, list) else []


def normalize_export(source, raw, *, digest, index, filename):
    """Return only explicit valid probability/odds observations; no guesses."""
    if source not in PROVIDERS:
        raise BridgeError("Onbekende bronadapter")
    base = _base(raw, source=source, digest=digest, index=index)
    records = []
    if source == "prophitbet":
        probs = _triple(raw, ("Prob(1)", "Prob(X)", "Prob(2)"))
        if not probs:
            raise BridgeError("ProphitBet RESULT-export met Prob(1), Prob(X), Prob(2) vereist")
        for market, prob in zip(MARKETS, probs):
            records.append(_source_record(
                base, kind="prediction", market=market, value=prob,
                source_file=filename, row=index,
                note="ProphitBet modelkans; niet onafhankelijk gevalideerd",
            ))
        odds = _odds_triple(raw, ("1", "X", "2"))
        if odds:
            for market, price in zip(MARKETS, odds):
                records.append(_source_record(
                    base, kind="odds", market=market, value=price,
                    bookmaker="ProphitBet invoer (bookmaker onbekend)",
                    source_file=filename, row=index,
                    note="Quotering uit ProphitBet-export; moment van prijs onbekend",
                ))
    elif source == "oddsharvester":
        odds_rows = _extract_nested(raw.get("1x2_market"))
        if not odds_rows:
            raise BridgeError("OddsHarvester-record mist bruikbare 1x2_market-lijst")
        parsed, seen = 0, set()
        date, timestamp = parse_date(raw.get("scraped_date"))
        for market_line in odds_rows[:MAX_BOOKMAKERS]:
            if not isinstance(market_line, dict):
                continue
            if text(market_line.get("period", "")) not in ("", "FullTime", "full_time", "Full Time"):
                continue
            bookmaker = text(market_line.get("bookmaker_name")) or "Onbekende bookmaker"
            triple = _odds_triple(market_line, ("1", "X", "2"))
            if not triple:
                continue
            blocked = market_line.get("blocked_outcomes", [])
            if isinstance(blocked, str):
                blocked = _extract_nested(blocked)
            if not isinstance(blocked, list):
                blocked = []
            for market, label, price in zip(MARKETS, ("1", "X", "2"), triple):
                if label in blocked:
                    continue
                if (bookmaker.casefold(), market) in seen:
                    continue
                seen.add((bookmaker.casefold(), market))
                records.append(_source_record(
                    base, kind="odds", market=market, value=price,
                    bookmaker=bookmaker, observed_at=timestamp,
                    source_file=filename, row=index,
                    note=("Scrape-tijd bevestigd" if timestamp else
                          "Geen geldige tijdstempel; geen actuele prijsclaim"),
                ))
                parsed += 1
        if not parsed:
            raise BridgeError("Geen bruikbare volledige 1X2-quoteringen")
    else:  # prediict: format adapter only; repo has no confirmed redistribution license
        prob_cols = ("home_win_prob", "draw_prob", "away_win_prob")
        if all(key in raw for key in prob_cols):
            probs = _triple(raw, prob_cols)
            if not probs:
                raise BridgeError("Lege modelkansen in Prediict-export")
            for market, prob in zip(MARKETS, probs):
                records.append(_source_record(
                    base, kind="prediction", market=market, value=prob,
                    source_file=filename, row=index,
                    note="Prediict-modeluitvoer; geen bewezen kalibratie",
                ))
        else:
            market = _outcome(raw.get("outcome"))
            probability = numeric(raw.get("model_probability"))
            if market is None or probability is None:
                raise BridgeError("Prediict-bestand mist herkenbare voorspelling")
            records.append(_source_record(
                base, kind="prediction", market=market, value=probability,
                source_file=filename, row=index,
                note="Prediict value-bet CSV: alleen kans voor deze markt beschikbaar",
            ))
        market = _outcome(raw.get("outcome"))
        price = numeric(raw.get("bookmaker_odds"), low=1.01, high=1000)
        if market is not None and price is not None:
            records.append(_source_record(
                base, kind="odds", market=market, value=price,
                bookmaker="Prediict export (bookmaker niet gespecificeerd)",
                source_file=filename, row=index,
                note="Historische Prediict-quotering; opnametijd niet bekend",
            ))
    return records


def load_export(path, source):
    if source not in PROVIDERS:
        raise BridgeError("Onbekende bronadapter")
    rows, digest = read_rows(path)
    observations, errors = [], []
    filename = Path(path).name
    if not rows:
        raise BridgeError("Export bevat geen records")
    for index, row in enumerate(rows, start=1):
        try:
            observations.extend(normalize_export(
                source, row, digest=digest, index=index, filename=filename
            ))
        except BridgeError as exc:
            if len(errors) < 20:
                errors.append({"row": index, "error": str(exc)})
    return {
        "source": source, "digest": digest, "file": filename,
        "rows": len(rows), "observations": observations,
        "rejected_rows": sum(1 for _ in errors) if len(errors) < 20 else 20,
        "errors": errors,
    }
