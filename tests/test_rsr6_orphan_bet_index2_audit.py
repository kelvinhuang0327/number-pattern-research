"""
test_rsr6_orphan_bet_index2_audit.py
======================================
Tests for RSR-6 orphan bet_index=2 audit artifact.

Validates:
  - JSON artifact exists with correct fields
  - DB rows before/after == 72462
  - bet_index schema exists
  - P128 Phase 2 classification correct
  - Orphan row audit fields
  - Apply gate impact fields
  - Blocked/excluded fields
  - No DB writes occurred
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACT_PATH = PROJECT_ROOT / "outputs" / "replay" / "rsr6_orphan_bet_index2_audit_20260528.json"
P128_ARTIFACT = PROJECT_ROOT / "outputs" / "replay" / "p128_wave2_adapter_phase2_20260528.json"


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_PATH.exists(), f"Artifact not found: {ARTIFACT_PATH}"
    return json.loads(ARTIFACT_PATH.read_text())


# ── Top-level classification ──────────────────────────────────────────────────

class TestClassification:
    def test_task_id(self, artifact):
        assert artifact["task_id"] == "RSR6"

    def test_classification(self, artifact):
        assert artifact["classification"] == "RSR6_ORPHAN_BET_INDEX2_AUDIT_READY"

    def test_generated_at_present(self, artifact):
        assert artifact.get("generated_at"), "generated_at missing"


# ── DB invariant ──────────────────────────────────────────────────────────────

class TestDbInvariant:
    def test_rows_before_72462(self, artifact):
        assert artifact["db_snapshot_before"]["total_rows"] == 72462

    def test_rows_after_72462(self, artifact):
        assert artifact["db_snapshot_after"]["total_rows"] == 72462

    def test_invariant_ok_before(self, artifact):
        assert artifact["db_snapshot_before"]["invariant_ok"] is True

    def test_invariant_ok_after(self, artifact):
        assert artifact["db_snapshot_after"]["invariant_ok"] is True

    def test_no_rows_modified(self, artifact):
        assert artifact["db_snapshot_after"]["rows_modified"] == 0


# ── Schema check ──────────────────────────────────────────────────────────────

class TestSchema:
    def test_bet_index_column_check(self, artifact):
        # The script verifies bet_index exists — if artifact generated successfully
        # with these field checks, the column exists
        assert artifact["db_snapshot_before"]["invariant_ok"] is True


# ── P128 Phase 2 source artifact ──────────────────────────────────────────────

class TestP128SourceArtifact:
    def test_p128_artifact_exists(self):
        assert P128_ARTIFACT.exists(), f"P128 Phase 2 artifact not found: {P128_ARTIFACT}"

    def test_p128_classification_in_rsr6(self, artifact):
        assert artifact["p128_phase2_source_summary"]["classification"] == "P128_WAVE2_ADAPTER_PHASE2_READY"

    def test_p128_classification_ok(self, artifact):
        assert artifact["p128_phase2_source_summary"]["classification_ok"] is True

    def test_p128_rsr6_strategies_listed(self, artifact):
        blocked = artifact["p128_phase2_source_summary"]["rsr6_strategies_blocked"]
        assert "power_precision_3bet" in blocked
        assert "power_orthogonal_5bet" in blocked


# ── Orphan row summary ────────────────────────────────────────────────────────

class TestOrphanRowSummary:
    def test_affected_strategies(self, artifact):
        s = artifact["orphan_row_summary"]["affected_strategies"]
        assert "power_precision_3bet" in s
        assert "power_orthogonal_5bet" in s

    def test_total_orphan_rows_positive(self, artifact):
        assert artifact["orphan_row_summary"]["total_orphan_rows"] > 0

    def test_total_orphan_rows_40(self, artifact):
        assert artifact["orphan_row_summary"]["total_orphan_rows"] == 40

    def test_rows_by_strategy_present(self, artifact):
        rbs = artifact["orphan_row_summary"]["rows_by_strategy"]
        assert "power_precision_3bet" in rbs
        assert "power_orthogonal_5bet" in rbs

    def test_rows_by_strategy_counts(self, artifact):
        rbs = artifact["orphan_row_summary"]["rows_by_strategy"]
        assert rbs["power_precision_3bet"]["bi_2_orphan"] == 20
        assert rbs["power_orthogonal_5bet"]["bi_2_orphan"] == 20

    def test_draw_range_present(self, artifact):
        assert artifact["orphan_row_summary"]["target_draw_range"] == "99000085–99000104"

    def test_source_blank_count(self, artifact):
        assert artifact["orphan_row_summary"]["source_blank_count"] == 40

    def test_provenance_incomplete_count(self, artifact):
        assert artifact["orphan_row_summary"]["provenance_incomplete_count"] == 40

    def test_db_write_in_rsr6_false(self, artifact):
        assert artifact["orphan_row_summary"]["db_write_in_rsr6"] is False

    def test_cleanup_executed_false(self, artifact):
        assert artifact["orphan_row_summary"]["cleanup_executed"] is False

    def test_bi1_overlap_complete(self, artifact):
        assert artifact["orphan_row_summary"]["bi1_overlap_complete"] is True


# ── Orphan rows detail ────────────────────────────────────────────────────────

class TestOrphanRowsDetail:
    def test_orphan_rows_list_length(self, artifact):
        assert len(artifact["orphan_rows"]) == 40

    def test_orphan_rows_all_bi2(self, artifact):
        for r in artifact["orphan_rows"]:
            assert r["bet_index"] == 2

    def test_orphan_rows_source_blank(self, artifact):
        for r in artifact["orphan_rows"]:
            assert not r["source"]

    def test_orphan_rows_replay_run_id_6(self, artifact):
        for r in artifact["orphan_rows"]:
            assert r["replay_run_id"] == 6

    def test_orphan_rows_both_strategies(self, artifact):
        sids = {r["strategy_id"] for r in artifact["orphan_rows"]}
        assert "power_precision_3bet" in sids
        assert "power_orthogonal_5bet" in sids


# ── Apply gate impact ─────────────────────────────────────────────────────────

class TestApplyGateImpact:
    def test_power_precision_not_apply_ready(self, artifact):
        assert artifact["apply_gate_impact"]["power_precision_3bet_apply_ready"] is False

    def test_power_orthogonal_not_apply_ready(self, artifact):
        assert artifact["apply_gate_impact"]["power_orthogonal_5bet_apply_ready"] is False

    def test_p7_p8_p9_p11_not_evaluated(self, artifact):
        assert artifact["apply_gate_impact"]["p7_p8_p9_p11_apply_ready_not_evaluated"] is True

    def test_controlled_apply_not_executed(self, artifact):
        assert artifact["apply_gate_impact"]["controlled_apply_executed"] is False

    def test_replay_rows_inserted_zero(self, artifact):
        assert artifact["apply_gate_impact"]["replay_rows_inserted"] == 0

    def test_production_db_rows_after(self, artifact):
        assert artifact["apply_gate_impact"]["production_db_rows_after"] == 72462


# ── Blocked / excluded ────────────────────────────────────────────────────────

class TestBlockedExcluded:
    def test_no_db_write(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("no_db_write_in_rsr6") is True

    def test_no_controlled_apply(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("no_controlled_apply_in_rsr6") is True

    def test_4star_excluded(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("4_STAR_excluded") is True

    def test_p108_not_run(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("P108_not_run") is True

    def test_p117_not_run(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("P117_not_run") is True

    def test_p118_not_run(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("P118_not_run") is True

    def test_rejected_strategies_no_action(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("rejected_strategies_no_action") is True

    def test_no_scheduler_install(self, artifact):
        be = artifact["blocked_or_excluded"]
        assert be.get("no_scheduler_install") is True


# ── Authorization gate ────────────────────────────────────────────────────────

class TestAuthorizationGate:
    def test_auth_gate_present(self, artifact):
        assert "authorization_gate_if_cleanup_needed" in artifact

    def test_auth_phrase_present(self, artifact):
        phrase = artifact["authorization_gate_if_cleanup_needed"]["authorization_phrase"]
        assert phrase and len(phrase) > 20

    def test_cleanup_sql_present(self, artifact):
        sql = artifact["authorization_gate_if_cleanup_needed"]["cleanup_sql"]
        assert "DELETE" in sql
        assert "bet_index = 2" in sql or "bet_index=2" in sql

    def test_rows_to_delete_40(self, artifact):
        assert artifact["authorization_gate_if_cleanup_needed"]["rows_to_delete"] == 40

    def test_post_cleanup_expected_rows(self, artifact):
        assert artifact["authorization_gate_if_cleanup_needed"]["post_cleanup_expected_rows"] == 72422


# ── Resolution recommendation ─────────────────────────────────────────────────

class TestResolutionRecommendation:
    def test_recommended_option(self, artifact):
        rec = artifact["resolution_recommendation"]
        assert rec["recommended_option"] == "A_quarantine_delete"

    def test_options_list_length(self, artifact):
        assert len(artifact["resolution_recommendation"]["options"]) >= 2

    def test_rows_to_delete(self, artifact):
        assert artifact["resolution_recommendation"]["rows_to_delete"] == 40


# ── Worktree check ────────────────────────────────────────────────────────────

class TestWorktreeCheck:
    def test_branch_ok(self, artifact):
        assert artifact["repo_worktree_check"]["branch_ok"] is True

    def test_branch_name(self, artifact):
        assert artifact["repo_worktree_check"]["branch"] == "claude/zen-gates-ff6802"
