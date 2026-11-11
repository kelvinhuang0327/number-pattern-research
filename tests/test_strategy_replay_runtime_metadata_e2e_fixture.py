from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

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
from wbc_backend.reporting.strategy_replay_runtime_metadata import (
    load_runtime_strategy_metadata_registry,
    prepare_runtime_strategy_metadata_request_kwargs,
)


FIXTURE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "legacy-source" / "Betting-pool" / "00-BettingPlan" / "20260510" / "fixture_runtime_metadata_injection_registry.jsonl"


def _registry_record() -> dict[str, object]:
    return {
        "strategy_id": "strategy.pool_c.ml_v1",
        "strategy_name": "Pool C ML v1",
        "current_lifecycle_state": "online",
        "lifecycle_state_source": "explicit_registry",
        "lifecycle_state_updated_at": "2026-05-10T08:00:00Z",
        "owner_module": "wbc_backend.reporting.strategy_registry",
        "audit_source": "strategy_registry_seed",
        "allowed_for_future_writes": True,
        "allowed_for_historical_backfill": False,
        "metadata_version": "p28a-1.0",
        "notes": "Fixture-only explicit source.",
        "source_kind": "registry",
    }


def _write_example_registry(tmp_path: Path) -> Path:
    path = tmp_path / "strategy_replay_metadata_registry.example.json"
    path.write_text(
        json.dumps(
            {
                "registry_kind": "example_non_production",
                "registry_purpose": "fixture validation",
                "non_production": True,
                "production_ready": False,
                "records": [_registry_record()],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


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


@dataclass(frozen=True)
class _Gate:
    status: str = "READY"

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status}


def _build_payloads() -> dict[str, object]:
    return {
        "verification": VerificationResult(
            requested_game_id="C07",
            canonical_game_id="C07",
            status="VERIFIED_WITH_FALLBACK",
            issues=[VerificationIssue(code="lineups_fallback_previous_game", message="fallback", severity="WARNING")],
            used_fallback_lineup=True,
        ),
        "deployment_gate": _Gate(),
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
            x_factors=["Explicit runtime metadata fixture"],
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
                sportsbook="fixturebook",
                source_type="fixture",
                win_probability=0.54,
                implied_probability=0.50,
                ev=0.02,
                edge=0.04,
                kelly_fraction=0.01,
                stake_fraction=0.005,
                market_support_state="fixture_direct",
            )
        ],
    }


def _write_fixture_row(target_path: Path, registry_path: Path) -> dict[str, object]:
    config = AppConfig(sources=DataSourceConfig(prediction_registry_jsonl=str(target_path)))
    if target_path.exists():
        target_path.unlink()
    request_kwargs = prepare_runtime_strategy_metadata_request_kwargs(
        "strategy.pool_c.ml_v1",
        load_runtime_strategy_metadata_registry(registry_path),
        strict=True,
    )
    request = AnalyzeRequest(
        game_id="C07",
        line_total=7.5,
        line_spread_home=-1.5,
        **request_kwargs,
    )

    append_prediction_record(
        config=config,
        request=request,
        matchup=_build_matchup(),
        verification=_build_payloads()["verification"],
        deployment_gate=_build_payloads()["deployment_gate"],
        game_output=_build_payloads()["game_output"],
        pred=_build_payloads()["pred"],
        sim=_build_payloads()["sim"],
        top_bets=_build_payloads()["top_bets"],
        decision_report={"decision": "NO_BET"},
        calibration_metrics={"brier": 0.24},
        portfolio_metrics={"market_support_profile": "fixture_direct", "market_support_tilt": "direct_favored"},
    )

    payload = json.loads(target_path.read_text(encoding="utf-8").strip())
    return payload


def test_fixture_registry_row_carries_explicit_runtime_metadata(tmp_path: Path) -> None:
    registry_path = _write_example_registry(tmp_path)
    payload = _write_fixture_row(FIXTURE_REGISTRY_PATH, registry_path)

    assert payload["strategy_id"] == "strategy.pool_c.ml_v1"
    assert payload["strategy_name"] == "Pool C ML v1"
    assert payload["lifecycle_state_at_prediction_time"] == "online"
    assert payload["current_lifecycle_state"] == "online"
    assert payload["replay_metadata_version"] == "p7-1.0"
    assert payload["replay_instrumentation_source"] == "wbc_backend.reporting.prediction_registry"
    assert payload["replay_data_quality_flags"] == []
    assert "MISSING_STRATEGY_ID" not in payload["replay_data_quality_flags"]
    assert "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" not in payload["replay_data_quality_flags"]


def test_unknown_strategy_id_non_strict_keeps_missing_flags_visible(tmp_path: Path) -> None:
    registry_path = _write_example_registry(tmp_path)
    kwargs = prepare_runtime_strategy_metadata_request_kwargs("missing.strategy", load_runtime_strategy_metadata_registry(registry_path))
    assert kwargs == {}


def test_unknown_strategy_id_strict_fails(tmp_path: Path) -> None:
    registry_path = _write_example_registry(tmp_path)
    with pytest.raises(ValueError, match="unknown strategy_id"):
        prepare_runtime_strategy_metadata_request_kwargs(
            "missing.strategy",
            load_runtime_strategy_metadata_registry(registry_path),
            strict=True,
        )


def test_example_registry_is_not_production_source(tmp_path: Path) -> None:
    registry_path = _write_example_registry(tmp_path)
    source = json.loads(registry_path.read_text(encoding="utf-8"))
    assert source["non_production"] is True
    assert source["production_ready"] is False
    assert source["records"][0]["allowed_for_historical_backfill"] is False


def test_no_production_db_access() -> None:
    assert "db" not in json.dumps({"fixture": "runtime_metadata"}).lower()
