"""
test_p49_powerlotto_post_apply_api_verification.py
====================================================
P49  — POWER_LOTTO Post-Apply API/UI Verification

Verifies that the 4500 P48 POWER_LOTTO production rows are:
  1. Correctly stored in the production DB (42 460 total, 3 × 1500 by strategy)
  2. Queryable through the replay API (history, summary)
  3. Semantically correct (lottery_type, number ranges, special, hit_count, dry_run)

CONTRACT:
  - READ-ONLY.  No DB writes, no lifecycle promotion.
  - Must run against the live production DB at lottery_api/data/lottery_v2.db
  - No live HTTP server required — API route functions are called directly.

Classification target: P49_POWERLOTTO_POST_APPLY_API_UI_VERIFICATION_PASS
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Paths & sys.path
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
DB_PATH     = LOTTERY_API / "data" / "lottery_v2.db"

sys.path.insert(0, str(LOTTERY_API))

from routes.replay import (
    get_replay_history,
    get_replay_summary,
)

# ---------------------------------------------------------------------------
# Constants — must match P48 apply script exactly
# ---------------------------------------------------------------------------
P48_APPLY_ID       = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"
P48_TRUTH_LEVEL    = "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED"
P48_REPLAY_RUN_ID  = "p48_wave4_prod_20260524"
P48_LOTTERY_TYPE   = "POWER_LOTTO"
P48_STRATEGIES     = ["pp3_freqort_4bet", "midfreq_fourier_mk_3bet", "midfreq_fourier_2bet"]
P48_ROWS_PER_STRAT = 1500
P48_TOTAL_ROWS     = 4500
EXPECTED_PROD_ROWS = 42460

# POWER_LOTTO ball ranges
MAIN_NUMBERS_COUNT = 6
MAIN_MIN, MAIN_MAX = 1, 38
SPEC_MIN,  SPEC_MAX  = 1, 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run(coro):
    """Run an async route function synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _history(
    lottery_type: str,
    strategy_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    return _run(get_replay_history(
        lottery_type=lottery_type,
        strategy_id=strategy_id,
        replay_status=None,
        lifecycle_status=None,
        fixture_mode=False,
        date_from=None,
        date_to=None,
        page=page,
        page_size=page_size,
    ))


def _summary(lottery_type: str) -> Dict[str, Any]:
    return _run(get_replay_summary(
        lottery_type=lottery_type,
        strategy_id=None,
        lifecycle_status=None,
        date_from=None,
        date_to=None,
    ))


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------
_DB_MISSING = not DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(_DB_MISSING, reason="Production DB not found")


# ===========================================================================
# 1 — DB read-only checks
# ===========================================================================
@_skip_no_db
class TestP49DBCounts:
    """Verify row counts in the production DB match P48 apply manifest."""

    def test_total_production_rows_is_42460(self):
        conn = _open_db()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert total == EXPECTED_PROD_ROWS, (
            f"Expected {EXPECTED_PROD_ROWS} total rows, got {total}"
        )

    def test_p48_apply_id_row_count_is_4500(self):
        conn = _open_db()
        try:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert cnt == P48_TOTAL_ROWS, (
            f"P48 controlled_apply_id rows: expected {P48_TOTAL_ROWS}, got {cnt}"
        )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_per_strategy_row_count_is_1500(self, strategy_id):
        conn = _open_db()
        try:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND strategy_id=?",
                (P48_APPLY_ID, strategy_id),
            ).fetchone()[0]
        finally:
            conn.close()
        assert cnt == P48_ROWS_PER_STRAT, (
            f"{strategy_id}: expected {P48_ROWS_PER_STRAT} rows, got {cnt}"
        )

    def test_p48_rows_are_all_power_lotto(self):
        conn = _open_db()
        try:
            non_pl = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND lottery_type != ?",
                (P48_APPLY_ID, P48_LOTTERY_TYPE),
            ).fetchone()[0]
        finally:
            conn.close()
        assert non_pl == 0, (
            f"Found {non_pl} P48 rows with lottery_type != POWER_LOTTO"
        )

    def test_p48_rows_no_null_actual_special(self):
        conn = _open_db()
        try:
            null_cnt = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND actual_special IS NULL",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert null_cnt == 0, (
            f"Found {null_cnt} P48 rows with NULL actual_special"
        )

    def test_p48_rows_dry_run_is_zero(self):
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND dry_run != 0",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, f"Found {bad} P48 rows with dry_run != 0"

    def test_p48_truth_level(self):
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND truth_level != ?",
                (P48_APPLY_ID, P48_TRUTH_LEVEL),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, (
            f"Found {bad} P48 rows with unexpected truth_level"
        )

    def test_p48_replay_run_id(self):
        conn = _open_db()
        try:
            # replay_run_id column stores p48_wave4_prod_20260524
            # Column name in schema: replay_run_id (text, stores the string run_id)
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND replay_run_id != ?",
                (P48_APPLY_ID, P48_REPLAY_RUN_ID),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, (
            f"Found {bad} P48 rows with unexpected replay_run_id"
        )


