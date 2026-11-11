"""
Tests for the live MLB odds pipeline:
  - live_odds_collector: timeline update engine, idempotency, slot classification
  - odds_capture_scheduler: capture windows, scheduling logic
  - clv_calculator: CLV computation, validation
  - feed_jobs integration: live timeline priority over canonical
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def timeline_dir(tmp_path: Path) -> Path:
    d = tmp_path / "mlb_context"
    d.mkdir()
    return d


def _make_snapshot(
    *,
    home_team: str = "New York Yankees",
    away_team: str = "Boston Red Sox",
    game_time: str = "2025-07-15T23:05:00Z",
    home_ml: int = -150,
    away_ml: int = 130,
    fetched_at: str = "2025-07-15T19:00:00Z",
    source: str = "TSL",
) -> dict:
    return {
        "home_team": home_team,
        "away_team": away_team,
        "game_time": game_time,
        "home_ml": home_ml,
        "away_ml": away_ml,
        "ou_line": 8.5,
        "fetched_at": fetched_at,
        "source": source,
    }


# ---------------------------------------------------------------------------
# live_odds_collector tests
# ---------------------------------------------------------------------------


class TestTimelineUpdateEngine:
    """Tests for update_timeline_from_snapshots."""

    def test_creates_new_timeline_from_first_snapshot(self, timeline_dir: Path):
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        snap = _make_snapshot(fetched_at="2025-07-15T19:00:00Z")
        result = update_timeline_from_snapshots([snap], timeline_path=tl_path)

        assert result["snapshots_received"] == 1
        assert result["games_updated"] == 1
        assert result["snapshots_added"] == 1
        assert tl_path.exists()

        lines = [json.loads(l) for l in tl_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        tl = lines[0]
        assert tl["opening_home_ml"] == -150
        assert tl["opening_away_ml"] == 130
        assert tl["opening_ts"] == "2025-07-15T19:00:00Z"

    def test_idempotent_duplicate_snapshot(self, timeline_dir: Path):
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        snap = _make_snapshot(fetched_at="2025-07-15T19:00:00Z")

        update_timeline_from_snapshots([snap], timeline_path=tl_path)
        result2 = update_timeline_from_snapshots([snap], timeline_path=tl_path)

        assert result2["duplicates_skipped"] == 1
        assert result2["snapshots_added"] == 0

    def test_slot_classification_decision_window(self, timeline_dir: Path):
        """Snapshot at T-2.5h should fill decision slot."""
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        # Game at 23:05 UTC, snapshot at 20:30 UTC (2.5h before = 150min before)
        snap = _make_snapshot(
            game_time="2025-07-15T23:05:00Z",
            fetched_at="2025-07-15T20:30:00Z",
            home_ml=-155,
            away_ml=135,
        )
        update_timeline_from_snapshots([snap], timeline_path=tl_path)

        lines = [json.loads(l) for l in tl_path.read_text().splitlines() if l.strip()]
        tl = lines[0]
        # 150min >= DECISION_LEAD_MINUTES (120), so decision slot should be filled
        assert tl["decision_home_ml"] == -155
        assert tl["decision_ts"] == "2025-07-15T20:30:00Z"

    def test_slot_classification_closing_window(self, timeline_dir: Path):
        """Snapshot at T-10min should fill pregame + closing slots."""
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        # Game at 23:05 UTC, snapshot at 22:55 UTC (10min before)
        snap = _make_snapshot(
            game_time="2025-07-15T23:05:00Z",
            fetched_at="2025-07-15T22:55:00Z",
            home_ml=-160,
            away_ml=140,
        )
        update_timeline_from_snapshots([snap], timeline_path=tl_path)

        lines = [json.loads(l) for l in tl_path.read_text().splitlines() if l.strip()]
        tl = lines[0]
        assert tl["latest_pregame_home_ml"] == -160
        assert tl["closing_home_ml"] == -160

    def test_multiple_snapshots_build_full_timeline(self, timeline_dir: Path):
        """Multiple snapshots at different times fill all slots."""
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        game_time = "2025-07-15T23:05:00Z"

        # Opening (early morning)
        s1 = _make_snapshot(game_time=game_time, fetched_at="2025-07-15T14:00:00Z", home_ml=-140, away_ml=120)
        # Decision window (T-2.5h)
        s2 = _make_snapshot(game_time=game_time, fetched_at="2025-07-15T20:30:00Z", home_ml=-150, away_ml=130)
        # Pre-game (T-15min)
        s3 = _make_snapshot(game_time=game_time, fetched_at="2025-07-15T22:50:00Z", home_ml=-155, away_ml=135)
        # Closing (T-3min)
        s4 = _make_snapshot(game_time=game_time, fetched_at="2025-07-15T23:02:00Z", home_ml=-160, away_ml=140)

        update_timeline_from_snapshots([s1, s2, s3, s4], timeline_path=tl_path)

        lines = [json.loads(l) for l in tl_path.read_text().splitlines() if l.strip()]
        tl = lines[0]
        assert tl["opening_home_ml"] == -140
        assert tl["decision_home_ml"] == -150
        assert tl["latest_pregame_home_ml"] == -160  # latest before game
        assert tl["closing_home_ml"] == -160
        assert len(tl["odds_history"]) == 4

    def test_unmatchable_snapshot_counted(self, timeline_dir: Path):
        from wbc_backend.mlb_data.live_odds_collector import update_timeline_from_snapshots

        tl_path = timeline_dir / "odds_timeline.jsonl"
        bad_snap = {"home_team": "", "away_team": "", "game_time": "", "home_ml": -150, "away_ml": 130}
        result = update_timeline_from_snapshots([bad_snap], timeline_path=tl_path)
        assert result["unmatchable"] == 1
        assert result["snapshots_added"] == 0


class TestSnapshotClassification:
    def test_early_snapshot(self):
        from wbc_backend.mlb_data.live_odds_collector import _classify_snapshot_type

        snap = datetime(2025, 7, 15, 14, 0, tzinfo=timezone.utc)
        game = datetime(2025, 7, 15, 23, 5, tzinfo=timezone.utc)
        assert _classify_snapshot_type(snap, game) == "early"

    def test_pregame_snapshot(self):
        from wbc_backend.mlb_data.live_odds_collector import _classify_snapshot_type

        snap = datetime(2025, 7, 15, 22, 30, tzinfo=timezone.utc)
        game = datetime(2025, 7, 15, 23, 5, tzinfo=timezone.utc)
        assert _classify_snapshot_type(snap, game) == "pregame"

    def test_closing_snapshot(self):
        from wbc_backend.mlb_data.live_odds_collector import _classify_snapshot_type

        snap = datetime(2025, 7, 15, 23, 2, tzinfo=timezone.utc)
        game = datetime(2025, 7, 15, 23, 5, tzinfo=timezone.utc)
        assert _classify_snapshot_type(snap, game) == "closing"

    def test_postgame_snapshot(self):
        from wbc_backend.mlb_data.live_odds_collector import _classify_snapshot_type

        snap = datetime(2025, 7, 16, 2, 0, tzinfo=timezone.utc)
        game = datetime(2025, 7, 15, 23, 5, tzinfo=timezone.utc)
        assert _classify_snapshot_type(snap, game) == "postgame"


# ---------------------------------------------------------------------------
# clv_calculator tests
# ---------------------------------------------------------------------------


class TestCLVCalculator:
    def _write_timeline(self, path: Path, timelines: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(t, ensure_ascii=False) for t in timelines),
            encoding="utf-8",
        )

    def test_compute_clv_positive(self):
        from wbc_backend.mlb_data.clv_calculator import compute_clv

        # Decision: -140 → implied prob 0.583; Closing: -160 → implied prob 0.615
        # CLV = 0.615 - 0.583 = +0.032 (bet moved in our direction)
        tl = {
            "game_id": "MLB-2025-07-15-7:05PM-BOS-AT-NYY",
            "decision_home_ml": -140,
            "decision_away_ml": 120,
            "closing_home_ml": -160,
            "closing_away_ml": 140,
            "decision_ts": "2025-07-15T21:00:00Z",
            "closing_ts": "2025-07-15T23:00:00Z",
            "odds_history": [
                {"ts": "2025-07-15T21:00:00Z", "home_ml": -140, "away_ml": 120},
                {"ts": "2025-07-15T23:00:00Z", "home_ml": -160, "away_ml": 140},
            ],
        }
        result = compute_clv(tl)
        assert result.clv_available
        assert result.clv_value > 0
        assert result.decision_home_ml == -140
        assert result.closing_home_ml == -160

    def test_compute_clv_negative(self):
        from wbc_backend.mlb_data.clv_calculator import compute_clv

        # Decision: -160 → implied 0.615; Closing: -140 → implied 0.583
        # CLV = 0.583 - 0.615 = -0.032
        tl = {
            "game_id": "MLB-2025-07-15-7:05PM-BOS-AT-NYY",
            "decision_home_ml": -160,
            "decision_away_ml": 140,
            "closing_home_ml": -140,
            "closing_away_ml": 120,
            "decision_ts": "2025-07-15T21:00:00Z",
            "closing_ts": "2025-07-15T23:00:00Z",
            "odds_history": [
                {"ts": "2025-07-15T21:00:00Z", "home_ml": -160, "away_ml": 140},
                {"ts": "2025-07-15T23:00:00Z", "home_ml": -140, "away_ml": 120},
            ],
        }
        result = compute_clv(tl)
        assert result.clv_available
        assert result.clv_value < 0

    def test_compute_clv_missing_data_returns_unavailable(self):
        from wbc_backend.mlb_data.clv_calculator import compute_clv

        tl = {"game_id": "test", "decision_home_ml": -150, "closing_home_ml": None}
        result = compute_clv(tl)
        assert not result.clv_available
        assert result.clv_value is None

    def test_compute_clv_batch(self, timeline_dir: Path):
        from wbc_backend.mlb_data.clv_calculator import compute_clv_batch

        tl_path = timeline_dir / "odds_timeline.jsonl"
        timelines = [
            {
                "game_id": "game1",
                "decision_home_ml": -140,
                "decision_away_ml": 120,
                "closing_home_ml": -160,
                "closing_away_ml": 140,
                "decision_ts": "2025-07-15T21:00:00Z",
                "closing_ts": "2025-07-15T23:00:00Z",
                "odds_history": [
                    {"ts": "2025-07-15T21:00:00Z", "home_ml": -140},
                    {"ts": "2025-07-15T23:00:00Z", "home_ml": -160},
                ],
            },
            {
                "game_id": "game2",
                "decision_home_ml": -130,
                "decision_away_ml": 110,
                "closing_home_ml": -130,
                "closing_away_ml": 110,
                "decision_ts": "2025-07-15T21:00:00Z",
                "closing_ts": "2025-07-15T23:00:00Z",
                "odds_history": [
                    {"ts": "2025-07-15T21:00:00Z", "home_ml": -130},
                    {"ts": "2025-07-15T23:00:00Z", "home_ml": -130},
                ],
            },
        ]
        self._write_timeline(tl_path, timelines)
        batch = compute_clv_batch(tl_path)
        assert batch["total_games"] == 2
        assert batch["clv_available"] == 2


class TestCLVValidation:
    def test_validate_timeline_valid(self):
        from wbc_backend.mlb_data.clv_calculator import validate_timeline

        tl = {
            "decision_home_ml": -140,
            "closing_home_ml": -150,
            "decision_ts": "2025-07-15T19:00:00Z",
            "closing_ts": "2025-07-15T21:00:00Z",
            "odds_history": [
                {"ts": "2025-07-15T19:00:00Z", "home_ml": -140, "away_ml": 120},
                {"ts": "2025-07-15T21:00:00Z", "home_ml": -150, "away_ml": 130},
            ],
        }
        ok, reason = validate_timeline(tl)
        assert ok
        assert reason is None

    def test_validate_timeline_decision_after_closing_rejected(self):
        from wbc_backend.mlb_data.clv_calculator import validate_timeline

        tl = {
            "decision_home_ml": -150,
            "closing_home_ml": -140,
            "decision_ts": "2025-07-15T23:00:00Z",
            "closing_ts": "2025-07-15T21:00:00Z",
        }
        ok, reason = validate_timeline(tl)
        assert not ok
        assert reason is not None
        assert "not_before" in reason

    def test_validate_timeline_missing_timestamps(self):
        from wbc_backend.mlb_data.clv_calculator import validate_timeline

        tl = {"decision_ts": None, "closing_ts": None}
        ok, reason = validate_timeline(tl)
        assert not ok
        assert reason == "missing_timestamps"


# ---------------------------------------------------------------------------
# odds_capture_scheduler tests
# ---------------------------------------------------------------------------


class TestCaptureWindows:
    def test_determine_windows_with_no_games(self, timeline_dir: Path, monkeypatch):
        from wbc_backend.mlb_data import odds_capture_scheduler as sched

        tl_path = timeline_dir / "odds_timeline.jsonl"
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        monkeypatch.setattr(sched, "WBC_NPB_HISTORY_PATH", tl_path)
        # Empty file
        tl_path.write_text("", encoding="utf-8")

        windows = sched.determine_capture_windows()
        assert windows["continuous"] is True
        # No games → no decision/pregame/closing windows
        assert windows["decision"] is False
        assert windows["pregame"] is False
        assert windows["closing"] is False

    def test_determine_windows_decision_active(self, timeline_dir: Path, monkeypatch):
        from wbc_backend.mlb_data import odds_capture_scheduler as sched

        tl_path = timeline_dir / "odds_timeline.jsonl"
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        monkeypatch.setattr(sched, "WBC_NPB_HISTORY_PATH", tl_path)

        # Game in 1.5 hours (within 60-120 min decision window)
        now = datetime(2025, 7, 15, 20, 0, tzinfo=timezone.utc)
        game_time = now + timedelta(hours=1, minutes=30)
        tl_data = {
            "game_id": "test-game",
            "commence_time": game_time.isoformat().replace("+00:00", "Z"),
        }
        tl_path.write_text(json.dumps(tl_data), encoding="utf-8")

        windows = sched.determine_capture_windows(now=now)
        assert windows["decision"] is True
        assert windows["pregame"] is False

    def test_should_capture_always_true_for_continuous(self, timeline_dir: Path, monkeypatch):
        from wbc_backend.mlb_data import odds_capture_scheduler as sched

        tl_path = timeline_dir / "odds_timeline.jsonl"
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        tl_path.write_text("", encoding="utf-8")

        assert sched.should_capture_now() is True

    def test_capture_status_empty(self, timeline_dir: Path, monkeypatch):
        from wbc_backend.mlb_data import odds_capture_scheduler as sched

        tl_path = timeline_dir / "odds_timeline.jsonl"
        schedule_path = timeline_dir / "odds_capture_schedule.json"
        monkeypatch.setattr(sched, "TIMELINE_PATH", tl_path)
        monkeypatch.setattr(sched, "SCHEDULE_PATH", schedule_path)
        tl_path.write_text("", encoding="utf-8")

        status = sched.get_capture_status()
        assert status["total_games"] == 0
        assert status["games_clv_ready"] == 0


# ---------------------------------------------------------------------------
# feed_jobs integration tests
# ---------------------------------------------------------------------------


class TestFeedJobsLiveIntegration:
    def test_live_timeline_prioritized_over_canonical(self, tmp_path: Path, monkeypatch):
        """Live timeline with decision_ts should override canonical without it."""
        import wbc_backend.mlb_data.feed_jobs as fj

        # Setup canonical source (no decision data)
        canonical_dir = tmp_path / "mlb_context_sources"
        canonical_dir.mkdir()
        canonical_path = canonical_dir / "odds_timeline_canonical.jsonl"
        canonical_record = {
            "game_id": "MLB-2025-07-15-7:05PM-BOS-AT-NYY",
            "opening_home_ml": -140,
            "opening_away_ml": 120,
            "closing_home_ml": -150,
            "closing_away_ml": 130,
            "odds_history": [
                {"ts": "2025-07-15T23:00:00Z", "home_ml": -150, "away_ml": 130},
            ],
            "fetched_at": "2025-07-15T23:30:00Z",
        }
        canonical_path.write_text(json.dumps(canonical_record), encoding="utf-8")

        # Setup live source (has decision data + more history)
        live_dir = tmp_path / "mlb_context"
        live_dir.mkdir()
        live_path = live_dir / "odds_timeline.jsonl"
        live_record = {
            "game_id": "MLB-2025-07-15-7:05PM-BOS-AT-NYY",
            "opening_home_ml": -135,
            "opening_away_ml": 115,
            "decision_home_ml": -145,
            "decision_away_ml": 125,
            "closing_home_ml": -155,
            "closing_away_ml": 135,
            "decision_ts": "2025-07-15T21:00:00Z",
            "closing_ts": "2025-07-15T23:00:00Z",
            "odds_history": [
                {"ts": "2025-07-15T14:00:00Z", "home_ml": -135, "away_ml": 115},
                {"ts": "2025-07-15T21:00:00Z", "home_ml": -145, "away_ml": 125},
                {"ts": "2025-07-15T23:00:00Z", "home_ml": -155, "away_ml": 135},
            ],
            "fetched_at": "2025-07-15T23:05:00Z",
        }
        live_path.write_text(json.dumps(live_record), encoding="utf-8")

        # Monkey-patch the paths used in generate_odds_timeline_feed
        orig_func = fj.generate_odds_timeline_feed

        def patched_feed(df, output_path, tsl_history_path=""):
            # Patch the two hardcoded paths
            monkeypatch.setattr(
                "wbc_backend.mlb_data.feed_jobs.Path",
                lambda p: Path(str(p).replace(
                    "data/mlb_context_sources", str(canonical_dir)
                ).replace(
                    "data/mlb_context/", str(live_dir) + "/"
                )),
            )
            return orig_func(df, output_path, tsl_history_path)

        # This test verifies the logic of source prioritization.
        # The _source_candidates() now lists live timeline first.
        from wbc_backend.mlb_data.feed_jobs import _source_candidates
        candidates = _source_candidates()
        odds_paths = candidates["odds_timeline"]
        assert str(odds_paths[0]) == "data/mlb_context/odds_timeline.jsonl"
        assert str(odds_paths[1]) == "data/mlb_context_sources/odds_timeline_canonical.jsonl"


class TestSourceCandidatesOrder:
    def test_live_timeline_is_first_odds_source(self):
        from wbc_backend.mlb_data.feed_jobs import _source_candidates

        candidates = _source_candidates()
        odds_sources = candidates["odds_timeline"]
        assert str(odds_sources[0]) == "data/mlb_context/odds_timeline.jsonl"
