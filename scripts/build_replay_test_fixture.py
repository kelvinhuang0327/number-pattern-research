#!/usr/bin/env python3
"""
Build a deterministic synthetic SQLite fixture for replay requires_db tests.

This fixture is intentionally minimal and synthetic:
  - No real production DB data.
  - No strategy edge claim semantics.
  - No active strategy state.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


def _build_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE strategy_replay_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type TEXT NOT NULL,
            strategy_scope TEXT NOT NULL DEFAULT 'ALL',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            generator_version TEXT NOT NULL DEFAULT 'v0.1',
            data_hash TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            target_date TEXT,
            strategy_id TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            strategy_version TEXT NOT NULL DEFAULT 'v0.1',
            history_cutoff_draw TEXT,
            replay_status TEXT NOT NULL,
            reject_reason TEXT,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            hit_numbers TEXT,
            hit_count INTEGER DEFAULT 0,
            special_hit INTEGER DEFAULT 0,
            replay_run_id INTEGER,
            generated_at TEXT,
            UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
        )
        """
    )
    cur.execute("CREATE INDEX idx_srr_lottery ON strategy_replay_runs(lottery_type)")
    cur.execute("CREATE INDEX idx_srr_status ON strategy_replay_runs(status)")
    cur.execute("CREATE INDEX idx_spr_lottery ON strategy_prediction_replays(lottery_type)")
    cur.execute("CREATE INDEX idx_spr_strategy ON strategy_prediction_replays(strategy_id)")
    cur.execute("CREATE INDEX idx_spr_draw ON strategy_prediction_replays(target_draw)")
    cur.execute("CREATE INDEX idx_spr_status ON strategy_prediction_replays(replay_status)")
    cur.execute("CREATE INDEX idx_spr_run ON strategy_prediction_replays(replay_run_id)")


def _seed_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    # Fixed timestamps keep cadence checks deterministic and within 14 days.
    runs = [
        (
            1001,
            "BIG_LOTTO",
            "ALL",
            "2026-05-07T08:00:00+00:00",
            "2026-05-07T08:05:00+00:00",
            "DONE",
            "fixture-v1",
            "fixture-hash-big-done",
            "synthetic fixture run",
        ),
        (
            1002,
            "POWER_LOTTO",
            "ALL",
            "2026-05-07T09:00:00+00:00",
            "2026-05-07T09:05:00+00:00",
            "DONE",
            "fixture-v1",
            "fixture-hash-power-done",
            "synthetic fixture run",
        ),
        (
            1003,
            "DAILY_539",
            "ALL",
            "2026-05-07T10:00:00+00:00",
            "2026-05-07T10:05:00+00:00",
            "DONE",
            "fixture-v1",
            "fixture-hash-539-done",
            "synthetic fixture run",
        ),
        (
            1004,
            "BIG_LOTTO",
            "ALL",
            "2026-04-20T08:00:00+00:00",
            "2026-04-20T08:05:00+00:00",
            "FAILED_LEGACY",
            "fixture-v1",
            "fixture-hash-big-legacy",
            "legacy fixture row",
        ),
    ]
    cur.executemany(
        """
        INSERT INTO strategy_replay_runs
        (id, lottery_type, strategy_scope, started_at, finished_at, status, generator_version, data_hash, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        runs,
    )

    replay_rows = [
        (
            2001,
            "BIG_LOTTO",
            "114000101",
            "2026-05-01",
            "synthetic_big_A",
            "Synthetic Big Strategy A",
            "fixture-v1",
            "114000100",
            "PREDICTED",
            None,
            "[1,2,3,4,5,6]",
            None,
            "[2,3,4,5,6,7]",
            None,
            "[2,3,4,5,6]",
            5,
            0,
            1001,
            "2026-05-07T08:01:00+00:00",
        ),
        (
            2002,
            "POWER_LOTTO",
            "114000201",
            "2026-05-02",
            "synthetic_power_A",
            "Synthetic Power Strategy A",
            "fixture-v1",
            "114000200",
            "REPLAY_ERROR",
            "synthetic error note",
            "[8,9,10,11,12,13]",
            5,
            "[8,9,10,20,21,22]",
            6,
            "[8,9,10]",
            3,
            1,
            1002,
            "2026-05-07T09:01:00+00:00",
        ),
        (
            2003,
            "DAILY_539",
            "114000301",
            "2026-05-03",
            "synthetic_539_A",
            "Synthetic 539 Strategy A",
            "fixture-v1",
            "114000300",
            "PREDICTED",
            None,
            "[1,11,21,31,39]",
            None,
            "[1,5,9,21,39]",
            None,
            "[1,21,39]",
            3,
            0,
            1003,
            "2026-05-07T10:01:00+00:00",
        ),
    ]
    cur.executemany(
        """
        INSERT INTO strategy_prediction_replays
        (id, lottery_type, target_draw, target_date, strategy_id, strategy_name, strategy_version,
         history_cutoff_draw, replay_status, reject_reason, predicted_numbers, predicted_special,
         actual_numbers, actual_special, hit_numbers, hit_count, special_hit, replay_run_id, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        replay_rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic synthetic replay DB fixture."
    )
    parser.add_argument(
        "--output",
        required=False,
        default="/tmp/lottery_replay_test_fixture.db",
        help="Output sqlite fixture path (default: /tmp/lottery_replay_test_fixture.db)",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    conn = sqlite3.connect(str(output))
    try:
        _build_schema(conn)
        _seed_data(conn)
        conn.commit()
        cur = conn.cursor()
        run_count = cur.execute("SELECT COUNT(*) FROM strategy_replay_runs").fetchone()[0]
        replay_count = cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()

    print(f"[replay-fixture] built: {output}")
    print(f"[replay-fixture] strategy_replay_runs={run_count}")
    print(f"[replay-fixture] strategy_prediction_replays={replay_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
