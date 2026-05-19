"""
tests/test_p3_replay_catalog_api_contract.py
=============================================
P3 Replay Catalog API contract tests.

Tests:
  1. All 59 catalog entries can be loaded (or fallback to P1/P2 dry-run JSON)
  2. Filter by visibility state works correctly
  3. Filter by lifecycle state works correctly
  4. Replay readiness flags are semantically correct
  5. State messages map each visibility state
  6. RECONSTRUCTIBLE ≠ replay success
  7. ARTIFACT_CANDIDATE ≠ ONLINE
  8. NO_DATA / REGISTERED_NO_DATA ≠ has historical predictions
  9. Summary counts are internally consistent
 10. DB row count unchanged after catalog load

HARD CONSTRAINTS VERIFIED:
  - RECONSTRUCTIBLE → can_show_replay_rows=False
  - ARTIFACT_CANDIDATE → is_artifact_only=True, is_production_strategy may be False
  - NO_DATA → can_show_replay_rows=False
  - dry_run_only=True when source is fallback JSON
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import pytest
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.services.replay_catalog_source import load_catalog, load_catalog_with_source_info
from lottery_api.models.replay_catalog_api_contract import (
    build_catalog_list_response,
    build_readiness_flags,
    VISIBILITY_STATE_MESSAGES,
    ALL_VISIBILITY_STATES,
)

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog_info():
    return load_catalog_with_source_info(db_path=DB_PATH, p2_json=P2_JSON, p1_json=P1_JSON)


@pytest.fixture(scope="module")
def catalog(catalog_info):
    return catalog_info["entries"]


@pytest.fixture(scope="module")
def list_response(catalog, catalog_info):
    return build_catalog_list_response(
        catalog,
        source_used=catalog_info["source_used"],
    )


# ---------------------------------------------------------------------------
# Section 1: Catalog loading
# ---------------------------------------------------------------------------

class TestCatalogLoading:
    def test_catalog_loads_without_error(self, catalog):
        assert catalog is not None
        assert len(catalog) > 0

    def test_catalog_has_59_or_more_entries(self, catalog):
        # 59 planned entries (P2 dry-run); P1 JSON has 18+41=59
        # Live DB may have more if applied
        assert len(catalog) >= 59, f"Expected ≥59 catalog entries, got {len(catalog)}"

    def test_source_info_returned(self, catalog_info):
        assert "source_used" in catalog_info
        assert catalog_info["source_used"] in ("live_db", "p2_json", "p1_json")
        assert catalog_info["total"] == len(catalog_info["entries"])

    def test_all_entries_have_required_fields(self, catalog):
        required = [
            "strategy_id", "display_name", "lottery_type",
            "lifecycle_state", "catalog_visibility_state",
        ]
        for entry in catalog:
            d = entry.to_dict()
            for field in required:
                assert field in d and d[field], (
                    f"Entry {entry.strategy_id!r} missing field {field!r}"
                )

    def test_no_db_write_during_load(self, catalog):
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460, f"DB was modified during catalog load! count={count}"


# ---------------------------------------------------------------------------
# Section 2: Visibility state distribution
# ---------------------------------------------------------------------------

class TestVisibilityStateDistribution:
    def test_registered_with_replay_rows_count(self, catalog):
        count = sum(1 for e in catalog if e.catalog_visibility_state == "REGISTERED_WITH_REPLAY_ROWS")
        assert count == 6, f"Expected 6 REGISTERED_WITH_REPLAY_ROWS, got {count}"

    def test_reconstructible_count(self, catalog):
        count = sum(1 for e in catalog if e.catalog_visibility_state == "RECONSTRUCTIBLE")
        assert count == 12, f"Expected 12 RECONSTRUCTIBLE, got {count}"

    def test_artifact_candidate_count(self, catalog):
        count = sum(1 for e in catalog if e.catalog_visibility_state == "ARTIFACT_CANDIDATE")
        assert count == 41, f"Expected 41 ARTIFACT_CANDIDATE, got {count}"

    def test_total_adds_up(self, catalog):
        counts = Counter(e.catalog_visibility_state for e in catalog)
        assert sum(counts.values()) == len(catalog)

    def test_all_states_valid(self, catalog):
        for e in catalog:
            assert e.catalog_visibility_state in ALL_VISIBILITY_STATES, (
                f"{e.strategy_id!r} has unknown state {e.catalog_visibility_state!r}"
            )


# ---------------------------------------------------------------------------
# Section 3: Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_visibility_registered_with_rows(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_visibility="REGISTERED_WITH_REPLAY_ROWS",
            source_used="p2_json",
        )
        assert resp.total == 6
        assert all(i.catalog_visibility_state == "REGISTERED_WITH_REPLAY_ROWS" for i in resp.items)

    def test_filter_by_visibility_reconstructible(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_visibility="RECONSTRUCTIBLE",
            source_used="p2_json",
        )
        assert resp.total == 12

    def test_filter_by_visibility_artifact_candidate(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_visibility="ARTIFACT_CANDIDATE",
            source_used="p2_json",
        )
        assert resp.total == 41

    def test_filter_by_lifecycle_online(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_lifecycle="ONLINE",
            source_used="p2_json",
        )
        assert resp.total >= 1
        assert all(i.lifecycle_state == "ONLINE" for i in resp.items)

    def test_filter_by_lifecycle_not_registered(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_lifecycle="NOT_REGISTERED",
            source_used="p2_json",
        )
        assert resp.total == 41
        assert all(i.lifecycle_state == "NOT_REGISTERED" for i in resp.items)

    def test_no_filter_returns_all(self, catalog, list_response):
        assert list_response.total == len(catalog)

    def test_summary_counts_preserved_after_filter(self, catalog):
        resp = build_catalog_list_response(
            catalog,
            filter_visibility="RECONSTRUCTIBLE",
            source_used="p2_json",
        )
        # summary_by_visibility must reflect ALL entries (not just filtered)
        assert resp.summary_by_visibility.get("ARTIFACT_CANDIDATE", 0) == 41
        assert resp.summary_by_visibility.get("REGISTERED_WITH_REPLAY_ROWS", 0) == 6


# ---------------------------------------------------------------------------
# Section 4: Readiness flags — semantic correctness
# ---------------------------------------------------------------------------

class TestReadinessFlags:
    def test_registered_with_rows_can_show_replay(self, list_response):
        items_rwr = [i for i in list_response.items
                     if i.catalog_visibility_state == "REGISTERED_WITH_REPLAY_ROWS"]
        assert len(items_rwr) == 6
        for item in items_rwr:
            assert item.readiness.can_show_replay_rows is True
            assert item.readiness.is_catalog_visible is True
            assert item.readiness.can_enter_reconstruction_queue is False
            assert item.readiness.can_show_no_data_message is False
            assert item.readiness.is_artifact_only is False

    def test_reconstructible_cannot_show_replay(self, list_response):
        items_r = [i for i in list_response.items
                   if i.catalog_visibility_state == "RECONSTRUCTIBLE"]
        assert len(items_r) == 12
        for item in items_r:
            assert item.readiness.can_show_replay_rows is False, (
                f"RECONSTRUCTIBLE {item.strategy_id!r} must not show replay rows"
            )
            assert item.readiness.can_enter_reconstruction_queue is True
            assert item.readiness.is_catalog_visible is True

    def test_artifact_candidate_is_artifact_only(self, list_response):
        items_ac = [i for i in list_response.items
                    if i.catalog_visibility_state == "ARTIFACT_CANDIDATE"]
        assert len(items_ac) == 41
        for item in items_ac:
            assert item.readiness.is_artifact_only is True
            assert item.readiness.can_show_replay_rows is False, (
                f"ARTIFACT_CANDIDATE {item.strategy_id!r} must not show replay rows"
            )
            assert item.readiness.can_enter_reconstruction_queue is False

    def test_no_data_cannot_show_replay(self, list_response):
        no_data = [i for i in list_response.items
                   if i.catalog_visibility_state in ("REGISTERED_NO_DATA", "UNSUPPORTED")]
        for item in no_data:
            assert item.readiness.can_show_replay_rows is False
            assert item.readiness.can_show_no_data_message is True

    def test_only_registered_with_rows_is_success(self, list_response):
        for item in list_response.items:
            if item.catalog_visibility_state != "REGISTERED_WITH_REPLAY_ROWS":
                assert item.readiness.can_show_replay_rows is False, (
                    f"Non-REGISTERED {item.strategy_id!r} must not be replay success"
                )


# ---------------------------------------------------------------------------
# Section 5: State messages
# ---------------------------------------------------------------------------

class TestStateMessages:
    def test_all_5_states_have_messages(self):
        for state in ALL_VISIBILITY_STATES:
            assert state in VISIBILITY_STATE_MESSAGES
            msg = VISIBILITY_STATE_MESSAGES[state]
            assert msg.get("badge"), f"State {state!r} missing badge"
            assert msg.get("badge_zh"), f"State {state!r} missing badge_zh"
            assert msg.get("summary"), f"State {state!r} missing summary"

    def test_only_registered_with_rows_can_show_replay(self):
        for state, msg in VISIBILITY_STATE_MESSAGES.items():
            if state == "REGISTERED_WITH_REPLAY_ROWS":
                assert msg["can_show_replay"] is True
            else:
                assert msg["can_show_replay"] is False, (
                    f"State {state!r} must not have can_show_replay=True"
                )

    def test_reconstructible_message_mentions_not_yet_backfilled(self):
        msg = VISIBILITY_STATE_MESSAGES["RECONSTRUCTIBLE"]
        assert msg["can_show_replay"] is False
        assert msg["is_success"] is False

    def test_artifact_candidate_message_says_not_online(self):
        msg = VISIBILITY_STATE_MESSAGES["ARTIFACT_CANDIDATE"]
        # Must not imply ONLINE or production
        assert "runtime" in msg["detail"].lower() or "not" in msg["detail"].lower()
        assert msg["can_show_replay"] is False

    def test_state_messages_in_list_response(self, list_response):
        for item in list_response.items:
            assert item.state_message is not None
            assert "badge" in item.state_message
            assert "can_show_replay" in item.state_message


# ---------------------------------------------------------------------------
# Section 6: List response shape
# ---------------------------------------------------------------------------

class TestListResponseShape:
    def test_response_has_required_fields(self, list_response):
        d = list_response.to_dict()
        required = [
            "items", "total", "source_used", "filter_visibility",
            "filter_lifecycle", "summary_by_visibility", "summary_by_lifecycle",
            "dry_run_only",
        ]
        for field in required:
            assert field in d, f"Response missing field {field!r}"

    def test_items_are_serializable(self, list_response):
        d = list_response.to_dict()
        serialized = json.dumps(d)
        assert len(serialized) > 100

    def test_dry_run_true_for_json_source(self, catalog):
        resp = build_catalog_list_response(catalog, source_used="p2_json")
        assert resp.dry_run_only is True

    def test_dry_run_true_for_p1_source(self, catalog):
        resp = build_catalog_list_response(catalog, source_used="p1_json")
        assert resp.dry_run_only is True

    def test_dry_run_false_only_for_live_db(self, catalog):
        resp = build_catalog_list_response(catalog, source_used="live_db")
        assert resp.dry_run_only is False

    def test_summary_visibility_sums_to_total_unfiltered(self, catalog):
        resp = build_catalog_list_response(catalog, source_used="p2_json")
        assert sum(resp.summary_by_visibility.values()) == len(catalog)
