"""
P129A: Production Migration Authorization Gate — Test Suite
===========================================================
Tests:
  1.  Artifact existence
  2.  task_id and classification (WAITING)
  3.  P129 source artifact valid
  4.  Production DB rows before / after == 54462
  5.  production_db_modified == false
  6.  migration_execution_performed == false
  7.  corrected_migration_sql_required == true
  8.  row_number_copy_sql_required == true
  9.  authorization_gate: authorization_present == false, migration_allowed == false
  10. authorization_gate: exact required phrase
  11. authorization_gate: stop_reason present
  12. P126 apply status: blocked
  13. blocked_or_excluded coverage
  14. required_authorization_phrases
  15. rehearsal_findings
  16. Markdown content
  17. Idempotency
  18. No forbidden files staged
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT     = Path(__file__).resolve().parent.parent
P129A_JSON    = REPO_ROOT / "outputs/replay/p129a_production_migration_authorization_gate_20260528.json"
P129A_MD      = REPO_ROOT / "docs/replay/p129a_production_migration_authorization_gate_20260528.md"
P129A_SCRIPT  = REPO_ROOT / "scripts/p129a_production_migration_authorization_gate.py"
P129_JSON     = REPO_ROOT / "outputs/replay/p129_bet_index_schema_migration_rehearsal_20260528.json"
DB_PATH       = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS   = 54462
EXPECTED_NEW_ROWS      = 18000
EXPECTED_TOTAL_AFTER   = 72462
EXACT_AUTH_PHRASE      = "YES authorize migration_plan_p128 because <reason>"
EXPECTED_CLASSIFICATION = "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION"

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
    assert P129A_JSON.exists(), f"P129A JSON not found: {P129A_JSON}"
    with open(P129A_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestArtifactExistence:
    def test_json_exists(self):
        assert P129A_JSON.exists(), f"Missing: {P129A_JSON}"

    def test_md_exists(self):
        assert P129A_MD.exists(), f"Missing: {P129A_MD}"

    def test_script_exists(self):
        assert P129A_SCRIPT.exists(), f"Missing: {P129A_SCRIPT}"

    def test_p129_source_exists(self):
        assert P129_JSON.exists(), f"Missing P129 source: {P129_JSON}"


# ---------------------------------------------------------------------------
# 2. task_id and classification
# ---------------------------------------------------------------------------
class TestClassification:
    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P129A"

    def test_classification_waiting(self, artifact):
        assert artifact["classification"] == EXPECTED_CLASSIFICATION, \
            f"Expected {EXPECTED_CLASSIFICATION}, got {artifact['classification']}"

    def test_generated_at_present(self, artifact):
        assert "generated_at" in artifact and artifact["generated_at"]


# ---------------------------------------------------------------------------
# 3. P129 source artifact valid
# ---------------------------------------------------------------------------
class TestP129SourceValid:
    def test_p129_summary_present(self, artifact):
        assert "p129_source_summary" in artifact

    def test_p129_classification_ok(self, artifact):
        assert artifact["p129_source_summary"]["classification_ok"] is True

    def test_p129_classification_value(self, artifact):
        assert artifact["p129_source_summary"]["classification"] == \
            "P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY"

    def test_p129_migration_ok(self, artifact):
        assert artifact["p129_source_summary"]["migration_rehearsal_ok"] is True

    def test_p129_all_checks_passed(self, artifact):
        assert artifact["p129_source_summary"]["all_checks_passed"] is True

    def test_p129_rows_before(self, artifact):
        assert artifact["p129_source_summary"]["rows_before"] == EXPECTED_REPLAY_ROWS

    def test_p129_rows_after(self, artifact):
        assert artifact["p129_source_summary"]["rows_after"] == EXPECTED_REPLAY_ROWS

    def test_p129_not_modified(self, artifact):
        assert artifact["p129_source_summary"]["production_db_modified_in_p129"] is False


# ---------------------------------------------------------------------------
# 4. Production DB rows before / after == 54462
# ---------------------------------------------------------------------------
class TestProductionDBRows:
    def _ro_conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        return conn

    def test_snapshot_before_rows(self, artifact):
        assert artifact["production_db_snapshot_before"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_snapshot_after_rows(self, artifact):
        assert artifact["production_db_snapshot_after"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_live_production_rows(self):
        conn = self._ro_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == EXPECTED_REPLAY_ROWS, \
            f"Live production rows={count}, expected={EXPECTED_REPLAY_ROWS}"

    def test_production_no_bet_index_before(self, artifact):
        assert artifact["production_db_snapshot_before"]["has_bet_index_column"] is False

    def test_production_no_bet_index_after(self, artifact):
        assert artifact["production_db_snapshot_after"]["has_bet_index_column"] is False

    def test_live_no_bet_index_column(self):
        conn = self._ro_conn()
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(strategy_prediction_replays)"
        ).fetchall()]
        conn.close()
        assert "bet_index" not in cols, \
            "bet_index exists in production DB — migration ran without authorization"


# ---------------------------------------------------------------------------
# 5. production_db_modified == false
# ---------------------------------------------------------------------------
class TestProductionDBNotModified:
    def test_production_db_modified_false(self, artifact):
        assert artifact["production_db_modified"] is False

    def test_snapshots_consistent(self, artifact):
        before = artifact["production_db_snapshot_before"]["replay_rows"]
        after  = artifact["production_db_snapshot_after"]["replay_rows"]
        assert before == after == EXPECTED_REPLAY_ROWS


# ---------------------------------------------------------------------------
# 6. migration_execution_performed == false
# ---------------------------------------------------------------------------
class TestMigrationNotExecuted:
    def test_migration_execution_performed_false(self, artifact):
        assert artifact["migration_execution_performed"] is False


# ---------------------------------------------------------------------------
# 7. corrected_migration_sql_required == true
# ---------------------------------------------------------------------------
class TestCorrectedMigrationSQL:
    def test_corrected_migration_sql_required(self, artifact):
        assert artifact["corrected_migration_sql_required"] is True

    def test_rehearsal_findings_has_corrected_sql(self, artifact):
        findings = artifact["rehearsal_findings"]
        assert "corrected_copy_sql" in findings

    def test_corrected_sql_has_row_number(self, artifact):
        findings = artifact["rehearsal_findings"]
        corrected = findings["corrected_copy_sql"]
        sql = corrected.get("corrected_sql_p129", "")
        assert "ROW_NUMBER" in sql.upper()

    def test_original_sql_p128_fails_note(self, artifact):
        findings = artifact["rehearsal_findings"]
        corrected = findings["corrected_copy_sql"]
        why_fails = corrected.get("why_original_fails", "")
        assert why_fails  # must explain why

    def test_corrected_sql_row_count_preserved(self, artifact):
        findings = artifact["rehearsal_findings"]
        corrected = findings["corrected_copy_sql"]
        assert corrected.get("row_count_preserved") == EXPECTED_REPLAY_ROWS


# ---------------------------------------------------------------------------
# 8. row_number_copy_sql_required == true
# ---------------------------------------------------------------------------
class TestRowNumberRequired:
    def test_row_number_copy_sql_required(self, artifact):
        assert artifact["row_number_copy_sql_required"] is True

    def test_p129_source_marks_refinement(self, artifact):
        assert artifact["p129_source_summary"]["p128_copy_sql_refinement_required"] is True

    def test_p129_source_marks_row_number(self, artifact):
        assert artifact["p129_source_summary"]["row_number_required"] is True


# ---------------------------------------------------------------------------
# 9. authorization_gate: authorization_present == false, migration_allowed == false
# ---------------------------------------------------------------------------
class TestAuthorizationGate:
    def test_gate_present(self, artifact):
        assert "authorization_gate" in artifact

    def test_authorization_present_false(self, artifact):
        assert artifact["authorization_gate"]["authorization_present"] is False

    def test_migration_allowed_false(self, artifact):
        assert artifact["authorization_gate"]["migration_allowed"] is False

    def test_classification_waiting(self, artifact):
        assert artifact["authorization_gate"]["classification"] == EXPECTED_CLASSIFICATION

    def test_stop_reason_present(self, artifact):
        stop = artifact["authorization_gate"]["stop_reason"]
        assert stop and "WAITING" in stop.upper()


# ---------------------------------------------------------------------------
# 10. authorization_gate: exact required phrase
# ---------------------------------------------------------------------------
class TestExactRequiredPhrase:
    def test_exact_phrase_present(self, artifact):
        phrase = artifact["authorization_gate"]["exact_required_phrase"]
        assert phrase == EXACT_AUTH_PHRASE, \
            f"Expected '{EXACT_AUTH_PHRASE}', got '{phrase}'"

    def test_exact_phrase_contains_authorize_migration(self, artifact):
        phrase = artifact["authorization_gate"]["exact_required_phrase"]
        assert "authorize migration_plan_p128" in phrase.lower()

    def test_exact_phrase_contains_because(self, artifact):
        phrase = artifact["authorization_gate"]["exact_required_phrase"]
        assert "because" in phrase.lower()


# ---------------------------------------------------------------------------
# 11. authorization_gate: stop_reason
# ---------------------------------------------------------------------------
class TestStopReason:
    def test_stop_reason_waiting(self, artifact):
        stop = artifact["authorization_gate"]["stop_reason"]
        assert "WAITING" in stop.upper()

    def test_stop_reason_mentions_migration(self, artifact):
        stop = artifact["authorization_gate"]["stop_reason"]
        assert "MIGRATION" in stop.upper() or "AUTHORIZATION" in stop.upper()


# ---------------------------------------------------------------------------
# 12. P126 apply status: blocked
# ---------------------------------------------------------------------------
class TestP126ApplyStatus:
    def test_p126_status_present(self, artifact):
        assert "p126_apply_status" in artifact

    def test_p126_status_blocked(self, artifact):
        status = artifact["p126_apply_status"]["status"]
        assert "BLOCKED" in status.upper()

    def test_p126_blocked_reason_mentions_migration(self, artifact):
        reason = artifact["p126_apply_status"]["reason"]
        assert "migration" in reason.lower() or "schema" in reason.lower()

    def test_p126_total_new_rows(self, artifact):
        assert artifact["p126_apply_status"]["total_new_rows_if_applied"] == EXPECTED_NEW_ROWS

    def test_p126_total_after_apply(self, artifact):
        assert artifact["p126_apply_status"]["total_rows_after_apply"] == EXPECTED_TOTAL_AFTER

    def test_p126_blocked_until_has_migration_step(self, artifact):
        blocked_until = artifact["p126_apply_status"]["apply_blocked_until"]
        assert any("migration" in b.lower() for b in blocked_until)

    def test_p126_blocked_until_has_per_strategy_phrases(self, artifact):
        blocked_until = artifact["p126_apply_status"]["apply_blocked_until"]
        assert any("per-strategy" in b.lower() or "5 phrase" in b.lower()
                   or "authorization phrase" in b.lower() for b in blocked_until)


# ---------------------------------------------------------------------------
# 13. blocked_or_excluded coverage
# ---------------------------------------------------------------------------
class TestBlockedOrExcluded:
    def test_blocked_present(self, artifact):
        assert "blocked_or_excluded" in artifact

    def test_p126_apply_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "p126_apply" in items or any("p126" in i.lower() for i in items)

    def test_4star_excluded(self, artifact):
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

    def test_scheduler_not_installed(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert any("scheduler" in i.lower() for i in items)

    def test_no_lifecycle_mutation(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert any("lifecycle" in i.lower() or "champion" in i.lower()
                   or "registry" in i.lower() for i in items)


# ---------------------------------------------------------------------------
# 14. required_authorization_phrases
# ---------------------------------------------------------------------------
class TestRequiredAuthorizationPhrases:
    def test_phrases_present(self, artifact):
        assert "required_authorization_phrases" in artifact

    def test_migration_auth_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]
        phrase = phrases.get("migration_authorization", "")
        assert phrase == EXACT_AUTH_PHRASE, \
            f"Expected exact phrase, got: '{phrase}'"

    def test_5_per_strategy_phrases(self, artifact):
        phrases = artifact["required_authorization_phrases"]
        per_strat = phrases.get("per_strategy_phrases_also_required_after_migration", [])
        assert len(per_strat) == 5

    @pytest.mark.parametrize("strategy", [
        "biglotto_echo_aware_3bet",
        "daily539_f4cold_5bet",
        "daily539_f4cold_3bet",
        "power_fourier_rhythm_2bet",
        "biglotto_ts3_markov_4bet_w30",
    ])
    def test_per_strategy_phrase_present(self, artifact, strategy):
        phrases = artifact["required_authorization_phrases"]
        per_strat = phrases.get("per_strategy_phrases_also_required_after_migration", [])
        assert any(strategy in p for p in per_strat), \
            f"Missing per-strategy phrase for: {strategy}"


# ---------------------------------------------------------------------------
# 15. rehearsal_findings
# ---------------------------------------------------------------------------
class TestRehearsalFindings:
    def test_findings_present(self, artifact):
        assert "rehearsal_findings" in artifact

    def test_migration_ok(self, artifact):
        assert artifact["rehearsal_findings"]["migration_rehearsal_ok"] is True

    def test_rows_preserved(self, artifact):
        assert artifact["rehearsal_findings"]["rows_preserved_in_rehearsal"] == EXPECTED_REPLAY_ROWS

    def test_production_not_modified_in_p129(self, artifact):
        assert artifact["rehearsal_findings"]["production_db_modified_in_p129"] is False

    def test_120_duplicate_groups(self, artifact):
        assert artifact["rehearsal_findings"]["duplicate_groups_discovered"] == 120

    def test_160_extra_rows(self, artifact):
        assert artifact["rehearsal_findings"]["extra_rows_from_old_runs"] == 160

    def test_naive_copy_fails_documented(self, artifact):
        assert artifact["rehearsal_findings"]["p128_copy_sql_naive_fails"] is True

    def test_corrected_sql_required(self, artifact):
        assert artifact["rehearsal_findings"]["corrected_copy_sql_required"] is True

    def test_bet_index_distribution(self, artifact):
        bi = artifact["rehearsal_findings"]["bet_index_default_validation"]
        assert bi["rows_with_bet_index_1"] == 54302
        assert bi["rows_with_bet_index_gt1"] == 160
        assert bi["all_rows_valid"] is True


# ---------------------------------------------------------------------------
# 16. Markdown content
# ---------------------------------------------------------------------------
class TestMarkdownContent:
    @pytest.fixture(scope="class")
    def md(self):
        assert P129A_MD.exists()
        return P129A_MD.read_text()

    def test_classification_in_md(self, md):
        assert "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION" in md

    def test_executive_summary_in_md(self, md):
        assert "Executive Summary" in md or "executive" in md.lower()

    def test_p129_recap_in_md(self, md):
        assert "P129" in md and ("rehearsal" in md.lower() or "Rehearsal" in md)

    def test_120_duplicate_groups_in_md(self, md):
        assert "120" in md

    def test_naive_migration_fails_in_md(self, md):
        assert "naive" in md.lower() or "UNIQUE constraint" in md or "FAILS" in md.upper()

    def test_row_number_in_md(self, md):
        assert "ROW_NUMBER" in md

    def test_production_non_action_in_md(self, md):
        assert "Non-Action" in md or "NOT modified" in md or "NOT DONE" in md

    def test_authorization_gate_section_in_md(self, md):
        assert "Authorization Gate" in md or "authorization gate" in md.lower()

    def test_exact_auth_phrase_in_md(self, md):
        assert "YES authorize migration_plan_p128 because" in md

    def test_p126_blocked_in_md(self, md):
        assert "BLOCKED" in md.upper() and ("P126" in md or "p126" in md.lower())

    def test_explicit_non_actions_in_md(self, md):
        assert "Non-Action" in md or "NOT EXECUTED" in md or "NOT DONE" in md

    def test_54462_in_md(self, md):
        assert "54462" in md

    def test_18000_in_md(self, md):
        assert "18,000" in md or "18000" in md

    def test_waiting_classification_in_md(self, md):
        assert "WAITING" in md.upper()


# ---------------------------------------------------------------------------
# 17. Idempotency
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_script_reruns_cleanly(self):
        result = subprocess.run(
            [sys.executable, "scripts/p129a_production_migration_authorization_gate.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"
        assert "P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION" in result.stdout
        assert "DONE" in result.stdout

    def test_json_stable_after_rerun(self):
        with open(P129A_JSON) as f:
            before = json.load(f)

        subprocess.run(
            [sys.executable, "scripts/p129a_production_migration_authorization_gate.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        with open(P129A_JSON) as f:
            after = json.load(f)

        assert before["task_id"] == after["task_id"]
        assert before["classification"] == after["classification"] == EXPECTED_CLASSIFICATION
        assert before["production_db_modified"] == after["production_db_modified"] is False
        assert before["migration_execution_performed"] == after["migration_execution_performed"] is False
        assert (before["production_db_snapshot_before"]["replay_rows"]
                == after["production_db_snapshot_before"]["replay_rows"]
                == EXPECTED_REPLAY_ROWS)


# ---------------------------------------------------------------------------
# 18. No forbidden files staged
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
