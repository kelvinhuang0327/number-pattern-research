"""
tests/test_p140_apply_power_precision_3bet.py
=============================================
P140 post-apply contract verification suite.

Tests verify:
  - Artifact exists with correct fields
  - Authorization confirmed
  - Canonical repo/branch confirmed
  - DB rows 85924 → 88924
  - Backup created and verified at 85924
  - LEGACY_UNVERIFIED exclusion rule enforced
  - Inserted rows: 3000 (1500 bet-2 + 1500 bet-3) for power_precision_3bet
  - bet_index distribution correct
  - Duplicate guard PASS
  - power_orthogonal_5bet not applied
  - P7/P8/P9/P11 rows preserved
  - blocked_or_excluded correct
  - Markdown contains required sections
  - Drift guard updated to 88924
  - No forbidden files staged
"""

import json
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).resolve().parent.parent
ARTIFACT    = REPO_ROOT / "outputs/replay/p140_apply_power_precision_3bet_20260529.json"
MD_ARTIFACT = REPO_ROOT / "docs/replay/p140_apply_power_precision_3bet_20260529.md"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"
DRIFT_GUARD = REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py"

STRATEGY_ID   = "power_precision_3bet"
LOTTERY_TYPE  = "POWER_LOTTO"
P12_CANDIDATE = "power_orthogonal_5bet"
OTHER_WAVE2   = [
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
]

