"""
P28A — Unit tests for OddsAPI quota persistence (Policy B) and
        closing window reservation (Policy A).

Policy B: api_calls_today persisted to disk BEFORE the API call so the
          counter survives a daemon crash during the request.
Policy A: When api_calls_today >= cap - CLOSING_WINDOW_RESERVE and a
          future game's trigger window has not yet opened, block the call
          to preserve quota for that closing window.
Policy C: Both A and B active (the recommended configuration).

Root cause addressed: P26K QUOTA_HARD_CAP
  — daemon restart wiped in-memory counter → two early calls consumed the
    daily budget before the closing window (07:10–08:56Z).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wbc_backend.mlb_data.daily_closing_capture import (
    CLOSING_WINDOW_RESERVE,
    TRIGGER_LEAD_MINUTES,
    _next_trigger_game,
    _today_utc,
    run_daily_closing_capture,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _game_row(game_id: str, offset_minutes: float) -> dict:
    """Build a minimal JSONL timeline row whose game starts *offset_minutes* from now."""
    ct = _utc_now() + timedelta(minutes=offset_minutes)
    return {
        "game_id": game_id,
        "source": "live",
        "commence_time": ct.isoformat().replace("+00:00", "Z"),
    }


def _write_timeline(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in rows),
        encoding="utf-8",
    )


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def _ok_capture(**_kwargs) -> dict:
    """Mock capture_external_closing that returns a minimal success payload."""
    return {
        "fetched": 1,
        "matched": 1,
        "updated": 1,
        "stale_skipped": 0,
        "unmatched": 0,
        "status": "ok",
    }


CAPTURE_PATH = "wbc_backend.mlb_data.daily_closing_capture.capture_external_closing"


# ---------------------------------------------------------------------------
# Policy A: closing-window quota reservation
# ---------------------------------------------------------------------------

class TestPolicyA:
    """Policy A — block calls when quota would be exhausted before a future game window."""

    def test_blocks_when_future_game_exists_and_quota_at_reserve(self, tmp_path):
        """api_calls=1 + future game → status=skipped_quota_reserved_for_closing."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Game C started 5 min ago (within 90 min window, triggers current call).
        # Game B starts 120 min from now (future, trigger not yet open).
        _write_timeline(timeline, [
            _game_row("C01", -5),
            _game_row("B01", 120),
        ])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] == "skipped_quota_reserved_for_closing", (
            f"Expected quota_reserved, got {result['status']!r}:\n{result}"
        )
        assert result["api_calls_today"] == 1, "No new call should have been made"
        mock_cap.assert_not_called()

    def test_no_block_when_api_calls_zero(self, tmp_path):
        """api_calls=0 → Policy A never triggers regardless of future games."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_timeline(timeline, [
            _game_row("C01", -5),
            _game_row("B01", 120),
        ])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 0,
            "fetched": False,
        })

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] != "skipped_quota_reserved_for_closing", (
            f"Should not have been blocked at api_calls=0: {result}"
        )
        mock_cap.assert_called_once()

    def test_no_block_when_no_future_game(self, tmp_path):
        """api_calls=1 but no future game → no reservation needed."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Only a current game, no future games.
        _write_timeline(timeline, [_game_row("C01", -5)])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] != "skipped_quota_reserved_for_closing", (
            f"Should not block with no future game: {result}"
        )
        mock_cap.assert_called_once()

    def test_no_block_when_game_in_trigger_window(self, tmp_path):
        """Policy A does not block once the target game is within TRIGGER_LEAD_MINUTES."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Target game starts in 5 min (within the 10-min trigger threshold).
        _write_timeline(timeline, [_game_row("B01", 5)])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] != "skipped_quota_reserved_for_closing", (
            f"Policy A should not block a game inside the trigger window:\n{result}"
        )
        mock_cap.assert_called_once()

    def test_force_bypasses_policy_a(self, tmp_path):
        """force=True overrides Policy A reservation."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_timeline(timeline, [
            _game_row("C01", -5),
            _game_row("B01", 120),
        ])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
                force=True,
            )

        assert result["status"] != "skipped_quota_reserved_for_closing", (
            f"force=True must bypass Policy A:\n{result}"
        )
        mock_cap.assert_called_once()


# ---------------------------------------------------------------------------
# Policy B: quota persistence before API call
# ---------------------------------------------------------------------------

