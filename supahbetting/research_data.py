"""Careful calendar-year 2016-present OpenFootball CC0 ingestion.

Runs on the owner's PC: no hidden background process, no unverified matches,
no claims that the upstream source is current merely because it was fetched.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .trained_model import LEAGUES

SOURCE = "https://raw.githubusercontent.com/openfootball/football.json/master"
LOCAL = Path("data/research")
MAX_BYTES = 2_000_000


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def seasons(today=None):
    today = today or datetime.now(timezone.utc).date()
    final = today.year if today.month >= 7 else today.year - 1
    return [f"{y}-{(y+1)%100:02d}" for y in range(2015, final + 1)]


def valid_score(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(n) is not int or n < 0 or n > 20 for n in value)):
        return None
    return value


def parse_source(source, league, season, today=None):
    today = today or datetime.now(timezone.utc).date()
    if league not in LEAGUES or season not in seasons(today):
        raise ValueError("Ongeldige broncompetitie of seizoen")
    if not isinstance(source, dict) or not isinstance(source.get("matches"), list):
        raise ValueError("Onbekend OpenFootball-formaat")
    finished, planned, seen = [], [], set()
    for item in source["matches"]:
        if not isinstance(item, dict):
            continue
        home, away = item.get("team1"), item.get("team2")
        if not (isinstance(home, str) and isinstance(away, str)
                and home.strip() and away.strip() and home.strip() != away.strip()
                and len(home) <= 120 and len(away) <= 120):
            continue
        try:
            day = date.fromisoformat(item["date"])
        except (ValueError, TypeError, KeyError):
            continue
        if (day.year not in (int(season[:4]), int(season[:4])+1)
                or day < date(2016, 1, 1)):
            continue
        identifier = hashlib.sha256(
            json.dumps([league, season, day.isoformat(), home.strip(), away.strip()],
                       ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:24]
        if identifier in seen:
            raise ValueError("Dubbele wedstrijd in bron (zelfde datum/thuis/uit)")
        seen.add(identifier)
        base = {"id": identifier, "league": league, "season": season,
                "date": day.isoformat(), "home": home.strip(), "away": away.strip()}
        score = item.get("score")
        ft = valid_score(score.get("ft")) if isinstance(score, dict) else None
        if ft is not None and day <= today:
            finished.append({**base, "hg": ft[0], "ag": ft[1]})
        elif ft is None and day > today:
            planned.append(base)
        # Same-day scheduled games cannot be safely assumed pre-kickoff.
    return finished, planned


def retrieve(league, season, *, root=LOCAL / "raw", timeout=25):
    if league not in LEAGUES or season not in seasons():
        raise ValueError("Ongeldige bron")
    path = Path(root) / season / (league + ".json")
    headers = {"User-Agent": "SupahBetting-Research/0.12 (public CC0 results)",
               "Accept": "application/json"}
    url = f"{SOURCE}/{season}/{league}.json"
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Bronbestand is te groot")
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
                raise ValueError("Onjuist JSON-schema")
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, path)
            atomic_json(path.with_suffix(".provenance.json"), {
                "source_url": url, "license": "CC0-1.0",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            })
            return data, "downloaded", url
    except HTTPError as exc:
        if exc.code == 404:
            return None, "not_published", url
        raise RuntimeError("Bron geeft HTTP " + str(exc.code)) from None
    except URLError as exc:
        raise RuntimeError("OpenFootball tijdelijk niet bereikbaar") from exc


def refresh(*, directory=LOCAL, full=None, delay=1.0, fetcher=None, today=None):
    today = today or datetime.now(timezone.utc).date()
    directory = Path(directory)
    inventory = directory / "inventory.json"
    fetcher = fetcher or retrieve
    old = json.loads(inventory.read_text(encoding="utf-8")) if inventory.exists() else {}
    if full is None:
        last_full = old.get("last_full_check_at_utc")
        try:
            age = (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
                   - datetime.fromisoformat(last_full)).total_seconds() if last_full else None
        except (TypeError, ValueError):
            age = None
        full = not inventory.exists() or age is None or age >= 7 * 86400
    completed = {m["id"]: m for m in old.get("matches", [])}
    fixtures = {m["id"]: m for m in old.get("fixtures", [])}
    coverage = {x["key"]: x for x in old.get("coverage", [])}
    failures = []
    requested = seasons(today)
    selected = requested if full else requested[-2:]
    for season in selected:
        for league in LEAGUES:
            key = f"{season}/{league}"
            try:
                if fetcher is retrieve:
                    data, status, url = fetcher(league, season, root=directory / "raw")
                else:
                    data, status, url = fetcher(league, season)
                if data is None:
                    coverage[key] = {"key": key, "state": status, "finished": 0,
                                     "fixtures": 0, "url": url}
                    continue
                results, future = parse_source(data, league, season, today)
                # Never erase complete season scores on a temporarily truncated feed.
                old_count = sum(
                    m["league"] == league and m["season"] == season
                    for m in completed.values()
                )
                if old_count >= 10 and len(results) < old_count * 0.7:
                    raise ValueError("Bron fors ingekort; oude resultaten in quarantaine")
                completed = {k: v for k, v in completed.items()
                             if (v["season"], v["league"]) != (season, league)}
                fixtures = {k: v for k, v in fixtures.items()
                            if (v["season"], v["league"]) != (season, league)}
                completed.update({m["id"]: m for m in results})
                fixtures.update({m["id"]: m for m in future})
                coverage[key] = {
                    "key": key, "state": status, "finished": len(results),
                    "fixtures": len(future), "url": url,
                    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            except (ValueError, OSError, RuntimeError) as exc:
                failures.append({"key": key, "error_type": type(exc).__name__})
            if delay and fetcher is retrieve:
                time.sleep(max(0.5, delay))
    matches = sorted(completed.values(), key=lambda m: (m["date"], m["league"], m["home"]))
    planned = sorted(fixtures.values(), key=lambda m: (m["date"], m["league"], m["home"]))
    if not matches:
        raise ValueError("Geen gecontroleerde wedstrijden; bestaand bestand behouden")
    seen_before = {m["id"] for m in old.get("matches", [])}
    is_first_import = not inventory.exists()
    # A full initial backfill is NOT 22,000+ matches "played since the last scan".
    new_ids = ([] if is_first_import else
               [m["id"] for m in matches if m["id"] not in seen_before])
    result = {
        "schema_version": 1, "source": "openfootball/football.json",
        "license": "CC0-1.0", "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "season_range": [requested[0], requested[-1]],
        "last_full_check_at_utc": (
            datetime.now(timezone.utc).isoformat() if full
            else old.get("last_full_check_at_utc")
        ),
        "matches": matches, "fixtures": planned,
        "coverage": sorted(coverage.values(), key=lambda m: m["key"]),
        "failed_sources": failures, "new_final_match_ids": new_ids,
        "is_initial_import": is_first_import,
        "first_import_at_utc": (
            datetime.now(timezone.utc).isoformat() if is_first_import
            else old.get("first_import_at_utc", old.get("fetched_at_utc"))
        ),
        "initial_backfill_matches": (
            len(matches) if is_first_import else old.get("initial_backfill_matches", len(old.get("matches", [])))
        ),
        "latest_result_date": max(m["date"] for m in matches),
        "warning": "Upstream kan achterlopen; geen bewijs van volledige dekking of actualiteit.",
    }
    atomic_json(inventory, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()
    result = refresh(full=True if args.full else None, delay=max(0.5, args.delay))
    print(json.dumps({
        "finished_matches": len(result["matches"]),
        "future_fixtures": len(result["fixtures"]),
        "new_results": len(result["new_final_match_ids"]),
        "initial_backfill": result.get("initial_backfill_matches"),
        "is_initial_import": result["is_initial_import"],
        "latest_result_date": result["latest_result_date"],
        "missing_sources": [c["key"] for c in result["coverage"]
                            if c["state"] == "not_published"],
        "failed_sources": result["failed_sources"],
    }, indent=2))


if __name__ == "__main__":
    main()
