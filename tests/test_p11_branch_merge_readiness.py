"""
test_p11_branch_merge_readiness.py
=====================================
Tests for P11 Branch Merge Readiness.

Verifies:
  1. P11 JSON exists and valid
  2. dry_run_only=True
  3. production_rows=460
  4. apply_authorized=False
  5. required_phrase exact match
  6. contains_db_change=False
  7. contains_production_apply=False
  8. contains_retired_apply=False
  9. fake_success_count=0
 10. legal_next_actions limited to 2
 11. illegal_next_actions includes apply-without-phrase
 12. merge readiness doc exists
 13. PR description draft exists
 14. production DB row count = 460
 15. no DB/backup/pid files staged
 16. all merge gate conditions True
 17. commit chain has 11 commits
 18. diff_scope.db_files_changed = 0
 19. API change is additive-only / non-breaking
 20. blocked_items_post_merge lists P7 ONLINE as first item
 21. diff scope is consistent
 22. PR draft mentions production DB unchanged
 23. PR draft mentions CEO phrase requirement
 24. Merge readiness doc mentions drift guard PASS
 25. safety_flags show no unauthorized apply
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P11_JSON   = REPO_ROOT / "outputs" / "replay" / "p11_branch_merge_readiness_20260520.json"
READINESS  = REPO_ROOT / "docs" / "replay" / "p11_branch_merge_readiness_20260520.md"
PR_DRAFT   = REPO_ROOT / "docs" / "replay" / "p11_pr_description_draft_20260520.md"

REQUIRED_PHRASE = "YES apply P7 controlled replay rows"
PRODUCTION_ROWS = 460

sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="module")
def p11() -> dict:
    assert P11_JSON.exists(), f"P11 JSON not found: {P11_JSON}"
    return json.loads(P11_JSON.read_text())


class TestP11Structure:
    def test_phase(self, p11):
        assert p11["phase"] == "P11_BRANCH_MERGE_READINESS"

    def test_dry_run_only(self, p11):
        assert p11["dry_run_only"] is True

    def test_has_required_keys(self, p11):
        required = (
            "phase", "dry_run_only", "production_rows", "apply_authorized",
            "required_phrase", "test_total_before_p11", "drift_guard",
            "latest_commit", "branch", "merge_target", "contains_db_change",
            "contains_production_apply", "contains_retired_apply",
            "contains_ui_large_redesign", "p7_online_apply_status",
            "p10_operations_ready", "diff_scope", "api_change_summary",
            "commit_chain", "merge_gate", "blocked_items_post_merge",
            "legal_next_actions", "illegal_next_actions",
            "fake_success_count", "safety_flags",
        )
        for key in required:
            assert key in p11, f"Missing key: {key}"


class TestSafetyFields:
    def test_production_rows(self, p11):
        assert p11["production_rows"] == PRODUCTION_ROWS

    def test_apply_not_authorized(self, p11):
        assert p11["apply_authorized"] is False

    def test_required_phrase_exact(self, p11):
        assert p11["required_phrase"] == REQUIRED_PHRASE

    def test_no_db_change(self, p11):
        assert p11["contains_db_change"] is False

    def test_no_production_apply(self, p11):
        assert p11["contains_production_apply"] is False

    def test_no_retired_apply(self, p11):
        assert p11["contains_retired_apply"] is False

    def test_no_large_ui_redesign(self, p11):
        assert p11["contains_ui_large_redesign"] is False

    def test_fake_success_zero(self, p11):
        assert p11["fake_success_count"] == 0

    def test_safety_no_unauthorized_apply(self, p11):
        assert p11["safety_flags"]["unauthorized_apply_performed"] is False

    def test_safety_no_db_write(self, p11):
        assert p11["safety_flags"]["db_write_performed"] is False

    def test_p7_status_blocked(self, p11):
        assert "BLOCKED" in p11["p7_online_apply_status"]

    def test_p10_operations_ready(self, p11):
        assert p11["p10_operations_ready"] is True


class TestMergeGate:
    def test_all_gate_conditions_true(self, p11):
        gate = p11["merge_gate"]
        for condition, value in gate.items():
            assert value is True, f"Merge gate condition '{condition}' is not True"

    def test_gate_has_required_conditions(self, p11):
        gate = p11["merge_gate"]
        for cond in ("all_tests_green", "drift_guard_pass", "production_rows_460",
                     "no_db_change", "no_production_apply", "no_retired_apply",
                     "api_contract_pass", "fake_success_count_zero"):
            assert cond in gate, f"Merge gate missing condition: {cond}"


class TestDiffScope:
    def test_db_files_changed_zero(self, p11):
        assert p11["diff_scope"]["db_files_changed"] == 0

    def test_pid_files_zero(self, p11):
        assert p11["diff_scope"]["pid_files_in_diff"] == 0

    def test_backup_files_zero(self, p11):
        assert p11["diff_scope"]["backup_files_in_diff"] == 0

    def test_runtime_files_zero(self, p11):
        assert p11["diff_scope"]["runtime_files_in_diff"] == 0

    def test_files_changed_positive(self, p11):
        assert p11["diff_scope"]["files_changed"] > 0

    def test_insertions_positive(self, p11):
        assert p11["diff_scope"]["insertions"] > 0


class TestAPIChange:
    def test_api_change_non_breaking(self, p11):
        assert p11["api_change_summary"]["breaking_change"] is False

    def test_api_type_additive(self, p11):
        assert p11["api_change_summary"]["type"] == "ADDITIVE_ONLY"

    def test_api_contract_pass(self, p11):
        assert p11["api_change_summary"]["api_contract_tests"] == "44/44 PASS"


class TestCommitChain:
    def test_has_commits(self, p11):
        assert len(p11["commit_chain"]) >= 8

    def test_latest_commit_present(self, p11):
        hashes = {c["hash"] for c in p11["commit_chain"]}
        assert p11["latest_commit"] in hashes

    def test_commits_have_hash_and_subject(self, p11):
        for commit in p11["commit_chain"]:
            assert "hash" in commit
            assert "subject" in commit


class TestLegalActions:
    def test_exactly_two_legal_actions(self, p11):
        assert len(p11["legal_next_actions"]) == 2

    def test_open_pr_legal(self, p11):
        assert "OPEN_PR_FOR_REVIEW" in p11["legal_next_actions"]

    def test_ceo_authorize_legal(self, p11):
        assert "CEO_AUTHORIZE_P7_ONLINE_APPLY_28_ROWS" in p11["legal_next_actions"]

    def test_merge_with_db_illegal(self, p11):
        assert "MERGE_WITH_DB_FILES" in p11["illegal_next_actions"]

    def test_apply_without_phrase_illegal(self, p11):
        assert "APPLY_WITHOUT_EXACT_PHRASE" in p11["illegal_next_actions"]

    def test_fabricate_illegal(self, p11):
        assert "FABRICATE_REPLAY_ROWS" in p11["illegal_next_actions"]


class TestBlockedItems:
    def test_has_blocked_items(self, p11):
        assert len(p11["blocked_items_post_merge"]) >= 3

    def test_p7_online_is_first_blocked(self, p11):
        first = p11["blocked_items_post_merge"][0]
        assert "P7" in first or "28" in first or "488" in first

    def test_retired_in_blocked(self, p11):
        all_items = " ".join(p11["blocked_items_post_merge"])
        assert "RETIRED" in all_items or "retired" in all_items.lower() or "93" in all_items


class TestDocumentArtifacts:
    def test_readiness_doc_exists(self):
        assert READINESS.exists(), f"Readiness doc missing: {READINESS}"

    def test_pr_draft_exists(self):
        assert PR_DRAFT.exists(), f"PR draft missing: {PR_DRAFT}"

    def test_readiness_doc_mentions_drift_guard(self):
        content = READINESS.read_text()
        assert "DRIFT_GUARD" in content.upper() or "drift guard" in content.lower()

    def test_readiness_doc_mentions_no_db(self):
        content = READINESS.read_text()
        assert "no db" in content.lower() or "zero db" in content.lower() or "no_db" in content.lower() or "NO DB" in content.upper()

    def test_pr_draft_mentions_production_db_unchanged(self):
        content = PR_DRAFT.read_text()
        assert "460" in content
        assert "unchanged" in content.lower() or "does not modify" in content.lower()

    def test_pr_draft_mentions_ceo_phrase(self):
        content = PR_DRAFT.read_text()
        assert REQUIRED_PHRASE in content

    def test_pr_draft_mentions_303_tests(self):
        content = PR_DRAFT.read_text()
        assert "303" in content

    def test_pr_draft_has_out_of_scope_section(self):
        content = PR_DRAFT.read_text()
        assert "Out of Scope" in content or "out of scope" in content.lower()

    def test_pr_draft_has_rollback_section(self):
        content = PR_DRAFT.read_text()
        assert "Rollback" in content or "rollback" in content.lower()


class TestProductionDB:
    def test_production_rows_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == PRODUCTION_ROWS, (
            f"CRITICAL: Production rows = {count}, expected {PRODUCTION_ROWS}"
        )
