"""
test_p28d2_tsl_monitor_alert_formatter.py
P28D.2: Targeted tests for the TSL monitor alert formatter.

Five groups:
  A – no-alert conditions → should_emit_alert returns False, emit returns None
  B – alert-status conditions → notification emitted and formatted
  C – early-withdrawal conditions → high-priority wording (🚨 HIGH, 早期撤市)
  D – malformed / edge-case inputs → failure-safe, no exception
  E – backward compat (pre-P28D.1 rows lacking tsl_monitor_* fields) → no-alert
"""
from __future__ import annotations

import logging

import pytest

from wbc_backend.mlb_data.tsl_monitor_alert_formatter import (
    emit_alert_if_needed,
    format_alert_message,
    should_emit_alert,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _base_alert_row() -> dict:
    """Minimal heartbeat row that triggers an alert."""
    return {
        "tsl_monitor_status": "alert",
        "tsl_monitor_new_alerts_count": 2,
        "tsl_monitor_alerts_count": 5,
        "tsl_monitor_has_withdrawal_early": False,
        "timestamp": "2026-01-01T00:00:00Z",
    }


def _withdrawal_row() -> dict:
    """Heartbeat row that signals early withdrawal."""
    return {
        "tsl_monitor_status": "alert",
        "tsl_monitor_new_alerts_count": 1,
        "tsl_monitor_alerts_count": 3,
        "tsl_monitor_has_withdrawal_early": True,
        "timestamp": "2026-01-02T00:00:00Z",
    }


# ===========================================================================
# Group A — no-alert conditions
# ===========================================================================

class TestNoAlertConditions:
    def test_status_ok_no_alert(self):
        row = {**_base_alert_row(), "tsl_monitor_status": "ok",
               "tsl_monitor_has_withdrawal_early": False}
        assert should_emit_alert(row) is False

    def test_status_no_data_no_alert(self):
        row = {**_base_alert_row(), "tsl_monitor_status": "no_data",
               "tsl_monitor_has_withdrawal_early": False}
        assert should_emit_alert(row) is False

    def test_status_error_no_withdrawal_no_alert(self):
        # "error" alone (without early withdrawal) does NOT trigger alert
        row = {**_base_alert_row(), "tsl_monitor_status": "error",
               "tsl_monitor_has_withdrawal_early": False}
        assert should_emit_alert(row) is False

    def test_empty_row_no_alert(self):
        assert should_emit_alert({}) is False

    def test_emit_returns_none_when_no_alert(self):
        row = {**_base_alert_row(), "tsl_monitor_status": "ok",
               "tsl_monitor_has_withdrawal_early": False}
        assert emit_alert_if_needed(row) is None

    def test_status_alert_case_sensitive(self):
        # Only lowercase "alert" triggers — not uppercase
        row = {**_base_alert_row(), "tsl_monitor_status": "ALERT",
               "tsl_monitor_has_withdrawal_early": False}
        assert should_emit_alert(row) is False


# ===========================================================================
# Group B — alert-status conditions
# ===========================================================================

class TestAlertStatusConditions:
    def test_alert_status_triggers(self):
        row = _base_alert_row()
        assert should_emit_alert(row) is True

    def test_emit_returns_message_on_alert(self):
        row = _base_alert_row()
        msg = emit_alert_if_needed(row)
        assert msg is not None
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_formatted_message_contains_tsl_header(self):
        row = _base_alert_row()
        msg = format_alert_message(row)
        assert "TSL Monitor Alert" in msg

    def test_formatted_message_contains_status(self):
        row = _base_alert_row()
        msg = format_alert_message(row)
        assert "alert" in msg.lower()

    def test_formatted_message_contains_new_alerts_count(self):
        row = {**_base_alert_row(), "tsl_monitor_new_alerts_count": 7}
        msg = format_alert_message(row)
        assert "7" in msg

    def test_formatted_message_contains_total_tracked(self):
        row = {**_base_alert_row(), "tsl_monitor_alerts_count": 42}
        msg = format_alert_message(row)
        assert "42" in msg

    def test_formatted_message_contains_timestamp(self):
        row = _base_alert_row()
        msg = format_alert_message(row)
        assert "2026-01-01T00:00:00Z" in msg

    def test_emit_logs_warning(self, caplog):
        row = _base_alert_row()
        with caplog.at_level(logging.WARNING):
            emit_alert_if_needed(row)
        assert any("TSL Monitor Alert" in r.message for r in caplog.records)


# ===========================================================================
# Group C — early-withdrawal high-priority wording
# ===========================================================================

class TestEarlyWithdrawalConditions:
    def test_withdrawal_early_true_triggers(self):
        row = _withdrawal_row()
        assert should_emit_alert(row) is True

    def test_withdrawal_early_without_alert_status_still_triggers(self):
        # has_withdrawal_early alone triggers even if status is "ok"
        row = {**_withdrawal_row(), "tsl_monitor_status": "ok"}
        assert should_emit_alert(row) is True

    def test_high_priority_emoji_in_message(self):
        row = _withdrawal_row()
        msg = format_alert_message(row)
        assert "🚨" in msg

    def test_high_priority_tag_in_message(self):
        row = _withdrawal_row()
        msg = format_alert_message(row)
        assert "HIGH" in msg

    def test_withdrawal_early_label_in_message(self):
        row = _withdrawal_row()
        msg = format_alert_message(row)
        assert "早期撤市" in msg

    def test_withdrawal_class_constant_in_message(self):
        row = _withdrawal_row()
        msg = format_alert_message(row)
        assert "TSL_MARKET_WITHDRAWAL_EARLY" in msg

    def test_emit_returns_message_for_withdrawal(self):
        row = _withdrawal_row()
        msg = emit_alert_if_needed(row)
        assert msg is not None
        assert "🚨" in msg

    def test_non_withdrawal_row_does_not_have_high_priority(self):
        row = _base_alert_row()
        msg = format_alert_message(row)
        assert "🚨 HIGH" not in msg
        assert "ℹ️" in msg or "INFO" in msg


# ===========================================================================
# Group D — malformed / edge-case inputs (failure-safe)
# ===========================================================================

class TestMalformedInputs:
    def test_none_input_should_emit_false(self):
        assert should_emit_alert(None) is False

    def test_none_input_emit_returns_none(self):
        assert emit_alert_if_needed(None) is None

    def test_list_input_should_emit_false(self):
        assert should_emit_alert([1, 2, 3]) is False

    def test_string_input_should_emit_false(self):
        assert should_emit_alert("alert") is False

    def test_format_none_does_not_raise(self):
        msg = format_alert_message(None)
        assert isinstance(msg, str)

    def test_format_list_does_not_raise(self):
        msg = format_alert_message([])
        assert isinstance(msg, str)

    def test_none_counts_default_to_zero(self):
        row = {
            "tsl_monitor_status": "alert",
            "tsl_monitor_new_alerts_count": None,
            "tsl_monitor_alerts_count": None,
            "tsl_monitor_has_withdrawal_early": False,
        }
        msg = format_alert_message(row)
        assert "0" in msg

    def test_missing_timestamp_shows_unknown(self):
        row = {
            "tsl_monitor_status": "alert",
            "tsl_monitor_new_alerts_count": 1,
            "tsl_monitor_alerts_count": 1,
            "tsl_monitor_has_withdrawal_early": False,
        }
        msg = format_alert_message(row)
        assert "unknown" in msg

    def test_extra_fields_ignored(self):
        row = {**_base_alert_row(), "extra_field": "ignored", "another": 99}
        msg = format_alert_message(row)
        assert isinstance(msg, str)
        assert "extra_field" not in msg


# ===========================================================================
# Group E — backward compatibility (pre-P28D.1 rows)
# ===========================================================================

class TestBackwardCompatibility:
    """Old heartbeat rows lack tsl_monitor_* fields. They must never trigger alerts."""

    def _old_row(self) -> dict:
        """Simulate a pre-P28D.1 heartbeat row (no tsl_monitor_* keys)."""
        return {
            "timestamp": "2025-01-01T00:00:00Z",
            "status": "captured",
            "games_updated": 5,
            "external_closing_status": "idle",
        }

    def test_old_row_no_alert(self):
        assert should_emit_alert(self._old_row()) is False

    def test_old_row_emit_returns_none(self):
        assert emit_alert_if_needed(self._old_row()) is None

    def test_old_row_format_safe(self):
        msg = format_alert_message(self._old_row())
        assert isinstance(msg, str)

    def test_partial_row_only_status_not_alert(self):
        row = {**self._old_row(), "tsl_monitor_status": "no_data"}
        assert should_emit_alert(row) is False

    def test_partial_row_status_ok_not_alert(self):
        row = {**self._old_row(), "tsl_monitor_status": "ok",
               "tsl_monitor_has_withdrawal_early": False}
        assert should_emit_alert(row) is False

    def test_partial_row_status_alert_triggers(self):
        # Partial row that happens to have the alert status — still triggers
        row = {**self._old_row(), "tsl_monitor_status": "alert"}
        assert should_emit_alert(row) is True
