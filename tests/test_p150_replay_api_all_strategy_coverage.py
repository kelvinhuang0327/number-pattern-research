"""
tests/test_p150_replay_api_all_strategy_coverage.py
=====================================================
P150: Replay API All Strategy Coverage — test suite.

Verifies:
  1. JSON artifact existence and required fields
  2. Repo / branch / DB / P149 checks
  3. bet_index support (in source code, not live API)
  4. no_data_reason support
  5. All-strategy catalog coverage (40 strategies)
  6. h6_gate_mk20_ew85 handling (zero rows, no DB write)
  7. Non-actions (no DB write, no replay rows mutated)
  8. Markdown artifact existence and content
  9. No forbidden files staged
  10. Unit tests for registry and route changes
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
JSON_PATH = REPO_ROOT / "outputs" / "replay" / "p150_replay_api_all_strategy_coverage_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p150_replay_api_all_strategy_coverage_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ROUTE_PATH = REPO_ROOT / "lottery_api" / "routes" / "replay.py"
REGISTRY_PATH = REPO_ROOT / "lottery_api" / "models" / "replay_strategy_registry.py"

VALID_CLASSIFICATIONS = {
    "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY",
    "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_PARTIAL",
    "P150_BLOCKED_REGISTRY_DB_MUTATION_AUTHORIZATION_REQUIRED",
}

EXPECTED_DB_ROWS = 94924


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert JSON_PATH.exists(), f"P150 JSON artifact not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text())


# ─── 1. JSON artifact existence and required fields ────────────────────────────

def test_json_exists():
    assert JSON_PATH.exists(), f"P150 JSON artifact not found: {JSON_PATH}"


def test_task_id(artifact):
    assert artifact["task_id"] == "P150"


def test_classification_valid(artifact):
    cls = artifact.get("classification")
    assert cls in VALID_CLASSIFICATIONS, (
        f"Invalid classification: {cls!r}. Expected one of {VALID_CLASSIFICATIONS}"
    )


# ─── 2. Repo / branch / DB / P149 checks ─────────────────────────────────────

def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows(artifact):
    assert artifact["db_snapshot"]["row_count"] == EXPECTED_DB_ROWS, (
        f"DB row count mismatch: {artifact['db_snapshot']['row_count']} != {EXPECTED_DB_ROWS}"
    )


def test_p149_classification(artifact):
    assert artifact["p149_source_summary"]["classification"] == (
        "P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY"
    )


# ─── 3. bet_index support ─────────────────────────────────────────────────────

def test_bet_index_in_api_source():
    """bet_index must be present in the SQL SELECT and response record in replay.py"""
    route_code = ROUTE_PATH.read_text()
    # SQL SELECT must include bet_index
    assert "bet_index" in route_code, "bet_index not found in replay.py"
    # Must be in response record dict
    assert '"bet_index"' in route_code or "'bet_index'" in route_code, (
        "bet_index not returned in response record"
    )


def test_bet_index_returned_flag(artifact):
    if artifact["classification"] == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY":
        assert artifact["bet_index_api_support"]["bet_index_returned_in_replay_history"] is True


def test_multi_bet_rows_distinguishable(artifact):
    if artifact["classification"] == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY":
        assert artifact["bet_index_api_support"]["multi_bet_rows_distinguishable"] is True


def test_bet_index_column_in_db():
    """bet_index column must exist in strategy_prediction_replays"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
        assert "bet_index" in cols, f"bet_index column not in DB schema. Columns: {cols}"
    finally:
        conn.close()


# ─── 4. no_data_reason support ────────────────────────────────────────────────

def test_no_data_reason_in_source():
    """no_data_reason must appear in both registry and route"""
    registry_code = REGISTRY_PATH.read_text()
    route_code = ROUTE_PATH.read_text()
    assert "no_data_reason" in registry_code, "no_data_reason not in registry"
    assert "no_data_reason" in route_code, "no_data_reason not in route"


def test_no_data_reason_returned(artifact):
    if artifact["classification"] == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY":
        assert artifact["no_data_reason_support"]["no_data_reason_returned"] is True


def test_h6_no_data_reason(artifact):
    assert artifact["h6_gate_mk20_ew85_handling"]["no_data_reason"] == "ONLINE_ZERO_REPLAY_ROWS"


def test_rejected_strategies_have_no_data_reason(artifact):
    if artifact["classification"] == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY":
        assert artifact["no_data_reason_support"]["rejected_no_data_strategies_visible"] is True


# ─── 5. All-strategy catalog coverage ────────────────────────────────────────

def test_total_strategies_from_p149(artifact):
    assert artifact["all_strategy_coverage_summary"]["total_strategies_discovered_from_p149"] == 40


def test_strategies_visible_in_catalog(artifact):
    if artifact["classification"] == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY":
        visible = artifact["all_strategy_coverage_summary"]["strategies_visible_in_replay_catalog_after_p150"]
        assert visible == 40, f"Expected 40 strategies visible, got {visible}"


def test_registry_has_40_strategies():
    """Source-controlled registry must have exactly 40 strategies after P150"""
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    all_s = list_strategy_lifecycle_metadata()
    assert len(all_s) == 40, f"Expected 40 strategies in registry, got {len(all_s)}"


