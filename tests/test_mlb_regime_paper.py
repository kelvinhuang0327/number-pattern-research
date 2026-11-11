from __future__ import annotations

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.models.mlb_regime_paper import RegimeGateConfig, classify_regimes_from_row, regime_feature_sets


class TestMLBRegimePaper(unittest.TestCase):
    def test_regime_feature_sets_cover_whitelist(self):
        sets = regime_feature_sets()
        for regime in ("favorites", "small_edge", "weak_starter_mismatch", "heavy_bullpen_stress"):
            self.assertIn(regime, sets)
            self.assertGreater(len(sets[regime]), 0)

    def test_classify_regimes_from_row(self):
        gate = RegimeGateConfig(
            favorite_cutoff=0.55,
            small_edge_band=0.04,
            weak_starter_cutoff=0.60,
            heavy_bullpen_cutoff=12.0,
        )
        row = pd.Series(
            {
                "market_home_prob": 0.57,
                "starter_recent_ra_diff": 0.20,
                "bullpen_usage_diff": 14.0,
            }
        )
        regimes = classify_regimes_from_row(row, gate)
        self.assertIn("favorites", regimes)
        self.assertIn("weak_starter_mismatch", regimes)
        self.assertIn("heavy_bullpen_stress", regimes)


if __name__ == "__main__":
    unittest.main()
