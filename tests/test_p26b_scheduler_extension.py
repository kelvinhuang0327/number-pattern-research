"""
P26B — Tests for WBC/NPB scheduler extension
paper_only=true / diagnostic_only=true

Validates that determine_capture_windows() correctly triggers
closing/pregame/decision windows for WBC/NPB games from
tsl_odds_history.jsonl, while preserving all MLB window logic.

10 required test cases:
1.  MLB existing behavior preserved (no WBC file)
2.  WBC game at T-90min triggers decision window
3.  WBC game at T-30min triggers pregame window
4.  WBC game at T-5min triggers closing window
5.  WBC game at T+30min still triggers closing window (within -120min)
6.  WBC game at T+3h does NOT trigger (started >120min ago)
7.  Missing tsl_odds_history.jsonl → no crash, no WBC windows
8.  NPB game uses identical logic to WBC
9.  MLB window unaffected when WBC game is also present
10. _wbc_npb_audit entry exists for each WBC trigger
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import wbc_backend.mlb_data.odds_capture_scheduler as sched


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_tsl_record(
    match_id: str,
    game_time: datetime,
    home: str = "HomeTeam",
    away: str = "AwayTeam",
    fetched_offset_h: float = -6.0,
) -> dict:
    """Build a minimal tsl_odds_history row."""
    fetched_at = game_time + timedelta(hours=fetched_offset_h)
    return {
        "match_id": match_id,
        "game_time": game_time.isoformat().replace("+00:00", "Z"),
        "home_team_name": home,
        "away_team_name": away,
        "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "markets": [],
        "source": "TSL_TEST",
    }


def _write_tsl_history(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "tsl_odds_history.jsonl"
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return p


def _make_mlb_timeline(tmp_path: Path, game_time: datetime) -> Path:
    """Write a minimal odds_timeline.jsonl with one MLB game."""
    tl_path = tmp_path / "odds_timeline.jsonl"
    tl_path.write_text(
        json.dumps({
            "game_id": "mlb-test-001",
            "commence_time": game_time.isoformat().replace("+00:00", "Z"),
        }),
        encoding="utf-8",
    )
    return tl_path


# ── Test 1: MLB existing behavior preserved ────────────────────────────────────

class TestMLBBackwardCompatibility:
    def test_mlb_windows_unchanged_with_no_wbc_file(self, tmp_path, monkeypatch):
        """MLB window logic must work identically when no WBC file is present."""
        # MLB game in 90min → decision window (60-120min)
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=90)
        tl_path = _make_mlb_timeline(tmp_path, game_time)
        nonexistent = tmp_path / "nonexistent.jsonl"

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=nonexistent)

        assert windows["continuous"] is True
        assert windows["decision"] is True    # MLB game at T-90min triggers decision
        assert windows["pregame"] is False
        assert windows["closing"] is False
        assert windows["_wbc_npb_audit"] == []

    def test_mlb_closing_window_still_fires(self, tmp_path, monkeypatch):
        """MLB closing window (T-5min) must still work after P26B extension."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=3)  # 3min to game start
        tl_path = _make_mlb_timeline(tmp_path, game_time)
        nonexistent = tmp_path / "nonexistent.jsonl"

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=nonexistent)
        assert windows["closing"] is True


# ── Test 2: WBC game at T-90min triggers decision ──────────────────────────────

class TestWBCDecisionWindow:
    def test_wbc_game_at_t_minus_90min_triggers_decision(self, tmp_path, monkeypatch):
        """WBC game 90 min away → decision=True."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=90)
        record = _make_tsl_record("wbc-001", game_time, home="台灣", away="日本")
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["decision"] is True, f"Expected decision=True, got {windows}"
        assert "decision" in windows["_wbc_npb_audit"][0]["trigger_types"]


# ── Test 3: WBC game at T-30min triggers pregame ───────────────────────────────

class TestWBCPregameWindow:
    def test_wbc_game_at_t_minus_30min_triggers_pregame(self, tmp_path, monkeypatch):
        """WBC game 30 min away → pregame=True."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=30)
        record = _make_tsl_record("wbc-002", game_time)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["pregame"] is True
        assert "pregame" in windows["_wbc_npb_audit"][0]["trigger_types"]

    def test_wbc_game_at_t_minus_10min_triggers_pregame_and_closing(
        self, tmp_path, monkeypatch
    ):
        """WBC game 10 min away → both pregame and closing."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=10)
        record = _make_tsl_record("wbc-003", game_time)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)
        triggers = windows["_wbc_npb_audit"][0]["trigger_types"]
        assert windows["pregame"] is True
        assert windows["closing"] is True
        assert "pregame" in triggers
        assert "closing" in triggers


# ── Test 4: WBC game at T-5min triggers closing ────────────────────────────────

class TestWBCClosingWindow:
    def test_wbc_game_at_t_minus_5min_triggers_closing(self, tmp_path, monkeypatch):
        """WBC game 5 min away → closing=True."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=5)
        record = _make_tsl_record("wbc-004", game_time)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["closing"] is True


# ── Test 5: WBC game at T+30min still triggers closing ─────────────────────────

