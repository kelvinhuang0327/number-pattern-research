from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.layer import ResearchLayer
from research.settlement_ingestion import SettlementIngestionEngine
from research.skip_day_policy import ACTIVE_DAY, PARTIAL_DAY, SKIPPED_DAY
from research.utils import load_json, load_jsonl


@dataclass
class SkipDayRecord:
    game_id: str
    league: str = "MLB"
    tournament: str = "MLB"
    home_team: str = "BOS"
    away_team: str = "NYY"
    game_time_utc: str = "2026-03-30T18:00:00Z"
    round_name: str = "Regular"
    market_home_prob: float = 0.54
    odds: dict = field(default_factory=lambda: {"home_ml": -118, "away_ml": 108, "book": "test"})
    game_type: str = "MLB_REGULAR"


def make_result(side: str = "home") -> SimpleNamespace:
    return SimpleNamespace(
        home_win_prob=0.57 if side == "home" else 0.43,
        away_win_prob=0.43 if side == "home" else 0.57,
        confidence_interval_95=(0.52, 0.62),
        model_outputs=[],
        model_weights_used={"marl": 1.0},
        models_activated=["marl"],
        tail_risk_score=0.06,
        blowout_prob=0.12,
        shutout_prob=0.06,
        expected_total_runs=9.0,
        recommended_side=side,
        recommended_kelly_fraction=0.10,
        edge_vs_market=0.05,
        execution_mode="PAPER_ONLY",
        paper_side=side,
        paper_reason="unit_test",
        paper_regime="favorites" if side == "home" else "underdogs",
        applicable_regimes=["favorites"],
        governance_flags={"execution_mode": "PAPER_ONLY"},
        game_type="MLB_REGULAR",
        metrics_pool="MLB_PAPER_ONLY",
        betting_advice="",
        audit_trail={"tradeability": "PAPER_ONLY"},
        warnings=[],
    )


