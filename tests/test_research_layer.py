from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.config import research_paths
from research.layer import ResearchLayer
from research.utils import load_json, load_jsonl
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator


@dataclass
class ResearchSpringRecord:
    game_id: str = "MLB-SPRING-RESEARCH-001"
    league: str = "MLB"
    tournament: str = "MLB"
    home_team: str = "NYY"
    away_team: str = "BOS"
    game_time_utc: str = "2026-03-30T18:00:00Z"
    round_name: str = "Warmup"
    market_home_prob: float = 0.54
    ou_line: float = 9.0
    home_starter: str = "Spring H"
    away_starter: str = "Spring A"
    home_lineup: list = field(default_factory=list)
    away_lineup: list = field(default_factory=list)
    home_bullpen: list = field(default_factory=list)
    away_bullpen: list = field(default_factory=list)
    bullpen_usage: dict = None
    odds: dict = field(default_factory=lambda: {"home_ml": -118, "away_ml": 108, "book": "test"})
    weather: dict = field(default_factory=dict)
    pitchers: dict = field(default_factory=dict)
    lineups: dict = field(default_factory=dict)
    injury_report: dict = field(default_factory=dict)
    game_type: str = "SPRING_TRAINING"


class StubMarlPredictor:
    def predict(self, record):
        return 0.57


def make_fake_result() -> SimpleNamespace:
    return SimpleNamespace(
        home_win_prob=0.57,
        away_win_prob=0.43,
        confidence_interval_95=(0.52, 0.62),
        model_outputs=[],
        model_weights_used={"marl": 1.0},
        models_activated=["marl"],
        tail_risk_score=0.06,
        blowout_prob=0.12,
        shutout_prob=0.06,
        expected_total_runs=9.0,
        recommended_side="home",
        recommended_kelly_fraction=0.10,
        edge_vs_market=0.05,
        execution_mode="PAPER_ONLY",
        paper_side="home",
        paper_reason="unit_test",
        paper_regime="favorites",
        applicable_regimes=["favorites"],
        governance_flags={"execution_mode": "PAPER_ONLY"},
        game_type="MLB_REGULAR",
        metrics_pool="MLB_PAPER_ONLY",
        betting_advice="",
        audit_trail={"tradeability": "PAPER_ONLY"},
        warnings=[],
    )


