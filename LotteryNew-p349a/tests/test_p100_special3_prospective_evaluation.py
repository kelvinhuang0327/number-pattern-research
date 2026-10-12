"""
tests/test_p100_special3_prospective_evaluation.py
===================================================
P100: Special3 Prospective Result Evaluation Gate — 13 tests

Verifies:
  1.  JSON artifact exists and is valid
  2.  MD artifact exists
  3.  Classification is valid P100 value
  4.  P99 artifact reference is correct
  5.  dry_run_only is true
  6.  Excluded rejected strategy is absent from predictions
  7.  HOLD: classification + evaluation_status consistent
  8.  Evaluation results: consistent with actual_draw_available
  9.  No DB writes
  10. replay_rows remains 54462
  11. 4_STAR remains DATA_GAP_BLOCKING
  12. No Special3 production promotion
  13. P101 recommendation exists
"""

import json
import os
import sqlite3
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(
    REPO_ROOT, "outputs", "replay",
    "special3_prospective_evaluation_20260527.json"
)
MD_PATH = os.path.join(
    REPO_ROOT, "docs", "replay",
    "special3_prospective_evaluation_20260527.md"
)
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_POWER_LOTTO_MAX = 115000041

VALID_CLASSIFICATIONS = {
    "P100_SPECIAL3_PROSPECTIVE_EVALUATION_HOLD_NO_ACTUAL_DRAW",
    "P100_SPECIAL3_PROSPECTIVE_EVALUATION_READY",
}

REJECTED_STRATEGY = "position_cold_rebound_topk"


# ─── fixtures ───

@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH, "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# ─── tests ───

def test_01_json_artifact_exists_and_valid():
    """JSON artifact exists and is valid JSON."""
    assert os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}"
    with open(JSON_PATH, "r") as f:
        data = json.load(f)
    assert isinstance(data, dict), "Artifact must be a JSON object"
    assert len(data) > 0, "Artifact must not be empty"


def test_02_md_artifact_exists():
    """MD artifact exists and is non-empty."""
    assert os.path.exists(MD_PATH), f"Missing: {MD_PATH}"
    content = open(MD_PATH).read()
    assert len(content) > 100, "MD artifact appears empty"


def test_03_classification_is_valid(artifact):
    """Classification is one of the two valid P100 values."""
    cls = artifact.get("classification", "")
    assert cls in VALID_CLASSIFICATIONS, (
        f"Invalid classification: {cls!r}. "
        f"Expected one of {VALID_CLASSIFICATIONS}"
    )


def test_04_p99_artifact_reference(artifact):
    """P99 artifact reference is present and correct."""
    p99_ref = artifact.get("p99_artifact", "")
    assert "special3_prospective_dryrun_plan_20260527" in p99_ref, (
        f"P99 artifact reference unexpected: {p99_ref!r}"
    )
    p99_cls = artifact.get("p99_classification", "")
    assert p99_cls == "P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY", (
        f"P99 classification mismatch: {p99_cls!r}"
    )


def test_05_dry_run_only_is_true(artifact):
    """dry_run_only must be true."""
    assert artifact.get("dry_run_only") is True, (
        "dry_run_only must be True"
    )
    assert artifact.get("p99_dry_run_only") is True, (
        "p99_dry_run_only must be True"
    )


def test_06_rejected_strategy_excluded(artifact):
    """position_cold_rebound_topk must appear only in excluded list, never in evaluation results."""
    excluded = artifact.get("p99_excluded_strategies", [])
    assert REJECTED_STRATEGY in excluded, (
        f"Rejected strategy {REJECTED_STRATEGY!r} not in excluded list"
    )
    # If EVALUATED, check evaluation_results don't reference it
    if artifact.get("evaluation_results"):
        strategies = [r["strategy"] for r in artifact["evaluation_results"]]
        assert REJECTED_STRATEGY not in strategies, (
            f"Rejected strategy {REJECTED_STRATEGY!r} appears in evaluation_results"
        )


