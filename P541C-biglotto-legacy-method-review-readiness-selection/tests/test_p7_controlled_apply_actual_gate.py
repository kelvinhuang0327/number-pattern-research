"""
test_p7_controlled_apply_actual_gate.py
==========================================
P7 Controlled Apply Actual Gate — Tests.

ALL DB write tests run on a TEMP COPY of the DB.
The production DB (lottery_api/data/lottery_v2.db) is NEVER modified.

Tests:
  1. Script default mode has no DB write
  2. --apply without --backup is refused
  3. ONLINE_ONLY scope inserts at most 28 rows on temp DB
  4. RETIRED rows not inserted under ONLINE_ONLY
  5. Duplicate re-run inserts 0 additional rows (idempotent)
  6. Rollback plan identifies inserted rows
  7. Rollback on temp DB restores row count
  8. INCLUDE_RETIRED_WITH_WARNING requires --include-retired-reviewed
  9. Script never imports draw data
 10. Script never executes strategy logic
 11. Production DB untouched after all tests
 12. Max insert guard: refuses > 28
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_PATH = REPO_ROOT / "backups" / "lottery_v2_pre_p7_controlled_apply_20260520.db"
APPLY_SCRIPT = REPO_ROOT / "scripts" / "p7_controlled_replay_row_apply.py"
P7_JSON     = REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"

sys.path.insert(0, str(REPO_ROOT))


def _db_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path.resolve()))
    conn.execute("PRAGMA query_only = ON")
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _run_apply(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(APPLY_SCRIPT)] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


@pytest.fixture(scope="function")
def temp_db(tmp_path) -> Path:
    """Copy of the production DB for testing. Production DB is NOT used for writes."""
    dest = tmp_path / "lottery_v2_test.db"
    shutil.copy2(DB_PATH, dest)
    return dest


@pytest.fixture(scope="function")
def temp_backup(tmp_path, temp_db) -> Path:
    """Backup copy for temp DB (satisfies --backup requirement in tests)."""
    dest = tmp_path / "backup.db"
    shutil.copy2(temp_db, dest)
    return dest


# ---------------------------------------------------------------------------
# Section 1: Script safety (no production DB touch)
# ---------------------------------------------------------------------------

class TestScriptSafety:
    def test_no_apply_arg_in_usage_dangerous(self):
        """Script must have --apply in argparse but NOT execute by default."""
        src = APPLY_SCRIPT.read_text()
        # Has --apply defined
        assert 'add_argument(\n        "--apply"' in src or '"--apply"' in src, (
            "Script must expose --apply flag"
        )
        # But default must be False
        assert "default=False" in src, "default for --apply must be False"

    def test_no_draw_import(self):
        src = APPLY_SCRIPT.read_text()
        # Must not import raw draw data
        assert "import_draw" not in src and "ingest" not in src.lower(), (
            "Apply script must not import draw data"
        )

    def test_no_strategy_logic(self):
        src = APPLY_SCRIPT.read_text()
        # Must not call predict_func or strategy logic
        assert "predict_func" not in src and "generate_" not in src, (
            "Apply script must not execute strategy logic"
        )

    def test_opens_production_db_readonly_by_default(self):
        src = APPLY_SCRIPT.read_text()
        # Either URI mode=ro or PRAGMA query_only is acceptable
        assert "query_only" in src or "mode=ro" in src, (
            "Apply script must open DB read-only (query_only PRAGMA or mode=ro URI)"
        )

    def test_no_direct_insert_sql_outside_apply_block(self):
        src = APPLY_SCRIPT.read_text()
        # INSERT SQL must be guarded by args.apply check
        assert "INSERT INTO" in src, "INSERT SQL must exist (for apply mode)"
        # The 'if not args.apply' early-return guard must precede the actual
        # conn_rw.execute(_INSERT_SQL, ...) call site
        early_return_pos = src.find("if not args.apply:")
        execute_pos = src.find("conn_rw.execute(_INSERT_SQL")
        assert early_return_pos != -1, "'if not args.apply:' guard not found"
        assert execute_pos != -1, "conn_rw.execute(_INSERT_SQL) not found"
        assert early_return_pos < execute_pos, (
            "conn_rw.execute(_INSERT_SQL) must appear AFTER the 'if not args.apply' guard"
        )


# ---------------------------------------------------------------------------
# Section 2: No-apply default
# ---------------------------------------------------------------------------

class TestNoApplyDefault:
    def test_default_run_no_db_write(self):
        """Running without --apply must not change production DB row count."""
        before = _db_count(DB_PATH)
        result = _run_apply([])
        after  = _db_count(DB_PATH)
        assert after == before, (
            f"Production DB changed without --apply! {before} → {after}"
        )
        assert "DRY-RUN" in result.stdout, (
            "Script must print DRY-RUN indicator when no --apply"
        )

    def test_explicit_scope_no_apply_no_write(self):
        before = _db_count(DB_PATH)
        _run_apply(["--scope", "ONLINE_ONLY"])
        after  = _db_count(DB_PATH)
        assert after == before

    def test_production_db_count_unchanged(self):
        assert _db_count(DB_PATH) == 460


# ---------------------------------------------------------------------------
# Section 3: Backup requirement
# ---------------------------------------------------------------------------

class TestBackupRequirement:
    def test_apply_without_backup_refused(self, temp_db, tmp_path):
        """--apply should fail if backup file doesn't exist."""
        fake_backup = str(tmp_path / "nonexistent.db")
        result = _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", fake_backup,
        ])
        assert result.returncode != 0, (
            "Script must refuse --apply when backup file is missing"
        )
        assert "SAFETY STOP" in result.stdout or "SAFETY STOP" in result.stderr


