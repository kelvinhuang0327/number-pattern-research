"""
P97 Special3 / Special4 Dry-Run Closure — Evidence Suite
10 tests verifying all output artifacts and governance invariants.

Classification: P97_SPECIAL3_SPECIAL4_DRYRUN_CLOSURE_READY
Branch: p97-special3-special4-dryrun-closure
Generated: 2026-05-27
"""

import json
import pathlib
import sqlite3

import pytest

# ── Paths ──────────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs" / "replay"

LEADING_ZERO_MD   = OUTPUTS / "special3_leading_zero_check_20260527.md"
BASELINE_JSON     = OUTPUTS / "special3_baseline_dryrun_20260527.json"
BASELINE_MD       = OUTPUTS / "special3_baseline_dryrun_20260527.md"
SPECIAL4_PLAN_MD  = OUTPUTS / "special4_ingestion_plan_20260527.md"
DB_PATH           = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_REPLAY_ROWS = 54462  # post-P94 Tier B governance baseline


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_baseline_json():
    with open(BASELINE_JSON) as f:
        return json.load(f)


# ── Test 01: Special3 leading-zero report exists and is PASS ──────────────────

def test_01_special3_leading_zero_report_exists_and_pass():
    """LEADING_ZERO_MD must exist and declare PASS result."""
    assert LEADING_ZERO_MD.exists(), f"Missing: {LEADING_ZERO_MD}"
    content = LEADING_ZERO_MD.read_text()
    assert "PASS" in content, "Leading-zero check must declare PASS"
    assert "4,115" in content or "4115" in content, "Expected 4115 draws verified"
    assert "errors" in content.lower(), "Must mention errors count"


# ── Test 02: Special3 baseline JSON exists and is valid ───────────────────────

def test_02_special3_baseline_json_exists_and_valid():
    """BASELINE_JSON must exist and parse as valid JSON with required fields."""
    assert BASELINE_JSON.exists(), f"Missing: {BASELINE_JSON}"
    data = _load_baseline_json()
    assert data["task"] == "special3_baseline_dryrun"
    assert data["dry_run"] is True
    assert data["draws_loaded"] == 4115
    assert data["windows"] == [150, 500, 1500]
    assert data["top_ns"] == [10, 20, 50, 100]


# ── Test 03: Special3 baseline MD summary exists ──────────────────────────────

def test_03_special3_baseline_md_exists():
    """BASELINE_MD summary report must exist."""
    assert BASELINE_MD.exists(), f"Missing: {BASELINE_MD}"
    content = BASELINE_MD.read_text()
    assert "PROVISIONAL" in content, "MD must include PROVISIONAL classification"
    assert "REJECT" in content, "MD must include REJECT classification"
    assert "position_cold_rebound_topk" in content, "REJECT strategy must be named"


# ── Test 04: Special4 ingestion plan exists and is DATA_GAP_BLOCKING ─────────

def test_04_special4_ingestion_plan_exists_and_data_blocked():
    """SPECIAL4_PLAN_MD must exist and declare DATA_GAP_BLOCKING."""
    assert SPECIAL4_PLAN_MD.exists(), f"Missing: {SPECIAL4_PLAN_MD}"
    content = SPECIAL4_PLAN_MD.read_text()
    assert "DATA_GAP_BLOCKING" in content, "Plan must declare DATA_GAP_BLOCKING"
    # 4_STAR has 0 rows — plan must acknowledge this
    assert "0" in content, "Plan must reference 0 rows"


# ── Test 05: Classification fields exist for all 6 strategies ────────────────

def test_05_all_six_strategies_classified():
    """All 6 Special3 strategies must have classification entries."""
    data = _load_baseline_json()
    expected_strategies = {
        "position_frequency_topk",
        "recent_position_hot_topk",
        "position_cold_rebound_topk",
        "sum_band_frequency",
        "span_band_frequency",
        "ensemble_rank_v1",
    }
    classifications = data.get("classifications", {})
    for s in expected_strategies:
        assert s in classifications, f"Missing classification for {s}"
        cls = classifications[s]["classification"]
        assert cls in ("PROVISIONAL", "REJECT", "INCONCLUSIVE"), (
            f"Invalid classification '{cls}' for {s}"
        )


# ── Test 06: position_cold_rebound_topk is REJECT ────────────────────────────

def test_06_cold_rebound_is_rejected():
    """position_cold_rebound_topk must be classified REJECT (negative edge)."""
    data = _load_baseline_json()
    cls = data["classifications"]["position_cold_rebound_topk"]
    assert cls["classification"] == "REJECT", (
        f"Expected REJECT, got {cls['classification']}"
    )
    edge = cls.get("avg_edge_all_windows_top_ns", 0)
    assert edge < 0, f"Expected negative edge for REJECT strategy, got {edge}"


# ── Test 07: No DB write claimed in JSON ──────────────────────────────────────

def test_07_no_db_write_claimed():
    """dry_run JSON must explicitly declare db_writes=false."""
    data = _load_baseline_json()
    assert data["dry_run"] is True, "dry_run must be true"
    assert data.get("db_writes") is False, (
        f"db_writes must be False (got {data.get('db_writes')})"
    )
    assert data.get("replay_rows_changed") == 0, (
        f"replay_rows_changed must be 0 (got {data.get('replay_rows_changed')})"
    )


# ── Test 08: 4_STAR explicitly data-blocked in plan ──────────────────────────

def test_08_4star_data_blocked_in_plan():
    """Special4 plan must document 4_STAR schema readiness but 0 rows."""
    content = SPECIAL4_PLAN_MD.read_text()
    # Must mention 4_STAR schema exists
    assert "4_STAR" in content, "Plan must reference 4_STAR lottery_type"
    # Must block baseline dryrun until ingestion
    assert "Do NOT start" in content or "not start" in content.lower(), (
        "Plan must block 4_STAR baseline dryrun until ingestion"
    )
    # Must mention the row threshold
    assert "1,000" in content or "1000" in content, (
        "Plan must reference minimum row threshold for research"
    )


# ── Test 09: No 4_STAR backtest claim in plan ─────────────────────────────────

def test_09_no_4star_backtest_claim():
    """Special4 plan must not claim any backtest results (data-blocked)."""
    content = SPECIAL4_PLAN_MD.read_text()
    # Plan should not claim edge, ROI, or strategy results for 4_STAR
    forbidden_phrases = ["edge_vs_random", "direct_hit_rate", "PROVISIONAL", "VALIDATED"]
    for phrase in forbidden_phrases:
        assert phrase not in content, (
            f"Plan must not claim backtest result '{phrase}' — 4_STAR is data-blocked"
        )


# ── Test 10: Replay rows remain at governance baseline ───────────────────────

def test_10_replay_rows_unchanged_at_governance_baseline():
    """strategy_prediction_replays must remain at 54462 (P94 Tier B baseline)."""
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_REPLAY_ROWS, (
        f"Replay rows changed! Expected {EXPECTED_REPLAY_ROWS}, got {count}. "
        "P97 is dry-run only — no rows should be inserted."
    )
