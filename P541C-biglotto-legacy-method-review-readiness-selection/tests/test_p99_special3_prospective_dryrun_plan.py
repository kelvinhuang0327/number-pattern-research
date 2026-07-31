"""
tests/test_p99_special3_prospective_dryrun_plan.py
P99 Special3 Prospective Dry-run Planning — governance tests (15 tests)
"""
import json
import pathlib
import sqlite3

import pytest

JSON_PATH = pathlib.Path("outputs/replay/special3_prospective_dryrun_plan_20260527.json")
MD_PATH   = pathlib.Path("docs/replay/special3_prospective_dryrun_plan_20260527.md")
DB_PATH   = "lottery_api/data/lottery_v2.db"

EXPECTED_REPLAY_ROWS   = 54462
EXPECTED_CLASSIFICATION = "P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY"
EXPECTED_TRUTH_LEVEL    = "SPECIAL3_PROSPECTIVE_DRYRUN"
EXPECTED_TARGET_DRAW    = "NEXT_AFTER_CURRENT_MAX"
EXPECTED_EVAL_STATUS    = "PENDING_ACTUAL_DRAW"

P99_CANDIDATES = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
    "ensemble_rank_v1",
]
REJECTED_STRATEGY   = "position_cold_rebound_topk"
ENSEMBLE_V2_MEMBERS = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]


@pytest.fixture(scope="module")
def artifact():
    """Load the P99 JSON artifact once for all tests."""
    assert JSON_PATH.exists(), f"JSON artifact not found: {JSON_PATH}"
    with open(JSON_PATH) as f:
        return json.load(f)


# ── Test 01 ───────────────────────────────────────────────────────────────────

def test_01_json_artifact_exists_and_valid(artifact):
    """JSON artifact exists and can be parsed."""
    assert isinstance(artifact, dict), "Artifact must be a dict"
    assert len(artifact) > 0, "Artifact must not be empty"


# ── Test 02 ───────────────────────────────────────────────────────────────────

def test_02_md_artifact_exists():
    """MD artifact exists."""
    assert MD_PATH.exists(), f"MD artifact not found: {MD_PATH}"
    content = MD_PATH.read_text()
    assert len(content) > 100, "MD content appears to be empty"


# ── Test 03 ───────────────────────────────────────────────────────────────────

def test_03_classification(artifact):
    """classification == P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY."""
    assert artifact["classification"] == EXPECTED_CLASSIFICATION, (
        f"Expected {EXPECTED_CLASSIFICATION!r}, got {artifact.get('classification')!r}"
    )


# ── Test 04 ───────────────────────────────────────────────────────────────────

def test_04_five_p99_candidates(artifact):
    """All 5 P98 candidate strategies are recorded in p99_candidates."""
    candidates = artifact.get("p99_candidates", [])
    for strategy in P99_CANDIDATES:
        assert strategy in candidates, f"{strategy!r} missing from p99_candidates"
    assert len(candidates) == 5, f"Expected 5 candidates, got {len(candidates)}"


# ── Test 05 ───────────────────────────────────────────────────────────────────

def test_05_rejected_strategy_excluded(artifact):
    """Rejected strategy is in excluded_strategies and absent from ensemble_v2_members."""
    excluded = artifact.get("excluded_strategies", [])
    assert REJECTED_STRATEGY in excluded, (
        f"{REJECTED_STRATEGY!r} must be in excluded_strategies"
    )
    v2_members = artifact.get("ensemble_v2_members", [])
    assert REJECTED_STRATEGY not in v2_members, (
        f"{REJECTED_STRATEGY!r} must NOT be in ensemble_v2_members"
    )


# ── Test 06 ───────────────────────────────────────────────────────────────────

