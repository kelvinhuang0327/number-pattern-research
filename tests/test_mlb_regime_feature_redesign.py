from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.mlb_regime_feature_redesign import build_regime_redesign_frame, redesign_feature_families


class TestMLBRegimeFeatureRedesign(unittest.TestCase):
    def test_feature_registry_targets_only_requested_regimes(self):
        families = redesign_feature_families()
        self.assertIn("small_edge", families)
        self.assertIn("weak_starter_mismatch", families)
        self.assertNotIn("favorites", families)

    def test_redesign_frame_contains_joined_and_derived_fields(self):
        frame = build_regime_redesign_frame()
        for col in (
            "elo_diff",
            "woba_diff",
            "market_minus_elo_prob",
            "starter_recent_ra_volatility_diff",
            "bullpen_bridge_quality",
            "applicable_regimes",
        ):
            self.assertIn(col, frame.columns)
        self.assertGreater(frame["strict_valid"].sum(), 100)


if __name__ == "__main__":
    unittest.main()