def test_07_hold_or_evaluated_consistent(artifact):
    """
    If HOLD: classification matches, evaluation_status = PENDING_ACTUAL_DRAW,
             hold_reason present, evaluation_results = None.
    If EVALUATED: classification matches, evaluation_status = EVALUATED,
                  actual_draw_number present, evaluation_results is list.
    """
    cls = artifact["classification"]
    status = artifact.get("evaluation_status", "")
    available = artifact.get("actual_draw_available", None)

    if cls == "P100_SPECIAL3_PROSPECTIVE_EVALUATION_HOLD_NO_ACTUAL_DRAW":
        assert status == "PENDING_ACTUAL_DRAW", (
            f"HOLD artifact must have evaluation_status=PENDING_ACTUAL_DRAW, got {status!r}"
        )
        assert available is False, "HOLD artifact must have actual_draw_available=false"
        assert artifact.get("hold_reason"), "HOLD artifact must include hold_reason"
        assert artifact.get("evaluation_results") is None, (
            "HOLD artifact must have evaluation_results=null"
        )
    elif cls == "P100_SPECIAL3_PROSPECTIVE_EVALUATION_READY":
        assert status == "EVALUATED", (
            f"EVALUATED artifact must have evaluation_status=EVALUATED, got {status!r}"
        )
        assert available is True, "EVALUATED artifact must have actual_draw_available=true"
        assert artifact.get("actual_draw_number") is not None, (
            "EVALUATED artifact must include actual_draw_number"
        )
        results = artifact.get("evaluation_results")
        assert isinstance(results, list) and len(results) > 0, (
            "EVALUATED artifact must include non-empty evaluation_results"
        )


def test_08_evaluation_results_match_availability(artifact):
    """
    evaluation_results is null iff actual_draw_available is false.
    If available=true, evaluation_results must have 24 records (6 strategies × 4 top_N).
    """
    available = artifact.get("actual_draw_available", None)
    results = artifact.get("evaluation_results")
    if available is False:
        assert results is None, "No results expected when actual draw unavailable"
    else:
        assert isinstance(results, list), "evaluation_results must be a list when available"
        assert len(results) == 24, (
            f"Expected 24 evaluation records (6 strategies × 4 top_N), got {len(results)}"
        )


def test_09_no_db_writes(artifact):
    """db_writes must be false and replay_rows_changed must be 0."""
    assert artifact.get("db_writes") is False, "db_writes must be False"
    assert artifact.get("replay_rows_changed") == 0, (
        "replay_rows_changed must be 0"
    )


def test_10_replay_rows_unchanged(artifact, db):
    """Live DB replay rows remain at 54462 and match artifact record."""
    live_rows = db.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert live_rows == EXPECTED_REPLAY_ROWS, (
        f"Live replay_rows={live_rows} != expected {EXPECTED_REPLAY_ROWS}"
    )
    assert artifact.get("replay_rows_before") == EXPECTED_REPLAY_ROWS, (
        f"Artifact replay_rows_before={artifact.get('replay_rows_before')} != {EXPECTED_REPLAY_ROWS}"
    )
    assert artifact.get("replay_rows_after") == EXPECTED_REPLAY_ROWS, (
        f"Artifact replay_rows_after={artifact.get('replay_rows_after')} != {EXPECTED_REPLAY_ROWS}"
    )


def test_11_4star_data_gap_blocking(artifact, db):
    """4_STAR has 0 draws and artifact reports DATA_GAP_BLOCKING."""
    s4_count = db.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    assert s4_count == 0, f"4_STAR draws should be 0, got {s4_count}"
    assert artifact.get("special4_status") == "DATA_GAP_BLOCKING", (
        f"special4_status should be DATA_GAP_BLOCKING, got {artifact.get('special4_status')!r}"
    )
    assert artifact.get("star4_backtest") is False, (
        "star4_backtest must be False"
    )


def test_12_no_special3_production_promotion(artifact):
    """no_production_promotion must be true — Special3 never promoted."""
    assert artifact.get("no_production_promotion") is True, (
        "no_production_promotion must be True"
    )


def test_13_p101_recommendation_exists(artifact):
    """p101_recommendation must exist with valid structure."""
    p101 = artifact.get("p101_recommendation")
    assert isinstance(p101, dict), "p101_recommendation must be a dict"
    assert "status" in p101, "p101_recommendation must have status"
    assert "reason" in p101, "p101_recommendation must have reason"
    assert "trigger" in p101, "p101_recommendation must have trigger"
    # If HOLD, status must be NOT_YET_ELIGIBLE
    if artifact["classification"] == "P100_SPECIAL3_PROSPECTIVE_EVALUATION_HOLD_NO_ACTUAL_DRAW":
        assert p101["status"] == "NOT_YET_ELIGIBLE", (
            f"p101 status should be NOT_YET_ELIGIBLE for HOLD, got {p101['status']!r}"
        )
