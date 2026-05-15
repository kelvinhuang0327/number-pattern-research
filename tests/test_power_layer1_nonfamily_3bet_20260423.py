import unittest

from tools import research_power_layer1_nonfamily_3bet_20260423 as research


def make_candidate(
    *,
    edge=0.01,
    perm_p=0.01,
    cohens_d=1.5,
    efficiency_pass=True,
    leakage="PASS",
    mcnemar_pass=True,
    mcnemar_triggered=True,
):
    windows = {
        name: {"edge": edge}
        for name in research.WINDOW_SPECS
    }
    permutation_tests = {
        name: {"p_emp": perm_p, "cohens_d": cohens_d}
        for name in research.WINDOW_SPECS
    }
    efficiency = {
        name: {
            "pass": efficiency_pass,
            "per_bet_efficiency_pct": 95.0 if efficiency_pass else 70.0,
        }
        for name in research.WINDOW_SPECS
    }
    return {
        "name": "synthetic_candidate",
        "windows": windows,
        "permutation_tests": permutation_tests,
        "efficiency_vs_pp3_freqort_4bet": efficiency,
        "leakage_check": leakage,
        "mcnemar": {"pass": mcnemar_pass, "p_value": 0.01 if mcnemar_pass else 0.42},
        "mcnemar_triggered": mcnemar_triggered,
    }


class TestPowerLayer1Nonfamily3Bet20260423(unittest.TestCase):
    def test_result_schema_keys_include_required_outputs(self):
        required = {
            "completed_markdown",
            "task_result_json",
            "changed_files_list",
            "final_decision",
            "candidates",
        }
        self.assertTrue(required.issubset(research.RESULT_SCHEMA_KEYS))

    def test_build_window_indices_preserves_full_lengths(self):
        windows = research.build_window_indices(total_draws=2500, min_history=research.MIN_HISTORY)
        self.assertEqual(len(windows["recent_150"]), 150)
        self.assertEqual(len(windows["recent_500"]), 500)
        self.assertEqual(len(windows["recent_1500"]), 1500)
        self.assertGreaterEqual(windows["recent_150"][0], research.MIN_HISTORY)

    def test_determine_candidate_decision_promotes_only_on_full_gate_pass(self):
        promote_candidate = make_candidate()
        decision, failures, triggered = research.determine_candidate_decision(promote_candidate)
        self.assertEqual(decision, "PROMOTE")
        self.assertEqual(failures, [])
        self.assertTrue(triggered)

        watch_candidate = make_candidate(perm_p=0.08, cohens_d=0.9, mcnemar_pass=False, mcnemar_triggered=False)
        decision, failures, triggered = research.determine_candidate_decision(watch_candidate)
        self.assertEqual(decision, "WATCH")
        self.assertIn("recent_150: permutation_p>=0.05", failures)
        self.assertFalse(triggered)

        reject_candidate = make_candidate(edge=-0.01, perm_p=0.30, cohens_d=0.2, efficiency_pass=False, mcnemar_pass=False, mcnemar_triggered=False)
        decision, failures, triggered = research.determine_candidate_decision(reject_candidate)
        self.assertEqual(decision, "REJECT")
        self.assertIn("recent_150: edge<=0", failures)
        self.assertIn("recent_150: per_bet_efficiency<=80%", failures)
        self.assertFalse(triggered)


if __name__ == "__main__":
    unittest.main()
