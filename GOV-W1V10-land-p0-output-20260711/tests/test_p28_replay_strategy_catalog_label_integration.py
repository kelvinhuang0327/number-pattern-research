"""
P28: Replay Strategy Catalog Label Integration Tests
=====================================================
Calls the catalog route function directly (no full-app import, no torch dep).

Verifies /api/replay/strategy-catalog:
  - Returns all 59 strategies with P26 labels
  - Correct counts per label (row-backed=8, artifact-only=41, retired=5,
    rejected-registered=4, observation=1)
  - Non-row-backed entries have is_queryable=false
  - Row-backed entries have is_queryable=true and row_count > 0
  - safe_user_message present for all entries
  - Response is JSON-serializable
  - No DB write occurs (production rows remain 12460)
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_replay_strategy_catalog  # noqa: E402

_DB_PATH = LOTTERY_API / "data" / "lottery_v2.db"

# ── Expected counts from P24 inventory ────────────────────────────────────────
_EXPECTED_TOTAL       = 59
_EXPECTED_ROW_BACKED  = 8
_EXPECTED_AO          = 41
_EXPECTED_RETIRED     = 5
_EXPECTED_REJECTED    = 4
_EXPECTED_OBSERVATION = 1
_EXPECTED_PRODUCTION_ROWS = 19960

# ── Shared catalog fixture ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def catalog():
    return asyncio.get_event_loop().run_until_complete(get_replay_strategy_catalog())


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_catalog_returns_dict(catalog):
    assert isinstance(catalog, dict)


def test_catalog_total_strategies(catalog):
    assert catalog["total_strategies"] == _EXPECTED_TOTAL
    assert len(catalog["strategies"]) == _EXPECTED_TOTAL


def test_catalog_row_backed_count(catalog):
    assert catalog["label_summary"]["row-backed"] == _EXPECTED_ROW_BACKED
    assert catalog["row_backed_count"] == _EXPECTED_ROW_BACKED


def test_catalog_artifact_only_count(catalog):
    assert catalog["label_summary"]["artifact-only"] == _EXPECTED_AO


def test_catalog_retired_count(catalog):
    assert catalog["label_summary"]["retired"] == _EXPECTED_RETIRED


def test_catalog_rejected_registered_count(catalog):
    assert catalog["label_summary"]["rejected-registered"] == _EXPECTED_REJECTED


def test_catalog_observation_count(catalog):
    assert catalog["label_summary"]["observation"] == _EXPECTED_OBSERVATION


def test_all_entries_have_p26_labels(catalog):
    valid = {
        "row-backed", "artifact-only", "no-data", "reconstructible",
        "manual-review", "unsupported", "retired", "rejected-registered", "observation",
    }
    for e in catalog["strategies"]:
        assert e.get("primary_label") in valid, (
            f"{e.get('strategy_id')} has unknown label: {e.get('primary_label')}"
        )


def test_row_backed_entries_are_queryable(catalog):
    row_backed = [e for e in catalog["strategies"] if e["primary_label"] == "row-backed"]
    assert len(row_backed) == _EXPECTED_ROW_BACKED
    for e in row_backed:
        assert e["is_queryable"] is True, f"{e['strategy_id']} is_queryable={e['is_queryable']}"
        assert e["row_count"] > 0, f"{e['strategy_id']} row_count={e['row_count']}"
        assert e["is_row_backed"] is True


def test_non_row_backed_entries_not_queryable(catalog):
    non_rb = [e for e in catalog["strategies"] if e["primary_label"] != "row-backed"]
    assert len(non_rb) == _EXPECTED_TOTAL - _EXPECTED_ROW_BACKED
    for e in non_rb:
        assert e["is_queryable"] is False, (
            f"{e['strategy_id']} label={e['primary_label']} is_queryable={e['is_queryable']}"
        )


def test_all_entries_have_safe_user_message(catalog):
    for e in catalog["strategies"]:
        assert e.get("safe_user_message"), (
            f"{e.get('strategy_id')} (label={e.get('primary_label')}) missing safe_user_message"
        )


def test_response_json_serializable(catalog):
    serialized = json.dumps(catalog)
    reparsed = json.loads(serialized)
    assert reparsed["total_strategies"] == _EXPECTED_TOTAL


def test_no_db_write_flag(catalog):
    assert catalog.get("no_db_write") is True


def test_production_rows_unchanged():
    if not _DB_PATH.exists():
        pytest.skip("DB not found")
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == _EXPECTED_PRODUCTION_ROWS, (
        f"Production rows changed! Expected {_EXPECTED_PRODUCTION_ROWS}, got {count}"
    )


def test_all_entries_have_required_fields(catalog):
    required = {
        "strategy_id", "lottery_type", "lifecycle_state",
        "replay_visibility_state", "primary_label", "label_display_name",
        "label_description", "row_count", "verified_row_count",
        "is_row_backed", "is_queryable", "reconstructible_candidate",
        "needs_manual_review", "unsupported_reason", "safe_user_message",
    }
    for e in catalog["strategies"]:
        missing = required - set(e.keys())
        assert not missing, f"{e.get('strategy_id')} missing fields: {missing}"


def test_non_row_backed_count_field(catalog):
    assert catalog["non_row_backed_count"] == _EXPECTED_TOTAL - _EXPECTED_ROW_BACKED


def test_p26_label_module_referenced(catalog):
    assert "p26_label_module" in catalog


def test_artifact_only_entries_not_queryable(catalog):
    ao = [e for e in catalog["strategies"] if e["primary_label"] == "artifact-only"]
    assert len(ao) == _EXPECTED_AO
    for e in ao:
        assert e["is_queryable"] is False
        assert e["is_row_backed"] is False


def test_retired_entries_not_queryable(catalog):
    retired = [e for e in catalog["strategies"] if e["primary_label"] == "retired"]
    assert len(retired) == _EXPECTED_RETIRED
    for e in retired:
        assert e["is_queryable"] is False


def test_rejected_registered_entries_not_queryable(catalog):
    rejected = [e for e in catalog["strategies"] if e["primary_label"] == "rejected-registered"]
    assert len(rejected) == _EXPECTED_REJECTED
    for e in rejected:
        assert e["is_queryable"] is False


def test_observation_entry_not_queryable(catalog):
    obs = [e for e in catalog["strategies"] if e["primary_label"] == "observation"]
    assert len(obs) == _EXPECTED_OBSERVATION
    for e in obs:
        assert e["is_queryable"] is False