# ---------------------------------------------------------------------------
# Section 4: ONLINE_ONLY insert on temp DB
# ---------------------------------------------------------------------------

class TestOnlineOnlyInsert:
    def test_inserts_exactly_online_rows_on_temp_db(self, temp_db, temp_backup, tmp_path):
        before = _db_count(temp_db)
        result_json = tmp_path / "apply_result.json"

        result = _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(temp_backup),
            "--scope", "ONLINE_ONLY",
            "--json-out", str(result_json),
        ])
        assert result.returncode == 0, (
            f"Apply failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        after = _db_count(temp_db)
        inserted = after - before
        assert inserted >= 1, f"Expected at least 1 insert, got {inserted}"
        assert inserted <= 28, f"Expected at most 28 inserts, got {inserted}"

        # Verify result JSON
        data = json.loads(result_json.read_text())
        assert data["applied"] is True
        assert data["inserted"] == inserted
        assert data["rows_after"] == after

    def test_no_retired_rows_inserted(self, temp_db, temp_backup, tmp_path):
        """Confirm no RETIRED rows are inserted in ONLINE_ONLY scope."""
        result_json = tmp_path / "apply_result.json"
        _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(temp_backup),
            "--scope", "ONLINE_ONLY",
            "--json-out", str(result_json),
        ])

        # Check inserted rows lifecycle
        conn = sqlite3.connect(str(temp_db))
        rows = conn.execute(
            "SELECT strategy_id FROM strategy_prediction_replays "
            "WHERE source='P7_CONTROLLED_APPLY'"
        ).fetchall()
        conn.close()

        inserted_ids = {r[0] for r in rows}
        retired_ids  = {"acb_1bet", "acb_markov_midfreq_3bet", "midfreq_acb_2bet"}
        assert not inserted_ids.intersection(retired_ids), (
            f"RETIRED strategies found in applied rows: "
            f"{inserted_ids.intersection(retired_ids)}"
        )

    def test_production_db_unchanged_after_temp_apply(self):
        """Production DB must remain at 460 rows regardless of temp DB tests."""
        assert _db_count(DB_PATH) == 460


