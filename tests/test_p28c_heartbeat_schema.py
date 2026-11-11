"""
test_p28c_heartbeat_schema.py
P28C: Heartbeat vs Fetch Schema v2 — targeted tests

Covers:
  Group A — semantic field derivation from run_scheduled_capture results
  Group B — backward compatibility (all v1 fields preserved)
  Group C — exception / edge-case safety
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from wbc_backend.mlb_data.heartbeat_schema import (
    SEMANTIC_STATUS_VERSION,
    SemanticHeartbeatRow,
    make_semantic_heartbeat_row,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TIMESTAMP = "2026-01-01T12:00:00Z"

STATE_EMPTY: dict[str, Any] = {}
STATE_FETCHED: dict[str, Any] = {
    "fetched": True,
    "api_calls_today": 1,
}


def _result_skipped(reason: str = "no games in capture window") -> dict[str, Any]:
    """Simulate run_scheduled_capture() → status=skipped."""
    return {
        "status": "skipped",
        "reason": reason,
        "timestamp": TIMESTAMP,
    }


def _result_captured_empty() -> dict[str, Any]:
    """Simulate run_scheduled_capture() → status=captured but TSL returned 0 snapshots."""
    return {
        "status": "captured",
        "timestamp": TIMESTAMP,
        "windows": {},
        "result": {
            "snapshots_received": 0,
            "games_updated": 0,
            "snapshots_added": 0,
            "duplicates_skipped": 0,
        },
    }


def _result_captured_with_data(
    *,
    snapshots: int = 3,
    games_updated: int = 2,
    ec_status: str = "skipped_too_early",
) -> dict[str, Any]:
    """Simulate run_scheduled_capture() → status=captured, TSL returned data."""
    return {
        "status": "captured",
        "timestamp": TIMESTAMP,
        "windows": {},
        "result": {
            "snapshots_received": snapshots,
            "games_updated": games_updated,
            "snapshots_added": snapshots,
            "duplicates_skipped": 0,
            "external_closing": {
                "status": ec_status,
                "games_updated": 0,
                "api_calls_today": 1,
                "trigger_reason": "15.0 min until first game",
            },
        },
    }


def _result_closing_ok() -> dict[str, Any]:
    """Simulate closing odds successfully captured."""
    return {
        "status": "captured",
        "timestamp": TIMESTAMP,
        "windows": {},
        "result": {
            "snapshots_received": 4,
            "games_updated": 3,
            "snapshots_added": 4,
            "duplicates_skipped": 0,
            "external_closing": {
                "status": "ok",
                "games_updated": 2,
                "api_calls_today": 1,
                "trigger_reason": "2.5 min until first game",
            },
        },
    }


def _result_quota_hard_cap() -> dict[str, Any]:
    """Simulate quota hard-cap blocking external fetch."""
    return {
        "status": "captured",
        "timestamp": TIMESTAMP,
        "windows": {},
        "result": {
            "snapshots_received": 2,
            "games_updated": 1,
            "snapshots_added": 2,
            "duplicates_skipped": 0,
            "external_closing": {
                "status": "skipped_daily_cap_reached",
                "games_updated": 0,
                "api_calls_today": 2,
            },
        },
    }


def _result_quota_reserved() -> dict[str, Any]:
    """Simulate quota reserved for future closing window."""
    return {
        "status": "captured",
        "timestamp": TIMESTAMP,
        "windows": {},
        "result": {
            "snapshots_received": 2,
            "games_updated": 1,
            "snapshots_added": 2,
            "duplicates_skipped": 0,
            "external_closing": {
                "status": "skipped_quota_reserved_for_closing",
                "games_updated": 0,
                "api_calls_today": 1,
            },
        },
    }


def _result_exception() -> dict[str, Any]:
    """Simulate daemon exception path."""
    return {"status": "exception"}


# ---------------------------------------------------------------------------
# Group A — semantic field derivation
# ---------------------------------------------------------------------------


class TestSemanticFields:
    def test_skipped_fetch_not_attempted(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_EMPTY, TIMESTAMP)
        assert row["odds_fetch_attempted"] is False
        assert row["fetch_success"] is False
        assert row["source_empty"] is False

    def test_skipped_fetch_skip_reason_populated(self) -> None:
        row = make_semantic_heartbeat_row(
            _result_skipped("no games in capture window"), STATE_EMPTY, TIMESTAMP
        )
        assert row["fetch_skip_reason"] == "no games in capture window"

    def test_skipped_default_reason(self) -> None:
        """No 'reason' key → defaults to 'no_capture_window'."""
        row = make_semantic_heartbeat_row(
            {"status": "skipped"}, STATE_EMPTY, TIMESTAMP
        )
        assert row["fetch_skip_reason"] == "no_capture_window"

    def test_captured_empty_fetch_attempted_true(self) -> None:
        row = make_semantic_heartbeat_row(_result_captured_empty(), STATE_EMPTY, TIMESTAMP)
        assert row["odds_fetch_attempted"] is True

    def test_captured_empty_source_empty_true(self) -> None:
        row = make_semantic_heartbeat_row(_result_captured_empty(), STATE_EMPTY, TIMESTAMP)
        assert row["source_empty"] is True
        assert row["fetch_success"] is False

    def test_captured_empty_skip_reason_source_returned_empty(self) -> None:
        row = make_semantic_heartbeat_row(_result_captured_empty(), STATE_EMPTY, TIMESTAMP)
        assert row["fetch_skip_reason"] == "source_returned_empty"

    def test_captured_with_data_fetch_success(self) -> None:
        row = make_semantic_heartbeat_row(
            _result_captured_with_data(), STATE_EMPTY, TIMESTAMP
        )
        assert row["fetch_success"] is True
        assert row["source_empty"] is False
        assert row["fetch_skip_reason"] is None

    def test_captured_with_data_target_games_seen(self) -> None:
        row = make_semantic_heartbeat_row(
            _result_captured_with_data(games_updated=2), STATE_EMPTY, TIMESTAMP
        )
        assert row["target_games_seen"] == 2

    def test_closing_odds_captured(self) -> None:
        row = make_semantic_heartbeat_row(_result_closing_ok(), STATE_EMPTY, TIMESTAMP)
        assert row["closing_odds_captured"] is True
        assert row["external_fetch_blocked_by_quota"] is False
        assert row["quota_reserved_for_closing"] is False

    def test_quota_hard_cap_blocked(self) -> None:
        row = make_semantic_heartbeat_row(_result_quota_hard_cap(), STATE_EMPTY, TIMESTAMP)
        assert row["external_fetch_blocked_by_quota"] is True
        assert row["closing_odds_captured"] is False

    def test_quota_hard_cap_fetch_skip_reason(self) -> None:
        row = make_semantic_heartbeat_row(_result_quota_hard_cap(), STATE_EMPTY, TIMESTAMP)
        assert row["fetch_skip_reason"] == "skipped_daily_cap_reached"

    def test_quota_reserved_for_closing(self) -> None:
        row = make_semantic_heartbeat_row(_result_quota_reserved(), STATE_EMPTY, TIMESTAMP)
        assert row["quota_reserved_for_closing"] is True
        assert row["external_fetch_blocked_by_quota"] is False

    def test_quota_reserved_skip_reason(self) -> None:
        row = make_semantic_heartbeat_row(_result_quota_reserved(), STATE_EMPTY, TIMESTAMP)
        assert row["fetch_skip_reason"] == "skipped_quota_reserved_for_closing"

    def test_exception_path(self) -> None:
        row = make_semantic_heartbeat_row(_result_exception(), STATE_EMPTY, TIMESTAMP)
        assert row["fetch_skip_reason"] == "exception"
        assert row["odds_fetch_attempted"] is False
        assert row["fetch_success"] is False

    def test_heartbeat_written_always_true(self) -> None:
        for result in [
            _result_skipped(),
            _result_captured_empty(),
            _result_captured_with_data(),
            _result_exception(),
        ]:
            row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
            assert row["heartbeat_written"] is True, f"heartbeat_written=False for {result['status']}"

    def test_schema_version_always_v2(self) -> None:
        for result in [
            _result_skipped(),
            _result_captured_with_data(),
            _result_exception(),
        ]:
            row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
            assert row["semantic_status_version"] == "v2"

    def test_target_games_missing_is_zero(self) -> None:
        """target_games_missing is not yet derivable — always 0."""
        row = make_semantic_heartbeat_row(_result_captured_with_data(), STATE_EMPTY, TIMESTAMP)
        assert row["target_games_missing"] == 0


# ---------------------------------------------------------------------------
# Group B — backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    V1_FIELDS = {"timestamp", "status", "fetched", "api_calls_today", "next_trigger_minutes"}

    def test_all_v1_fields_present_skipped(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_EMPTY, TIMESTAMP)
        assert self.V1_FIELDS.issubset(row.keys())

    def test_all_v1_fields_present_captured(self) -> None:
        row = make_semantic_heartbeat_row(
            _result_captured_with_data(), STATE_FETCHED, TIMESTAMP
        )
        assert self.V1_FIELDS.issubset(row.keys())

    def test_fetched_from_state(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_FETCHED, TIMESTAMP)
        assert row["fetched"] is True

    def test_fetched_defaults_false_when_state_empty(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_EMPTY, TIMESTAMP)
        assert row["fetched"] is False

    def test_api_calls_today_from_state(self) -> None:
        state = {"api_calls_today": 2}
        row = make_semantic_heartbeat_row(_result_skipped(), state, TIMESTAMP)
        assert row["api_calls_today"] == 2

    def test_timestamp_preserved(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_EMPTY, TIMESTAMP)
        assert row["timestamp"] == TIMESTAMP

    def test_next_trigger_minutes_passed_through(self) -> None:
        row = make_semantic_heartbeat_row(
            _result_skipped(), STATE_EMPTY, TIMESTAMP, next_trigger_minutes=12.5
        )
        assert row["next_trigger_minutes"] == pytest.approx(12.5)

    def test_next_trigger_minutes_none_by_default(self) -> None:
        row = make_semantic_heartbeat_row(_result_skipped(), STATE_EMPTY, TIMESTAMP)
        assert row["next_trigger_minutes"] is None

    def test_status_uses_ec_status_when_present(self) -> None:
        """status field should reflect fine-grained ec status, not just 'captured'."""
        row = make_semantic_heartbeat_row(
            _result_captured_with_data(ec_status="skipped_too_early"),
            STATE_EMPTY,
            TIMESTAMP,
        )
        assert row["status"] == "skipped_too_early"

    def test_status_falls_back_to_outer_when_no_ec(self) -> None:
        """With no external_closing key, status = outer status."""
        row = make_semantic_heartbeat_row(_result_captured_empty(), STATE_EMPTY, TIMESTAMP)
        # No external_closing present → ec_status="" → falls back to "captured"
        assert row["status"] == "captured"

    def test_closing_ok_status_is_ok(self) -> None:
        row = make_semantic_heartbeat_row(_result_closing_ok(), STATE_EMPTY, TIMESTAMP)
        assert row["status"] == "ok"


# ---------------------------------------------------------------------------
# Group C — edge cases and safety
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_none_result_safe(self) -> None:
        """Passing None result should not raise."""
        row = make_semantic_heartbeat_row(None, STATE_EMPTY, TIMESTAMP)  # type: ignore[arg-type]
        assert row["semantic_status_version"] == SEMANTIC_STATUS_VERSION
        assert row["heartbeat_written"] is True

    def test_empty_dict_result_safe(self) -> None:
        row = make_semantic_heartbeat_row({}, STATE_EMPTY, TIMESTAMP)
        assert row["status"] == "unknown"
        assert row["odds_fetch_attempted"] is False

    def test_none_state_safe(self) -> None:
        """Passing None state should not raise."""
        row = make_semantic_heartbeat_row(_result_skipped(), None, TIMESTAMP)  # type: ignore[arg-type]
        assert row["fetched"] is False
        assert row["api_calls_today"] == 0

    def test_closing_ok_but_zero_games_not_captured(self) -> None:
        """status=ok but games_updated=0 should NOT set closing_odds_captured."""
        result = {
            "status": "captured",
            "result": {
                "snapshots_received": 2,
                "games_updated": 1,
                "external_closing": {
                    "status": "ok",
                    "games_updated": 0,
                },
            },
        }
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["closing_odds_captured"] is False

    def test_to_dict_json_serialisable(self) -> None:
        """SemanticHeartbeatRow.to_dict() must produce a JSON-serialisable dict."""
        schema = SemanticHeartbeatRow(
            timestamp=TIMESTAMP,
            status="ok",
            fetched=True,
            api_calls_today=1,
            next_trigger_minutes=10.0,
        )
        serialised = json.dumps(schema.to_dict())
        loaded = json.loads(serialised)
        assert loaded["semantic_status_version"] == SEMANTIC_STATUS_VERSION
        assert loaded["heartbeat_written"] is True

    def test_semantic_status_version_constant(self) -> None:
        assert SEMANTIC_STATUS_VERSION == "v2"

    def test_result_inner_not_dict_safe(self) -> None:
        """If result['result'] is not a dict, should not crash."""
        result = {"status": "captured", "result": "unexpected_string"}
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["odds_fetch_attempted"] is True
        assert row["fetch_success"] is False
        assert row["target_games_seen"] == 0