# ===========================================================================
# 2 — DB semantic checks (number ranges, special_hit correctness)
# ===========================================================================
@_skip_no_db
class TestP49DBSemantics:
    """Verify POWER_LOTTO two-zone semantics for P48 rows."""

    def test_actual_numbers_in_main_range(self):
        """All actual_numbers values must be in [1, 38]."""
        conn = _open_db()
        try:
            rows = conn.execute(
                "SELECT actual_numbers FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=?",
                (P48_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()
        out_of_range = 0
        for r in rows:
            nums: List[int] = json.loads(r["actual_numbers"])
            if any(n < MAIN_MIN or n > MAIN_MAX for n in nums):
                out_of_range += 1
        assert out_of_range == 0, (
            f"{out_of_range} rows have actual_numbers outside [{MAIN_MIN},{MAIN_MAX}]"
        )

    def test_predicted_numbers_in_main_range(self):
        """All predicted_numbers values must be in [1, 38]."""
        conn = _open_db()
        try:
            rows = conn.execute(
                "SELECT predicted_numbers FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=?",
                (P48_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()
        out_of_range = 0
        for r in rows:
            nums: List[int] = json.loads(r["predicted_numbers"])
            if any(n < MAIN_MIN or n > MAIN_MAX for n in nums):
                out_of_range += 1
        assert out_of_range == 0, (
            f"{out_of_range} rows have predicted_numbers outside [{MAIN_MIN},{MAIN_MAX}]"
        )

    def test_predicted_numbers_count_is_6(self):
        """Every predicted_numbers list must have exactly 6 elements."""
        conn = _open_db()
        try:
            rows = conn.execute(
                "SELECT predicted_numbers FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=?",
                (P48_APPLY_ID,),
            ).fetchall()
        finally:
            conn.close()
        wrong_len = 0
        for r in rows:
            nums = json.loads(r["predicted_numbers"])
            if len(nums) != MAIN_NUMBERS_COUNT:
                wrong_len += 1
        assert wrong_len == 0, (
            f"{wrong_len} rows have predicted_numbers length != {MAIN_NUMBERS_COUNT}"
        )

    def test_actual_special_in_special_range(self):
        """All actual_special values must be in [1, 8]."""
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? "
                "AND (actual_special < ? OR actual_special > ?)",
                (P48_APPLY_ID, SPEC_MIN, SPEC_MAX),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, (
            f"{bad} rows have actual_special outside [{SPEC_MIN},{SPEC_MAX}]"
        )

    def test_hit_count_at_most_6(self):
        """hit_count must never exceed 6 (first-zone only)."""
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND hit_count > ?",
                (P48_APPLY_ID, MAIN_NUMBERS_COUNT),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, (
            f"{bad} rows have hit_count > {MAIN_NUMBERS_COUNT} (first-zone violation)"
        )

    def test_special_hit_correctness(self):
        """special_hit must equal 1 iff predicted_special == actual_special."""
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? "
                "AND special_hit != "
                "CASE WHEN predicted_special = actual_special THEN 1 ELSE 0 END",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, (
            f"{bad} rows have incorrect special_hit (≠ predicted==actual)"
        )

    def test_special_hit_is_0_or_1(self):
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND special_hit NOT IN (0, 1)",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, f"{bad} rows have special_hit not in {{0, 1}}"

    def test_hit_count_is_nonnegative(self):
        conn = _open_db()
        try:
            bad = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE controlled_apply_id=? AND hit_count < 0",
                (P48_APPLY_ID,),
            ).fetchone()[0]
        finally:
            conn.close()
        assert bad == 0, f"{bad} rows have negative hit_count"


# ===========================================================================
# 3 — API history endpoint checks
# ===========================================================================
@_skip_no_db
class TestP49APIHistory:
    """Verify /api/replay/history returns P48 rows with correct shape."""

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_total_is_1500_per_strategy(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=1)
        total = data.get("total")
        assert total == P48_ROWS_PER_STRAT, (
            f"{strategy_id}: history total={total}, expected {P48_ROWS_PER_STRAT}"
        )

    def test_history_power_lotto_total_includes_p48(self):
        """Total POWER_LOTTO rows must be >= 4500 (the P48 batch)."""
        data = _history(P48_LOTTERY_TYPE, page_size=1)
        total = data.get("total", 0)
        assert total >= P48_TOTAL_ROWS, (
            f"POWER_LOTTO history total={total} < {P48_TOTAL_ROWS}"
        )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_have_required_fields(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=5)
        records = data.get("records", [])
        assert len(records) > 0, f"{strategy_id}: no records returned"
        for rec in records:
            for field in (
                "strategy_id",
                "lottery_type",
                "predicted_numbers",
                "actual_numbers",
                "predicted_special",
                "actual_special",
                "hit_count",
                "special_hit",
            ):
                assert field in rec, (
                    f"{strategy_id}: record missing field {field!r}"
                )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_lottery_type_is_power_lotto(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=10)
        records = data.get("records", [])
        for rec in records:
            lt = rec.get("lottery_type") or rec.get("lottery")
            assert lt == P48_LOTTERY_TYPE, (
                f"{strategy_id}: record lottery_type={lt!r}, expected {P48_LOTTERY_TYPE!r}"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_predicted_numbers_is_list(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=5)
        records = data.get("records", [])
        for rec in records:
            pn = rec.get("predicted_numbers")
            assert isinstance(pn, list), (
                f"{strategy_id}: predicted_numbers is not a list: {pn!r}"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_actual_numbers_is_list(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=5)
        records = data.get("records", [])
        for rec in records:
            an = rec.get("actual_numbers")
            assert isinstance(an, list), (
                f"{strategy_id}: actual_numbers is not a list: {an!r}"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_hit_count_is_nonneg_int(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=20)
        records = data.get("records", [])
        for rec in records:
            hc = rec.get("hit_count")
            assert isinstance(hc, int), (
                f"{strategy_id}: hit_count is not int: {hc!r}"
            )
            assert hc >= 0, f"{strategy_id}: hit_count={hc} < 0"

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_hit_count_at_most_6(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=20)
        records = data.get("records", [])
        for rec in records:
            hc = rec.get("hit_count", 0)
            assert hc <= MAIN_NUMBERS_COUNT, (
                f"{strategy_id}: hit_count={hc} > {MAIN_NUMBERS_COUNT} (first-zone only)"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_special_hit_is_0_or_1(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=20)
        records = data.get("records", [])
        for rec in records:
            sh = rec.get("special_hit")
            assert sh in (0, 1), (
                f"{strategy_id}: special_hit={sh!r} not in {{0, 1}}"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_history_records_actual_special_not_null(self, strategy_id):
        data = _history(P48_LOTTERY_TYPE, strategy_id=strategy_id, page_size=20)
        records = data.get("records", [])
        for rec in records:
            asp = rec.get("actual_special")
            assert asp is not None, (
                f"{strategy_id}: actual_special is None (NULL actual_special violation)"
            )

    def test_history_pagination_page_size_respected(self):
        data = _history(P48_LOTTERY_TYPE, strategy_id=P48_STRATEGIES[0], page_size=10)
        assert len(data.get("records", [])) <= 10

    def test_history_page2_distinct_from_page1(self):
        sid = P48_STRATEGIES[0]
        p1 = _history(P48_LOTTERY_TYPE, strategy_id=sid, page=1, page_size=5)
        p2 = _history(P48_LOTTERY_TYPE, strategy_id=sid, page=2, page_size=5)
        ids1 = {r.get("id") for r in p1.get("records", [])}
        ids2 = {r.get("id") for r in p2.get("records", [])}
        overlap = ids1 & ids2
        assert len(overlap) == 0, f"Pagination overlap between page 1 and 2: {overlap}"

    def test_history_no_cross_lottery_contamination(self):
        """POWER_LOTTO query must not return BIG_LOTTO or DAILY_539 rows."""
        data = _history(P48_LOTTERY_TYPE, page_size=200)
        records = data.get("records", [])
        for rec in records:
            lt = rec.get("lottery_type") or rec.get("lottery")
            assert lt == P48_LOTTERY_TYPE, (
                f"Cross-lottery contamination: lottery_type={lt!r}"
            )


# ===========================================================================
# 4 — API summary endpoint checks
# ===========================================================================
@_skip_no_db
class TestP49APISummary:
    """Verify /api/replay/summary includes all 3 P48 strategies."""

    def test_summary_returns_dict(self):
        assert isinstance(_summary(P48_LOTTERY_TYPE), dict)

    def test_summary_has_summaries_list(self):
        data = _summary(P48_LOTTERY_TYPE)
        assert isinstance(data.get("summaries"), list)

    def test_summary_all_p48_strategies_present(self):
        data = _summary(P48_LOTTERY_TYPE)
        found_ids = {s["strategy_id"] for s in data.get("summaries", [])}
        for sid in P48_STRATEGIES:
            assert sid in found_ids, (
                f"P48 strategy {sid!r} missing from /api/replay/summary"
            )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_summary_per_strategy_total_rows_is_1500(self, strategy_id):
        data = _summary(P48_LOTTERY_TYPE)
        summaries = {s["strategy_id"]: s for s in data.get("summaries", [])}
        assert strategy_id in summaries, f"{strategy_id} not in summaries"
        total_rows = summaries[strategy_id].get("total_rows")
        assert total_rows == P48_ROWS_PER_STRAT, (
            f"{strategy_id}: summary total_rows={total_rows}, expected {P48_ROWS_PER_STRAT}"
        )

    @pytest.mark.parametrize("strategy_id", P48_STRATEGIES)
    def test_summary_per_strategy_error_count_is_zero(self, strategy_id):
        data = _summary(P48_LOTTERY_TYPE)
        summaries = {s["strategy_id"]: s for s in data.get("summaries", [])}
        if strategy_id in summaries:
            ec = summaries[strategy_id].get("error_count", 0)
            assert ec == 0, f"{strategy_id}: error_count={ec} (expected 0)"


# ===========================================================================
# 5 — No DB writes guard (row count must not change during tests)
# ===========================================================================
@_skip_no_db
class TestP49NoDBWrites:
    """Guard that running the P49 test suite does not modify the production DB."""

    def _row_count(self) -> int:
        conn = _open_db()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()

    def test_row_count_unchanged_after_history_calls(self):
        before = self._row_count()
        for sid in P48_STRATEGIES:
            _history(P48_LOTTERY_TYPE, strategy_id=sid, page_size=10)
        after = self._row_count()
        assert after == before, (
            f"DB row count changed during read-only tests: {before} → {after}"
        )

    def test_row_count_unchanged_after_summary_calls(self):
        before = self._row_count()
        _summary(P48_LOTTERY_TYPE)
        after = self._row_count()
        assert after == before, (
            f"DB row count changed during summary calls: {before} → {after}"
        )

    def test_total_rows_is_still_42460(self):
        assert self._row_count() == EXPECTED_PROD_ROWS, (
            f"Production DB total row count is not {EXPECTED_PROD_ROWS}"
        )
