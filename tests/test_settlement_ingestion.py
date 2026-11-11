from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.layer import ResearchLayer
from research.settlement_ingestion import SettlementIngestionEngine
from research.utils import load_json, load_jsonl


@dataclass
class SettlementTestRecord:
    game_id: str
    league: str = "MLB"
    tournament: str = "MLB"
    home_team: str = "BOS"
    away_team: str = "NYY"
    game_time_utc: str = "2026-03-30T18:00:00Z"
    round_name: str = "Regular"
    market_home_prob: float = 0.50
    odds: dict = field(default_factory=lambda: {"home_ml": -100, "away_ml": 100, "book": "test"})
    game_type: str = "MLB_REGULAR"


def make_fake_result(side: str = "home", kelly: float = 100.0) -> SimpleNamespace:
    return SimpleNamespace(
        home_win_prob=0.58 if side == "home" else 0.42,
        away_win_prob=0.42 if side == "home" else 0.58,
        confidence_interval_95=(0.52, 0.62),
        model_outputs=[],
        model_weights_used={"marl": 1.0},
        models_activated=["marl"],
        tail_risk_score=0.06,
        blowout_prob=0.12,
        shutout_prob=0.06,
        expected_total_runs=9.0,
        recommended_side=side,
        recommended_kelly_fraction=kelly,
        edge_vs_market=0.08,
        execution_mode="PAPER_ONLY",
        paper_side=side,
        paper_reason="unit_test",
        paper_regime="favorites" if side == "home" else "underdogs",
        applicable_regimes=["favorites", "underdogs"],
        governance_flags={"execution_mode": "PAPER_ONLY"},
        game_type="MLB_REGULAR",
        metrics_pool="MLB_PAPER_ONLY",
        betting_advice="",
        audit_trail={"tradeability": "PAPER_ONLY"},
        warnings=[],
    )


