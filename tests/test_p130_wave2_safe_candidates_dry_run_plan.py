"""
tests/test_p130_wave2_safe_candidates_dry_run_plan.py
=====================================================
Verification tests for P130: Wave 2 safe candidates controlled_apply dry-run plan.

Validates the JSON artifact and live DB state. No DB writes.
"""

import json
import pathlib
import sqlite3

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p130_wave2_safe_candidates_dry_run_plan_20260528.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p130_wave2_safe_candidates_dry_run_plan_20260528.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_DB_ROWS = 72422
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

EXPECTED_TOTAL_INSERT = 13502

EXPECTED_ESTIMATES = {
    "acb_markov_midfreq_3bet": 3000,
    "midfreq_fourier_mk_3bet": 3000,
    "fourier_rhythm_3bet": 3002,
    "pp3_freqort_4bet": 4500,
}

EXPECTED_APPLY_ORDER = [
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "pp3_freqort_4bet",
    "fourier_rhythm_3bet",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P130 JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text())


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. Artifact identity
# ---------------------------------------------------------------------------


def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P130"


def test_classification(artifact):
    assert artifact["classification"] == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY"


def test_generated_at_present(artifact):
    assert "generated_at" in artifact and artifact["generated_at"]


# ---------------------------------------------------------------------------
# 2. DB snapshot (read-only, unchanged)
# ---------------------------------------------------------------------------


