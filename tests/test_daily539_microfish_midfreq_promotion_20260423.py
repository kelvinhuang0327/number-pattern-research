import unittest

from tools import validate_daily539_microfish_midfreq_promotion_20260423 as promotion


class TestDaily539MicroFishMidFreqPromotion(unittest.TestCase):
    def test_evaluate_bet_efficiency_uses_incremental_baseline(self):
        records = []
        for idx in range(10):
            records.append(
                {
                    "draw": str(idx + 1),
                    "date": "2026/01/01",
                    "match_counts": [2, 0],
                    "is_m2plus_1": idx < 2,
                    "is_m2plus_2": idx < 4,
                }
            )

        result = promotion.evaluate_bet_efficiency(records, num_bets=2, window=10)

        self.assertEqual(result[0]["incremental_efficiency_pct"], 100.0)
        self.assertEqual(result[0]["cumulative_hit_rate"], 20.0)
        self.assertEqual(result[1]["cumulative_hit_rate"], 40.0)
        self.assertAlmostEqual(result[1]["incremental_efficiency_pct"], 197.24, places=2)

    def test_build_window_failures_collects_all_gate_breaks(self):
        window_result = {
            "candidate_metrics": {"edge": -0.1},
            "candidate_permutation": {"p_value": 0.2, "cohens_d": 0.8},
            "candidate_efficiency": [
                {"bet": 1, "incremental_efficiency_pct": 100.0},
                {"bet": 2, "incremental_efficiency_pct": 72.0},
            ],
            "mcnemar_vs_incumbent": {"p_value": 0.12, "net": -3},
        }

        failures = promotion.build_window_failures(window_result)

        self.assertEqual(
            failures,
            ["edge<=0", "perm>=0.05", "d<=1.0", "eff<80", "mcnemar>=0.05", "mcnemar_net<=0"],
        )

    def test_determine_verdict_requires_all_windows_and_leakage(self):
        passing_windows = {"150": [], "500": [], "1500": []}
        passing_leakage = {"formal_checker_passed": True, "microfish_slice_checks_passed": True}
        failing_windows = {"150": [], "500": ["perm>=0.05"], "1500": []}

        self.assertEqual(promotion.determine_verdict(passing_windows, passing_leakage), "PASS_PROMOTION")
        self.assertEqual(promotion.determine_verdict(failing_windows, passing_leakage), "REJECT")
        self.assertEqual(
            promotion.determine_verdict(
                passing_windows,
                {"formal_checker_passed": False, "microfish_slice_checks_passed": True},
            ),
            "REJECT",
        )


if __name__ == "__main__":
    unittest.main()