def test_06_ensemble_v2_members_correct(artifact):
    """ensemble_v2_members contains exactly 4 approved strategies (no rejected)."""
    v2_members = artifact.get("ensemble_v2_members", [])
    assert set(v2_members) == set(ENSEMBLE_V2_MEMBERS), (
        f"Expected members {sorted(ENSEMBLE_V2_MEMBERS)}, got {sorted(v2_members)}"
    )
    assert len(v2_members) == 4, f"Expected 4 v2 members, got {len(v2_members)}"
    assert REJECTED_STRATEGY not in v2_members


# ── Test 07 ───────────────────────────────────────────────────────────────────

def test_07_truth_level_all_predictions(artifact):
    """Every prediction record has truth_level == SPECIAL3_PROSPECTIVE_DRYRUN."""
    predictions = artifact.get("prospective_predictions", [])
    assert len(predictions) > 0, "No predictions found"
    for p in predictions:
        assert p.get("truth_level") == EXPECTED_TRUTH_LEVEL, (
            f"Prediction {p.get('strategy_id')}/top{p.get('top_n')} "
            f"has wrong truth_level: {p.get('truth_level')!r}"
        )


# ── Test 08 ───────────────────────────────────────────────────────────────────

def test_08_dry_run_flags(artifact):
    """dry_run_only == True and db_writes == False at top level."""
    assert artifact.get("dry_run_only") is True, "dry_run_only must be True"
    assert artifact.get("db_writes") is False, "db_writes must be False"


# ── Test 09 ───────────────────────────────────────────────────────────────────

def test_09_no_db_writes_in_artifact(artifact):
    """replay_rows_before == replay_rows_after (no rows inserted)."""
    before = artifact.get("replay_rows_before")
    after  = artifact.get("replay_rows_after")
    assert before == EXPECTED_REPLAY_ROWS, (
        f"replay_rows_before expected {EXPECTED_REPLAY_ROWS}, got {before}"
    )
    assert after == EXPECTED_REPLAY_ROWS, (
        f"replay_rows_after expected {EXPECTED_REPLAY_ROWS}, got {after}"
    )
    assert before == after, "replay_rows_before != replay_rows_after (writes occurred)"


# ── Test 10 ───────────────────────────────────────────────────────────────────

def test_10_live_db_replay_rows_unchanged():
    """Live DB still has exactly 54462 strategy_prediction_replays rows."""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()
    assert count == EXPECTED_REPLAY_ROWS, (
        f"Live DB replay rows = {count}, expected {EXPECTED_REPLAY_ROWS}"
    )


# ── Test 11 ───────────────────────────────────────────────────────────────────

def test_11_leading_zero_serialization_rule(artifact):
    """leading_zero_serialization rule exists; all predictions use 3-char strings."""
    # Protocol level rule exists
    lz = artifact.get("leading_zero_serialization")
    assert lz is not None, "leading_zero_serialization block must exist"
    assert "rule" in lz, "leading_zero_serialization must have a 'rule' key"

    # All serialized prediction strings must be exactly 3 chars
    predictions = artifact.get("prospective_predictions", [])
    for p in predictions:
        for ticket_str in p.get("serialized_predictions", []):
            assert len(ticket_str) == 3 and ticket_str.isdigit(), (
                f"Serialized ticket {ticket_str!r} is not a 3-digit string "
                f"(strategy={p.get('strategy_id')}, top_n={p.get('top_n')})"
            )

    # Verify known examples from the spec
    example_059 = lz.get("example_ticket_059")
    assert example_059 == "059", f"example_ticket_059 expected '059', got {example_059!r}"
    example_001 = lz.get("example_ticket_001")
    assert example_001 == "001", f"example_ticket_001 expected '001', got {example_001!r}"


# ── Test 12 ───────────────────────────────────────────────────────────────────

