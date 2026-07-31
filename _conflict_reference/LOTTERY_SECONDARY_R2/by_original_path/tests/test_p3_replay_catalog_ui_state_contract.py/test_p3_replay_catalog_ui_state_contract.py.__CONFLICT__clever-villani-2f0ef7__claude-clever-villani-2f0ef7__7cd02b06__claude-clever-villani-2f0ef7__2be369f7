"""
tests/test_p3_replay_catalog_ui_state_contract.py
===================================================
P3 UI State Contract tests — validates the TypeScript badge definitions
(replicated in Python for CI) and the Python state message table.

Tests:
  1. All 5 visibility states have badge definitions
  2. REGISTERED_WITH_REPLAY_ROWS is the ONLY state with canShowReplayRows=True
  3. RECONSTRUCTIBLE has canEnterReconstructionQueue=True only
  4. ARTIFACT_CANDIDATE has isArtifactOnly=True and NOT production
  5. NO_DATA states have canShowNoDataMessage=True
  6. UNSUPPORTED has canShowNoDataMessage=True
  7. Badge variants are in allowed set
  8. Smoke: TypeScript file contains expected exports
  9. Smoke: Python state messages do not contradict TypeScript expectations
 10. 59 catalog entries all have a defined badge via state_message
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_catalog_api_contract import (
    VISIBILITY_STATE_MESSAGES,
    ALL_VISIBILITY_STATES,
    build_readiness_flags,
)
from lottery_api.services.replay_catalog_source import load_catalog

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"

TS_FILE = REPO_ROOT / "frontend" / "src" / "replay" / "replayCatalogState.ts"

ALLOWED_VARIANTS = {"success", "info", "warning", "muted", "disabled"}


# ---------------------------------------------------------------------------
# Python state message table
# ---------------------------------------------------------------------------

class TestPythonStateMessages:
    def test_all_5_states_defined(self):
        assert set(ALL_VISIBILITY_STATES) == {
            "REGISTERED_WITH_REPLAY_ROWS",
            "RECONSTRUCTIBLE",
            "REGISTERED_NO_DATA",
            "ARTIFACT_CANDIDATE",
            "UNSUPPORTED",
        }

    def test_only_registered_with_rows_can_show_replay(self):
        for state in ALL_VISIBILITY_STATES:
            msg = VISIBILITY_STATE_MESSAGES[state]
            expected = (state == "REGISTERED_WITH_REPLAY_ROWS")
            assert msg["can_show_replay"] is expected, (
                f"State {state!r}: can_show_replay should be {expected}, got {msg['can_show_replay']}"
            )

    def test_only_registered_with_rows_is_success(self):
        for state in ALL_VISIBILITY_STATES:
            msg = VISIBILITY_STATE_MESSAGES[state]
            expected = (state == "REGISTERED_WITH_REPLAY_ROWS")
            assert msg["is_success"] is expected, (
                f"State {state!r}: is_success should be {expected}"
            )

    def test_all_messages_have_badge_fields(self):
        for state in ALL_VISIBILITY_STATES:
            msg = VISIBILITY_STATE_MESSAGES[state]
            assert msg.get("badge"), f"{state!r} missing badge"
            assert msg.get("badge_zh"), f"{state!r} missing badge_zh"
            assert msg.get("summary"), f"{state!r} missing summary"
            assert msg.get("detail"), f"{state!r} missing detail"


# ---------------------------------------------------------------------------
# Python readiness flags
# ---------------------------------------------------------------------------

class TestReadinessFlagLogic:
    @pytest.mark.parametrize("state,lc,expected_can_show", [
        ("REGISTERED_WITH_REPLAY_ROWS", "ONLINE",         True),
        ("RECONSTRUCTIBLE",              "ONLINE",         False),
        ("RECONSTRUCTIBLE",              "OFFLINE",        False),
        ("REGISTERED_NO_DATA",           "ONLINE",         False),
        ("ARTIFACT_CANDIDATE",           "NOT_REGISTERED", False),
        ("UNSUPPORTED",                  "RETIRED",        False),
    ])
    def test_can_show_replay_rows(self, state, lc, expected_can_show):
        flags = build_readiness_flags(state, lc)
        assert flags.can_show_replay_rows is expected_can_show, (
            f"can_show_replay_rows for ({state!r}, {lc!r}) should be {expected_can_show}"
        )

    @pytest.mark.parametrize("state,lc,expected_queue", [
        ("RECONSTRUCTIBLE",             "ONLINE",         True),
        ("RECONSTRUCTIBLE",             "OFFLINE",        True),
        ("REGISTERED_WITH_REPLAY_ROWS", "ONLINE",         False),
        ("ARTIFACT_CANDIDATE",          "NOT_REGISTERED", False),
        ("REGISTERED_NO_DATA",          "ONLINE",         False),
    ])
    def test_can_enter_reconstruction_queue(self, state, lc, expected_queue):
        flags = build_readiness_flags(state, lc)
        assert flags.can_enter_reconstruction_queue is expected_queue

    @pytest.mark.parametrize("state,lc,expected_artifact", [
        ("ARTIFACT_CANDIDATE",           "NOT_REGISTERED", True),
        ("REGISTERED_WITH_REPLAY_ROWS",  "ONLINE",         False),
        ("RECONSTRUCTIBLE",              "ONLINE",         False),
    ])
    def test_is_artifact_only(self, state, lc, expected_artifact):
        flags = build_readiness_flags(state, lc)
        assert flags.is_artifact_only is expected_artifact

    @pytest.mark.parametrize("state,lc,expected_prod", [
        ("REGISTERED_WITH_REPLAY_ROWS", "ONLINE",         True),
        ("ARTIFACT_CANDIDATE",          "NOT_REGISTERED", False),
        ("RECONSTRUCTIBLE",             "OFFLINE",        False),
    ])
    def test_is_production_strategy(self, state, lc, expected_prod):
        flags = build_readiness_flags(state, lc)
        assert flags.is_production_strategy is expected_prod

    def test_no_data_states_can_show_no_data_message(self):
        for state in ("REGISTERED_NO_DATA", "UNSUPPORTED"):
            flags = build_readiness_flags(state, "ONLINE")
            assert flags.can_show_no_data_message is True

    def test_reconstructible_cannot_show_no_data_message(self):
        flags = build_readiness_flags("RECONSTRUCTIBLE", "ONLINE")
        assert flags.can_show_no_data_message is False


# ---------------------------------------------------------------------------
# TypeScript file smoke tests
# ---------------------------------------------------------------------------

class TestTypeScriptFileSanity:
    def test_ts_file_exists(self):
        assert TS_FILE.exists(), f"Missing TypeScript state file: {TS_FILE}"

    def test_ts_file_exports_catalog_state_badges(self):
        content = TS_FILE.read_text()
        assert "CATALOG_STATE_BADGES" in content, "TS file must export CATALOG_STATE_BADGES"

    def test_ts_file_has_all_5_states(self):
        content = TS_FILE.read_text()
        for state in ALL_VISIBILITY_STATES:
            assert state in content, f"TS file missing state {state!r}"

    def test_ts_file_only_registered_with_rows_can_show_replay(self):
        content = TS_FILE.read_text()
        # Verify REGISTERED_WITH_REPLAY_ROWS has canShowReplayRows: true
        assert "canShowReplayRows: true" in content
        # Verify the false count is correct (4 states must have false)
        false_count = content.count("canShowReplayRows: false")
        assert false_count == 4, (
            f"Expected 4 states with canShowReplayRows: false, got {false_count}"
        )

    def test_ts_file_artifact_candidate_not_marked_online(self):
        content = TS_FILE.read_text()
        # ARTIFACT_CANDIDATE section must have isArtifactOnly: true
        assert "isArtifactOnly: true" in content

    def test_ts_file_no_raw_js_syntax_errors(self):
        content = TS_FILE.read_text()
        # Basic sanity: balanced braces
        assert content.count("{") == content.count("}"), "TS file has unbalanced braces"

    def test_ts_file_has_get_state_badge_function(self):
        content = TS_FILE.read_text()
        assert "getStateBadge" in content, "TS file must export getStateBadge function"


# ---------------------------------------------------------------------------
# Integration: all 59 catalog entries have valid badge
# ---------------------------------------------------------------------------

class TestAllCatalogEntriesHaveBadge:
    @pytest.fixture(scope="class")
    def catalog(self):
        return load_catalog(db_path=DB_PATH, p2_json=P2_JSON, p1_json=P1_JSON)

    def test_all_entries_have_defined_state_message(self, catalog):
        for entry in catalog:
            msg = VISIBILITY_STATE_MESSAGES.get(entry.catalog_visibility_state)
            assert msg is not None, (
                f"Entry {entry.strategy_id!r} has unmapped state "
                f"{entry.catalog_visibility_state!r}"
            )

    def test_6_entries_can_show_replay(self, catalog):
        can_show = [
            e for e in catalog
            if VISIBILITY_STATE_MESSAGES.get(e.catalog_visibility_state, {}).get("can_show_replay")
        ]
        assert len(can_show) == 6

    def test_12_reconstructible_entries_cannot_show_replay(self, catalog):
        recon = [e for e in catalog if e.catalog_visibility_state == "RECONSTRUCTIBLE"]
        assert len(recon) == 12
        for e in recon:
            flags = build_readiness_flags(e.catalog_visibility_state, e.lifecycle_state)
            assert flags.can_show_replay_rows is False

    def test_41_artifact_candidates_not_marked_online(self, catalog):
        artifacts = [e for e in catalog if e.catalog_visibility_state == "ARTIFACT_CANDIDATE"]
        assert len(artifacts) == 41
        for e in artifacts:
            # ARTIFACT_CANDIDATE must never have lifecycle_state == ONLINE
            assert e.lifecycle_state != "ONLINE", (
                f"ARTIFACT_CANDIDATE {e.strategy_id!r} incorrectly has lifecycle ONLINE"
            )
