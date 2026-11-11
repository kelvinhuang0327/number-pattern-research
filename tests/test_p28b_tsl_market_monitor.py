"""
tests/test_p28b_tsl_market_monitor.py
P28B: Unit tests for TslMarketAvailabilityMonitor

Coverage groups:
  1. First-seen record creation
  2. Still-present → last_seen updated, no classification
  3. Disappeared > 2h → TSL_MARKET_WITHDRAWAL_EARLY
  4. Disappeared <= 2h → TSL_MARKET_NORMAL_REMOVAL
  5. Never seen before game_time → TSL_MARKET_NEVER_SEEN
  6. Reappearance resets consecutive_absent_cycles; classification is permanent
  7. P26K reconstruction (3469930.1 @ 5.60h, 3469931.1 @ 4.08h → both EARLY)
  8. State persistence (save/load round-trip)
  9. Context string stored on first disappearance only
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wbc_backend.mlb_data.tsl_market_availability_monitor import (
    CLASS_NEVER_SEEN,
    CLASS_NORMAL_REMOVAL,
    CLASS_WITHDRAWAL_EARLY,
    TslMarketAvailabilityMonitor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POLL_BASE = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _game_at(hours_from_base: float) -> str:
    return _iso(_POLL_BASE + timedelta(hours=hours_from_base))


def _ts(hours_from_base: float) -> str:
    return _iso(_POLL_BASE + timedelta(hours=hours_from_base))


def _mon(tmp_path: Path) -> TslMarketAvailabilityMonitor:
    return TslMarketAvailabilityMonitor(state_path=tmp_path / "state.json")


# ---------------------------------------------------------------------------
# 1. First-seen record creation
# ---------------------------------------------------------------------------


class TestFirstSeen:
    def test_record_created(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        mon.update(
            seen_match_ids={"M1"},
            match_metadata={"M1": {"game_time": _game_at(6), "league": "NPB"}},
            poll_ts=_ts(0),
        )
        state = mon.get_state()
        assert "M1" in state
        rec = state["M1"]
        assert rec["first_seen_timestamp"] == _ts(0)
        assert rec["last_seen_timestamp"] == _ts(0)
        assert rec["latest_seen_in_source"] is True
        assert rec["league"] == "NPB"
        assert rec["classification"] is None

    def test_multiple_matches_created(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        mon.update(
            seen_match_ids={"A1", "A2", "A3"},
            match_metadata={m: {"game_time": gt} for m in ("A1", "A2", "A3")},
            poll_ts=_ts(0),
        )
        assert set(mon.get_state()) == {"A1", "A2", "A3"}

    def test_home_away_teams_stored(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        mon.update(
            seen_match_ids={"T1"},
            match_metadata={
                "T1": {
                    "game_time": _game_at(8),
                    "home_team_name": "Giants",
                    "away_team_name": "Lions",
                }
            },
            poll_ts=_ts(0),
        )
        rec = mon.get_state()["T1"]
        assert rec["home_team"] == "Giants"
        assert rec["away_team"] == "Lions"


# ---------------------------------------------------------------------------
# 2. Still present — last_seen updated; no classification
# ---------------------------------------------------------------------------


class TestStillPresent:
    def test_last_seen_updated_across_cycles(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(10)
        meta = {"M1": {"game_time": gt, "league": "KBO"}}
        mon.update(seen_match_ids={"M1"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids={"M1"}, match_metadata=meta, poll_ts=_ts(1))
        rec = mon.get_state()["M1"]
        assert rec["first_seen_timestamp"] == _ts(0)
        assert rec["last_seen_timestamp"] == _ts(1)
        assert rec["classification"] is None

    def test_disappeared_at_not_set_while_present(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(8)
        meta = {"X1": {"game_time": gt}}
        for h in range(4):
            mon.update(seen_match_ids={"X1"}, match_metadata=meta, poll_ts=_ts(h))
        assert mon.get_state()["X1"]["disappeared_at"] is None

    def test_absent_cycles_zero_while_present(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(6)
        meta = {"Y1": {"game_time": gt}}
        for h in range(3):
            mon.update(seen_match_ids={"Y1"}, match_metadata=meta, poll_ts=_ts(h))
        assert mon.get_state()["Y1"]["consecutive_absent_cycles"] == 0


# ---------------------------------------------------------------------------
# 3. Early withdrawal (> 2h before game)
# ---------------------------------------------------------------------------


class TestEarlyWithdrawal:
    def test_classified_withdrawal_early(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)  # game in 5h
        meta = {"G1": {"game_time": gt, "league": "NPB"}}
        mon.update(seen_match_ids={"G1"}, match_metadata=meta, poll_ts=_ts(0))
        events = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        # disappeared at ts(1): game is 5-1=4h away → EARLY
        assert len(events) == 1
        assert events[0]["classification"] == CLASS_WITHDRAWAL_EARLY

    def test_hours_before_game_value(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(4)  # 4h from base
        meta = {"G2": {"game_time": gt}}
        mon.update(seen_match_ids={"G2"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(0.5))
        # disappeared at 0.5h from base; game at 4h → 3.5h left
        rec = mon.get_state()["G2"]
        assert rec["hours_before_game"] == pytest.approx(3.5, abs=0.02)
        assert rec["classification"] == CLASS_WITHDRAWAL_EARLY

    def test_get_early_withdrawals_filter(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"E1": {"game_time": gt}}
        mon.update(seen_match_ids={"E1"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        ew = mon.get_early_withdrawals()
        assert len(ew) == 1
        assert ew[0]["match_id"] == "E1"

    def test_get_alerts_includes_early(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"E2": {"game_time": gt}}
        mon.update(seen_match_ids={"E2"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        alerts = mon.get_alerts()
        assert any(a["match_id"] == "E2" for a in alerts)


# ---------------------------------------------------------------------------
# 4. Normal removal (<= 2h before game)
# ---------------------------------------------------------------------------


class TestNormalRemoval:
    def test_classified_normal_removal(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        # Game at base+1.5h; disappears at base → 1.5h before game → NORMAL
        gt = _game_at(1.5)
        meta = {"N1": {"game_time": gt}}
        mon.update(seen_match_ids={"N1"}, match_metadata=meta, poll_ts=_ts(-2))
        events = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(0))
        assert len(events) == 1
        assert events[0]["classification"] == CLASS_NORMAL_REMOVAL

    def test_boundary_exactly_two_hours_is_normal(self, tmp_path: Path) -> None:
        """Exactly 2.0h → NORMAL_REMOVAL (threshold is strictly >)."""
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(2.0)
        meta = {"N2": {"game_time": gt}}
        mon.update(seen_match_ids={"N2"}, match_metadata=meta, poll_ts=_ts(-1))
        events = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(0))
        assert events[0]["classification"] == CLASS_NORMAL_REMOVAL

    def test_no_early_withdrawals_for_normal_removal(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(1.0)
        meta = {"N3": {"game_time": gt}}
        mon.update(seen_match_ids={"N3"}, match_metadata=meta, poll_ts=_ts(-1))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(0))
        assert mon.get_early_withdrawals() == []


# ---------------------------------------------------------------------------
# 5. Never seen before game_time
# ---------------------------------------------------------------------------


class TestNeverSeen:
    def test_registered_match_never_seen_after_game_time(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        # Game was 1h ago
        past_game = _ts(-1)
        mon.register_match("SCHED1", game_time=past_game, league="MLB")
        events = mon.update(
            seen_match_ids=set(),
            match_metadata={},
            poll_ts=_ts(0),
        )
        assert len(events) == 1
        assert events[0]["classification"] == CLASS_NEVER_SEEN
        assert events[0]["match_id"] == "SCHED1"

    def test_never_seen_not_fired_before_game_time(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        future_game = _game_at(3)
        mon.register_match("SCHED2", game_time=future_game)
        events = mon.update(
            seen_match_ids=set(),
            match_metadata={},
            poll_ts=_ts(0),
        )
        assert not any(e["classification"] == CLASS_NEVER_SEEN for e in events)

    def test_never_seen_not_fired_if_match_was_seen(self, tmp_path: Path) -> None:
        """NEVER_SEEN must not fire if the match appeared at least once."""
        mon = _mon(tmp_path)
        mon.load()
        past_game = _ts(-0.5)
        meta = {"LIVE1": {"game_time": past_game}}
        mon.update(seen_match_ids={"LIVE1"}, match_metadata=meta, poll_ts=_ts(-2))
        events = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(0))
        never_seen_events = [e for e in events if e["classification"] == CLASS_NEVER_SEEN]
        assert never_seen_events == []


# ---------------------------------------------------------------------------
# 6. Reappearance
# ---------------------------------------------------------------------------


class TestReappearance:
    def test_absent_cycles_reset_on_reappearance(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(8)
        meta = {"R1": {"game_time": gt}}
        mon.update(seen_match_ids={"R1"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(2))
        assert mon.get_state()["R1"]["consecutive_absent_cycles"] == 2
        # Reappears
        mon.update(seen_match_ids={"R1"}, match_metadata=meta, poll_ts=_ts(3))
        assert mon.get_state()["R1"]["consecutive_absent_cycles"] == 0

    def test_classification_permanent_after_reappearance(self, tmp_path: Path) -> None:
        """Once classified EARLY, it stays EARLY even if match reappears."""
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"R2": {"game_time": gt}}
        mon.update(seen_match_ids={"R2"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))  # → EARLY
        mon.update(seen_match_ids={"R2"}, match_metadata=meta, poll_ts=_ts(2))  # reappears
        assert mon.get_state()["R2"]["classification"] == CLASS_WITHDRAWAL_EARLY

    def test_no_duplicate_events_on_continued_absence(self, tmp_path: Path) -> None:
        """Subsequent absence cycles must not emit duplicate events."""
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"R3": {"game_time": gt}}
        mon.update(seen_match_ids={"R3"}, match_metadata=meta, poll_ts=_ts(0))
        events1 = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        events2 = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(2))
        events3 = mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(3))
        assert len(events1) == 1
        assert events2 == []
        assert events3 == []


# ---------------------------------------------------------------------------
# 7. P26K reconstruction
# ---------------------------------------------------------------------------


class TestP26KReconstruction:
    """
    P26K incident: TSL silently removed NPB games 3469930.1 and 3469931.1
    from the pre-game list at ~03:24Z and ~04:55Z on 2026-05-20.
    Both games had game_time = 09:00Z  (5.60h and 4.08h before tipoff).
    Both should be classified TSL_MARKET_WITHDRAWAL_EARLY.
    """

    GAME_TIME = "2026-05-20T09:00:00Z"
    MID_1 = "3469930.1"
    MID_2 = "3469931.1"
    SEEN_TS = "2026-05-20T01:00:00Z"
    GONE_TS_1 = "2026-05-20T03:24:00Z"
    GONE_TS_2 = "2026-05-20T04:55:00Z"

    @property
    def _meta(self) -> dict:
        return {
            self.MID_1: {"game_time": self.GAME_TIME, "league": "NPB"},
            self.MID_2: {"game_time": self.GAME_TIME, "league": "NPB"},
        }

    def test_game1_withdrawal_early(self, tmp_path: Path) -> None:
        """3469930.1 disappeared at 03:24Z — 5.60h before 09:00Z → EARLY."""
        mon = _mon(tmp_path)
        mon.load()
        mon.update(seen_match_ids={self.MID_1, self.MID_2}, match_metadata=self._meta, poll_ts=self.SEEN_TS)
        # MID_1 gone, MID_2 still present
        events = mon.update(seen_match_ids={self.MID_2}, match_metadata=self._meta, poll_ts=self.GONE_TS_1)
        assert len(events) == 1
        ev = events[0]
        assert ev["match_id"] == self.MID_1
        assert ev["classification"] == CLASS_WITHDRAWAL_EARLY
        assert ev["hours_before_game"] == pytest.approx(5.60, abs=0.05)

    def test_game2_withdrawal_early(self, tmp_path: Path) -> None:
        """3469931.1 disappeared at 04:55Z — 4.08h before 09:00Z → EARLY."""
        mon = _mon(tmp_path)
        mon.load()
        mon.update(seen_match_ids={self.MID_1, self.MID_2}, match_metadata=self._meta, poll_ts=self.SEEN_TS)
        mon.update(seen_match_ids={self.MID_2}, match_metadata=self._meta, poll_ts=self.GONE_TS_1)
        # MID_2 also gone now
        events = mon.update(seen_match_ids=set(), match_metadata=self._meta, poll_ts=self.GONE_TS_2)
        game2 = [e for e in events if e["match_id"] == self.MID_2]
        assert len(game2) == 1
        assert game2[0]["classification"] == CLASS_WITHDRAWAL_EARLY
        assert game2[0]["hours_before_game"] == pytest.approx(4.08, abs=0.05)

    def test_both_in_get_alerts(self, tmp_path: Path) -> None:
        """Full P26K replay: both matches appear in get_alerts() as EARLY."""
        mon = _mon(tmp_path)
        mon.load()
        mon.update(seen_match_ids={self.MID_1, self.MID_2}, match_metadata=self._meta, poll_ts=self.SEEN_TS)
        mon.update(seen_match_ids={self.MID_2}, match_metadata=self._meta, poll_ts=self.GONE_TS_1)
        mon.update(seen_match_ids=set(), match_metadata=self._meta, poll_ts=self.GONE_TS_2)
        alerts = mon.get_alerts()
        alert_ids = {a["match_id"] for a in alerts}
        assert self.MID_1 in alert_ids
        assert self.MID_2 in alert_ids
        assert all(a["classification"] == CLASS_WITHDRAWAL_EARLY for a in alerts)

    def test_p26k_source_name(self, tmp_path: Path) -> None:
        """source_name should be TSL_PREGAME_LIST for both P26K games."""
        mon = _mon(tmp_path)
        mon.load()
        mon.update(seen_match_ids={self.MID_1, self.MID_2}, match_metadata=self._meta, poll_ts=self.SEEN_TS)
        mon.update(seen_match_ids={self.MID_2}, match_metadata=self._meta, poll_ts=self.GONE_TS_1)
        mon.update(seen_match_ids=set(), match_metadata=self._meta, poll_ts=self.GONE_TS_2)
        for rec in mon.get_alerts():
            assert rec["source_name"] == "TSL_PREGAME_LIST"


# ---------------------------------------------------------------------------
# 8. State persistence
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_save_load_roundtrip_basic(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(6)
        meta = {"P1": {"game_time": gt, "league": "KBO"}}
        mon.update(seen_match_ids={"P1"}, match_metadata=meta, poll_ts=_ts(0))
        mon.save()

        mon2 = _mon(tmp_path)
        mon2.load()
        state = mon2.get_state()
        assert "P1" in state
        assert state["P1"]["league"] == "KBO"
        assert state["P1"]["first_seen_timestamp"] == _ts(0)

    def test_save_preserves_classification(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"P2": {"game_time": gt}}
        mon.update(seen_match_ids={"P2"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        mon.save()

        mon2 = _mon(tmp_path)
        mon2.load()
        assert mon2.get_state()["P2"]["classification"] == CLASS_WITHDRAWAL_EARLY

    def test_empty_state_roundtrip(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        mon.save()
        mon2 = _mon(tmp_path)
        mon2.load()
        assert mon2.get_state() == {}

    def test_state_file_is_valid_json(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(4)
        meta = {"P3": {"game_time": gt}}
        mon.update(seen_match_ids={"P3"}, match_metadata=meta, poll_ts=_ts(0))
        mon.save()
        state_file = tmp_path / "state.json"
        parsed = json.loads(state_file.read_text())
        assert "P3" in parsed

    def test_load_handles_missing_file(self, tmp_path: Path) -> None:
        mon = TslMarketAvailabilityMonitor(state_path=tmp_path / "nonexistent.json")
        mon.load()  # should not raise
        assert mon.get_state() == {}


# ---------------------------------------------------------------------------
# 9. Context string
# ---------------------------------------------------------------------------


class TestContextString:
    def test_context_stored_on_first_disappearance(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"C1": {"game_time": gt}}
        mon.update(seen_match_ids={"C1"}, match_metadata=meta, poll_ts=_ts(0))
        ctx = "cycle_id=abc123 source=TSL_BLOB3RD status=200"
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1), context=ctx)
        assert mon.get_state()["C1"]["source_response_context"] == ctx

    def test_context_not_overwritten_on_subsequent_absence(self, tmp_path: Path) -> None:
        """source_response_context is frozen at first disappearance."""
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(8)
        meta = {"C2": {"game_time": gt}}
        mon.update(seen_match_ids={"C2"}, match_metadata=meta, poll_ts=_ts(0))
        ctx_first = "first_absence_context"
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1), context=ctx_first)
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(2), context="should_not_overwrite")
        assert mon.get_state()["C2"]["source_response_context"] == ctx_first

    def test_empty_context_default(self, tmp_path: Path) -> None:
        mon = _mon(tmp_path)
        mon.load()
        gt = _game_at(5)
        meta = {"C3": {"game_time": gt}}
        mon.update(seen_match_ids={"C3"}, match_metadata=meta, poll_ts=_ts(0))
        mon.update(seen_match_ids=set(), match_metadata=meta, poll_ts=_ts(1))
        assert mon.get_state()["C3"]["source_response_context"] == ""
