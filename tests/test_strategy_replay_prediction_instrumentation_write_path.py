from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.config.settings import AppConfig, DataSourceConfig
from wbc_backend.data.wbc_verification import VerificationIssue, VerificationResult
from wbc_backend.domain.schemas import (
    AnalyzeRequest,
    BetRecommendation,
    GameOutput,
    Matchup,
    PredictionResult,
    SimulationSummary,
    TeamSnapshot,
)
from wbc_backend.reporting.prediction_registry import append_prediction_record
from wbc_backend.reporting.strategy_replay_adapter import build_strategy_replay_rows, load_prediction_registry_entries


def _build_matchup() -> Matchup:
    away = TeamSnapshot(
        team="TPE",
        elo=1510,
        batting_woba=0.33,
        batting_ops_plus=104,
        pitching_fip=3.7,
        pitching_whip=1.20,
        pitching_stuff_plus=101,
        der=0.71,
        bullpen_depth=8.1,
        pitch_limit=65,
    )
    home = TeamSnapshot(
        team="KOR",
        elo=1500,
        batting_woba=0.32,
        batting_ops_plus=101,
        pitching_fip=3.9,
        pitching_whip=1.24,
        pitching_stuff_plus=100,
        der=0.70,
        bullpen_depth=8.0,
        pitch_limit=65,
    )
    return Matchup(
        game_id="C07",
        tournament="WBC2026",
        game_time_utc="2026-03-08T03:00:00Z",
        home=home,
        away=away,
        round_name="Pool C",
    )


def _build_common_payloads(*, canonical_game_id: str | None = None) -> dict[str, object]:
    return {
        "verification": VerificationResult(
            requested_game_id="C07",
            canonical_game_id=canonical_game_id,
            status="VERIFIED_WITH_FALLBACK",
            issues=[VerificationIssue(code="lineups_fallback_previous_game", message="fallback", severity="WARNING")],
            used_fallback_lineup=True,
        ),
        "deployment_gate": type("Gate", (), {"to_dict": lambda self: {"status": "READY"}})(),
        "game_output": GameOutput(
            game_id="C07",
            home_team="KOR",
            away_team="TPE",
            home_win_prob=0.46,
            away_win_prob=0.54,
            predicted_home_score=4.9,
            predicted_away_score=5.2,
            market_bias_score=0.0,
            ev_best=0.0,
            best_bet_strategy="",
            confidence_index=0.85,
        ),
        "pred": PredictionResult(
            game_id="C07",
            home_win_prob=0.46,
            away_win_prob=0.54,
            expected_home_runs=4.9,
            expected_away_runs=5.2,
            x_factors=["Previous-game lineup fallback applied"],
            diagnostics={"regime": "POOL"},
            confidence_score=0.85,
        ),
        "sim": SimulationSummary(
            home_win_prob=0.48,
            away_win_prob=0.52,
            over_prob=0.57,
            under_prob=0.43,
            home_cover_prob=0.49,
            away_cover_prob=0.51,
        ),
        "top_bets": [
            BetRecommendation(
                market="ML",
                side="TPE",
                line=None,
                sportsbook="testbook",
                source_type="tsl",
                win_probability=0.54,
                implied_probability=0.50,
                ev=0.02,
                edge=0.04,
                kelly_fraction=0.01,
                stake_fraction=0.005,
                market_support_state="tsl_direct",
            )
        ],
    }


