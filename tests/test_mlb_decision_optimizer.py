from __future__ import annotations

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.models.mlb_decision_optimizer import _calibration_curve, _compute_side_metrics


class TestMLBDecisionOptimizer(unittest.TestCase):
    def test_calibration_curve_outputs_bucket_rows(self):
        probs = np.array([0.12, 0.18, 0.55, 0.61, 0.84, 0.91], dtype=float)
        y = np.array([0, 0, 1, 0, 1, 1], dtype=int)
        rows = _calibration_curve(probs, y, n_bins=5)
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(all(row.n > 0 for row in rows))

    def test_decision_metrics_respect_threshold_and_confidence(self):
        probs = np.array([0.60, 0.54, 0.44, 0.30], dtype=float)
        y = np.array([1, 1, 0, 0], dtype=int)
        market = np.array([0.50, 0.53, 0.47, 0.48], dtype=float)
        metrics = _compute_side_metrics(probs, y, market, threshold=0.05, confidence_cutoff=0.05)
        self.assertEqual(metrics["n_bets"], 2)
        self.assertGreater(metrics["roi"], 0)


if __name__ == "__main__":
    unittest.main()
