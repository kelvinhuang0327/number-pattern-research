"""
test_p6_source_promotion_policy.py
=====================================
P6 Source Promotion Policy — Functional / Integration Tests.

Tests the P6 script and its JSON output against actual P5 artifacts:
  1. Script has no --apply flag
  2. No DB write (row count stays at 460)
  3. All SKIP rows remain NOT_P7_CANDIDATE
  4. All PLAN_INSERT rows with TIER_1 + provenance + numbers → P7_CANDIDATE
  5. RETIRED approved with lifecycle_warning
  6. ONLINE approved without lifecycle_warning
  7. REJECTED lifecycle blocked
  8. JSON output has required keys
  9. p6_can_apply always False
 10. approved_for_p7_candidate <= plan_insert_rows
 11. total rows = P5 total
 12. DB row count verified field present and correct
"""

from __future__ import annotations

import inspect
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P5_PLAN    = REPO_ROOT / "outputs" / "replay" / "p5_historical_reconstruction_plan_20260520.json"
P6_SCRIPT  = REPO_ROOT / "scripts" / "p6_source_promotion_policy.py"
P6_JSON    = REPO_ROOT / "outputs" / "replay" / "p6_source_promotion_policy_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_source_promotion_policy import (
    SourcePromotionDecision,
    SourcePromotionTier,
    P7CandidateStatus,
    evaluate_promotion_policy,
    summarize_promotion_results,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p6_json() -> dict:
    if not P6_JSON.exists():
        pytest.skip(f"P6 output not found: {P6_JSON}. Run scripts/p6_source_promotion_policy.py first.")
    return json.loads(P6_JSON.read_text())


@pytest.fixture(scope="module")
def p5_json() -> dict:
    if not P5_PLAN.exists():
        pytest.skip(f"P5 plan not found: {P5_PLAN}. Run scripts/p5_historical_reconstruction_plan.py first.")
    return json.loads(P5_PLAN.read_text())


def _db_replay_count() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 1: Script safety
# ---------------------------------------------------------------------------

class TestScriptSafety:
    def test_script_has_no_apply_flag(self):
        src = P6_SCRIPT.read_text()
        # Check that --apply is not registered as an argparse argument.
        # (The word may appear in comments/docstrings, but not as an add_argument call.)
        assert 'add_argument("--apply"' not in src and "add_argument('--apply'" not in src, (
            "P6 script must not expose a --apply flag via argparse; "
            "P7 apply is handled separately"
        )

    def test_script_has_no_db_write(self):
        src = P6_SCRIPT.read_text()
        # Must not contain any INSERT / UPDATE / DELETE SQL
        for keyword in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
            assert keyword not in src, (
                f"P6 script contains forbidden SQL keyword: {keyword!r}"
            )

    def test_script_opens_db_readonly(self):
        src = P6_SCRIPT.read_text()
        assert "mode=ro" in src, (
            "P6 script must open the DB with mode=ro (read-only)"
        )


# ---------------------------------------------------------------------------
# Section 2: DB safety (no rows changed)
# ---------------------------------------------------------------------------

class TestDBSafety:
    def test_db_row_count_is_460(self):
        count = _db_replay_count()
        assert count == 460, (
            f"strategy_prediction_replays row count changed! "
            f"Expected 460, got {count}"
        )

    def test_p6_json_db_verified_field(self, p6_json):
        assert "db_row_count_verified" in p6_json
        assert p6_json["db_row_count_verified"] == 460

    def test_p7_candidate_rows_have_no_replay_row_ids(self, p6_json):
        for row in p6_json.get("p7_candidate_rows", []):
            assert "replay_row_id" not in row, (
                "P7 candidate rows must not reference existing replay_row_id — "
                "P6 does not create replay rows"
            )


# ---------------------------------------------------------------------------
# Section 3: P6 JSON output structure
# ---------------------------------------------------------------------------