def test_write_path_carries_replay_metadata_when_supplied(tmp_path: Path) -> None:
    registry_path = tmp_path / "prediction_registry.jsonl"
    config = AppConfig(sources=DataSourceConfig(prediction_registry_jsonl=str(registry_path)))
    request = AnalyzeRequest(
        game_id="C07",
        line_total=7.5,
        line_spread_home=-1.5,
        strategy_id="wbc.pool_c.ml_v1",
        strategy_name="Pool C ML v1",
        lifecycle_state_at_prediction_time="online",
        current_lifecycle_state="online",
        canonical_outcome_key="C07",
    )
    payloads = _build_common_payloads()

    append_prediction_record(
        config=config,
        request=request,
        matchup=_build_matchup(),
        verification=payloads["verification"],
        deployment_gate=payloads["deployment_gate"],
        game_output=payloads["game_output"],
        pred=payloads["pred"],
        sim=payloads["sim"],
        top_bets=payloads["top_bets"],
        decision_report={"decision": "NO_BET"},
        calibration_metrics={"brier": 0.24},
        portfolio_metrics={"market_support_profile": "tsl_direct", "market_support_tilt": "direct_favored"},
    )

    payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
    assert payload["strategy_id"] == "wbc.pool_c.ml_v1"
    assert payload["strategy_name"] == "Pool C ML v1"
    assert payload["lifecycle_state_at_prediction_time"] == "online"
    assert payload["current_lifecycle_state"] == "online"
    assert payload["canonical_outcome_key"] == "C07"
    assert payload["canonical_outcome_key_used_fallback"] is False
    assert payload["replay_metadata_version"] == "p7-1.0"
    assert payload["replay_data_quality_flags"] == []


def test_write_path_flags_missing_strategy_and_fallback_canonical_key(tmp_path: Path) -> None:
    registry_path = tmp_path / "prediction_registry.jsonl"
    config = AppConfig(sources=DataSourceConfig(prediction_registry_jsonl=str(registry_path)))
    request = AnalyzeRequest(game_id="C07", line_total=7.5, line_spread_home=-1.5)
    payloads = _build_common_payloads(canonical_game_id=None)

    append_prediction_record(
        config=config,
        request=request,
        matchup=_build_matchup(),
        verification=payloads["verification"],
        deployment_gate=payloads["deployment_gate"],
        game_output=payloads["game_output"],
        pred=payloads["pred"],
        sim=payloads["sim"],
        top_bets=payloads["top_bets"],
        decision_report={"decision": "NO_BET"},
        calibration_metrics={"brier": 0.24},
        portfolio_metrics={"market_support_profile": "tsl_direct", "market_support_tilt": "direct_favored"},
    )

    payload = json.loads(registry_path.read_text(encoding="utf-8").strip())
    assert payload["strategy_id"] == ""
    assert payload["strategy_name"] == ""
    assert payload["lifecycle_state_at_prediction_time"] == ""
    assert payload["current_lifecycle_state"] == ""
    assert payload["canonical_outcome_key"] == "C07"
    assert payload["canonical_outcome_key_used_fallback"] is True
    assert "MISSING_STRATEGY_ID" in payload["replay_data_quality_flags"]
    assert "MISSING_STRATEGY_NAME" in payload["replay_data_quality_flags"]
    assert "MISSING_CURRENT_LIFECYCLE_STATE" in payload["replay_data_quality_flags"]
    assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in payload["replay_data_quality_flags"]
    assert "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID" in payload["replay_data_quality_flags"]


def test_legacy_prediction_rows_remain_readable(tmp_path: Path) -> None:
    registry_path = tmp_path / "prediction_registry.jsonl"
    registry_path.write_text(
        json.dumps(
            {
                "recorded_at_utc": "2026-05-10T00:00:00Z",
                "game_id": "C07",
                "request": {"game_id": "C07", "line_total": 7.5, "line_spread_home": -1.5},
                "verification": {"status": "VERIFIED_WITH_FALLBACK", "canonical_game_id": "C07"},
                "deployment_gate": {"status": "READY"},
                "game_output": {"confidence_index": 0.85},
                "prediction": {"confidence_score": 0.85},
                "simulation": {"home_win_prob": 0.48},
                "top_bets": [],
                "market_support": {"primary": "unknown"},
                "decision_report": {"decision": "NO_BET"},
                "calibration_metrics": {},
                "portfolio_metrics": {},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    entries = load_prediction_registry_entries(registry_path)
    rows = build_strategy_replay_rows(entries, [])

    assert len(entries) == 1
    assert len(rows) == 1
    assert rows[0]["game_id"] == "C07"
    assert rows[0]["canonical_outcome_key"] == "C07"
    assert "MISSING_STRATEGY_ID" in set(rows[0]["data_quality_flags"])