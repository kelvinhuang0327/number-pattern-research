"""
tests/test_p131_apply_acb_markov_midfreq_3bet.py
=================================================
Verifies P131 controlled apply of acb_markov_midfreq_3bet bet-2/bet-3 rows.
"""

import json
import sqlite3
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parent.parent
OUT_JSON    = REPO_ROOT / "outputs/replay/p131_apply_acb_markov_midfreq_3bet_20260528.json"
OUT_MD      = REPO_ROOT / "docs/replay/p131_apply_acb_markov_midfreq_3bet_20260528.md"
DB_PATH     = REPO_ROOT / "lottery_api/data/lottery_v2.db"

STRATEGY_ID = "acb_markov_midfreq_3bet"
LOTTERY_TYPE = "DAILY_539"

EXPECTED_ROWS_BEFORE    = 72422
EXPECTED_ROWS_AFTER     = 75422
EXPECTED_ROWS_CURRENT   = 82922   # Post P133 apply (pp3_freqort_4bet +4500)
EXPECTED_INSERT_ROWS    = 3000
EXPECTED_BET1           = 1500
EXPECTED_BET2           = 1500
EXPECTED_BET3           = 1500
EXPECTED_STRATEGY_TOTAL = 4500
CONTROLLED_APPLY_ID     = "P131_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V20260528"


def _load():
    assert OUT_JSON.exists(), f"P131 JSON not found: {OUT_JSON}"
    return json.loads(OUT_JSON.read_text(encoding="utf-8"))


def _db():
    return sqlite3.connect(str(DB_PATH))


# ---------------------------------------------------------------------------
# Artifact existence
# ---------------------------------------------------------------------------

def test_json_exists():
    assert OUT_JSON.exists()


def test_md_exists():
    assert OUT_MD.exists()


# ---------------------------------------------------------------------------
# Task identity
# ---------------------------------------------------------------------------

def test_task_id():
    d = _load()
    assert d["task_id"] == "P131"


def test_classification():
    d = _load()
    assert d["classification"] == "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_authorization_present():
    d = _load()
    assert d["authorization"]["authorization_present"] is True


def test_authorization_apply_allowed():
    d = _load()
    assert d["authorization"]["apply_allowed"] is True


def test_authorization_exact_phrase():
    d = _load()
    auth = d["authorization"]
    assert auth["exact_required_phrase"] == (
        "P130_AUTHORIZED_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_BET2_BET3_V20260528"
    )
    assert auth["authorization_text_observed"] == auth["exact_required_phrase"]


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def test_backup_created():
    d = _load()
    assert d["backup"]["backup_created"] is True


def test_backup_row_count():
    d = _load()
    assert d["backup"]["backup_row_count"] == EXPECTED_ROWS_BEFORE


def test_backup_file_exists():
    d = _load()
    bp = Path(d["backup"]["backup_path"])
    assert bp.exists(), f"Backup file missing: {bp}"


# ---------------------------------------------------------------------------
# DB rows before / after
# ---------------------------------------------------------------------------

def test_db_rows_before():
    d = _load()
    assert d["db_snapshot_before"]["replay_rows"] == EXPECTED_ROWS_BEFORE


def test_db_rows_after():
    d = _load()
    assert d["db_snapshot_after"]["replay_rows"] == EXPECTED_ROWS_AFTER


def test_db_actual_total():
    conn = _db()
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    # P133 applied pp3_freqort_4bet after P132 — live DB is now 82922
    assert total == EXPECTED_ROWS_CURRENT


# ---------------------------------------------------------------------------
# Apply scope
# ---------------------------------------------------------------------------

def test_apply_scope_strategy_id():
    d = _load()
    assert d["apply_scope"]["strategy_id"] == STRATEGY_ID


def test_apply_scope_lottery_type():
    d = _load()
    assert d["apply_scope"]["lottery_type"] == LOTTERY_TYPE


