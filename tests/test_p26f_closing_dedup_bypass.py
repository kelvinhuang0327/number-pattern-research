"""
P26F — Tests for closing snapshot dedup bypass
paper_only=true / diagnostic_only=true

Validates that append_tsl_history() / save_tsl_snapshot() correctly:
1. Skips duplicate MNL odds in normal mode (force_closing=False)
2. Force-saves when force_closing=True, even if MNL odds unchanged
3. Audit fields are present on force-saved rows
4. Non-closing duplicate odds are still skipped (no inflation)
5. capture_live_odds() accepts force_closing parameter
6. force_closing=True path doesn't crash on missing context
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.tsl_snapshot import append_tsl_history, save_tsl_snapshot


# ── helpers ───────────────────────────────────────────────────────────────────

def _game(game_id: str, home_odds: str = "1.80", away_odds: str = "2.10") -> dict:
    """Minimal TSL game dict."""
    return {
        "gameId": game_id,
        "homeTeamName": "HomeTeam",
        "awayTeamName": "AwayTeam",
        "gameTime": "2026-05-21T18:00:00+08:00",
        "markets": [
            {
                "marketCode": "MNL",
                "outcomes": [
                    {"outcomeName": "HomeTeam", "odds": home_odds},
                    {"outcomeName": "AwayTeam", "odds": away_odds},
                ],
            }
        ],
    }


def _read_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ── Test 1: Non-closing duplicate MNL odds → dedup, not written ──────────────

class TestNonClosingDedup:
    def test_duplicate_odds_skipped_by_default(self, tmp_path, monkeypatch):
        """Normal mode: same MNL odds → skip second write."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-001", "1.80", "2.10")
        fetched = "2026-05-21T10:00:00Z"

        # First write → saved
        append_tsl_history(games=[game], source="TEST", fetched_at=fetched)
        rows_after_first = _read_history(hist)
        assert len(rows_after_first) == 1

        # Second write, same odds → dedup, NOT saved
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:15:00Z")
        rows_after_second = _read_history(hist)
        assert len(rows_after_second) == 1, (
            "Duplicate MNL odds must be deduped in normal mode"
        )

    def test_changed_odds_always_written(self, tmp_path, monkeypatch):
        """Normal mode: different MNL odds → always written."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game1 = _game("match-002", "1.80", "2.10")
        game2 = _game("match-002", "1.75", "2.15")  # odds changed

        append_tsl_history(games=[game1], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        append_tsl_history(games=[game2], source="TEST", fetched_at="2026-05-21T10:15:00Z")

        rows = _read_history(hist)
        assert len(rows) == 2, "Changed MNL odds must always be written"


# ── Test 2: Closing duplicate MNL odds + force_closing=True → force written ───

class TestForceClosingBypass:
    def test_force_closing_bypasses_dedup(self, tmp_path, monkeypatch):
        """force_closing=True: same MNL odds → still written (dedup bypassed)."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-003", "1.80", "2.10")

        # First write (normal)
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        assert len(_read_history(hist)) == 1

        # Second write, same odds, force_closing=True → MUST be written
        append_tsl_history(
            games=[game], source="TEST",
            fetched_at="2026-05-21T15:00:00Z",  # within ±2h of game
            force_closing=True,
        )
        rows = _read_history(hist)
        assert len(rows) == 2, (
            "force_closing=True must bypass dedup and write even with unchanged odds"
        )

    def test_force_closing_without_prior_snapshot(self, tmp_path, monkeypatch):
        """force_closing=True on first write: no dedup key yet → written normally."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-004")
        append_tsl_history(
            games=[game], source="TEST", fetched_at="2026-05-21T15:00:00Z",
            force_closing=True,
        )
        assert len(_read_history(hist)) == 1


# ── Test 3: Audit fields present on force-saved rows ──────────────────────────

class TestAuditFields:
    def test_force_closing_row_has_audit_fields(self, tmp_path, monkeypatch):
        """Row written with force_closing=True must carry audit fields."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-005")

        # First normal write (no audit fields)
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        first_row = _read_history(hist)[0]
        assert "force_closing_snapshot" not in first_row

        # Second write, same odds, force_closing=True
        append_tsl_history(
            games=[game], source="TEST", fetched_at="2026-05-21T15:00:00Z",
            force_closing=True,
        )
        rows = _read_history(hist)
        assert len(rows) == 2
        forced_row = rows[1]
        assert forced_row.get("force_closing_snapshot") is True
        assert forced_row.get("capture_reason") == "closing_window"
        assert "dedup_bypassed" in forced_row

    def test_dedup_bypassed_flag_is_true_when_odds_unchanged(self, tmp_path, monkeypatch):
        """dedup_bypassed=True when odds were unchanged (force truly bypassed dedup)."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-006", "1.90", "2.00")
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        append_tsl_history(
            games=[game], source="TEST", fetched_at="2026-05-21T15:00:00Z",
            force_closing=True,
        )
        rows = _read_history(hist)
        forced = rows[1]
        assert forced["dedup_bypassed"] is True, (
            "dedup_bypassed must be True when odds were unchanged and force_closing overrode it"
        )

    def test_normal_row_has_no_audit_fields(self, tmp_path, monkeypatch):
        """Normal (non-force) rows must NOT have force_closing audit fields."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-007")
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        row = _read_history(hist)[0]
        assert "force_closing_snapshot" not in row
        assert "capture_reason" not in row