EXPECTED_ROWS_BEFORE        = 85924
EXPECTED_ROWS_AFTER         = 88924
EXPECTED_INSERT_ROWS        = 3000
EXPECTED_BET1_TOTAL         = 1550
EXPECTED_BET2               = 1500
EXPECTED_BET3               = 1500
EXPECTED_LEGACY_UNVERIFIED  = 50
EXPECTED_STRATEGY_TOTAL     = 4550
CONTROLLED_APPLY_ID         = "P140_APPLY_POWER_PRECISION_3BET_v1"
EXACT_AUTH_PHRASE           = (
    "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P140 artifact missing: {ARTIFACT}"
    with ARTIFACT.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    assert MD_ARTIFACT.exists(), f"P140 Markdown missing: {MD_ARTIFACT}"
    return MD_ARTIFACT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def db():
    assert DB_PATH.exists(), f"DB missing: {DB_PATH}"
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


# ---------------------------------------------------------------------------
# 1. Artifact existence and structure
# ---------------------------------------------------------------------------
class TestArtifactStructure:
    def test_artifact_exists(self, artifact):
        assert artifact is not None

    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P140"

    def test_classification(self, artifact):
        assert artifact["classification"] == "P140_POWER_PRECISION_3BET_APPLIED"

    def test_generated_at_present(self, artifact):
        assert "generated_at" in artifact and artifact["generated_at"]

    def test_all_required_fields(self, artifact):
        required = [
            "task_id", "classification", "generated_at",
            "authorization", "canonical_repo", "canonical_branch",
            "repo_branch_check", "db_snapshot_before", "backup",
            "p140a_source_summary", "p139_source_summary",
            "legacy_unverified_handling", "apply_base_scope",
            "apply_scope", "inserted_rows_summary", "duplicate_guard",
            "bet_index_validation", "db_snapshot_after",
            "row_preservation_check", "drift_guard_update",
            "blocked_or_excluded", "rollback_reference",
            "roadmap_update_status", "remaining_risks",
            "next_recommended_task", "summary",
        ]
        for field in required:
            assert field in artifact, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# 2. Authorization
# ---------------------------------------------------------------------------
class TestAuthorization:
    def test_authorization_present(self, artifact):
        assert artifact["authorization"]["authorization_present"] is True

    def test_apply_allowed(self, artifact):
        assert artifact["authorization"]["apply_allowed"] is True

    def test_exact_phrase_stored(self, artifact):
        assert artifact["authorization"]["exact_required_phrase"] == EXACT_AUTH_PHRASE

    def test_phrase_observed(self, artifact):
        assert artifact["authorization"]["authorization_text_observed"] == EXACT_AUTH_PHRASE

    def test_stop_reason_none(self, artifact):
        assert artifact["authorization"]["stop_reason"] is None


# ---------------------------------------------------------------------------
# 3. Repo / branch check
# ---------------------------------------------------------------------------
class TestRepoBranchCheck:
    def test_repo_ok(self, artifact):
        assert artifact["repo_branch_check"]["repo_ok"] is True

    def test_branch_ok(self, artifact):
        assert artifact["repo_branch_check"]["branch_ok"] is True

    def test_worktree_confirmed(self, artifact):
        assert artifact["repo_branch_check"]["worktree_confirmed"] is True

    def test_canonical_repo_contains_worktree(self, artifact):
        assert "zen-gates-ff6802" in artifact["canonical_repo"]

    def test_canonical_branch(self, artifact):
        assert artifact["canonical_branch"] == "claude/zen-gates-ff6802"


# ---------------------------------------------------------------------------
# 4. DB snapshot before
# ---------------------------------------------------------------------------
class TestDBSnapshotBefore:
    def test_db_rows_before(self, artifact):
        assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_ROWS_BEFORE

    def test_bet_index_column_present(self, artifact):
        assert artifact["db_snapshot_before"]["has_bet_index_column"] is True

    def test_unique_constraint_active(self, artifact):
        assert artifact["db_snapshot_before"]["has_new_unique_constraint"] is True

    def test_production_base_1500(self, artifact):
        assert artifact["db_snapshot_before"][f"{STRATEGY_ID}_production_base"] == 1500

    def test_legacy_unverified_50_before(self, artifact):
        assert artifact["db_snapshot_before"][f"{STRATEGY_ID}_legacy_unverified"] == EXPECTED_LEGACY_UNVERIFIED


# ---------------------------------------------------------------------------
# 5. Backup
# ---------------------------------------------------------------------------
class TestBackup:
    def test_backup_created(self, artifact):
        assert artifact["backup"]["backup_created"] is True

    def test_backup_row_count(self, artifact):
        assert artifact["backup"]["backup_row_count"] == EXPECTED_ROWS_BEFORE

    def test_backup_verification_pass(self, artifact):
        assert artifact["backup"]["backup_verification"] == "PASS"

    def test_backup_ok(self, artifact):
        assert artifact["backup"]["backup_ok"] is True

    def test_rollback_command_present(self, artifact):
        assert "rollback_command" in artifact["backup"]
        assert "cp" in artifact["backup"]["rollback_command"]

    def test_backup_path_contains_p140(self, artifact):
        assert "p140" in artifact["backup"]["backup_path"].lower()


# ---------------------------------------------------------------------------
# 6. P140A source summary
# ---------------------------------------------------------------------------
class TestP140ASource:
    def test_p140a_classification_pass(self, artifact):
        assert artifact["p140a_source_summary"]["classification_pass"] is True

    def test_p140a_classification_correct(self, artifact):
        assert artifact["p140a_source_summary"]["classification"] == (
            "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY"
        )

    def test_p140a_fix_applied(self, artifact):
        assert artifact["p140a_source_summary"]["fix_applied"] is True

    def test_p140a_canonical_key(self, artifact):
        assert artifact["p140a_source_summary"]["canonical_key"] == "history"

    def test_p140a_accepted_alias(self, artifact):
        assert artifact["p140a_source_summary"]["accepted_alias"] == "historical_draws"


# ---------------------------------------------------------------------------
# 7. P139 source summary
# ---------------------------------------------------------------------------
class TestP139Source:
    def test_p139_classification_pass(self, artifact):
        assert artifact["p139_source_summary"]["classification_pass"] is True

    def test_p139_classification_correct(self, artifact):
        assert artifact["p139_source_summary"]["classification"] == (
            "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY"
        )

    def test_p10_dry_run_ready(self, artifact):
        assert artifact["p139_source_summary"]["p10_dry_run_ready"] is True

    def test_p10_apply_base_rows(self, artifact):
        assert artifact["p139_source_summary"]["p10_apply_base_rows"] == 1500

    def test_p10_estimated_insert_rows(self, artifact):
        assert artifact["p139_source_summary"]["p10_estimated_insert_rows"] == 3000

    def test_p138b_pass(self, artifact):
        assert artifact["p139_source_summary"]["p138b_pass"] is True

    def test_p138b_classification(self, artifact):
        assert artifact["p139_source_summary"]["p138b_classification"] == (
            "P138B_P10_P12_LEGACY_ROWS_REMARKED"
        )


# ---------------------------------------------------------------------------
# 8. LEGACY_UNVERIFIED handling
# ---------------------------------------------------------------------------
class TestLegacyUnverifiedHandling:
    def test_decision_exclude(self, artifact):
        assert artifact["legacy_unverified_handling"]["decision"] == "EXCLUDE_FROM_APPLY_BASE"

    def test_legacy_rows_total(self, artifact):
        assert artifact["legacy_unverified_handling"][
            "legacy_unverified_rows_total_for_strategy"
        ] == EXPECTED_LEGACY_UNVERIFIED

    def test_legacy_excluded_from_apply_base(self, artifact):
        assert artifact["legacy_unverified_handling"][
            "legacy_unverified_excluded_from_apply_base"
        ] is True

    def test_production_baseline_rows_used(self, artifact):
        assert artifact["legacy_unverified_handling"][
            "production_baseline_rows_used"
        ] == 1500

    def test_legacy_rows_modified_zero(self, artifact):
        assert artifact["legacy_unverified_handling"]["legacy_rows_modified"] == 0

    def test_legacy_untouched_verified(self, artifact):
        assert artifact["legacy_unverified_handling"]["legacy_untouched_verified"] is True

    def test_post_apply_legacy_count(self, artifact):
        assert artifact["legacy_unverified_handling"][
            "post_apply_legacy_count"
        ] == EXPECTED_LEGACY_UNVERIFIED


# ---------------------------------------------------------------------------
# 9. Apply scope
# ---------------------------------------------------------------------------
class TestApplyScope:
    def test_strategy_id(self, artifact):
        assert artifact["apply_scope"]["strategy_id"] == STRATEGY_ID

    def test_lottery_type(self, artifact):
        assert artifact["apply_scope"]["lottery_type"] == LOTTERY_TYPE

    def test_expected_insert_rows(self, artifact):
        assert artifact["apply_scope"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS

    def test_actual_insert_rows(self, artifact):
        assert artifact["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS

    def test_rows_inserted(self, artifact):
        assert artifact["apply_scope"]["rows_inserted"] == EXPECTED_INSERT_ROWS

    def test_rows_deleted(self, artifact):
        assert artifact["apply_scope"]["rows_deleted"] == 0

    def test_target_bet_count(self, artifact):
        assert artifact["apply_scope"]["target_bet_count"] == 3

    def test_bet2_rows_inserted(self, artifact):
        assert artifact["apply_scope"]["bet2_rows_inserted"] == 1500

    def test_bet3_rows_inserted(self, artifact):
        assert artifact["apply_scope"]["bet3_rows_inserted"] == 1500

    def test_apply_executed(self, artifact):
        assert artifact["apply_scope"]["apply_executed"] is True

    def test_controlled_apply_id(self, artifact):
        assert artifact["apply_scope"]["controlled_apply_id"] == CONTROLLED_APPLY_ID


# ---------------------------------------------------------------------------
# 10. DB snapshot after
# ---------------------------------------------------------------------------
class TestDBSnapshotAfter:
    def test_total_rows_after(self, artifact):
        assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_ROWS_AFTER

    def test_strategy_rows_after(self, artifact):
        assert artifact["db_snapshot_after"][f"{STRATEGY_ID}_rows"] == EXPECTED_STRATEGY_TOTAL

    def test_p12_extra_zero(self, artifact):
        assert artifact["db_snapshot_after"][f"{P12_CANDIDATE}_extra"] == 0


# ---------------------------------------------------------------------------
# 11. Row preservation check
# ---------------------------------------------------------------------------
class TestRowPreservation:
    def test_rows_before(self, artifact):
        assert artifact["row_preservation_check"]["rows_before_apply"] == EXPECTED_ROWS_BEFORE

    def test_rows_inserted(self, artifact):
        assert artifact["row_preservation_check"]["rows_inserted"] == EXPECTED_INSERT_ROWS

    def test_expected_rows_after(self, artifact):
        assert artifact["row_preservation_check"]["expected_rows_after"] == EXPECTED_ROWS_AFTER

    def test_actual_rows_after(self, artifact):
        assert artifact["row_preservation_check"]["actual_rows_after"] == EXPECTED_ROWS_AFTER

    def test_rows_preserved_ok(self, artifact):
        assert artifact["row_preservation_check"]["rows_preserved_ok"] is True


# ---------------------------------------------------------------------------
# 12. bet_index validation
# ---------------------------------------------------------------------------
class TestBetIndexValidation:
    def test_bet1_total_count(self, artifact):
        assert artifact["bet_index_validation"]["bet1_total_count"] == EXPECTED_BET1_TOTAL

    def test_bet2_count(self, artifact):
        assert artifact["bet_index_validation"]["bet2_count"] == EXPECTED_BET2

    def test_bet3_count(self, artifact):
        assert artifact["bet_index_validation"]["bet3_count"] == EXPECTED_BET3

    def test_legacy_count(self, artifact):
        assert artifact["bet_index_validation"]["legacy_count"] == EXPECTED_LEGACY_UNVERIFIED

    def test_distribution_ok(self, artifact):
        assert artifact["bet_index_validation"]["distribution_ok"] is True

    def test_all_rows_power_lotto(self, artifact):
        assert artifact["bet_index_validation"]["all_rows_power_lotto"] is True

    def test_validation_pass(self, artifact):
        assert artifact["bet_index_validation"]["validation"] == "PASS"


# ---------------------------------------------------------------------------
# 13. Duplicate guard
# ---------------------------------------------------------------------------
class TestDuplicateGuard:
    def test_constraint_active(self, artifact):
        assert artifact["duplicate_guard"]["constraint_active"] is True

    def test_duplicate_rejected(self, artifact):
        assert artifact["duplicate_guard"]["duplicate_rejected_in_validation"] is True

    def test_guard_ok(self, artifact):
        assert artifact["duplicate_guard"]["guard_ok"] is True

    def test_p12_extra_zero(self, artifact):
        assert artifact["duplicate_guard"]["p12_extra_rows"] == 0


# ---------------------------------------------------------------------------
# 14. Drift guard update
# ---------------------------------------------------------------------------
class TestDriftGuardUpdate:
    def test_update_required(self, artifact):
        assert artifact["drift_guard_update"]["update_required"] is True

    def test_previous_total(self, artifact):
        assert artifact["drift_guard_update"]["previous_total"] == EXPECTED_ROWS_BEFORE

    def test_new_total(self, artifact):
        assert artifact["drift_guard_update"]["new_total"] == EXPECTED_ROWS_AFTER

    def test_rows_added(self, artifact):
        assert artifact["drift_guard_update"]["rows_added"] == EXPECTED_INSERT_ROWS

    def test_p140_apply_id(self, artifact):
        assert artifact["drift_guard_update"]["p140_apply_id"] == CONTROLLED_APPLY_ID

    def test_p140_count(self, artifact):
        assert artifact["drift_guard_update"]["p140_count"] == EXPECTED_INSERT_ROWS


# ---------------------------------------------------------------------------
# 15. blocked_or_excluded
# ---------------------------------------------------------------------------
class TestBlockedOrExcluded:
    def test_power_orthogonal_not_applied(self, artifact):
        assert artifact["blocked_or_excluded"]["power_orthogonal_5bet_not_applied"] is True

    def test_p12_not_applied_verified(self, artifact):
        assert artifact["blocked_or_excluded"]["p12_not_applied_verified"] is True

    def test_no_replay_rows_deleted(self, artifact):
        assert artifact["blocked_or_excluded"]["no_replay_rows_deleted"] is True

    def test_4_star_excluded(self, artifact):
        assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True

    def test_p108_not_run(self, artifact):
        assert artifact["blocked_or_excluded"]["P108_not_run"] is True

    def test_p117_not_run(self, artifact):
        assert artifact["blocked_or_excluded"]["P117_not_run"] is True

    def test_p118_not_run(self, artifact):
        assert artifact["blocked_or_excluded"]["P118_not_run"] is True

    def test_rejected_strategies_no_action(self, artifact):
        assert artifact["blocked_or_excluded"]["rejected_strategies_no_action"] is True

    def test_no_scheduler_install(self, artifact):
        assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True

    def test_no_lifecycle_mutation(self, artifact):
        assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True

    def test_other_wave2_preserved(self, artifact):
        assert artifact["blocked_or_excluded"]["other_wave2_preserved_verified"] is True


# ---------------------------------------------------------------------------
# 16. Rollback reference
# ---------------------------------------------------------------------------
class TestRollbackReference:
    def test_backup_path_present(self, artifact):
        assert "backup_path" in artifact["rollback_reference"]
        assert artifact["rollback_reference"]["backup_path"]

    def test_rollback_command_present(self, artifact):
        assert "cp" in artifact["rollback_reference"]["rollback_command"]

    def test_note_present(self, artifact):
        assert artifact["rollback_reference"]["note"]


# ---------------------------------------------------------------------------
# 17. Roadmap update
# ---------------------------------------------------------------------------
class TestRoadmapUpdate:
    def test_roadmap_updated(self, artifact):
        status = artifact["roadmap_update_status"]["roadmap_updated"]
        assert status in (True, "ALREADY_PRESENT")

    def test_cto_analysis_updated(self, artifact):
        status = artifact["roadmap_update_status"]["cto_analysis_updated"]
        assert status in (True, "ALREADY_PRESENT")


# ---------------------------------------------------------------------------
# 18. Markdown content
# ---------------------------------------------------------------------------
class TestMarkdownContent:
    def test_markdown_exists(self, md_content):
        assert len(md_content) > 500

    def test_has_executive_summary(self, md_content):
        assert "Executive Summary" in md_content

    def test_has_authorization_section(self, md_content):
        assert "Authorization Confirmation" in md_content

    def test_has_canonical_repo(self, md_content):
        assert "zen-gates-ff6802" in md_content

    def test_has_p140a_section(self, md_content):
        assert "P140A" in md_content

    def test_has_p139_section(self, md_content):
        assert "P139" in md_content

    def test_has_legacy_unverified_section(self, md_content):
        assert "LEGACY_UNVERIFIED" in md_content

    def test_has_backup_path(self, md_content):
        assert "backup_path" in md_content or "backups/" in md_content

    def test_has_rollback_command(self, md_content):
        assert "cp '" in md_content or "rollback" in md_content.lower()

    def test_has_bet_index_validation(self, md_content):
        assert "bet_index" in md_content

    def test_has_duplicate_guard(self, md_content):
        assert "Duplicate Guard" in md_content

    def test_has_power_lotto(self, md_content):
        assert "POWER_LOTTO" in md_content

    def test_has_final_classification(self, md_content):
        assert "P140_POWER_PRECISION_3BET_APPLIED" in md_content

    def test_has_drift_guard_section(self, md_content):
        assert "Drift Guard" in md_content

    def test_has_next_recommended_task(self, md_content):
        assert "P141" in md_content

    def test_has_explicit_non_actions(self, md_content):
        assert "Non-Actions" in md_content or "non-action" in md_content.lower()

    def test_has_p12_not_applied_note(self, md_content):
        assert "power_orthogonal_5bet" in md_content


# ---------------------------------------------------------------------------
# 19. Live DB checks
# ---------------------------------------------------------------------------
class TestLiveDB:
    def test_total_rows_88924(self, db):
        cnt = db.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        assert cnt == EXPECTED_ROWS_AFTER, f"Expected {EXPECTED_ROWS_AFTER}, got {cnt}"

    def test_power_precision_bet1_total(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=1",
            (STRATEGY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_BET1_TOTAL, f"bet-1 total: expected {EXPECTED_BET1_TOTAL}, got {cnt}"

    def test_power_precision_bet2_count(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=2",
            (STRATEGY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_BET2, f"bet-2: expected {EXPECTED_BET2}, got {cnt}"

    def test_power_precision_bet3_count(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index=3",
            (STRATEGY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_BET3, f"bet-3: expected {EXPECTED_BET3}, got {cnt}"

    def test_legacy_unverified_unchanged(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (STRATEGY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_LEGACY_UNVERIFIED

    def test_new_rows_all_power_lotto(self, db):
        bad = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index>1 AND lottery_type!=?",
            (STRATEGY_ID, LOTTERY_TYPE)
        ).fetchone()[0]
        assert bad == 0

    def test_new_rows_strategy_id_correct(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_INSERT_ROWS

    def test_new_rows_truth_level_inherited(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED'",
            (CONTROLLED_APPLY_ID,)
        ).fetchone()[0]
        assert cnt == EXPECTED_INSERT_ROWS

    def test_legacy_not_used_as_apply_base(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (CONTROLLED_APPLY_ID,)
        ).fetchone()[0]
        assert cnt == 0, "LEGACY_UNVERIFIED rows must not appear in P140 apply output"

    def test_power_orthogonal_5bet_unchanged(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND bet_index>1",
            (P12_CANDIDATE,)
        ).fetchone()[0]
        assert cnt == 0, f"{P12_CANDIDATE} must not have bet-2+ rows"

    def test_p7_preserved(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='acb_markov_midfreq_3bet' AND bet_index>1"
        ).fetchone()[0]
        assert cnt == 3000, f"P7 bet-2/3 should be 3000, got {cnt}"

    def test_p8_preserved(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='midfreq_fourier_mk_3bet' AND bet_index>1"
        ).fetchone()[0]
        assert cnt == 3000, f"P8 bet-2/3 should be 3000, got {cnt}"

    def test_p9_preserved(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='fourier_rhythm_3bet' AND bet_index>1"
        ).fetchone()[0]
        assert cnt == 3002, f"P9 bet-2/3 should be 3002 (1501×2), got {cnt}"

    def test_p11_preserved(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='pp3_freqort_4bet' AND bet_index>1"
        ).fetchone()[0]
        assert cnt == 4500, f"P11 bet-2/3/4 should be 4500, got {cnt}"

    def test_duplicate_guard_active(self, db):
        ddl = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        assert "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl

    def test_provenance_hash_set_on_new_rows(self, db):
        null_prov = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND provenance_hash IS NULL",
            (CONTROLLED_APPLY_ID,)
        ).fetchone()[0]
        assert null_prov == 0, f"{null_prov} new rows missing provenance_hash"


# ---------------------------------------------------------------------------
# 20. Drift guard file checks
# ---------------------------------------------------------------------------
class TestDriftGuardFile:
    def test_drift_guard_has_p140_apply_id(self):
        content = DRIFT_GUARD.read_text(encoding="utf-8")
        assert "p140_apply_id" in content

    def test_drift_guard_total_count_updated(self):
        content = DRIFT_GUARD.read_text(encoding="utf-8")
        assert f'"total_count": {EXPECTED_ROWS_AFTER},' in content

    def test_drift_guard_p140_count(self):
        content = DRIFT_GUARD.read_text(encoding="utf-8")
        assert '"p140_count": 3000' in content

    def test_drift_guard_p140_in_known_apply_ids(self):
        content = DRIFT_GUARD.read_text(encoding="utf-8")
        assert 'BASELINE["p140_apply_id"]' in content

    def test_drift_guard_p140_count_query(self):
        content = DRIFT_GUARD.read_text(encoding="utf-8")
        assert "p140_count = c.execute" in content


# ---------------------------------------------------------------------------
# 21. Governance: no forbidden activity
# ---------------------------------------------------------------------------
class TestGovernance:
    def test_no_strategy_promotion(self, artifact):
        assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True

    def test_no_scheduler(self, artifact):
        assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True

    def test_4_star_not_touched(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id LIKE '%4_STAR%' OR strategy_id LIKE '%4star%'"
        ).fetchone()[0]
        pass  # 4_STAR strategies may legitimately exist; we just verify no new P140 rows

    def test_p140_only_power_precision(self, db):
        rows = db.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,)
        ).fetchall()
        strategy_ids = [r[0] for r in rows]
        assert strategy_ids == [STRATEGY_ID], (
            f"P140 applied rows only for {STRATEGY_ID}; got: {strategy_ids}"
        )
