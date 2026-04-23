import unittest

from tools import research_daily539_poolsize_h013 as h013


class TestDaily539PoolsizeH013(unittest.TestCase):
    def test_verify_slice_integrity_accepts_prior_history(self):
        history = [
            {"draw": "1", "dt": h013.datetime.strptime("2026/01/01", "%Y/%m/%d").date()},
            {"draw": "2", "dt": h013.datetime.strptime("2026/01/02", "%Y/%m/%d").date(), "next_date": None},
        ]
        target = {"draw": "3", "dt": h013.datetime.strptime("2026/01/03", "%Y/%m/%d").date()}
        h013.verify_slice_integrity(history, target)

    def test_verify_slice_integrity_rejects_leakage(self):
        history = [
            {"draw": "3", "dt": h013.datetime.strptime("2026/01/03", "%Y/%m/%d").date(), "next_date": None},
        ]
        target = {"draw": "3", "dt": h013.datetime.strptime("2026/01/03", "%Y/%m/%d").date()}
        with self.assertRaises(ValueError):
            h013.verify_slice_integrity(history, target)

    def test_audit_pool_series_flags_missing_data(self):
        draws = []
        for idx in range(2000):
            draws.append(
                {
                    "draw": str(idx + 1),
                    "date": "2026/01/01",
                    "dt": h013.datetime.strptime("2026/01/01", "%Y/%m/%d").date(),
                    "numbers": [1, 2, 3, 4, 5],
                    "jackpot_amount": None,
                }
            )
        audit = h013.audit_pool_series(draws)
        self.assertEqual(audit["nonnull_count"], 0)
        self.assertEqual(audit["coverage_pct"], 0.0)
        self.assertEqual(audit["longest_consecutive_nonnull_run"], 0)
        for window in h013.WINDOWS:
            self.assertFalse(audit["tail_window_availability"][str(window)]["tail_span_fully_available"])

    def test_build_candidate_summary_marks_data_unavailable(self):
        pool_audit = {
            "feature_key": "jackpot_amount",
            "total_draws": 5839,
            "nonnull_count": 0,
            "coverage_pct": 0.0,
            "tail_window_availability": {
                "150": {"required_history_span": 450, "nonnull_in_tail_span": 0},
                "500": {"required_history_span": 800, "nonnull_in_tail_span": 0},
                "1500": {"required_history_span": 1800, "nonnull_in_tail_span": 0},
            },
        }
        leakage = {"formal_checker_passed": True, "h013_slice_checks_passed": True}
        summary = h013.build_candidate_summary(h013.CANDIDATES[0], pool_audit, leakage)
        self.assertEqual(summary["status"], "REJECT")
        self.assertFalse(summary["formal_backtest_executed"])
        self.assertEqual(summary["blocked_by"], "DATA_UNAVAILABLE")
        self.assertIn("coverage is 0.00%", summary["rationale"])

    def test_load_draws_real_data_has_expected_shape(self):
        draws = h013.load_draws()
        self.assertGreater(len(draws), 1500)
        self.assertIn("jackpot_amount", draws[0])
        self.assertLess(int(draws[0]["draw"]), int(draws[-1]["draw"]))


if __name__ == "__main__":
    unittest.main()
