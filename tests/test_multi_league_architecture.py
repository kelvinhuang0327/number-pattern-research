from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from baseball_scenario_engine.runner import ScenarioRequest, ScenarioRunner
from league_adapters.registry import get_league_adapter, normalize_league_name
from wbc_backend.backtesting.league_backtest import BacktestConfig, LeagueBacktestEngine


@dataclass
class DummyRecord:
    game_id: str
    home_team: str
    away_team: str
    round_name: str = ""
    actual_home_win: int = 1
    weather: dict = None
    odds: dict = None
    pitchers: dict = None
    lineups: dict = None
    bullpen_usage: dict = None
    features: dict = None


class TestLeagueAdapters(unittest.TestCase):
    def test_registry_normalizes_league_names(self):
        self.assertEqual(normalize_league_name("wbc"), "WBC")
        self.assertEqual(normalize_league_name("major_league_baseball"), "MLB")

    def test_get_league_adapter_distinguishes_leagues(self):
        self.assertEqual(get_league_adapter("WBC").name(), "WBC")
        self.assertEqual(get_league_adapter("MLB").name(), "MLB")


class TestScenarioEngine(unittest.TestCase):
    def test_scenario_runner_returns_adjusted_probs(self):
        runner = ScenarioRunner()
        out = runner.run(
            ScenarioRequest(
                league="WBC",
                game_id="WBC26-TEST-001",
                home_team="USA",
                away_team="VEN",
                base_probs={"home_win_prob": 0.62, "away_win_prob": 0.38},
                features={"short_sample_shrinkage": 0.2},
            )
        )
        self.assertEqual(out.league, "WBC")
        self.assertAlmostEqual(out.adjustments["home_win_prob"] + out.adjustments["away_win_prob"], 1.0, places=6)
        self.assertIn("rules", out.diagnostics)


class TestLeagueBacktest(unittest.TestCase):
    def test_backtest_requires_minimum_sample_size(self):
        engine = LeagueBacktestEngine(BacktestConfig(league="MLB", min_sample_size=2))
        records = [
            DummyRecord(game_id="1", home_team="A", away_team="B"),
            DummyRecord(game_id="2", home_team="C", away_team="D"),
        ]

        result = engine.run(records, lambda _: {"home_win_prob": 0.55, "away_win_prob": 0.45})
        self.assertEqual(result.league, "MLB")
        self.assertEqual(result.n_games, 2)
        self.assertTrue(result.brier >= 0.0)
        self.assertTrue(result.logloss >= 0.0)


if __name__ == "__main__":
    unittest.main()
