from __future__ import annotations

import os
import pickle
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.domain.schemas import Matchup, PitcherSnapshot, SubModelResult, TeamSnapshot
from wbc_backend.features.advanced import build_advanced_features, compute_clutch_index
from wbc_backend.models.ensemble import predict_matchup
from wbc_backend.models.gbm_stack import RealGBMStack
from wbc_backend.models.lightgbm_model import LightGBMModel
from wbc_backend.models.neural_net import NeuralNetModel
from wbc_backend.models.stacking import StackingModel


class TestAdvancedFeatureStability(unittest.TestCase):
    def test_compute_clutch_index_returns_bounded_scalar(self):
        team = TeamSnapshot(
            team="TPE",
            elo=1500,
            batting_woba=0.320,
            batting_ops_plus=100,
            pitching_fip=3.8,
            pitching_whip=1.25,
            pitching_stuff_plus=100,
            der=0.7,
            bullpen_depth=8.0,
            pitch_limit=65,
            clutch_woba=0.335,
        )
        idx = compute_clutch_index(team=team, lineup=[])
        self.assertIsInstance(idx, float)
        self.assertGreaterEqual(idx, -0.5)
        self.assertLessEqual(idx, 0.5)

    def test_high_value_pitcher_features_flow_into_feature_dict(self):
        matchup = Matchup(
            game_id="TPE_AUS_002",
            tournament="WBC2026",
            game_time_utc="2026-03-06T10:00:00Z",
            home=TeamSnapshot(
                team="TPE",
                elo=1510,
                batting_woba=0.330,
                batting_ops_plus=108,
                pitching_fip=3.6,
                pitching_whip=1.20,
                pitching_stuff_plus=104,
                der=0.705,
                bullpen_depth=8.2,
                pitch_limit=65,
            ),
            away=TeamSnapshot(
                team="AUS",
                elo=1470,
                batting_woba=0.316,
                batting_ops_plus=98,
                pitching_fip=4.1,
                pitching_whip=1.31,
                pitching_stuff_plus=97,
                der=0.694,
                bullpen_depth=7.4,
                pitch_limit=65,
            ),
            home_sp=PitcherSnapshot(
                name="Home SP",
                team="TPE",
                era=3.2,
                fip=3.1,
                whip=1.12,
                k_per_9=9.8,
                bb_per_9=2.2,
                stuff_plus=112,
                ip_last_30=26.0,
                era_last_3=2.8,
                pitch_count_last_3d=0,
                fastball_velo=95.0,
                high_leverage_era=2.9,
                pitch_mix={"FF": 50, "SL": 30, "CH": 20},
                recent_fastball_velos=[95.4, 95.1, 94.8],
                career_fastball_velo=94.5,
                woba_vs_left=0.285,
                woba_vs_right=0.305,
                innings_last_14d=12.0,
                season_avg_innings_per_14d=10.0,
                recent_spin_rate=2450.0,
                career_spin_rate_mean=2400.0,
                career_spin_rate_std=25.0,
            ),
            away_sp=PitcherSnapshot(
                name="Away SP",
                team="AUS",
                era=4.3,
                fip=4.1,
                whip=1.28,
                k_per_9=8.1,
                bb_per_9=3.1,
                stuff_plus=101,
                ip_last_30=21.0,
                era_last_3=4.8,
                pitch_count_last_3d=0,
                fastball_velo=92.0,
                high_leverage_era=4.5,
                pitch_mix={"FF": 70, "CU": 20, "CH": 10},
                recent_fastball_velos=[91.8, 91.5, 91.7],
                career_fastball_velo=92.4,
                woba_vs_left=0.335,
                woba_vs_right=0.320,
                innings_last_14d=8.0,
                season_avg_innings_per_14d=10.0,
                recent_spin_rate=2210.0,
                career_spin_rate_mean=2250.0,
                career_spin_rate_std=20.0,
            ),
        )

        feats = build_advanced_features(matchup)

        for key in (
            "pitch_arsenal_entropy_diff",
            "velocity_trend_diff",
            "platoon_split_diff",
            "recent_inning_load_diff",
            "spin_rate_zscore_diff",
        ):
            self.assertIn(key, feats.feature_dict)

        self.assertNotEqual(feats.feature_dict["pitch_arsenal_entropy_diff"], 0.0)
        self.assertGreater(feats.feature_dict["recent_inning_load_diff"], 0.0)