def test_db_rows_artifact(artifact):
    assert artifact["db_snapshot"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_expected_match(artifact):
    assert artifact["db_snapshot"]["rows_match_expected"] is True


def test_db_rows_live(db_conn):
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_DB_ROWS, f"DB has {count} rows, expected {EXPECTED_DB_ROWS}"


def test_bet_index_schema_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_schema_exists"] is True


# ---------------------------------------------------------------------------
# 3. P128 Phase 3 source summary
# ---------------------------------------------------------------------------


def test_p128_phase3_classification(artifact):
    p3 = artifact["p128_phase3_source_summary"]
    assert p3["classification"] == "P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY"


def test_p128_phase3_classification_pass(artifact):
    assert artifact["p128_phase3_source_summary"]["classification_pass"] is True


def test_p128_phase3_all_safe_dry_run_ready(artifact):
    assert artifact["p128_phase3_source_summary"]["all_safe_dry_run_ready"] is True


# ---------------------------------------------------------------------------
# 4. Safe candidate dry-run plan strategies
# ---------------------------------------------------------------------------


def test_safe_candidate_plan_is_list(artifact):
    assert isinstance(artifact["safe_candidate_dry_run_plan"], list)


def test_safe_candidate_plan_has_four_strategies(artifact):
    assert len(artifact["safe_candidate_dry_run_plan"]) == 4


def test_safe_candidate_plan_has_all_ids(artifact):
    plan_ids = [s["strategy_id"] for s in artifact["safe_candidate_dry_run_plan"]]
    for sid in SAFE_CANDIDATE_IDS:
        assert sid in plan_ids, f"Safe candidate {sid} missing from dry-run plan"


@pytest.mark.parametrize("strategy_id,expected_est", list(EXPECTED_ESTIMATES.items()))
def test_estimated_insert_rows_per_strategy(artifact, strategy_id, expected_est):
    plan = {s["strategy_id"]: s for s in artifact["safe_candidate_dry_run_plan"]}
    assert strategy_id in plan
    assert plan[strategy_id]["estimated_insert_rows"] == expected_est, (
        f"{strategy_id}: expected {expected_est}, got {plan[strategy_id]['estimated_insert_rows']}"
    )


# ---------------------------------------------------------------------------
# 5. P9 fourier_rhythm_3bet anomaly flag
# ---------------------------------------------------------------------------


def test_p9_anomaly_in_summary(artifact):
    summary = artifact["estimated_insert_rows_summary"]
    p9 = next(
        (s for s in summary["per_candidate"] if s["strategy_id"] == "fourier_rhythm_3bet"),
        None,
    )
    assert p9 is not None
    assert p9["p9_anomaly"] is True


def test_p9_estimated_insert_is_3002(artifact):
    summary = artifact["estimated_insert_rows_summary"]
    p9 = next(
        s for s in summary["per_candidate"] if s["strategy_id"] == "fourier_rhythm_3bet"
    )
    assert p9["estimated_insert_rows"] == 3002


def test_p9_anomaly_note_in_summary(artifact):
    note = artifact["estimated_insert_rows_summary"].get("note", "")
    assert "115000041" in note or "1501" in note


# ---------------------------------------------------------------------------
# 6. Estimated insert rows summary
# ---------------------------------------------------------------------------


def test_total_estimated_insert_rows(artifact):
    assert artifact["estimated_insert_rows_summary"]["total_safe_insert_rows"] == EXPECTED_TOTAL_INSERT


def test_db_rows_after_estimated(artifact):
    assert (
        artifact["estimated_insert_rows_summary"]["db_rows_after_safe_apply_estimated"]
        == EXPECTED_DB_ROWS + EXPECTED_TOTAL_INSERT
    )


# ---------------------------------------------------------------------------
# 7. Recommended apply order
# ---------------------------------------------------------------------------


def test_apply_order_is_list(artifact):
    assert isinstance(artifact["recommended_apply_order"], list)


def test_apply_order_has_four_steps(artifact):
    assert len(artifact["recommended_apply_order"]) == 4


def test_apply_order_p7_first(artifact):
    order = artifact["recommended_apply_order"]
    first = next(s for s in order if s["step"] == 1)
    assert first["strategy_id"] == "acb_markov_midfreq_3bet"


def test_apply_order_p9_last(artifact):
    order = artifact["recommended_apply_order"]
    last = next(s for s in order if s["step"] == 4)
    assert last["strategy_id"] == "fourier_rhythm_3bet"


def test_apply_order_p9_has_anomaly_note(artifact):
    order = artifact["recommended_apply_order"]
    p9_step = next(s for s in order if s["strategy_id"] == "fourier_rhythm_3bet")
    note = p9_step.get("p9_anomaly_note", "")
    assert "115000041" in note or "draw" in note.lower() or "anomaly" in note.lower()


def test_apply_order_strategy_ids(artifact):
    order = artifact["recommended_apply_order"]
    order_ids = [s["strategy_id"] for s in sorted(order, key=lambda x: x["step"])]
    assert order_ids == EXPECTED_APPLY_ORDER


# ---------------------------------------------------------------------------
# 8. Authorization phrase templates
# ---------------------------------------------------------------------------


def test_auth_phrases_is_list(artifact):
    assert isinstance(artifact["authorization_phrases_required_later"], list)


def test_auth_phrases_count(artifact):
    assert len(artifact["authorization_phrases_required_later"]) == 4


def test_auth_phrases_not_yet_issued(artifact):
    for entry in artifact["authorization_phrases_required_later"]:
        assert entry["status"] == "NOT_YET_ISSUED"


def test_auth_phrases_have_templates(artifact):
    for entry in artifact["authorization_phrases_required_later"]:
        template = entry.get("phrase_template", "")
        assert template.startswith("P130_AUTHORIZED_APPLY_"), (
            f"Unexpected template: {template}"
        )


# ---------------------------------------------------------------------------
# 9. Duplicate guard summary
# ---------------------------------------------------------------------------


def test_duplicate_guard_all_conflict_free(artifact):
    assert artifact["duplicate_guard_summary"]["all_safe_conflict_free"] is True


def test_duplicate_guard_abort_on_conflict(artifact):
    assert artifact["duplicate_guard_summary"]["abort_on_conflict"] is True


def test_duplicate_guard_per_candidate_all_pass(artifact):
    for entry in artifact["duplicate_guard_summary"]["per_candidate_status"]:
        assert entry["conflict_free"] is True, (
            f"{entry['strategy_id']} has conflicts: {entry.get('existing_conflicts')}"
        )


# ---------------------------------------------------------------------------
# 10. Apply gate status
# ---------------------------------------------------------------------------


def test_apply_gate_dry_run_plan_only(artifact):
    assert artifact["apply_gate_status"]["dry_run_plan_only"] is True


def test_apply_gate_no_controlled_apply(artifact):
    assert artifact["apply_gate_status"]["controlled_apply_executed"] is False


def test_apply_gate_no_replay_rows(artifact):
    assert artifact["apply_gate_status"]["replay_rows_inserted"] == 0


def test_apply_gate_db_rows_unchanged(artifact):
    assert artifact["apply_gate_status"]["production_db_rows_expected"] == EXPECTED_DB_ROWS
    assert artifact["apply_gate_status"]["production_db_rows_after"] == EXPECTED_DB_ROWS


def test_apply_gate_authorization_required_later(artifact):
    assert artifact["apply_gate_status"]["per_strategy_authorization_required_later"] is True


# ---------------------------------------------------------------------------
# 11. Blocked candidate scope
# ---------------------------------------------------------------------------


def test_blocked_apply_ready_false(artifact):
    assert artifact["blocked_candidate_scope"]["apply_ready"] is False


def test_blocked_power_precision_apply_ready_false(artifact):
    pp = artifact["blocked_candidate_scope"]["power_precision_3bet"]
    assert pp["apply_ready"] is False


def test_blocked_power_orthogonal_apply_ready_false(artifact):
    po = artifact["blocked_candidate_scope"]["power_orthogonal_5bet"]
    assert po["apply_ready"] is False


def test_blocked_rsr6_cleanup_completed(artifact):
    for sid in BLOCKED_CANDIDATE_IDS:
        entry = artifact["blocked_candidate_scope"][sid]
        assert entry["rsr6_cleanup_completed"] is True


def test_blocked_re_evaluation_required(artifact):
    for sid in BLOCKED_CANDIDATE_IDS:
        entry = artifact["blocked_candidate_scope"][sid]
        assert entry["re_evaluation_required"] is True


# ---------------------------------------------------------------------------
# 12. Governance / blocked_or_excluded
# ---------------------------------------------------------------------------


def test_no_db_write(artifact):
    assert artifact["blocked_or_excluded"]["no_db_write_in_P130"] is True


def test_no_controlled_apply(artifact):
    assert artifact["blocked_or_excluded"]["no_controlled_apply_in_P130"] is True


def test_p10_p12_not_apply_ready(artifact):
    assert artifact["blocked_or_excluded"]["P10_P12_not_apply_ready"] is True


def test_blocked_4star(artifact):
    assert artifact["blocked_or_excluded"]["4_STAR_excluded"] is True


def test_blocked_p108(artifact):
    assert artifact["blocked_or_excluded"]["P108_not_run"] is True


def test_blocked_p117(artifact):
    assert artifact["blocked_or_excluded"]["P117_not_run"] is True


def test_blocked_p118(artifact):
    assert artifact["blocked_or_excluded"]["P118_not_run"] is True


def test_no_scheduler_install(artifact):
    assert artifact["blocked_or_excluded"]["no_scheduler_install"] is True


def test_no_lifecycle_mutation(artifact):
    assert artifact["blocked_or_excluded"]["no_lifecycle_champion_registry_mutation"] is True


def test_p126b_p126f_untouched(artifact):
    assert artifact["blocked_or_excluded"]["P126B_P126F_rows_untouched"] is True


def test_no_apply_execution_script(artifact):
    assert artifact["blocked_or_excluded"]["no_apply_execution_script_created"] is True


# ---------------------------------------------------------------------------
# 13. Markdown content checks
# ---------------------------------------------------------------------------


def test_markdown_exists():
    assert MD_PATH.exists()


def test_markdown_has_classification():
    text = MD_PATH.read_text()
    assert "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY" in text


def test_markdown_has_all_safe_candidates():
    text = MD_PATH.read_text()
    for sid in SAFE_CANDIDATE_IDS:
        assert sid in text, f"Safe candidate {sid} not in Markdown"


def test_markdown_has_blocked_candidates():
    text = MD_PATH.read_text()
    for sid in BLOCKED_CANDIDATE_IDS:
        assert sid in text, f"Blocked candidate {sid} not in Markdown"


def test_markdown_has_p9_anomaly():
    text = MD_PATH.read_text()
    assert "1501" in text or "115000041" in text


def test_markdown_has_apply_order():
    text = MD_PATH.read_text()
    assert "apply order" in text.lower() or "recommended" in text.lower()


def test_markdown_has_auth_phrase_templates():
    text = MD_PATH.read_text()
    assert "P130_AUTHORIZED_APPLY" in text


# ---------------------------------------------------------------------------
# 14. Live DB: safe candidates still have only bet_index=1 rows
# ---------------------------------------------------------------------------


def test_safe_candidates_no_bi2_rows_live(db_conn):
    for sid in SAFE_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (sid,),
        ).fetchone()[0]
        assert count == 0, f"{sid} should have 0 bi=2 rows (no apply yet), got {count}"


