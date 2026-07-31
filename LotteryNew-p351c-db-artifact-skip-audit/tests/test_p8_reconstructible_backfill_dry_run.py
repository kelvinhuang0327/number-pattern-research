"""
test_p8_reconstructible_backfill_dry_run.py
=============================================
Tests for P8 Reconstructible Backfill Dry-Run Plan.

Verifies:
  1. Plan JSON structure and required fields
  2. Total candidates = 121
  3. READY_FOR_ONLINE_APPLY = 28 (ONLINE strategies)
  4. PENDING_HUMAN_REVIEW_RETIRED = 93 (RETIRED strategies)
  5. All 121 candidates have prediction_items data
  6. All 121 candidates have draw result data
  7. All 121 have both (field completeness = 100%)
  8. Projection: 460+28=488 (ONLINE only), 460+121=581 (all)
  9. All entries dry_run_only=True
 10. No DB write performed
 11. PENDING_HUMAN_REVIEW entries are exactly RETIRED lifecycle
 12. READY entries are exactly ONLINE lifecycle
 13. Payload preview has required fields (no actual_numbers fabricated)
 14. Production rows unchanged at 460
 15. Script has no INSERT/DELETE/UPDATE SQL
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
PLAN_JSON   = REPO_ROOT / "outputs" / "replay" / "p8_reconstructible_backfill_dry_run_20260520.json"
PLAN_SCRIPT = REPO_ROOT / "scripts" / "p8_reconstructible_backfill_dry_run.py"

sys.path.insert(0, str(REPO_ROOT))

EXPECTED_READY          = 28
EXPECTED_PENDING_REVIEW = 93
EXPECTED_TOTAL          = 121
PRODUCTION_ROWS         = 460


@pytest.fixture(scope="module")
def plan() -> dict:
    assert PLAN_JSON.exists(), f"Plan JSON not found: {PLAN_JSON}. Run p8 script first."
    return json.loads(PLAN_JSON.read_text())


@pytest.fixture(scope="module")
def candidates(plan) -> list[dict]:
    return plan["candidates"]


class TestPlanStructure:
    def test_phase_is_p8(self, plan):
        assert plan["phase"] == "P8_RECONSTRUCTIBLE_BACKFILL_DRY_RUN"

    def test_dry_run_only(self, plan):
        assert plan["dry_run_only"] is True

    def test_db_write_false(self, plan):
        assert plan["db_write_performed"] is False

    def test_has_required_keys(self, plan):
        for key in ("phase", "generated_at", "dry_run_only", "db_write_performed",
                    "production_replay_rows_unchanged", "total_candidates",
                    "by_status", "by_strategy", "field_completeness",
                    "human_review_required_count", "ready_for_authorized_apply",
                    "why_no_db_write_this_round", "post_apply_projection",
                    "candidates", "safety_flags"):
            assert key in plan, f"Missing key: {key}"

    def test_total_candidates(self, plan):
        assert plan["total_candidates"] == EXPECTED_TOTAL

    def test_safety_flags(self, plan):
        flags = plan["safety_flags"]
        assert flags["db_write_performed"] is False
        assert flags["replay_rows_generated"] is False
        assert flags["strategy_executed"] is False
        assert flags["draw_data_imported"] is False
        assert flags["fake_success_count_is_zero"] is True
        assert flags["production_rows_unchanged"] is True

    def test_no_write_reasons_present(self, plan):
        reasons = plan["why_no_db_write_this_round"]
        assert len(reasons) > 0
        # Must mention CEO phrase somewhere
        assert any("YES apply P7" in r for r in reasons), (
            "Must reference CEO authorization phrase in no-write reasons"
        )


class TestStatusDistribution:
    def test_ready_count(self, plan):
        assert plan["by_status"].get("READY_FOR_ONLINE_APPLY", 0) == EXPECTED_READY

    def test_pending_review_count(self, plan):
        assert plan["by_status"].get("PENDING_HUMAN_REVIEW_RETIRED", 0) == EXPECTED_PENDING_REVIEW

    def test_no_duplicate_skips(self, plan):
        assert plan["by_status"].get("SKIP_ALREADY_EXISTS", 0) == 0

    def test_no_no_data_skips(self, plan):
        assert plan["by_status"].get("SKIP_NO_DATA", 0) == 0

    def test_status_counts_sum(self, plan):
        total = sum(plan["by_status"].values())
        assert total == EXPECTED_TOTAL

    def test_ready_for_authorized_apply(self, plan):
        assert plan["ready_for_authorized_apply"] == EXPECTED_READY

    def test_human_review_count(self, plan):
        assert plan["human_review_required_count"] == EXPECTED_PENDING_REVIEW


class TestFieldCompleteness:
    def test_all_have_prediction_items(self, plan):
        fc = plan["field_completeness"]
        assert fc["have_prediction_items"] == EXPECTED_TOTAL

    def test_all_have_draw_result(self, plan):
        fc = plan["field_completeness"]
        assert fc["have_draw_result"] == EXPECTED_TOTAL

    def test_all_have_both_complete(self, plan):
        fc = plan["field_completeness"]
        assert fc["have_both_complete"] == EXPECTED_TOTAL

    def test_no_missing_prediction(self, plan):
        assert plan["field_completeness"]["missing_prediction"] == 0

    def test_no_missing_draw_result(self, plan):
        assert plan["field_completeness"]["missing_draw_result"] == 0


class TestCandidateEntries:
    def test_all_dry_run_only(self, candidates):
        non_dro = [c for c in candidates if not c.get("dry_run_only")]
        assert not non_dro

    def test_ready_entries_are_online(self, candidates):
        for c in candidates:
            if c["status"] == "READY_FOR_ONLINE_APPLY":
                assert c["lifecycle_state"] == "ONLINE"

    def test_pending_entries_are_retired(self, candidates):
        for c in candidates:
            if c["status"] == "PENDING_HUMAN_REVIEW_RETIRED":
                assert c["lifecycle_state"] == "RETIRED"

    def test_ready_entries_have_payload_preview(self, candidates):
        for c in candidates:
            if c["status"] == "READY_FOR_ONLINE_APPLY":
                assert c["payload_preview"] is not None
                pp = c["payload_preview"]
                assert pp.get("predicted_numbers") is not None
                assert pp.get("actual_numbers") is not None
                assert pp.get("truth_level") == "RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD"
                assert pp.get("source") == "P7_CONTROLLED_APPLY"
                assert pp.get("dry_run") == 1  # preview only, not inserted

    def test_payload_hit_count_non_negative(self, candidates):
        for c in candidates:
            pp = c.get("payload_preview")
            if pp:
                assert pp.get("hit_count", 0) >= 0

    def test_readiness_flags_consistent(self, candidates):
        for c in candidates:
            r = c["readiness"]
            if c["status"] == "READY_FOR_ONLINE_APPLY":
                assert r["is_ready"] is True
                assert r["has_prediction_items"] is True
                assert r["has_draw_result"] is True
                assert r["needs_human_review"] is False
            elif c["status"] == "PENDING_HUMAN_REVIEW_RETIRED":
                assert r["is_ready"] is False
                assert r["needs_human_review"] is True

    def test_should_count_as_success_only_for_ready(self, candidates):
        for c in candidates:
            r = c["readiness"]
            if c["status"] != "READY_FOR_ONLINE_APPLY":
                assert r.get("should_count_as_success") is not True, (
                    f"Non-READY candidate {c['strategy_id']} {c['draw_id']} "
                    f"has should_count_as_success=True"
                )


class TestProjections:
    def test_projection_online_only(self, plan):
        proj = plan["post_apply_projection"]["online_only"]
        assert proj["current_rows"] == PRODUCTION_ROWS
        assert proj["rows_to_add"] == EXPECTED_READY
        assert proj["projected"] == PRODUCTION_ROWS + EXPECTED_READY  # 488

    def test_projection_online_plus_retired(self, plan):
        proj = plan["post_apply_projection"]["online_plus_retired"]
        assert proj["current_rows"] == PRODUCTION_ROWS
        assert proj["rows_to_add"] == EXPECTED_TOTAL  # 121
        assert proj["projected"] == PRODUCTION_ROWS + EXPECTED_TOTAL  # 581

    def test_by_strategy_count(self, plan):
        # 5 strategies total (2 ONLINE + 3 RETIRED)
        assert len(plan["by_strategy"]) == 5

    def test_human_review_strategies(self, plan):
        expected = {"acb_1bet", "acb_markov_midfreq_3bet", "midfreq_acb_2bet"}
        actual   = set(plan["human_review_required_strategies"])
        assert actual == expected


class TestProductionDB:
    def test_production_rows_unchanged(self, plan):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == PRODUCTION_ROWS

    def test_plan_reports_correct_production_rows(self, plan):
        assert plan["production_replay_rows_unchanged"] == PRODUCTION_ROWS


class TestScriptSafety:
    def test_no_insert_sql(self):
        src = PLAN_SCRIPT.read_text()
        # INSERT is allowed in the sql variable name (_INSERT_SQL mentioned as comment/string)
        # but no actual INSERT INTO statement as a real write
        assert "conn.execute(_INSERT" not in src
        # The only INSERT reference should be in a string for payload_preview.dry_run
        lines_with_insert = [l for l in src.splitlines()
                              if "INSERT INTO" in l.upper() and not l.strip().startswith("#")]
        assert not lines_with_insert, f"Found INSERT SQL: {lines_with_insert}"

    def test_no_delete_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "DELETE FROM" not in src.upper()

    def test_no_update_sql(self):
        src = PLAN_SCRIPT.read_text()
        lines = [l for l in src.splitlines()
                 if "UPDATE " in l.upper() and not l.strip().startswith("#")]
        assert not lines

    def test_opens_db_readonly(self):
        src = PLAN_SCRIPT.read_text()
        assert "query_only" in src or "mode=ro" in src

    def test_no_strategy_execution(self):
        src = PLAN_SCRIPT.read_text()
        assert "predict_func" not in src and "generate_numbers" not in src
