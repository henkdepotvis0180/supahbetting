"""SQLite research ledger for read-only native fork exports.

Separates imported external predictions and prices from the existing paper-bet
database so uncertain scraped odds never override transactional slip prices.
"""
from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .fork_bridge import BridgeError, PROVIDERS, load_export, utc_now
from .store import Store

LOG = logging.getLogger("supahbetting.research")
SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson"}
MAX_FILES_PER_SOURCE = 30
MAX_SCAN_OBSERVATIONS = 6000


class ResearchStore:
    def __init__(self, db_path, inbox=None):
        self.store = Store(db_path)
        self.inbox = Path(inbox) if inbox is not None else Path(db_path).parent / "imports"
        self.setup()

    def setup(self):
        with self.store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS research_imports (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    observation_count INTEGER NOT NULL,
                    rejected_count INTEGER NOT NULL,
                    UNIQUE(source, sha256)
                );
                CREATE TABLE IF NOT EXISTS research_observations (
                    id INTEGER PRIMARY KEY,
                    import_id INTEGER NOT NULL REFERENCES research_imports(id),
                    event_key TEXT NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    home_key TEXT NOT NULL,
                    away_key TEXT NOT NULL,
                    kickoff_date TEXT NOT NULL DEFAULT '',
                    kickoff TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('prediction','odds')),
                    market TEXT NOT NULL CHECK(market IN ('home','draw','away')),
                    value REAL NOT NULL CHECK(value >= 0),
                    bookmaker TEXT NOT NULL DEFAULT '',
                    observed_at TEXT NOT NULL DEFAULT '',
                    source_file TEXT NOT NULL DEFAULT '',
                    source_row INTEGER NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    imported_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS research_event_market
                    ON research_observations(event_key, market, kind);
                CREATE INDEX IF NOT EXISTS research_import_ref
                    ON research_observations(import_id);
            """)
            db.commit()

    def ingest(self, path, source):
        if source not in PROVIDERS:
            raise BridgeError("Onbekende bron")
        file = Path(path)
        payload = load_export(file, source)
        if not payload["observations"]:
            raise BridgeError("Geen geldige voorspellingen of quoteringen; controleer de export")
        now = utc_now()
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            seen = db.execute(
                "SELECT id FROM research_imports WHERE source=? AND sha256=?",
                (source, payload["digest"]),
            ).fetchone()
            if seen:
                return {
                    "source": source, "file": payload["file"],
                    "imported": 0, "skipped": True, "rejected_rows": 0,
                    "message": "Bestand eerder geïmporteerd; niet dubbel opgeslagen",
                    "errors": [],
                }
            row = db.execute(
                """INSERT INTO research_imports
                   (source,sha256,filename,imported_at,row_count,observation_count,rejected_count)
                   VALUES (?,?,?,?,?,?,?)""",
                (source, payload["digest"], payload["file"], now, payload["rows"],
                 len(payload["observations"]), payload["rejected_rows"]),
            )
            columns = [
                "import_id","event_key","home_team","away_team","home_key","away_key",
                "kickoff_date","kickoff","source","kind","market","value",
                "bookmaker","observed_at","source_file","source_row","note","imported_at",
            ]
            records = [tuple(
                row.lastrowid if field == "import_id" else
                now if field == "imported_at" else entry[field]
                for field in columns
            ) for entry in payload["observations"]]
            db.executemany(
                "INSERT INTO research_observations (" + ",".join(columns) +
                ") VALUES (" + ",".join("?" for _ in columns) + ")", records
            )
            db.commit()
        return {
            "source": source, "file": payload["file"], "imported": len(records),
            "skipped": False, "rejected_rows": payload["rejected_rows"],
            "errors": payload["errors"],
            "message": "Exportgegevens verwerkt voor onderzoeksvergelijking",
        }

    def make_inbox(self):
        self.inbox.mkdir(parents=True, exist_ok=True)
        for name in PROVIDERS:
            (self.inbox / name).mkdir(parents=True, exist_ok=True)

    def scan_inbox(self):
        """Read only bounded regular files inside designated provider directories.

        The HTTP layer never accepts paths. Symlinks are not followed. When
        multiple providers fail, other folders remain usable.
        """
        self.make_inbox()
        results, errors = [], []
        for name in PROVIDERS:
            directory = self.inbox / name
            try:
                if directory.is_symlink():
                    raise OSError("symlink directory forbidden")
                files = sorted(
                    (p for p in directory.iterdir()
                     if p.suffix.lower() in SUFFIXES and p.is_file()
                     and not p.is_symlink()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:MAX_FILES_PER_SOURCE]
                for file in files:
                    try:
                        results.append(self.ingest(file, name))
                    except (BridgeError, OSError, sqlite3.Error):
                        if len(errors) < 15:
                            errors.append({
                                "provider": name, "file": file.name[:120],
                                "error": "Kon export niet verwerken; controleer type, inhoud en rechten",
                            })
                        LOG.warning("Research export import skipped for %s", name)
            except OSError:
                errors.append({
                    "provider": name, "file": "",
                    "error": "Importmap is niet leesbaar",
                })
        return {
            "files_checked": len(results) + sum(1 for err in errors if err["file"]),
            "files_imported": sum(not x["skipped"] for x in results),
            "observations_imported": sum(x["imported"] for x in results),
            "rejected_rows": sum(x["rejected_rows"] for x in results),
            "errors": errors[:15],
            "inbox": str(self.inbox),
        }

    def status(self):
        with self.store.connection() as db:
            imports = [
                dict(row) for row in db.execute("""
                    SELECT source, COUNT(*) AS files, SUM(row_count) AS rows,
                           SUM(observation_count) AS observations,
                           MAX(imported_at) AS last_import
                    FROM research_imports GROUP BY source ORDER BY source
                """).fetchall()
            ]
            counts = {
                row["kind"]: row["n"] for row in db.execute(
                    "SELECT kind,COUNT(*) AS n FROM research_observations GROUP BY kind"
                ).fetchall()
            }
        return {
            "sources": imports,
            "predictions": counts.get("prediction", 0),
            "odds": counts.get("odds", 0),
            "inbox_folders": [name for name in PROVIDERS],
            "warning": (
                "Externe voorspellingen zijn niet onafhankelijk gekalibreerd; "
                "oude of niet-gedateerde odds zijn geen actuele prijzen."
            ),
        }

    def opportunities(self, *, max_results=100, now=None):
        """Strict exact match of event identity + market. No fuzzy matching.

        Undated native exports can only match records from the *same* file row,
        preventing unrelated fixtures with recurring team names from merging.
        """
        now = now or datetime.now(timezone.utc)
        today = now.date().isoformat()
        with self.store.connection() as db:
            rows = [dict(row) for row in db.execute(
                """SELECT * FROM research_observations ORDER BY id DESC LIMIT ?""",
                (MAX_SCAN_OBSERVATIONS,),
            ).fetchall()]
        odds_by_match = defaultdict(list)
        predictions = []
        for row in rows:
            key = (row["event_key"], row["market"])
            if row["kind"] == "odds":
                odds_by_match[key].append(row)
            else:
                predictions.append(row)
        opportunities = []
        for pred in predictions:
            key = (pred["event_key"], pred["market"])
            offers = odds_by_match.get(key, [])
            if not offers:
                continue
            for offer in offers:
                p, price = pred["value"], offer["value"]
                # Exclude duplicate import variants of exactly the same quoted
                # bookmaker+source+match+market; keep only latest captured row.
                date = pred["kickoff_date"] or offer["kickoff_date"]
                is_past = bool(date and date < today)
                # Only complete source timestamps can support freshness claims.
                captured = offer["observed_at"]
                age_hours = None
                if captured:
                    try:
                        timestamp = datetime.fromisoformat(captured)
                        if timestamp.tzinfo is not None:
                            age_hours = (now - timestamp).total_seconds() / 3600.0
                    except ValueError:
                        pass
                if is_past:
                    freshness = "historisch"
                elif age_hours is None:
                    freshness = "tijd_onbekend"
                elif age_hours < -0.05:
                    freshness = "tijd_ongeldig"
                elif age_hours <= 24:
                    freshness = "max_24_uur_oud"
                else:
                    freshness = "verouderd"
                opportunities.append({
                    "event_key": pred["event_key"],
                    "home_team": pred["home_team"], "away_team": pred["away_team"],
                    "kickoff_date": date,
                    "market": pred["market"],
                    "probability": round(p, 6),
                    "decimal_odds": price,
                    "fair_odds": round(1 / p, 4) if p > 0 else None,
                    "expected_roi": round(p * price - 1, 6),
                    "prediction_source": pred["source"],
                    "prediction_file": pred["source_file"],
                    "bookmaker": offer["bookmaker"],
                    "odds_source": offer["source"],
                    "odds_file": offer["source_file"],
                    "price_observed_at": captured,
                    "freshness": freshness,
                    "source_note": pred["note"],
                    "price_note": offer["note"],
                    "is_recommendation": False,
                })
        deduped = {}
        for result in opportunities:
            identity = (
                result["event_key"], result["market"],
                result["prediction_source"], result["bookmaker"],
            )
            if identity not in deduped:
                deduped[identity] = result
        ranked = sorted(
            deduped.values(), key=lambda row: row["expected_roi"], reverse=True
        )
        result = ranked[:max(1, min(int(max_results), 200))]
        return {
            "opportunities": result,
            "total_pairs": len(ranked),
            "sample_warning": (
                "Onderzoeksranglijst — geen wedadvies. Prijzen kunnen oud zijn en "
                "modelkansen zijn niet bewezen winstgevend. "
                "Geen historische odds presenteren als actueel aanbod."
            ),
        }
