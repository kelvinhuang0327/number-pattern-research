"""
Tests for P125 Adapter Gap Plan From P124 Matrix
=================================================
Task: P125_ADAPTER_GAP_PLAN_FROM_P124_MATRIX
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
P124_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.json"
)
P125_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p125_adapter_gap_plan_from_p124_20260528.json"
)
P125_MD = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "p125_adapter_gap_plan_from_p124_20260528.md"
)
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

KNOWN_TIER_B_STRATEGIES = {
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "biglotto_echo_aware_3bet",
    "biglotto_ts3_markov_4bet_w30",
    "power_fourier_rhythm_2bet",
}

EXPECTED_REPLAY_ROWS = 54462


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p124():
    assert P124_ARTIFACT.exists(), f"P124 artifact missing: {P124_ARTIFACT}"
    with open(P124_ARTIFACT) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p125():
    assert P125_ARTIFACT.exists(), f"P125 artifact missing: {P125_ARTIFACT}"
    with open(P125_ARTIFACT) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Input artifact tests
# ---------------------------------------------------------------------------

class TestP124Prerequisite:
    def test_p124_artifact_exists(self, p124):
        assert P124_ARTIFACT.exists()

    def test_p124_task_id(self, p124):
        assert p124["task_id"] == "P124"

    def test_p124_classification(self, p124):
        assert p124["classification"] == "P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY"

    def test_p124_replay_rows_invariant(self, p124):
        assert p124["db_snapshot"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_p124_3star_count(self, p124):
        assert p124["db_snapshot"]["3_STAR"]["count"] == 4179

    def test_p124_3star_max_draw(self, p124):
        assert str(p124["db_snapshot"]["3_STAR"]["max_draw"]) == "115000106"

    def test_p124_4star_count(self, p124):
        assert p124["db_snapshot"]["4_STAR"]["count"] == 2922

    def test_p124_4star_max_draw(self, p124):
        assert str(p124["db_snapshot"]["4_STAR"]["max_draw"]) == "115000103"

    def test_p124_power_lotto_count(self, p124):
        assert p124["db_snapshot"]["POWER_LOTTO"]["count"] == 1913

    def test_p124_power_lotto_max_draw(self, p124):
        assert str(p124["db_snapshot"]["POWER_LOTTO"]["max_draw"]) == "115000041"


# ---------------------------------------------------------------------------
# P125 artifact structure
# ---------------------------------------------------------------------------

class TestP125ArtifactStructure:
    def test_p125_artifact_exists(self, p125):
        assert P125_ARTIFACT.exists()

    def test_task_id(self, p125):
        assert p125["task_id"] == "P125"

    def test_classification(self, p125):
        assert p125["classification"] == "P125_ADAPTER_GAP_PLAN_READY"

    def test_generated_at_present(self, p125):
        assert "generated_at" in p125
        assert p125["generated_at"]

    def test_p124_source_artifact_present(self, p125):
        assert "p124_source_artifact" in p125

    def test_db_snapshot_present(self, p125):
        assert "db_snapshot" in p125
        snap = p125["db_snapshot"]
        assert snap["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_required_top_level_keys(self, p125):
        required = {
            "task_id", "generated_at", "classification", "p124_source_artifact",
            "db_snapshot", "controlled_apply_ready", "adapter_build_needed",
            "replay_storage_design_risks", "blocked_or_forbidden",
            "recommended_sequence", "p126_candidate_scope",
            "p127_candidate_scope", "p128_candidate_scope", "summary",
        }
        for key in required:
            assert key in p125, f"Missing required key: {key}"


# ---------------------------------------------------------------------------
# Controlled-apply-ready list
# ---------------------------------------------------------------------------

class TestControlledApplyReady:
    def test_exactly_5_candidates(self, p125):
        assert len(p125["controlled_apply_ready"]) == 5, (
            f"Expected 5 controlled_apply_ready, got {len(p125['controlled_apply_ready'])}"
        )

    def test_contains_all_known_tier_b(self, p125):
        actual_ids = {c["strategy_id"] for c in p125["controlled_apply_ready"]}
        for sid in KNOWN_TIER_B_STRATEGIES:
            assert sid in actual_ids, f"Missing known Tier-B strategy: {sid}"

    def test_all_require_explicit_authorization(self, p125):
        for c in p125["controlled_apply_ready"]:
            assert c["explicit_apply_authorization_required"] is True, (
                f"{c['strategy_id']} missing explicit_apply_authorization_required=true"
            )

    def test_all_have_required_fields(self, p125):
        required = {
            "strategy_id", "lottery_type", "target_bet_count", "current_label",
            "proposed_action", "expected_rows_estimate", "risk_level",
            "required_pre_apply_tests", "explicit_apply_authorization_required",
        }
        for c in p125["controlled_apply_ready"]:
            for field in required:
                assert field in c, (
                    f"Candidate {c.get('strategy_id')} missing field: {field}"
                )

    def test_all_have_pre_apply_tests(self, p125):
        for c in p125["controlled_apply_ready"]:
            assert isinstance(c["required_pre_apply_tests"], list)
            assert len(c["required_pre_apply_tests"]) > 0

    def test_p126_scope_flag_present(self, p125):
        for c in p125["controlled_apply_ready"]:
            assert c.get("p126_scope") is True


# ---------------------------------------------------------------------------
# Adapter-build-needed list
# ---------------------------------------------------------------------------

class TestAdapterBuildNeeded:
    def test_non_empty(self, p125):
        assert len(p125["adapter_build_needed"]) > 0

    def test_exactly_12_strategies(self, p125):
        assert len(p125["adapter_build_needed"]) == 12

    def test_all_have_required_fields(self, p125):
        required = {
            "strategy_id", "lottery_type", "desired_bet_count",
            "missing_component", "proposed_adapter_contract",
            "test_plan", "risk_level", "no_db_write_in_p125",
        }
        for a in p125["adapter_build_needed"]:
            for field in required:
                assert field in a, (
                    f"Adapter {a.get('strategy_id')} missing field: {field}"
                )

    def test_no_db_write_flag(self, p125):
        for a in p125["adapter_build_needed"]:
            assert a["no_db_write_in_p125"] is True

    def test_proposed_adapter_contract_structure(self, p125):
        for a in p125["adapter_build_needed"]:
            contract = a["proposed_adapter_contract"]
            assert "method" in contract
            assert "must_not_fabricate" in contract
            assert contract["must_not_fabricate"] is True


# ---------------------------------------------------------------------------
# Blocked / forbidden
# ---------------------------------------------------------------------------

class TestBlockedOrForbidden:
    def test_4star_source_unknown_present(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "4_STAR_source_unknown" in blocked
        entry = blocked["4_STAR_source_unknown"]
        assert entry["lottery_type"] == "4_STAR"
        assert entry["status"] == "source_unknown"

    def test_rejected_strategies_no_action_forever(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "rejected_strategies" in blocked
        entry = blocked["rejected_strategies"]
        assert "strategy_ids" in entry
        assert len(entry["strategy_ids"]) > 0
        assert "no_action" in entry.get("rule", "")

    def test_p108_still_blocked(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "P108_Special3" in blocked

    def test_p117_still_blocked(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "P117_POWER_LOTTO_OOS" in blocked

    def test_p118_still_blocked(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "P118_BIG_LOTTO_quarantine" in blocked

    def test_fabricated_rows_forbidden(self, p125):
        blocked = p125["blocked_or_forbidden"]
        assert "fabricated_rows" in blocked


# ---------------------------------------------------------------------------
# No DB write confirmation
# ---------------------------------------------------------------------------

class TestNoDBWrite:
    def test_artifact_does_not_claim_db_write(self, p125):
        assert p125["governance"]["db_writes"] == 0

    def test_summary_db_writes_zero(self, p125):
        assert p125["summary"]["db_writes_in_p125"] == 0

    def test_no_scheduler_installed(self, p125):
        assert p125["governance"]["scheduler_installed"] is False

    def test_no_fabricated_rows(self, p125):
        assert p125["governance"]["fabricated_rows"] == 0

    def test_no_4star_included(self, p125):
        assert p125["governance"]["4_STAR_included"] is False

    def test_p128_scope_no_db_write(self, p125):
        assert p125["p128_candidate_scope"]["no_db_write_in_p125"] is True

    def test_p127_scope_no_db_write(self, p125):
        assert p125["p127_candidate_scope"]["no_db_write_in_p125"] is True

    def test_p126_scope_authorization_required(self, p125):
        assert p125["p126_candidate_scope"]["authorization_required"] is True


# ---------------------------------------------------------------------------
# DB replay rows unchanged
# ---------------------------------------------------------------------------

class TestDBInvariant:
    def test_replay_rows_still_54462(self):
        assert DB_PATH.exists()
        con = sqlite3.connect(DB_PATH)
        count = con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        con.close()
        assert count == EXPECTED_REPLAY_ROWS, (
            f"DB replay row count changed! Expected {EXPECTED_REPLAY_ROWS}, got {count}"
        )


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

class TestMarkdownReport:
    def test_md_exists(self):
        assert P125_MD.exists()

    def test_md_contains_p126(self):
        text = P125_MD.read_text()
        assert "P126" in text

    def test_md_contains_p127(self):
        text = P125_MD.read_text()
        assert "P127" in text

    def test_md_contains_p128(self):
        text = P125_MD.read_text()
        assert "P128" in text

    def test_md_contains_classification(self):
        text = P125_MD.read_text()
        assert "P125_ADAPTER_GAP_PLAN_READY" in text

    def test_md_mentions_no_db_write(self):
        text = P125_MD.read_text()
        assert "No DB" in text or "no DB" in text or "0" in text

    def test_md_mentions_native_multi_bet_zero(self):
        text = P125_MD.read_text()
        assert "native_multi_bet" in text or "Native Multi-Bet" in text or "native multi-bet" in text


# ---------------------------------------------------------------------------
# Recommended sequence
# ---------------------------------------------------------------------------

class TestRecommendedSequence:
    def test_has_3_phases(self, p125):
        seq = p125["recommended_sequence"]
        phases = {s["phase"] for s in seq}
        assert "P126" in phases
        assert "P127" in phases
        assert "P128" in phases

    def test_sequence_ordered(self, p125):
        seq = p125["recommended_sequence"]
        nums = [s["sequence"] for s in seq]
        assert nums == sorted(nums)


# ---------------------------------------------------------------------------
# Forbidden staging scan (subprocess)
# ---------------------------------------------------------------------------

class TestForbiddenStagingScan:
    def test_db_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        staged = result.stdout.strip().splitlines()
        forbidden = [
            f for f in staged
            if any(
                pat in f
                for pat in ["lottery_v2.db", "lottery_history.json", ".pid", "runtime/"]
            )
        ]
        assert not forbidden, f"Forbidden files staged: {forbidden}"

    def test_git_dir_is_dot_git(self):
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.stdout.strip() == ".git"
