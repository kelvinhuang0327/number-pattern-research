from __future__ import annotations

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.mlb_model_rebuild import _bet_metrics, _regime_slice_metrics, build_mlb_rebuild_frame, feature_families


class TestMLBModelRebuild(unittest.TestCase):
    def test_feature_family_registry(self):
        families = feature_families()
        self.assertIn("market", families)
        self.assertIn("team", families)
        self.assertIn("starter", families)
        self.assertIn("bullpen", families)
        self.assertIn("lineup_context", families)
        self.assertIn("environment", families)

    def test_rebuild_frame_contains_strict_rows_and_targets(self):
        frame = build_mlb_rebuild_frame()
        self.assertIn("strict_valid", frame.columns)
        self.assertIn("target", frame.columns)
        self.assertGreater(frame["strict_valid"].sum(), 100)

    def test_bet_metrics_ignores_nan_market_rows(self):
        probs = np.array([0.60, 0.48, 0.55])
        market = np.array([0.50, np.nan, 0.51])
        y = np.array([1, 0, 1])
        metrics = _bet_metrics(probs, market, y, threshold=0.01)
        self.assertEqual(metrics["n_bets"], 2)
        self.assertGreater(metrics["clv"], 0.0)

    def test_regime_slice_metrics_reports_stability_and_classification(self):
        frame = build_mlb_rebuild_frame().loc[:, ["market_home_prob", "target"]].head(12).copy()
        frame["market_home_prob"] = np.linspace(0.42, 0.58, len(frame))
        frame["target"] = np.array([0, 1] * 6)
        probs = np.linspace(0.50, 0.66, len(frame))
        result = _regime_slice_metrics(frame, probs, "sample", np.ones(len(frame), dtype=bool))
        self.assertIn("fold_roi_std", result)
        self.assertIn("classification", result)
        self.assertGreaterEqual(result["n_games"], 1)


if __name__ == "__main__":
    unittest.main()