class TestPolicyB:
    """Policy B — api_calls_today written to disk BEFORE the HTTP request fires."""

    def test_counter_on_disk_before_api_call(self, tmp_path):
        """State file must show incremented counter while the API call is in flight."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_timeline(timeline, [_game_row("A01", -5)])
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 0,
            "fetched": False,
        })

        observed: list[int] = []

        def _spy_capture(**_kwargs):
            on_disk = json.loads(state_p.read_text())
            observed.append(on_disk.get("api_calls_today", -1))
            return _ok_capture()

        with patch(CAPTURE_PATH, side_effect=_spy_capture):
            run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert observed == [1], (
            f"api_calls_today on disk must be 1 when the API call fires; got {observed}"
        )

    def test_state_restored_on_restart_same_date(self, tmp_path):
        """Simulated restart: state loaded from disk preserves api_calls_today."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Pre-restart state: 1 call used.
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })
        _write_timeline(timeline, [_game_row("A01", -5)])

        with patch(CAPTURE_PATH, side_effect=_ok_capture):
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        # Counter starts at 1 (restored) and increments to 2 for this call.
        assert result["api_calls_today"] == 2, (
            f"Expected api_calls_today=2 after restoring pre-restart count of 1; "
            f"got {result['api_calls_today']}"
        )

    def test_state_resets_on_new_date(self, tmp_path):
        """Stale state from a different date is discarded; counter resets to 0."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_state(state_p, {
            "date": "2020-01-01",   # past date — should trigger reset
            "api_calls_today": 99,
            "fetched": True,        # would prevent a call if date matched today
        })
        _write_timeline(timeline, [_game_row("A01", -5)])

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        # After date reset: starts at 0, increments to 1 for this call.
        assert result["api_calls_today"] == 1, (
            f"Expected api_calls_today=1 after date-triggered reset; "
            f"got {result['api_calls_today']}"
        )
        mock_cap.assert_called_once()

    def test_hard_cap_respected_after_restore(self, tmp_path):
        """Restored api_calls_today=2 immediately triggers the hard cap."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 2,
            "fetched": False,
        })
        _write_timeline(timeline, [_game_row("A01", -5)])

        with patch(CAPTURE_PATH) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] == "skipped_daily_cap_reached"
        mock_cap.assert_not_called()


# ---------------------------------------------------------------------------
# Policy C: combined A + B (P26K regression test)
# ---------------------------------------------------------------------------

class TestPolicyC:
    """Policy C integration — reproduce P26K and verify the fix."""

    def test_p26k_post_restart_retry_is_blocked(self, tmp_path):
        """
        P26K replay:
          - Policy B: daemon restart preserves api_calls_today=1 from disk.
          - Policy A: retry for game C (7 min past) is blocked because game B
                      (108 min away) still needs the last quota call.
          - Net effect: quota available for game B's closing window.
        """
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Post-restart state restored from disk (Policy B in action).
        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })
        # Game C: 7 min past (within 90-min window, would trigger a retry).
        # Game B: 108 min away (NPB / Asian game, needs closing odds).
        _write_timeline(timeline, [
            _game_row("C01", -7),
            _game_row("B01", 108),
        ])

        with patch(CAPTURE_PATH) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] == "skipped_quota_reserved_for_closing", (
            f"P26K replay: expected quota_reserved, got {result['status']!r}:\n{result}"
        )
        mock_cap.assert_not_called()
        assert result["api_calls_today"] == 1, "Quota must not have been consumed"

    def test_p26k_game_b_fetches_when_in_trigger_window(self, tmp_path):
        """Game B can fetch once its trigger window opens (T-8min)."""
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        _write_state(state_p, {
            "date": _today_utc(),
            "api_calls_today": 1,
            "fetched": False,
        })
        # Game B is now 8 min away — inside the 10-min trigger threshold.
        _write_timeline(timeline, [_game_row("B01", 8)])

        with patch(CAPTURE_PATH, side_effect=_ok_capture) as mock_cap:
            result = run_daily_closing_capture(
                api_key="fake",
                timeline_path=timeline,
                state_path=state_p,
            )

        assert result["status"] == "ok", (
            f"Game B should fetch successfully once in trigger window: {result['status']!r}:\n{result}"
        )
        assert result["api_calls_today"] == 2
        mock_cap.assert_called_once()

    def test_full_day_sequence(self, tmp_path):
        """
        Simulate a full day:
          tick 1 — game A at T-5, api_calls=0 → fetch succeeds (api_calls→1)
          tick 2 — game A at T-7, api_calls=1, game B at T+108 → RESERVED
          tick 3 — game B at T-8, api_calls=1 → fetch succeeds (api_calls→2)
          tick 4 — game B fetched=True → skipped_already_done
        """
        timeline = tmp_path / "tl.jsonl"
        state_p  = tmp_path / "st.json"

        # Tick 1: first call for game A, api_calls=0
        _write_state(state_p, {"date": _today_utc(), "api_calls_today": 0, "fetched": False})
        _write_timeline(timeline, [_game_row("A01", -5)])
        with patch(CAPTURE_PATH, side_effect=_ok_capture):
            r1 = run_daily_closing_capture(api_key="fake", timeline_path=timeline, state_path=state_p)
        assert r1["status"] == "ok"
        assert r1["api_calls_today"] == 1

        # Tick 2: retry for game A with future game B present → reserved
        _write_state(state_p, {"date": _today_utc(), "api_calls_today": 1, "fetched": False})
        _write_timeline(timeline, [_game_row("A01", -7), _game_row("B01", 108)])
        with patch(CAPTURE_PATH) as mock_cap:
            r2 = run_daily_closing_capture(api_key="fake", timeline_path=timeline, state_path=state_p)
        assert r2["status"] == "skipped_quota_reserved_for_closing"
        mock_cap.assert_not_called()

        # Tick 3: game B now in trigger window → fetch succeeds
        _write_state(state_p, {"date": _today_utc(), "api_calls_today": 1, "fetched": False})
        _write_timeline(timeline, [_game_row("B01", 8)])
        with patch(CAPTURE_PATH, side_effect=_ok_capture):
            r3 = run_daily_closing_capture(api_key="fake", timeline_path=timeline, state_path=state_p)
        assert r3["status"] == "ok"
        assert r3["api_calls_today"] == 2

        # Tick 4: cap=2 already hit (hard cap check fires before fetched check)
        _write_state(state_p, {"date": _today_utc(), "api_calls_today": 2, "fetched": True})
        with patch(CAPTURE_PATH) as mock_cap:
            r4 = run_daily_closing_capture(api_key="fake", timeline_path=timeline, state_path=state_p)
        assert r4["status"] in ("skipped_daily_cap_reached", "skipped_already_done"), (
            f"Expected a skip status at cap, got {r4['status']!r}"
        )
        mock_cap.assert_not_called()


