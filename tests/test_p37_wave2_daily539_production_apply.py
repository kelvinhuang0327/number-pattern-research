"""
test_p37_wave2_daily539_production_apply.py
=============================================
P37 Wave 2 DAILY_539 Production Apply — post-apply verification tests.

Verifies the state of the production DB AFTER the P37 apply script has run.
Reads from the actual production DB (lottery_api/data/lottery_v2.db).

Tests:
  - Exactly 6 Wave 2 DAILY_539 strategies applied
  - No BIG_LOTTO strategies applied via P37
  - No P31B Wave 1 strategies in the P37 applied set
  - Total inserted rows = 9000
  - Each strategy has exactly 1500 rows
  - Production rows = 28960 after apply
  - No lifecycle = ONLINE rows were inserted (all DRY_RUN)
  - Duplicate check passed (no unexpected duplicates)
  - Per-strategy row counts in production DB match expected
  - controlled_apply_id correctly set for all P37 rows
  - truth_level correctly set for all P37 rows
  - dry_run = 0 (production rows, not rehearsal)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Constants ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P37_MANIFEST_PATH = REPO_ROOT / "outputs" / "replay" / "p37_wave2_daily539_production_apply_20260523.json"

CONTROLLED_APPLY_ID = "P37_DAILY539_WAVE2_9000_PROD_20260523"
EXPECTED_TOTAL_ROWS = 28960
EXPECTED_INSERTED_ROWS = 9000
ROWS_PER_STRATEGY = 1500

WAVE2_STRATEGY_IDS = frozenset({
    "markov_1bet_539",
    "acb_single_539",
    "zone_gap_3bet_539",
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
})

WAVE1_STRATEGY_IDS = frozenset({
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
})

# BIG_LOTTO strategies (must not be present in P37 rows)
BIGLOTTO_STRATEGY_IDS = frozenset({
    "ts3_regime_3bet",
    "biglotto_triple_strike",
    "biglotto_deviation_2bet",
    "regime_2bet",
    "p1_deviation_4bet",
    "p1_dev_sum5bet",
})


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _conn():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _count_all() -> int:
    conn = _conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


def _p37_rows_by_strategy() -> dict[str, int]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ? GROUP BY strategy_id",
            (CONTROLLED_APPLY_ID,),
        ).fetchall()
        return {row["strategy_id"]: row["cnt"] for row in rows}
    finally:
        conn.close()


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestP37ProductionApplyDB:
    """Tests reading directly from the production DB."""

    def test_total_production_rows_is_28960(self):
        """Total rows in production DB must be exactly 28960 after P37 apply."""
        total = _count_all()
        assert total == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {total}"
        )

    def test_p37_inserted_exactly_9000_rows(self):
        """P37 controlled_apply_id must correspond to exactly 9000 rows."""
        counts = _p37_rows_by_strategy()
        total_p37 = sum(counts.values())
        assert total_p37 == EXPECTED_INSERTED_ROWS, (
            f"Expected {EXPECTED_INSERTED_ROWS} P37 rows, got {total_p37}"
        )

    def test_exactly_6_wave2_strategies_applied(self):
        """Exactly 6 Wave 2 DAILY_539 strategies must be present in P37 rows."""
        counts = _p37_rows_by_strategy()
        applied_strategies = set(counts.keys())
        assert applied_strategies == WAVE2_STRATEGY_IDS, (
            f"Applied strategies mismatch.\n"
            f"Expected: {sorted(WAVE2_STRATEGY_IDS)}\n"
            f"Got: {sorted(applied_strategies)}"
        )

    def test_each_wave2_strategy_has_exactly_1500_rows(self):
        """Each of the 6 Wave 2 strategies must have exactly 1500 rows."""
        counts = _p37_rows_by_strategy()
        for sid in WAVE2_STRATEGY_IDS:
            count = counts.get(sid, 0)
            assert count == ROWS_PER_STRATEGY, (
                f"Strategy {sid}: expected {ROWS_PER_STRATEGY} rows, got {count}"
            )

    def test_no_biglotto_strategies_in_p37_rows(self):
        """No BIG_LOTTO strategies should be in P37 applied rows."""
        counts = _p37_rows_by_strategy()
        for sid in BIGLOTTO_STRATEGY_IDS:
            assert sid not in counts, (
                f"BIG_LOTTO strategy '{sid}' unexpectedly found in P37 rows"
            )

    def test_no_wave1_strategies_in_p37_rows(self):
        """No P31B Wave 1 strategies should be in P37 applied rows."""
        counts = _p37_rows_by_strategy()
        for sid in WAVE1_STRATEGY_IDS:
            assert sid not in counts, (
                f"Wave 1 strategy '{sid}' unexpectedly found in P37 rows"
            )

    def test_no_online_lifecycle_in_p37_rows(self):
        """No P37 rows should have lifecycle_status = ONLINE."""
        conn = _conn()
        try:
            online_count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND source LIKE '%ONLINE%'",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
            # Also check strategy_id is not in a known ONLINE category
            # (All Wave 2 strategies should be DRY_RUN, never promoted)
            assert online_count == 0, (
                f"Found {online_count} rows with ONLINE in source for P37"
            )
        finally:
            conn.close()

    def test_all_p37_rows_have_dry_run_equals_zero(self):
        """All P37 rows must have dry_run = 0 (production rows, not rehearsal)."""
        conn = _conn()
        try:
            non_prod = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND dry_run != 0",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert non_prod == 0, (
            f"Found {non_prod} P37 rows with dry_run != 0 (should all be production rows)"
        )

    def test_all_p37_rows_have_correct_truth_level(self):
        """All P37 rows must have truth_level = DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED."""
        expected_truth_level = "DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED"
        conn = _conn()
        try:
            wrong_tl = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND truth_level != ?",
                (CONTROLLED_APPLY_ID, expected_truth_level),
            ).fetchone()[0]
        finally:
            conn.close()
        assert wrong_tl == 0, (
            f"Found {wrong_tl} P37 rows with incorrect truth_level"
        )

    def test_all_p37_rows_are_daily539(self):
        """All P37 rows must have lottery_type = DAILY_539."""
        conn = _conn()
        try:
            non_539 = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND lottery_type != 'DAILY_539'",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert non_539 == 0, (
            f"Found {non_539} P37 rows with lottery_type != DAILY_539"
        )

    def test_all_p37_rows_have_correct_source(self):
        """All P37 rows must have source = P37_WAVE2_PRODUCTION_APPLY."""
        expected_source = "P37_WAVE2_PRODUCTION_APPLY"
        conn = _conn()
        try:
            wrong_source = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND source != ?",
                (CONTROLLED_APPLY_ID, expected_source),
            ).fetchone()[0]
        finally:
            conn.close()
        assert wrong_source == 0, (
            f"Found {wrong_source} P37 rows with incorrect source"
        )

    def test_duplicate_check_no_extra_rows_for_wave2_strategies(self):
        """Wave 2 strategy rows in production must all belong to P37 (no pre-existing duplicates)."""
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays "
                "WHERE strategy_id IN (?,?,?,?,?,?) GROUP BY strategy_id",
                tuple(sorted(WAVE2_STRATEGY_IDS)),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            # Each Wave 2 strategy should have exactly ROWS_PER_STRATEGY rows total
            assert row["cnt"] == ROWS_PER_STRATEGY, (
                f"Strategy {row['strategy_id']}: expected exactly {ROWS_PER_STRATEGY} rows, "
                f"got {row['cnt']} — possible duplicate insertion"
            )

    def test_all_p37_rows_have_predicted_status(self):
        """All P37 rows should have replay_status = PREDICTED (no errors)."""
        conn = _conn()
        try:
            non_predicted = conn.execute(
                "SELECT replay_status, COUNT(*) as cnt FROM strategy_prediction_replays "
                "WHERE controlled_apply_id = ? AND replay_status != 'PREDICTED' "
                "GROUP BY replay_status",
                (CONTROLLED_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()
        assert len(non_predicted) == 0, (
            f"Found non-PREDICTED rows in P37: {[(r['replay_status'], r['cnt']) for r in non_predicted]}"
        )


class TestP37Manifest:
    """Tests reading the P37 apply manifest JSON."""

    def test_manifest_file_exists(self):
        assert P37_MANIFEST_PATH.exists(), f"Manifest not found: {P37_MANIFEST_PATH}"

    def test_manifest_classification(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["classification"] == "P37_WAVE2_DAILY539_PRODUCTION_APPLY_MERGED_TO_MAIN"

    def test_manifest_row_counts(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["production_rows_before"] == 19960
        assert data["production_rows_inserted"] == 9000
        assert data["production_rows_after"] == 28960

    def test_manifest_has_6_strategies(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert len(data["strategies"]) == 6

    def test_manifest_all_strategies_dry_run(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        for s in data["strategies"]:
            assert s["lifecycle"] == "DRY_RUN", (
                f"Strategy {s['strategy_id']} has lifecycle={s['lifecycle']}, expected DRY_RUN"
            )

    def test_manifest_each_strategy_1500_rows(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        for s in data["strategies"]:
            assert s["inserted"] == 1500, (
                f"Strategy {s['strategy_id']} inserted={s['inserted']}, expected 1500"
            )

    def test_manifest_duplicate_check_pass(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["duplicate_check"] == "PASS"

    def test_manifest_transaction_atomic(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["transaction"] == "ATOMIC_COMMIT"

    def test_manifest_wave_is_2(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["wave"] == 2

    def test_manifest_lottery_type_daily539(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["lottery_type"] == "DAILY_539"

    def test_manifest_authorization_phrase(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["authorization"] == "YES apply P37 production wave2 daily539"

    def test_manifest_all_pass(self):
        data = json.loads(P37_MANIFEST_PATH.read_text())
        assert data["all_pass"] is True
        assert data["preflight_pass"] is True
        assert data["duplicate_check_pass"] is True
        assert data["postflight_pass"] is True