def test_safe_candidates_bi1_rows_present(db_conn):
    expected = {
        "acb_markov_midfreq_3bet": 1500,
        "midfreq_fourier_mk_3bet": 1500,
        "fourier_rhythm_3bet": 1501,
        "pp3_freqort_4bet": 1500,
    }
    for sid, exp in expected.items():
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (sid,),
        ).fetchone()[0]
        assert count == exp, f"{sid}: expected {exp} bi=1 rows, got {count}"


def test_blocked_candidates_no_bi2_rows_live(db_conn):
    for sid in BLOCKED_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=2",
            (sid,),
        ).fetchone()[0]
        assert count == 0, f"{sid} should have 0 bi=2 rows after RSR-6 cleanup, got {count}"


def test_blocked_candidates_bi1_rows_1550(db_conn):
    for sid in BLOCKED_CANDIDATE_IDS:
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (sid,),
        ).fetchone()[0]
        assert count == 1550, f"{sid}: expected 1550 bi=1 rows, got {count}"


# ---------------------------------------------------------------------------
# 15. No forbidden files staged
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
    staged_a = [line[3:] for line in staged.splitlines() if line.startswith("A ")]
    assert not any("lottery_v2.db" in f for f in staged_a), (
        "DB should not be staged in P130 (dry-run plan only)"
    )
    for forbidden in [".history", ".pid", ".runtime"]:
        assert forbidden not in staged, f"Forbidden pattern '{forbidden}' in git status"
