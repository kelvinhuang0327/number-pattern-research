from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.betting.optimizer import find_top_bets
from wbc_backend.config.settings import AppConfig
from wbc_backend.domain.schemas import OddsLine
from wbc_backend.research.runtime import run_research_cycle
from wbc_backend.scheduler.jobs import AutoScheduler


class DummyCLV:
    def __init__(self, *_args, **_kwargs):
        pass

    def predict_closing_odds(self, *_args, **_kwargs):
        return 1.85

    def get_market_efficiency_score(self, *_args, **_kwargs):
        return 0.90


class TestOptimizerRegression(unittest.TestCase):
    def test_confidence_not_cascading_between_candidates(self):
        odds = [
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
            OddsLine(
                sportsbook="BookB",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.62}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.65,
                config=config,
            )

        self.assertEqual(len(bets), 2)
        self.assertAlmostEqual(bets[0].confidence, bets[1].confidence, places=4)
        self.assertEqual(bets[0].market_support_state, "intl_only")
        self.assertIn("market_support=intl_only", bets[0].reason)

    def test_reject_gate_blocks_low_confidence_candidates(self):
        odds = [
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.52,
                config=config,
            )

        self.assertEqual(bets, [])

    def test_reject_gate_uses_calibration_to_block_borderline_edges(self):
        odds = [
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.05,
                source_type="intl",
            ),
        ]
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            blocked = find_top_bets(
                odds_lines=odds,
                true_probs={"ML_TPE": 0.56},
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.66,
                config=config,
                model_brier=0.29,
                calibration_ece=0.13,
            )
            allowed = find_top_bets(
                odds_lines=odds,
                true_probs={"ML_TPE": 0.65},
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.70,
                config=config,
                model_brier=0.29,
                calibration_ece=0.13,
            )

        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 1)
        self.assertIn("brier_penalty", allowed[0].reason)
        self.assertIn("ece_penalty", allowed[0].reason)

    def test_tsl_bets_blocked_when_feed_is_officially_blocked(self):
        odds = [
            OddsLine(
                sportsbook="TSL",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="tsl",
            ),
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                tsl_feed_status={
                    "success": False,
                    "note": "modern_pre_2026-03-13=HTTP Error 403: Forbidden",
                },
            )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sportsbook, "BookA")
        self.assertIn("market_support=intl_only", bets[0].reason)

    def test_tsl_bets_blocked_when_matchup_missing_from_latest_snapshot(self):
        odds = [
            OddsLine(
                sportsbook="TSL",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="tsl",
            ),
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                tsl_feed_status={
                    "success": True,
                    "note": "modern_pre_zh=7",
                },
                tsl_matchup_status={
                    "in_snapshot": False,
                },
            )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sportsbook, "BookA")

    def test_tsl_bets_blocked_when_market_not_listed_in_snapshot(self):
        odds = [
            OddsLine(
                sportsbook="TSL",
                market="RL",
                side="TPE",
                line=-1.5,
                decimal_odds=2.2,
                source_type="tsl",
            ),
            OddsLine(
                sportsbook="BookA",
                market="RL",
                side="TPE",
                line=-1.5,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"RL_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                tsl_feed_status={"success": True, "note": "modern_pre_zh=7"},
                tsl_matchup_status={"in_snapshot": True, "market_codes": ["MNL", "OU"]},
            )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sportsbook, "BookA")
        self.assertIn("market_support=intl_only", bets[0].reason)

    def test_tsl_bets_keep_direct_support_when_market_is_listed_in_snapshot(self):
        odds = [
            OddsLine(
                sportsbook="TSL",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="tsl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                tsl_feed_status={"success": True, "note": "modern_pre_zh=7"},
                tsl_matchup_status={"in_snapshot": True, "market_codes": ["MNL", "OU"]},
            )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sportsbook, "TSL")
        self.assertEqual(bets[0].market_support_state, "tsl_direct")
        self.assertIn("market_support=tsl_direct", bets[0].reason)
        self.assertIn("market_env=unknown", bets[0].reason)

    def test_tsl_bets_lose_direct_support_when_snapshot_is_stale(self):
        odds = [
            OddsLine(
                sportsbook="TSL",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="tsl",
            ),
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                tsl_feed_status={"success": True, "note": "modern_pre_zh=7"},
                tsl_matchup_status={"in_snapshot": True, "market_codes": ["MNL"], "is_fresh": False},
            )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].sportsbook, "BookA")
        self.assertIn("market_support=intl_only", bets[0].reason)

    def test_market_environment_weights_international_candidates_by_market_support(self):
        odds = [
            OddsLine(
                sportsbook="BookA",
                market="ML",
                side="TPE",
                line=None,
                decimal_odds=2.2,
                source_type="intl",
            ),
            OddsLine(
                sportsbook="BookB",
                market="RL",
                side="TPE",
                line=-1.5,
                decimal_odds=2.2,
                source_type="intl",
            ),
        ]
        true_probs = {"ML_TPE": 0.60, "RL_TPE": 0.60}
        config = AppConfig()

        with patch("wbc_backend.betting.optimizer.ClosingLineModel", DummyCLV):
            bets = find_top_bets(
                odds_lines=odds,
                true_probs=true_probs,
                home_code="TPE",
                away_code="AUS",
                confidence_score=0.75,
                config=config,
                market_support_by_market={
                    "ML": "direct",
                    "RL": "unlisted_market",
                },
            )

        self.assertEqual(len(bets), 2)
        self.assertEqual(bets[0].market, "ML")
        self.assertIn("market_env=direct", bets[0].reason)
        self.assertIn("market_env=unlisted_market", bets[1].reason)
        self.assertGreater(bets[0].confidence, bets[1].confidence)


class TestRuntimeAndScheduler(unittest.TestCase):
    def test_research_cycle_writes_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "v3_cycle.json"
            payload = run_research_cycle(seed=42, artifact_path=artifact)
            self.assertTrue(artifact.exists())
            self.assertTrue(payload["all_passed"])

            parsed = json.loads(artifact.read_text())
            self.assertEqual(parsed["phase_count"], 6)

    def test_scheduler_registers_research_cycle_task(self):
        scheduler = AutoScheduler(AppConfig())
        scheduler.setup_default_tasks()
        task_names = [t.name for t in scheduler.tasks]
        self.assertIn("research_cycle", task_names)


if __name__ == "__main__":
    unittest.main()
