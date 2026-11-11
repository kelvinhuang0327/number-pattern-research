"""
tests/test_phase28_real_clv_activation_check.py
===============================================
Phase 28 — Real CLV Activation Readiness Check: 6 unit tests.

Tests:
  1. Read-only default does not mutate CLV files.
  2. Valid candidate closing_ts > prediction_time → would_compute = True.
  3. closing_ts <= prediction_time → invalid_before_prediction.
  4. Missing source → remain pending.
  5. Same-snapshot rejected (diff_seconds < 60).
  6. Activation decision logic: READY / WAITING / INVALID / MANUAL_REVIEW.

All tests use synthetic in-memory data — no production CLV files are read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_phase28_real_clv_activation_check import (
    ACTIVATION_DECISION_INVALID,
    ACTIVATION_DECISION_MANUAL,
    ACTIVATION_DECISION_READY,
    ACTIVATION_DECISION_WAITING,
    INVALID_BEFORE_PREDICTION,
    INVALID_GAME_ID_MISMATCH,
    INVALID_MISSING_SOURCE,
    INVALID_SAME_SNAPSHOT,
    build_preview_payload,
    build_timeline_index,
    compute_activation_decision,
    evaluate_closing_candidate,
    evaluate_single_record,
    extract_game_id_from_snapshot_ref,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

PRED_TIME = "2026-04-30T08:35:10Z"
CLOSING_TIME_VALID = "2026-04-30T16:09:33Z"   # ~7.5 h after prediction
CLOSING_TIME_BEFORE = "2026-04-30T08:00:00Z"  # before prediction
CLOSING_TIME_SAME_SNAP = "2026-04-30T08:35:20Z"  # only 10 s after prediction


def _make_clv_record(
    prediction_id: str = "pred_001",
    canonical_match_id: str = "baseball:mlb:20260430:ATL:DET",
    selection: str = "home",
    odds_snapshot_ref: str | None = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES|TSL|snap@T",
    prediction_time_utc: str = PRED_TIME,
    clv_status: str = "PENDING_CLOSING",
) -> dict:
    return {
        "prediction_id": prediction_id,
        "canonical_match_id": canonical_match_id,
        "selection": selection,
        "odds_snapshot_ref": odds_snapshot_ref,
        "prediction_time_utc": prediction_time_utc,
        "clv_status": clv_status,
        "implied_probability_at_prediction": 0.555556,
    }


def _make_timeline_record(
    game_id: str = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES",
    closing_home_ml: float | None = -154.0,
    closing_away_ml: float | None = 130.0,
    closing_ts: str | None = CLOSING_TIME_VALID,
    external_closing_home_ml: float | None = None,
    external_closing_ts: str | None = None,
) -> dict:
    return {
        "game_id": game_id,
        "closing_home_ml": closing_home_ml,
        "closing_away_ml": closing_away_ml,
        "closing_ts": closing_ts,
        "external_closing_home_ml": external_closing_home_ml,
        "external_closing_ts": external_closing_ts,
    }


# ── Test 1: Read-only — CLV file must not be mutated ─────────────────────────

def test_readonly_does_not_mutate_clv(tmp_path):
    """
    run_check() must never overwrite or modify the source CLV JSONL file.
    The preview JSON is written to a DIFFERENT directory.
    """
    # Create a synthetic CLV file in tmp_path
    clv_file = tmp_path / "clv_records.jsonl"
    timeline_file = tmp_path / "timeline.jsonl"
    preview_dir = tmp_path / "reports"

    record = _make_clv_record()
    tl_record = _make_timeline_record()

    clv_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    timeline_file.write_text(json.dumps(tl_record) + "\n", encoding="utf-8")

    # Record original CLV content
    original_content = clv_file.read_text(encoding="utf-8")

    from scripts.run_phase28_real_clv_activation_check import run_check
    run_check(clv_path=clv_file, timeline_path=timeline_file, preview_output_dir=preview_dir)

    # CLV file must be unchanged
    assert clv_file.read_text(encoding="utf-8") == original_content, (
        "CLV JSONL file was mutated — run_check() must be read-only"
    )

    # Preview should have been written to the reports dir, NOT to the CLV location
    preview_files = list(preview_dir.glob("clv_activation_preview_*.json"))
    assert preview_files, "Preview JSON was not created in preview_output_dir"


# ── Test 2: Valid closing_ts > prediction_time → would_compute ────────────────

def test_valid_closing_ts_after_prediction_would_compute():
    """
    When closing_ts is well after prediction_time and closing_ml is valid,
    evaluate_closing_candidate() must return candidate_valid=True and
    the record evaluation must set would_compute=True.
    """
    result = evaluate_closing_candidate(
        closing_ml=-154.0,
        closing_ts_str=CLOSING_TIME_VALID,
        prediction_time_utc_str=PRED_TIME,
    )
    assert result["candidate_valid"] is True, f"Expected valid candidate, got: {result}"
    assert result["invalid_reason"] is None
    assert result["closing_ts_after_pred"] is True
    assert result["same_snapshot"] is False
    assert result["diff_seconds"] > 3600, "Expected closing_ts many hours after prediction"

    # Full record evaluation
    clv_row = _make_clv_record(selection="home")
    tl_record = _make_timeline_record(closing_home_ml=-154.0, closing_ts=CLOSING_TIME_VALID)
    idx = build_timeline_index([tl_record])
    rec_result = evaluate_single_record(clv_row, idx, idx)
    assert rec_result["would_compute"] is True, f"Expected would_compute=True: {rec_result}"
    assert rec_result["closing_ml"] == -154.0
    assert rec_result["block_reason"] is None


# ── Test 3: closing_ts <= prediction_time → invalid_before_prediction ─────────

def test_closing_ts_before_prediction_invalid():
    """
    When closing_ts is before or equal to prediction_time_utc,
    candidate_valid must be False with reason=invalid_before_prediction.
    """
    result = evaluate_closing_candidate(
        closing_ml=-154.0,
        closing_ts_str=CLOSING_TIME_BEFORE,
        prediction_time_utc_str=PRED_TIME,
    )
    assert result["candidate_valid"] is False
    assert result["invalid_reason"] == INVALID_BEFORE_PREDICTION
    assert result["closing_ts_after_pred"] is False

    # Equal timestamps (exactly at prediction time) also invalid
    result_equal = evaluate_closing_candidate(
        closing_ml=-154.0,
        closing_ts_str=PRED_TIME,
        prediction_time_utc_str=PRED_TIME,
    )
    assert result_equal["candidate_valid"] is False
    assert result_equal["invalid_reason"] == INVALID_BEFORE_PREDICTION


# ── Test 4: Missing closing source → remain pending ───────────────────────────

def test_missing_source_remain_pending():
    """
    When there is no timeline entry for a record (canonical_match_id lookup fails
    AND no snapshot_ref), the record must remain pending with reason=game_id_mismatch.
    """
    clv_row = _make_clv_record(
        odds_snapshot_ref=None,  # no snapshot ref → no improved lookup
        canonical_match_id="baseball:mlb:20260430:ATL:DET",
    )
    # Timeline indexed by a DIFFERENT game_id
    tl_record = _make_timeline_record(game_id="MLB-UNRELATED-GAME")
    idx = build_timeline_index([tl_record])
    result = evaluate_single_record(clv_row, idx, idx)

    assert result["would_compute"] is False
    assert result["snapshot_lookup_found"] is False
    assert result["canonical_lookup_found"] is False
    assert result["block_reason"] == INVALID_GAME_ID_MISMATCH

    # Also test evaluate_closing_candidate with None closing_ml
    cand = evaluate_closing_candidate(
        closing_ml=None,
        closing_ts_str=CLOSING_TIME_VALID,
        prediction_time_utc_str=PRED_TIME,
    )
    assert cand["candidate_valid"] is False
    assert cand["invalid_reason"] == INVALID_MISSING_SOURCE


# ── Test 5: Same-snapshot rejected ───────────────────────────────────────────

def test_same_snapshot_rejected():
    """
    When closing_ts is only 10 seconds after prediction_time (< 60 s threshold),
    the candidate must be rejected as same_snapshot.
    """
    result = evaluate_closing_candidate(
        closing_ml=-154.0,
        closing_ts_str=CLOSING_TIME_SAME_SNAP,
        prediction_time_utc_str=PRED_TIME,
    )
    assert result["candidate_valid"] is False
    assert result["invalid_reason"] == INVALID_SAME_SNAPSHOT
    assert result["same_snapshot"] is True
    assert result["closing_ts_after_pred"] is True   # IS after, but too close
    assert result["diff_seconds"] is not None
    assert result["diff_seconds"] < 60


# ── Test 6: Activation decision logic ────────────────────────────────────────

def test_activation_decision_logic():
    """
    compute_activation_decision() must return the correct enum for each scenario.
    """
    # READY_TO_COMPUTE: at least 1 would_compute
    results_ready = [
        {"would_compute": True, "block_reason": None},
        {"would_compute": False, "block_reason": INVALID_GAME_ID_MISMATCH},
    ]
    assert compute_activation_decision(results_ready) == ACTIVATION_DECISION_READY

    # WAITING_FOR_CLOSING_SOURCE: all missing source
    results_waiting = [
        {"would_compute": False, "block_reason": INVALID_GAME_ID_MISMATCH},
        {"would_compute": False, "block_reason": INVALID_MISSING_SOURCE},
    ]
    assert compute_activation_decision(results_waiting) == ACTIVATION_DECISION_WAITING

    # Empty list → WAITING
    assert compute_activation_decision([]) == ACTIVATION_DECISION_WAITING

    # DATA_INVALID_REQUIRES_REPAIR: candidates found but all timestamp-invalid
    results_invalid = [
        {"would_compute": False, "block_reason": INVALID_BEFORE_PREDICTION},
        {"would_compute": False, "block_reason": INVALID_SAME_SNAPSHOT},
    ]
    assert compute_activation_decision(results_invalid) == ACTIVATION_DECISION_INVALID

    # MANUAL_REVIEW_REQUIRED: mixed / ambiguous reasons
    results_manual = [
        {"would_compute": False, "block_reason": INVALID_BEFORE_PREDICTION},
        {"would_compute": False, "block_reason": INVALID_MISSING_SOURCE},
        {"would_compute": False, "block_reason": "conflict_external_vs_tsl"},
    ]
    assert compute_activation_decision(results_manual) == ACTIVATION_DECISION_MANUAL

    # extract_game_id_from_snapshot_ref
    ref = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES|TSL|snap@2026-04-30T05:16:54Z"
    assert extract_game_id_from_snapshot_ref(ref) == "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
    assert extract_game_id_from_snapshot_ref(None) is None
    assert extract_game_id_from_snapshot_ref("") is None
