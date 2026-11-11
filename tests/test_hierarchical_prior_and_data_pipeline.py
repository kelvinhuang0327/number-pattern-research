from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.config.settings import AppConfig
from wbc_backend.data.validator import load_dataset_frame, validate_dataset
from wbc_backend.domain.schemas import Matchup, TeamSnapshot
from wbc_backend.features.advanced import FEATURE_NAMES
from wbc_backend.models.bayesian import hierarchical_bayesian_win_prob, predict
from wbc_backend.models.trainer import _df_to_features


ASPLAYED_SAMPLE = """Date,Start Time (Sask),Start Time (EDT),Away,Away Score,Home,Home Score,Status,Away Starter,Home Starter,Winner,Loser,Save
2025-03-18,4:10 AM,6:10 AM,Los Angeles Dodgers,4,Chicago Cubs,1,Final,Yoshinobu Yamamoto,Shota Imanaga,Yoshinobu Yamamoto,Ben Brown,Tanner Scott
2025-03-19,4:10 AM,6:10 AM,Los Angeles Dodgers,6,Chicago Cubs,3,Final,Roki Sasaki,Justin Steele,Landon Knack,Justin Steele,Alex Vesia
2025-03-27,1:05 PM,3:05 PM,Milwaukee Brewers,2,New York Yankees,4,Final,Freddy Peralta,Carlos Rodón,Carlos Rodón,Freddy Peralta,Devin Williams
2025-03-28,1:05 PM,3:05 PM,Milwaukee Brewers,3,New York Yankees,1,Final,DL Hall,Marcus Stroman,DL Hall,Marcus Stroman,Trevor Megill
"""


class TestMLB2025Normalization(unittest.TestCase):
    def test_validator_normalizes_asplayed_latin1_schema(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "mlb-2025-asplayed.csv"
            csv_path.write_bytes(ASPLAYED_SAMPLE.replace("Rodón", "Rod\xf3n").encode("latin1"))

            df = load_dataset_frame(str(csv_path))
            self.assertIsNotNone(df)
            assert df is not None
            for column in ("date", "away_team", "home_team", "away_score", "home_score", "away_starter", "home_starter"):
                self.assertIn(column, df.columns)

            base = AppConfig()
            config = replace(base, sources=replace(base.sources, mlb_2025_csv=str(csv_path)))
            report = validate_dataset("MLB_2025", config)
            self.assertTrue(report.is_valid)
            self.assertGreater(report.completeness_pct, 0.99)

    def test_training_matrix_uses_real_game_log_without_synthetic_noise(self):
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "mlb-2025-asplayed.csv"
            csv_path.write_bytes(ASPLAYED_SAMPLE.replace("Rodón", "Rod\xf3n").encode("latin1"))
            df = load_dataset_frame(str(csv_path))
            assert df is not None

            X, y = _df_to_features(df)

            self.assertEqual(X.shape, (4, len(FEATURE_NAMES)))
            self.assertFalse(np.isnan(X).any())
            self.assertEqual(y.tolist(), [0.0, 0.0, 1.0, 0.0])
            self.assertNotEqual(float(X[1][FEATURE_NAMES.index("elo_diff")]), 0.0)
            self.assertNotEqual(float(X[1][FEATURE_NAMES.index("rpg_diff")]), 0.0)


class TestHierarchicalPriorRuntime(unittest.TestCase):
    def _make_matchup(self, sample_size: int) -> Matchup:
        return Matchup(
            game_id=f"HBP_{sample_size}",
            tournament="WBC2026",
            game_time_utc="2026-03-10T10:00:00Z",
            round_name="Pool C",
            home=TeamSnapshot(
                team="TPE",
                elo=1560,
                batting_woba=0.345,
                batting_ops_plus=118,
                pitching_fip=3.25,
                pitching_whip=1.14,
                pitching_stuff_plus=108,
                der=0.715,
                bullpen_depth=8.6,
                pitch_limit=65,
                roster_strength_index=88.0,
                sample_size=sample_size,
                league_prior_strength=18.0,
                runs_per_game=5.2,
                win_pct_last_10=0.7,
            ),
            away=TeamSnapshot(
                team="AUS",
                elo=1490,
                batting_woba=0.314,
                batting_ops_plus=95,
                pitching_fip=4.35,
                pitching_whip=1.31,
                pitching_stuff_plus=96,
                der=0.692,
                bullpen_depth=7.3,
                pitch_limit=65,
                roster_strength_index=75.0,
                sample_size=sample_size,
                league_prior_strength=6.0,
                runs_per_game=3.9,
                win_pct_last_10=0.4,
            ),
        )

    def test_low_sample_shrinks_more_toward_prior(self):
        low_prob, _, low_diag = hierarchical_bayesian_win_prob(self._make_matchup(8))
        high_prob, _, high_diag = hierarchical_bayesian_win_prob(self._make_matchup(180))

        self.assertLess(abs(low_prob - low_diag["prior_home"]), abs(high_prob - high_diag["prior_home"]))
        self.assertLess(low_diag["home_shrink"], high_diag["home_shrink"])

    def test_predict_exposes_hierarchical_diagnostics(self):
        result = predict(self._make_matchup(80))
        self.assertIn("prior_home", result.diagnostics)
        self.assertIn("home_shrink", result.diagnostics)
        self.assertGreater(result.home_win_prob, 0.5)


if __name__ == "__main__":
    unittest.main()
