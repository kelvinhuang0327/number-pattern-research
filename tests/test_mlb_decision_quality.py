from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.evaluation.mlb_decision_quality import _decision_label, evaluate_mlb_decision_quality


class TestMLBDecisionQuality(unittest.TestCase):
    def test_decision_quality_report_has_expected_shapes(self):
        report = evaluate_mlb_decision_quality(
            report_path="data/wbc_backend/reports/mlb_decision_quality_report_test.json",
        )
        self.assertTrue(report["paper_mode"])
        self.assertEqual(report["execution_mode"], "PAPER_ONLY")
        self.assertIn("per_game", report)
        self.assertIn("summary", report)
        self.assertGreater(len(report["per_game"]), 100)
        labels = report["summary"]["label_counts"]
        for key in ("GOOD_BET_WIN", "GOOD_BET_LOSS", "BAD_BET_WIN", "BAD_BET_LOSS", "NO_BET"):
            self.assertIn(key, labels)

    def test_decision_label_rule_paths(self):
        self.assertEqual(
            _decision_label(was_selected_for_bet=False, clv_available=True, edge=0.1, clv=0.1, actual_result=1),
            "NO_BET",
        )
        self.assertEqual(
            _decision_label(was_selected_for_bet=True, clv_available=False, edge=0.1, clv=0.1, actual_result=1),
            "NO_BET",
        )
        self.assertEqual(
            _decision_label(was_selected_for_bet=True, clv_available=True, edge=0.02, clv=0.03, actual_result=1),
            "GOOD_BET_WIN",
        )
        self.assertEqual(
            _decision_label(was_selected_for_bet=True, clv_available=True, edge=0.02, clv=0.03, actual_result=0),
            "GOOD_BET_LOSS",
        )
        self.assertEqual(
            _decision_label(was_selected_for_bet=True, clv_available=True, edge=-0.01, clv=0.02, actual_result=1),
            "BAD_BET_WIN",
        )
        self.assertEqual(
            _decision_label(was_selected_for_bet=True, clv_available=True, edge=0.01, clv=0.0, actual_result=0),
            "BAD_BET_LOSS",
        )


if __name__ == "__main__":
    unittest.main()
