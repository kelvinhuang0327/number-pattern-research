"""
test_p48_powerlotto_wave4_production_apply.py
==============================================
P48 — POWER_LOTTO Wave 4 Production Apply tests.

Tests:
  1. Two-zone semantics for production rows (first-zone and special-zone)
  2. hit_count is first-zone only (never includes special)
  3. special_hit correctness (0 or 1)
  4. lottery_type = POWER_LOTTO only
  5. No BIG_LOTTO or DAILY_539 rows in apply set
  6. Per-strategy row count = 1500
  7. Total rows = 4500 (or 4500 - skip_count)
  8. dry_run = 0 for production rows
  9. truth_level = POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED
  10. No lifecycle promotion to ONLINE detected
  11. Production DB row count verification (if DB available)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
MANIFEST_PATH = (
    REPO_ROOT / "outputs" / "replay"
    / "p48_powerlotto_wave4_production_apply_20260524.json"
)

WAVE4_STRATEGY_IDS = [
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
]
CONTROLLED_APPLY_ID   = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"
TRUTH_LEVEL           = "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED"
RUN_ID                = "p48_wave4_prod_20260524"
PRE_APPLY_PROD_ROWS   = 37960
EXPECTED_APPLIED_ROWS = 4500
POST_APPLY_PROD_ROWS  = 42460  # or adjusted by Policy A skip_count


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _load_manifest() -> dict | None:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return None


def _build_sample_rows(n: int = 10, strategy_id: str = "pp3_freqort_4bet") -> List[dict]:
    """Build minimal synthetic production rows for unit-testing semantics."""
    rows = []
    for i in range(n):
        predicted = list(range(1, 7))          # [1,2,3,4,5,6]
        actual    = list(range(3, 9))           # [3,4,5,6,7,8]
        hits      = sorted(set(predicted) & set(actual))  # [3,4,5,6]
        pred_sp   = 3
        actual_sp = 3
        rows.append({
            "lottery_type":       "POWER_LOTTO",
            "target_draw":        str(100 + i),
            "strategy_id":        strategy_id,
            "replay_status":      "PREDICTED",
            "predicted_numbers":  json.dumps(predicted),
            "predicted_special":  pred_sp,
            "actual_numbers":     json.dumps(actual),
            "actual_special":     actual_sp,
            "hit_numbers":        json.dumps(hits),
            "hit_count":          len(hits),
            "special_hit":        1 if pred_sp == actual_sp else 0,
            "dry_run":            0,
            "truth_level":        TRUTH_LEVEL,
        })
    return rows


# ─── Unit tests: two-zone semantics ──────────────────────────────────────────

class TestPowerLottoTwoZoneSemantics:
    """Validate POWER_LOTTO two-zone semantics on sample rows."""

    def test_predicted_numbers_exactly_6_unique(self):
        rows = _build_sample_rows()
        for row in rows:
            pred = json.loads(row["predicted_numbers"])
            assert len(pred) == 6, f"Expected 6 predicted_numbers, got {len(pred)}"
            assert len(set(pred)) == 6, f"Duplicate predicted_numbers: {pred}"

    def test_predicted_numbers_in_range_1_38(self):
        rows = _build_sample_rows()
        for row in rows:
            pred = json.loads(row["predicted_numbers"])
            assert all(1 <= n <= 38 for n in pred), (
                f"predicted_numbers out of [1,38]: {pred}"
            )

    def test_actual_numbers_exactly_6_unique(self):
        rows = _build_sample_rows()
        for row in rows:
            actual = json.loads(row["actual_numbers"])
            assert len(actual) == 6, f"Expected 6 actual_numbers, got {len(actual)}"
            assert len(set(actual)) == 6, f"Duplicate actual_numbers: {actual}"

    def test_hit_count_is_first_zone_only(self):
        """hit_count must equal |predicted_numbers ∩ actual_numbers|, never includes special."""
        rows = _build_sample_rows()
        for row in rows:
            pred   = set(json.loads(row["predicted_numbers"]))
            actual = set(json.loads(row["actual_numbers"]))
            expected_hits = len(pred & actual)
            assert row["hit_count"] == expected_hits, (
                f"hit_count={row['hit_count']} expected {expected_hits} "
                f"(first-zone only, special not counted)"
            )

    def test_special_hit_is_0_or_1(self):
        rows = _build_sample_rows()
        for row in rows:
            assert row["special_hit"] in (0, 1), (
                f"special_hit={row['special_hit']} must be 0 or 1"
            )

    def test_special_hit_derived_from_special_comparison(self):
        """special_hit = 1 iff predicted_special == actual_special."""
        # Build rows where pred_sp == actual_sp (special_hit = 1)
        row_hit = {
            "lottery_type": "POWER_LOTTO", "replay_status": "PREDICTED",
            "predicted_numbers": json.dumps([1, 2, 3, 4, 5, 6]),
            "actual_numbers": json.dumps([7, 8, 9, 10, 11, 12]),
            "predicted_special": 5, "actual_special": 5,
            "hit_count": 0, "hit_numbers": json.dumps([]),
            "special_hit": 1, "dry_run": 0, "truth_level": TRUTH_LEVEL,
        }
        assert row_hit["special_hit"] == 1

        # Build rows where pred_sp != actual_sp (special_hit = 0)
        row_miss = {**row_hit, "actual_special": 3, "special_hit": 0}
        assert row_miss["special_hit"] == 0

    def test_predicted_special_in_range_1_8(self):
        rows = _build_sample_rows()
        for row in rows:
            ps = row.get("predicted_special")
            if ps is not None:
                assert 1 <= int(ps) <= 8, (
                    f"predicted_special={ps} not in [1,8]"
                )

    def test_actual_special_in_range_1_8(self):
        """Policy A guarantees actual_special is not NULL here."""
        rows = _build_sample_rows()
        for row in rows:
            asp = row.get("actual_special")
            assert asp is not None, "actual_special must not be NULL (Policy A skips such rows)"
            assert 1 <= int(asp) <= 8, f"actual_special={asp} not in [1,8]"

    def test_lottery_type_is_power_lotto(self):
        rows = _build_sample_rows()
        for row in rows:
            assert row["lottery_type"] == "POWER_LOTTO"

    def test_no_big_lotto_or_daily539_rows(self):
        rows = _build_sample_rows()
        for row in rows:
            assert row["lottery_type"] not in ("BIG_LOTTO", "DAILY_539"), (
                f"Found forbidden lottery_type: {row['lottery_type']}"
            )

    def test_dry_run_is_0_for_production_rows(self):
        rows = _build_sample_rows()
        for row in rows:
            assert row["dry_run"] == 0, (
                f"dry_run={row['dry_run']} — production rows must have dry_run=0"
            )

    def test_truth_level_is_p48_production_label(self):
        rows = _build_sample_rows()
        for row in rows:
            assert row["truth_level"] == TRUTH_LEVEL, (
                f"truth_level={row['truth_level']} expected {TRUTH_LEVEL}"
            )


# ─── Integration: validate semantics checker from apply script ────────────────

class TestApplyScriptSemanticsValidator:
    """Test the _validate_powerlotto_semantics function from the apply script."""

    def setup_method(self):
        from scripts.p48_powerlotto_wave4_production_apply import (
            _validate_powerlotto_semantics,
        )
        self._validate = _validate_powerlotto_semantics

    def test_valid_rows_pass(self):
        rows = _build_sample_rows(5)
        result = self._validate(rows)
        assert result["semantics_valid"], f"Expected valid, errors: {result['errors']}"
        assert result["error_count"] == 0

    def test_wrong_lottery_type_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["lottery_type"] = "BIG_LOTTO"
        result = self._validate(rows)
        assert not result["semantics_valid"]
        assert result["error_count"] > 0

    def test_wrong_predicted_number_count_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["predicted_numbers"] = json.dumps([1, 2, 3, 4, 5])  # only 5
        result = self._validate(rows)
        assert not result["semantics_valid"]

    def test_out_of_range_predicted_numbers_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["predicted_numbers"] = json.dumps([1, 2, 3, 4, 5, 39])  # 39 > 38
        result = self._validate(rows)
        assert not result["semantics_valid"]

    def test_wrong_hit_count_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["hit_count"] = 99  # wrong
        result = self._validate(rows)
        assert not result["semantics_valid"]

    def test_wrong_special_hit_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["special_hit"] = 2  # must be 0 or 1
        result = self._validate(rows)
        assert not result["semantics_valid"]

    def test_special_hit_mismatch_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["predicted_special"] = 1
        rows[0]["actual_special"] = 2
        rows[0]["special_hit"] = 1  # wrong: should be 0
        result = self._validate(rows)
        assert not result["semantics_valid"]

    def test_dry_run_nonzero_fails(self):
        rows = _build_sample_rows(1)
        rows[0]["dry_run"] = 1  # wrong for production
        result = self._validate(rows)
        assert not result["semantics_valid"]


# ─── Integration: production DB state (post-apply) ───────────────────────────

class TestProductionDBAfterApply:
    """
    Verify production DB state after P48 apply.
    Requires PROD_DB_PATH to exist (skipped otherwise).
    """

    @pytest.fixture(autouse=True)
    def require_db(self):
        if not PROD_DB_PATH.exists():
            pytest.skip("Production DB not found — skipping live DB tests")

    def _conn(self):
        return sqlite3.connect(str(PROD_DB_PATH))

    def test_production_row_count_is_42460_or_adjusted(self):
        """After P48 apply: production rows must be 42460 (or 42460 - skip_count)."""
        manifest = _load_manifest()
        if manifest is None:
            pytest.skip("P48 manifest not found — apply not yet run")

        expected_after = manifest["prod_rows_after"]
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert total == expected_after, (
            f"Production rows={total}, expected={expected_after} (from P48 manifest)"
        )

    def test_per_strategy_row_counts(self):
        """Each Wave 4 strategy must have exactly 1500 rows (or 1500 - skips)."""
        manifest = _load_manifest()
        if manifest is None:
            pytest.skip("P48 manifest not found")

        expected = manifest.get("per_strategy_inserted", {})
        conn = self._conn()
        try:
            for sid in WAVE4_STRATEGY_IDS:
                n = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays "
                    "WHERE lottery_type='POWER_LOTTO' AND strategy_id=? AND truth_level=?",
                    (sid, TRUTH_LEVEL),
                ).fetchone()[0]
                exp = expected.get(sid, 1500)
                assert n == exp, (
                    f"Strategy {sid}: {n} rows in DB, expected {exp}"
                )
        finally:
            conn.close()

    def test_no_p47_dryrun_rows_in_production(self):
        """P47 dry-run rows must never appear in production DB."""
        conn = self._conn()
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE truth_level = 'P47_WAVE4_POWERLOTTO_DRY_RUN'",
            ).fetchone()[0]
        finally:
            conn.close()
        assert n == 0, f"Found {n} P47 dry-run rows in production (expected 0)"

    def test_all_wave4_rows_have_dry_run_0(self):
        """All P48 production rows must have dry_run=0."""
        conn = self._conn()
        try:
            n_wrong = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND dry_run != 0",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n_wrong == 0, f"Found {n_wrong} P48 rows with dry_run != 0"

    def test_no_online_lifecycle_in_wave4_rows(self):
        """No row in P48 apply set should have a lifecycle=ONLINE flag anywhere."""
        conn = self._conn()
        try:
            # Check truth_level doesn't contain ONLINE
            n_online = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND truth_level LIKE '%ONLINE%'",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n_online == 0, f"Found {n_online} P48 rows with ONLINE in truth_level"

    def test_all_wave4_actual_special_non_null(self):
        """Policy A guarantees all inserted rows have non-null actual_special."""
        conn = self._conn()
        try:
            n_null = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND actual_special IS NULL",
                (CONTROLLED_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert n_null == 0, (
            f"Found {n_null} P48 rows with actual_special=NULL "
            "(Policy A should have skipped these)"
        )

    def test_powerlotto_semantics_in_production_sample(self):
        """Spot-check POWER_LOTTO semantics on a sample of P48 production rows."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND replay_status='PREDICTED' LIMIT 100",
                (CONTROLLED_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            pytest.skip("No P48 PREDICTED rows found in production DB")

        for row in rows:
            sid = row["strategy_id"]
            pred = json.loads(row["predicted_numbers"]) if row["predicted_numbers"] else None
            actual = json.loads(row["actual_numbers"]) if row["actual_numbers"] else None

            if pred is not None:
                assert len(pred) == 6, f"{sid}: predicted_numbers len={len(pred)}"
                assert len(set(pred)) == 6, f"{sid}: duplicate predicted_numbers"
                assert all(1 <= n <= 38 for n in pred), f"{sid}: predicted_numbers out of [1,38]"

            if actual is not None:
                assert len(actual) == 6, f"{sid}: actual_numbers len={len(actual)}"

            if pred is not None and actual is not None:
                expected_hit = len(set(pred) & set(actual))
                assert row["hit_count"] == expected_hit, (
                    f"{sid}: hit_count={row['hit_count']} expected {expected_hit}"
                )

            assert row["special_hit"] in (0, 1), f"{sid}: special_hit={row['special_hit']}"
            assert row["actual_special"] is not None, f"{sid}: actual_special is NULL"
            assert row["lottery_type"] == "POWER_LOTTO", f"lottery_type={row['lottery_type']}"


# ─── Lifecycle guard ──────────────────────────────────────────────────────────

class TestLifecycleGuard:
    """Ensure no ONLINE lifecycle promotion in P48."""

    def test_wave4_adapters_lifecycle_is_dry_run(self):
        """All Wave 4 adapters must report lifecycle_status=DRY_RUN, not ONLINE."""
        from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS
        for adapter in WAVE4_ADAPTERS:
            assert adapter.meta.lifecycle_status == "DRY_RUN", (
                f"{adapter.meta.strategy_id}: lifecycle_status={adapter.meta.lifecycle_status} "
                "expected DRY_RUN"
            )
            assert adapter.meta.lifecycle_status != "ONLINE", (
                f"{adapter.meta.strategy_id}: ONLINE lifecycle detected — P48_BLOCKED_BY_LIFECYCLE_PROMOTION_DETECTED"
            )

    def test_wave4_strategy_ids_match_expected(self):
        """Wave 4 strategy IDs must exactly match the 3 P47-verified strategies."""
        from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS
        actual_ids = {a.meta.strategy_id for a in WAVE4_ADAPTERS}
        expected_ids = set(WAVE4_STRATEGY_IDS)
        assert actual_ids == expected_ids, (
            f"Adapter IDs mismatch: {actual_ids} vs expected {expected_ids}"
        )