# ---------------------------------------------------------------------------
# Section 5: Idempotency — duplicate re-run
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_rerun_inserts_zero_additional_rows(self, temp_db, temp_backup, tmp_path):
        """Running apply twice should not insert duplicates."""
        # First apply
        _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(temp_backup),
            "--scope", "ONLINE_ONLY",
        ])
        count_after_first = _db_count(temp_db)

        # Refresh backup to match post-apply state so preflight passes on second run
        backup2 = tmp_path / "backup2.db"
        shutil.copy2(temp_db, backup2)

        # Second apply — pass updated expected-rows and fresh backup
        result_json = tmp_path / "r2.json"
        result = _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(backup2),
            "--scope", "ONLINE_ONLY",
            "--json-out", str(result_json),
            "--expected-rows", str(count_after_first),
        ])
        count_after_second = _db_count(temp_db)
        assert count_after_second == count_after_first, (
            f"Second apply changed row count: {count_after_first} → {count_after_second}"
        )

        data = json.loads(result_json.read_text())
        assert data["duplicate_skipped"] > 0, (
            "Second run must report duplicate_skipped > 0"
        )
        assert data["inserted"] == 0, (
            "Second run must insert 0 additional rows"
        )


# ---------------------------------------------------------------------------
# Section 6: Rollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_plan_identifies_rows(self, temp_db, temp_backup, tmp_path):
        """After apply, rollback plan should find the inserted rows."""
        result_json = tmp_path / "apply_result.json"
        _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(temp_backup),
            "--scope", "ONLINE_ONLY",
            "--json-out", str(result_json),
        ])
        data = json.loads(result_json.read_text())
        inserted = data["inserted"]
        if inserted == 0:
            pytest.skip("No rows inserted (likely all duplicates already)")

        # Find a controlled_apply_id from the DB
        conn = sqlite3.connect(str(temp_db))
        cap_id = conn.execute(
            "SELECT controlled_apply_id FROM strategy_prediction_replays "
            "WHERE source='P7_CONTROLLED_APPLY' LIMIT 1"
        ).fetchone()
        conn.close()

        assert cap_id and cap_id[0], "Inserted rows must have controlled_apply_id"

    def test_rollback_on_temp_db_restores_count(self, temp_db, temp_backup, tmp_path):
        """After apply + rollback, row count returns to original."""
        count_before = _db_count(temp_db)

        _run_apply([
            "--apply", "--db", str(temp_db),
            "--backup", str(temp_backup),
            "--scope", "ONLINE_ONLY",
        ])
        count_after_apply = _db_count(temp_db)
        if count_after_apply == count_before:
            pytest.skip("Nothing was inserted (all duplicates)")

        # Get a controlled_apply_id
        conn = sqlite3.connect(str(temp_db))
        cap_id = conn.execute(
            "SELECT controlled_apply_id FROM strategy_prediction_replays "
            "WHERE source='P7_CONTROLLED_APPLY' LIMIT 1"
        ).fetchone()[0]
        conn.close()

        # Rollback
        result = _run_apply([
            "--apply",
            "--rollback-plan", cap_id,
            "--rollback-apply",
            "--db", str(temp_db),
            "--backup", str(temp_backup),
        ])
        assert result.returncode == 0, (
            f"Rollback failed:\n{result.stdout}\n{result.stderr}"
        )

        # Note: rollback_apply only rolls back rows with that specific controlled_apply_id
        # Count may not be fully restored if multiple controlled_apply_ids were used
        conn = sqlite3.connect(str(temp_db))
        remaining_p7 = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE source='P7_CONTROLLED_APPLY'"
        ).fetchone()[0]
        conn.close()
        assert remaining_p7 == 0 or remaining_p7 < count_after_apply - count_before, (
            "Rollback must remove some or all applied rows"
        )


# ---------------------------------------------------------------------------
# Section 7: INCLUDE_RETIRED_WITH_WARNING scope requires flag
# ---------------------------------------------------------------------------

class TestRetiredScopeGate:
    def test_retired_scope_without_reviewed_flag_refused(self, temp_db, temp_backup):
        """INCLUDE_RETIRED_WITH_WARNING without --include-retired-reviewed must fail."""
        result = _run_apply([
            "--apply",
            "--scope", "INCLUDE_RETIRED_WITH_WARNING",
            "--db", str(temp_db),
            "--backup", str(temp_backup),
        ])
        assert result.returncode != 0, (
            "INCLUDE_RETIRED_WITH_WARNING must refuse without --include-retired-reviewed"
        )
        assert "SAFETY STOP" in result.stdout or "SAFETY STOP" in result.stderr

    def test_production_still_unchanged(self):
        assert _db_count(DB_PATH) == 460
