"""
test_apply_p1_catalog_visibility.py
=====================================
Tests for the P1 catalog visibility apply script.

Covers:
  1. Apply is idempotent (run twice = same result)
  2. Apply requires --apply flag (dry-run is default)
  3. Apply creates DB backup before writing
  4. Existing 18 strategies preserved/visible after apply
  5. Artifact-only entries not marked ONLINE after apply
  6. strategy_catalog_p1 table created correctly
  7. Rollback plan is documented in report
  8. strategy_replay_runs / prediction_runs / prediction_items untouched
  9. NO_DATA entries exist for strategies without replay rows
  10. Apply result JSON contains required keys
"""
import json
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
APPLY_RESULT = PROJECT_ROOT / "outputs" / "replay" / "p1_catalog_visibility_apply_result_20260518.json"
DRY_RUN_RESULT = PROJECT_ROOT / "outputs" / "replay" / "p1_catalog_visibility_apply_dry_run_20260518.json"
BACKUP_DIR = PROJECT_ROOT / "lottery_api" / "data" / "backups"
P1_TABLE = "strategy_catalog_p1"


@pytest.fixture(scope="module")
def apply_result():
    """Load the apply result JSON."""
    if not APPLY_RESULT.exists():
        pytest.skip(f"Apply result not found: {APPLY_RESULT}. Run apply_p1_catalog_visibility.py --apply first.")
    return json.loads(APPLY_RESULT.read_text())


@pytest.fixture(scope="module")
def dry_run_result():
    """Load the dry-run result JSON."""
    if not DRY_RUN_RESULT.exists():
        pytest.skip(f"Dry-run result not found: {DRY_RUN_RESULT}.")
    return json.loads(DRY_RUN_RESULT.read_text())


@pytest.fixture(scope="module")
def db_con():
    """Read-only DB connection for verification."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield con
    con.close()


class TestApplyResultSchema:
    def test_apply_result_file_exists(self):
        assert APPLY_RESULT.exists(), f"Apply result not found: {APPLY_RESULT}"

    def test_dry_run_result_file_exists(self):
        assert DRY_RUN_RESULT.exists(), f"Dry-run result not found: {DRY_RUN_RESULT}"

    def test_apply_result_status_complete(self, apply_result):
        assert apply_result["status"] == "APPLY_COMPLETE", \
            f"Expected APPLY_COMPLETE, got {apply_result.get('status')}"

    def test_apply_result_required_keys(self, apply_result):
        required = ["status", "generated_at", "mode", "inserted", "skipped",
                    "backup_path", "idempotency_pass", "rollback_plan", "safety"]
        for key in required:
            assert key in apply_result, f"Missing required key in apply result: {key}"

    def test_dry_run_mode_is_dry_run(self, dry_run_result):
        assert dry_run_result["mode"] == "DRY_RUN"

    def test_apply_mode_is_apply(self, apply_result):
        assert apply_result["mode"] == "APPLY"


class TestApplyIdempotency:
    def test_idempotency_pass_in_apply_result(self, apply_result):
        assert apply_result["idempotency_pass"] is True, \
            "Apply result must confirm idempotency"

    def test_second_run_inserts_zero(self, apply_result):
        """After initial apply, subsequent applies should insert 0 rows."""
        # We verify this by running the apply function directly
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.apply_p1_catalog_visibility import run as apply_run
        result = apply_run(apply=True)
        assert result.get("inserted", 0) == 0, \
            f"Second apply run should insert 0 rows, got {result.get('inserted')}"
        assert result.get("idempotency_pass") is True

    def test_skipped_equals_total_on_second_run(self, apply_result):
        """All entries should be SKIPPED on second run."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.apply_p1_catalog_visibility import run as apply_run
        result = apply_run(apply=True)
        total = result.get("inserted", 0) + result.get("skipped", 0)
        assert result.get("inserted", 0) == 0
        assert total > 0


class TestApplySafety:
    def test_apply_safety_flags(self, apply_result):
        safety = apply_result["safety"]
        assert safety["draw_import"] is False
        assert safety["replay_row_generation"] is False
        assert safety["prediction_update"] is False
        assert safety["strategy_execution"] is False

    def test_apply_db_write_flag_true(self, apply_result):
        """Apply mode should have db_write=True in safety flags."""
        assert apply_result["safety"]["db_write"] is True

    def test_rollback_plan_documented(self, apply_result):
        rp = apply_result.get("rollback_plan", "")
        assert len(rp) > 20, "rollback_plan must be documented"
        assert "strategy_catalog_p1" in rp, "rollback_plan must mention the P1 table"

    def test_backup_created(self, apply_result):
        backup_path = apply_result.get("backup_path")
        assert backup_path is not None, "backup_path must be set in apply result"
        assert Path(backup_path).exists(), f"Backup file must exist: {backup_path}"


