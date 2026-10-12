"""
Test suite for P66: Wave 6 Controlled Production Apply

Covers:
- Artifact existence and schema
- Classification: P66_WAVE6_CONTROLLED_APPLY_COMPLETED
- Production DB: 46960 total rows after apply
- cold_complement_2bet: 1500 rows, CAID correct, no ONLINE
- zonal_entropy_2bet: 1500 rows, CAID correct, no ONLINE
- lag_reversion_2bet: 0 rows (excluded — P64b GATE_FAIL)
- Governance: no lifecycle_promotion, no online_promotion, no champion_replacement
- Leakage: 0 violations for both strategies
- Schema: all rows have PICK=6, nums [1..38], special [1..8], dry_run=0
- Post-verify: semantic_ok, p59_preserved, total_ok
- Backup created (pre-apply snapshot)
- Rollback SQL documented
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
APPLY_JSON = REPO / "outputs" / "replay" / "p66_wave6_controlled_apply_20260525.json"
APPLY_DOC  = REPO / "docs" / "replay" / "p66_wave6_controlled_apply_20260525.md"
APPLY_SCRIPT = REPO / "scripts" / "p66_wave6_controlled_apply.py"
PROD_DB    = REPO / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_DIR = REPO / "backups"

# ─── Constants ────────────────────────────────────────────────────────────────

LOTTERY_TYPE        = "POWER_LOTTO"
EXPECTED_ROWS_AFTER = 46960
EXPECTED_ROWS_BEFORE = 43960
ROWS_PER_STRATEGY   = 1500
TOTAL_APPLIED_ROWS  = 3000

STRATEGY_COLD  = "cold_complement_2bet"
STRATEGY_ZONAL = "zonal_entropy_2bet"
STRATEGY_LAG   = "lag_reversion_2bet"

CAID_COLD  = "P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525"
CAID_ZONAL = "P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525"

P65_COMMIT = "b2ae277"

PICK         = 6
POOL         = 38
SPECIAL_POOL = 8


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def result() -> dict:
    return json.load(open(APPLY_JSON))


@pytest.fixture(scope="module")
def doc_text() -> str:
    return APPLY_DOC.read_text()


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect(str(PROD_DB))
    yield conn
    conn.close()


# ─── Class 1: Artifact Existence ─────────────────────────────────────────────

class TestArtifactExistence:
    def test_apply_json_exists(self):
        assert APPLY_JSON.exists(), f"Missing: {APPLY_JSON}"

    def test_apply_json_nonempty(self):
        assert APPLY_JSON.stat().st_size > 100

    def test_apply_doc_exists(self):
        assert APPLY_DOC.exists(), f"Missing: {APPLY_DOC}"

    def test_apply_doc_nonempty(self):
        assert APPLY_DOC.stat().st_size > 200

    def test_apply_script_exists(self):
        assert APPLY_SCRIPT.exists(), f"Missing: {APPLY_SCRIPT}"

    def test_apply_script_nonempty(self):
        assert APPLY_SCRIPT.stat().st_size > 500

    def test_prod_db_exists(self):
        assert PROD_DB.exists(), f"Missing: {PROD_DB}"


# ─── Class 2: JSON Schema ────────────────────────────────────────────────────

class TestJsonSchema:
    def test_classification_present(self, result):
        assert "classification" in result

    def test_overall_ok_present(self, result):
        assert "overall_ok" in result

    def test_phase_present(self, result):
        assert result.get("phase") == "P66"

    def test_strategies_applied_present(self, result):
        assert "strategies_applied" in result

    def test_cold_strategy_present(self, result):
        assert STRATEGY_COLD in result["strategies_applied"]

    def test_zonal_strategy_present(self, result):
        assert STRATEGY_ZONAL in result["strategies_applied"]

    def test_excluded_strategy_documented(self, result):
        assert "excluded_strategy" in result

    def test_governance_present(self, result):
        assert "governance" in result

    def test_post_apply_verification_present(self, result):
        assert "post_apply_verification" in result

    def test_backup_present(self, result):
        assert "backup" in result

    def test_rollback_present(self, result):
        assert "rollback" in result

    def test_pre_flight_present(self, result):
        assert "pre_flight" in result

    def test_p65_ref_present(self, result):
        assert "p65_ref" in result

    def test_run_id_present(self, result):
        assert "run_id" in result

    def test_started_at_present(self, result):
        assert "started_at" in result

    def test_finished_at_present(self, result):
        assert "finished_at" in result


# ─── Class 3: Classification ─────────────────────────────────────────────────

class TestClassification:
    def test_classification_completed(self, result):
        assert result["classification"] == "P66_WAVE6_CONTROLLED_APPLY_COMPLETED"

    def test_overall_ok_true(self, result):
        assert result["overall_ok"] is True

    def test_phase_p66(self, result):
        assert result["phase"] == "P66"

    def test_lottery_type(self, result):
        assert result.get("lottery_type") == "POWER_LOTTO"


# ─── Class 4: Production Rows Count ──────────────────────────────────────────

class TestProductionRowCount:
    def test_prod_rows_after(self, db_conn):
        total = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert total == EXPECTED_ROWS_AFTER, f"Expected {EXPECTED_ROWS_AFTER}, got {total}"

    def test_cold_rows_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_COLD),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY, f"Expected {ROWS_PER_STRATEGY}, got {count}"

    def test_zonal_rows_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ZONAL),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY, f"Expected {ROWS_PER_STRATEGY}, got {count}"

    def test_lag_reversion_absent(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_LAG),
        ).fetchone()[0]
        assert count == 0, f"lag_reversion_2bet must have 0 rows, got {count}"

    def test_caid_cold_row_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CAID_COLD,),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY

    def test_caid_zonal_row_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            (CAID_ZONAL,),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY

    def test_p59_rows_preserved(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=?",
            ("P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525",),
        ).fetchone()[0]
        assert count == 1500, f"P59 rows must be preserved as 1500, got {count}"

    def test_json_prod_rows_before(self, result):
        assert result["production_rows_before"] == EXPECTED_ROWS_BEFORE

    def test_json_prod_rows_after(self, result):
        assert result["production_rows_after"] == EXPECTED_ROWS_AFTER


# ─── Class 5: CAIDs ──────────────────────────────────────────────────────────

class TestCAIDs:
    def test_cold_caid_correct(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["controlled_apply_id"] == CAID_COLD

    def test_zonal_caid_correct(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["controlled_apply_id"] == CAID_ZONAL

    def test_cold_caid_contains_p66(self):
        assert "P66" in CAID_COLD

    def test_zonal_caid_contains_p66(self):
        assert "P66" in CAID_ZONAL

    def test_cold_caid_contains_wave6(self):
        assert "WAVE6" in CAID_COLD

    def test_zonal_caid_contains_wave6(self):
        assert "WAVE6" in CAID_ZONAL


# ─── Class 6: No ONLINE Promotion ────────────────────────────────────────────

class TestNoOnlinePromotion:
    def test_online_cold_in_db(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (LOTTERY_TYPE, STRATEGY_COLD),
        ).fetchone()[0]
        assert count == 0, f"cold_complement must have 0 ONLINE rows, got {count}"

    def test_online_zonal_in_db(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type=? AND strategy_id=? AND replay_status='ONLINE'",
            (LOTTERY_TYPE, STRATEGY_ZONAL),
        ).fetchone()[0]
        assert count == 0, f"zonal_entropy must have 0 ONLINE rows, got {count}"

    def test_governance_online_promotion_false(self, result):
        assert result["governance"]["online_promotion"] is False

    def test_post_online_promotion_ok(self, result):
        assert result["post_apply_verification"]["online_promotion_ok"] is True


# ─── Class 7: Governance Flags ───────────────────────────────────────────────

class TestGovernanceFlags:
    def test_lifecycle_promotion_false(self, result):
        assert result["governance"]["lifecycle_promotion"] is False

    def test_champion_replacement_false(self, result):
        assert result["governance"]["champion_replacement"] is False

    def test_registry_mutation_false(self, result):
        assert result["governance"]["registry_mutation"] is False

    def test_coverage_expansion_only(self, result):
        assert result["governance"]["coverage_expansion_only"] is True

    def test_performance_improvement_claim_false(self, result):
        assert result["governance"]["performance_improvement_claim"] is False

    def test_wave5_champion_unchanged(self, result):
        assert result["governance"]["wave5_champion_unchanged"] == "fourier30_markov30_2bet"


# ─── Class 8: Excluded Strategy ──────────────────────────────────────────────

class TestExcludedStrategy:
    def test_excluded_strategy_id(self, result):
        assert result["excluded_strategy"]["strategy_id"] == STRATEGY_LAG

    def test_excluded_strategy_not_applied(self, result):
        assert result["excluded_strategy"]["applied"] is False

    def test_excluded_reason_present(self, result):
        reason = result["excluded_strategy"].get("reason", "")
        assert len(reason) > 0

    def test_lag_not_in_strategies_applied(self, result):
        assert STRATEGY_LAG not in result["strategies_applied"]


# ─── Class 9: Insert Results ─────────────────────────────────────────────────

class TestInsertResults:
    def test_cold_inserted_1500(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["rows_inserted"] == ROWS_PER_STRATEGY

    def test_zonal_inserted_1500(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["rows_inserted"] == ROWS_PER_STRATEGY

    def test_cold_insert_ok(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["insert_result"]["insert_ok"] is True

    def test_zonal_insert_ok(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["insert_result"]["insert_ok"] is True

    def test_cold_skipped_zero(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["insert_result"]["skipped"] == 0

    def test_zonal_skipped_zero(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["insert_result"]["skipped"] == 0


# ─── Class 10: Validation Results ────────────────────────────────────────────

class TestValidationResults:
    def test_cold_schema_valid(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["schema_validation"]["valid"] is True

    def test_zonal_schema_valid(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["schema_validation"]["valid"] is True

    def test_cold_schema_zero_errors(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["schema_validation"]["error_count"] == 0

    def test_zonal_schema_zero_errors(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["schema_validation"]["error_count"] == 0

    def test_cold_leakage_pass(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["leakage_check"]["pass"] is True

    def test_zonal_leakage_pass(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["leakage_check"]["pass"] is True

    def test_cold_leakage_zero_violations(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["leakage_check"]["violation_count"] == 0

    def test_zonal_leakage_zero_violations(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["leakage_check"]["violation_count"] == 0

    def test_cold_dup_pre_pass(self, result):
        cold = result["strategies_applied"][STRATEGY_COLD]
        assert cold["dup_check_pre"]["pass"] is True

    def test_zonal_dup_pre_pass(self, result):
        zonal = result["strategies_applied"][STRATEGY_ZONAL]
        assert zonal["dup_check_pre"]["pass"] is True


# ─── Class 11: DB Semantics ──────────────────────────────────────────────────

class TestDBSemantics:
    def test_cold_rows_pick6(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 20",
            (CAID_COLD,),
        ).fetchall()
        errors = []
        for row in rows:
            nums = json.loads(row[0]) if row[0] else []
            if len(nums) != PICK:
                errors.append(f"expected {PICK}, got {len(nums)}: {nums}")
        assert not errors, f"cold PICK errors: {errors}"

    def test_zonal_rows_pick6(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 20",
            (CAID_ZONAL,),
        ).fetchall()
        errors = []
        for row in rows:
            nums = json.loads(row[0]) if row[0] else []
            if len(nums) != PICK:
                errors.append(f"expected {PICK}, got {len(nums)}: {nums}")
        assert not errors, f"zonal PICK errors: {errors}"

    def test_cold_rows_in_pool(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 50",
            (CAID_COLD,),
        ).fetchall()
        errors = []
        for row in rows:
            nums = json.loads(row[0]) if row[0] else []
            if any(not (1 <= n <= POOL) for n in nums):
                errors.append(f"nums out of [1..{POOL}]: {nums}")
        assert not errors

    def test_zonal_rows_in_pool(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_numbers FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 50",
            (CAID_ZONAL,),
        ).fetchall()
        errors = []
        for row in rows:
            nums = json.loads(row[0]) if row[0] else []
            if any(not (1 <= n <= POOL) for n in nums):
                errors.append(f"nums out of [1..{POOL}]: {nums}")
        assert not errors

    def test_cold_special_in_pool(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_special FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND predicted_special IS NOT NULL LIMIT 50",
            (CAID_COLD,),
        ).fetchall()
        errors = []
        for row in rows:
            sp = int(row[0])
            if not (1 <= sp <= SPECIAL_POOL):
                errors.append(f"special out of [1..{SPECIAL_POOL}]: {sp}")
        assert not errors

    def test_zonal_special_in_pool(self, db_conn):
        rows = db_conn.execute(
            "SELECT predicted_special FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND predicted_special IS NOT NULL LIMIT 50",
            (CAID_ZONAL,),
        ).fetchall()
        errors = []
        for row in rows:
            sp = int(row[0])
            if not (1 <= sp <= SPECIAL_POOL):
                errors.append(f"special out of [1..{SPECIAL_POOL}]: {sp}")
        assert not errors

    def test_cold_dry_run_zero(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (CAID_COLD,),
        ).fetchone()[0]
        assert count == 0, f"cold has {count} rows with dry_run != 0"

    def test_zonal_dry_run_zero(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (CAID_ZONAL,),
        ).fetchone()[0]
        assert count == 0, f"zonal has {count} rows with dry_run != 0"

    def test_cold_status_predicted(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND replay_status='PREDICTED'",
            (CAID_COLD,),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY

    def test_zonal_status_predicted(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND replay_status='PREDICTED'",
            (CAID_ZONAL,),
        ).fetchone()[0]
        assert count == ROWS_PER_STRATEGY


# ─── Class 12: Post-apply Verification ───────────────────────────────────────

class TestPostApplyVerification:
    def test_post_total_ok(self, result):
        assert result["post_apply_verification"]["total_ok"] is True

    def test_post_cold_rows_ok(self, result):
        assert result["post_apply_verification"]["cold_rows_ok"] is True

    def test_post_zonal_rows_ok(self, result):
        assert result["post_apply_verification"]["zonal_rows_ok"] is True

    def test_post_lag_absent(self, result):
        assert result["post_apply_verification"]["lag_reversion_absent"] is True

    def test_post_semantic_ok(self, result):
        assert result["post_apply_verification"]["semantic_ok"] is True

    def test_post_p59_preserved(self, result):
        assert result["post_apply_verification"]["p59_rows_preserved"] is True

    def test_post_online_ok(self, result):
        assert result["post_apply_verification"]["online_promotion_ok"] is True

    def test_post_dry_run_zero_ok(self, result):
        assert result["post_apply_verification"]["dry_run_zero_ok"] is True

    def test_post_p66_total_ok(self, result):
        assert result["post_apply_verification"]["p66_total_ok"] is True

    def test_post_p66_total_rows_count(self, result):
        assert result["post_apply_verification"]["p66_total_rows"] == TOTAL_APPLIED_ROWS


# ─── Class 13: Hit Statistics ─────────────────────────────────────────────────

class TestHitStatistics:
    def test_cold_hit_stats_present(self, result):
        assert "hit_stats" in result["strategies_applied"][STRATEGY_COLD]

    def test_zonal_hit_stats_present(self, result):
        assert "hit_stats" in result["strategies_applied"][STRATEGY_ZONAL]

    def test_cold_predicted_1500(self, result):
        stats = result["strategies_applied"][STRATEGY_COLD]["hit_stats"]
        assert stats["predicted"] == ROWS_PER_STRATEGY

    def test_zonal_predicted_1500(self, result):
        stats = result["strategies_applied"][STRATEGY_ZONAL]["hit_stats"]
        assert stats["predicted"] == ROWS_PER_STRATEGY

    def test_cold_m3_plus_rate_positive(self, result):
        rate = result["strategies_applied"][STRATEGY_COLD]["hit_stats"]["hit_3plus_rate_pct"]
        assert rate > 0, f"cold M3+ must be > 0, got {rate}"

    def test_zonal_m3_plus_rate_positive(self, result):
        rate = result["strategies_applied"][STRATEGY_ZONAL]["hit_stats"]["hit_3plus_rate_pct"]
        assert rate > 0, f"zonal M3+ must be > 0, got {rate}"

    def test_cold_within_noise_band(self, result):
        stats = result["strategies_applied"][STRATEGY_COLD]["hit_stats"]
        rate = stats["hit_3plus_rate_pct"]
        theoretical = stats["theoretical_m3_baseline_pct"]
        delta = rate - theoretical
        assert delta >= -1.0, f"cold M3+ too far below baseline: delta={delta:.2f}pp"

    def test_zonal_within_noise_band(self, result):
        stats = result["strategies_applied"][STRATEGY_ZONAL]["hit_stats"]
        rate = stats["hit_3plus_rate_pct"]
        theoretical = stats["theoretical_m3_baseline_pct"]
        delta = rate - theoretical
        assert delta >= -1.0, f"zonal M3+ too far below baseline: delta={delta:.2f}pp"

    def test_cold_z_test_present(self, result):
        assert "z_test" in result["strategies_applied"][STRATEGY_COLD]["hit_stats"]

    def test_zonal_z_test_present(self, result):
        assert "z_test" in result["strategies_applied"][STRATEGY_ZONAL]["hit_stats"]


# ─── Class 14: Pre-flight Data ────────────────────────────────────────────────

class TestPreFlightData:
    def test_preflight_rows_ok(self, result):
        assert result["pre_flight"]["production_rows_ok"] is True

    def test_preflight_cold_clean(self, result):
        assert result["pre_flight"]["cold_complement_clean"] is True

    def test_preflight_zonal_clean(self, result):
        assert result["pre_flight"]["zonal_entropy_clean"] is True

    def test_preflight_dup_pass(self, result):
        assert result["pre_flight"]["duplicate_check_pass"] is True

    def test_preflight_p59_ok(self, result):
        assert result["pre_flight"]["p59_rows_ok"] is True

    def test_preflight_wave6_clean(self, result):
        assert result["pre_flight"]["wave6_clean"] is True

    def test_preflight_lag_absent(self, result):
        assert result["pre_flight"]["lag_reversion_rows"] == 0


# ─── Class 15: Backup ────────────────────────────────────────────────────────

class TestBackup:
    def test_backup_ok(self, result):
        assert result["backup"]["ok"] is True

    def test_backup_rows_correct(self, result):
        assert result["backup"]["backup_rows"] == EXPECTED_ROWS_BEFORE

    def test_backup_path_present(self, result):
        path = result["backup"].get("backup_path")
        assert path is not None and len(path) > 0

    def test_backup_file_exists(self, result):
        path = Path(result["backup"]["backup_path"])
        assert path.exists(), f"Backup file not found: {path}"

    def test_backup_dir_exists(self):
        assert BACKUP_DIR.exists()


# ─── Class 16: Rollback Documentation ────────────────────────────────────────

class TestRollback:
    def test_rollback_sql_present(self, result):
        sql = result["rollback"].get("rollback_sql", "")
        assert len(sql) > 0

    def test_rollback_sql_contains_caid_cold(self, result):
        sql = result["rollback"]["rollback_sql"]
        assert CAID_COLD in sql

    def test_rollback_sql_contains_caid_zonal(self, result):
        sql = result["rollback"]["rollback_sql"]
        assert CAID_ZONAL in sql

    def test_rollback_verify_sql_present(self, result):
        verify = result["rollback"].get("verify_sql", "")
        assert len(verify) > 0

    def test_rollback_restore_cmd_present(self, result):
        cmd = result["rollback"].get("restore_backup_cmd", "")
        assert len(cmd) > 0


# ─── Class 17: P65 Reference ─────────────────────────────────────────────────

class TestP65Reference:
    def test_p65_ref_commit(self, result):
        assert result["p65_ref"]["commit"] == P65_COMMIT

    def test_p65_ref_classification(self, result):
        assert result["p65_ref"]["classification"] == "P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION"


# ─── Class 18: Doc Content ───────────────────────────────────────────────────

class TestDocContent:
    def test_doc_has_p66_classification(self, doc_text):
        assert "P66_WAVE6_CONTROLLED_APPLY_COMPLETED" in doc_text

    def test_doc_mentions_cold_complement(self, doc_text):
        assert "cold_complement_2bet" in doc_text

    def test_doc_mentions_zonal_entropy(self, doc_text):
        assert "zonal_entropy_2bet" in doc_text

    def test_doc_mentions_lag_excluded(self, doc_text):
        assert "lag_reversion_2bet" in doc_text

    def test_doc_shows_row_counts(self, doc_text):
        assert "46960" in doc_text

    def test_doc_mentions_no_online(self, doc_text):
        assert "online" in doc_text.lower() or "ONLINE" in doc_text

    def test_doc_mentions_governance(self, doc_text):
        assert "Governance" in doc_text or "governance" in doc_text

    def test_doc_has_rollback_sql(self, doc_text):
        assert "DELETE FROM strategy_prediction_replays" in doc_text

    def test_doc_has_authorization(self, doc_text):
        assert "Authorization" in doc_text or "authorization" in doc_text


# ─── Class 19: No Forbidden Files Staged ─────────────────────────────────────

class TestForbiddenFilesSanity:
    def test_db_file_path_not_in_script_as_staged(self):
        # Sanity: script should not reference git add for the DB
        text = APPLY_SCRIPT.read_text()
        assert "git add lottery_api/data/lottery_v2.db" not in text

    def test_no_temp_db_in_repo(self):
        # No stray DB files created during apply
        KNOWN_LEGACY_DBS = {"lottery.db", "lottery_v2.db"}
        for db_path in REPO.glob("*.db"):
            assert db_path.name in KNOWN_LEGACY_DBS, (
                f"Unexpected DB file in repo root: {db_path.name}"
            )


# ─── Class 20: No ONLINE Status in DB ────────────────────────────────────────

class TestNoOnlineStatusDB:
    def test_no_online_cold_caid(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND replay_status='ONLINE'",
            (CAID_COLD,),
        ).fetchone()[0]
        assert count == 0

    def test_no_online_zonal_caid(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND replay_status='ONLINE'",
            (CAID_ZONAL,),
        ).fetchone()[0]
        assert count == 0

    def test_wave6_total_in_json(self, result):
        post = result["post_apply_verification"]
        assert post["cold_rows"] + post["zonal_rows"] == TOTAL_APPLIED_ROWS
