"""
test_p75_batch_a_apply_script_creation.py
==========================================
P75 governance tests — Batch A Apply Script Creation.

Asserts all P75 artifacts exist, have correct metadata,
and enforce the correct blocking logic.
"""

import json
import pathlib
import ast

REPO_ROOT  = pathlib.Path(__file__).resolve().parent.parent

PLAN_JSON   = REPO_ROOT / "outputs" / "replay" / "p74_batch_a_apply_plan_20260526.json"
SCRIPT_PY   = REPO_ROOT / "scripts" / "p74_batch_a_controlled_apply.py"
P75_JSON    = REPO_ROOT / "outputs" / "replay" / "p75_batch_a_apply_script_creation_20260526.json"
P75_DOC     = REPO_ROOT / "docs" / "replay" / "p75_batch_a_apply_script_creation_20260526.md"


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------

def test_apply_plan_json_exists():
    assert PLAN_JSON.exists(), f"Plan JSON not found: {PLAN_JSON}"


def test_apply_script_exists():
    assert SCRIPT_PY.exists(), f"Apply script not found: {SCRIPT_PY}"


def test_p75_evidence_json_exists():
    assert P75_JSON.exists(), f"P75 evidence JSON not found: {P75_JSON}"


def test_p75_doc_exists():
    assert P75_DOC.exists(), f"P75 doc not found: {P75_DOC}"


# ---------------------------------------------------------------------------
# Apply plan JSON correctness
# ---------------------------------------------------------------------------

def _plan() -> dict:
    with PLAN_JSON.open() as f:
        return json.load(f)


def test_plan_project_context_lock():
    assert _plan()["project_context_lock"] == "LotteryNew"


def test_plan_production_rows():
    assert _plan()["production_rows_current"] == 46960


def test_plan_final_status_blocked():
    assert _plan()["final_plan_status"] == "PLAN_BLOCKED_BY_SOURCE_DATA_GAP"


def test_plan_total_insert_rows_is_zero():
    assert _plan()["total_plan_insert_rows"] == 0


def test_plan_draws_after_115000040_is_zero():
    disc = _plan()["source_draw_discovery"]
    assert disc["draws_after_115000040"] == 0


def test_plan_eligible_draws_false():
    disc = _plan()["source_draw_discovery"]
    assert disc["eligible_draws_for_plan"] == 0


def test_plan_candidates_are_batch_a_only():
    candidates = _plan()["candidate_strategies"]
    sids = {c["strategy_id"] for c in candidates}
    assert sids == {"fourier_rhythm_3bet", "fourier30_markov30_2bet"}, (
        f"Unexpected candidates: {sids}"
    )


def test_plan_no_daily_539_candidates():
    candidates = _plan()["candidate_strategies"]
    lotteries = {c["lottery_type"] for c in candidates}
    assert "DAILY_539" not in lotteries, "DAILY_539 must not appear in Batch A plan"


def test_plan_no_big_lotto_candidates():
    candidates = _plan()["candidate_strategies"]
    lotteries = {c["lottery_type"] for c in candidates}
    assert "BIG_LOTTO" not in lotteries, "BIG_LOTTO must not appear in Batch A plan"


def test_plan_no_db_write():
    assert _plan()["no_db_write"] is True


def test_plan_fourier_rhythm_existing_rows():
    candidates = _plan()["candidate_strategies"]
    fr = next(c for c in candidates if c["strategy_id"] == "fourier_rhythm_3bet")
    assert fr["existing_rows"] == 1500


def test_plan_fourier30_markov30_existing_rows():
    candidates = _plan()["candidate_strategies"]
    fm = next(c for c in candidates if c["strategy_id"] == "fourier30_markov30_2bet")
    assert fm["existing_rows"] == 1500


# ---------------------------------------------------------------------------
# Apply script source checks
# ---------------------------------------------------------------------------

def _script_source() -> str:
    return SCRIPT_PY.read_text()


def test_script_defaults_to_dry_run():
    src = _script_source()
    assert "--apply" in src, "Script must mention --apply flag"
    # dry_run=True default
    assert "default=True" in src or "dry_run=True" in src or "dry_run = True" in src, (
        "Script dry-run must default to True"
    )


def test_script_requires_backup_for_apply():
    src = _script_source()
    assert "--backup" in src, "Script must have --backup argument"
    assert "backup" in src and ("not found" in src or "not_found" in src.replace("-", "_")), (
        "Script must refuse apply when backup is missing"
    )


def test_script_refuses_apply_without_correct_row_count():
    src = _script_source()
    assert "EXPECTED_ROWS_BEFORE_APPLY" in src, (
        "Script must define EXPECTED_ROWS_BEFORE_APPLY constant"
    )
    assert "SAFETY STOP" in src, "Script must emit SAFETY STOP on guard failure"