def test_all_strategy_catalog_endpoint_exists():
    """New /api/replay/all-strategy-catalog endpoint must be defined in route file"""
    route_code = ROUTE_PATH.read_text()
    assert "/api/replay/all-strategy-catalog" in route_code


def test_db_only_lifecycle_handling(artifact):
    """22 DB-only strategies must have lifecycle placeholders in registry"""
    assert artifact["strategy_catalog_coverage_changes"]["lifecycle_placeholders_added"] == 22
    assert artifact["db_only_strategy_lifecycle_handling"]["strategy_count"] == 22
    assert artifact["db_only_strategy_lifecycle_handling"]["approach"] in (
        "source_controlled_registry_placeholder",
        "blocked_pending_authorization",
    )


def test_db_only_missing_lifecycle_status_in_registry():
    """P150 added 22 DB_ONLY_MISSING_LIFECYCLE stubs; P156C later updated all 22 to ONLINE/RETIRED.
    Post-P156C: 0 DB_ONLY_MISSING_LIFECYCLE stubs remain. Total strategies still 40."""
    import importlib
    sys.path.insert(0, str(REPO_ROOT))
    import lottery_api.models.replay_strategy_registry as reg_mod
    importlib.reload(reg_mod)
    all_s = reg_mod.list_strategy_lifecycle_metadata()
    db_only = [s for s in all_s if s["lifecycle_status"] == "DB_ONLY_MISSING_LIFECYCLE"]
    # P156C resolved all 22 DB_ONLY stubs — 0 remain
    assert len(db_only) == 0, f"Expected 0 DB_ONLY_MISSING_LIFECYCLE after P156C, got {len(db_only)}"
    # Total must still be 40
    assert len(all_s) == 40, f"Expected 40 total strategies, got {len(all_s)}"


def test_catalog_shows_zero_replay_row_strategies():
    """Strategies with zero rows must appear in /api/replay/all-strategy-catalog data"""
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    all_s = list_strategy_lifecycle_metadata()
    # h6_gate_mk20_ew85 must be in catalog
    ids = [s["strategy_id"] for s in all_s]
    assert "h6_gate_mk20_ew85" in ids


# ─── 6. h6_gate_mk20_ew85 handling ───────────────────────────────────────────

def test_h6_replay_rows_inserted(artifact):
    assert artifact["h6_gate_mk20_ew85_handling"]["replay_rows_inserted"] == 0


def test_h6_no_db_write(artifact):
    """h6_gate_mk20_ew85 must not have replay rows in DB"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = 'h6_gate_mk20_ew85'"
        ).fetchone()[0]
        assert count == 0, f"h6_gate_mk20_ew85 should have 0 rows in DB, got {count}"
    finally:
        conn.close()


def test_h6_registry_metadata():
    """h6_gate_mk20_ew85 must have no_data_reason in registry"""
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.models.replay_strategy_registry import get_strategy_lifecycle_metadata
    meta = get_strategy_lifecycle_metadata("h6_gate_mk20_ew85")
    assert meta["lifecycle_status"] == "OBSERVATION"
    assert meta.get("no_data_reason") == "ONLINE_ZERO_REPLAY_ROWS"


# ─── 7. Non-actions ───────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p150"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p150"] == 0


def test_no_replay_rows_updated(artifact):
    assert artifact["non_actions"]["replay_rows_updated_in_p150"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p150"] == 0


def test_no_live_api_called(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p150"] is False


def test_db_row_count_unchanged():
    """DB row count must remain at EXPECTED_DB_ROWS after P150"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        assert count == EXPECTED_DB_ROWS, f"DB row count changed: {count} != {EXPECTED_DB_ROWS}"
    finally:
        conn.close()


# ─── 8. Markdown artifact ─────────────────────────────────────────────────────

def test_markdown_exists():
    assert MD_PATH.exists(), f"P150 Markdown not found: {MD_PATH}"


def test_markdown_contains_bet_index():
    content = MD_PATH.read_text()
    assert "bet_index" in content


def test_markdown_contains_no_data_reason():
    content = MD_PATH.read_text()
    assert "no_data_reason" in content


def test_markdown_contains_all_required_sections():
    content = MD_PATH.read_text()
    required = [
        "Executive Summary",
        "Canonical Repo",
        "P149 Recap",
        "Replay API Changes",
        "bet_index",
        "no_data_reason",
        "All-Strategy",
        "Zero Replay",
        "DB-Only Lifecycle",
        "h6_gate_mk20_ew85",
        "Tests and Verification",
        "Non-Actions",
        "Dirty File Hygiene",
        "Remaining Risks",
        "Next Task",
        "Final Classification",
    ]
    for section in required:
        assert section in content, f"Markdown missing section: {section!r}"


# ─── 9. No forbidden files staged ────────────────────────────────────────────

def test_no_forbidden_files_staged():
    """lottery_v2.db and drift_guard script must not be staged"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    FORBIDDEN = ["lottery_v2.db", "replay_lifecycle_drift_guard.py"]
    for f in staged:
        for pattern in FORBIDDEN:
            assert pattern not in f, f"Forbidden file staged: {f}"


def test_no_pid_or_history_files_staged():
    """No pid, history, or pyc files staged"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    FORBIDDEN_SUFFIXES = [".pid", ".pyc", ".pyo", "LIVE_MONITORING_VERIFIED"]
    for f in staged:
        for suffix in FORBIDDEN_SUFFIXES:
            assert not f.endswith(suffix), f"Forbidden file staged: {f}"
