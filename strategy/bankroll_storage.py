"""
BankrollState SQLite Persistence Layer.

Provides atomic, crash-safe bankroll state management via SQLite.
Ensures bankroll state survives system restarts (§ P1 優化項目).

Usage:
    from strategy.bankroll_storage import BankrollStorage

    storage = BankrollStorage()           # uses default path
    state = storage.load()                # load or create
    state.current -= 500                  # modify in-memory
    storage.save(state)                   # persist
    storage.record_bet(bet_record)        # append bet history
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict
from typing import Dict, List, Optional

from strategy.kelly_criterion import BankrollState

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "bankroll.db"
)


class BankrollStorage:
    """SQLite-backed BankrollState persistence."""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    # ── Schema ────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bankroll_state (
                    id              INTEGER PRIMARY KEY CHECK (id = 1),
                    initial         REAL NOT NULL,
                    current         REAL NOT NULL,
                    peak            REAL NOT NULL,
                    consecutive_losses INTEGER NOT NULL DEFAULT 0,
                    daily_pnl       REAL NOT NULL DEFAULT 0.0,
                    conservative_mode INTEGER NOT NULL DEFAULT 0,
                    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bet_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
                    game_id         TEXT,
                    market          TEXT,
                    side            TEXT,
                    odds            REAL,
                    stake_pct       REAL,
                    stake_amount    REAL,
                    pnl             REAL,
                    won             INTEGER,
                    bankroll_after  REAL,
                    metadata_json   TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_snapshot (
                    date            TEXT PRIMARY KEY,
                    opening_bankroll REAL NOT NULL,
                    closing_bankroll REAL,
                    daily_pnl       REAL,
                    bets_count      INTEGER DEFAULT 0,
                    wins            INTEGER DEFAULT 0,
                    peak            REAL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Load / Save ───────────────────────────────────────

    def load(self) -> BankrollState:
        """Load the most recent BankrollState, or create a fresh one."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT initial, current, peak, consecutive_losses, "
                "daily_pnl, conservative_mode FROM bankroll_state WHERE id=1"
            ).fetchone()

        if row is None:
            state = BankrollState()
            self.save(state)
            return state

        return BankrollState(
            initial=row[0],
            current=row[1],
            peak=row[2],
            consecutive_losses=row[3],
            daily_pnl=row[4],
            conservative_mode=bool(row[5]),
            bets_today=[],
        )

    def save(self, state: BankrollState) -> None:
        """Upsert the singleton bankroll state row."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO bankroll_state
                    (id, initial, current, peak, consecutive_losses,
                     daily_pnl, conservative_mode, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    initial = excluded.initial,
                    current = excluded.current,
                    peak    = excluded.peak,
                    consecutive_losses = excluded.consecutive_losses,
                    daily_pnl          = excluded.daily_pnl,
                    conservative_mode  = excluded.conservative_mode,
                    updated_at         = datetime('now')
            """, (
                state.initial,
                state.current,
                state.peak,
                state.consecutive_losses,
                state.daily_pnl,
                int(state.conservative_mode),
            ))

    # ── Bet History ───────────────────────────────────────

    def record_bet(
        self,
        game_id: str,
        market: str,
        side: str,
        odds: float,
        stake_pct: float,
        stake_amount: float,
        pnl: float,
        won: bool,
        bankroll_after: float,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Append a bet result to the history ledger."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO bet_history
                    (game_id, market, side, odds, stake_pct, stake_amount,
                     pnl, won, bankroll_after, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, market, side, odds, stake_pct, stake_amount,
                pnl, int(won), bankroll_after,
                json.dumps(metadata) if metadata else None,
            ))

    def get_bet_history(self, limit: int = 100) -> List[Dict]:
        """Retrieve recent bet history as list of dicts."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bet_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Daily Snapshots ───────────────────────────────────

    def save_daily_snapshot(
        self, date: str, opening: float, closing: float,
        daily_pnl: float, bets_count: int, wins: int, peak: float,
    ) -> None:
        """Record end-of-day bankroll snapshot."""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO daily_snapshot
                    (date, opening_bankroll, closing_bankroll,
                     daily_pnl, bets_count, wins, peak)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    closing_bankroll = excluded.closing_bankroll,
                    daily_pnl        = excluded.daily_pnl,
                    bets_count       = excluded.bets_count,
                    wins             = excluded.wins,
                    peak             = excluded.peak
            """, (date, opening, closing, daily_pnl, bets_count, wins, peak))

    def get_daily_snapshots(self, limit: int = 30) -> List[Dict]:
        """Retrieve recent daily snapshots."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM daily_snapshot ORDER BY date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Reset ──────────────────────────────────────────────

    def reset_daily(self, state: BankrollState) -> None:
        """Reset daily counters (call at start of new trading day)."""
        state.daily_pnl = 0.0
        state.bets_today = []
        self.save(state)
