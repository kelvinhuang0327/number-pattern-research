"""Tests for AlphaFeatureLab — automated feature discovery."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from wbc_backend.intelligence.auto_feature_lab import (
    AlphaFeatureLab,
    FeatureImportance,
    SelectionResult,
)


def _make_df(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic MLB-like pregame feature DataFrame."""
    rng = np.random.RandomState(seed)
    data = {
        "elo_diff": rng.randn(n) * 50,
        "wr_diff": rng.randn(n) * 0.1,
        "rd_diff": rng.randn(n) * 0.5,
        "rf_diff": rng.randn(n) * 0.3,
        "ra_diff": rng.randn(n) * 0.3,
        "bullpen_stress_diff": rng.randn(n) * 0.2,
        "park_hr_factor": 1.0 + rng.randn(n) * 0.1,
        "park_run_factor": 1.0 + rng.randn(n) * 0.1,
    }
    df = pd.DataFrame(data)
    # Target: loosely correlated with elo_diff
    prob = 1 / (1 + np.exp(-0.01 * df["elo_diff"].values))
    df["home_win"] = (rng.rand(n) < prob).astype(float)
    return df


BASE = [
    "elo_diff", "wr_diff", "rd_diff", "rf_diff", "ra_diff",
    "bullpen_stress_diff", "park_hr_factor", "park_run_factor",
]


class TestGenerateCandidates(unittest.TestCase):
    def test_generates_interaction_columns(self):
        lab = AlphaFeatureLab(base_features=BASE, max_candidates=20)
        df = _make_df(100)
        out = lab.generate_candidates(df)

        self.assertGreater(len(lab.candidate_names), 0)
        self.assertLessEqual(len(lab.candidate_names), 20)
        for col in lab.candidate_names:
            self.assertIn(col, out.columns)
            self.assertTrue(col.startswith("alpha_"))

    def test_respects_max_candidates(self):
        lab = AlphaFeatureLab(base_features=BASE, max_candidates=5)
        df = _make_df(50)
        lab.generate_candidates(df)
        self.assertEqual(len(lab.candidate_names), 5)

    def test_no_nan_inf_in_output(self):
        lab = AlphaFeatureLab(base_features=BASE, max_candidates=30)
        df = _make_df(100)
        out = lab.generate_candidates(df)
        for col in lab.candidate_names:
            arr = out[col].to_numpy()
            self.assertFalse(np.any(np.isnan(arr)), f"NaN in {col}")
            self.assertFalse(np.any(np.isinf(arr)), f"Inf in {col}")

    def test_skip_when_too_few_features(self):
        lab = AlphaFeatureLab(base_features=["only_one"])
        df = pd.DataFrame({"only_one": [1, 2, 3]})
        out = lab.generate_candidates(df)
        self.assertEqual(len(lab.candidate_names), 0)
        self.assertEqual(len(out.columns), 1)


class TestRankAndSelect(unittest.TestCase):
    def test_returns_selection_result(self):
        lab = AlphaFeatureLab(base_features=BASE, max_candidates=10)
        df = _make_df(300)
        df = lab.generate_candidates(df)

        features = BASE + lab.candidate_names
        X_train = df.iloc[:200][features]
        y_train = df.iloc[:200]["home_win"].to_numpy()
        X_val = df.iloc[200:][features]
        y_val = df.iloc[200:]["home_win"].to_numpy()

        result = lab.rank_and_select(X_train, y_train, X_val, y_val)

        self.assertIsInstance(result, SelectionResult)
        self.assertGreater(len(result.all_ranked), 0)
        self.assertGreater(len(result.survivors), 0)
        # Base features should always survive (protection rule)
        for bf in BASE:
            self.assertIn(bf, result.survivors)

    def test_importance_ordering(self):
        lab = AlphaFeatureLab(base_features=BASE, max_candidates=6)
        df = _make_df(300)
        df = lab.generate_candidates(df)

        features = BASE + lab.candidate_names
        X_train = df.iloc[:200][features]
        y_train = df.iloc[:200]["home_win"].to_numpy()
        X_val = df.iloc[200:][features]
        y_val = df.iloc[200:]["home_win"].to_numpy()

        result = lab.rank_and_select(X_train, y_train, X_val, y_val)

        # Ranked descending by importance
        means = [fi.importance_mean for fi in result.all_ranked]
        for i in range(len(means) - 1):
            self.assertGreaterEqual(means[i], means[i + 1])

    def test_small_sample_returns_all(self):
        lab = AlphaFeatureLab(base_features=["a", "b"])
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "home_win": [0, 1]})
        result = lab.rank_and_select(
            df[["a", "b"]], df["home_win"].to_numpy(),
            df[["a", "b"]], df["home_win"].to_numpy(),
        )
        # With <30 samples, returns all feature names
        self.assertEqual(result.survivors, ["a", "b"])


class TestStability(unittest.TestCase):
    def test_compute_stability_fractions(self):
        lab = AlphaFeatureLab(base_features=BASE)

        r1 = SelectionResult([], ["a", "b", "c"], ["d"], 0.001)
        r2 = SelectionResult([], ["a", "c"], ["b", "d"], 0.001)
        r3 = SelectionResult([], ["a", "b"], ["c", "d"], 0.001)

        stability = lab.compute_stability([r1, r2, r3])

        self.assertAlmostEqual(stability["a"], 1.0)         # 3/3
        self.assertAlmostEqual(stability["b"], 2 / 3, places=4)  # 2/3
        self.assertAlmostEqual(stability["c"], 2 / 3, places=4)  # 2/3
        self.assertNotIn("d", stability)  # never survived

    def test_empty_windows(self):
        lab = AlphaFeatureLab(base_features=BASE)
        self.assertEqual(lab.compute_stability([]), {})


if __name__ == "__main__":
    unittest.main()