class TestSkipDayPolicy(unittest.TestCase):
    def _seed_prediction(self, base_dir: str, game_id: str, *, side: str = "home", game_time: str = "2026-03-30T18:00:00Z"):
        layer = ResearchLayer(base_dir=base_dir, enabled=True)
        layer.capture(make_result(side=side), record=SkipDayRecord(game_id=game_id, game_time_utc=game_time))

    def _write_settlements(self, tmpdir: str, rows: list[dict]) -> Path:
        input_path = Path(tmpdir) / "settlements.json"
        input_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return input_path

    def test_skipped_day_records_diagnostics_and_excludes_roi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = self._write_settlements(
                tmpdir,
                [
                    {
                        "game_id": "SKIP-001",
                        "result": "home_win",
                        "final_score": "5-2",
                        "settlement_time": "2026-03-30T23:00:00Z",
                    }
                ],
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            summary = engine.ingest_file(str(input_path))

            self.assertEqual(summary["settled_count"], 0)
            self.assertEqual(summary["skipped_missing_prediction"], 1)
            self.assertEqual(summary["pending_count"], 0)

            ledger = load_jsonl(Path(summary["ledger_path"]))
            self.assertEqual(ledger, [])

            roi = load_json(Path(summary["roi_path"]), {})
            self.assertEqual(roi["sample_size"], 0)
            self.assertEqual(roi["current_bankroll"], roi["initial_bankroll"])

            registry = load_jsonl(Path(summary["daily_registry_path"]))
            self.assertEqual(len(registry), 1)
            self.assertEqual(registry[0]["status"], SKIPPED_DAY)
            self.assertEqual(registry[0]["prediction_count"], 0)
            self.assertEqual(registry[0]["game_count_detected"], 1)

            diagnostics = load_json(Path(summary["missed_prediction_days_path"]), {})
            self.assertEqual(len(diagnostics["entries"]), 1)
            self.assertEqual(diagnostics["entries"][0]["status"], SKIPPED_DAY)
            self.assertTrue(diagnostics["entries"][0]["results_ingested"])

    def test_partial_day_is_detected_and_does_not_pollute_pending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "PARTIAL-001", side="home")
            input_path = self._write_settlements(
                tmpdir,
                [
                    {
                        "game_id": "PARTIAL-001",
                        "result": "home_win",
                        "final_score": "6-3",
                        "settlement_time": "2026-03-30T22:00:00Z",
                    },
                    {
                        "game_id": "PARTIAL-002",
                        "result": "away_win",
                        "final_score": "1-4",
                        "settlement_time": "2026-03-30T23:00:00Z",
                    },
                ],
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            summary = engine.ingest_file(str(input_path))

            self.assertEqual(summary["settled_count"], 1)
            self.assertEqual(summary["skipped_missing_prediction"], 1)
            self.assertEqual(summary["pending_count"], 0)

            registry = load_jsonl(Path(summary["daily_registry_path"]))
            self.assertEqual(registry[-1]["status"], PARTIAL_DAY)
            self.assertEqual(registry[-1]["prediction_count"], 1)
            self.assertEqual(registry[-1]["game_count_detected"], 2)

            diagnostics = load_json(Path(summary["missed_prediction_days_path"]), {})
            self.assertEqual(diagnostics["entries"][-1]["status"], PARTIAL_DAY)
            self.assertEqual(diagnostics["entries"][-1]["games_found"], 2)
            self.assertEqual(diagnostics["entries"][-1]["prediction_events"], 1)

            pending = load_json(Path(summary["pending_path"]), {})
            self.assertEqual(pending["pending_count"], 0)
            self.assertEqual(pending["entries"], [])

    def test_active_day_still_works_normally(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "ACTIVE-001", side="home")
            input_path = self._write_settlements(
                tmpdir,
                [
                    {
                        "game_id": "ACTIVE-001",
                        "result": "home_win",
                        "final_score": "7-2",
                        "settlement_time": "2026-03-30T21:00:00Z",
                    }
                ],
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            summary = engine.ingest_file(str(input_path))

            self.assertEqual(summary["settled_count"], 1)
            self.assertEqual(summary["skipped_missing_prediction"], 0)

            registry = load_jsonl(Path(summary["daily_registry_path"]))
            self.assertEqual(registry[-1]["status"], ACTIVE_DAY)
            self.assertEqual(registry[-1]["prediction_count"], 1)
            self.assertEqual(registry[-1]["game_count_detected"], 1)

            diagnostics = load_json(Path(summary["missed_prediction_days_path"]), {})
            self.assertEqual(diagnostics.get("entries", []), [])

            roi = load_json(Path(summary["roi_path"]), {})
            self.assertEqual(roi["sample_size"], 1)
            self.assertGreater(roi["current_bankroll"], roi["initial_bankroll"])

    def test_rerunning_skipped_day_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = self._write_settlements(
                tmpdir,
                [
                    {
                        "game_id": "SKIP-IDEMP-001",
                        "result": "away_win",
                        "final_score": "2-5",
                        "settlement_time": "2026-03-30T23:30:00Z",
                    }
                ],
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            first = engine.ingest_file(str(input_path))
            second = engine.ingest_file(str(input_path))

            self.assertEqual(first["skipped_missing_prediction"], 1)
            self.assertEqual(second["skipped_existing_settlement"], 0)
            self.assertEqual(second["skipped_missing_prediction"], 1)

            registry = load_jsonl(Path(first["daily_registry_path"]))
            self.assertEqual(len(registry), 1)
            self.assertEqual(registry[0]["status"], SKIPPED_DAY)

            diagnostics = load_json(Path(first["missed_prediction_days_path"]), {})
            self.assertEqual(len(diagnostics["entries"]), 1)
            self.assertEqual(diagnostics["entries"][0]["status"], SKIPPED_DAY)


if __name__ == "__main__":
    unittest.main()