class TestP6OutputStructure:
    REQUIRED_KEYS = {
        "phase", "generated_at", "dry_run_only",
        "db_row_count_verified", "total_plan_rows",
        "plan_insert_rows", "approved_for_p7_candidate",
        "rejected_count", "manual_review_required",
        "rejected_by_reason", "by_strategy", "by_lifecycle_state",
        "by_source_tier", "lifecycle_warnings", "p7_candidate_rows",
        "all_results",
    }

    def test_required_keys_present(self, p6_json):
        for key in self.REQUIRED_KEYS:
            assert key in p6_json, f"Missing required key {key!r} in P6 output"

    def test_phase_is_p6(self, p6_json):
        assert p6_json["phase"] == "P6"

    def test_dry_run_only_true(self, p6_json):
        assert p6_json["dry_run_only"] is True

    def test_total_matches_p5(self, p6_json, p5_json):
        assert p6_json["total_plan_rows"] == p5_json["total_plan_rows"], (
            f"P6 total rows ({p6_json['total_plan_rows']}) != "
            f"P5 total rows ({p5_json['total_plan_rows']})"
        )

    def test_approved_lte_plan_insert(self, p6_json):
        assert p6_json["approved_for_p7_candidate"] <= p6_json["plan_insert_rows"], (
            "approved_for_p7_candidate must be <= plan_insert_rows"
        )

    def test_counts_consistent(self, p6_json):
        total    = p6_json["total_plan_rows"]
        approved = p6_json["approved_for_p7_candidate"]
        rejected = p6_json["rejected_count"]
        manual   = p6_json["manual_review_required"]
        assert approved + rejected + manual == total, (
            f"approved({approved}) + rejected({rejected}) + manual({manual}) "
            f"!= total({total})"
        )


# ---------------------------------------------------------------------------
# Section 4: Candidate classification correctness
# ---------------------------------------------------------------------------

class TestCandidateClassification:
    def test_all_results_have_p6_can_apply_false(self, p6_json):
        for r in p6_json["all_results"]:
            assert r["p6_can_apply"] is False, (
                f"p6_can_apply must be False; got True for "
                f"{r['strategy_id']}/{r['draw_id']}"
            )

    def test_all_results_have_dry_run_only_true(self, p6_json):
        for r in p6_json["all_results"]:
            assert r["dry_run_only"] is True

    def test_skip_rows_are_not_p7_candidates(self, p6_json):
        for r in p6_json["all_results"]:
            if r["planned_action"] != "PLAN_INSERT_REPLAY_ROW":
                assert r["p7_candidate_status"] == P7CandidateStatus.NOT_P7_CANDIDATE, (
                    f"SKIP row {r['strategy_id']}/{r['draw_id']} must be NOT_P7_CANDIDATE"
                )

    def test_plan_insert_tier1_with_provenance_and_numbers_approved(self, p6_json):
        for r in p6_json["all_results"]:
            if (
                r["planned_action"] == "PLAN_INSERT_REPLAY_ROW"
                and r["source_tier"] == SourcePromotionTier.TIER_1_DB_PREDICTION_PAYLOAD
                and r["provenance_hash"]
                and r["has_predicted_numbers"]
                and r["lifecycle_state"] not in ("REJECTED", "OFFLINE")
            ):
                assert r["p7_candidate_status"] == P7CandidateStatus.P7_CANDIDATE, (
                    f"TIER_1 PLAN_INSERT with provenance+numbers+valid lifecycle "
                    f"should be P7_CANDIDATE: {r['strategy_id']}/{r['draw_id']}"
                )

    def test_rejected_lifecycle_not_candidate(self, p6_json):
        for r in p6_json["all_results"]:
            if r["lifecycle_state"] == "REJECTED":
                assert r["p7_candidate_status"] == P7CandidateStatus.NOT_P7_CANDIDATE, (
                    f"REJECTED lifecycle must not be P7_CANDIDATE: "
                    f"{r['strategy_id']}/{r['draw_id']}"
                )

    def test_retired_candidates_have_lifecycle_warning(self, p6_json):
        for r in p6_json["p7_candidate_rows"]:
            if r["lifecycle_state"] == "RETIRED":
                assert r["lifecycle_warning"] is not None, (
                    f"RETIRED P7 candidate {r['strategy_id']}/{r['draw_id']} "
                    f"must have lifecycle_warning"
                )

    def test_online_candidates_have_no_lifecycle_warning(self, p6_json):
        for r in p6_json["p7_candidate_rows"]:
            if r["lifecycle_state"] == "ONLINE":
                assert r["lifecycle_warning"] is None, (
                    f"ONLINE P7 candidate {r['strategy_id']}/{r['draw_id']} "
                    f"must NOT have lifecycle_warning, got: {r['lifecycle_warning']!r}"
                )

    def test_code_scan_only_not_candidate(self, p6_json):
        for r in p6_json["all_results"]:
            if r["source_tier"] == SourcePromotionTier.TIER_4_CODE_SCAN_ONLY:
                assert r["p7_candidate_status"] == P7CandidateStatus.NOT_P7_CANDIDATE, (
                    f"TIER_4_CODE_SCAN_ONLY must not be P7_CANDIDATE: "
                    f"{r['strategy_id']}/{r['draw_id']}"
                )


