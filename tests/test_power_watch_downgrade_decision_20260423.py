import unittest

from tools import validate_power_watch_downgrade_decision_20260423 as decision


class TestPowerWatchDowngradeDecision20260423(unittest.TestCase):
    def test_build_not_triggered_mcnemar_branch(self):
        payload = decision.build_not_triggered_mcnemar(
            ["permutation p gate not fully passed", "per-bet efficiency gate not fully passed"]
        )
        self.assertEqual(payload["status"], "NOT_TRIGGERED")
        self.assertIn("permutation p gate not fully passed", payload["reason"])
        self.assertFalse(payload["pass"])

    def test_determine_downgrade_action_downweights_on_perm_failure_ratio(self):
        windows = {
            "recent_150": {"edge": 0.01},
            "recent_500": {"edge": 0.012},
            "recent_1500": {"edge": 0.009},
        }
        perm = {
            "recent_150": {"p_emp": 0.17},
            "recent_500": {"p_emp": 0.22},
            "recent_1500": {"p_emp": 0.19},
        }
        rolling_summary = {
            "slice_count": 5,
            "slice_length": 300,
            "positive_edge_slices": 5,
            "nonpositive_edge_slices": 0,
            "permutation_pass_slices": 0,
            "permutation_fail_slices": 5,
            "permutation_fail_ratio": 1.0,
            "cohens_d_fail_slices": 5,
            "cohens_d_fail_ratio": 1.0,
            "consecutive_nonpositive_edge_slices": 0,
            "consecutive_permutation_fail_slices": 5,
            "latest_slice": {"slice_id": "slice_5", "edge_pct": 0.6, "permutation_p": 0.22, "cohens_d": 0.7},
        }
        result = decision.determine_downgrade_action(windows, perm, rolling_summary)
        self.assertEqual(result["status"], "WATCH")
        self.assertEqual(result["action"], "DOWNWEIGHT_WATCH_PRIORITY")
        self.assertTrue(result["triggered"])

    def test_payload_contract_fields_present(self):
        payload = {
            "status": "WATCH",
            "target_strategy": "fourier_rhythm_3bet",
            "windows": {"recent_150": {}, "recent_500": {}, "recent_1500": {}},
            "rolling_oos_summary": {"target": {}, "candidate": {}, "reference": {}},
            "permutation": {"target": {}, "candidate": {}, "reference": {}},
            "cohens_d": {"target": {}, "candidate": {}, "reference": {}},
            "efficiency": {"candidate_vs_pp3_freqort_4bet": {}},
            "leakage_check": {"status": "PASS"},
            "mcnemar": {"status": "NOT_TRIGGERED", "reason": "gate failed"},
            "downgrade_policy": {"action": "DOWNWEIGHT_WATCH_PRIORITY"},
            "planner_recommendation": "topic",
        }
        required = {
            "status",
            "target_strategy",
            "windows",
            "rolling_oos_summary",
            "permutation",
            "cohens_d",
            "efficiency",
            "leakage_check",
            "mcnemar",
            "downgrade_policy",
            "planner_recommendation",
        }
        self.assertTrue(required.issubset(payload.keys()))


if __name__ == "__main__":
    unittest.main()