def test_12_target_draw_is_next_after_max(artifact):
    """target_draw == NEXT_AFTER_CURRENT_MAX (prospective — not yet ingested)."""
    assert artifact.get("target_draw") == EXPECTED_TARGET_DRAW, (
        f"target_draw expected {EXPECTED_TARGET_DRAW!r}, "
        f"got {artifact.get('target_draw')!r}"
    )
    # Also verify every prediction record has the same target_draw
    for p in artifact.get("prospective_predictions", []):
        assert p.get("target_draw") == EXPECTED_TARGET_DRAW, (
            f"Prediction {p.get('strategy_id')}/top{p.get('top_n')} "
            f"has wrong target_draw: {p.get('target_draw')!r}"
        )


# ── Test 13 ───────────────────────────────────────────────────────────────────

def test_13_evaluation_status_pending(artifact):
    """evaluation_status == PENDING_ACTUAL_DRAW (top-level and per-prediction)."""
    assert artifact.get("evaluation_status") == EXPECTED_EVAL_STATUS, (
        f"Top-level evaluation_status expected {EXPECTED_EVAL_STATUS!r}, "
        f"got {artifact.get('evaluation_status')!r}"
    )
    for p in artifact.get("prospective_predictions", []):
        assert p.get("evaluation_status") == EXPECTED_EVAL_STATUS, (
            f"Prediction {p.get('strategy_id')}/top{p.get('top_n')} "
            f"has wrong evaluation_status: {p.get('evaluation_status')!r}"
        )


# ── Test 14 ───────────────────────────────────────────────────────────────────

def test_14_special4_data_gap_blocking(artifact):
    """special4_status == DATA_GAP_BLOCKING and star4_backtest == NOT_RUN.

    P107B baseline repair note:
    The P99 artifact historically recorded special4_status=DATA_GAP_BLOCKING
    because 4_STAR data was absent at P99 evaluation time. That historical
    artifact fact remains correct and must not be rewritten.
    P104 subsequently ingested 2922 4_STAR rows (source_unknown provenance).
    P105/P106/P107A governance accepted the new DB baseline but explicitly
    confirmed: 4_STAR backtest remains NOT AUTHORIZED.
    The live-DB cross-check 'star4_count == 0' is therefore stale.
    We assert the post-P104 accepted baseline instead.
    """
    # Historical artifact assertions remain correct (P99 was recorded correctly)
    assert artifact.get("special4_status") == "DATA_GAP_BLOCKING", (
        f"special4_status expected DATA_GAP_BLOCKING (historical P99 artifact), "
        f"got {artifact.get('special4_status')!r}"
    )
    assert artifact.get("star4_backtest") == "NOT_RUN", (
        f"star4_backtest expected NOT_RUN, got {artifact.get('star4_backtest')!r}"
    )
    # P107B baseline repair: live DB cross-check updated to post-P104 baseline.
    # 4_STAR rows exist (P104 ingestion) but backtest remains unauthorized.
    conn = sqlite3.connect(DB_PATH)
    star4_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
    ).fetchone()[0]
    conn.close()
    assert star4_count == 2922, (
        f"4_STAR count mismatch: expected 2922 (P104 accepted baseline), "
        f"got {star4_count}. Historical artifact DATA_GAP_BLOCKING remains valid."
    )


# ── Test 15 ───────────────────────────────────────────────────────────────────

def test_15_p100_recommendation_exists(artifact):
    """p100_recommendation exists with status == NOT_YET_ELIGIBLE."""
    rec = artifact.get("p100_recommendation")
    assert rec is not None, "p100_recommendation block must exist"
    assert isinstance(rec, dict), "p100_recommendation must be a dict"
    assert rec.get("status") == "NOT_YET_ELIGIBLE", (
        f"p100_recommendation.status expected NOT_YET_ELIGIBLE, "
        f"got {rec.get('status')!r}"
    )
    assert "criteria" in rec, "p100_recommendation must have 'criteria' list"
    assert len(rec["criteria"]) >= 1, "p100_recommendation.criteria must not be empty"
    assert "reason" in rec, "p100_recommendation must have 'reason' key"
