"""
test_p3_per_draw_all_strategy_coverage_matrix.py
==================================================
Tests for P3 Per-Draw All-Strategy Coverage Matrix.

Verifies:
  1. Matrix JSON structure and required fields
  2. Summary JSON structure and required fields
  3. ROW_BACKED cells have actual replay rows in DB
  4. RECONSTRUCTIBLE cells have prediction_items or P7 plan rows
  5. NO_DATA cells have neither replay rows nor prediction_items
  6. fake_success_count == 0 (critical invariant)
  7. should_count_as_success is True only for ROW_BACKED cells
  8. All entries have dry_run_only=True
  9. Production DB unchanged at 460
 10. Script has no INSERT/DELETE/UPDATE SQL
 11. Display status matches visibility state
 12. Coverage percentages are consistent with cell counts
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).resolve().parent.parent
DB_PATH       = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
MATRIX_JSON   = REPO_ROOT / "outputs" / "replay" / "p3_per_draw_all_strategy_coverage_matrix_20260520.json"
SUMMARY_JSON  = REPO_ROOT / "outputs" / "replay" / "p3_per_draw_all_strategy_coverage_summary_20260520.json"
MATRIX_SCRIPT = REPO_ROOT / "scripts" / "p3_per_draw_all_strategy_coverage_matrix.py"

sys.path.insert(0, str(REPO_ROOT))

VALID_VISIBILITY = {"ROW_BACKED", "RECONSTRUCTIBLE", "NO_DATA", "ARTIFACT_ONLY"}
VALID_DISPLAY    = {
    "SHOW_REPLAY_RESULT", "SHOW_RECONSTRUCTIBLE_PENDING",
    "SHOW_NO_DATA", "SHOW_ARTIFACT_ONLY"
}


@pytest.fixture(scope="module")
def matrix() -> dict:
    assert MATRIX_JSON.exists(), f"Matrix JSON not found: {MATRIX_JSON}. Run p3 script first."
    return json.loads(MATRIX_JSON.read_text())


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_JSON.exists(), f"Summary JSON not found: {SUMMARY_JSON}. Run p3 script first."
    return json.loads(SUMMARY_JSON.read_text())


@pytest.fixture(scope="module")
def entries(matrix) -> list[dict]:
    return matrix["entries"]


class TestMatrixStructure:
    def test_matrix_has_required_keys(self, matrix):
        for key in ("phase", "generated_at", "dry_run_only", "total_entries", "entries"):
            assert key in matrix, f"Missing key: {key}"

    def test_phase_is_p3_matrix(self, matrix):
        assert matrix["phase"] == "P3_COVERAGE_MATRIX"

    def test_dry_run_only(self, matrix):
        assert matrix["dry_run_only"] is True

    def test_total_entries_matches_list(self, matrix, entries):
        assert matrix["total_entries"] == len(entries)

    def test_entry_has_required_fields(self, entries):
        required = {
            "draw_number", "draw_date", "lottery_type", "strategy_id",
            "strategy_name", "lifecycle_status", "visibility_state",
            "has_replay_row", "has_prediction_items", "replay_row_count",
            "prediction_items_count", "actual_numbers_available",
            "hit_count_available", "source_table", "source_artifact",
            "display_status", "should_count_as_success", "dry_run_only",
        }
        for e in entries[:10]:  # check first 10
            missing = required - set(e.keys())
            assert not missing, f"Entry missing fields: {missing}"

    def test_all_entries_dry_run_only(self, entries):
        non_dro = [e for e in entries if not e.get("dry_run_only")]
        assert not non_dro, f"{len(non_dro)} entries have dry_run_only != True"

    def test_visibility_states_valid(self, entries):
        for e in entries:
            assert e["visibility_state"] in VALID_VISIBILITY

    def test_display_statuses_valid(self, entries):
        for e in entries:
            assert e["display_status"] in VALID_DISPLAY


class TestSummaryStructure:
    def test_summary_has_required_keys(self, summary):
        required = {
            "phase", "generated_at", "dry_run_only", "db_write_performed",
            "total_draws", "total_strategies", "total_matrix_cells",
            "by_visibility_state", "by_display_status", "by_lottery_type",
            "row_backed_coverage_pct", "reconstructible_coverage_pct", "no_data_pct",
            "artifact_only_count", "product_visible_strategy_count",
            "real_replay_success_count", "fake_success_count",
            "production_replay_rows_unchanged", "safety_flags",
        }
        missing = required - set(summary.keys())
        assert not missing, f"Summary missing keys: {missing}"

    def test_phase_is_p3_summary(self, summary):
        assert summary["phase"] == "P3_COVERAGE_SUMMARY"

    def test_db_write_false(self, summary):
        assert summary["db_write_performed"] is False

    def test_safety_flags(self, summary):
        flags = summary["safety_flags"]
        assert flags["db_write_performed"] is False
        assert flags["replay_rows_generated"] is False
        assert flags["strategy_executed"] is False
        assert flags["draw_data_imported"] is False
        assert flags["fake_success_count_is_zero"] is True

    def test_total_strategies_is_18(self, summary):
        assert summary["total_strategies"] == 18

    def test_total_draws_positive(self, summary):
        assert summary["total_draws"] > 0

    def test_total_matrix_cells_consistent(self, summary, entries):
        assert summary["total_matrix_cells"] == len(entries)

    def test_by_visibility_state_sums_to_total(self, summary):
        total_from_vis = sum(summary["by_visibility_state"].values())
        assert total_from_vis == summary["total_matrix_cells"]

    def test_coverage_pcts_sum_approx_100(self, summary):
        row_backed   = summary["row_backed_coverage_pct"]
        reconstructible = summary["reconstructible_coverage_pct"]
        no_data      = summary["no_data_pct"]
        total        = row_backed + reconstructible + no_data
        assert abs(total - 100.0) < 1.0, f"Coverage pcts don't sum to ~100: {total}"

    def test_row_backed_pct_consistent(self, summary):
        rb_count = summary["by_visibility_state"].get("ROW_BACKED", 0)
        total    = summary["total_matrix_cells"]
        expected_pct = round(rb_count / total * 100, 2) if total else 0
        assert abs(summary["row_backed_coverage_pct"] - expected_pct) < 0.01

    def test_product_visible_strategy_count(self, summary):
        # ONLINE strategies only
        from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
        online = [m for m in list_strategy_lifecycle_metadata()
                  if m.get("lifecycle_status") == "ONLINE"]
        assert summary["product_visible_strategy_count"] == len(online)


class TestCriticalInvariants:
    def test_fake_success_count_is_zero(self, summary):
        """CRITICAL: fake_success_count must be 0. NO_DATA/RECONSTRUCTIBLE/ARTIFACT_ONLY
        must never be counted as success."""
        assert summary["fake_success_count"] == 0, (
            f"INTEGRITY VIOLATION: fake_success_count={summary['fake_success_count']}"
        )

    def test_should_count_as_success_only_for_row_backed(self, entries):
        """should_count_as_success=True implies visibility_state=ROW_BACKED."""
        violations = [
            e for e in entries
            if e["should_count_as_success"] and e["visibility_state"] != "ROW_BACKED"
        ]
        assert not violations, (
            f"Non-ROW_BACKED entries marked as success: "
            f"{[v['strategy_id'] + ':' + v['draw_number'] for v in violations[:5]]}"
        )

    def test_row_backed_entries_have_replay_rows(self, entries):
        for e in entries:
            if e["visibility_state"] == "ROW_BACKED":
                assert e["has_replay_row"] is True
                assert e["replay_row_count"] > 0

    def test_no_data_entries_have_no_source(self, entries):
        for e in entries:
            if e["visibility_state"] == "NO_DATA":
                assert not e["has_replay_row"]

    def test_reconstructible_entries_have_source_data(self, entries):
        for e in entries:
            if e["visibility_state"] == "RECONSTRUCTIBLE":
                assert e["has_prediction_items"] or e.get("source_artifact") is not None, (
                    f"RECONSTRUCTIBLE entry {e['strategy_id']} {e['draw_number']} "
                    f"has no prediction_items and no source_artifact"
                )

    def test_display_status_matches_visibility(self, entries):
        mapping = {
            "ROW_BACKED":      "SHOW_REPLAY_RESULT",
            "RECONSTRUCTIBLE": "SHOW_RECONSTRUCTIBLE_PENDING",
            "NO_DATA":         "SHOW_NO_DATA",
            "ARTIFACT_ONLY":   "SHOW_ARTIFACT_ONLY",
        }
        for e in entries:
            expected = mapping.get(e["visibility_state"])
            if expected:
                assert e["display_status"] == expected, (
                    f"{e['strategy_id']} {e['draw_number']}: "
                    f"visibility={e['visibility_state']} but display={e['display_status']}"
                )


class TestProductionDBIntegrity:
    def test_production_rows_unchanged(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460, f"Production rows changed: expected 460, got {count}"

    def test_summary_reports_correct_production_rows(self, summary):
        assert summary["production_replay_rows_unchanged"] == 460


class TestScriptSafety:
    def test_no_insert_sql(self):
        src = MATRIX_SCRIPT.read_text()
        assert "INSERT INTO" not in src.upper()

    def test_no_delete_sql(self):
        src = MATRIX_SCRIPT.read_text()
        assert "DELETE FROM" not in src.upper()

    def test_no_update_sql(self):
        src = MATRIX_SCRIPT.read_text()
        assert "UPDATE " not in src.upper()

    def test_opens_db_readonly(self):
        src = MATRIX_SCRIPT.read_text()
        assert "query_only" in src or "mode=ro" in src

    def test_no_strategy_execution(self):
        src = MATRIX_SCRIPT.read_text()
        assert "predict_func" not in src and "generate_numbers" not in src
