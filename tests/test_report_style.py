from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
from wbc_backend.reports.spring_training_game_report import build_spring_training_game_report
from wbc_backend.ux.report_style import build_report_header, render_report_banner


@dataclass
class SpringRecord:
    game_id: str = "MLB-SPRING-STYLE-001"
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


class TestReportStyle(unittest.TestCase):
    def test_report_header_and_banner_are_consistent(self):
        header = build_report_header(
            title="TEST REPORT",
            mode="SANDBOX_ONLY",
            safety="NOT RECOMMENDED FOR BETTING",
            purpose="sanity check",
            scope="spring training",
            source="unit-test",
            status="sandbox-only",
            generated_at="2026-03-26T00:00:00Z",
        )
        banner = render_report_banner(header)
        self.assertEqual(header["mode"], "SANDBOX_ONLY")
        self.assertIn("TEST REPORT", banner)
        self.assertIn("MODE: SANDBOX_ONLY", banner)
        self.assertIn("SAFETY: NOT RECOMMENDED FOR BETTING", banner)

    def test_spring_report_includes_standard_header(self):
        orchestrator = PredictionOrchestrator(marl_predictor=StubMarlPredictor())
        result = orchestrator.predict(SpringRecord(), use_hierarchical_mc=False, use_world_model=False)
        report = build_spring_training_game_report(record=SpringRecord(), orchestrator_result=result)
        self.assertIn("report_header", report)
        self.assertIn("report_summary", report)
        self.assertEqual(report["report_header"]["mode"], "SANDBOX_ONLY")
        self.assertEqual(report["report_header"]["safety"], "NOT RECOMMENDED FOR BETTING")
        self.assertEqual(report["report_summary"]["mode"], "SANDBOX_ONLY")
        self.assertEqual(report["report_summary"]["safety"], "NOT RECOMMENDED FOR BETTING")
        self.assertIn("MODE: SANDBOX_ONLY", report["markdown_report"])


if __name__ == "__main__":
    unittest.main()
