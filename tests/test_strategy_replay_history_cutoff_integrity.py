"""
P0-2 Replay Integrity CI Gate

Read-only integrity checks for strategy_prediction_replays:
1) history_cutoff_draw must be present, except rows linked to FAILED_LEGACY runs
   with non-empty notes.
2) history_cutoff_draw must be strictly less than target_draw.
3) predicted/actual/hit fields must be non-empty when status is not ERROR.

This test runs offline and only reads lottery_api/data/lottery_v2.db.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _connect_ro() -> sqlite3.Connection:
    # Force read-only mode for CI gate checks.
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt_rows(rows: list[sqlite3.Row], limit: int = 20) -> str:
    lines = []
    for r in rows[:limit]:
        lines.append(
            "id={id} lottery={lottery_type} target={target_draw} status={replay_status} "
            "run={replay_run_id} run_status={run_status} cutoff={history_cutoff_draw}".format(
                id=r["id"],
                lottery_type=r["lottery_type"],
                target_draw=r["target_draw"],
                replay_status=r["replay_status"],
                replay_run_id=r["replay_run_id"],
                run_status=r["run_status"],
                history_cutoff_draw=r["history_cutoff_draw"],
            )
        )
    if len(rows) > limit:
        lines.append(f"... and {len(rows) - limit} more")
    return "\n".join(lines)


@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestReplayHistoryCutoffIntegrity:
    def test_history_cutoff_not_null_except_failed_legacy_with_notes(self):
        conn = _connect_ro()
        try:
            rows = conn.execute(
                """
                SELECT
                    r.id,
                    r.lottery_type,
                    r.target_draw,
                    r.replay_status,
                    r.replay_run_id,
                    r.history_cutoff_draw,
                    COALESCE(run.status, '') AS run_status,
                    COALESCE(run.notes, '') AS run_notes
                FROM strategy_prediction_replays r
                LEFT JOIN strategy_replay_runs run
                    ON run.id = r.replay_run_id
                WHERE (r.history_cutoff_draw IS NULL OR TRIM(CAST(r.history_cutoff_draw AS TEXT)) = '')
                  AND NOT (
                    COALESCE(run.status, '') = 'FAILED_LEGACY'
                    AND TRIM(COALESCE(run.notes, '')) != ''
                  )
                ORDER BY r.id
                """
            ).fetchall()
        finally:
            conn.close()

        assert not rows, (
            "Found rows with missing history_cutoff_draw outside FAILED_LEGACY exception:\n"
            + _fmt_rows(rows)
        )

    def test_history_cutoff_must_be_strictly_before_target_draw(self):
        conn = _connect_ro()
        try:
            rows = conn.execute(
                """
                SELECT
                    r.id,
                    r.lottery_type,
                    r.target_draw,
                    r.replay_status,
                    r.replay_run_id,
                    r.history_cutoff_draw,
                    COALESCE(run.status, '') AS run_status
                FROM strategy_prediction_replays r
                LEFT JOIN strategy_replay_runs run
                    ON run.id = r.replay_run_id
                WHERE r.history_cutoff_draw IS NOT NULL
                  AND TRIM(CAST(r.history_cutoff_draw AS TEXT)) != ''
                  AND CAST(r.history_cutoff_draw AS INTEGER) >= CAST(r.target_draw AS INTEGER)
                ORDER BY r.id
                """
            ).fetchall()
        finally:
            conn.close()

        assert not rows, (
            "Found causal violations (history_cutoff_draw >= target_draw):\n"
            + _fmt_rows(rows)
        )

    def test_non_error_rows_must_have_predicted_actual_hit_fields(self):
        conn = _connect_ro()
        try:
            rows = conn.execute(
                """
                SELECT
                    r.id,
                    r.lottery_type,
                    r.target_draw,
                    r.replay_status,
                    r.replay_run_id,
                    r.history_cutoff_draw,
                    COALESCE(run.status, '') AS run_status,
                    r.predicted_numbers,
                    r.actual_numbers,
                    r.hit_numbers
                FROM strategy_prediction_replays r
                LEFT JOIN strategy_replay_runs run
                    ON run.id = r.replay_run_id
                WHERE UPPER(COALESCE(r.replay_status, '')) NOT LIKE '%ERROR%'
                  AND (
                    r.predicted_numbers IS NULL OR TRIM(r.predicted_numbers) = ''
                    OR r.actual_numbers IS NULL OR TRIM(r.actual_numbers) = ''
                    OR r.hit_numbers IS NULL OR TRIM(r.hit_numbers) = ''
                  )
                ORDER BY r.id
                """
            ).fetchall()
        finally:
            conn.close()

        assert not rows, (
            "Found non-error rows with missing predicted/actual/hit fields:\n"
            + _fmt_rows(rows)
        )
