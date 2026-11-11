from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.mlb_alpha_lab import MLBAlphaLab


class TestMLBAlphaLab(unittest.TestCase):
    def test_research_cycle_outputs_expected_sections(self):
        lab = MLBAlphaLab()
        report = lab.run_full_research_cycle(report_path="data/wbc_backend/reports/mlb_alpha_discovery_report_test.json")
        self.assertIn("feature_impact_table", report)
        self.assertIn("alpha_ranking", report)
        self.assertIn("clv_analysis", report)
        self.assertIn("production_gap_map", report)
        self.assertIn("final_verdict", report)
        self.assertGreaterEqual(len(report["feature_impact_table"]), 5)

    def test_partial_ready_when_strict_blocked_but_research_available(self):
        """When strict_valid=0 but research_valid>0, verdict should be PARTIAL READY (RESEARCH_VALID)."""
        lab = MLBAlphaLab()
        report = lab.run_full_research_cycle(report_path="data/wbc_backend/reports/mlb_alpha_discovery_report_test_blocked.json")
        strict_rate = report["production_gap_map"]["strict_valid_rate"]
        if strict_rate == 0.0:
            self.assertEqual(report["implementation_summary"]["strict_gate"]["status"], "BLOCKED BY DATA LAYER")
            # If research results exist (freshness-blocked, not data-unavailable), verdict is PARTIAL READY
            research_games = report["production_gap_map"].get("status_distribution", {}).get("RESEARCH_VALID", 0)
            if research_games > 0:
                self.assertEqual(report["final_verdict"], "PARTIAL READY (RESEARCH_VALID)")
            else:
                self.assertEqual(report["final_verdict"], "BLOCKED BY DATA")


if __name__ == "__main__":
    unittest.main()