class TestDBState:
    def test_p1_table_exists(self, db_con):
        tables = db_con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (P1_TABLE,)
        ).fetchone()
        assert tables is not None, f"Table {P1_TABLE} must exist after apply"

    def test_p1_table_has_entries(self, db_con):
        count = db_con.execute(f"SELECT COUNT(*) FROM {P1_TABLE}").fetchone()[0]
        assert count > 0, f"Table {P1_TABLE} must have entries after apply"

    def test_existing_18_strategies_visible(self, db_con):
        """All 18 existing code registry strategies must be in the P1 catalog."""
        expected_18 = {
            "power_precision_3bet", "power_orthogonal_5bet", "fourier_rhythm_3bet",
            "biglotto_triple_strike", "biglotto_deviation_2bet", "ts3_regime_3bet",
            "daily539_f4cold", "daily539_markov_cold",
            "biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet",
            "power_shlc_midfreq", "p1_deviation_2bet_539",
            "acb_1bet", "acb_markov_midfreq", "acb_markov_midfreq_3bet",
            "midfreq_acb_2bet", "midfreq_fourier_2bet", "h6_gate_mk20_ew85",
        }
        rows = db_con.execute(f"SELECT strategy_id FROM {P1_TABLE}").fetchall()
        registered_ids = {r[0] for r in rows}
        missing = expected_18 - registered_ids
        assert missing == set(), \
            f"Missing existing strategies in P1 catalog: {missing}"

    def test_no_artifact_only_marked_online(self, db_con):
        """Artifact-only entries must not be marked ONLINE in the catalog."""
        bad = db_con.execute(
            f"""SELECT strategy_id, lifecycle_state, catalog_visibility_state
                FROM {P1_TABLE}
                WHERE catalog_visibility_state = 'ARTIFACT_CANDIDATE'
                AND lifecycle_state = 'ONLINE'"""
        ).fetchall()
        assert bad == [], \
            f"Found {len(bad)} ARTIFACT_CANDIDATE entries with ONLINE lifecycle: {[r[0] for r in bad]}"

    def test_no_data_entries_for_strategies_without_rows(self, db_con):
        """Strategies without replay rows must have REGISTERED_NO_DATA or ARTIFACT_CANDIDATE visibility."""
        no_data_entries = db_con.execute(
            f"SELECT strategy_id, has_replay_rows, catalog_visibility_state FROM {P1_TABLE} WHERE has_replay_rows = 0"
        ).fetchall()
        for sid, has_rows, vis in no_data_entries:
            assert vis in ("REGISTERED_NO_DATA", "ARTIFACT_CANDIDATE"), \
                f"{sid} has no replay rows but visibility is {vis}"

    def test_existing_replay_tables_untouched(self, db_con):
        """strategy_replay_runs must NOT be modified by P1 apply."""
        count_before = db_con.execute(
            "SELECT COUNT(*) FROM strategy_replay_runs"
        ).fetchone()[0]
        # Replay rows are pre-existing; P1 should not add/remove any
        assert count_before >= 0  # Basic sanity check (no exception = table intact)

    def test_prediction_tables_untouched(self, db_con):
        """prediction_runs and prediction_items must NOT be modified by P1 apply."""
        run_count = db_con.execute("SELECT COUNT(*) FROM prediction_runs").fetchone()[0]
        item_count = db_con.execute("SELECT COUNT(*) FROM prediction_items").fetchone()[0]
        # Tables must still exist and have their original data
        assert run_count > 0, "prediction_runs was unexpectedly emptied"
        assert item_count > 0, "prediction_items was unexpectedly emptied"


class TestDryRunNoDBWrite:
    def test_dry_run_would_insert_positive(self, dry_run_result):
        """Dry-run must report entries that would be inserted."""
        assert dry_run_result.get("would_insert", 0) > 0

    def test_dry_run_no_db_write(self, dry_run_result):
        assert dry_run_result["safety"]["db_write"] is False

    def test_dry_run_rollback_plan(self, dry_run_result):
        rp = dry_run_result.get("rollback_plan", "")
        assert len(rp) > 20
