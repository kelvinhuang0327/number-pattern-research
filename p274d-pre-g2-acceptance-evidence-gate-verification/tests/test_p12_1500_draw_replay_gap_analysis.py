"""
test_p12_1500_draw_replay_gap_analysis.py
==========================================
P12 1500-Draw Replay Gap Analysis — Test Suite.

Tests:
  1.  gap analysis JSON exists
  2.  dry_run_only=True
  3.  production_rows=460
  4.  target_draw_window=1500
  5.  registry_strategy_count=18
  6.  projected_rows_for_18_strategies=27000
  7.  current_gap_vs_18_strategies > 0
  8.  p7_28_rows_is_product_complete=False
  9.  fake_success_count=0
  10. artifact_only entries not counted as executable
  11. NO_DATA entries not counted as success (blocked)
  12. recommended_phase_1 exists
  13. recommended_phase_1 estimated_rows=3000
  14. production DB rows remain 460 after script execution
  15. no apply output generated (db_write_performed=False)
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT  = pathlib.Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p12_1500_draw_gap_analysis_20260520.json"
SCRIPT      = REPO_ROOT / "scripts" / "p12_1500_draw_replay_gap_analysis.py"
PYTHON      = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json() -> dict:
    assert OUTPUT_JSON.exists(), f"Gap analysis JSON not found: {OUTPUT_JSON}"
    with open(OUTPUT_JSON) as f:
        return json.load(f)


def _db_row_count() -> int:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Fixture: ensure script has been run at least once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def ensure_output_exists():
    """Run the script if JSON output does not exist yet."""
    if not OUTPUT_JSON.exists():
        result = subprocess.run(
            [PYTHON, str(SCRIPT)],
            capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        assert result.returncode == 0, (
            f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
    yield


# ---------------------------------------------------------------------------
# Test 1: gap analysis JSON exists
# ---------------------------------------------------------------------------

def test_gap_analysis_json_exists():
    """Test 1: output JSON file must exist."""
    assert OUTPUT_JSON.exists(), f"Expected gap analysis JSON at {OUTPUT_JSON}"


# ---------------------------------------------------------------------------
# Test 2: dry_run_only=True
# ---------------------------------------------------------------------------

def test_dry_run_only_true():
    """Test 2: dry_run_only must be True."""
    data = _load_json()
    assert data.get("dry_run_only") is True, (
        f"Expected dry_run_only=True, got {data.get('dry_run_only')}"
    )


# ---------------------------------------------------------------------------
# Test 3: production_rows=460
# ---------------------------------------------------------------------------

def test_production_rows_460():
    """Test 3: production_rows field must be 460."""
    data = _load_json()
    assert data.get("production_rows") == 460, (
        f"Expected production_rows=460, got {data.get('production_rows')}"
    )


# ---------------------------------------------------------------------------
# Test 4: target_draw_window=1500
# ---------------------------------------------------------------------------

def test_target_draw_window_1500():
    """Test 4: target_draw_window must be 1500."""
    data = _load_json()
    assert data.get("target_draw_window") == 1500, (
        f"Expected target_draw_window=1500, got {data.get('target_draw_window')}"
    )


# ---------------------------------------------------------------------------
# Test 5: registry_strategy_count=18
# ---------------------------------------------------------------------------

def test_registry_strategy_count_18():
    """Test 5: registry_strategy_count must be 18."""
    data = _load_json()
    assert data.get("registry_strategy_count") == 18, (
        f"Expected registry_strategy_count=18, got {data.get('registry_strategy_count')}"
    )


# ---------------------------------------------------------------------------
# Test 6: projected_rows_for_18_strategies=27000
# ---------------------------------------------------------------------------

def test_projected_rows_27000():
    """Test 6: projected_rows_for_18_strategies must be 27000 (18 × 1500)."""
    data = _load_json()
    assert data.get("projected_rows_for_18_strategies") == 27000, (
        f"Expected 27000, got {data.get('projected_rows_for_18_strategies')}"
    )


# ---------------------------------------------------------------------------
# Test 7: current_gap_vs_18_strategies > 0
# ---------------------------------------------------------------------------

def test_current_gap_positive():
    """Test 7: current_gap_vs_18_strategies must be positive."""
    data = _load_json()
    gap = data.get("current_gap_vs_18_strategies")
    assert isinstance(gap, (int, float)), f"Gap should be numeric, got {type(gap)}"
    assert gap > 0, f"Expected gap > 0, got {gap}"


# ---------------------------------------------------------------------------
# Test 8: p7_28_rows_is_product_complete=False
# ---------------------------------------------------------------------------

def test_p7_28_rows_not_product_complete():
    """Test 8: p7_28_rows_is_product_complete must be False."""
    data = _load_json()
    assert data.get("p7_28_rows_is_product_complete") is False, (
        f"Expected p7_28_rows_is_product_complete=False, got "
        f"{data.get('p7_28_rows_is_product_complete')}"
    )


# ---------------------------------------------------------------------------
# Test 9: fake_success_count=0
# ---------------------------------------------------------------------------

def test_fake_success_count_zero():
    """Test 9: fake_success_count must be 0."""
    data = _load_json()
    assert data.get("fake_success_count") == 0, (
        f"Expected fake_success_count=0, got {data.get('fake_success_count')}"
    )


# ---------------------------------------------------------------------------
# Test 10: artifact_only entries not counted as executable
# ---------------------------------------------------------------------------

def test_artifact_only_not_executable():
    """Test 10: artifact-only count must not be included in executable candidates."""
    data = _load_json()
    artifact_count   = data.get("artifact_only_count", 0)
    executable_count = len(data.get("executable_strategy_candidates", []))

    # artifact-only strategies must not appear in executable list
    assert artifact_count == 41, f"Expected artifact_only_count=41, got {artifact_count}"
    # executable candidates must come only from registry (max 18, practical = 8 ONLINE)
    assert executable_count <= 18, (
        f"executable_strategy_candidates count {executable_count} exceeds registry size 18"
    )
    # Must not equal 59 (full catalog including artifacts)
    assert executable_count != 59, (
        "executable_strategy_candidates = 59 means artifact-only strategies were "
        "incorrectly included"
    )

    # All executable strategies must be ONLINE
    online_candidates = set(data.get("online_strategy_candidates", []))
    executable_set    = set(data.get("executable_strategy_candidates", []))
    assert executable_set == online_candidates, (
        "executable_strategy_candidates must equal online_strategy_candidates"
    )


# ---------------------------------------------------------------------------
# Test 11: NO_DATA / REJECTED entries not counted as executable
# ---------------------------------------------------------------------------

def test_no_data_not_counted_as_executable():
    """Test 11: REJECTED and NO_DATA blocked strategies must not be in executable list."""
    data = _load_json()
    rejected = set(data.get("rejected_blocked", []))
    executable = set(data.get("executable_strategy_candidates", []))

    overlap = rejected & executable
    assert not overlap, (
        f"REJECTED strategies found in executable_strategy_candidates: {overlap}"
    )


def test_no_data_not_counted_as_success():
    """Test 11b: NO_DATA strategies must not appear in online/executable list."""
    data = _load_json()
    no_data = set(data.get("no_data_exclusions", []))
    online  = set(data.get("online_strategy_candidates", []))

    overlap = no_data & online
    assert not overlap, (
        f"NO_DATA exclusion strategies found in online_strategy_candidates: {overlap}"
    )


# ---------------------------------------------------------------------------
# Test 12: recommended_phase_1 exists
# ---------------------------------------------------------------------------

def test_recommended_phase_1_exists():
    """Test 12: recommended_phase_1 key must be present."""
    data = _load_json()
    assert "recommended_phase_1" in data, "recommended_phase_1 key missing from output"
    phase1 = data["recommended_phase_1"]
    assert isinstance(phase1, dict), f"recommended_phase_1 must be a dict, got {type(phase1)}"


# ---------------------------------------------------------------------------
# Test 13: recommended_phase_1 estimated_rows=3000
# ---------------------------------------------------------------------------

def test_recommended_phase_1_estimated_rows_3000():
    """Test 13: recommended_phase_1.estimated_rows must equal 3000."""
    data   = _load_json()
    phase1 = data.get("recommended_phase_1", {})
    assert phase1.get("estimated_rows") == 3000, (
        f"Expected recommended_phase_1.estimated_rows=3000, got "
        f"{phase1.get('estimated_rows')}"
    )


def test_recommended_phase_1_dry_run_only():
    """Test 13b: recommended_phase_1.dry_run_only must be True."""
    data   = _load_json()
    phase1 = data.get("recommended_phase_1", {})
    assert phase1.get("dry_run_only") is True, (
        f"recommended_phase_1.dry_run_only must be True, got {phase1.get('dry_run_only')}"
    )


def test_recommended_phase_1_strategy_count_2():
    """Test 13c: recommended_phase_1.strategy_count must be 2."""
    data   = _load_json()
    phase1 = data.get("recommended_phase_1", {})
    assert phase1.get("strategy_count") == 2, (
        f"Expected strategy_count=2, got {phase1.get('strategy_count')}"
    )


# ---------------------------------------------------------------------------
# Test 14: production DB rows remain 460 after script execution
# ---------------------------------------------------------------------------

def test_production_db_rows_unchanged():
    """Test 14: production strategy_prediction_replays rows must still be 460."""
    # Re-run the script to confirm read-only property
    result = subprocess.run(
        [PYTHON, str(SCRIPT)],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert result.returncode == 0, (
        f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    actual_count = _db_row_count()
    assert actual_count == 460, (
        f"Production DB rows changed after script execution! "
        f"Expected 460, got {actual_count}"
    )


# ---------------------------------------------------------------------------
# Test 15: no apply output generated (db_write_performed=False)
# ---------------------------------------------------------------------------

def test_no_apply_output_generated():
    """Test 15: db_write_performed must be False, strategy_execution_performed must be False."""
    data = _load_json()

    assert data.get("db_write_performed") is False, (
        f"Expected db_write_performed=False, got {data.get('db_write_performed')}"
    )
    assert data.get("strategy_execution_performed") is False, (
        f"Expected strategy_execution_performed=False, got "
        f"{data.get('strategy_execution_performed')}"
    )


# ---------------------------------------------------------------------------
# Additional: safety flags present
# ---------------------------------------------------------------------------

def test_safety_flags_present():
    """Additional: all safety flags must be present and True."""
    data  = _load_json()
    flags = data.get("safety_flags", {})

    required_flags = [
        "no_db_write",
        "no_strategy_execution",
        "no_fake_rows",
        "no_artifact_as_executable",
        "no_no_data_as_success",
        "no_p7_apply",
        "no_retired_apply",
    ]
    for flag in required_flags:
        assert flag in flags,         f"Missing safety flag: {flag}"
        assert flags[flag] is True,   f"Safety flag {flag} must be True, got {flags[flag]}"


def test_draw_data_sufficient_for_all_lottery_types():
    """Additional: all lottery types must have sufficient draw data for 1500-period backfill."""
    data = _load_json()
    assert data.get("draw_data_sufficient_for_1500") is True, (
        "draw_data_sufficient_for_1500 must be True — all lottery types must have "
        "≥1600 historical draws"
    )
    available = data.get("available_draws_by_lottery", {})
    for lt in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO"):
        info = available.get(lt, {})
        assert info.get("sufficient_for_1500") is True, (
            f"{lt} does not have sufficient draws for 1500-period backfill"
        )
        assert info.get("total_draws", 0) >= 1500, (
            f"{lt} has only {info.get('total_draws')} draws, need ≥1500"
        )
