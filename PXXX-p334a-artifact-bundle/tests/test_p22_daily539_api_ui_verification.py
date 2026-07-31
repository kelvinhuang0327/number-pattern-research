"""
test_p22_daily539_api_ui_verification.py
=========================================
P22 — DAILY_539 API/UI Verification

Read-only verification that:
1. Production DB row count is unchanged at 12460.
2. DAILY_539 per-strategy verified row counts (daily539_f4cold, daily539_markov_cold) ≥ 1500.
3. All required DAILY_539 field semantics are correct (5-number, no-special, timestamps, hit_count).
4. API endpoint GET /api/replay/history?lottery_type=DAILY_539 returns correct fields.
5. Per-strategy API filters work for both DAILY_539 strategies.
6. Pagination works correctly at 12460-row DB scale.
7. UI data-model: predicted_special is NULL → rpSpecialChip not called → no misleading 6th number.
8. CEO-level opportunistic observations recorded in outputs/replay/p22_daily539_api_ui_verification_20260521.json.

Branch: p22-daily539-api-ui-verification
Authorization: YES create new branch for P22 DAILY_539 API UI verification
Date: 2026-05-21
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT  = Path(__file__).resolve().parents[1]
_API_ROOT   = _REPO_ROOT / "lottery_api"
_PROD_DB    = _API_ROOT / "data" / "lottery_v2.db"
_OUTPUT_JSON = _REPO_ROOT / "outputs" / "replay" / "p22_daily539_api_ui_verification_20260521.json"
_INDEX_HTML  = _REPO_ROOT / "index.html"

if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from routes.replay import get_replay_history, get_replay_summary


# ── helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
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
):
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


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_PROD_DB))
    conn.row_factory = sqlite3.Row
    return conn


PROD_ROW_TOTAL      = 12460
F4COLD_ID           = "daily539_f4cold"
MARKOV_ID           = "daily539_markov_cold"
TRUTH_VERIFIED      = "DAILY539_BACKFILL_VERIFIED"
MIN_VERIFIED_ROWS   = 1500


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Production DB row count guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductionRowCount:
    """Production DB must remain at exactly 12460 before and after all checks."""

    def test_total_rows_12460(self):
        conn = _open_db()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        assert total == PROD_ROW_TOTAL, (
            f"Production row count changed! Expected {PROD_ROW_TOTAL}, got {total}. "
            "STOP — possible DB write contamination."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DAILY_539 per-strategy verified row counts
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyStrategyVerifiedRowCounts:
    """daily539_f4cold and daily539_markov_cold must each have ≥ 1500 verified rows."""

    def _verified_count(self, strategy_id: str) -> int:
        conn = _open_db()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type='DAILY_539' AND strategy_id=? AND truth_level=?",
                (strategy_id, TRUTH_VERIFIED),
            ).fetchone()[0]
        finally:
            conn.close()

    def test_f4cold_verified_rows_ge_1500(self):
        count = self._verified_count(F4COLD_ID)
        assert count >= MIN_VERIFIED_ROWS, (
            f"daily539_f4cold has only {count} DAILY539_BACKFILL_VERIFIED rows; need ≥ {MIN_VERIFIED_ROWS}"
        )

    def test_markov_cold_verified_rows_ge_1500(self):
        count = self._verified_count(MARKOV_ID)
        assert count >= MIN_VERIFIED_ROWS, (
            f"daily539_markov_cold has only {count} DAILY539_BACKFILL_VERIFIED rows; need ≥ {MIN_VERIFIED_ROWS}"
        )

    def test_daily539_total_rows_3180(self):
        conn = _open_db()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='DAILY_539'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert total == 3180, f"Expected 3180 DAILY_539 rows, got {total}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DAILY_539 field contract verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyFieldContracts:
    """Verify DAILY_539 field semantics across all DAILY539_BACKFILL_VERIFIED rows."""

    @pytest.fixture(scope="class")
    def verified_rows(self):
        conn = _open_db()
        try:
            rows = conn.execute(
                """
                SELECT predicted_numbers, actual_numbers, hit_numbers, hit_count,
                       predicted_special, special_hit,
                       prediction_cutoff_date, prediction_generated_at
                FROM strategy_prediction_replays
                WHERE lottery_type='DAILY_539' AND truth_level='DAILY539_BACKFILL_VERIFIED'
                """
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def _parse_json(self, val: Any):
        if val is None:
            return None
        if isinstance(val, list):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None

    def test_verified_rows_count(self, verified_rows):
        assert len(verified_rows) == 3000, (
            f"Expected 3000 verified rows (1500 × 2 strategies), got {len(verified_rows)}"
        )

    def test_predicted_numbers_length_5(self, verified_rows):
        failures = [
            i for i, r in enumerate(verified_rows)
            if len(self._parse_json(r["predicted_numbers"]) or []) != 5
        ]
        assert not failures, (
            f"predicted_numbers length != 5 in {len(failures)} rows (indices: {failures[:10]})"
        )

    def test_actual_numbers_length_5(self, verified_rows):
        failures = [
            i for i, r in enumerate(verified_rows)
            if len(self._parse_json(r["actual_numbers"]) or []) != 5
        ]
        assert not failures, (
            f"actual_numbers length != 5 in {len(failures)} rows (indices: {failures[:10]})"
        )

    def test_hit_count_matches_hit_numbers(self, verified_rows):
        failures = []
        for i, r in enumerate(verified_rows):
            hit_nums = self._parse_json(r["hit_numbers"]) or []
            hit_cnt  = r["hit_count"] or 0
            if len(hit_nums) != hit_cnt:
                failures.append(i)
        assert not failures, (
            f"hit_count != len(hit_numbers) in {len(failures)} rows (indices: {failures[:10]})"
        )

    def test_hit_numbers_are_subset_of_intersection(self, verified_rows):
        """hit_numbers must be a subset of intersection(predicted_numbers, actual_numbers)."""
        failures = []
        for i, r in enumerate(verified_rows):
            pred  = set(self._parse_json(r["predicted_numbers"]) or [])
            act   = set(self._parse_json(r["actual_numbers"]) or [])
            hits  = set(self._parse_json(r["hit_numbers"]) or [])
            inter = pred & act
            if not hits.issubset(inter):
                failures.append(i)
        assert not failures, (
            f"hit_numbers not subset of intersection in {len(failures)} rows (indices: {failures[:10]})"
        )

    def test_predicted_special_null_for_daily_539(self, verified_rows):
        """DAILY_539 has no special number; predicted_special must be NULL."""
        failures = [
            i for i, r in enumerate(verified_rows)
            if r["predicted_special"] is not None and r["predicted_special"] != "" and r["predicted_special"] != 0
        ]
        assert not failures, (
            f"predicted_special is non-null in {len(failures)} DAILY_539 rows (indices: {failures[:10]}). "
            "This would trigger misleading special-number chip in UI."
        )

    def test_special_hit_false_or_zero(self, verified_rows):
        """DAILY_539 has no special number; special_hit must be 0 or NULL."""
        failures = [
            i for i, r in enumerate(verified_rows)
            if r["special_hit"] not in (0, None, False)
        ]
        assert not failures, (
            f"special_hit is non-zero in {len(failures)} DAILY_539 rows (indices: {failures[:10]})"
        )

    def test_prediction_cutoff_date_present(self, verified_rows):
        failures = [
            i for i, r in enumerate(verified_rows)
            if not r["prediction_cutoff_date"]
        ]
        assert not failures, (
            f"prediction_cutoff_date missing in {len(failures)} rows (indices: {failures[:10]})"
        )

    def test_prediction_generated_at_present(self, verified_rows):
        failures = [
            i for i, r in enumerate(verified_rows)
            if not r["prediction_generated_at"]
        ]
        assert not failures, (
            f"prediction_generated_at missing in {len(failures)} rows (indices: {failures[:10]})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API response contract for DAILY_539
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyApiContract:
    """Verify GET /api/replay/history?lottery_type=DAILY_539 response shape and field contract."""

    @pytest.fixture(scope="class")
    def daily539_response(self):
        return _history("DAILY_539", page=1, page_size=50)

    def test_response_has_total(self, daily539_response):
        assert "total" in daily539_response

    def test_response_total_3180(self, daily539_response):
        assert daily539_response["total"] == 3180, (
            f"Expected 3180 DAILY_539 API rows, got {daily539_response['total']}"
        )

    def test_response_has_records(self, daily539_response):
        assert "records" in daily539_response
        assert isinstance(daily539_response["records"], list)
        assert len(daily539_response["records"]) > 0

    def test_records_have_required_fields(self, daily539_response):
        required_keys = {
            "id", "lottery_type", "target_draw", "strategy_id",
            "predicted_numbers", "actual_numbers", "hit_numbers", "hit_count",
            "predicted_special", "special_hit",
            "prediction_cutoff_date", "prediction_generated_at",
        }
        for rec in daily539_response["records"]:
            missing = required_keys - set(rec.keys())
            assert not missing, f"Record missing keys: {missing}. Record id={rec.get('id')}"

    def test_records_lottery_type_is_daily_539(self, daily539_response):
        for rec in daily539_response["records"]:
            assert rec["lottery_type"] == "DAILY_539", (
                f"Record id={rec.get('id')} has lottery_type={rec['lottery_type']!r}"
            )

    def test_records_predicted_numbers_length_5(self, daily539_response):
        failures = [
            rec["id"] for rec in daily539_response["records"]
            if len(rec.get("predicted_numbers") or []) != 5
        ]
        assert not failures, f"predicted_numbers length != 5 for records: {failures}"

    def test_records_actual_numbers_length_5(self, daily539_response):
        failures = [
            rec["id"] for rec in daily539_response["records"]
            if len(rec.get("actual_numbers") or []) != 5
        ]
        assert not failures, f"actual_numbers length != 5 for records: {failures}"

    def test_records_predicted_special_is_null_or_zero(self, daily539_response):
        """predicted_special must be null/0 for DAILY_539 (no special number lottery)."""
        failures = [
            rec["id"] for rec in daily539_response["records"]
            if rec.get("predicted_special") not in (None, 0, "", False)
        ]
        assert not failures, (
            f"predicted_special non-null for records: {failures}. "
            "Would trigger misleading '特' chip in UI."
        )

    def test_records_special_hit_is_zero(self, daily539_response):
        failures = [
            rec["id"] for rec in daily539_response["records"]
            if rec.get("special_hit") not in (0, None, False)
        ]
        assert not failures, f"special_hit non-zero for records: {failures}"

    def test_records_hit_count_matches_hit_numbers(self, daily539_response):
        failures = [
            rec["id"] for rec in daily539_response["records"]
            if len(rec.get("hit_numbers") or []) != (rec.get("hit_count") or 0)
        ]
        assert not failures, f"hit_count mismatch for records: {failures}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Per-strategy API filters
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerStrategyApiFilter:
    """Per-strategy API filters must return only rows for the specified strategy."""

    @pytest.fixture(scope="class")
    def f4cold_response(self):
        return _history("DAILY_539", strategy_id=F4COLD_ID, page_size=200)

    @pytest.fixture(scope="class")
    def markov_response(self):
        return _history("DAILY_539", strategy_id=MARKOV_ID, page_size=200)

    def test_f4cold_total_1590(self, f4cold_response):
        assert f4cold_response["total"] == 1590, (
            f"Expected 1590 f4cold rows (1500 verified + 90 legacy), got {f4cold_response['total']}"
        )

    def test_markov_total_1590(self, markov_response):
        assert markov_response["total"] == 1590, (
            f"Expected 1590 markov_cold rows (1500 verified + 90 legacy), got {markov_response['total']}"
        )

    def test_f4cold_all_records_have_correct_strategy_id(self, f4cold_response):
        for rec in f4cold_response["records"]:
            assert rec["strategy_id"] == F4COLD_ID, (
                f"f4cold filter returned record with strategy_id={rec['strategy_id']!r}"
            )

    def test_markov_all_records_have_correct_strategy_id(self, markov_response):
        for rec in markov_response["records"]:
            assert rec["strategy_id"] == MARKOV_ID, (
                f"markov filter returned record with strategy_id={rec['strategy_id']!r}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Pagination verification
# ═══════════════════════════════════════════════════════════════════════════════

class TestPagination:
    """Pagination must work correctly across all 3180 DAILY_539 rows."""

    def test_first_page_50_records(self):
        resp = _history("DAILY_539", page=1, page_size=50)
        assert len(resp["records"]) == 50

    def test_pages_calculated_correctly(self):
        resp = _history("DAILY_539", page=1, page_size=50)
        assert resp["pages"] == (3180 + 49) // 50  # ceil(3180/50) = 64

    def test_last_page_has_remaining_records(self):
        resp = _history("DAILY_539", page=1, page_size=50)
        pages = resp["pages"]
        last = _history("DAILY_539", page=pages, page_size=50)
        remaining = 3180 % 50
        expected = remaining if remaining else 50
        assert len(last["records"]) == expected, (
            f"Last page has {len(last['records'])} records, expected {expected}"
        )

    def test_page_beyond_total_returns_empty(self):
        resp = _history("DAILY_539", page=9999, page_size=50)
        assert resp["records"] == [], "Page beyond total must return empty records"

    def test_no_duplicate_ids_across_two_pages(self):
        page1 = _history("DAILY_539", page=1, page_size=50)
        page2 = _history("DAILY_539", page=2, page_size=50)
        ids1 = {r["id"] for r in page1["records"]}
        ids2 = {r["id"] for r in page2["records"]}
        overlap = ids1 & ids2
        assert not overlap, f"Duplicate IDs across pages 1 and 2: {overlap}"

    def test_pagination_at_biglotto_scale_12460_rows(self):
        """Verify pagination works for BIG_LOTTO at full 4640 scale (DB is 12460 total)."""
        resp = _history("BIG_LOTTO", page=1, page_size=200)
        assert resp["total"] == 4640, f"Expected 4640 BIG_LOTTO rows, got {resp['total']}"
        assert resp["pages"] == (4640 + 199) // 200

    def test_pagination_total_sum_equals_daily539_total(self):
        """Sum of records across all pages must equal the total count."""
        page_size = 200
        resp_p1 = _history("DAILY_539", page=1, page_size=page_size)
        total_reported = resp_p1["total"]
        pages = resp_p1["pages"]

        # Collect all records over all pages
        all_ids: set[int] = set()
        for p in range(1, pages + 1):
            resp = _history("DAILY_539", page=p, page_size=page_size)
            for r in resp["records"]:
                all_ids.add(r["id"])

        assert len(all_ids) == total_reported, (
            f"Sum of unique IDs across all pages ({len(all_ids)}) != total ({total_reported})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. UI data-model: no misleading special-number display
# ═══════════════════════════════════════════════════════════════════════════════

class TestUIDataModel:
    """
    Verify UI data model correctness for DAILY_539:
    - predicted_special is NULL → rpSpecialChip not called → no '特' chip rendered.
    - History table has no explicit special-number column.
    - rpSpecialChip condition: r.predicted_special != null — NULL is safe.
    """

    def test_ui_index_html_exists(self):
        assert _INDEX_HTML.exists(), f"index.html not found at {_INDEX_HTML}"

    def test_ui_replay_section_contains_daily_539_option(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert 'value="DAILY_539"' in content, "DAILY_539 option missing from replay lottery selector"
        assert "rp-lottery-select" in content, "#rp-lottery-select missing from replay section"

    def test_ui_rpspecialchip_guards_null(self):
        """rpSpecialChip has an (if num == null) null guard - DAILY_539 predicted_special=NULL is safe."""
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "if (num == null) return ''" in content, (
            "rpSpecialChip null guard missing — DAILY_539 NULL predicted_special could render stray '特' chip"
        )

    def test_ui_predicted_special_null_in_db(self):
        """DAILY_539 rows in DB: predicted_special IS NULL (not empty string) → JS null → no chip."""
        conn = _open_db()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type='DAILY_539' AND predicted_special IS NOT NULL"
            ).fetchone()[0]
        finally:
            conn.close()
        assert rows == 0, (
            f"{rows} DAILY_539 rows have non-NULL predicted_special. "
            "These would trigger rpSpecialChip and mislead users with a '特' chip."
        )

    def test_api_predicted_special_is_null_for_daily539(self):
        """API returns predicted_special=null for DAILY_539 records."""
        resp = _history("DAILY_539", page=1, page_size=50)
        non_null = [
            rec["id"] for rec in resp["records"]
            if rec.get("predicted_special") is not None
        ]
        assert not non_null, (
            f"API returned non-null predicted_special for DAILY_539 records: {non_null}. "
            "UI would render stray '特' chip."
        )

    def test_ui_replay_section_has_lottery_selector(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "rp-lottery-select" in content, "Replay section missing lottery_type selector"

    def test_ui_replay_section_has_strategy_selector(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "rp-strategy-select" in content, "Replay section missing strategy selector"

    def test_ui_replay_section_has_date_range_inputs(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "rp-date-from" in content, "Replay section missing date-from input"
        assert "rp-date-to" in content, "Replay section missing date-to input"

    def test_ui_replay_section_has_pagination_controls(self):
        content = _INDEX_HTML.read_text(encoding="utf-8")
        assert "rp-prev-btn" in content, "Replay section missing pagination prev button"
        assert "rp-next-btn" in content, "Replay section missing pagination next button"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Output JSON evidence file
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutputEvidence:
    """Output JSON must exist and contain required evidence fields."""

    def test_output_json_exists(self):
        assert _OUTPUT_JSON.exists(), (
            f"Output JSON not found: {_OUTPUT_JSON}. "
            "Run the verification script to generate evidence."
        )

    def test_output_json_valid(self):
        content = json.loads(_OUTPUT_JSON.read_text(encoding="utf-8"))
        assert isinstance(content, dict), "Output JSON must be a dict"

    def test_output_json_has_classification(self):
        content = json.loads(_OUTPUT_JSON.read_text(encoding="utf-8"))
        assert "classification" in content, "Output JSON missing 'classification'"

    def test_output_json_has_production_rows(self):
        content = json.loads(_OUTPUT_JSON.read_text(encoding="utf-8"))
        assert content.get("production_rows") == PROD_ROW_TOTAL, (
            f"Output JSON production_rows != {PROD_ROW_TOTAL}"
        )

    def test_output_json_has_ceo_observations(self):
        content = json.loads(_OUTPUT_JSON.read_text(encoding="utf-8"))
        assert "ceo_opportunistic_observations" in content, (
            "Output JSON missing 'ceo_opportunistic_observations'"
        )
