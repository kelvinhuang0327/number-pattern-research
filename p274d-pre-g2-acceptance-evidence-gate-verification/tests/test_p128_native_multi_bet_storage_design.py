"""
P128: Native Multi-Bet Replay Storage Design — Test Suite
==========================================================
Tests:
  1.  Artifact existence
  2.  task_id and classification
  3.  DB invariants (live DB — read-only)
  4.  DB snapshot consistency (before == after, no writes)
  5.  P126 source summary
  6.  Storage options considered
  7.  Recommended storage design
  8.  One-row-per-bet decision
  9.  Bet index representation
  10. Duplicate key contract
  11. Migration plan structure
  12. P126 apply readiness
  13. Governance (no DB writes, no scheduler, no 4_STAR/P108/P117/P118)
  14. Blocked/excluded items
  15. Required authorization phrases
  16. Markdown output
  17. Idempotency (script can run twice cleanly)
  18. No forbidden files staged
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
P128_JSON   = REPO_ROOT / "outputs/replay/p128_native_multi_bet_storage_design_20260528.json"
P128_MD     = REPO_ROOT / "docs/replay/p128_native_multi_bet_storage_design_20260528.md"
P126_JSON   = REPO_ROOT / "outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS      = 54462
EXPECTED_TOTAL_AFTER      = 72462
EXPECTED_NEW_ROWS         = 18000
EXPECTED_CANDIDATE_COUNT  = 5

FORBIDDEN_STAGE_PATTERNS = [
    "lottery_api/data/lottery_v2.db",
    "lottery_api/data/lottery_history.json",
    "backend.pid",
    "frontend.pid",
    "runtime/",
]


# ---------------------------------------------------------------------------
# Fixture — load artifact once
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def artifact():
    assert P128_JSON.exists(), f"P128 JSON not found: {P128_JSON}"
    with open(P128_JSON) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact existence
# ---------------------------------------------------------------------------
class TestArtifactExistence:
    def test_json_exists(self):
        assert P128_JSON.exists(), f"Missing: {P128_JSON}"

    def test_md_exists(self):
        assert P128_MD.exists(), f"Missing: {P128_MD}"

    def test_script_exists(self):
        script = REPO_ROOT / "scripts/p128_native_multi_bet_storage_design.py"
        assert script.exists(), f"Missing: {script}"

    def test_p126_source_exists(self):
        assert P126_JSON.exists(), f"Missing P126 source: {P126_JSON}"


# ---------------------------------------------------------------------------
# 2. task_id and classification
# ---------------------------------------------------------------------------
class TestClassification:
    def test_task_id(self, artifact):
        assert artifact["task_id"] == "P128"

    def test_classification(self, artifact):
        assert artifact["classification"] == "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY"

    def test_generated_at_present(self, artifact):
        assert "generated_at" in artifact
        assert artifact["generated_at"]

    def test_p126_source_referenced(self, artifact):
        assert "p126_source_artifact" in artifact
        assert "p126" in artifact["p126_source_artifact"]


# ---------------------------------------------------------------------------
# 3. DB invariants (live read-only)
# ---------------------------------------------------------------------------
class TestDBInvariantsLive:
    def _ro_conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        return conn

    def test_replay_rows_54462(self):
        conn = self._ro_conn()
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        conn.close()
        assert count == EXPECTED_REPLAY_ROWS, f"replay_rows={count}, expected={EXPECTED_REPLAY_ROWS}"

    def test_3star_count(self):
        conn = self._ro_conn()
        count = conn.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'").fetchone()[0]
        conn.close()
        assert count == 4179

    def test_4star_count(self):
        conn = self._ro_conn()
        count = conn.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'").fetchone()[0]
        conn.close()
        assert count == 2922

    def test_power_lotto_count(self):
        conn = self._ro_conn()
        count = conn.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'").fetchone()[0]
        conn.close()
        assert count == 1913

    def test_no_bet_index_column_currently(self):
        conn = self._ro_conn()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
        conn.close()
        assert "bet_index" not in cols, "bet_index already exists — migration may have been run"

    def test_current_unique_constraint(self):
        conn = self._ro_conn()
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='strategy_prediction_replays'"
        ).fetchone()[0]
        conn.close()
        assert "lottery_type, target_draw, strategy_id, replay_run_id" in ddl


# ---------------------------------------------------------------------------
# 4. DB snapshot — before == after (no writes)
# ---------------------------------------------------------------------------
class TestDBSnapshot:
    def test_before_equals_after(self, artifact):
        assert artifact["db_snapshot_before"] == artifact["db_snapshot_after"], \
            "db_snapshot_before != db_snapshot_after — possible DB write detected"

    def test_before_replay_rows(self, artifact):
        assert artifact["db_snapshot_before"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_after_replay_rows(self, artifact):
        assert artifact["db_snapshot_after"]["replay_rows"] == EXPECTED_REPLAY_ROWS

    def test_3star_in_snapshot(self, artifact):
        assert artifact["db_snapshot_before"]["3_STAR"]["count"] == 4179

    def test_4star_in_snapshot(self, artifact):
        assert artifact["db_snapshot_before"]["4_STAR"]["count"] == 2922

    def test_power_in_snapshot(self, artifact):
        assert artifact["db_snapshot_before"]["POWER_LOTTO"]["count"] == 1913


# ---------------------------------------------------------------------------
# 5. P126 source summary
# ---------------------------------------------------------------------------
class TestP126SourceSummary:
    def test_p126_summary_present(self, artifact):
        assert "p126_source_summary" in artifact

    def test_p126_classification(self, artifact):
        assert artifact["p126_source_summary"]["classification"] == "P126_DRY_RUN_PLAN_READY"

    def test_p126_total_new_rows(self, artifact):
        assert artifact["p126_source_summary"]["total_new_rows_if_all_applied"] == EXPECTED_NEW_ROWS

    def test_p126_candidate_count(self, artifact):
        assert artifact["p126_source_summary"]["candidate_count"] == EXPECTED_CANDIDATE_COUNT

    def test_p126_prov_guard_pass(self, artifact):
        assert artifact["p126_source_summary"]["all_prov_guard_pass"] is True

    def test_p126_dup_guard_pass(self, artifact):
        assert artifact["p126_source_summary"]["all_dup_guard_pass"] is True

    def test_p128_pending_resolved(self, artifact):
        assert artifact["p126_source_summary"]["p128_now_resolved"] is True


# ---------------------------------------------------------------------------
# 6. Storage options considered
# ---------------------------------------------------------------------------
class TestStorageOptions:
    def test_options_present(self, artifact):
        assert "storage_options_considered" in artifact

    def test_at_least_3_options(self, artifact):
        assert len(artifact["storage_options_considered"]) >= 3

    def test_option_a_present(self, artifact):
        options = artifact["storage_options_considered"]
        option_ids = [o["option_id"] for o in options]
        assert "A" in option_ids

    def test_option_a_recommended(self, artifact):
        opts = {o["option_id"]: o for o in artifact["storage_options_considered"]}
        assert opts["A"]["recommended"] is True

    def test_option_b_not_recommended(self, artifact):
        opts = {o["option_id"]: o for o in artifact["storage_options_considered"]}
        assert opts["B"]["recommended"] is False

    def test_option_c_not_recommended(self, artifact):
        opts = {o["option_id"]: o for o in artifact["storage_options_considered"]}
        assert opts["C"]["recommended"] is False

    def test_option_a_migration_required(self, artifact):
        opts = {o["option_id"]: o for o in artifact["storage_options_considered"]}
        assert opts["A"]["migration_required"] is True

    def test_option_b_no_migration(self, artifact):
        opts = {o["option_id"]: o for o in artifact["storage_options_considered"]}
        assert opts["B"]["migration_required"] is False


# ---------------------------------------------------------------------------
# 7. Recommended storage design
# ---------------------------------------------------------------------------
class TestRecommendedStorageDesign:
    def test_present(self, artifact):
        assert "recommended_storage_design" in artifact

    def test_option_a_selected(self, artifact):
        assert artifact["recommended_storage_design"]["option_selected"] == "A"

    def test_one_row_per_bet_approach(self, artifact):
        assert "one_row_per_bet" in artifact["recommended_storage_design"]["approach"]

    def test_bet_index_column_defined(self, artifact):
        assert "bet_index" in artifact["recommended_storage_design"]["bet_index_column"]

    def test_migration_required(self, artifact):
        assert artifact["recommended_storage_design"]["migration_required"] is True

    def test_new_unique_constraint(self, artifact):
        uc = artifact["recommended_storage_design"]["new_unique_constraint"]
        assert "lottery_type" in uc
        assert "target_draw" in uc
        assert "strategy_id" in uc
        assert "bet_index" in uc

    def test_existing_rows_unchanged(self, artifact):
        assert artifact["recommended_storage_design"]["row_count_after_migration"] == EXPECTED_REPLAY_ROWS


# ---------------------------------------------------------------------------
# 8. One-row-per-bet decision
# ---------------------------------------------------------------------------
class TestOneRowPerBetDecision:
    def test_present(self, artifact):
        assert "one_row_per_bet_decision" in artifact

    def test_decision_approved(self, artifact):
        assert artifact["one_row_per_bet_decision"]["decision"] == "APPROVED"

    def test_convention(self, artifact):
        assert artifact["one_row_per_bet_decision"]["convention"] == "one_row_per_bet"

    def test_bet_index_column_required(self, artifact):
        assert artifact["one_row_per_bet_decision"]["bet_index_column_required"] is True

    def test_approved_for_p126(self, artifact):
        assert artifact["one_row_per_bet_decision"]["approved_for_p126_apply"] is True

    def test_approval_condition_present(self, artifact):
        assert artifact["one_row_per_bet_decision"]["approval_condition"]


# ---------------------------------------------------------------------------
# 9. Bet index representation
# ---------------------------------------------------------------------------
class TestBetIndexRepresentation:
    def test_present(self, artifact):
        assert "bet_index_representation" in artifact

    def test_column_name(self, artifact):
        assert artifact["bet_index_representation"]["column_name"] == "bet_index"

    def test_column_type_has_default_1(self, artifact):
        assert "DEFAULT 1" in artifact["bet_index_representation"]["column_type"]

    def test_bet_1_meaning_defined(self, artifact):
        assert artifact["bet_index_representation"]["bet_1_meaning"]

    def test_bet_n_meaning_defined(self, artifact):
        assert artifact["bet_index_representation"]["bet_n_meaning"]


# ---------------------------------------------------------------------------
# 10. Duplicate key contract
# ---------------------------------------------------------------------------
class TestDuplicateKeyContract:
    def test_present(self, artifact):
        assert "duplicate_key_contract" in artifact

    def test_full_dedup_tuple_contains_lottery_type(self, artifact):
        assert "lottery_type" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_full_dedup_tuple_contains_target_draw(self, artifact):
        assert "target_draw" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_full_dedup_tuple_contains_strategy_id(self, artifact):
        assert "strategy_id" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_full_dedup_tuple_contains_bet_index(self, artifact):
        assert "bet_index" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_full_dedup_tuple_contains_predicted_numbers_fingerprint(self, artifact):
        assert "predicted_numbers_fingerprint" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_full_dedup_tuple_contains_provenance_hash(self, artifact):
        assert "provenance_hash" in artifact["duplicate_key_contract"]["full_dedup_tuple"]

    def test_primary_unique_constraint_has_lottery_type(self, artifact):
        cols = artifact["duplicate_key_contract"]["primary_unique_constraint"]["columns"]
        assert "lottery_type" in cols

    def test_primary_unique_constraint_has_bet_index(self, artifact):
        cols = artifact["duplicate_key_contract"]["primary_unique_constraint"]["columns"]
        assert "bet_index" in cols

    def test_provenance_hash_guard_present(self, artifact):
        assert "provenance_hash_guard" in artifact["duplicate_key_contract"]

    def test_hash_input_fields_include_bet_index(self, artifact):
        fields = artifact["duplicate_key_contract"]["provenance_hash_guard"]["hash_input_fields"]
        assert "bet_index" in fields

    def test_dedup_enforcement_has_db_level(self, artifact):
        enforcement = artifact["duplicate_key_contract"]["dedup_enforcement_order"]
        assert any("DB level" in e or "constraint" in e.lower() for e in enforcement)


# ---------------------------------------------------------------------------
# 11. Migration plan
# ---------------------------------------------------------------------------
class TestMigrationPlan:
    def test_present(self, artifact):
        assert "migration_plan_if_needed" in artifact

    def test_migration_type(self, artifact):
        assert "SQLite" in artifact["migration_plan_if_needed"]["migration_type"]

    def test_has_steps(self, artifact):
        assert len(artifact["migration_plan_if_needed"]["steps"]) >= 10

    def test_step_1_is_first(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert steps[0]["step"] == 1

    def test_has_begin_transaction(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert any("BEGIN" in s["sql"].upper() for s in steps)

    def test_has_commit(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert any("COMMIT" in s["sql"].upper() for s in steps)

    def test_has_create_new_table(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert any("CREATE TABLE" in s["sql"].upper() for s in steps)

    def test_has_drop_old_table(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert any("DROP TABLE" in s["sql"].upper() for s in steps)

    def test_has_rename(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        assert any("RENAME" in s["sql"].upper() for s in steps)

    def test_new_table_has_bet_index(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        create_steps = [s for s in steps if "CREATE TABLE" in s["sql"].upper()]
        assert any("bet_index" in s["sql"] for s in create_steps)

    def test_new_table_has_correct_unique_constraint(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        create_steps = [s for s in steps if "CREATE TABLE" in s["sql"].upper()]
        assert any("UNIQUE(lottery_type, target_draw, strategy_id, bet_index)" in s["sql"]
                   for s in create_steps)

    def test_has_post_migration_invariants(self, artifact):
        assert len(artifact["migration_plan_if_needed"]["post_migration_invariants"]) >= 3

    def test_invariant_includes_54462(self, artifact):
        invs = artifact["migration_plan_if_needed"]["post_migration_invariants"]
        assert any("54462" in inv for inv in invs)

    def test_authorization_required(self, artifact):
        assert artifact["migration_plan_if_needed"]["authorization_required"] is True

    def test_authorization_phrase_present(self, artifact):
        phrase = artifact["migration_plan_if_needed"]["authorization_phrase"]
        assert "authorize migration_plan_p128" in phrase.lower() or "migration" in phrase.lower()

    def test_not_executed_in_p128(self, artifact):
        assert artifact["migration_plan_if_needed"]["not_executed_in_p128"] is True

    def test_has_bet_index_index_creation(self, artifact):
        steps = artifact["migration_plan_if_needed"]["steps"]
        index_steps = [s for s in steps if "CREATE INDEX" in s["sql"].upper()]
        assert any("bet_index" in s["sql"] for s in index_steps)


# ---------------------------------------------------------------------------
# 12. P126 apply readiness
# ---------------------------------------------------------------------------
class TestP126ApplyReadiness:
    def test_present(self, artifact):
        assert "p126_apply_readiness_after_p128" in artifact

    def test_overall_readiness(self, artifact):
        r = artifact["p126_apply_readiness_after_p128"]["overall_readiness"]
        assert r in ("CONDITIONALLY_READY", "READY")

    def test_total_new_rows(self, artifact):
        assert artifact["p126_apply_readiness_after_p128"]["total_new_rows_if_applied"] == EXPECTED_NEW_ROWS

    def test_total_rows_after(self, artifact):
        assert artifact["p126_apply_readiness_after_p128"]["total_rows_after_apply"] == EXPECTED_TOTAL_AFTER

    def test_candidate_count(self, artifact):
        assert len(artifact["p126_apply_readiness_after_p128"]["candidates"]) == EXPECTED_CANDIDATE_COUNT

    def test_db_writes_zero(self, artifact):
        assert artifact["p126_apply_readiness_after_p128"]["db_writes_in_p128"] == 0

    def test_migration_not_executed(self, artifact):
        assert artifact["p126_apply_readiness_after_p128"]["migration_not_executed_in_p128"] is True

    def test_rsr1_resolved(self, artifact):
        assert "RSR-1" in artifact["p126_apply_readiness_after_p128"]["p128_resolved_rsr"]

    def test_rsr2_resolved(self, artifact):
        assert "RSR-2" in artifact["p126_apply_readiness_after_p128"]["p128_resolved_rsr"]

    def test_preconditions_present(self, artifact):
        assert len(artifact["p126_apply_readiness_after_p128"]["preconditions"]) >= 4

    def test_migration_precondition_pending(self, artifact):
        preconds = artifact["p126_apply_readiness_after_p128"]["preconditions"]
        migration_pre = [p for p in preconds if "migration" in p["check"].lower()]
        assert any(p["status"] in ("PENDING", "REQUIRED") for p in migration_pre)

    def test_auth_phrases_in_preconditions(self, artifact):
        preconds = artifact["p126_apply_readiness_after_p128"]["preconditions"]
        phrase_pre = [p for p in preconds if "authorization_phrases" in p["check"]]
        assert len(phrase_pre) > 0
        all_phrases = phrase_pre[0].get("phrases_required", [])
        assert len(all_phrases) == EXPECTED_CANDIDATE_COUNT

    @pytest.mark.parametrize("strategy", [
        "biglotto_echo_aware_3bet",
        "daily539_f4cold_5bet",
        "daily539_f4cold_3bet",
        "power_fourier_rhythm_2bet",
        "biglotto_ts3_markov_4bet_w30",
    ])
    def test_candidate_present(self, artifact, strategy):
        candidates = artifact["p126_apply_readiness_after_p128"]["candidates"]
        ids = [c["strategy_id"] for c in candidates]
        assert strategy in ids, f"Missing candidate: {strategy}"


# ---------------------------------------------------------------------------
# 13. Governance
# ---------------------------------------------------------------------------
class TestGovernance:
    def test_governance_present(self, artifact):
        assert "governance" in artifact

    def test_db_writes_zero(self, artifact):
        assert artifact["governance"]["db_writes"] == 0

    def test_schema_not_changed(self, artifact):
        assert artifact["governance"]["schema_changes_executed"] is False

    def test_scheduler_not_installed(self, artifact):
        assert artifact["governance"]["scheduler_installed"] is False

    def test_strategy_not_promoted(self, artifact):
        assert artifact["governance"]["strategy_promoted"] is False

    def test_4star_not_included(self, artifact):
        assert artifact["governance"]["4_STAR_included"] is False

    def test_p108_not_executed(self, artifact):
        assert artifact["governance"]["P108_executed"] is False

    def test_p117_not_executed(self, artifact):
        assert artifact["governance"]["P117_executed"] is False

    def test_p118_not_executed(self, artifact):
        assert artifact["governance"]["P118_executed"] is False

    def test_p126_apply_not_executed(self, artifact):
        assert artifact["governance"]["p126_apply_executed"] is False

    def test_pragma_query_only(self, artifact):
        assert "ON" in str(artifact["governance"]["pragma_query_only"])

    def test_migration_design_only(self, artifact):
        assert "DESIGN_ONLY" in artifact["governance"]["migration_plan_status"]


# ---------------------------------------------------------------------------
# 14. Blocked / excluded
# ---------------------------------------------------------------------------
class TestBlockedExcluded:
    def test_present(self, artifact):
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

    def test_db_writes_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "db_writes" in items

    def test_migration_execution_blocked(self, artifact):
        items = [b["item"] for b in artifact["blocked_or_excluded"]]
        assert "migration_execution" in items


# ---------------------------------------------------------------------------
# 15. Required authorization phrases
# ---------------------------------------------------------------------------
class TestRequiredAuthorizationPhrases:
    def test_present(self, artifact):
        assert "required_authorization_phrases" in artifact

    def test_migration_phrase_present(self, artifact):
        phrase = artifact["required_authorization_phrases"]["migration_authorization"]
        assert "migration" in phrase.lower() or "p128" in phrase.lower()

    def test_5_per_strategy_phrases(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert len(phrases) == EXPECTED_CANDIDATE_COUNT

    def test_biglotto_echo_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert any("biglotto_echo_aware_3bet" in p for p in phrases)

    def test_daily539_f4cold_5bet_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert any("daily539_f4cold_5bet" in p for p in phrases)

    def test_daily539_f4cold_3bet_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert any("daily539_f4cold_3bet" in p for p in phrases)

    def test_power_fourier_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert any("power_fourier_rhythm_2bet" in p for p in phrases)

    def test_biglotto_ts3_phrase(self, artifact):
        phrases = artifact["required_authorization_phrases"]["per_strategy_apply_authorization"]
        assert any("biglotto_ts3_markov_4bet_w30" in p for p in phrases)


# ---------------------------------------------------------------------------
# 16. Markdown output
# ---------------------------------------------------------------------------
class TestMarkdownOutput:
    @pytest.fixture(scope="class")
    def md_content(self):
        assert P128_MD.exists()
        return P128_MD.read_text()

    def test_classification_in_md(self, md_content):
        assert "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY" in md_content

    def test_executive_summary_in_md(self, md_content):
        assert "Executive Summary" in md_content or "executive" in md_content.lower()

    def test_migration_plan_in_md(self, md_content):
        assert "Migration Plan" in md_content or "migration" in md_content.lower()

    def test_one_row_per_bet_in_md(self, md_content):
        assert "one-row-per-bet" in md_content or "one_row_per_bet" in md_content

    def test_bet_index_in_md(self, md_content):
        assert "bet_index" in md_content

    def test_p126_readiness_in_md(self, md_content):
        assert "CONDITIONALLY_READY" in md_content or "READY" in md_content

    def test_auth_phrases_in_md(self, md_content):
        assert "biglotto_echo_aware_3bet" in md_content
        assert "daily539_f4cold_5bet" in md_content
        assert "daily539_f4cold_3bet" in md_content
        assert "power_fourier_rhythm_2bet" in md_content
        assert "biglotto_ts3_markov_4bet_w30" in md_content

    def test_4star_excluded_in_md(self, md_content):
        assert "4_STAR" in md_content

    def test_p108_excluded_in_md(self, md_content):
        assert "P108" in md_content

    def test_db_rows_in_md(self, md_content):
        assert "54462" in md_content

    def test_plus_18000_in_md(self, md_content):
        assert "18000" in md_content or "18,000" in md_content

    def test_explicit_non_actions_section(self, md_content):
        assert "Non-Action" in md_content or "non-action" in md_content.lower() or "Explicit" in md_content

    def test_zero_db_writes_in_md(self, md_content):
        assert "db_writes" in md_content.lower() or "no DB write" in md_content.lower() or "0" in md_content

    def test_unique_constraint_in_md(self, md_content):
        assert "bet_index" in md_content and "UNIQUE" in md_content.upper()


# ---------------------------------------------------------------------------
# 17. Idempotency
# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_script_reruns_cleanly(self):
        result = subprocess.run(
            [sys.executable, "scripts/p128_native_multi_bet_storage_design.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Script failed on re-run:\n{result.stderr}"
        assert "P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY" in result.stdout
        assert "DONE" in result.stdout

    def test_json_stable_after_rerun(self):
        # Load JSON before and after re-run
        with open(P128_JSON) as f:
            before = json.load(f)

        subprocess.run(
            [sys.executable, "scripts/p128_native_multi_bet_storage_design.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )

        with open(P128_JSON) as f:
            after = json.load(f)

        # Classification, task_id, summary must be stable (generated_at will differ)
        assert before["task_id"] == after["task_id"]
        assert before["classification"] == after["classification"]
        assert before["db_snapshot_before"]["replay_rows"] == after["db_snapshot_before"]["replay_rows"]
        assert before["governance"]["db_writes"] == after["governance"]["db_writes"] == 0


# ---------------------------------------------------------------------------
# 18. No forbidden files staged
# ---------------------------------------------------------------------------
class TestForbiddenFilesNotStaged:
    def test_no_forbidden_files_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        staged = result.stdout.strip()
        if not staged:
            return  # Nothing staged — clean
        for forbidden in FORBIDDEN_STAGE_PATTERNS:
            for line in staged.splitlines():
                assert forbidden not in line, \
                    f"Forbidden file staged: {line} (matched pattern: {forbidden})"

    def test_db_file_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        assert "lottery_v2.db" not in result.stdout

    def test_history_json_not_staged(self):
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True
        )
        assert "lottery_history.json" not in result.stdout