def test_apply_scope_expected_insert_rows():
    d = _load()
    assert d["apply_scope"]["expected_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_actual_insert_rows():
    d = _load()
    assert d["apply_scope"]["actual_insert_rows"] == EXPECTED_INSERT_ROWS


def test_apply_scope_executed():
    d = _load()
    assert d["apply_scope"]["apply_executed"] is True


def test_apply_scope_target_bet_count():
    d = _load()
    assert d["apply_scope"]["target_bet_count"] == 3


# ---------------------------------------------------------------------------
# Inserted rows — strategy_id and lottery_type
# ---------------------------------------------------------------------------

def test_inserted_rows_strategy_id():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id=? AND strategy_id!=?",
        (CONTROLLED_APPLY_ID, STRATEGY_ID)
    ).fetchone()[0]
    conn.close()
    assert cnt == 0, f"Found {cnt} rows with wrong strategy_id under P131 controlled_apply_id"


def test_inserted_rows_lottery_type():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id=? AND lottery_type!=?",
        (CONTROLLED_APPLY_ID, LOTTERY_TYPE)
    ).fetchone()[0]
    conn.close()
    assert cnt == 0, f"Found {cnt} rows with wrong lottery_type under P131"


def test_inserted_rows_count():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (CONTROLLED_APPLY_ID,)
    ).fetchone()[0]
    conn.close()
    assert cnt == EXPECTED_INSERT_ROWS


# ---------------------------------------------------------------------------
# bet_index distribution
# ---------------------------------------------------------------------------

def test_bet_index_bet1():
    d = _load()
    assert d["bet_index_validation"]["bet1_count"] == EXPECTED_BET1


def test_bet_index_bet2():
    d = _load()
    assert d["bet_index_validation"]["bet2_count"] == EXPECTED_BET2


def test_bet_index_bet3():
    d = _load()
    assert d["bet_index_validation"]["bet3_count"] == EXPECTED_BET3


def test_bet_index_distribution_ok():
    d = _load()
    assert d["bet_index_validation"]["distribution_ok"] is True


def test_bet_index_validation_pass():
    d = _load()
    assert d["bet_index_validation"]["validation"] == "PASS"


def test_bet_index_actual_db():
    conn = _db()
    rows = conn.execute(
        "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
        (STRATEGY_ID,)
    ).fetchall()
    conn.close()
    dist = {r[0]: r[1] for r in rows}
    assert dist == {1: 1500, 2: 1500, 3: 1500}, f"Unexpected dist: {dist}"


# ---------------------------------------------------------------------------
# Duplicate guard
# ---------------------------------------------------------------------------

def test_duplicate_guard_constraint_active():
    d = _load()
    assert d["duplicate_guard"]["constraint_active"] is True


def test_duplicate_guard_rejected():
    d = _load()
    assert d["duplicate_guard"]["duplicate_rejected_in_validation"] is True


def test_duplicate_guard_ok():
    d = _load()
    assert d["duplicate_guard"]["guard_ok"] is True


# ---------------------------------------------------------------------------
# Row preservation
# ---------------------------------------------------------------------------

def test_row_preservation():
    d = _load()
    rp = d["row_preservation_check"]
    assert rp["rows_preserved_ok"] is True
    assert rp["actual_rows_after"] == EXPECTED_ROWS_AFTER
    assert rp["expected_rows_after"] == EXPECTED_ROWS_AFTER


# ---------------------------------------------------------------------------
# Blocked / excluded strategies
# ---------------------------------------------------------------------------

def test_p8_not_applied():
    d = _load()
    assert d["blocked_or_excluded"]["P8_not_applied"] is True


def test_p9_not_applied():
    d = _load()
    assert d["blocked_or_excluded"]["P9_not_applied"] is True


def test_p11_not_applied():
    d = _load()
    assert d["blocked_or_excluded"]["P11_not_applied"] is True


def test_p10_p12_not_apply_ready():
    d = _load()
    assert d["blocked_or_excluded"]["P10_P12_not_apply_ready_until_re_evaluation"] is True


