"""
P129: bet_index Schema Migration Rehearsal — Test Suite
=======================================================
Tests:
  1.  Artifact existence
  2.  task_id and classification
  3.  production_db_modified == false
  4.  Production DB replay rows before / after == 54462
  5.  Rehearsal DB evidence present
  6.  P128 source summary
  7.  Migration rehearsal steps (18 steps, all OK)
  8.  Schema before (no bet_index)
  9.  Schema after rehearsal (has bet_index, new UNIQUE)
  10. bet_index default validation
  11. Unique constraint validation
  12. Replay row preservation (54462 in rehearsal)
  13. P126 apply dependency (blocked until production migration)
  14. Production migration checklist
  15. Required authorization phrases
  16. Blocked / excluded items
  17. Pre-migration duplicate audit (key rehearsal finding)
  18. Markdown content
  19. Idempotency
  20. No forbidden files staged
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
P129_JSON = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
P129_MD   = REPO_ROOT / "docs/replay/p129_bet_index_schema_migration_rehearsal_20260528.md"
P129_SCRIPT = REPO_ROOT / "scripts/p129_bet_index_schema_migration_rehearsal.py"
P128_JSON = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
DB_PATH   = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_NEW_ROWS    = 18000
EXPECTED_TOTAL_AFTER = 72462

FORBIDDEN_STAGE_PATTERNS = [
    "lottery_api/data/lottery_v2.db",
    "lottery_api/data/lottery_history.json",
    "backend.pid",
    "frontend.pid",
    "runtime/",
]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert P129_JSON.exists(), f"P129 JSON not found: {P129_JSON}"
    with open(P129_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestArtifactExistence:
    def test_json_exists(self):
        assert P129_JSON.exists(), f"Missing: {P129_JSON}"

    def test_md_exists(self):
        assert P129_MD.exists(), f"Missing: {P129_MD}"

    def test_script_exists(self):
        assert P129_SCRIPT.exists(), f"Missing: {P129_SCRIPT}"

    def test_p128_source_exists(self):
        assert P128_JSON.exists(), f"Missing P128 source: {P128_JSON}"


# ---------------------------------------------------------------------------
# 2. task_id and classification
# ---------------------------------------------------------------------------
class TestClassification:
    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P129"

    def test_classification(self, artifact):
        assert artifact["classification"] == "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY"

    def test_generated_at_present(self, artifact):
        assert "generated_at" in artifact and artifact["generated_at"]


# ---------------------------------------------------------------------------
# 3. production_db_modified == false
# ---------------------------------------------------------------------------
class TestProductionDBNotModified:
    def test_production_db_modified_false(self, artifact):
        assert artifact["production_db_modified"] is False, \
            "production_db_modified must be false — no production writes allowed"

    def test_snapshot_before_no_bet_index(self, artifact):
        assert artifact["db_snapshot_before"]["has_bet_index_column"] is False

    def test_snapshot_after_no_bet_index_in_production(self, artifact):
        assert artifact["db_snapshot_after"]["has_bet_index_column"] is False


# ---------------------------------------------------------------------------
# 4. Production DB replay rows before / after == 54462
# ---------------------------------------------------------------------------
class TestProductionDBRows:
    def _ro_conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        return conn

    def test_snapshot_before_rows(self, artifact):
        assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_snapshot_after_rows(self, artifact):
        assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_live_production_rows(self):
        conn = self._ro_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == EXPECTED_REPLAY_ROWS, \
            f"Live production rows={count}, expected={EXPECTED_REPLAY_ROWS}"

    def test_production_no_bet_index_column(self):
        conn = self._ro_conn()
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()]
        conn.close()
        assert "bet_index" not in cols, \
            "bet_index exists in production DB — migration may have been run without authorization"


# ---------------------------------------------------------------------------
# 5. Rehearsal DB evidence present
# ---------------------------------------------------------------------------
class TestRehearsalDBEvidence:
    def test_rehearsal_db_path_present(self, artifact):
        assert "rehearsal_db_path" in artifact
        assert artifact["rehearsal_db_path"]

    def test_rehearsal_copy_rows(self, artifact):
        assert artifact["rehearsal_copy_rows"] == EXPECTED_REPLAY_ROWS

    def test_rehearsal_copy_integrity_ok(self, artifact):
        assert artifact["rehearsal_copy_integrity_ok"] is True


# ---------------------------------------------------------------------------
# 6. P128 source summary
# ---------------------------------------------------------------------------
class TestP128SourceSummary:
    def test_p128_summary_present(self, artifact):
        assert "p128_source_summary" in artifact

    def test_p128_classification_ok(self, artifact):
        assert artifact["p128_source_summary"]["classification_ok"] is True

    def test_p128_classification_value(self, artifact):
        assert artifact["p128_source_summary"]["classification"] == \
            "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY"

    def test_p128_option_a_selected(self, artifact):
        assert artifact["p128_source_summary"]["recommended_option"] == "A"

    def test_p128_bet_index_column(self, artifact):
        col = artifact["p128_source_summary"]["bet_index_column"]
        assert "bet_index" in col
        assert "DEFAULT 1" in col or "default 1" in col.lower()

    def test_p128_new_unique_constraint(self, artifact):
        uc = artifact["p128_source_summary"]["new_unique_constraint"]
        assert "bet_index" in uc
        assert "lottery_type" in uc
        assert "strategy_id" in uc

    def test_p128_migration_steps_count(self, artifact):
        assert artifact["p128_source_summary"]["migration_steps_in_p128"] >= 18


# ---------------------------------------------------------------------------
# 7. Migration rehearsal steps
# ---------------------------------------------------------------------------
class TestMigrationRehearsalSteps:
    def test_migration_rehearsal_ok(self, artifact):
        assert artifact["migration_rehearsal_ok"] is True

    def test_migration_steps_count_18(self, artifact):
        assert artifact["migration_rehearsal_steps_count"] == 18

    def test_no_migration_error(self, artifact):
        assert artifact["migration_rehearsal_error"] is None

    def test_all_steps_ok(self, artifact):
        failed = [
            s for s in artifact["migration_rehearsal_steps"]
            if not str(s["status"]).startswith("OK")
        ]
        assert failed == [], f"Failed steps: {failed}"

    def test_step_1_is_pragma(self, artifact):
        step1 = artifact["migration_rehearsal_steps"][0]
        assert step1["step"] == 1
        assert "PRAGMA" in step1["sql"].upper()

    def test_step_has_create_table(self, artifact):
        steps = artifact["migration_rehearsal_steps"]
        assert any("CREATE TABLE" in s["sql"].upper() for s in steps)

    def test_step_has_commit(self, artifact):
        steps = artifact["migration_rehearsal_steps"]
        assert any("COMMIT" in s["sql"].upper() for s in steps)

    def test_step_18_confirms_54462(self, artifact):
        step18 = artifact["migration_rehearsal_steps"][-1]
        assert step18["step"] == 18
        assert "OK" in str(step18["status"])


# ---------------------------------------------------------------------------
# 8. Schema before (no bet_index)
# ---------------------------------------------------------------------------
class TestSchemaBefore:
    def test_schema_before_present(self, artifact):
        assert "schema_before" in artifact

    def test_schema_before_no_bet_index(self, artifact):
        assert artifact["schema_before"]["has_bet_index_column"] is False

    def test_schema_before_old_unique_constraint(self, artifact):
        uc = artifact["schema_before"]["current_unique_constraint"]
        assert "replay_run_id" in uc

    def test_schema_before_has_columns(self, artifact):
        assert len(artifact["schema_before"]["columns"]) >= 20


# ---------------------------------------------------------------------------
# 9. Schema after rehearsal (bet_index present, new UNIQUE)
# ---------------------------------------------------------------------------
class TestSchemaAfterRehearsal:
    def test_schema_after_present(self, artifact):
        assert "schema_after_rehearsal" in artifact

    def test_schema_after_has_bet_index(self, artifact):
        assert artifact["schema_after_rehearsal"]["has_bet_index_column"] is True

    def test_schema_after_new_unique_constraint(self, artifact):
        assert artifact["schema_after_rehearsal"]["has_new_unique_constraint"] is True

    def test_schema_after_has_bet_index_index(self, artifact):
        assert artifact["schema_after_rehearsal"]["has_bet_index_index"] is True

    def test_schema_after_columns_include_bet_index(self, artifact):
        cols = artifact["schema_after_rehearsal"]["columns"]
        assert "bet_index" in cols

    def test_schema_after_ddl_has_bet_index(self, artifact):
        # Check the full_ddl field (ddl_excerpt may be truncated before bet_index appears)
        ddl = artifact["schema_after_rehearsal"].get("full_ddl", artifact["schema_after_rehearsal"]["ddl_excerpt"])
        assert "bet_index" in ddl

    def test_schema_after_ddl_has_new_unique(self, artifact):
        ddl = artifact["schema_after_rehearsal"].get("full_ddl", artifact["schema_after_rehearsal"]["ddl_excerpt"])
        assert "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in ddl


# ---------------------------------------------------------------------------
# 10. bet_index default validation
# ---------------------------------------------------------------------------
class TestBetIndexDefaultValidation:
    def test_validation_ok(self, artifact):
        assert artifact["bet_index_default_validation"]["validation_ok"] is True

    def test_total_rows_preserved(self, artifact):
        assert artifact["bet_index_default_validation"]["total_rows"] == EXPECTED_REPLAY_ROWS

    def test_no_invalid_bet_index(self, artifact):
        assert artifact["bet_index_default_validation"]["rows_with_invalid_bet_index"] == 0

    def test_all_rows_valid(self, artifact):
        assert artifact["bet_index_default_validation"]["all_rows_have_valid_bet_index"] is True

    def test_bet_index_1_rows_present(self, artifact):
        assert artifact["bet_index_default_validation"]["rows_with_bet_index_1"] > 0

    def test_note_mentions_row_number(self, artifact):
        note = artifact["bet_index_default_validation"]["note"]
        assert "ROW_NUMBER" in note or "row_number" in note.lower()


# ---------------------------------------------------------------------------
# 11. Unique constraint validation
# ---------------------------------------------------------------------------
class TestUniqueConstraintValidation:
    def test_validation_ok(self, artifact):
        assert artifact["unique_constraint_validation"]["validation_ok"] is True

    def test_duplicate_rejected(self, artifact):
        assert artifact["unique_constraint_validation"]["duplicate_same_bet_index_rejected"] is True

    def test_different_bet_index_allowed(self, artifact):
        assert artifact["unique_constraint_validation"]["different_bet_index_allowed"] is True

    def test_constraint_works(self, artifact):
        assert artifact["unique_constraint_validation"]["constraint_works_as_expected"] is True


# ---------------------------------------------------------------------------
# 12. Replay row preservation (54462 in rehearsal)
# ---------------------------------------------------------------------------
class TestReplayRowPreservation:
    def test_check_ok(self, artifact):
        assert artifact["replay_row_preservation_check"]["check_ok"] is True

    def test_expected_rows(self, artifact):
        assert artifact["replay_row_preservation_check"]["expected_rows"] == EXPECTED_REPLAY_ROWS

    def test_actual_rows(self, artifact):
        assert artifact["replay_row_preservation_check"]["actual_rows_after_migration"] == EXPECTED_REPLAY_ROWS

    def test_rows_preserved(self, artifact):
        assert artifact["replay_row_preservation_check"]["rows_preserved"] is True


# ---------------------------------------------------------------------------
# 13. P126 apply dependency (blocked until production migration)
# ---------------------------------------------------------------------------
class TestP126ApplyDependency:
    def test_p126_dependency_present(self, artifact):
        assert "p126_apply_dependency" in artifact

    def test_apply_status_blocked(self, artifact):
        status = artifact["p126_apply_dependency"]["apply_status"]
        assert "BLOCKED" in status.upper()

    def test_apply_blocked_until_mentions_migration(self, artifact):
        reason = artifact["p126_apply_dependency"]["apply_blocked_until"]
        assert "migration" in reason.lower() or "authorized" in reason.lower()

    def test_total_new_rows(self, artifact):
        assert artifact["p126_apply_dependency"]["total_new_rows_if_applied"] == EXPECTED_NEW_ROWS

    def test_total_after_apply(self, artifact):
        assert artifact["p126_apply_dependency"]["total_rows_after_apply"] == EXPECTED_TOTAL_AFTER

    def test_5_candidates_present(self, artifact):
        assert len(artifact["p126_apply_dependency"]["candidates"]) == 5

    @pytest.mark.parametrize("strategy", [
        "biglotto_echo_aware_3bet",
        "daily539_f4cold_5bet",
        "daily539_f4cold_3bet",
        "power_fourier_rhythm_2bet",
        "biglotto_ts3_markov_4bet_w30",
    ])
    def test_candidate_present(self, artifact, strategy):
        candidates = artifact["p126_apply_dependency"]["candidates"]
        ids = [c["strategy_id"] for c in candidates]
        assert strategy in ids, f"Missing candidate: {strategy}"


# ---------------------------------------------------------------------------
# 14. Production migration checklist
# ---------------------------------------------------------------------------
class TestProductionMigrationChecklist:
    def test_checklist_present(self, artifact):
        assert "production_migration_checklist" in artifact

    def test_checklist_has_entries(self, artifact):
        assert len(artifact["production_migration_checklist"]) >= 10

    def test_checklist_has_backup_step(self, artifact):
        checks = [c["check"].lower() for c in artifact["production_migration_checklist"]]
        assert any("backup" in c for c in checks)

    def test_checklist_has_authorization_step(self, artifact):
        checks = [c["check"].lower() for c in artifact["production_migration_checklist"]]
        assert any("authorization" in c or "authorize" in c for c in checks)

    def test_checklist_has_integrity_check(self, artifact):
        details = [c["detail"].lower() for c in artifact["production_migration_checklist"]]
        assert any("integrity" in d for d in details)

    def test_checklist_seq_ordered(self, artifact):
        seqs = [c["seq"] for c in artifact["production_migration_checklist"]]
        assert seqs == sorted(seqs)

    def test_migration_execution_blocked_in_checklist(self, artifact):
        blocked = [c for c in artifact["production_migration_checklist"]
                   if "BLOCKED" in str(c.get("status", "")).upper()
                   or "REQUIRED" in str(c.get("status", "")).upper()]
        assert len(blocked) >= 3


# ---------------------------------------------------------------------------
# 15. Required authorization phrases
# ---------------------------------------------------------------------------
class TestRequiredAuthorizationPhrases:
    def test_phrases_present(self, artifact):
        assert "required_authorization_phrases" in artifact

    def test_migration_auth_phrase_present(self, artifact):
        phrases = artifact["required_authorization_phrases"]
        assert any("authorize migration_plan_p128" in p.lower() or "migration" in p.lower()
                   for p in phrases)

    def test_migration_phrase_exact_format(self, artifact):
        phrases = artifact["required_authorization_phrases"]
        assert any("YES authorize migration_plan_p128 because" in p for p in phrases), \
            f"Missing exact migration auth phrase in: {phrases}"


# ---------------------------------------------------------------------------
# 16. Blocked / excluded items
# ---------------------------------------------------------------------------
class TestBlockedExcluded:
    def test_blocked_present(self, artifact):
        assert "blocked_or_excluded" in artifact

    def test_4star_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "4_STAR" in items

    def test_p108_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "P108" in items

    def test_p117_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "P117" in items

    def test_p118_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "P118" in items

    def test_rejected_strategies_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "rejected_strategies" in items

    def test_production_db_writes_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert any("production" in i.lower() or "db_write" in i.lower() for i in items)

    def test_p126_apply_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "p126_apply" in items


# ---------------------------------------------------------------------------
# 17. Pre-migration duplicate audit (key rehearsal finding)
# ---------------------------------------------------------------------------
class TestPreMigrationDuplicateAudit:
    def test_audit_present(self, artifact):
        assert "pre_migration_duplicate_audit" in artifact

    def test_duplicate_groups_count(self, artifact):
        assert artifact["pre_migration_duplicate_audit"]["duplicate_groups_count"] == 120

    def test_extra_rows_count(self, artifact):
        assert artifact["pre_migration_duplicate_audit"]["extra_rows_count"] == 160

    def test_p128_copy_sql_refinement_required(self, artifact):
        assert artifact["pre_migration_duplicate_audit"]["p128_copy_sql_refinement_required"] is True

    def test_resolution_mentions_row_number(self, artifact):
        res = artifact["pre_migration_duplicate_audit"]["resolution"]
        assert "ROW_NUMBER" in res

    def test_rows_preserved_after_refinement(self, artifact):
        assert artifact["pre_migration_duplicate_audit"]["rows_preserved_after_refinement"] == EXPECTED_REPLAY_ROWS

    def test_strategies_affected_present(self, artifact):
        affected = artifact["pre_migration_duplicate_audit"]["strategies_affected"]
        assert len(affected) >= 4

    def test_root_cause_explains_null_uniqueness(self, artifact):
        root = artifact["pre_migration_duplicate_audit"]["root_cause"]
        assert "replay_run_id" in root or "NULL" in root


# ---------------------------------------------------------------------------
# 18. Markdown content
# ---------------------------------------------------------------------------
class TestMarkdownContent:
    @pytest.fixture(scope="class")
    def md(self):
        assert P129_MD.exists()
        return P129_MD.read_text()

    def test_classification_in_md(self, md):
        assert "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY" in md

    def test_executive_summary_in_md(self, md):
        assert "Executive Summary" in md or "executive" in md.lower()

    def test_production_non_action_in_md(self, md):
        assert "Production DB Non-Action" in md or "production_db_modified" in md.lower() or "NOT modified" in md

    def test_rehearsal_steps_in_md(self, md):
        assert "Rehearsal DB Steps" in md or "rehearsal" in md.lower()

    def test_schema_before_after_in_md(self, md):
        assert "Schema Before" in md and "Schema After" in md

    def test_bet_index_in_md(self, md):
        assert "bet_index" in md

    def test_unique_constraint_in_md(self, md):
        assert "UNIQUE" in md.upper() and "bet_index" in md

    def test_54462_in_md(self, md):
        assert "54462" in md

    def test_production_checklist_in_md(self, md):
        assert "Production Migration Checklist" in md or "migration checklist" in md.lower()

    def test_auth_phrase_in_md(self, md):
        assert "YES authorize migration_plan_p128 because" in md

    def test_explicit_non_actions_in_md(self, md):
        assert "Non-Action" in md or "non-action" in md.lower() or "NOT" in md

    def test_4star_excluded_in_md(self, md):
        assert "4_STAR" in md

    def test_p108_excluded_in_md(self, md):
        assert "P108" in md

    def test_p126_blocked_in_md(self, md):
        assert "BLOCKED" in md.upper()

    def test_duplicate_audit_finding_in_md(self, md):
        assert "ROW_NUMBER" in md or "duplicate" in md.lower()

    def test_18000_new_rows_in_md(self, md):
        assert "18,000" in md or "18000" in md


# ---------------------------------------------------------------------------
# 19. Idempotency
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_script_reruns_cleanly(self):
        result = subprocess.run(
            [sys.executable, "scripts/p129_bet_index_schema_migration_rehearsal.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed on re-run:\n{result.stderr}"
        assert "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY" in result.stdout
        assert "DONE" in result.stdout

    def test_json_stable_after_rerun(self):
        with open(P129_JSON) as f:
            before = json.load(f)

        subprocess.run(
            [sys.executable, "scripts/p129_bet_index_schema_migration_rehearsal.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        with open(P129_JSON) as f:
            after = json.load(f)

        assert before["task_id"] == after["task_id"]
        assert before["classification"] == after["classification"]
        assert before["production_db_modified"] == after["production_db_modified"] is False
        assert before["db_snapshot_before"]["replay_rows"] == after["db_snapshot_before"]["replay_rows"] == EXPECTED_REPLAY_ROWS


# ---------------------------------------------------------------------------
# 20. No forbidden files staged
# ---------------------------------------------------------------------------
class TestForbiddenFilesNotStaged:
    def test_no_forbidden_files_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        staged = result.stdout.strip()
        if not staged:
            return
        for forbidden in FORBIDDEN_STAGE_PATTERNS:
            for line in staged.splitlines():
                assert forbidden not in line, \
                    f"Forbidden file staged: {line} (pattern: {forbidden})"

    def test_db_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert "lottery_v2.db" not in result.stdout

    def test_history_json_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert "lottery_history.json" not in result.stdout
