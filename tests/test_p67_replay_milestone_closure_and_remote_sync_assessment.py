"""
P67 — Replay Milestone 1 Closure & Remote Sync Assessment
Evidence-only smoke tests.
"""
import json
import os
import sqlite3
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
JSON_PATH = os.path.join(
    PROJECT_ROOT,
    "outputs", "replay",
    "p67_replay_milestone_closure_and_remote_sync_assessment_20260526.json"
)
DOC_PATH = os.path.join(
    PROJECT_ROOT,
    "docs", "replay",
    "p67_replay_milestone_closure_and_remote_sync_assessment_20260526.md"
)


def test_production_rows_46960():
    """Production row count must be exactly 46960 post-P66."""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert count == 46960, f"Expected 46960 rows, got {count}"


def test_controlled_apply_ids_present():
    """All 3 controlled apply IDs from P58/P66 must exist in DB."""
    expected_ids = [
        "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525",
        "P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525",
        "P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525",
    ]
    conn = sqlite3.connect(DB_PATH)
    for apply_id in expected_ids:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
            (apply_id,)
        ).fetchone()[0]
        assert count == 1500, f"apply_id={apply_id} expected 1500 rows, got {count}"
    conn.close()


def test_all_strategies_dry_run():
    """All strategies must remain in replay/backfill verified state (no ONLINE promotions).

    The schema uses truth_level for governance classification.
    No truth_level value should indicate a live ONLINE promotion.
    """
    conn = sqlite3.connect(DB_PATH)
    # Accepted truth_level patterns: backfill verified + controlled apply verified
    rows = conn.execute(
        "SELECT DISTINCT truth_level FROM strategy_prediction_replays;"
    ).fetchall()
    conn.close()
    allowed_patterns = ("BACKFILL_VERIFIED", "CONTROLLED_APPLY_VERIFIED")
    unexpected = [
        r[0] for r in rows
        if r[0] is not None and not any(p in r[0] for p in allowed_patterns)
    ]
    assert unexpected == [], f"Found unexpected (possibly promoted) truth_level states: {unexpected}"


def test_json_output_exists():
    """P67 JSON output file must exist."""
    assert os.path.exists(JSON_PATH), f"Missing: {JSON_PATH}"


def test_json_output_content():
    """P67 JSON must record correct task metadata."""
    with open(JSON_PATH) as f:
        data = json.load(f)
    assert data["task"] == "P67"
    assert data["db_writes"] is False
    assert data["production_rows"] == 46960
    assert data["milestone_status"] == "COMPLETE"
    assert len(data["controlled_apply_ids"]) == 3
    assert data["remote_sync"]["force_push"] is False


def test_doc_exists():
    """P67 markdown closure doc must exist."""
    assert os.path.exists(DOC_PATH), f"Missing: {DOC_PATH}"


def test_no_db_staged():
    """Ensure DB file is not in git staging area."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    db_files = [f for f in staged if f.endswith(".db") or "lottery_v2" in f]
    assert db_files == [], f"DB files must not be staged: {db_files}"
