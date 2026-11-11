from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
from wbc_backend.reports.spring_training_game_report import (
    build_spring_training_game_report,
    build_spring_training_tracking_summary,
)


@dataclass
class SpringRecord:
    game_id: str = "MLB-SPRING-001"
    league: str = "MLB"
    tournament: str = "MLB"
    home_team: str = "NYY"
    away_team: str = "BOS"
    game_time_utc: str = "2026-03-12T18:00:00Z"
    round_name: str = "Warmup"
    market_home_prob: float = 0.54
    ou_line: float = 9.0
    home_starter: str = "Spring H"
    away_starter: str = "Spring A"
    home_lineup: list = field(default_factory=list)
    away_lineup: list = field(default_factory=list)
    home_bullpen: list = field(default_factory=list)
    away_bullpen: list = field(default_factory=list)
    bullpen_usage: dict | None = None
    odds: dict | None = field(default_factory=lambda: {"home_ml": -118, "away_ml": 108, "book": "test"})
    weather: dict | None = field(default_factory=dict)
    pitchers: dict | None = field(default_factory=dict)
    lineups: dict | None = field(default_factory=dict)
    injury_report: dict | None = field(default_factory=dict)
    game_type: str = "SPRING_TRAINING"


class StubMarlPredictor:
    def predict(self, record):
        return 0.57


class TestSpringTrainingSandbox(unittest.TestCase):
    def test_spring_training_routes_to_sandbox_only(self):
        orchestrator = PredictionOrchestrator(marl_predictor=StubMarlPredictor())
        with patch("wbc_backend.models.mlb_regime_paper.default_mlb_regime_paper_system") as paper_stub:
            result = orchestrator.predict(
                SpringRecord(),
                use_hierarchical_mc=False,
                use_world_model=False,
            )

        paper_stub.assert_not_called()
        self.assertEqual(result.game_type, "SPRING_TRAINING")
        self.assertEqual(result.execution_mode, "SANDBOX_ONLY")
        self.assertEqual(result.betting_advice, "NOT_RECOMMENDED_FOR_BETTING")
        self.assertEqual(result.metrics_pool, "SPRING_SANDBOX_ONLY")
        self.assertEqual(result.recommended_side, "pass")
        self.assertEqual(result.recommended_kelly_fraction, 0.0)
        self.assertEqual(result.paper_reason, "spring_training_sandbox_only")
        self.assertEqual(result.audit_trail["tradeability"], "SANDBOX_ONLY")
        self.assertEqual(result.audit_trail["sandbox_output_layer"], "spring_training_game_report")
        self.assertEqual(result.governance_flags["metrics_pool"], "SPRING_SANDBOX_ONLY")
        self.assertEqual(result.governance_flags["live_execution"], "disabled")
        report = result.audit_trail["spring_training_report"]
        self.assertEqual(report["header"]["mode"], "SANDBOX_ONLY")
        self.assertEqual(report["output_section"]["recommendation"], "NO_BET")
        self.assertIn("SANDBOX_ONLY", report["markdown_report"])
        self.assertIn("NOT RECOMMENDED FOR BETTING", report["markdown_report"])

    def test_spring_training_report_has_expected_sections(self):
        orchestrator = PredictionOrchestrator(marl_predictor=StubMarlPredictor())
        result = orchestrator.predict(
            SpringRecord(),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        report = build_spring_training_game_report(record=SpringRecord(), orchestrator_result=result)
        self.assertEqual(report["game_type"], "SPRING_TRAINING")
        self.assertEqual(report["header"]["title"], "SPRING TRAINING")
        self.assertEqual(report["header"]["mode"], "SANDBOX_ONLY")
        self.assertEqual(report["output_section"]["execution_mode"], "SANDBOX_ONLY")
        self.assertEqual(report["output_section"]["recommendation"], "NO_BET")
        self.assertGreaterEqual(report["output_section"]["confidence"], 0.0)
        self.assertIn("spring training", report["markdown_report"].lower())
        self.assertIn("sandbox-only", report["markdown_report"].lower())

    def test_spring_training_tracking_summary_isolated(self):
        orchestrator = PredictionOrchestrator(marl_predictor=StubMarlPredictor())
        result = orchestrator.predict(
            SpringRecord(),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        report = result.audit_trail["spring_training_report"]
        summary = build_spring_training_tracking_summary([report, report])
        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["analysis_count"], 2)
        self.assertEqual(summary["prediction_distribution"]["NO_BET"], 2)
        self.assertEqual(summary["metrics_pool"], "SPRING_SANDBOX_ONLY")
        self.assertEqual(summary["roi"], "unavailable")
        self.assertEqual(summary["clv"], "unavailable")

    def test_paper_monitor_can_include_spring_tracking_without_polluting_mlb_metrics(self):
        from wbc_backend.research.mlb_paper_monitor import run_mlb_paper_tracking_monitor

        spring_report = build_spring_training_game_report(
            record=SpringRecord(),
            orchestrator_result=PredictionOrchestrator(marl_predictor=StubMarlPredictor()).predict(
                SpringRecord(),
                use_hierarchical_mc=False,
                use_world_model=False,
            ),
        )

        decision_report = {
            "per_game": [
                {
                    "game_id": "MLB-2026_03_20-ATL-BOS",
                    "regime": "favorites",
                    "was_selected_for_bet": False,
                    "paper_pnl": 0.0,
                    "brier": 0.2,
                    "logloss": 0.5,
                    "clv_available": False,
                    "clv": 0.0,
                }
            ]
        }
        regime_report = {
            "paper_mode_reporting": {
                "by_regime": [
                    {"regime": "favorites", "fold_stability": 0.1},
                ]
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "monitor.json")
            with patch("wbc_backend.research.mlb_paper_monitor.evaluate_mlb_decision_quality", return_value=decision_report), \
                 patch("wbc_backend.research.mlb_paper_monitor.run_mlb_regime_paper_mode", return_value=regime_report):
                summary = run_mlb_paper_tracking_monitor(
                    spring_training_reports=[spring_report],
                    output_path=out_path,
                )

            self.assertEqual(summary.status, "OK")
            payload = json.loads(open(out_path, "r", encoding="utf-8").read())
            self.assertIn("spring_training_tracking", payload)
            self.assertEqual(payload["spring_training_tracking"]["sample_count"], 1)
            self.assertEqual(payload["spring_training_tracking"]["roi"], "unavailable")
            self.assertEqual(payload["governance_flags"]["execution_mode"], "PAPER_ONLY")
            self.assertNotIn("roi_total", payload.get("spring_training_tracking", {}))


if __name__ == "__main__":
    unittest.main()
