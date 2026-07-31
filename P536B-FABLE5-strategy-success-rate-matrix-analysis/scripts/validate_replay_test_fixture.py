#!/usr/bin/env python3
"""
Validate integrity of the synthetic replay sqlite fixture.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


REQUIRED_TABLE_COLUMNS = {
    "fixture_metadata": {
        "fixture_name",
        "fixture_version",
        "schema_version",
        "created_by",
        "synthetic_only",
        "created_at",
    },
    "strategy_replay_runs": {
        "id",
        "lottery_type",
        "started_at",
        "status",
        "notes",
    },
    "strategy_prediction_replays": {
        "id",
        "lottery_type",
        "target_draw",
        "history_cutoff_draw",
        "replay_status",
        "predicted_numbers",
        "actual_numbers",
        "hit_numbers",
        "replay_run_id",
    },
}


def _fail(msg: str, code: int = 1) -> int:
    print(f"[replay-fixture-validate] ERROR: {msg}", file=sys.stderr)
    return code


def _table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate replay test fixture integrity.")
    parser.add_argument("--db", required=True, help="Path to sqlite fixture DB.")
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        return _fail(f"fixture DB not found: {db_path}", 2)

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        for table, req_cols in REQUIRED_TABLE_COLUMNS.items():
            if table not in tables:
                return _fail(f"required table missing: {table}")
            cols = _table_columns(cur, table)
            missing = sorted(req_cols - cols)
            if missing:
                return _fail(f"required columns missing in {table}: {missing}")

        meta = cur.execute(
            "SELECT fixture_name, fixture_version, schema_version, synthetic_only FROM fixture_metadata LIMIT 1"
        ).fetchone()
        if meta is None:
            return _fail("fixture_metadata is empty")
        if int(meta[3]) != 1:
            return _fail("fixture_metadata.synthetic_only must be 1")

        run_count = cur.execute("SELECT COUNT(*) FROM strategy_replay_runs").fetchone()[0]
        replay_count = cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        if run_count < 4:
            return _fail(f"strategy_replay_runs row count too low: {run_count}")
        if replay_count < 3:
            return _fail(f"strategy_prediction_replays row count too low: {replay_count}")

        # cadence support checks
        done_rows = cur.execute(
            "SELECT COUNT(*) FROM strategy_replay_runs WHERE status='DONE' AND lottery_type IN ('BIG_LOTTO','POWER_LOTTO','DAILY_539')"
        ).fetchone()[0]
        if done_rows < 3:
            return _fail("missing DONE rows for required lottery types")

        # integrity checks aligned with requires_db tests
        causal_violations = cur.execute(
            """
            SELECT COUNT(*) FROM strategy_prediction_replays
            WHERE history_cutoff_draw IS NOT NULL
              AND TRIM(CAST(history_cutoff_draw AS TEXT)) != ''
              AND CAST(history_cutoff_draw AS INTEGER) >= CAST(target_draw AS INTEGER)
            """
        ).fetchone()[0]
        if causal_violations > 0:
            return _fail(f"history_cutoff_draw >= target_draw violations: {causal_violations}")

        missing_non_error_fields = cur.execute(
            """
            SELECT COUNT(*) FROM strategy_prediction_replays
            WHERE UPPER(COALESCE(replay_status, '')) NOT LIKE '%ERROR%'
              AND (
                predicted_numbers IS NULL OR TRIM(predicted_numbers) = ''
                OR actual_numbers IS NULL OR TRIM(actual_numbers) = ''
                OR hit_numbers IS NULL OR TRIM(hit_numbers) = ''
              )
            """
        ).fetchone()[0]
        if missing_non_error_fields > 0:
            return _fail(
                "non-error rows missing predicted/actual/hit fields: "
                f"{missing_non_error_fields}"
            )

        print(f"[replay-fixture-validate] db={db_path}")
        print(
            "[replay-fixture-validate] metadata="
            f"name={meta[0]} version={meta[1]} schema={meta[2]} synthetic_only={meta[3]}"
        )
        print(f"[replay-fixture-validate] strategy_replay_runs={run_count}")
        print(f"[replay-fixture-validate] strategy_prediction_replays={replay_count}")
        print("[replay-fixture-validate] integrity=PASS")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
