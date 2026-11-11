from __future__ import annotations

import json
import os
import pickle
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.config.settings import AppConfig, DataSourceConfig, DeploymentGateConfig
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
from wbc_backend.features.advanced import FEATURE_NAMES
from wbc_backend.pipeline.deployment_gate import DeploymentGateError, evaluate_deployment_gate
from wbc_backend.reporting.prediction_registry import append_prediction_record


def _write_gate_files(root: Path, stale_artifact: bool = False) -> AppConfig:
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    expected_count = len(FEATURE_NAMES)
    count = expected_count - 1 if stale_artifact else expected_count
    for name in ("xgb_model.pkl", "lgbm_model.pkl", "cat_model.pkl", "nn_model.pkl"):
        with (artifacts / name).open("wb") as fh:
            pickle.dump({"feature_count": count, "model": {"name": name}}, fh)

    walkforward_path = root / "walkforward_summary.json"
    walkforward_path.write_text(
        json.dumps({"games": 1200, "brier": 0.242, "ml_roi": 0.011}),
        encoding="utf-8",
    )

    calibration_path = root / "calibration_compare.json"
    calibration_path.write_text(
        json.dumps(
            {
                "platt": {"summary": {"ml_roi": -0.01, "ece": 0.09}},
                "isotonic": {"summary": {"ml_roi": 0.02, "ece": 0.07}},
            }
        ),
        encoding="utf-8",
    )

    sources = DataSourceConfig(
        model_artifacts_dir=str(artifacts),
        walkforward_summary_json=str(walkforward_path),
        calibration_compare_json=str(calibration_path),
        prediction_registry_jsonl=str(root / "prediction_registry.jsonl"),
    )
    gate = DeploymentGateConfig(
        enabled=True,
        min_walkforward_games=500,
        max_walkforward_brier=0.25,
        min_best_calibration_ml_roi=0.0,
        require_artifact_schema_match=True,
    )
    return AppConfig(sources=sources, deployment_gate=gate)


class TestDeploymentGate(unittest.TestCase):

    def test_deployment_gate_passes_with_current_schema_and_positive_calibration(self):
        with tempfile.TemporaryDirectory() as td:
            config = _write_gate_files(Path(td), stale_artifact=False)
            report = evaluate_deployment_gate(config)
            report.ensure_ready()
            self.assertEqual(report.status, "READY")
            self.assertEqual(report.selected_calibration, "isotonic")

    def test_deployment_gate_blocks_stale_artifact_schema(self):
        with tempfile.TemporaryDirectory() as td:
            config = _write_gate_files(Path(td), stale_artifact=True)
            report = evaluate_deployment_gate(config)
            self.assertTrue(report.blocking)
            with self.assertRaises(DeploymentGateError):
                report.ensure_ready()


class TestPredictionRegistry(unittest.TestCase):
    def test_append_prediction_record_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            registry_path = Path(td) / "prediction_registry.jsonl"
            config = AppConfig(
                sources=DataSourceConfig(prediction_registry_jsonl=str(registry_path))
            )
            request = AnalyzeRequest(game_id="C07", line_total=7.5, line_spread_home=-1.5)
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
            matchup = Matchup(
                game_id="C07",
                tournament="WBC2026",
                game_time_utc="2026-03-08T03:00:00Z",
                home=home,
                away=away,
                round_name="Pool C",
            )
            verification = VerificationResult(
                requested_game_id="C07",
                canonical_game_id="C07",
                status="VERIFIED_WITH_FALLBACK",
                issues=[VerificationIssue(code="lineups_fallback_previous_game", message="fallback", severity="WARNING")],
                used_fallback_lineup=True,
            )
            gate = evaluate_deployment_gate(_write_gate_files(Path(td), stale_artifact=False))
            game_output = GameOutput(
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
            )
            pred = PredictionResult(
                game_id="C07",
                home_win_prob=0.46,
                away_win_prob=0.54,
                expected_home_runs=4.9,
                expected_away_runs=5.2,
                x_factors=["Previous-game lineup fallback applied"],
                diagnostics={"regime": "POOL"},
                confidence_score=0.85,
            )
            sim = SimulationSummary(
                home_win_prob=0.48,
                away_win_prob=0.52,
                over_prob=0.57,
                under_prob=0.43,
                home_cover_prob=0.49,
                away_cover_prob=0.51,
            )
            top_bets = [
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
            ]

            append_prediction_record(
                config=config,
                request=request,
                matchup=matchup,
                verification=verification,
                deployment_gate=gate,
                game_output=game_output,
                pred=pred,
                sim=sim,
                top_bets=top_bets,
                decision_report={"decision": "NO_BET"},
                calibration_metrics={"brier": 0.24},
                portfolio_metrics={
                    "survival_prob": 1.0,
                    "market_support_profile": "tsl_direct",
                    "market_support_tilt": "direct_favored",
                },
            )

            lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["game_id"], "C07")
            self.assertEqual(payload["teams"]["home"], "KOR")
            self.assertEqual(payload["verification"]["status"], "VERIFIED_WITH_FALLBACK")
            self.assertEqual(payload["deployment_gate"]["status"], "READY")
            self.assertEqual(payload["market_support"]["primary"], "tsl_direct")
            self.assertEqual(payload["market_support"]["best_bet_state"], "tsl_direct")
            self.assertEqual(payload["market_support"]["tilt"], "direct_favored")


if __name__ == "__main__":
    unittest.main()