class TestResearchLayer(unittest.TestCase):
    def _make_orchestrator_result(self, record):
        orchestrator = PredictionOrchestrator(marl_predictor=StubMarlPredictor())
        return orchestrator.predict(record, use_hierarchical_mc=False, use_world_model=False)

    def test_production_outputs_unchanged_when_research_disabled(self):
        record = ResearchSpringRecord()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"RESEARCH_MODE": "false", "RESEARCH_DIR": tmpdir}, clear=False):
                baseline = self._make_orchestrator_result(record)
            with patch.dict(os.environ, {"RESEARCH_MODE": "true", "RESEARCH_DIR": tmpdir}, clear=False):
                with patch("research.layer.capture", return_value={"active": True, "captured": True}) as capture_stub:
                    research_on = self._make_orchestrator_result(record)
                capture_stub.assert_called_once()
            self.assertEqual(
                {
                    "home_win_prob": baseline.home_win_prob,
                    "away_win_prob": baseline.away_win_prob,
                    "execution_mode": baseline.execution_mode,
                    "recommended_side": baseline.recommended_side,
                    "recommended_kelly_fraction": baseline.recommended_kelly_fraction,
                    "metrics_pool": baseline.metrics_pool,
                    "betting_advice": baseline.betting_advice,
                    "game_type": baseline.game_type,
                    "paper_side": baseline.paper_side,
                    "paper_reason": baseline.paper_reason,
                    "paper_regime": baseline.paper_regime,
                    "governance_flags": baseline.governance_flags,
                },
                {
                    "home_win_prob": research_on.home_win_prob,
                    "away_win_prob": research_on.away_win_prob,
                    "execution_mode": research_on.execution_mode,
                    "recommended_side": research_on.recommended_side,
                    "recommended_kelly_fraction": research_on.recommended_kelly_fraction,
                    "metrics_pool": research_on.metrics_pool,
                    "betting_advice": research_on.betting_advice,
                    "game_type": research_on.game_type,
                    "paper_side": research_on.paper_side,
                    "paper_reason": research_on.paper_reason,
                    "paper_regime": research_on.paper_regime,
                    "governance_flags": research_on.governance_flags,
                },
            )

    def test_trade_journal_records_prediction_and_settlement(self):
        record = ResearchSpringRecord()
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = ResearchLayer(base_dir=tmpdir, enabled=True)
            result = make_fake_result()
            capture_summary = layer.capture(
                result,
                record=record,
                settlement={
                    "result": "win",
                    "pnl": 6.0,
                    "roi": 0.06,
                    "clv": 0.01,
                    "stake": 100.0,
                    "timestamp": "2026-03-30T12:00:00Z",
                },
            )
            ledger = load_jsonl(Path(capture_summary["ledger_path"]))
            self.assertEqual(len(ledger), 2)
            prediction, settlement = ledger
            self.assertEqual(prediction["event_type"], "prediction")
            self.assertEqual(prediction["result"], "unknown")
            self.assertEqual(settlement["event_type"], "settlement")
            self.assertEqual(settlement["result"], "win")
            self.assertEqual(settlement["pnl"], 6.0)
            self.assertEqual(settlement["roi"], 0.06)
            self.assertEqual(Path(capture_summary["ledger_path"]).parent.resolve(), Path(tmpdir).resolve())
            self.assertTrue(Path(capture_summary["roi_path"]).exists())

    def test_roi_tracking_and_drawdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = ResearchLayer(base_dir=tmpdir, enabled=True)
            result = make_fake_result()
            layer.capture(
                result,
                record=ResearchSpringRecord(game_id="G1", game_time_utc="2026-03-30T12:00:00Z"),
                settlement={
                    "result": "win",
                    "pnl": 6.0,
                    "roi": 0.06,
                    "stake": 100.0,
                    "timestamp": "2026-03-30T12:00:00Z",
                },
            )
            layer.capture(
                result,
                record=ResearchSpringRecord(game_id="G2", game_time_utc="2026-03-31T12:00:00Z"),
                settlement={
                    "result": "loss",
                    "pnl": -6.0,
                    "roi": -0.06,
                    "stake": 100.0,
                    "timestamp": "2026-03-31T12:00:00Z",
                },
            )
            roi = load_json(Path(tmpdir) / "roi_tracking.json", {})
            self.assertAlmostEqual(roi["daily"]["2026-03-30"]["roi"], 0.06, places=4)
            self.assertAlmostEqual(roi["daily"]["2026-03-31"]["roi"], -0.06, places=4)
            self.assertEqual(roi["sample_size"], 2)
            self.assertGreater(roi["max_drawdown_pct"], 0.0)
            self.assertEqual(roi["current_bankroll"], 100.0)

    def test_triggers_postmortem_and_insights_fire(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = ResearchLayer(base_dir=tmpdir, enabled=True)
            result = make_fake_result()
            layer.capture(
                result,
                record=ResearchSpringRecord(game_id="POS"),
                settlement={
                    "result": "win",
                    "pnl": 8.0,
                    "roi": 0.08,
                    "stake": 100.0,
                    "timestamp": "2026-03-30T12:00:00Z",
                },
            )
            layer.capture(
                result,
                record=ResearchSpringRecord(game_id="NEG", game_time_utc="2026-03-31T12:00:00Z"),
                settlement={
                    "result": "loss",
                    "pnl": -8.0,
                    "roi": -0.08,
                    "stake": 100.0,
                    "timestamp": "2026-03-31T12:00:00Z",
                },
            )
            triggers = load_json(Path(tmpdir) / "triggers_log.json", [])
            self.assertTrue(any(row["direction"] == "positive" for row in triggers))
            self.assertTrue(any(row["direction"] == "negative" for row in triggers))
            reports = list((Path(tmpdir) / "postmortem_reports").glob("*.md"))
            self.assertGreaterEqual(len(reports), 1)
            report_text = reports[0].read_text(encoding="utf-8")
            self.assertIn("Performance Summary", report_text)
            self.assertIn("Decision Quality", report_text)
            self.assertIn("Root Cause Analysis", report_text)
            insights = load_json(Path(tmpdir) / "strategy_insights" / "latest.json", {})
            self.assertIn("best_performing_regimes", insights)
            self.assertIn("worst_performing_regimes", insights)
            self.assertIn("edge_stability", insights)
            self.assertIn("signal_decay", insights)

    def test_no_production_data_contamination(self):
        record = ResearchSpringRecord()
        with tempfile.TemporaryDirectory() as tmpdir:
            layer = ResearchLayer(base_dir=tmpdir, enabled=True)
            result = make_fake_result()
            summary = layer.capture(
                result,
                record=record,
                settlement={
                    "result": "win",
                    "pnl": 5.0,
                    "roi": 0.05,
                    "stake": 100.0,
                    "timestamp": "2026-03-30T12:00:00Z",
                },
            )
            for key in ("ledger_path", "roi_path", "insights_path"):
                self.assertTrue(str(Path(summary[key]).resolve()).startswith(str(Path(tmpdir).resolve())))
            self.assertFalse(Path("data/research").exists())


if __name__ == "__main__":
    unittest.main()