class TestWBCPostGameClosing:
    def test_wbc_game_started_30min_ago_still_triggers_closing(
        self, tmp_path, monkeypatch
    ):
        """WBC game started 30 min ago → closing still active (within ±120min)."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now - timedelta(minutes=30)   # game started 30 min ago
        record = _make_tsl_record("wbc-005", game_time, fetched_offset_h=-8.0)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["closing"] is True, (
            "Game started 30min ago must still trigger closing (within ±120min window)"
        )


# ── Test 6: WBC game at T+3h does NOT trigger ──────────────────────────────────

class TestWBCOldGame:
    def test_wbc_game_started_3h_ago_no_trigger(self, tmp_path, monkeypatch):
        """WBC game started >120min ago → no windows triggered."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now - timedelta(hours=3)   # started 3h ago → delta = -180min
        record = _make_tsl_record("wbc-006", game_time, fetched_offset_h=-10.0)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["decision"] is False
        assert windows["pregame"] is False
        assert windows["closing"] is False
        assert windows["_wbc_npb_audit"] == [], (
            "Game started >120min ago must not appear in audit"
        )


# ── Test 7: Missing source file → no crash ─────────────────────────────────────

class TestMissingSourceFile:
    def test_missing_wbc_file_no_crash(self, tmp_path, monkeypatch):
        """If tsl_odds_history.jsonl is missing, scheduler must not crash."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        nonexistent = tmp_path / "does_not_exist.jsonl"
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        # Must not raise
        windows = sched.determine_capture_windows(now=now, wbc_npb_source=nonexistent)

        assert windows["continuous"] is True
        assert windows["_wbc_npb_audit"] == []

    def test_load_wbc_game_times_returns_empty_on_missing_file(self, tmp_path):
        """_load_wbc_npb_game_times() must return [] if file does not exist."""
        result = sched._load_wbc_npb_game_times(
            source_path=tmp_path / "nonexistent.jsonl"
        )
        assert result == []

    def test_load_wbc_game_times_returns_empty_on_empty_file(self, tmp_path):
        """_load_wbc_npb_game_times() must return [] for an empty file."""
        p = tmp_path / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        result = sched._load_wbc_npb_game_times(source_path=p)
        assert result == []


# ── Test 8: NPB game uses identical logic ──────────────────────────────────────

class TestNPBGame:
    def test_npb_game_triggers_same_as_wbc(self, tmp_path, monkeypatch):
        """NPB game (same jsonl structure) triggers windows identically to WBC."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=20)
        # NPB teams (Japanese names)
        record = _make_tsl_record(
            "npb-001", game_time, home="羅德海洋", away="西武獅"
        )
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert windows["pregame"] is True
        assert windows["closing"] is True
        assert len(windows["_wbc_npb_audit"]) == 1
        assert windows["_wbc_npb_audit"][0]["home_team"] == "羅德海洋"


# ── Test 9: MLB window unaffected when WBC game present ───────────────────────

class TestMLBAndWBCCoexist:
    def test_mlb_and_wbc_both_contribute_independently(self, tmp_path, monkeypatch):
        """MLB game at T-90min and WBC game at T-5min → both trigger correctly."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        mlb_game_time = now + timedelta(minutes=90)   # MLB → decision
        wbc_game_time = now + timedelta(minutes=5)    # WBC → closing + pregame

        tl_path = _make_mlb_timeline(tmp_path, mlb_game_time)
        record = _make_tsl_record("wbc-009", wbc_game_time)
        tsl_path = _write_tsl_history(tmp_path, [record])

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        # MLB contributes decision
        assert windows["decision"] is True
        # WBC contributes closing + pregame
        assert windows["pregame"] is True
        assert windows["closing"] is True
        # Audit has exactly the WBC entry
        assert len(windows["_wbc_npb_audit"]) == 1
        assert windows["_wbc_npb_audit"][0]["match_id"] == "wbc-009"

    def test_mlb_closing_not_broken_by_wbc_source(self, tmp_path, monkeypatch):
        """MLB closing window (T-3min) works normally regardless of WBC data."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        mlb_game_time = now + timedelta(minutes=3)
        tl_path = _make_mlb_timeline(tmp_path, mlb_game_time)
        nonexistent = tmp_path / "no_wbc.jsonl"

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=nonexistent)

        assert windows["closing"] is True


# ── Test 10: _wbc_npb_audit entry populated on trigger ─────────────────────────

class TestAuditEntry:
    def test_audit_entry_fields_present(self, tmp_path, monkeypatch):
        """Each WBC trigger must produce a complete audit entry."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(minutes=20)
        record = _make_tsl_record(
            "wbc-010", game_time, home="台灣隊", away="美國隊"
        )
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        assert len(windows["_wbc_npb_audit"]) >= 1
        entry = windows["_wbc_npb_audit"][0]

        assert "match_id" in entry
        assert "home_team" in entry
        assert "away_team" in entry
        assert "game_time_utc" in entry
        assert "minutes_to_game" in entry
        assert "trigger_types" in entry
        assert "source" in entry
        assert "trigger_reason" in entry
        assert len(entry["trigger_types"]) > 0
        assert entry["match_id"] == "wbc-010"

    def test_no_audit_entry_for_non_triggered_game(self, tmp_path, monkeypatch):
        """Game too far in the future (e.g., 5h away) must NOT produce audit entry."""
        now = datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(hours=5)  # 300min away — only in lookahead, no trigger
        record = _make_tsl_record("wbc-011", game_time)
        tsl_path = _write_tsl_history(tmp_path, [record])
        tl_path = tmp_path / "empty_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")

        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)

        windows = sched.determine_capture_windows(now=now, wbc_npb_source=tsl_path)

        # No windows triggered, no audit entries
        assert windows["decision"] is False
        assert windows["pregame"] is False
        assert windows["closing"] is False
        assert windows["_wbc_npb_audit"] == []