def test_4star_excluded():
    d = _load()
    assert d["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_p108_not_run():
    d = _load()
    assert d["blocked_or_excluded"]["P108_not_run"] is True


def test_p117_not_run():
    d = _load()
    assert d["blocked_or_excluded"]["P117_not_run"] is True


def test_p118_not_run():
    d = _load()
    assert d["blocked_or_excluded"]["P118_not_run"] is True


def test_rejected_strategies_no_action():
    d = _load()
    assert d["blocked_or_excluded"]["rejected_strategies_no_action"] is True


def test_no_scheduler_install():
    d = _load()
    assert d["blocked_or_excluded"]["no_scheduler_install"] is True


def test_no_lifecycle_champion_registry_mutation():
    d = _load()
    assert d["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


def test_p8_applied_after_p132_db():
    # P132 applied midfreq_fourier_mk_3bet bet-2+bet-3 = 3000 rows after P131
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='midfreq_fourier_mk_3bet' AND bet_index>1"
    ).fetchone()[0]
    conn.close()
    assert cnt == 3000, f"P8 midfreq_fourier_mk_3bet should have 3000 bet_index>1 rows after P132, got {cnt}"


def test_p9_not_applied_db():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='fourier_rhythm_3bet' AND bet_index>1"
    ).fetchone()[0]
    conn.close()
    assert cnt == 0, f"P9 fourier_rhythm_3bet has {cnt} extra bet rows — should be 0"


def test_p11_applied_after_p133_db():
    # P133 applied pp3_freqort_4bet bet-2/bet-3/bet-4 = 4500 rows after P131/P132
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='pp3_freqort_4bet' AND bet_index>1"
    ).fetchone()[0]
    conn.close()
    assert cnt == 4500, f"P11 pp3_freqort_4bet should have 4500 bet_index>1 rows after P133, got {cnt}"


def test_p10_not_applied_db():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND bet_index>1"
    ).fetchone()[0]
    conn.close()
    assert cnt == 0, f"P10 power_precision_3bet has {cnt} extra bet rows — should be 0"


def test_p12_not_applied_db():
    conn = _db()
    cnt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND bet_index>1"
    ).fetchone()[0]
    conn.close()
    assert cnt == 0, f"P12 power_orthogonal_5bet has {cnt} extra bet rows — should be 0"


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------

def test_md_contains_backup_path():
    content = OUT_MD.read_text(encoding="utf-8")
    d = _load()
    assert d["backup"]["backup_path"] in content


def test_md_contains_rollback_reference():
    content = OUT_MD.read_text(encoding="utf-8")
    assert "Rollback" in content or "rollback" in content
    assert "cp " in content


def test_md_contains_classification():
    content = OUT_MD.read_text(encoding="utf-8")
    assert "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED" in content


# ---------------------------------------------------------------------------
# Drift guard
# ---------------------------------------------------------------------------

def test_drift_guard_update():
    d = _load()
    dg = d["drift_guard_update"]
    assert dg["update_required"] is True
    assert dg["new_total"] == EXPECTED_ROWS_AFTER


def test_drift_guard_pass():
    """Verify drift guard script passes at new baseline."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "scripts/replay_lifecycle_drift_guard.py", "--strict"],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    assert result.returncode == 0, (
        f"Drift guard FAIL:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout


# ---------------------------------------------------------------------------
# No forbidden files staged
# ---------------------------------------------------------------------------

def test_no_runtime_pid_files_staged():
    """Verify no runtime/pid/log files are staged."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    staged = result.stdout.strip().splitlines()
    forbidden_patterns = [".pid", ".log", "__pycache__", ".pyc"]
    violations = [f for f in staged if any(p in f for p in forbidden_patterns)]
    assert not violations, f"Forbidden files staged: {violations}"


# ---------------------------------------------------------------------------
# P130 source summary
# ---------------------------------------------------------------------------

def test_p130_source_classification():
    d = _load()
    assert d["p130_source_summary"]["classification"] == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY"


def test_p130_p7_in_safe_candidates():
    d = _load()
    assert d["p130_source_summary"]["p7_in_safe_candidates"] is True


def test_p130_p7_apply_ready():
    d = _load()
    assert d["p130_source_summary"]["p7_apply_ready_after_authorization"] is True