# ---------------------------------------------------------------------------
# _next_trigger_game helper
# ---------------------------------------------------------------------------

class TestNextTriggerGame:
    """Unit tests for the _next_trigger_game helper used by Policy A."""

    def test_returns_none_when_no_future_games(self, tmp_path):
        timeline = tmp_path / "tl.jsonl"
        # All games in the past (beyond the trigger threshold).
        _write_timeline(timeline, [
            _game_row("A01", -30),
            _game_row("A02", -15),
        ])
        assert _next_trigger_game(timeline) is None

    def test_returns_none_for_game_at_exact_threshold(self, tmp_path):
        """A game exactly at now+TRIGGER_LEAD_MINUTES is NOT a 'future' game."""
        timeline = tmp_path / "tl.jsonl"
        _write_timeline(timeline, [_game_row("B01", TRIGGER_LEAD_MINUTES)])
        # The helper uses strict >; a game exactly at the threshold is excluded.
        assert _next_trigger_game(timeline) is None

    def test_returns_game_beyond_threshold(self, tmp_path):
        timeline = tmp_path / "tl.jsonl"
        _write_timeline(timeline, [
            _game_row("A01", -5),           # in window
            _game_row("B01", TRIGGER_LEAD_MINUTES + 1),  # just beyond threshold
        ])
        result = _next_trigger_game(timeline)
        assert result is not None

    def test_returns_earliest_future_game(self, tmp_path):
        """Returns the minimum start time among all future (beyond threshold) games."""
        timeline = tmp_path / "tl.jsonl"
        earlier = _utc_now() + timedelta(minutes=TRIGGER_LEAD_MINUTES + 30)
        later   = _utc_now() + timedelta(minutes=TRIGGER_LEAD_MINUTES + 120)
        _write_timeline(timeline, [
            {"source": "live", "commence_time": later.isoformat().replace("+00:00", "Z"), "game_id": "X"},
            {"source": "live", "commence_time": earlier.isoformat().replace("+00:00", "Z"), "game_id": "Y"},
        ])
        result = _next_trigger_game(timeline)
        assert result is not None
        assert abs((result - earlier).total_seconds()) < 2  # within 2-second tolerance

    def test_skips_historical_rows(self, tmp_path):
        """Rows with source='historical_...' are ignored."""
        timeline = tmp_path / "tl.jsonl"
        _write_timeline(timeline, [
            {"source": "historical_2025", "commence_time":
             (_utc_now() + timedelta(hours=3)).isoformat().replace("+00:00", "Z"), "game_id": "H"},
        ])
        assert _next_trigger_game(timeline) is None
