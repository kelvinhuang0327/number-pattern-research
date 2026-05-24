"""
test_p48_powerlotto_special_null_policy.py
==========================================
P48 — POWER_LOTTO actual_special is NULL Policy tests.

Chosen policy: Policy A — skip rows where actual_special is NULL.

Tests:
  1. Policy A: _build_production_row returns None when actual_special is NULL
  2. Policy A: rows with non-null actual_special are NOT skipped
  3. Policy A: skip_count correctly accumulates across all strategies
  4. Policy A: no null actual_special rows ever inserted into production DB
  5. Policy A: manifest records skip_count
  6. Production DB: zero rows with actual_special=NULL in Wave 4 set (after apply)
  7. Policy A consistency: special_hit=0 is NOT used to mask NULL actual_special
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
MANIFEST_PATH  = (
    REPO_ROOT / "outputs" / "replay"
    / "p48_powerlotto_wave4_production_apply_20260524.json"
)

CONTROLLED_APPLY_ID = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"


# ─── Unit tests: _build_production_row Policy A ──────────────────────────────

class TestPolicyA:
    """Unit tests for Policy A in _build_production_row."""

    def setup_method(self):
        from scripts.p48_powerlotto_wave4_production_apply import _build_production_row
        self._build = _build_production_row

    def _make_raw(self, actual_special=None, strategy_id="pp3_freqort_4bet") -> dict:
        return {
            "strategy_id":            strategy_id,
            "lottery_type":           "POWER_LOTTO",
            "target_draw":            "1234",
            "draw_date":              "2026-01-01",
            "prediction_cutoff_date": "2025-12-31",
            "prediction_generated_at": "2026-01-01T00:00:00Z",
            "predicted_numbers":      [1, 2, 3, 4, 5, 6],
            "predicted_special":      3,
            "actual_numbers":         [1, 2, 7, 8, 9, 10],
            "actual_special":         actual_special,
            "hit_numbers":            [1, 2],
            "hit_count":              2,
            "special_hit":            0 if actual_special is None else (1 if actual_special == 3 else 0),
            "replay_status":          "PREDICTED",
            "reject_reason":          None,
            "history_cutoff_draw":    "1233",
            "strategy_name":          "Test",
            "strategy_version":       "v0.1",
        }

    def test_policy_a_returns_none_when_actual_special_is_null(self):
        """Policy A: returns None for rows where actual_special is NULL."""
        raw = self._make_raw(actual_special=None)
        result = self._build(raw, "2026-01-01T00:00:00Z")
        assert result is None, "Expected None (Policy A skip) when actual_special is NULL"

    def test_policy_a_does_not_skip_non_null_actual_special(self):
        """Policy A: non-null actual_special rows are NOT skipped."""
        for sp in range(1, 9):  # 1..8
            raw = self._make_raw(actual_special=sp)
            result = self._build(raw, "2026-01-01T00:00:00Z")
            assert result is not None, (
                f"Policy A should NOT skip row with actual_special={sp}"
            )

    def test_policy_a_does_not_set_special_hit_0_to_mask_null(self):
        """
        Policy A must SKIP null-special rows, NOT insert them with special_hit=0.
        This test verifies the distinction between Policy A and Policy B.
        """
        raw = self._make_raw(actual_special=None)
        result = self._build(raw, "2026-01-01T00:00:00Z")
        # Policy A returns None — it does NOT produce a row with special_hit=0
        assert result is None, (
            "Policy A must return None (skip), not insert with special_hit=0 (that would be Policy B)"
        )

    def test_produced_row_has_non_null_actual_special(self):
        """Rows produced by Policy A always have actual_special != NULL."""
        raw = self._make_raw(actual_special=5)
        result = self._build(raw, "2026-01-01T00:00:00Z")
        assert result is not None
        assert result["actual_special"] is not None
        assert result["actual_special"] == 5

    def test_produced_row_has_dry_run_0(self):
        """Production rows built by Policy A have dry_run=0."""
        raw = self._make_raw(actual_special=7)
        result = self._build(raw, "2026-01-01T00:00:00Z")
        assert result is not None
        assert result["dry_run"] == 0

    def test_produced_row_truth_level_is_p48_label(self):
        from scripts.p48_powerlotto_wave4_production_apply import TRUTH_LEVEL
        raw = self._make_raw(actual_special=2)
        result = self._build(raw, "2026-01-01T00:00:00Z")
        assert result is not None
        assert result["truth_level"] == TRUTH_LEVEL

    def test_produced_row_special_hit_matches_comparison(self):
        """special_hit = 1 iff predicted_special == actual_special."""
        # pred_sp=3, actual_sp=3 → special_hit=1
        raw = self._make_raw(actual_special=3)
        raw["predicted_special"] = 3
        raw["special_hit"] = 1
        result = self._build(raw, "2026-01-01T00:00:00Z")
        assert result is not None
        assert result["special_hit"] == 1

        # pred_sp=3, actual_sp=5 → special_hit=0
        raw2 = self._make_raw(actual_special=5)
        raw2["predicted_special"] = 3
        raw2["special_hit"] = 0
        result2 = self._build(raw2, "2026-01-01T00:00:00Z")
        assert result2 is not None
        assert result2["special_hit"] == 0

    def test_skip_count_accumulation(self):
        """Simulate 4500 raw rows where some have null actual_special; verify skip_count."""
        from scripts.p48_powerlotto_wave4_production_apply import (
            _build_production_row,
            WAVE4_STRATEGY_IDS,
        )
        now_str = "2026-01-01T00:00:00Z"

        # Simulate: 3 strategies × 10 rows each = 30 total, with 3 nulls (one per strategy)
        raw_rows = []
        for sid in WAVE4_STRATEGY_IDS:
            for i in range(10):
                raw = {
                    "strategy_id": sid,
                    "lottery_type": "POWER_LOTTO",
                    "target_draw": str(1000 + i),
                    "draw_date": "2026-01-01",
                    "prediction_cutoff_date": "2025-12-31",
                    "prediction_generated_at": now_str,
                    "predicted_numbers": [1, 2, 3, 4, 5, 6],
                    "predicted_special": 4,
                    "actual_numbers": [1, 2, 7, 8, 9, 10],
                    "actual_special": None if i == 0 else (i % 8) + 1,  # first row = NULL
                    "hit_numbers": [1, 2],
                    "hit_count": 2,
                    "special_hit": 0,
                    "replay_status": "PREDICTED",
                    "reject_reason": None,
                    "history_cutoff_draw": str(999 + i),
                    "strategy_name": "Test", "strategy_version": "v0.1",
                }
                raw_rows.append(raw)

        prod_rows = []
        skip_count = 0
        for raw in raw_rows:
            built = _build_production_row(raw, now_str)
            if built is None:
                skip_count += 1
            else:
                prod_rows.append(built)

        # 3 strategies × 1 null each = 3 skipped
        assert skip_count == 3, f"Expected 3 skips, got {skip_count}"
        assert len(prod_rows) == 27, f"Expected 27 inserted, got {len(prod_rows)}"

        # No prod_row should have actual_special=NULL
        for r in prod_rows:
            assert r["actual_special"] is not None, "Policy A violated: NULL actual_special in prod row"


# ─── Integration: manifest skip_count ────────────────────────────────────────

class TestManifestSkipCount:
    """Verify manifest records the Policy A skip_count."""

    def test_manifest_has_skip_count(self):
        if not MANIFEST_PATH.exists():
            pytest.skip("P48 manifest not found")
        manifest = json.loads(MANIFEST_PATH.read_text())
        assert "skip_count" in manifest, "Manifest missing 'skip_count'"
        assert isinstance(manifest["skip_count"], int), "skip_count must be int"

    def test_manifest_skip_count_is_zero(self):
        """
        All POWER_LOTTO draws have non-null specials (verified by pre-flight).
        Expected skip_count = 0.
        """
        if not MANIFEST_PATH.exists():
            pytest.skip("P48 manifest not found")
        manifest = json.loads(MANIFEST_PATH.read_text())
        sc = manifest["skip_count"]
        assert sc == 0, (
            f"Expected skip_count=0 (all POWER_LOTTO draws have non-null specials), got {sc}"
        )

    def test_manifest_inserted_equals_4500_minus_skips(self):
        if not MANIFEST_PATH.exists():
            pytest.skip("P48 manifest not found")
        manifest = json.loads(MANIFEST_PATH.read_text())
        expected_inserted = 4500 - manifest["skip_count"]
        assert manifest["inserted"] == expected_inserted, (
            f"inserted={manifest['inserted']} expected {expected_inserted}"
        )

    def test_manifest_special_null_policy_documented(self):
        if not MANIFEST_PATH.exists():
            pytest.skip("P48 manifest not found")
        manifest = json.loads(MANIFEST_PATH.read_text())
        assert "special_null_policy" in manifest
        policy_str = manifest["special_null_policy"]
        assert "Policy A" in policy_str or "policy_a" in policy_str.lower()
        assert "skip" in policy_str.lower(), (
            f"Policy A description must mention 'skip': {policy_str}"
        )


# ─── Integration: production DB (post-apply) ─────────────────────────────────

class TestProductionDBNullPolicy:
    """
    Verify that no NULL actual_special rows were inserted into production DB.
    Requires production DB (skipped if not available).
    """

    @pytest.fixture(autouse=True)
    def require_db(self):
        if not PROD_DB_PATH.exists():
            pytest.skip("Production DB not found")

    def _conn(self):
        return sqlite3.connect(str(PROD_DB_PATH))

    def test_no_null_actual_special_in_p48_rows(self):
        """Policy A: zero P48 rows with actual_special=NULL in production."""
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND actual_special IS NULL",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 0, (
            f"Found {n} P48 rows with actual_special=NULL in production. "
            "Policy A should have skipped these."
        )

    def test_all_p48_actual_special_in_valid_range(self):
        """All P48 rows must have actual_special in [1, 8]."""
        conn = self._conn()
        try:
            n_invalid = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND (actual_special < 1 OR actual_special > 8)",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n_invalid == 0, (
            f"Found {n_invalid} P48 rows with actual_special outside [1,8]"
        )

    def test_p48_rows_have_correct_special_hit_semantics(self):
        """
        Spot-check: special_hit must equal (predicted_special == actual_special).
        Tests up to 200 rows.
        """
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT predicted_special, actual_special, special_hit "
                "FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND replay_status='PREDICTED' LIMIT 200",
                (CONTROLLED_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            pytest.skip("No P48 PREDICTED rows found")

        errors = []
        for i, row in enumerate(rows):
            ps = row["predicted_special"]
            as_ = row["actual_special"]
            sh = row["special_hit"]
            if ps is not None and as_ is not None:
                expected = 1 if int(ps) == int(as_) else 0
                if sh != expected:
                    errors.append(
                        f"Row {i}: predicted_special={ps} actual_special={as_} "
                        f"special_hit={sh} expected={expected}"
                    )

        assert not errors, f"special_hit semantics errors:\n" + "\n".join(errors[:10])
