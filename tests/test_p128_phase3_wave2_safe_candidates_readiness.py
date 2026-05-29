"""
tests/test_p128_phase3_wave2_safe_candidates_readiness.py
=========================================================
Verification tests for P128 Phase 3: Wave 2 safe candidate readiness.

Validates the JSON artifact and live DB state. No DB writes.
"""

import json
import pathlib
import sqlite3

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

PHASE3_JSON = (
    REPO_ROOT / "outputs" / "replay" / "p128_phase3_wave2_safe_candidates_readiness_20260528.json"
)
PHASE3_MD = (
    REPO_ROOT / "docs" / "replay" / "p128_phase3_wave2_safe_candidates_readiness_20260528.md"
)
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_DB_ROWS = 72422            # P128P3 artifact snapshot (no DB write in P128P3)
EXPECTED_DB_ROWS_CURRENT = 82922    # After P133 applied pp3_freqort_4bet +4500
SAFE_CANDIDATE_IDS = [
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
]
BLOCKED_CANDIDATE_IDS = [
    "power_precision_3bet",
    "power_orthogonal_5bet",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def phase3_data():
    assert PHASE3_JSON.exists(), f"Phase 3 JSON not found: {PHASE3_JSON}"
    return json.loads(PHASE3_JSON.read_text())


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. JSON artifact identity
# ---------------------------------------------------------------------------


def test_phase3_json_exists():
    assert PHASE3_JSON.exists()


def test_task_id(phase3_data):
    assert phase3_data["task_id"] == "P128_PHASE3"


def test_classification(phase3_data):
    assert phase3_data["classification"] == "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY"


# ---------------------------------------------------------------------------
# 2. DB state
# ---------------------------------------------------------------------------


def test_db_rows_artifact(phase3_data):
    assert phase3_data["db_snapshot"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_live(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    # P128P3 was read-only. P131 applied acb_markov_midfreq_3bet +3000 rows.
    assert count == EXPECTED_DB_ROWS_CURRENT, (
        f"DB has {count} rows, expected {EXPECTED_DB_ROWS_CURRENT} (post-P131)"
    )


def test_bet_index_schema_exists(phase3_data):
    assert phase3_data["db_snapshot"]["bet_index_schema_exists"] is True


def test_bet_index_column_live(db_conn):
    cols = [r[1] for r in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_orphan_cleared_in_artifact(phase3_data):
    assert phase3_data["db_snapshot"]["orphan_bet_index2_count"] == 0
    assert phase3_data["db_snapshot"]["orphan_cleared"] is True


def test_orphan_cleared_live(db_conn):
    count = db_conn.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index = 2
          AND replay_run_id = 6
          AND (source IS NULL OR source = '')
          AND controlled_apply_id IS NULL
          AND provenance_hash IS NULL
          AND truth_level IS NULL
          AND CAST(target_draw AS INTEGER) BETWEEN 99000085 AND 99000104
        """
    ).fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# 3. RSR-6 cleanup artifact validation
# ---------------------------------------------------------------------------


def test_rsr6_cleanup_classification(phase3_data):
    rsr6 = phase3_data["rsr6_cleanup_source_summary"]
    assert rsr6["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"


def test_rsr6_cleanup_classification_pass(phase3_data):
    assert phase3_data["rsr6_cleanup_source_summary"]["classification_pass"] is True


def test_rsr6_deleted_rows(phase3_data):
    assert phase3_data["rsr6_cleanup_source_summary"]["deleted_rows"] == 40


# ---------------------------------------------------------------------------
# 4. P128 Phase 2 artifact validation
# ---------------------------------------------------------------------------


def test_p128_phase2_classification(phase3_data):
    p2 = phase3_data["p128_phase2_source_summary"]
    assert p2["classification"] == "P128_WAVE2_ADAPTER_PHASE2_READY"


def test_p128_phase2_classification_pass(phase3_data):
    assert phase3_data["p128_phase2_source_summary"]["classification_pass"] is True


# ---------------------------------------------------------------------------
# 5. Safe candidate scope
# ---------------------------------------------------------------------------


def test_excludes_rsr6_blocked(phase3_data):
    assert phase3_data["safe_candidate_scope"]["excludes_rsr6_blocked"] is True


def test_no_db_write_in_phase3(phase3_data):
    assert phase3_data["safe_candidate_scope"]["db_write_in_phase3"] is False


def test_no_controlled_apply_in_phase3(phase3_data):
    assert phase3_data["safe_candidate_scope"]["controlled_apply_executed"] is False


def test_no_replay_rows_inserted(phase3_data):
    assert phase3_data["safe_candidate_scope"]["replay_rows_inserted"] == 0


def test_production_db_rows_expected(phase3_data):
    assert phase3_data["safe_candidate_scope"]["production_db_rows_expected"] == EXPECTED_DB_ROWS


def test_production_db_rows_after(phase3_data):
    assert phase3_data["safe_candidate_scope"]["production_db_rows_after"] == EXPECTED_DB_ROWS


def test_safe_candidate_ids_present(phase3_data):
    scope_ids = phase3_data["safe_candidate_scope"]["candidate_strategy_ids"]
    for sid in SAFE_CANDIDATE_IDS:
        assert sid in scope_ids, f"Safe candidate {sid} missing from scope"


# ---------------------------------------------------------------------------
# 6. Blocked candidate scope
# ---------------------------------------------------------------------------


def test_blocked_power_precision(phase3_data):
    blocked = phase3_data["blocked_candidate_scope"]
    pp = blocked["power_precision_3bet"]
    assert pp["apply_ready"] is False
    assert pp["reason"] == "post_rsr6_cleanup_apply_gate_re_evaluation_required"
    assert pp["rsr6_cleanup_completed"] is True
    assert pp["orphan_bet_index2_cleared"] is True


def test_blocked_power_orthogonal(phase3_data):
    blocked = phase3_data["blocked_candidate_scope"]
    po = blocked["power_orthogonal_5bet"]
    assert po["apply_ready"] is False
    assert po["reason"] == "post_rsr6_cleanup_apply_gate_re_evaluation_required"
    assert po["rsr6_cleanup_completed"] is True
    assert po["orphan_bet_index2_cleared"] is True


def test_blocked_apply_ready_false(phase3_data):
    assert phase3_data["blocked_candidate_scope"]["apply_ready"] is False


# ---------------------------------------------------------------------------
# 7. Readiness matrix
# ---------------------------------------------------------------------------


def test_readiness_matrix_non_empty(phase3_data):
    assert len(phase3_data["readiness_matrix"]) > 0


def test_readiness_matrix_has_all_candidates(phase3_data):
    matrix_ids = [r["strategy_id"] for r in phase3_data["readiness_matrix"]]
    for sid in SAFE_CANDIDATE_IDS + BLOCKED_CANDIDATE_IDS:
        assert sid in matrix_ids, f"Strategy {sid} missing from readiness matrix"


def test_safe_candidates_dry_run_ready(phase3_data):
    for r in phase3_data["readiness_matrix"]:
        if r["strategy_id"] in SAFE_CANDIDATE_IDS:
            assert r["dry_run_ready"] is True, f"{r['strategy_id']} not dry_run_ready"
            assert r["rsr6_blocked"] is False


def test_blocked_candidates_not_dry_run_ready(phase3_data):
    for r in phase3_data["readiness_matrix"]:
        if r["strategy_id"] in BLOCKED_CANDIDATE_IDS:
            assert r["dry_run_ready"] is False
            assert r["rsr6_blocked"] is True
            assert r.get("apply_ready") is False


# ---------------------------------------------------------------------------
# 8. Apply gate status
# ---------------------------------------------------------------------------


def test_apply_gate_dry_run_only(phase3_data):
    assert phase3_data["apply_gate_status"]["dry_run_only"] is True


def test_apply_gate_no_controlled_apply(phase3_data):
    assert phase3_data["apply_gate_status"]["controlled_apply_executed"] is False


def test_apply_gate_no_replay_rows(phase3_data):
    assert phase3_data["apply_gate_status"]["replay_rows_inserted"] == 0


def test_apply_gate_authorization_required(phase3_data):
    assert phase3_data["apply_gate_status"]["per_strategy_authorization_required_later"] is True


# ---------------------------------------------------------------------------
# 9. Blocked/excluded governance
# ---------------------------------------------------------------------------


def test_blocked_4star(phase3_data):
    assert phase3_data["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108(phase3_data):
    assert phase3_data["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117(phase3_data):
    assert phase3_data["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118(phase3_data):
    assert phase3_data["blocked_or_excluded"]["P118_not_run"] is True


def test_blocked_rejected_strategies(phase3_data):
    assert phase3_data["blocked_or_excluded"]["rejected_strategies_no_action"] is True


def test_no_scheduler_install(phase3_data):
    assert phase3_data["blocked_or_excluded"]["no_scheduler_install"] is True


def test_no_lifecycle_mutation(phase3_data):
    assert phase3_data["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


# ---------------------------------------------------------------------------
# 10. Markdown content checks
# ---------------------------------------------------------------------------


def test_markdown_exists():
    assert PHASE3_MD.exists()


def test_markdown_has_safe_candidate_scope():
    text = PHASE3_MD.read_text()
    assert "Safe Candidate Scope" in text or "safe candidate" in text.lower()


def test_markdown_has_blocked_candidate_scope():
    text = PHASE3_MD.read_text()
    assert "Blocked Candidate" in text or "blocked candidate" in text.lower()


def test_markdown_has_apply_gate_rules():
    text = PHASE3_MD.read_text()
    assert "Apply Gate" in text or "apply gate" in text.lower()


def test_markdown_has_safe_candidates():
    text = PHASE3_MD.read_text()
    for sid in SAFE_CANDIDATE_IDS:
        assert sid in text, f"Safe candidate {sid} not in Markdown"


def test_markdown_has_blocked_candidates():
    text = PHASE3_MD.read_text()
    for sid in BLOCKED_CANDIDATE_IDS:
        assert sid in text, f"Blocked candidate {sid} not in Markdown"


def test_markdown_has_classification():
    text = PHASE3_MD.read_text()
    assert "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY" in text


# ---------------------------------------------------------------------------
# 11. Live DB: safe candidates have only bet_index=1 rows
# ---------------------------------------------------------------------------


def test_safe_candidates_no_bi2_rows(db_conn):
    # P131 applied acb_markov_midfreq_3bet. P132 applied midfreq_fourier_mk_3bet.
    # P133 applied pp3_freqort_4bet. P9 fourier_rhythm_3bet still 0.
    APPLIED = {"acb_markov_midfreq_3bet", "midfreq_fourier_mk_3bet", "pp3_freqort_4bet"}
    for sid in SAFE_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (sid,),
        ).fetchone()[0]
        if sid in APPLIED:
            assert count == 1500, f"{sid} should have 1500 bi=2 rows after P131/P132/P133, got {count}"
        else:
            assert count == 0, f"{sid} should have 0 bi=2 rows (not yet applied), got {count}"


def test_blocked_candidates_no_bi2_rows(db_conn):
    # After RSR-6 cleanup, blocked candidates also have 0 bi=2 rows
    for sid in BLOCKED_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (sid,),
        ).fetchone()[0]
        assert count == 0, f"{sid} should have 0 bi=2 rows after cleanup, got {count}"


def test_blocked_candidates_bi1_rows_present(db_conn):
    for sid in BLOCKED_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (sid,),
        ).fetchone()[0]
        assert count > 0, f"{sid} must have bi=1 rows present"
        # Post RSR-6 cleanup: should be exactly 1550
        assert count == 1550, f"{sid} bi=1 rows expected 1550, got {count}"


# ---------------------------------------------------------------------------
# 12. No forbidden files staged
# ---------------------------------------------------------------------------


def test_no_forbidden_files_staged():
    import subprocess
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    staged = result.stdout
    for forbidden in [".history", ".pid", ".runtime", "lottery_v2.db"]:
        # lottery_v2.db should NOT be staged in this phase (read-only)
        if forbidden == "lottery_v2.db":
            staged_files = [line[3:] for line in staged.splitlines() if line.startswith("A ")]
            assert not any("lottery_v2.db" in f for f in staged_files), (
                "DB should not be staged in Phase 3 (read-only phase)"
            )
        else:
            assert forbidden not in staged, f"Forbidden pattern '{forbidden}' in git status"
