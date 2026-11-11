from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.models.mlb_regime_paper import PaperInference
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator


@dataclass
class DummyRecord:
    game_id: str = "MLB-TEST-001"
    league: str = "MLB"
    tournament: str = "MLB"
    home_team: str = "NYM"
    away_team: str = "ATL"
    market_home_prob: float = 0.53
    ou_line: float = 8.5
    home_starter: str = "Starter H"
    away_starter: str = "Starter A"
    round_name: str = ""
    weather: dict = None
    odds: dict = None
    pitchers: dict = None
    lineups: dict = None
    bullpen_usage: dict = None
    injury_report: dict = None


class TestOrchestratorMLBIntegration(unittest.TestCase):
    def test_orchestrator_is_paper_only_without_strict_flag(self):
        o = PredictionOrchestrator()
        res = o.predict(DummyRecord())
        self.assertIn("league_adapter", res.audit_trail)
        self.assertEqual(res.audit_trail["league_adapter"], "MLB")
        self.assertIn("marl", res.models_activated)
        self.assertEqual(res.recommended_side, "pass")
        self.assertEqual(res.recommended_kelly_fraction, 0.0)
        self.assertEqual(res.audit_trail.get("tradeability"), "PAPER_ONLY")
        self.assertEqual(res.execution_mode, "PAPER_ONLY")
        self.assertEqual(res.paper_side, "skip")

    def test_orchestrator_surfaces_regime_paper_pick(self):
        @dataclass
        class StrictRecord(DummyRecord):
            strict_valid: bool = True

        class StubSystem:
            def predict_record(self, record):
                return PaperInference(
                    execution_mode="PAPER_ONLY",
                    paper_side="home",
                    paper_regime="favorites",
                    paper_prob=0.61,
                    edge_vs_market=0.08,
                    applicable_regimes=["favorites", "heavy_bullpen_stress"],
                    paper_reason="paper_pick_available",
                    candidates=[{"regime": "favorites", "paper_side": "home", "paper_prob": 0.61, "edge_vs_market": 0.08, "historical_fold_std": 0.07}],
                )

        with patch("wbc_backend.models.mlb_regime_paper.default_mlb_regime_paper_system", return_value=StubSystem()):
            o = PredictionOrchestrator()
            res = o.predict(StrictRecord())
        self.assertEqual(res.execution_mode, "PAPER_ONLY")
        self.assertEqual(res.recommended_side, "pass")
        self.assertEqual(res.recommended_kelly_fraction, 0.0)
        self.assertEqual(res.paper_side, "home")
        self.assertEqual(res.paper_regime, "favorites")
        self.assertIn("favorites", res.applicable_regimes)
        self.assertEqual(res.audit_trail.get("tradeability"), "PAPER_ONLY")


if __name__ == "__main__":
    unittest.main()