def test_script_refuses_duplicate_controlled_apply_id():
    src = _script_source()
    assert "p74_existing_count" in src or "_p74_existing_count" in src, (
        "Script must check for existing P74 controlled_apply_id rows"
    )


def test_script_no_lifecycle_import():
    src = _script_source()
    # Allow mentions in docstrings/comments; disallow actual imports or function calls
    assert "import lifecycle" not in src.lower(), (
        "Script must not import lifecycle layer"
    )
    assert "from lottery_api" not in src or "lifecycle" not in src.split("from lottery_api")[1].split("\n")[0].lower(), (
        "Script must not import lifecycle from lottery_api"
    )


def test_script_no_champion_import():
    src = _script_source()
    # Allow mentions in docstrings/comments; disallow actual imports
    assert "import champion" not in src.lower(), (
        "Script must not import champion layer"
    )
    assert "from lottery_api.champion" not in src.lower(), (
        "Script must not import from champion layer"
    )


def test_script_no_registry_import():
    src = _script_source()
    # registry import is allowed for display name lookup only — check for mutation calls
    assert "register(" not in src and "registry_mutation" not in src.lower(), (
        "Script must not mutate registry"
    )


def test_script_has_apply_flag():
    src = _script_source()
    assert "action=\"store_true\"" in src or "action='store_true'" in src, (
        "Script must declare --apply as store_true"
    )


def test_script_plan_status_gate():
    src = _script_source()
    assert "PLAN_READY_FOR_P76_APPLY" in src, (
        "Script must gate apply on PLAN_READY_FOR_P76_APPLY status"
    )


def test_script_batch_a_scope():
    src = _script_source()
    assert "fourier_rhythm_3bet" in src, "Script must reference fourier_rhythm_3bet"
    assert "fourier30_markov30_2bet" in src, "Script must reference fourier30_markov30_2bet"


# ---------------------------------------------------------------------------
# P75 evidence JSON correctness
# ---------------------------------------------------------------------------

def _p75() -> dict:
    with P75_JSON.open() as f:
        return json.load(f)


def test_p75_project_context_lock():
    assert _p75()["project_context_lock"] == "LotteryNew"


def test_p75_production_rows_before():
    assert _p75()["production_rows_before"] == 46960


def test_p75_production_rows_after():
    assert _p75()["production_rows_after"] == 46960


def test_p75_no_db_write():
    assert _p75()["no_db_write"] is True


def test_p75_no_force_push():
    assert _p75()["no_force_push"] is True


def test_p75_no_reset_hard():
    assert _p75()["no_reset_hard"] is True


def test_p75_no_git_clean():
    assert _p75()["no_git_clean"] is True


def test_p75_no_lifecycle_promotion():
    assert _p75()["no_lifecycle_promotion"] is True


def test_p75_no_champion_replacement():
    assert _p75()["no_champion_replacement"] is True


def test_p75_no_registry_mutation():
    assert _p75()["no_registry_mutation"] is True


def test_p75_final_classification():
    assert _p75()["final_classification"] == "P75_BLOCKED_BY_SOURCE_DATA_GAP"


def test_p75_draws_after_threshold_is_zero():
    disc = _p75()["source_draw_discovery"]
    assert disc["draws_after_115000040"] == 0


def test_p75_dry_run_no_write():
    dr = _p75()["script_dry_run_result"]
    assert dr["db_write_occurred"] is False


def test_p75_dry_run_eligible_rows_zero():
    dr = _p75()["script_dry_run_result"]
    assert dr["eligible_rows"] == 0


def test_p75_p76_not_ready():
    assert _p75()["p76_readiness_status"]["ready"] is False


def test_p75_apply_plan_path():
    p = _p75()["apply_plan_path"]
    assert "p74_batch_a_apply_plan" in p


def test_p75_script_path():
    p = _p75()["script_path"]
    assert "p74_batch_a_controlled_apply" in p


# ---------------------------------------------------------------------------
# Doc existence + content
# ---------------------------------------------------------------------------

def test_p75_doc_has_project_context_lock():
    doc = P75_DOC.read_text()
    assert "PROJECT_CONTEXT_LOCK: LotteryNew" in doc


def test_p75_doc_has_final_classification():
    doc = P75_DOC.read_text()
    assert "P75_BLOCKED_BY_SOURCE_DATA_GAP" in doc


def test_p75_doc_has_p74_blocker_summary():
    doc = P75_DOC.read_text()
    assert "P19B_POWERLOTTO_FOURIER_1500_PROD_20260520" in doc
    assert "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525" in doc


def test_p75_doc_has_draw_discovery():
    doc = P75_DOC.read_text()
    assert "115000040" in doc and "CAST" in doc
