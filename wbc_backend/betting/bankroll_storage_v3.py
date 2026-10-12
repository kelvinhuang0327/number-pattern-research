"""
BankrollState SQLite Persistence for wbc_backend.

Equivalent to strategy/bankroll_storage.py but uses the wbc_backend
BankrollState dataclass with its institutional-grade fields.
"""
from __future__ import annotations

import json
import os
import sqlite3

from wbc_backend.betting.risk_control import BankrollState

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "bankroll_v3.db"
)


class BankrollStorageV3:
    """SQLite-backed BankrollState persistence (V3 institutional)."""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bankroll_state (
                    id                  INTEGER PRIMARY KEY CHECK (id = 1),
                    initial             REAL NOT NULL,
                    current             REAL NOT NULL,
                    peak                REAL NOT NULL,
                    daily_start         REAL NOT NULL,
                    consecutive_losses  INTEGER NOT NULL DEFAULT 0,
                    total_bets_today    INTEGER NOT NULL DEFAULT 0,
                    daily_exposure      REAL NOT NULL DEFAULT 0.0,
                    is_conservative_mode INTEGER NOT NULL DEFAULT 0,
                    recent_results_json TEXT DEFAULT '[]',
                    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
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

    # ── Load / Save ───────────────────────────────────────

    def load(self) -> BankrollState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT initial, current, peak, daily_start, "
                "consecutive_losses, total_bets_today, daily_exposure, "
                "is_conservative_mode, recent_results_json "
                "FROM bankroll_state WHERE id=1"
            ).fetchone()

        if row is None:
            state = BankrollState()
            self.save(state)
            return state

        recent = json.loads(row[8]) if row[8] else []
        return BankrollState(
            initial=row[0],
            current=row[1],
            peak=row[2],
            daily_start=row[3],
            consecutive_losses=row[4],
            total_bets_today=row[5],
            daily_exposure=row[6],
            is_conservative_mode=bool(row[7]),
            recent_results=recent,
        )

    def save(self, state: BankrollState) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO bankroll_state
                    (id, initial, current, peak, daily_start,
                     consecutive_losses, total_bets_today, daily_exposure,
                     is_conservative_mode, recent_results_json, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    initial              = excluded.initial,
                    current              = excluded.current,
                    peak                 = excluded.peak,
                    daily_start          = excluded.daily_start,
                    consecutive_losses   = excluded.consecutive_losses,
                    total_bets_today     = excluded.total_bets_today,
                    daily_exposure       = excluded.daily_exposure,
                    is_conservative_mode = excluded.is_conservative_mode,
                    recent_results_json  = excluded.recent_results_json,
                    updated_at           = datetime('now')
            """, (
                state.initial,
                state.current,
                state.peak,
                state.daily_start,
                state.consecutive_losses,
                state.total_bets_today,
                state.daily_exposure,
                int(state.is_conservative_mode),
                json.dumps(state.recent_results),
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
        metadata: dict | None = None,
    ) -> None:
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

    def get_bet_history(self, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bet_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_daily_snapshot(
        self, date: str, opening: float, closing: float,
        daily_pnl: float, bets_count: int, wins: int, peak: float,
    ) -> None:
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

    def reset_daily(self, state: BankrollState) -> None:
        state.daily_start = state.current
        state.total_bets_today = 0
        state.daily_exposure = 0.0
        state.is_conservative_mode = False
        self.save(state)