class TestSettlementIngestion(unittest.TestCase):
    def _seed_prediction(
        self,
        base_dir: str,
        game_id: str,
        side: str = "home",
        kelly: float = 100.0,
        game_time: str = "2026-03-30T18:00:00Z",
        timestamp: str = None,
    ):
        layer = ResearchLayer(base_dir=base_dir, enabled=True)
        result = make_fake_result(side=side, kelly=kelly)
        record = SettlementTestRecord(game_id=game_id, game_time_utc=game_time)
        if timestamp is None:
            layer.capture(result, record=record)
            return
        with patch("research.trade_journal.utc_now_iso", return_value=timestamp):
            layer.capture(result, record=record)

    def test_json_ingestion_matches_and_sets_roi(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "GAME-001", side="home", kelly=100.0)
            input_path = Path(tmpdir) / "settlements.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "game_id": "GAME-001",
                            "result": "home_win",
                            "final_score": "6-3",
                            "settlement_time": "2026-03-30T22:00:00Z",
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            summary = engine.ingest_file(str(input_path))

            ledger = load_jsonl(Path(summary["ledger_path"]))
            self.assertEqual(len(ledger), 2)
            settlement = ledger[-1]
            self.assertEqual(settlement["event_type"], "settlement")
            self.assertEqual(settlement["result"], "win")
            self.assertEqual(settlement["game_id"], "GAME-001")
            self.assertEqual(settlement["pnl"], 100.0)
            self.assertEqual(settlement["roi"], 1.0)
            self.assertEqual(summary["settled_count"], 1)

            roi = load_json(Path(summary["roi_path"]), {})
            self.assertEqual(roi["sample_size"], 1)
            self.assertAlmostEqual(roi["daily"]["2026-03-30"]["roi"], 1.0, places=4)
            self.assertGreater(roi["current_bankroll"], roi["initial_bankroll"])

    def test_csv_ingestion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "GAME-CSV-001", side="away", kelly=50.0)
            input_path = Path(tmpdir) / "settlements.csv"
            with input_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=["game_id", "result", "final_score", "settlement_time"])
                writer.writeheader()
                writer.writerow(
                    {
                        "game_id": "GAME-CSV-001",
                        "result": "away_win",
                        "final_score": "2-5",
                        "settlement_time": "2026-03-30T23:15:00Z",
                    }
                )

            engine = SettlementIngestionEngine(base_dir=tmpdir)
            first = engine.ingest_file(str(input_path))
            second = engine.ingest_file(str(input_path))

            ledger = load_jsonl(Path(first["ledger_path"]))
            self.assertEqual(len(ledger), 2)
            self.assertEqual(first["settled_count"], 1)
            self.assertEqual(second["settled_count"], 0)
            self.assertEqual(second["skipped_existing_settlement"], 1)
            self.assertEqual(len(load_jsonl(Path(second["ledger_path"]))), 2)

    def test_triggers_postmortem_and_pending_settlements(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "GAME-POS", side="home", kelly=100.0, game_time="2026-03-28T12:00:00Z")
            self._seed_prediction(
                tmpdir,
                "GAME-PEND",
                side="home",
                kelly=100.0,
                game_time="2026-03-25T12:00:00Z",
                timestamp="2026-03-25T12:00:00Z",
            )
            self._seed_prediction(tmpdir, "GAME-NEG", side="away", kelly=100.0, game_time="2026-03-29T12:00:00Z")

            input_path = Path(tmpdir) / "settlements.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "game_id": "GAME-POS",
                            "result": "home_win",
                            "final_score": "7-2",
                            "settlement_time": "2026-03-29T12:00:00Z",
                        },
                        {
                            "game_id": "GAME-NEG",
                            "result": "home_win",
                            "final_score": "1-4",
                            "settlement_time": "2026-03-30T13:00:00Z",
                        },
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            engine = SettlementIngestionEngine(base_dir=tmpdir, pending_after_hours=24.0)
            summary = engine.ingest_file(str(input_path))

            triggers = load_json(Path(tmpdir) / "triggers_log.json", [])
            self.assertTrue(any(row["direction"] == "positive" for row in triggers))
            self.assertTrue(any(row["direction"] == "negative" for row in triggers))
            trigger_index = load_json(Path(tmpdir) / "trigger_index.json", [])
            self.assertGreaterEqual(len(trigger_index), 2)
            reports = list((Path(tmpdir) / "postmortem_reports").glob("*.md"))
            self.assertGreaterEqual(len(reports), 2)
            report_text = reports[0].read_text(encoding="utf-8")
            self.assertIn("Performance Summary", report_text)
            self.assertIn("Regime Breakdown", report_text)
            self.assertIn("Actionable Recommendations", report_text)
            pending = load_json(Path(tmpdir) / "pending_settlements.json", {})
            self.assertEqual(pending["pending_count"], 1)
            self.assertEqual(pending["entries"][0]["game_id"], "GAME-PEND")
            self.assertGreaterEqual(summary["trigger_count"], 2)

    def test_cli_ingests_and_isolated_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._seed_prediction(tmpdir, "GAME-CLI-001", side="home", kelly=100.0)
            input_path = Path(tmpdir) / "settlements.json"
            input_path.write_text(
                json.dumps(
                    [
                        {
                            "game_id": "GAME-CLI-001",
                            "result": "home_win",
                            "final_score": "4-1",
                            "settlement_time": "2026-03-30T21:00:00Z",
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            root_ledger = Path("research/trade_ledger.jsonl")
            root_roi = Path("research/roi_tracking.json")
            ledger_mtime = root_ledger.stat().st_mtime if root_ledger.exists() else None
            roi_mtime = root_roi.stat().st_mtime if root_roi.exists() else None

            script = Path(__file__).resolve().parents[1] / "scripts" / "ingest_research_settlements.py"
            env = os.environ.copy()
            env["RESEARCH_DIR"] = tmpdir
            env["RESEARCH_MODE"] = "true"
            proc = subprocess.run(
                [sys.executable, str(script), "--input", str(input_path), "--research-dir", tmpdir],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            output = json.loads(proc.stdout)
            self.assertEqual(output["settled_count"], 1)
            self.assertTrue(str(Path(output["ledger_path"]).resolve()).startswith(str(Path(tmpdir).resolve())))
            self.assertTrue(str(Path(output["roi_path"]).resolve()).startswith(str(Path(tmpdir).resolve())))
            if ledger_mtime is None:
                self.assertFalse(root_ledger.exists())
            else:
                self.assertAlmostEqual(root_ledger.stat().st_mtime, ledger_mtime, places=6)
            if roi_mtime is None:
                self.assertFalse(root_roi.exists())
            else:
                self.assertAlmostEqual(root_roi.stat().st_mtime, roi_mtime, places=6)


if __name__ == "__main__":
    unittest.main()
