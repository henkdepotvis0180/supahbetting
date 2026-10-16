"""SQLite storage: one transaction per write, server-side price snapshots, auditable settlement.

Database is local. No accounts, real-money transactions, or web-hosting support.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .domain import MARKETS, ValidationError, match_analysis, quote_slip, validate_match


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        try:
            yield db
        finally:
            db.close()

    def initialize(self):
        with self.connection() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    kickoff TEXT NOT NULL,
                    home_xg REAL NOT NULL,
                    away_xg REAL NOT NULL,
                    odds_home REAL NOT NULL,
                    odds_draw REAL NOT NULL,
                    odds_away REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    result_home INTEGER,
                    result_away INTEGER,
                    CHECK ((result_home IS NULL AND result_away IS NULL) OR
                           (result_home >= 0 AND result_away >= 0))
                );
                CREATE TABLE IF NOT EXISTS slips (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    stake REAL NOT NULL,
                    combined_odds REAL NOT NULL,
                    estimated_probability REAL NOT NULL,
                    estimated_roi REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    payout REAL NOT NULL DEFAULT 0,
                    profit REAL
                );
                CREATE TABLE IF NOT EXISTS slip_legs (
                    id INTEGER PRIMARY KEY,
                    slip_id INTEGER NOT NULL REFERENCES slips(id),
                    match_id INTEGER NOT NULL REFERENCES matches(id),
                    market TEXT NOT NULL,
                    odds_snapshot REAL NOT NULL,
                    probability_snapshot REAL NOT NULL,
                    home_snapshot TEXT NOT NULL,
                    away_snapshot TEXT NOT NULL,
                    UNIQUE(slip_id, match_id)
                );
                CREATE INDEX IF NOT EXISTS idx_slip_legs_match ON slip_legs(match_id);
                CREATE INDEX IF NOT EXISTS idx_slip_legs_slip ON slip_legs(slip_id);
            """)
            db.commit()

    @staticmethod
    def _match_record(row):
        item = dict(row)
        item["analysis"] = match_analysis(item)
        item["is_settled"] = item["result_home"] is not None
        return item

    def add_match(self, data):
        clean = validate_match(data)
        with self.connection() as db:
            cursor = db.execute(
                """INSERT INTO matches
                   (home_team, away_team, kickoff, home_xg, away_xg,
                    odds_home, odds_draw, odds_away, source, created_at)
                   VALUES (:home_team, :away_team, :kickoff, :home_xg, :away_xg,
                           :odds_home, :odds_draw, :odds_away, :source, :created_at)""",
                {**clean, "created_at": utc_now()},
            )
            db.commit()
            return self.get_match(cursor.lastrowid)

    def get_match(self, identifier):
        with self.connection() as db:
            row = db.execute("SELECT * FROM matches WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise ValidationError("Wedstrijd niet gevonden")
        return self._match_record(row)

    def list_matches(self):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM matches ORDER BY id DESC LIMIT 250").fetchall()
        return [self._match_record(row) for row in rows]

    def create_slip(self, choices, stake):
        if not isinstance(choices, list) or not 1 <= len(choices) <= 8:
            raise ValidationError("Kies 1 tot 8 selecties")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            legs = []
            for choice in choices:
                if not isinstance(choice, dict):
                    raise ValidationError("Ongeldige selectie")
                match_id = choice.get("match_id")
                market = choice.get("market")
                if isinstance(match_id, bool) or not isinstance(match_id, int) or match_id < 1:
                    raise ValidationError("Ongeldige wedstrijd-ID")
                if market not in MARKETS:
                    raise ValidationError("Onbekende weddenschapsmarkt")
                row = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
                if row is None:
                    raise ValidationError("Een geselecteerde wedstrijd bestaat niet")
                if row["result_home"] is not None:
                    raise ValidationError("Je kunt geen selectie toevoegen uit een afgerekende wedstrijd")
                analysis = match_analysis(row)
                data = analysis["markets"][market]
                legs.append({
                    "match_id": match_id, "market": market,
                    "decimal_odds": data["decimal_odds"], "probability": data["probability"],
                    "home_team": row["home_team"], "away_team": row["away_team"],
                })
            quote = quote_slip(legs, stake)
            slip = db.execute(
                """INSERT INTO slips
                   (created_at, stake, combined_odds, estimated_probability, estimated_roi)
                   VALUES (?, ?, ?, ?, ?)""",
                (utc_now(), quote["stake"], quote["combined_odds"],
                 quote["combined_probability"], quote["expected_roi"]),
            )
            slip_id = slip.lastrowid
            db.executemany(
                """INSERT INTO slip_legs
                   (slip_id, match_id, market, odds_snapshot, probability_snapshot,
                    home_snapshot, away_snapshot)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(slip_id, leg["match_id"], leg["market"], leg["decimal_odds"],
                  leg["probability"], leg["home_team"], leg["away_team"]) for leg in legs],
            )
            db.commit()
        return self.get_slip(slip_id)

    def get_slip(self, slip_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM slips WHERE id = ?", (slip_id,)).fetchone()
            if row is None:
                raise ValidationError("Betslip niet gevonden")
            legs = db.execute(
                """SELECT l.match_id, l.market, l.odds_snapshot, l.probability_snapshot,
                          l.home_snapshot, l.away_snapshot, m.result_home, m.result_away
                   FROM slip_legs l JOIN matches m ON m.id = l.match_id
                   WHERE l.slip_id = ? ORDER BY l.id""",
                (slip_id,),
            ).fetchall()
        result = dict(row)
        result["legs"] = [dict(leg) for leg in legs]
        result["potential_payout"] = result["stake"] * result["combined_odds"]
        return result

    def list_slips(self):
        with self.connection() as db:
            ids = [row["id"] for row in
                   db.execute("SELECT id FROM slips ORDER BY id DESC LIMIT 150").fetchall()]
        return [self.get_slip(i) for i in ids]

    def settle_match(self, match_id, home_goals, away_goals):
        for label, value in [("Thuisgoals", home_goals), ("Uitgoals", away_goals)]:
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValidationError(f"{label}: gebruik een geheel getal tussen 0 en 100")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
            if row is None:
                raise ValidationError("Wedstrijd niet gevonden")
            if row["result_home"] is not None:
                raise ValidationError("Wedstrijd is al afgerekend; resultaat is onveranderlijk")
            db.execute("UPDATE matches SET result_home = ?, result_away = ? WHERE id = ?",
                       (home_goals, away_goals, match_id))
            affected = db.execute(
                """SELECT DISTINCT s.id, s.stake, s.combined_odds
                   FROM slips s JOIN slip_legs l ON s.id = l.slip_id
                   WHERE l.match_id = ? AND s.status = 'open'""", (match_id,)
            ).fetchall()
            for slip in affected:
                legs = db.execute(
                    """SELECT l.market, m.result_home, m.result_away
                       FROM slip_legs l JOIN matches m ON l.match_id = m.id
                       WHERE l.slip_id = ?""", (slip["id"],)
                ).fetchall()
                lost = False
                complete = True
                for leg in legs:
                    if leg["result_home"] is None:
                        complete = False
                        continue
                    winner = ("home" if leg["result_home"] > leg["result_away"] else
                              "away" if leg["result_home"] < leg["result_away"] else "draw")
                    if winner != leg["market"]:
                        lost = True
                if lost:
                    db.execute(
                        "UPDATE slips SET status='lost', payout=0, profit=? WHERE id=?",
                        (-slip["stake"], slip["id"]),
                    )
                elif complete:
                    payout = slip["stake"] * slip["combined_odds"]
                    db.execute(
                        "UPDATE slips SET status='won', payout=?, profit=? WHERE id=?",
                        (payout, payout - slip["stake"], slip["id"]),
                    )
            db.commit()
        return self.get_match(match_id)

    def stats(self):
        with self.connection() as db:
            data = db.execute("""
                SELECT
                   COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN status='open' THEN stake ELSE 0 END),0) AS open_stake,
                   COALESCE(SUM(CASE WHEN status!='open' THEN stake ELSE 0 END),0) AS settled_stake,
                   COALESCE(SUM(CASE WHEN status!='open' THEN profit ELSE 0 END),0) AS realized_profit,
                   SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) AS won,
                   SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) AS lost,
                   SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS opened
                FROM slips
            """).fetchone()
        result = dict(data)
        result["realized_roi"] = (
            result["realized_profit"] / result["settled_stake"]
            if result["settled_stake"] else None
        )
        result["currency"] = "EUR (fictief)"
        return result

    def seed_demo(self):
        demo = [
            ("Demo Noord", "Demo Zuid", 1.70, 1.05, 2.05, 3.45, 3.85),
            ("Demo Oost", "Demo West", 1.28, 1.40, 2.60, 3.20, 2.70),
            ("Demo Blauw", "Demo Groen", 2.02, 0.82, 1.85, 3.70, 4.35),
            ("Demo Rood", "Demo Geel", 1.14, 1.70, 3.10, 3.45, 2.22),
        ]
        with self.connection() as db:
            rows = db.execute("SELECT COUNT(*) FROM matches WHERE source='DEMO - fictief'").fetchone()[0]
        if rows:
            return {"created": 0, "message": "Voorbeeldwedstrijden bestaan al"}
        for h, a, hx, ax, oh, od, oa in demo:
            self.add_match({
                "home_team": h, "away_team": a, "home_xg": hx, "away_xg": ax,
                "odds_home": oh, "odds_draw": od, "odds_away": oa,
                "source": "DEMO - fictief",
            })
        return {"created": len(demo), "message": "Fictieve voorbeeldwedstrijden aangemaakt"}
