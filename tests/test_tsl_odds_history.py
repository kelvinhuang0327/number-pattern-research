from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_game(*, home_odds: float, away_odds: float) -> list[dict]:
    return [
        {
            "gameId": 9001,
            "homeTeamName": "日本",
            "awayTeamName": "中華台北",
            "gameTime": "2026-03-07T19:00:00",
            "markets": [
                {
                    "marketCode": "MNL",
                    "outcomes": [
                        {"outcomeName": "日本", "odds": f"{home_odds:.2f}"},
                        {"outcomeName": "中華台北", "odds": f"{away_odds:.2f}"},
                    ],
                }
            ],
        }
    ]


def test_save_snapshot_appends_history_and_builds_market_timeline(tmp_path, monkeypatch):
    import data.tsl_snapshot as tsl_snapshot

    monkeypatch.setattr(tsl_snapshot, "TSL_SNAPSHOT_PATH", tmp_path / "tsl_snapshot.json")
    monkeypatch.setattr(tsl_snapshot, "TSL_HISTORY_PATH", tmp_path / "tsl_history.jsonl")

    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-07T08:00:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=1.58, away_odds=2.42),
        source="TSL_TEST",
    )

    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-07T10:30:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=1.52, away_odds=2.55),
        source="TSL_TEST",
    )

    timeline = tsl_snapshot.get_tsl_market_history("TPE", "JPN", market="ML")
    assert len(timeline) == 2
    assert timeline[0].home_odds == pytest.approx(1.58)
    assert timeline[1].home_odds == pytest.approx(1.52)
    assert timeline[0].away_odds == pytest.approx(2.42)
    assert timeline[1].away_odds == pytest.approx(2.55)

    ctx = tsl_snapshot.build_tsl_line_movement_context(
        "TPE",
        "JPN",
        market="ML",
        game_time="2026-03-07T19:00:00+08:00",
        max_snapshots=12,
    )
    assert ctx["opening_home_odds"] == pytest.approx(1.58)
    assert ctx["current_home_odds"] == pytest.approx(1.52)
    assert ctx["current_away_odds"] == pytest.approx(2.55)
    assert ctx["total_line_moves"] == 1
    assert len(ctx["line_history"]) == 2
    assert ctx["line_history"][0].timestamp_minutes_to_game > ctx["line_history"][1].timestamp_minutes_to_game
    assert ctx["line_movement_velocity"] > 0
    assert ctx["historical_home_implied_probs"][0] < ctx["historical_home_implied_probs"][1]


def test_decision_engine_derives_velocity_from_line_history():
    from wbc_backend.intelligence.decision_engine import InstitutionalDecisionEngine
    from wbc_backend.intelligence.line_movement_predictor import LineSnapshot, TimingAction

    engine = InstitutionalDecisionEngine(bankroll=10000)
    report = engine.analyze_match(
        match_id="TEST_TSL_HISTORY",
        match_label="TPE @ JPN",
        sub_model_probs={
            "elo": 0.70,
            "bayesian": 0.72,
            "poisson": 0.69,
            "gbm": 0.71,
            "ensemble": 0.70,
        },
        calibrated_prob=0.70,
        odds_home=1.92,
        odds_away=2.05,
        brier_score=0.20,
        platt_a=1.02,
        platt_b=-0.005,
        sharp_signal_count=1,
        market_liquidity_score=0.6,
        n_sportsbooks=4,
        sharp_direction_agrees=True,
        line_history=[
            LineSnapshot(timestamp_minutes_to_game=600.0, home_odds=2.02, away_odds=1.86),
            LineSnapshot(timestamp_minutes_to_game=240.0, home_odds=1.97, away_odds=1.91),
            LineSnapshot(timestamp_minutes_to_game=60.0, home_odds=1.92, away_odds=2.05),
        ],
        league="WBC",
        avg_limit_usd=5000,
        book_tier="generic",
    )

    assert report.expected_closing_odds > 0
    assert report.line_movement_confidence >= 0
    assert report.timing_action in {action.value for action in TimingAction}


def test_build_tsl_odds_time_series_feeds_market_steam_detection(tmp_path, monkeypatch):
    import data.tsl_snapshot as tsl_snapshot
    from wbc_backend.betting.market import market_adjustment
    from wbc_backend.domain.schemas import OddsLine

    monkeypatch.setattr(tsl_snapshot, "TSL_SNAPSHOT_PATH", tmp_path / "tsl_snapshot.json")
    monkeypatch.setattr(tsl_snapshot, "TSL_HISTORY_PATH", tmp_path / "tsl_history.jsonl")

    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-07T00:00:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=2.20, away_odds=1.70),
        source="TSL_TEST",
    )
    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-07T00:20:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=1.92, away_odds=2.02),
        source="TSL_TEST",
    )

    odds_history = tsl_snapshot.build_tsl_odds_time_series("TPE", "JPN", markets=("ML",), max_snapshots=12)
    assert "TSL_ML_JPN" in odds_history
    assert len(odds_history["TSL_ML_JPN"].snapshots) == 2

    odds_lines = [
        OddsLine(
            sportsbook="TSL",
            market="ML",
            side="JPN",
            line=None,
            decimal_odds=1.92,
            source_type="tsl",
        ),
        OddsLine(
            sportsbook="TSL",
            market="ML",
            side="TPE",
            line=None,
            decimal_odds=2.02,
            source_type="tsl",
        ),
    ]

    result = market_adjustment(
        0.55,
        odds_lines,
        "JPN",
        "TPE",
        odds_history=odds_history,
    )
    assert result["n_steam_moves"] >= 1
    assert result["market_weight_applied"] > 0.15


def test_stale_tsl_history_is_excluded_from_time_series_and_line_context(tmp_path, monkeypatch):
    import data.tsl_snapshot as tsl_snapshot

    monkeypatch.setattr(tsl_snapshot, "TSL_SNAPSHOT_PATH", tmp_path / "tsl_snapshot.json")
    monkeypatch.setattr(tsl_snapshot, "TSL_HISTORY_PATH", tmp_path / "tsl_history.jsonl")

    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-06T00:00:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=2.20, away_odds=1.70),
        source="TSL_TEST",
    )
    monkeypatch.setattr(tsl_snapshot, "_utc_now", lambda: "2026-03-06T00:20:00Z")
    tsl_snapshot.save_tsl_snapshot(
        games=_build_game(home_odds=1.92, away_odds=2.02),
        source="TSL_TEST",
    )

    monkeypatch.setattr(
        tsl_snapshot,
        "_utc_now_dt",
        lambda: tsl_snapshot._parse_iso_datetime("2026-03-07T12:00:00Z", assume_tz=tsl_snapshot.timezone.utc),
    )

    odds_history = tsl_snapshot.build_tsl_odds_time_series(
        "TPE",
        "JPN",
        markets=("ML",),
        max_snapshots=12,
        max_snapshot_age_hours=8.0,
    )
    line_ctx = tsl_snapshot.build_tsl_line_movement_context(
        "TPE",
        "JPN",
        market="ML",
        game_time="2026-03-07T19:00:00+08:00",
        max_snapshots=12,
        max_snapshot_age_hours=8.0,
    )

    assert odds_history == {}
    assert line_ctx["line_history"] == []
    assert line_ctx["total_line_moves"] == 0
