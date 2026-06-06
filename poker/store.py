"""
Persistence layer (N4): SQLite storage for opponent profiles and session
results, so reads accumulate across runs and can be visualised later.

Pure-stdlib (sqlite3). Safe to import without numpy.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = "data/poker_stats.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    name TEXT PRIMARY KEY,
    hands INTEGER, vpip REAL, pfr REAL, af REAL, fold REAL, style TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    hands INTEGER, big_blind REAL
);
CREATE TABLE IF NOT EXISTS session_players (
    session_id INTEGER, name TEXT, archetype TEXT,
    net REAL, bb100 REAL, hands INTEGER,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
"""


class StatsStore:
    def __init__(self, path: str = DEFAULT_DB):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---- profiles ------------------------------------------------------
    def upsert_profiles(self, profiles: list[dict]) -> None:
        """profiles: rows from ProfileBook.summary()."""
        cur = self.conn.cursor()
        for p in profiles:
            cur.execute(
                """INSERT INTO profiles(name, hands, vpip, pfr, af, fold, style)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(name) DO UPDATE SET
                     hands=excluded.hands, vpip=excluded.vpip, pfr=excluded.pfr,
                     af=excluded.af, fold=excluded.fold, style=excluded.style,
                     updated_at=CURRENT_TIMESTAMP""",
                (p["name"], p["hands"], p["vpip"], p["pfr"], p["af"], p["fold"], p["style"]))
        self.conn.commit()

    def get_profile(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT name,hands,vpip,pfr,af,fold,style FROM profiles WHERE name=?",
            (name,)).fetchone()
        if not row:
            return None
        keys = ["name", "hands", "vpip", "pfr", "af", "fold", "style"]
        return dict(zip(keys, row))

    def all_profiles(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT name,hands,vpip,pfr,af,fold,style FROM profiles ORDER BY hands DESC"
        ).fetchall()
        keys = ["name", "hands", "vpip", "pfr", "af", "fold", "style"]
        return [dict(zip(keys, r)) for r in rows]

    # ---- sessions ------------------------------------------------------
    def save_session(self, result) -> int:
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sessions(hands, big_blind) VALUES(?,?)",
                    (result.hands, result.big_blind))
        sid = cur.lastrowid
        for r in result.reports:
            cur.execute(
                """INSERT INTO session_players(session_id,name,archetype,net,bb100,hands)
                   VALUES(?,?,?,?,?,?)""",
                (sid, r.name, r.archetype, round(r.net, 2),
                 round(r.bb_per_100(result.big_blind), 2), r.hands))
        if result.profiles:
            self.upsert_profiles(result.profiles)
        self.conn.commit()
        return sid

    def session_history(self, name: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT s.id, s.created_at, sp.net, sp.bb100, sp.hands
               FROM session_players sp JOIN sessions s ON s.id=sp.session_id
               WHERE sp.name=? ORDER BY s.id""", (name,)).fetchall()
        keys = ["session_id", "created_at", "net", "bb100", "hands"]
        return [dict(zip(keys, r)) for r in rows]
