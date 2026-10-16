"""Documented CSV/JSON bridge for separately run model and odds data pipelines.

This intentionally does NOT run or scrape upstream tools. Export/transform their
outputs into the documented normalized schema and then import locally.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .domain import ValidationError
from .store import Store

COLUMNS = (
    "home_team", "away_team", "kickoff", "home_xg", "away_xg",
    "odds_home", "odds_draw", "odds_away", "source",
)


def rows_from_file(path):
    path = Path(path)
    if path.stat().st_size > 8_000_000:
        raise ValidationError("Importbestand is te groot (maximaal 8 MB)")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
    elif path.suffix.lower() == ".json":
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValidationError("JSON-import vereist een lijst met objecten")
        yield from payload
    else:
        raise ValidationError("Alleen .csv en .json zijn toegestaan")


def import_matches(store, path, limit=1000):
    result = {"imported": 0, "rejected": 0, "errors": []}
    for number, row in enumerate(rows_from_file(path), 1):
        if number > limit:
            raise ValidationError(f"Importlimiet ({limit} rijen) bereikt")
        try:
            if not isinstance(row, dict):
                raise ValidationError("Rij is geen object")
            # Source must be present in normalized datasets to preserve provenance.
            if not row.get("source"):
                raise ValidationError("Bronkolom ontbreekt")
            store.add_match(row)
            result["imported"] += 1
        except (ValidationError, TypeError, ValueError) as exc:
            result["rejected"] += 1
            if len(result["errors"]) < 20:
                result["errors"].append({"row": number, "error": str(exc)})
    return result


def main():
    parser = argparse.ArgumentParser(description="Importeer gecontroleerde voetbaldata")
    parser.add_argument("path", type=Path, help="CSV/JSON met genormaliseerde wedstrijden")
    parser.add_argument("--db", type=Path, default=Path(".supahbetting") / "data.sqlite3")
    args = parser.parse_args()
    result = import_matches(Store(args.db), args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["rejected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
