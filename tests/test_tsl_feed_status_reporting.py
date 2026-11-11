from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_attach_tsl_fetch_context_marks_blocked_prematch_feed(monkeypatch):
    from wbc_backend.domain.schemas import Matchup, PredictionResult, TeamSnapshot
    from wbc_backend.pipeline.service import PredictionService

    pred = PredictionResult(
        game_id="A01",
        home_win_prob=0.62,
        away_win_prob=0.38,
        expected_home_runs=5.1,
        expected_away_runs=3.4,
        x_factors=[],
        diagnostics={},
    )
    matchup = Matchup(
        game_id="A01",
        tournament="WBC2026",
        game_time_utc="2026-03-14T06:30:00Z",
        home=TeamSnapshot("JPN", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
        away=TeamSnapshot("TPE", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
    )

    monkeypatch.setattr(
        "wbc_backend.pipeline.service.read_tsl_fetch_status",
        lambda: {
            "source": "TSL_MULTI_SOURCE",
            "success": False,
            "games_count": 0,
            "note": (
                "modern_live=2; modern_live_baseball=0; modern_baseball_sport_id=34731.1; "
                "modern_pre_2026-03-13=HTTP Error 403: Forbidden"
            ),
            "fetched_at": "2026-03-13T02:37:45Z",
        },
    )
    monkeypatch.setattr(
        "wbc_backend.pipeline.service.load_tsl_snapshot",
        lambda: {"source": "TSL_MULTI_SOURCE", "fetched_at": "2026-03-13T02:37:45Z", "games": []},
    )

    PredictionService._attach_tsl_fetch_context(pred, matchup, odds_lines=[])

    assert pred.diagnostics["tsl_fetch_success"] == 0.0
    assert pred.diagnostics["tsl_games_count"] == 0.0
    assert pred.diagnostics["tsl_status"]["source"] == "TSL_MULTI_SOURCE"
    assert pred.diagnostics["tsl_matchup"]["in_snapshot"] is False
    assert any("TSL pre-match feed is currently blocked" in factor for factor in pred.x_factors)


def test_attach_tsl_fetch_context_marks_matchup_present_in_latest_snapshot(monkeypatch):
    from wbc_backend.domain.schemas import Matchup, PredictionResult, TeamSnapshot
    from wbc_backend.pipeline.service import PredictionService

    pred = PredictionResult(
        game_id="A01",
        home_win_prob=0.55,
        away_win_prob=0.45,
        expected_home_runs=4.8,
        expected_away_runs=4.0,
        x_factors=[],
        diagnostics={},
    )
    matchup = Matchup(
        game_id="A01",
        tournament="WBC2026",
        game_time_utc="2026-03-14T06:30:00Z",
        home=TeamSnapshot("DOM", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
        away=TeamSnapshot("KOR", 1500, 0.32, 100, 3.8, 1.25, 100, 0.70, 8.0, 65),
    )

    monkeypatch.setattr(
        "wbc_backend.pipeline.service.read_tsl_fetch_status",
        lambda: {
            "source": "TSL_BLOB3RD",
            "success": True,
            "games_count": 7,
            "note": "modern_pre_zh=7",
            "fetched_at": "2026-03-13T03:30:16Z",
        },
    )
    monkeypatch.setattr(
        "wbc_backend.pipeline.service.load_tsl_snapshot",
        lambda: {
            "source": "TSL_BLOB3RD",
            "fetched_at": "2026-03-13T03:30:16Z",
            "games": [
                {
                    "gameId": "3452400.1",
                    "awayTeamName": "南韓",
                    "homeTeamName": "多明尼加",
                    "gameTime": "2026-03-14T06:30:00+08:00",
                    "markets": [
                        {"marketCode": "MNL"},
                        {"marketCode": "HDC"},
                        {"marketCode": "OU"},
                        {"marketCode": "OE"},
                    ],
                }
            ],
        },
    )
    from datetime import datetime, timezone
    monkeypatch.setattr(
        "wbc_backend.pipeline.service.datetime",
        type(
            "FrozenDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime(2026, 3, 13, 4, 0, 0, tzinfo=timezone.utc)),
                "fromisoformat": staticmethod(datetime.fromisoformat),
            },
        ),
    )

    PredictionService._attach_tsl_fetch_context(pred, matchup, odds_lines=[])

    assert pred.diagnostics["tsl_matchup"]["in_snapshot"] is True
    assert pred.diagnostics["tsl_matchup"]["game_id"] == "3452400.1"
    assert pred.diagnostics["tsl_matchup"]["market_count"] == 4
    assert pred.diagnostics["tsl_matchup"]["is_fresh"] is True
    assert any("TSL snapshot includes this matchup" in factor for factor in pred.x_factors)


def test_render_full_report_includes_tsl_feed_status_block():
    from wbc_backend.domain.schemas import GameOutput, PredictionResult, SimulationSummary
    from wbc_backend.reporting.renderers import render_full_report

    game = GameOutput(
        game_id="A01",
        home_team="JPN",
        away_team="TPE",
        home_win_prob=0.62,
        away_win_prob=0.38,
        predicted_home_score=5.1,
        predicted_away_score=3.4,
        market_bias_score=0.01,
        ev_best=0.03,
        best_bet_strategy="ML JPN @ TSL",
        confidence_index=0.71,
        top_3_bets=[],
    )
    pred = PredictionResult(
        game_id="A01",
        home_win_prob=0.62,
        away_win_prob=0.38,
        expected_home_runs=5.1,
        expected_away_runs=3.4,
        x_factors=[],
        diagnostics={
            "tsl_status": {
                "source": "TSL_MULTI_SOURCE",
                "success": False,
                "games_count": 0,
                "fetched_at": "2026-03-13T02:37:45Z",
                "note": "modern_pre_2026-03-13=HTTP Error 403: Forbidden",
            },
            "tsl_matchup": {
                "in_snapshot": False,
                "snapshot_source": "TSL_MULTI_SOURCE",
                "snapshot_fetched_at": "2026-03-13T02:37:45Z",
            },
        },
    )
    sim = SimulationSummary(
        home_win_prob=0.62,
        away_win_prob=0.38,
        over_prob=0.53,
        under_prob=0.47,
        home_cover_prob=0.55,
        away_cover_prob=0.45,
    )

    report = render_full_report(
        game,
        pred,
        sim,
        market_result={
            "market_implied_home": 0.6,
            "adjusted_home_prob": 0.62,
            "market_support_summary": "TSL blocked",
            "market_support_by_market": {
                "ML": "blocked",
                "RL": "blocked",
                "OU": "blocked",
            },
        },
    )

    assert "TSL FEED STATUS" in report
    assert "TSL_MULTI_SOURCE" in report
    assert "modern_pre_2026-03-13=HTTP Error 403: Forbidden" in report
    assert "Matchup In Snapshot: False" in report
    assert "Market Support:      TSL blocked" in report
    assert "ML:blocked" in report


def test_portfolio_metrics_are_hardened_when_tsl_feed_blocked(monkeypatch):
    from types import SimpleNamespace

    from wbc_backend.betting.risk_control import BankrollState
    from wbc_backend.domain.schemas import BetRecommendation
    from wbc_backend.pipeline.service import PredictionService

    service = PredictionService.__new__(PredictionService)
    service.portfolio_risk = SimpleNamespace(
        state=SimpleNamespace(bankroll=10000.0, drawdown=0.0),
        size_portfolio=lambda proposals: SimpleNamespace(
            positions=[SimpleNamespace(stake_fraction=0.02, bet=SimpleNamespace(win_prob=0.60, odds=2.0))],
            total_exposure=0.02,
            portfolio_variance=0.0001,
            expected_daily_return=0.01,
            risk_level="GREEN",
            warnings=[],
        ),
    )
    service.bankroll = BankrollState(
        initial=10000.0,
        current=10000.0,
        peak=10000.0,
        daily_start=10000.0,
    )

    monkeypatch.setattr(
        "wbc_backend.pipeline.service.read_tsl_fetch_status",
        lambda: {
            "source": "TSL_MULTI_SOURCE",
            "success": False,
            "note": "modern_pre_2026-03-13=HTTP Error 403: Forbidden",
            "fetched_at": "2026-03-13T02:37:45Z",
        },
    )

    metrics = service._run_portfolio_optimization(
        top_bets=[
            BetRecommendation(
                market="ML",
                side="JPN",
                line=None,
                sportsbook="BookA",
                source_type="intl",
                win_probability=0.60,
                implied_probability=0.50,
                ev=0.08,
                edge=0.10,
                kelly_fraction=0.03,
                stake_fraction=0.02,
                stake_amount=200.0,
                confidence=0.70,
            )
        ],
        decision_rpt=SimpleNamespace(decision="BET", edge_score=3.2),
        matchup=None,
    )

    assert metrics["risk_level"] == "YELLOW"
    assert metrics["data_quality_risk"] == "HIGH"
    assert metrics["tsl_feed_state"] == "blocked"
    assert any("TSL pre-match feed blocked" in warning for warning in metrics["warnings"])


def test_render_full_report_includes_portfolio_data_quality_warnings():
    from wbc_backend.domain.schemas import GameOutput, PredictionResult, SimulationSummary
    from wbc_backend.reporting.renderers import render_full_report

    game = GameOutput(
        game_id="A01",
        home_team="JPN",
        away_team="TPE",
        home_win_prob=0.62,
        away_win_prob=0.38,
        predicted_home_score=5.1,
        predicted_away_score=3.4,
        market_bias_score=0.01,
        ev_best=0.03,
        best_bet_strategy="ML JPN @ BookA",
        confidence_index=0.71,
        top_3_bets=[],
    )
    pred = PredictionResult(
        game_id="A01",
        home_win_prob=0.62,
        away_win_prob=0.38,
        expected_home_runs=5.1,
        expected_away_runs=3.4,
        x_factors=[],
        diagnostics={},
    )
    sim = SimulationSummary(
        home_win_prob=0.62,
        away_win_prob=0.38,
        over_prob=0.53,
        under_prob=0.47,
        home_cover_prob=0.55,
        away_cover_prob=0.45,
    )

    report = render_full_report(
        game,
        pred,
        sim,
        market_result={"market_implied_home": 0.6, "adjusted_home_prob": 0.62},
        portfolio_metrics={
            "survival_prob": 0.98,
            "cvar_95": -0.0001,
            "expected_return": 0.01,
            "gross_exposure": 0.02,
            "drawdown_scale": 1.0,
            "current_drawdown": 0.0,
            "risk_level": "YELLOW",
            "data_quality_risk": "HIGH",
            "tsl_feed_state": "blocked",
            "tsl_matchup_in_snapshot": False,
            "tsl_matchup_market_count": 0,
            "market_support_profile": "intl_only",
            "tsl_feed_summary": "TSL pre-match blocked at official source (TSL_MULTI_SOURCE)",
            "warnings": ["TSL pre-match feed blocked; Taiwan-market recommendations are running in degraded mode"],
        },
    )

    assert "Data Quality Risk:    HIGH" in report
    assert "TSL Feed State:       blocked" in report
    assert "TSL Matchup Listed:   False" in report
    assert "Market Support:       International only" in report
    assert "Taiwan-market recommendations are running in degraded mode" in report