# ── Test 4: save_tsl_snapshot passes force_closing ────────────────────────────

class TestSaveTslSnapshotForceClosing:
    def test_save_tsl_snapshot_force_closing_writes_duplicate(self, tmp_path, monkeypatch):
        """save_tsl_snapshot(force_closing=True) writes duplicate odds."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        snap = tmp_path / "tsl_odds_snapshot.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)
        monkeypatch.setattr("data.tsl_snapshot.TSL_SNAPSHOT_PATH", snap)

        game = _game("match-008")
        save_tsl_snapshot(games=[game], source="TEST")
        assert len(_read_history(hist)) == 1

        save_tsl_snapshot(games=[game], source="TEST", force_closing=True)
        rows = _read_history(hist)
        assert len(rows) == 2, "save_tsl_snapshot(force_closing=True) must bypass dedup"
        assert rows[1].get("force_closing_snapshot") is True


# ── Test 5: capture_live_odds accepts force_closing ───────────────────────────

class TestCaptureLiveOddsForceClosing:
    def test_capture_live_odds_has_force_closing_param(self):
        """capture_live_odds() must accept force_closing kwarg."""
        import inspect
        from wbc_backend.mlb_data.live_odds_collector import capture_live_odds
        sig = inspect.signature(capture_live_odds)
        assert "force_closing" in sig.parameters, (
            "capture_live_odds() must have force_closing parameter"
        )

    def test_capture_live_odds_force_closing_default_false(self):
        """force_closing defaults to False (no breaking change)."""
        import inspect
        from wbc_backend.mlb_data.live_odds_collector import capture_live_odds
        sig = inspect.signature(capture_live_odds)
        assert sig.parameters["force_closing"].default is False


# ── Test 6: force_closing=False in non-closing capture ────────────────────────

class TestNoForceInNonClosing:
    def test_normal_duplicate_still_deduped_when_force_false(self, tmp_path, monkeypatch):
        """force_closing=False (default): dedup still applies."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game = _game("match-009")
        append_tsl_history(games=[game], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        append_tsl_history(
            games=[game], source="TEST", fetched_at="2026-05-21T10:15:00Z",
            force_closing=False,  # explicit False — dedup applies
        )
        assert len(_read_history(hist)) == 1


# ── Test 7: Missing context doesn't crash ─────────────────────────────────────

class TestMissingContextNoCrash:
    def test_empty_games_list_no_crash(self, tmp_path, monkeypatch):
        """Empty games list must not crash with force_closing=True."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)
        # Must not raise
        append_tsl_history(games=[], source="TEST", fetched_at="2026-05-21T15:00:00Z", force_closing=True)
        assert not hist.exists() or len(_read_history(hist)) == 0

    def test_game_without_mnl_always_written(self, tmp_path, monkeypatch):
        """Games without MNL market always written (original behavior unchanged)."""
        hist = tmp_path / "tsl_odds_history.jsonl"
        dedup = tmp_path / "tsl_dedup_state.json"
        monkeypatch.setattr("data.tsl_snapshot.TSL_HISTORY_PATH", hist)
        monkeypatch.setattr("data.tsl_snapshot._DEDUP_STATE_PATH", dedup)

        game_no_mnl = {
            "gameId": "match-010",
            "homeTeamName": "Home", "awayTeamName": "Away",
            "gameTime": "2026-05-21T18:00:00+08:00",
            "markets": [{"marketCode": "OU", "outcomes": []}],
        }
        append_tsl_history(games=[game_no_mnl], source="TEST", fetched_at="2026-05-21T10:00:00Z")
        append_tsl_history(games=[game_no_mnl], source="TEST", fetched_at="2026-05-21T10:15:00Z")
        rows = _read_history(hist)
        # Games without MNL have no odds_key → always appended
        assert len(rows) == 2, "Games without MNL market must always be written (no dedup key)"


# ── Test 8: Scheduler wires force_closing from windows ────────────────────────

class TestSchedulerWiresForceClosing:
    def test_run_scheduled_capture_passes_force_closing_true_when_closing(
        self, tmp_path, monkeypatch
    ):
        """run_scheduled_capture() must pass force_closing=True to capture_live_odds when closing=True."""
        import wbc_backend.mlb_data.odds_capture_scheduler as sched

        captured_kwargs: dict = {}

        def mock_capture(**kwargs):
            captured_kwargs.update(kwargs)
            return {"snapshots_received": 0, "games_updated": 0, "snapshots_added": 0}

        def mock_windows(_=None, **__):
            return {"continuous": True, "decision": False, "pregame": False, "closing": True, "_wbc_npb_audit": []}

        schedule_path = tmp_path / "odds_capture_schedule.json"
        tl_path = tmp_path / "odds_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        monkeypatch.setattr(sched, "SCHEDULE_PATH", schedule_path)
        monkeypatch.setattr(sched, "determine_capture_windows", mock_windows)
        # Patch capture_live_odds on the scheduler module's namespace (not collector)
        monkeypatch.setattr(sched, "capture_live_odds", mock_capture)

        sched.run_scheduled_capture(force=True)

        assert "force_closing" in captured_kwargs, "run_scheduled_capture must pass force_closing to capture_live_odds"
        assert captured_kwargs["force_closing"] is True, f"Expected force_closing=True, got {captured_kwargs['force_closing']}"

    def test_run_scheduled_capture_passes_force_closing_false_when_not_closing(
        self, tmp_path, monkeypatch
    ):
        """run_scheduled_capture() passes force_closing=False when closing=False."""
        import wbc_backend.mlb_data.odds_capture_scheduler as sched

        captured_kwargs: dict = {}

        def mock_capture(**kwargs):
            captured_kwargs.update(kwargs)
            return {"snapshots_received": 0, "games_updated": 0, "snapshots_added": 0}

        def mock_windows(_=None, **__):
            return {"continuous": True, "decision": False, "pregame": False, "closing": False, "_wbc_npb_audit": []}

        schedule_path = tmp_path / "odds_capture_schedule.json"
        tl_path = tmp_path / "odds_timeline.jsonl"
        tl_path.write_text("", encoding="utf-8")
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        monkeypatch.setattr(sched, "SCHEDULE_PATH", schedule_path)
        monkeypatch.setattr(sched, "determine_capture_windows", mock_windows)
        monkeypatch.setattr(sched, "capture_live_odds", mock_capture)

        sched.run_scheduled_capture(force=True)

        assert captured_kwargs.get("force_closing") is False, (
            f"Expected force_closing=False, got {captured_kwargs.get('force_closing')}"
        )
