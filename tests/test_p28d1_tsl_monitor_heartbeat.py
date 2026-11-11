"""
test_p28d1_tsl_monitor_heartbeat.py
P28D.1: TSL Monitor alert counts wired into SemanticHeartbeatRow.

Test coverage:
  A — No monitor result (tsl_monitor absent from result)
  B — Empty alerts (tsl_monitor present, new_alerts=[])
  C — Early-withdrawal alert present
  D — Multiple alerts, mixed classifications
  E — Malformed monitor result (non-dict, None, error key)
  F — Backward compatibility — all v2 fields still present
"""

from __future__ import annotations

import pytest

from wbc_backend.mlb_data.heartbeat_schema import (
    SEMANTIC_STATUS_VERSION,
    make_semantic_heartbeat_row,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIMESTAMP = "2026-05-23T10:00:00+00:00"
STATE_EMPTY: dict = {}


def _result_captured(inner: dict | None = None) -> dict:
    """Outer result dict mimicking run_scheduled_capture() → status=captured."""
    return {"status": "captured", "result": inner or {}}


def _tsl_monitor_no_alerts(total_tracked: int = 5) -> dict:
    return {"new_alerts": [], "total_tracked": total_tracked, "poll_ts": TIMESTAMP}


def _tsl_monitor_with_early_withdrawal() -> dict:
    return {
        "new_alerts": [
            {
                "classification": "TSL_MARKET_WITHDRAWAL_EARLY",
                "match_id": "2026-05-23T14:05:00+00:00|Cubs|Dodgers",
                "hours_before_game": 3.2,
                "game_time_utc": "2026-05-23T14:05:00+00:00",
            }
        ],
        "total_tracked": 8,
        "poll_ts": TIMESTAMP,
    }


def _tsl_monitor_mixed_alerts() -> dict:
    return {
        "new_alerts": [
            {"classification": "TSL_MARKET_NORMAL_REMOVAL", "match_id": "id1"},
            {"classification": "TSL_MARKET_WITHDRAWAL_EARLY", "match_id": "id2"},
            {"classification": "TSL_MARKET_NEVER_SEEN", "match_id": "id3"},
        ],
        "total_tracked": 12,
        "poll_ts": TIMESTAMP,
    }


def _tsl_monitor_error() -> dict:
    return {
        "new_alerts": [],
        "total_tracked": 0,
        "poll_ts": TIMESTAMP,
        "error": "state file corrupted",
    }


# ---------------------------------------------------------------------------
# Group A — No monitor result
# ---------------------------------------------------------------------------


class TestNoMonitorResult:
    def test_status_is_no_data_when_tsl_monitor_absent(self) -> None:
        result = _result_captured({"snapshots_received": 2})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "no_data"

    def test_alerts_count_zero_when_tsl_monitor_absent(self) -> None:
        result = _result_captured({"snapshots_received": 2})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_alerts_count"] == 0
        assert row["tsl_monitor_new_alerts_count"] == 0

    def test_no_withdrawal_flag_when_tsl_monitor_absent(self) -> None:
        result = _result_captured({"snapshots_received": 2})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_has_withdrawal_early"] is False

    def test_status_no_data_when_result_is_none(self) -> None:
        row = make_semantic_heartbeat_row(None, STATE_EMPTY, TIMESTAMP)  # type: ignore[arg-type]
        assert row["tsl_monitor_status"] == "no_data"
        assert row["tsl_monitor_alerts_count"] == 0

    def test_status_no_data_when_inner_result_is_empty_dict(self) -> None:
        result = _result_captured({})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "no_data"


# ---------------------------------------------------------------------------
# Group B — Empty alerts (monitor ran, no events)
# ---------------------------------------------------------------------------


class TestEmptyAlerts:
    def test_status_ok_when_no_new_alerts(self) -> None:
        mon = _tsl_monitor_no_alerts(total_tracked=3)
        result = _result_captured({"snapshots_received": 3, "tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "ok"

    def test_new_alerts_count_zero(self) -> None:
        mon = _tsl_monitor_no_alerts()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 0

    def test_total_tracked_reflected(self) -> None:
        mon = _tsl_monitor_no_alerts(total_tracked=7)
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_alerts_count"] == 7

    def test_no_withdrawal_when_alerts_empty(self) -> None:
        mon = _tsl_monitor_no_alerts()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_has_withdrawal_early"] is False


# ---------------------------------------------------------------------------
# Group C — Early-withdrawal alert present
# ---------------------------------------------------------------------------


class TestEarlyWithdrawalAlert:
    def test_status_alert_when_new_alerts(self) -> None:
        mon = _tsl_monitor_with_early_withdrawal()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "alert"

    def test_new_alerts_count_one(self) -> None:
        mon = _tsl_monitor_with_early_withdrawal()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 1

    def test_withdrawal_early_flag_set(self) -> None:
        mon = _tsl_monitor_with_early_withdrawal()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_has_withdrawal_early"] is True

    def test_total_tracked_reflected_with_alerts(self) -> None:
        mon = _tsl_monitor_with_early_withdrawal()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_alerts_count"] == 8


# ---------------------------------------------------------------------------
# Group D — Mixed alerts
# ---------------------------------------------------------------------------


class TestMixedAlerts:
    def test_status_alert_when_any_new_alerts(self) -> None:
        mon = _tsl_monitor_mixed_alerts()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "alert"

    def test_new_alerts_count_three(self) -> None:
        mon = _tsl_monitor_mixed_alerts()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 3

    def test_withdrawal_early_flag_set_when_mixed(self) -> None:
        mon = _tsl_monitor_mixed_alerts()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_has_withdrawal_early"] is True

    def test_no_withdrawal_flag_when_all_non_early(self) -> None:
        mon = {
            "new_alerts": [
                {"classification": "TSL_MARKET_NORMAL_REMOVAL"},
                {"classification": "TSL_MARKET_NEVER_SEEN"},
            ],
            "total_tracked": 5,
            "poll_ts": TIMESTAMP,
        }
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_has_withdrawal_early"] is False
        assert row["tsl_monitor_new_alerts_count"] == 2


# ---------------------------------------------------------------------------
# Group E — Malformed monitor result
# ---------------------------------------------------------------------------


class TestMalformedMonitorResult:
    def test_non_dict_tsl_monitor_treated_as_no_data(self) -> None:
        result = _result_captured({"tsl_monitor": "unexpected_string"})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "no_data"
        assert row["tsl_monitor_new_alerts_count"] == 0

    def test_none_tsl_monitor_treated_as_no_data(self) -> None:
        result = _result_captured({"tsl_monitor": None})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "no_data"

    def test_error_key_yields_error_status(self) -> None:
        mon = _tsl_monitor_error()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_status"] == "error"

    def test_error_status_counts_still_zero(self) -> None:
        mon = _tsl_monitor_error()
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 0
        assert row["tsl_monitor_has_withdrawal_early"] is False

    def test_non_list_new_alerts_is_safe(self) -> None:
        mon = {"new_alerts": "broken", "total_tracked": 3, "poll_ts": TIMESTAMP}
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 0
        assert row["tsl_monitor_status"] == "ok"

    def test_non_dict_items_in_new_alerts_skip_gracefully(self) -> None:
        mon = {
            "new_alerts": [None, "garbage", 42, {"classification": "TSL_MARKET_WITHDRAWAL_EARLY"}],
            "total_tracked": 4,
            "poll_ts": TIMESTAMP,
        }
        result = _result_captured({"tsl_monitor": mon})
        row = make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)
        assert row["tsl_monitor_new_alerts_count"] == 4
        assert row["tsl_monitor_has_withdrawal_early"] is True


# ---------------------------------------------------------------------------
# Group F — Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """All v2 fields must still be present with correct types after P28D.1."""

    V2_BOOL_FIELDS = [
        "heartbeat_written",
        "odds_fetch_attempted",
        "fetch_success",
        "source_empty",
        "closing_odds_captured",
        "external_fetch_blocked_by_quota",
        "quota_reserved_for_closing",
    ]
    V2_INT_FIELDS = ["api_calls_today", "target_games_seen", "target_games_missing"]
    V2_STR_FIELDS = ["timestamp", "status", "semantic_status_version"]

    def _row(self) -> dict:
        from wbc_backend.mlb_data.heartbeat_schema import make_semantic_heartbeat_row

        mon = _tsl_monitor_with_early_withdrawal()
        result = _result_captured({"snapshots_received": 3, "tsl_monitor": mon})
        return make_semantic_heartbeat_row(result, STATE_EMPTY, TIMESTAMP)

    def test_semantic_status_version_still_v2(self) -> None:
        assert self._row()["semantic_status_version"] == "v2"

    def test_heartbeat_written_still_present(self) -> None:
        assert self._row()["heartbeat_written"] is True

    @pytest.mark.parametrize("field", V2_BOOL_FIELDS)
    def test_v2_bool_fields_present(self, field: str) -> None:
        row = self._row()
        assert field in row
        assert isinstance(row[field], bool)

    @pytest.mark.parametrize("field", V2_INT_FIELDS)
    def test_v2_int_fields_present(self, field: str) -> None:
        row = self._row()
        assert field in row
        assert isinstance(row[field], int)

    @pytest.mark.parametrize("field", V2_STR_FIELDS)
    def test_v2_str_fields_present(self, field: str) -> None:
        row = self._row()
        assert field in row
        assert isinstance(row[field], str)

    def test_new_monitor_fields_all_present(self) -> None:
        row = self._row()
        assert "tsl_monitor_alerts_count" in row
        assert "tsl_monitor_new_alerts_count" in row
        assert "tsl_monitor_has_withdrawal_early" in row
        assert "tsl_monitor_status" in row

    def test_schema_version_constant_unchanged(self) -> None:
        assert SEMANTIC_STATUS_VERSION == "v2"