class TestEnsembleStability(unittest.TestCase):
    def test_predict_matchup_handles_missing_optional_odds_field(self):
        home = TeamSnapshot(
            team="TPE",
            elo=1510,
            batting_woba=0.330,
            batting_ops_plus=108,
            pitching_fip=3.6,
            pitching_whip=1.20,
            pitching_stuff_plus=104,
            der=0.705,
            bullpen_depth=8.2,
            pitch_limit=65,
        )
        away = TeamSnapshot(
            team="AUS",
            elo=1470,
            batting_woba=0.316,
            batting_ops_plus=98,
            pitching_fip=4.1,
            pitching_whip=1.31,
            pitching_stuff_plus=97,
            der=0.694,
            bullpen_depth=7.4,
            pitch_limit=65,
        )
        matchup = Matchup(
            game_id="TPE_AUS_001",
            tournament="WBC2026",
            game_time_utc="2026-03-05T10:00:00Z",
            home=home,
            away=away,
            round_name="Pool",
        )

        fake_adv = SimpleNamespace(
            home_sp_fatigue=0.15,
            away_sp_fatigue=0.12,
            home_bullpen_stress=0.21,
            away_bullpen_stress=0.18,
            home_matchup_edge=0.04,
            away_matchup_edge=0.01,
            home_clutch_index=0.05,
            away_clutch_index=0.01,
            feature_dict={"elo_diff": 40.0},
        )

        with patch("wbc_backend.models.ensemble.build_advanced_features", return_value=fake_adv), \
             patch("wbc_backend.models.ensemble.elo_model.predict", return_value=SubModelResult("elo", 0.55, 0.45, confidence=0.6)), \
             patch("wbc_backend.models.ensemble.poisson_model.predict", return_value=SubModelResult("poisson", 0.54, 0.46, expected_home_runs=4.1, expected_away_runs=3.7, confidence=0.58)), \
             patch("wbc_backend.models.ensemble.bayesian_model.predict", return_value=SubModelResult("bayesian", 0.56, 0.44, confidence=0.59)), \
             patch("wbc_backend.models.ensemble.baseline_model.predict", return_value=SubModelResult("baseline", 0.53, 0.47, confidence=0.52)), \
             patch("wbc_backend.models.ensemble.RealGBMStack") as mock_gbm, \
             patch("wbc_backend.models.ensemble.StackingModel") as mock_stack, \
             patch("wbc_backend.models.neural_net.NeuralNetModel") as mock_nn:
            mock_gbm.return_value.predict_single.return_value = SubModelResult("gbm", 0.57, 0.43, confidence=0.61)
            mock_nn.return_value.predict_single.return_value = SubModelResult("nn", 0.58, 0.42, confidence=0.60)
            mock_stack.return_value.predict.return_value = (0.59, 0.41, 0.66)

            pred = predict_matchup(matchup)

        self.assertGreaterEqual(pred.home_win_prob, 0.03)
        self.assertLessEqual(pred.home_win_prob, 0.97)
        self.assertIn("snr", pred.diagnostics)
        self.assertIn("regime", pred.diagnostics)
        self.assertGreater(pred.confidence_score, 0.0)


class TestArtifactSchemaStability(unittest.TestCase):
    def test_lightgbm_ignores_stale_feature_count_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            model = LightGBMModel()
            model.artifact_path = Path(td) / "lgbm.pkl"
            with open(model.artifact_path, "wb") as f:
                pickle.dump({"model": object(), "feature_count": 1}, f)

            model._load()
            self.assertIsNone(model.model)

    def test_neural_net_ignores_stale_feature_count_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            model = NeuralNetModel()
            model.artifact_path = Path(td) / "nn.pkl"
            with open(model.artifact_path, "wb") as f:
                pickle.dump(
                    {
                        "weights": [],
                        "biases": [],
                        "x_mean": [0.0],
                        "x_std": [1.0],
                        "feature_count": 1,
                    },
                    f,
                )

            model._load()
            self.assertFalse(model._fitted)


class TestGBMStackStability(unittest.TestCase):
    def test_predict_single_preserves_probability_direction(self):
        class FakeModel:
            def __init__(self, prob: float):
                self.prob = prob

            def predict_single(self, feature_dict):
                return SubModelResult("fake", self.prob, 1.0 - self.prob, confidence=0.5)

        stack = RealGBMStack()
        stack.models = {
            "a": FakeModel(0.2),
            "b": FakeModel(0.3),
            "c": FakeModel(0.4),
        }
        stack.weights = np.array([1 / 3, 1 / 3, 1 / 3], dtype=float)
        stack.bias = 0.0

        result = stack.predict_single({"elo_diff": -10.0})

        self.assertLess(result.home_win_prob, 0.5)
        self.assertGreater(result.away_win_prob, 0.5)


class TestStackingStability(unittest.TestCase):
    def test_predict_falls_back_when_artifact_model_names_do_not_match_live_models(self):
        stack = StackingModel()
        stack.weights = np.array([0.8, -0.6, 0.4], dtype=float)
        stack.bias = -0.2
        stack.model_names = ["xgboost", "lightgbm", "neural_net"]

        sub_results = [
            SubModelResult("elo", 0.64, 0.36, confidence=0.6),
            SubModelResult("poisson", 0.75, 0.25, confidence=0.65),
            SubModelResult("bayesian", 0.77, 0.23, confidence=0.7),
            SubModelResult("baseline", 0.58, 0.42, confidence=0.4),
            SubModelResult("real_gbm_stack", 0.93, 0.07, confidence=0.8),
            SubModelResult("neural_net", 0.84, 0.16, confidence=0.7),
        ]

        home_wp, away_wp, confidence = stack.predict(sub_results)

        self.assertGreater(home_wp, 0.5)
        self.assertLess(away_wp, 0.5)
        self.assertGreater(confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
