"""
test_p28d_tsl_poll_monitor.py
P28D: Wire TslMarketAvailabilityMonitor into TSL poll cycle — targeted tests

Covers:
  Group A — _make_match_id helper
  Group B — run_tsl_monitor_after_poll integration (in-memory / tmp dir)
  Group C — detection logic (withdrawal, normal removal, never seen)
  Group D — safety / edge cases (empty list, None, errors)
  Group E — capture_live_odds summary includes tsl_monitor key (unit test)
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from wbc_backend.mlb_data.tsl_poll_monitor_adapter import (
    _make_match_id,
    run_tsl_monitor_after_poll,
)
from wbc_backend.mlb_data.tsl_market_availability_monitor import (
    CLASS_NORMAL_REMOVAL,
    CLASS_NEVER_SEEN,
    CLASS_WITHDRAWAL_EARLY,
    TslMarketAvailabilityMonitor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAME_TIME_FAR = "2026-06-01T18:00:00Z"   # far future — early threshold applies
_GAME_TIME_NEAR = "2026-06-01T18:00:00Z"  # reused; poll_ts adjusted in tests

_POLL_TS_EARLY = "2026-06-01T12:00:00Z"   # 6h before game → WITHDRAWAL_EARLY
_POLL_TS_CLOSE = "2026-06-01T17:00:00Z"   # 1h before game → NORMAL_REMOVAL


def _snap(
    *,
    home: str = "New York Yankees",
    away: str = "Boston Red Sox",
    game_time: str = _GAME_TIME_FAR,
) -> dict[str, Any]:
    return {
        "home_team": home,
        "away_team": away,
        "game_time": game_time,
        "home_ml": -150,
        "away_ml": 130,
        "source": "TSL",
        "fetched_at": _POLL_TS_EARLY,
    }


def _tmp_state() -> Path:
    """Return a fresh temp-file path for monitor state (deleted by OS after test)."""
    tmp = tempfile.mktemp(suffix=".json")
    return Path(tmp)


# ---------------------------------------------------------------------------
# Group A — _make_match_id
# ---------------------------------------------------------------------------


class TestMakeMatchId:
    def test_stable_across_calls(self) -> None:
        snap = _snap()
        assert _make_match_id(snap) == _make_match_id(snap)

    def test_contains_all_components(self) -> None:
        snap = _snap(home="LA Dodgers", away="SF Giants", game_time="2026-06-01T20:00:00Z")
        mid = _make_match_id(snap)
        assert "LA Dodgers" in mid
        assert "SF Giants" in mid
        assert "2026-06-01T20:00:00Z" in mid

    def test_different_games_produce_different_ids(self) -> None:
        s1 = _snap(home="Team A", away="Team B")
        s2 = _snap(home="Team C", away="Team D")
        assert _make_match_id(s1) != _make_match_id(s2)

    def test_returns_empty_when_game_time_missing(self) -> None:
        snap = _snap()
        snap.pop("game_time")
        assert _make_match_id(snap) == ""

    def test_returns_empty_when_home_missing(self) -> None:
        snap = {
            "away_team": "Boston Red Sox",
            "game_time": _GAME_TIME_FAR,
            "source": "TSL",
        }
        assert _make_match_id(snap) == ""

    def test_returns_empty_when_away_missing(self) -> None:
        snap = {
            "home_team": "New York Yankees",
            "game_time": _GAME_TIME_FAR,
            "source": "TSL",
        }
        assert _make_match_id(snap) == ""

    def test_separator_char_used(self) -> None:
        """Verify pipe separator avoids accidental key collisions."""
        mid = _make_match_id(_snap())
        assert "|" in mid


# ---------------------------------------------------------------------------
# Group B — run_tsl_monitor_after_poll integration
# ---------------------------------------------------------------------------


class TestRunTslMonitorAfterPoll:
    def test_returns_dict_with_required_keys(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        result = run_tsl_monitor_after_poll(
            tsl_snaps=[_snap()],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert "new_alerts" in result
        assert "total_tracked" in result
        assert "poll_ts" in result

    def test_total_tracked_increments_on_new_match(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        r1 = run_tsl_monitor_after_poll(
            tsl_snaps=[_snap()],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r1["total_tracked"] == 1

    def test_same_match_not_double_counted(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        snaps = [_snap(), _snap()]  # exact duplicates
        r = run_tsl_monitor_after_poll(
            tsl_snaps=snaps,
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r["total_tracked"] == 1  # deduped by match_id

    def test_state_persisted_across_calls(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        run_tsl_monitor_after_poll(
            tsl_snaps=[_snap()],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert state.exists()
        loaded = json.loads(state.read_text(encoding="utf-8"))
        assert len(loaded) == 1

    def test_poll_ts_echoed_in_result(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        r = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r["poll_ts"] == _POLL_TS_EARLY

    def test_snaps_with_missing_fields_skipped(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        incomplete = {"home_team": "Team A", "source": "TSL"}  # no away_team or game_time
        r = run_tsl_monitor_after_poll(
            tsl_snaps=[incomplete],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r["total_tracked"] == 0  # incomplete snap skipped
        assert r["new_alerts"] == []


# ---------------------------------------------------------------------------
# Group C — detection logic
# ---------------------------------------------------------------------------


class TestDetectionLogic:
    def test_early_withdrawal_detected(self, tmp_path: Path) -> None:
        """Match seen at 6h before game, absent at next poll → WITHDRAWAL_EARLY."""
        state = tmp_path / "state.json"
        snap = _snap(game_time=_GAME_TIME_FAR)

        # Cycle 1: match present
        run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts=_POLL_TS_EARLY,  # 6h before game
            state_path=state,
        )
        # Cycle 2: match absent
        r2 = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts="2026-06-01T13:00:00Z",  # 5h before game > 2h threshold
            state_path=state,
        )
        assert len(r2["new_alerts"]) == 1
        assert r2["new_alerts"][0]["classification"] == CLASS_WITHDRAWAL_EARLY

    def test_normal_removal_within_2h(self, tmp_path: Path) -> None:
        """Match absent when < 2h before game → NORMAL_REMOVAL."""
        state = tmp_path / "state.json"
        snap = _snap(game_time=_GAME_TIME_FAR)

        # Cycle 1: match present at 6h before
        run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        # Cycle 2: absent at 1h before → NORMAL_REMOVAL
        r2 = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts=_POLL_TS_CLOSE,  # 1h before game
            state_path=state,
        )
        assert len(r2["new_alerts"]) == 1
        assert r2["new_alerts"][0]["classification"] == CLASS_NORMAL_REMOVAL

    def test_no_alert_when_match_still_present(self, tmp_path: Path) -> None:
        """Match present in both cycles → no new alerts."""
        state = tmp_path / "state.json"
        snap = _snap()
        run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        r2 = run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts="2026-06-01T14:00:00Z",
            state_path=state,
        )
        assert r2["new_alerts"] == []

    def test_classification_written_once(self, tmp_path: Path) -> None:
        """Once classified, a second absence cycle should NOT re-emit."""
        state = tmp_path / "state.json"
        snap = _snap(game_time=_GAME_TIME_FAR)

        run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        # First absence → classified
        r2 = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts="2026-06-01T13:00:00Z",
            state_path=state,
        )
        assert len(r2["new_alerts"]) == 1

        # Second absence → already classified, no new event
        r3 = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts="2026-06-01T14:00:00Z",
            state_path=state,
        )
        assert len(r3["new_alerts"]) == 0

    def test_never_seen_when_game_time_passed(self, tmp_path: Path) -> None:
        """Pre-registered match that was never seen → NEVER_SEEN after game_time."""
        state = tmp_path / "state.json"
        # Pre-register via direct monitor API
        monitor = TslMarketAvailabilityMonitor(state_path=state)
        monitor.load()
        monitor.register_match(
            match_id="test_never_seen",
            game_time="2020-01-01T12:00:00Z",  # past game
            league="MLB",
        )
        monitor.save()

        # Run monitor with empty snaps at a time AFTER game_time
        r = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts="2020-01-01T13:00:00Z",  # 1h after game_time
            state_path=state,
        )
        classifications = [a["classification"] for a in r["new_alerts"]]
        assert CLASS_NEVER_SEEN in classifications

    def test_hours_before_game_populated(self, tmp_path: Path) -> None:
        """hours_before_game should be approximately correct."""
        state = tmp_path / "state.json"
        snap = _snap(game_time=_GAME_TIME_FAR)

        run_tsl_monitor_after_poll(
            tsl_snaps=[snap],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        r2 = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts="2026-06-01T13:00:00Z",  # 5h before
            state_path=state,
        )
        alert = r2["new_alerts"][0]
        assert alert["hours_before_game"] == pytest.approx(5.0, abs=0.1)


# ---------------------------------------------------------------------------
# Group D — safety / edge cases
# ---------------------------------------------------------------------------


class TestSafety:
    def test_empty_snaps_list_no_crash(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        r = run_tsl_monitor_after_poll(
            tsl_snaps=[],
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r["new_alerts"] == []
        assert r["total_tracked"] == 0

    def test_state_path_created_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "dir" / "state.json"
        run_tsl_monitor_after_poll(
            tsl_snaps=[_snap()],
            poll_ts=_POLL_TS_EARLY,
            state_path=nested,
        )
        assert nested.exists()

    def test_returns_error_key_on_exception(self, tmp_path: Path) -> None:
        """When monitor raises internally, adapter returns safe fallback with 'error'."""
        state = tmp_path / "state.json"
        with patch(
            "wbc_backend.mlb_data.tsl_poll_monitor_adapter.TslMarketAvailabilityMonitor",
            side_effect=RuntimeError("mock crash"),
        ):
            r = run_tsl_monitor_after_poll(
                tsl_snaps=[_snap()],
                poll_ts=_POLL_TS_EARLY,
                state_path=state,
            )
        assert "error" in r
        assert r["new_alerts"] == []

    def test_does_not_raise_on_invalid_snap(self, tmp_path: Path) -> None:
        """Malformed snap dicts should not raise."""
        state = tmp_path / "state.json"
        bad_snaps = [None, {}, {"home_team": None}, 42]  # type: ignore[list-item]
        r = run_tsl_monitor_after_poll(
            tsl_snaps=bad_snaps,  # type: ignore[arg-type]
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert isinstance(r, dict)

    def test_multiple_matches_tracked(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        snaps = [
            _snap(home="Team A", away="Team B"),
            _snap(home="Team C", away="Team D"),
            _snap(home="Team E", away="Team F"),
        ]
        r = run_tsl_monitor_after_poll(
            tsl_snaps=snaps,
            poll_ts=_POLL_TS_EARLY,
            state_path=state,
        )
        assert r["total_tracked"] == 3


# ---------------------------------------------------------------------------
# Group E — capture_live_odds includes tsl_monitor
# ---------------------------------------------------------------------------

_MONITOR_MOCK_RESULT: dict[str, Any] = {
    "new_alerts": [],
    "total_tracked": 1,
    "poll_ts": "2030-01-01T12:00:00Z",
}


class TestCaptureIntegration:
    def test_tsl_monitor_in_summary_when_snapshots_present(
        self, tmp_path: Path
    ) -> None:
        """
        capture_live_odds() should include 'tsl_monitor' key in the returned
        summary when TSL snapshots are available.
        """
        from wbc_backend.mlb_data.live_odds_collector import capture_live_odds

        fake_snap = {
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
            "game_time": "2030-01-01T20:00:00Z",
            "home_ml": -150,
            "away_ml": 130,
            "source": "TSL",
            "fetched_at": "2030-01-01T12:00:00Z",
        }

        with (
            patch(
                "wbc_backend.mlb_data.live_odds_collector._fetch_tsl_odds",
                return_value=[fake_snap],
            ),
            patch(
                "wbc_backend.mlb_data.live_odds_collector.update_timeline_from_snapshots",
                return_value={
                    "snapshots_received": 1,
                    "games_updated": 1,
                    "snapshots_added": 1,
                    "duplicates_skipped": 0,
                },
            ),
            patch(
                "wbc_backend.mlb_data.live_odds_collector.backfill_slots",
                return_value={"timelines_updated": 0},
            ),
            # Mock the monitor call to avoid touching real state file
            patch(
                "wbc_backend.mlb_data.tsl_poll_monitor_adapter.run_tsl_monitor_after_poll",
                return_value=_MONITOR_MOCK_RESULT,
            ) as mock_mon,
        ):
            result = capture_live_odds(
                odds_api_key=None, timeline_path=tmp_path / "tl.jsonl"
            )

        assert "tsl_monitor" in result
        assert isinstance(result["tsl_monitor"]["new_alerts"], list)
        # Verify adapter was actually called
        mock_mon.assert_called_once()

    def test_tsl_monitor_in_summary_when_snapshots_empty(
        self, tmp_path: Path
    ) -> None:
        """
        When TSL returns empty, capture_live_odds() still includes 'tsl_monitor'
        in the early-return dict.
        """
        from wbc_backend.mlb_data.live_odds_collector import capture_live_odds

        with (
            patch(
                "wbc_backend.mlb_data.live_odds_collector._fetch_tsl_odds",
                return_value=[],
            ),
            patch(
                "wbc_backend.mlb_data.tsl_poll_monitor_adapter.run_tsl_monitor_after_poll",
                return_value={"new_alerts": [], "total_tracked": 0, "poll_ts": "ts"},
            ) as mock_mon,
        ):
            result = capture_live_odds(
                odds_api_key=None, timeline_path=tmp_path / "tl.jsonl"
            )

        assert result["snapshots_received"] == 0
        assert "tsl_monitor" in result
        assert result["tsl_monitor"]["new_alerts"] == []
        mock_mon.assert_called_once()
