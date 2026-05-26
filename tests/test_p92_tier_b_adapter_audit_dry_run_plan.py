"""
P92 — Tier B Adapter Audit + Dry-run Plan
Smoke tests for artifact correctness and baseline integrity.
"""
import json
import os
import sqlite3
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
JSON_PATH = os.path.join(PROJECT_ROOT, "outputs", "replay",
    "p92_tier_b_adapter_audit_dry_run_plan_20260526.json")
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "replay",
    "p92_tier_b_adapter_audit_dry_run_plan_20260526.md")


def test_json_exists():
    assert os.path.exists(JSON_PATH)

def test_doc_exists():
    assert os.path.exists(DOC_PATH)

def test_classification():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["task"] == "P92"
    assert d["final_classification"] == "P92_TIER_B_ADAPTER_AUDIT_DRY_RUN_PLAN_READY"
    assert d["db_writes"] is False
    assert d["replay_row_changes"] == 0
    assert d["lifecycle_promotions"] == 0
    assert d["dry_run_executed"] is False

def test_exactly_9_target_strategies():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["target_strategies_count"] == 9

def test_audit_entries_count_10():
    with open(JSON_PATH) as f:
        d = json.load(f)
    # 9 RSM strategies + 1 naming collision split = 10 audit entries
    assert d["audit_entries_count"] == 10

def test_audit_entries_have_adapter_status():
    with open(JSON_PATH) as f:
        d = json.load(f)
    entries = d.get("audit_results", [])
    assert len(entries) >= 9
    valid_statuses = [
        "adapter-ready", "adapter-partial", "blocked-already-covered",
        "blocked-rejected", "adapter-needed", "blocked-superseded"
    ]
    for e in entries:
        assert "adapter_status" in e, f"Missing adapter_status in {e.get('rsm_name')}"
        assert e["adapter_status"] in valid_statuses, \
            f"Invalid adapter_status: {e['adapter_status']} for {e.get('rsm_name')}"

def test_each_entry_has_row_estimate_or_blocker():
    with open(JSON_PATH) as f:
        d = json.load(f)
    entries = d.get("audit_results", [])
    for e in entries:
        is_blocked = e.get("adapter_status", "").startswith("blocked")
        has_estimate = e.get("expected_rows_1500p") not in (None, 0, "null")
        assert is_blocked or has_estimate, \
            f"Entry {e.get('rsm_name')} ({e.get('lottery_type')}) missing row estimate or blocker"

def test_adapter_ready_count():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["summary"]["adapter_ready"] == 5

def test_blocked_already_covered_count():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["summary"]["blocked_already_covered"] == 3

def test_blocked_rejected_count():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["summary"]["blocked_rejected"] == 1

def test_adapter_partial_count():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["summary"]["adapter_partial"] == 1

def test_ts3_markov_freq_is_rejected():
    with open(JSON_PATH) as f:
        d = json.load(f)
    entries = d.get("audit_results", [])
    rejected = [e for e in entries if e.get("rsm_name") == "ts3_markov_freq_5bet_w30"]
    assert len(rejected) == 1
    assert rejected[0]["adapter_status"] == "blocked-rejected"
    assert rejected[0]["eligible_for_dry_run"] is False

def test_deviation_complement_already_covered():
    with open(JSON_PATH) as f:
        d = json.load(f)
    entries = d.get("audit_results", [])
    covered = [e for e in entries if e.get("rsm_name") == "deviation_complement_2bet"]
    assert len(covered) == 1
    assert covered[0]["adapter_status"] == "blocked-already-covered"
    assert covered[0]["existing_db_rows"] == 1570

def test_fourier_rhythm_2bet_naming_collision():
    """fourier_rhythm_2bet appears in both POWER_LOTTO and BIG_LOTTO."""
    with open(JSON_PATH) as f:
        d = json.load(f)
    entries = d.get("audit_results", [])
    fr_entries = [e for e in entries if e.get("rsm_name") == "fourier_rhythm_2bet"]
    assert len(fr_entries) == 2, "Expected 2 entries for fourier_rhythm_2bet (naming collision)"
    lottery_types = {e["lottery_type"] for e in fr_entries}
    assert "POWER_LOTTO" in lottery_types
    assert "BIG_LOTTO" in lottery_types

def test_dry_run_not_executed():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["dry_run_executed"] is False

def test_db_write_forbidden():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["db_writes"] is False

def test_replay_row_insert_forbidden():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["replay_row_changes"] == 0

def test_lifecycle_promotion_forbidden():
    with open(JSON_PATH) as f:
        d = json.load(f)
    assert d["lifecycle_promotions"] == 0

def test_recommended_p93_exists():
    with open(JSON_PATH) as f:
        d = json.load(f)
    scope = d.get("recommended_p93_scope")
    assert scope, "Missing recommended_p93_scope"
    assert "strategy_candidates" in scope
    assert len(scope["strategy_candidates"]) == 5

def test_recommended_p93_row_estimate():
    with open(JSON_PATH) as f:
        d = json.load(f)
    scope = d["recommended_p93_scope"]
    # 5 strategies × 1500 = 7500
    assert scope["estimated_new_rows"] == 7500

def test_baseline_rows_46962():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    conn.close()
    assert count == 46962, f"Expected 46962, got {count}"

def test_max_draw_115000041():
    conn = sqlite3.connect(DB_PATH)
    max_draw = conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO';"
    ).fetchone()[0]
    conn.close()
    assert str(max_draw) == "115000041"

def test_p79_rows_intact():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, strategy_id, dry_run FROM strategy_prediction_replays WHERE id IN (46961, 46962);"
    ).fetchall()
    conn.close()
    assert len(rows) == 2, f"Expected 2 P79 rows, got {len(rows)}"
    for row in rows:
        assert row[2] == 0, f"Row {row[0]} dry_run should be 0"

def test_no_db_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=PROJECT_ROOT, capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    db_files = [f for f in staged if ".db" in f or "lottery_v2" in f]
    assert db_files == [], f"DB files staged: {db_files}"

def test_adapter_tool_files_exist():
    """All referenced adapter tool files must exist on disk."""
    adapter_files = [
        os.path.join(PROJECT_ROOT, "tools", "predict_539_5bet_f4cold.py"),
        os.path.join(PROJECT_ROOT, "tools", "predict_biglotto_echo_3bet.py"),
        os.path.join(PROJECT_ROOT, "tools", "power_fourier_rhythm.py"),
        os.path.join(PROJECT_ROOT, "tools", "backtest_biglotto_5bet_ts3markov.py"),
        os.path.join(PROJECT_ROOT, "tools", "predict_biglotto_triple_strike.py"),
    ]
    for path in adapter_files:
        assert os.path.exists(path), f"Missing adapter file: {path}"

def test_rejected_artifact_exists():
    """ts3_markov_freq_5bet rejected artifact must be present."""
    artifact = os.path.join(PROJECT_ROOT, "rejected", "ts3_markov_freq_5bet_biglotto.json")
    assert os.path.exists(artifact), "Missing rejected artifact for ts3_markov_freq_5bet"
