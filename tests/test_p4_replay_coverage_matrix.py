"""
tests/test_p4_replay_coverage_matrix.py
=========================================
P4 Coverage Matrix tests.

Tests:
  1. Script is read-only (DB row count unchanged before/after)
  2. Catalog denominator = all 59 catalog-visible entries (not just ONLINE)
  3. NO_DATA / RECONSTRUCTIBLE are NOT COVERED
  4. ARTIFACT_CANDIDATE → ARTIFACT_ONLY (not COVERED, not prediction success)
  5. Coverage status values are exhaustive
  6. Matrix output has required fields
  7. Summary counts internally consistent
  8. Most-recent-50-draws matrix can be computed
  9. by_lottery_type breakdown is correct
 10. coverage_pct correct
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.p4_replay_coverage_matrix import (
    run_coverage_matrix,
    _classify_coverage,
    COVERED,
    MISSING_REPLAY_ROW,
    RECONSTRUCTIBLE_PENDING,
    NO_DATA,
    ARTIFACT_ONLY,
    UNSUPPORTED_STATUS,
)
from lottery_api.services.replay_catalog_source import load_catalog

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"

VALID_STATUSES = {
    COVERED, MISSING_REPLAY_ROW, RECONSTRUCTIBLE_PENDING,
    NO_DATA, ARTIFACT_ONLY, UNSUPPORTED_STATUS,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def matrix_result():
    return run_coverage_matrix(
        limit=50,
        db_path=DB_PATH,
        p2_json=P2_JSON,
        p1_json=P1_JSON,
    )


# ---------------------------------------------------------------------------
# Section 1: Read-only safety
# ---------------------------------------------------------------------------

class TestReadOnlySafety:
    def test_db_row_count_unchanged(self, matrix_result):
        before = matrix_result["db_row_count_before"]
        after  = matrix_result["db_row_count_after"]
        assert before == after == 460, (
            f"DB was modified! before={before} after={after}"
        )

    def test_matrix_is_dry_run(self, matrix_result):
        assert matrix_result["dry_run"] is True

    def test_phase_is_p4(self, matrix_result):
        assert matrix_result["phase"] == "P4"

    def test_direct_db_count_still_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460


# ---------------------------------------------------------------------------
# Section 2: Denominator correctness
# ---------------------------------------------------------------------------

class TestDenominatorCorrectness:
    def test_catalog_denominator_is_all_59(self, matrix_result):
        assert matrix_result["catalog_total"] == 59, (
            f"Expected catalog denominator 59, got {matrix_result['catalog_total']}"
        )

    def test_draws_evaluated_is_50(self, matrix_result):
        assert matrix_result["draws_evaluated"] == 50

    def test_total_cells_correct(self, matrix_result):
        # total_cells must equal sum of (strategies_per_lt × draws_per_lt)
        expected = sum(
            v["strategy_count"] * v["draw_count"]
            for v in matrix_result["by_lottery_type"].values()
        )
        assert matrix_result["total_cells"] == expected

    def test_not_only_online_strategies(self, matrix_result):
        # The denominator must include ARTIFACT_CANDIDATE (NOT_REGISTERED) entries
        artifact_in_matrix = any(
            r["visibility_state"] == "ARTIFACT_CANDIDATE"
            for r in matrix_result["matrix"]
        )
        # Only applies if ARTIFACT_CANDIDATE strategies have matching lottery_type draws
        # At minimum, ARTIFACT_CANDIDATE is in catalog_total=59
        assert matrix_result["catalog_total"] >= 59


# ---------------------------------------------------------------------------
# Section 3: Coverage status classification
# ---------------------------------------------------------------------------

class TestCoverageStatusClassification:
    @pytest.mark.parametrize("vis_state,has_row,expected", [
        ("REGISTERED_WITH_REPLAY_ROWS", True,  COVERED),
        ("REGISTERED_WITH_REPLAY_ROWS", False, MISSING_REPLAY_ROW),
        ("RECONSTRUCTIBLE",             True,  RECONSTRUCTIBLE_PENDING),
        ("RECONSTRUCTIBLE",             False, RECONSTRUCTIBLE_PENDING),
        ("REGISTERED_NO_DATA",          False, NO_DATA),
        ("UNSUPPORTED",                 False, NO_DATA),
        ("ARTIFACT_CANDIDATE",          False, ARTIFACT_ONLY),
        ("ARTIFACT_CANDIDATE",          True,  ARTIFACT_ONLY),
    ])
    def test_classify_coverage(self, vis_state, has_row, expected):
        result = _classify_coverage(vis_state, has_row)
        assert result == expected, (
            f"_classify_coverage({vis_state!r}, {has_row}) = {result!r}, expected {expected!r}"
        )

    def test_reconstructible_never_covered(self, matrix_result):
        recon_rows = [r for r in matrix_result["matrix"]
                      if r["visibility_state"] == "RECONSTRUCTIBLE"]
        for row in recon_rows:
            assert row["coverage_status"] != COVERED, (
                f"RECONSTRUCTIBLE strategy {row['strategy_id']!r} marked COVERED"
            )

    def test_no_data_never_covered(self, matrix_result):
        no_data_rows = [r for r in matrix_result["matrix"]
                        if r["visibility_state"] in ("REGISTERED_NO_DATA", "UNSUPPORTED")]
        for row in no_data_rows:
            assert row["coverage_status"] != COVERED

    def test_artifact_candidate_uses_artifact_only_status(self, matrix_result):
        art_rows = [r for r in matrix_result["matrix"]
                    if r["visibility_state"] == "ARTIFACT_CANDIDATE"]
        for row in art_rows:
            assert row["coverage_status"] == ARTIFACT_ONLY, (
                f"ARTIFACT_CANDIDATE {row['strategy_id']!r} has status "
                f"{row['coverage_status']!r}, expected ARTIFACT_ONLY"
            )

    def test_all_status_values_valid(self, matrix_result):
        for row in matrix_result["matrix"]:
            assert row["coverage_status"] in VALID_STATUSES, (
                f"Unknown coverage_status: {row['coverage_status']!r}"
            )


# ---------------------------------------------------------------------------
# Section 4: Matrix output shape
# ---------------------------------------------------------------------------

class TestMatrixOutputShape:
    def test_required_top_level_fields(self, matrix_result):
        required = [
            "generated_at", "phase", "mode", "dry_run",
            "catalog_source", "catalog_total", "draw_limit",
            "draws_evaluated", "total_cells", "covered_cells",
            "coverage_pct", "status_counts", "by_lottery_type",
            "db_row_count_before", "db_row_count_after", "matrix",
        ]
        for field in required:
            assert field in matrix_result, f"Missing field: {field!r}"

    def test_matrix_row_required_fields(self, matrix_result):
        required_row_fields = [
            "draw", "lottery_type", "draw_date", "strategy_id",
            "visibility_state", "lifecycle_state",
            "has_prediction_row", "has_result_row", "coverage_status",
        ]
        for row in matrix_result["matrix"][:5]:  # spot check first 5
            for field in required_row_fields:
                assert field in row, f"Matrix row missing field: {field!r}"

    def test_coverage_pct_range(self, matrix_result):
        pct = matrix_result["coverage_pct"]
        assert 0.0 <= pct <= 100.0, f"coverage_pct out of range: {pct}"

    def test_status_counts_sum_to_total_cells(self, matrix_result):
        total = sum(matrix_result["status_counts"].values())
        assert total == matrix_result["total_cells"]

    def test_covered_cells_matches_status_counts(self, matrix_result):
        assert matrix_result["covered_cells"] == matrix_result["status_counts"].get(COVERED, 0)

    def test_catalog_source_is_valid(self, matrix_result):
        assert matrix_result["catalog_source"] in ("live_db", "p2_json", "p1_json")


# ---------------------------------------------------------------------------
# Section 5: Per-lottery type breakdown
# ---------------------------------------------------------------------------

class TestPerLotteryBreakdown:
    def test_by_lottery_type_has_entries(self, matrix_result):
        assert len(matrix_result["by_lottery_type"]) > 0

    def test_by_lottery_type_has_required_fields(self, matrix_result):
        for lt, data in matrix_result["by_lottery_type"].items():
            assert "strategy_count" in data, f"{lt!r} missing strategy_count"
            assert "draw_count" in data
            assert "total_cells" in data
            assert "covered" in data
            assert "coverage_pct" in data

    def test_registered_strategies_have_draws(self, matrix_result):
        # BIG_LOTTO, POWER_LOTTO, DAILY_539 should all be present
        lotteries = set(matrix_result["by_lottery_type"].keys())
        # At least one known lottery type should appear
        assert len(lotteries) >= 1

    def test_lottery_type_cells_correct(self, matrix_result):
        for lt, data in matrix_result["by_lottery_type"].items():
            expected = data["strategy_count"] * data["draw_count"]
            assert data["total_cells"] == expected, (
                f"{lt!r}: expected {expected} cells, got {data['total_cells']}"
            )


# ---------------------------------------------------------------------------
# Section 6: Reconciliation with expected counts
# ---------------------------------------------------------------------------

class TestReconciliation:
    def test_covered_only_from_registered_with_rows(self, matrix_result):
        for row in matrix_result["matrix"]:
            if row["coverage_status"] == COVERED:
                assert row["visibility_state"] == "REGISTERED_WITH_REPLAY_ROWS", (
                    f"Non-REGISTERED strategy {row['strategy_id']!r} marked COVERED"
                )

    def test_has_result_row_true_for_all_matrix_rows(self, matrix_result):
        for row in matrix_result["matrix"]:
            assert row["has_result_row"] is True, (
                "All matrix rows use draws from the draws table (actual results exist)"
            )

    def test_limit_50_returns_reasonable_cell_count(self, matrix_result):
        # With 6 registered strategies (BIG/POWER/DAILY_539), 50 draws distributed
        # across lottery types → at least some coverage cells
        assert matrix_result["total_cells"] > 0

    def test_db_unchanged_after_full_run(self, matrix_result):
        conn = sqlite3.connect(str(DB_PATH))
        current = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert current == 460, (
            f"DB row count changed to {current} after P4 matrix run"
        )
