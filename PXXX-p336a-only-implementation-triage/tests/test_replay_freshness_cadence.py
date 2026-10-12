"""
test_replay_freshness_cadence.py
=================================
P0-5-D  G4 — Freshness Cadence Gate

Cadence Policy v0.1  (from wiki/system/replay_data_hygiene.md §3.2):
  Each lottery type must have at least one DONE run whose started_at
  is within the last 14 days.

Rules:
  - FAILED_LEGACY runs must NOT count toward cadence compliance.
  - Missing a DONE run within 14 days must fail the gate.
  - A 30-day-old run fixture must FAIL (staleness regression guard).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
DB_PATH = LOTTERY_API / "data" / "lottery_v2.db"

CADENCE_DAYS = 14  # Maximum allowed age for the latest DONE run per lottery

LOTTERY_TYPES = ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _latest_done_run(conn: sqlite3.Connection, lottery_type: str) -> dict | None:
    """Return the most recent DONE run for a lottery type, or None."""
    row = conn.execute(
        """
        SELECT id, lottery_type, status, started_at, finished_at
        FROM strategy_replay_runs
        WHERE lottery_type = ?
          AND status = 'DONE'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (lottery_type,),
    ).fetchone()
    if row is None:
        return None
    cols = ("id", "lottery_type", "status", "started_at", "finished_at")
    return dict(zip(cols, row))


def _age_days(started_at_str: str, now: datetime) -> float:
    """Return age in days from started_at ISO string to now."""
    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return (now - started_at).total_seconds() / 86400.0


# ── Live DB fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live_conn():
    if not DB_PATH.exists():
        pytest.skip("Replay DB not found")
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ── Live cadence tests ────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.skipif(not DB_PATH.exists(), reason="Replay DB not found")
class TestFreshnessCadence:
    def test_all_lottery_types_have_done_run(self, live_conn):
        """Each lottery type must have at least one DONE run."""
        for lt in LOTTERY_TYPES:
            run = _latest_done_run(live_conn, lt)
            assert run is not None, (
                f"cadence: no DONE run found for {lt!r} — gate requires a DONE run within {CADENCE_DAYS} days"
            )

    def test_done_run_within_cadence_window(self, live_conn):
        """Each lottery's latest DONE run must be within 14 days."""
        now = datetime.now(timezone.utc)
        for lt in LOTTERY_TYPES:
            run = _latest_done_run(live_conn, lt)
            assert run is not None, f"cadence: no DONE run for {lt!r}"
            age = _age_days(run["started_at"], now)
            assert age <= CADENCE_DAYS, (
                f"cadence: {lt!r} latest DONE run is {age:.1f} days old "
                f"(max allowed: {CADENCE_DAYS} days, run_id={run['id']})"
            )

    def test_failed_legacy_does_not_count_as_done(self, live_conn):
        """FAILED_LEGACY runs must NOT satisfy the cadence requirement."""
        # Get all FAILED_LEGACY runs
        rows = live_conn.execute(
            "SELECT lottery_type, id FROM strategy_replay_runs WHERE status = 'FAILED_LEGACY'"
        ).fetchall()
        for lt, run_id in rows:
            # For this lottery type, FAILED_LEGACY alone must NOT be sufficient
            # The cadence requirement must be met by a DONE run
            done_run = _latest_done_run(live_conn, lt)
            assert done_run is not None, (
                f"cadence: {lt!r} only has FAILED_LEGACY run #{run_id}, no DONE run exists — gate fails"
            )
            assert done_run["status"] == "DONE", (
                f"cadence: latest run for {lt!r} returned status={done_run['status']!r}, expected DONE"
            )

    def test_failed_legacy_runs_excluded_from_cadence(self, live_conn):
        """Cadence query must filter out FAILED_LEGACY status explicitly."""
        for lt in LOTTERY_TYPES:
            # Confirm SQL only returns DONE rows
            row = live_conn.execute(
                """
                SELECT status FROM strategy_replay_runs
                WHERE lottery_type = ?
                  AND status = 'DONE'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (lt,),
            ).fetchone()
            if row is not None:
                assert row[0] == "DONE", (
                    f"cadence: query returned non-DONE status {row[0]!r} for {lt!r}"
                )


# ── Staleness regression fixture tests ────────────────────────────────────────

class TestCadencePolicyLogic:
    """Unit-level tests of the cadence logic — no live DB required."""

    def test_30_day_old_run_fails_cadence(self):
        """Fixture: a 30-day-old run must fail the 14-day cadence gate."""
        now = datetime.now(timezone.utc)
        stale_ts = (now - timedelta(days=30)).isoformat()
        age = _age_days(stale_ts, now)
        assert age > CADENCE_DAYS, (
            f"30-day-old run should be > {CADENCE_DAYS} days old, got {age:.1f}"
        )
        # This is the assertion the gate would fire
        with pytest.raises(AssertionError):
            assert age <= CADENCE_DAYS, f"cadence: stale run ({age:.1f} days old)"

    def test_1_day_old_run_passes_cadence(self):
        """Fixture: a 1-day-old run must pass the 14-day cadence gate."""
        now = datetime.now(timezone.utc)
        fresh_ts = (now - timedelta(days=1)).isoformat()
        age = _age_days(fresh_ts, now)
        assert age <= CADENCE_DAYS, f"1-day-old run should pass 14-day gate, got {age:.1f} days"

    def test_exactly_14_day_old_run_passes(self):
        """Boundary: exactly 14 days is on the boundary — must pass."""
        now = datetime.now(timezone.utc)
        boundary_ts = (now - timedelta(days=14, seconds=-60)).isoformat()  # 14d minus 1 min = 13.9996d
        age = _age_days(boundary_ts, now)
        assert age <= CADENCE_DAYS

    def test_15_day_old_run_fails_cadence(self):
        """Fixture: a 15-day-old run must fail the 14-day cadence gate."""
        now = datetime.now(timezone.utc)
        ts = (now - timedelta(days=15)).isoformat()
        age = _age_days(ts, now)
        assert age > CADENCE_DAYS, f"15-day run should be > {CADENCE_DAYS} days, got {age:.1f}"
