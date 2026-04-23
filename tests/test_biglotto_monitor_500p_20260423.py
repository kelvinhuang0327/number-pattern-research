import unittest

from tools import monitor_biglotto_500p_20260423 as monitor


class TestBigLottoMonitorDecisionLogic(unittest.TestCase):
    def test_keep_when_all_windows_clear_gates(self):
        windows = {
            "recent_150": {"edge": 0.01, "edge_pct": 1.0, "per_bet_efficiency": 1.1, "per_bet_efficiency_pct": 110.0},
            "recent_500": {"edge": 0.015, "edge_pct": 1.5, "per_bet_efficiency": 0.95, "per_bet_efficiency_pct": 95.0},
            "recent_1500": {"edge": 0.012, "edge_pct": 1.2, "per_bet_efficiency": 0.9, "per_bet_efficiency_pct": 90.0},
        }
        perm = {
            "recent_150": {"p_emp": 0.01},
            "recent_500": {"p_emp": 0.03},
            "recent_1500": {"p_emp": 0.04},
        }
        self.assertEqual(monitor.classify_final_decision(windows, perm, "PASS"), "KEEP")

    def test_downgrade_candidate_when_any_hard_gate_fails(self):
        windows = {
            "recent_150": {"edge": 0.01, "edge_pct": 1.0, "per_bet_efficiency": 1.1, "per_bet_efficiency_pct": 110.0},
            "recent_500": {"edge": -0.002, "edge_pct": -0.2, "per_bet_efficiency": 0.72, "per_bet_efficiency_pct": 72.0},
            "recent_1500": {"edge": 0.012, "edge_pct": 1.2, "per_bet_efficiency": 0.9, "per_bet_efficiency_pct": 90.0},
        }
        perm = {
            "recent_150": {"p_emp": 0.01},
            "recent_500": {"p_emp": 0.17},
            "recent_1500": {"p_emp": 0.04},
        }
        self.assertEqual(
            monitor.classify_final_decision(windows, perm, "PASS"),
            "DOWNGRADE_CANDIDATE",
        )

    def test_lifecycle_pattern_identifies_short_momentum(self):
        windows = {
            "recent_150": {"edge_pct": 1.0},
            "recent_500": {"edge_pct": 0.4},
            "recent_1500": {"edge_pct": -0.1},
        }
        self.assertEqual(monitor.lifecycle_pattern(windows), "SHORT_MOMENTUM")


if __name__ == "__main__":
    unittest.main()