# ---------------------------------------------------------------------------
# Section 5: P7 candidate row safety
# ---------------------------------------------------------------------------

class TestP7CandidateRowSafety:
    def test_all_candidate_rows_have_provenance_hash(self, p6_json):
        for row in p6_json["p7_candidate_rows"]:
            assert row["provenance_hash"], (
                f"P7 candidate {row['strategy_id']}/{row['draw_id']} "
                f"is missing provenance_hash"
            )

    def test_all_candidate_rows_have_predicted_numbers(self, p6_json):
        for row in p6_json["p7_candidate_rows"]:
            assert row["has_predicted_numbers"] is True, (
                f"P7 candidate {row['strategy_id']}/{row['draw_id']} "
                f"has no predicted_numbers"
            )

    def test_all_candidate_rows_plan_insert(self, p6_json):
        for row in p6_json["p7_candidate_rows"]:
            assert row["planned_action"] == "PLAN_INSERT_REPLAY_ROW", (
                f"P7 candidate {row['strategy_id']}/{row['draw_id']} "
                f"planned_action is not PLAN_INSERT_REPLAY_ROW"
            )

    def test_candidate_count_matches_approved_count(self, p6_json):
        assert len(p6_json["p7_candidate_rows"]) == p6_json["approved_for_p7_candidate"]


# ---------------------------------------------------------------------------
# Section 6: Summarize helper
# ---------------------------------------------------------------------------

class TestSummarizeHelper:
    def test_summarize_empty(self):
        summary = summarize_promotion_results([])
        assert summary["total_plan_rows"] == 0
        assert summary["approved_for_p7_candidate"] == 0
        assert summary["p7_candidate_rows"] == []

    def test_summarize_counts(self):
        from lottery_api.models.replay_source_promotion_policy import SourcePromotionResult

        approved = SourcePromotionResult(
            strategy_id="test_strat", lottery_type="DAILY_539",
            draw_id="115000001", draw_date=None,
            planned_action="PLAN_INSERT_REPLAY_ROW",
            source_tier=SourcePromotionTier.TIER_1_DB_PREDICTION_PAYLOAD,
            p5_can_apply=False,
            provenance_hash="abc123",
            has_predicted_numbers=True,
            run_id=1, lifecycle_state="ONLINE",
            lifecycle_warning=None,
            promotion_decision=SourcePromotionDecision.APPROVE_FOR_P7_CANDIDATE,
            p7_candidate_status=P7CandidateStatus.P7_CANDIDATE,
        )
        rejected = SourcePromotionResult(
            strategy_id="test_strat2", lottery_type="BIG_LOTTO",
            draw_id=None, draw_date=None,
            planned_action="SKIP_NO_HISTORICAL_PAYLOAD",
            source_tier=SourcePromotionTier.TIER_4_CODE_SCAN_ONLY,
            p5_can_apply=False,
            provenance_hash=None,
            has_predicted_numbers=False,
            run_id=None, lifecycle_state="RETIRED",
            lifecycle_warning="retired warning",
            promotion_decision=SourcePromotionDecision.REJECT_NOT_PLAN_INSERT,
            p7_candidate_status=P7CandidateStatus.NOT_P7_CANDIDATE,
            rejection_reason="not PLAN_INSERT",
        )
        summary = summarize_promotion_results([approved, rejected])
        assert summary["total_plan_rows"] == 2
        assert summary["approved_for_p7_candidate"] == 1
        assert summary["rejected_count"] == 1
        assert len(summary["p7_candidate_rows"]) == 1
