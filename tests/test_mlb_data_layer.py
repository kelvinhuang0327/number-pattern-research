from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from league_adapters.registry import get_league_adapter
from wbc_backend.mlb_data.health_report import build_health_report
from wbc_backend.mlb_data.ingestion import load_mlb_game_data
from wbc_backend.mlb_data.validator import validate_mlb_game_data


class TestMLBDataLayer(unittest.TestCase):
    def test_ingestion_and_validation_surface_missing_fields(self):
        rows = load_mlb_game_data()
        self.assertGreater(len(rows), 0)
        result = validate_mlb_game_data(rows[:10])
        self.assertGreaterEqual(result.research_valid_games + result.strict_valid_games, 1)
        self.assertGreater(len(result.issues), 0)

    def test_health_report_shape(self):
        rows = load_mlb_game_data()
        result = validate_mlb_game_data(rows[:20])
        report = build_health_report(rows[:20], result)
        self.assertIn("availability_pct", report)
        self.assertIn("validation_is_valid", report)
        self.assertIn("top_issues", report)
        self.assertIn("status_distribution", report)

    def test_wbc_adapter_unchanged(self):
        self.assertEqual(get_league_adapter("WBC").name(), "WBC")


if __name__ == "__main__":
    unittest.main()
