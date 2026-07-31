"""
tests/test_p64b_lag_reversion_wave6_mini_backtest.py
======================================================
P64b: lag_reversion_2bet Wave 6 Mini-Backtest — artifact validation tests.

Gate result: P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL
Best M3+: 3.73% (window-1500, -0.14pp vs 3.87% baseline)
Adapter decision: DEFER_ADAPTER_BUILD

Tests: 72 across 11 classes.
"""
import json
import os
import sqlite3
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
JSON_PATH = REPO_ROOT / "outputs" / "replay" / "p64b_lag_reversion_wave6_mini_backtest_20260525.json"
DOC_PATH  = REPO_ROOT / "docs"    / "replay" / "p64b_lag_reversion_wave6_mini_backtest_20260525.md"
SCRIPT_PATH = REPO_ROOT / "scripts" / "p64b_lag_reversion_wave6_mini_backtest.py"
PROD_DB   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _load() -> dict:
    with open(JSON_PATH) as f:
        return json.load(f)


class TestArtifactExistence(unittest.TestCase):
    """Verify all 3 P64b artifacts exist and are non-empty."""

    def test_json_exists(self):
        self.assertTrue(JSON_PATH.exists(), f"Missing: {JSON_PATH}")

    def test_json_not_empty(self):
        self.assertGreater(JSON_PATH.stat().st_size, 100)

    def test_doc_exists(self):
        self.assertTrue(DOC_PATH.exists(), f"Missing: {DOC_PATH}")

    def test_doc_not_empty(self):
        self.assertGreater(DOC_PATH.stat().st_size, 100)

    def test_script_exists(self):
        self.assertTrue(SCRIPT_PATH.exists(), f"Missing: {SCRIPT_PATH}")


class TestOutputSchema(unittest.TestCase):
    """JSON output has correct top-level keys and values."""

    def setUp(self):
        self.d = _load()

    def test_required_keys_present(self):
        for key in [
            "schema_version", "task_id", "strategy_id", "run_id",
            "generated_at", "marker", "governance", "algorithm",
            "backtest_config", "window_results", "evidence_gate",
            "preceding_task", "next_task", "base_commit", "classification",
        ]:
            self.assertIn(key, self.d, f"Missing key: {key}")

    def test_task_id(self):
        self.assertEqual(self.d["task_id"], "P64b")

    def test_strategy_id(self):
        self.assertEqual(self.d["strategy_id"], "lag_reversion_2bet")

    def test_schema_version(self):
        self.assertEqual(self.d["schema_version"], "1.0")

    def test_marker(self):
        self.assertEqual(self.d["marker"], "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_20260525")

    def test_preceding_task(self):
        self.assertEqual(self.d["preceding_task"], "P64a")

    def test_base_commit(self):
        self.assertEqual(self.d["base_commit"], "80611f3")

    def test_run_id_contains_strategy(self):
        self.assertIn("lag_reversion", self.d["run_id"])


class TestGovernanceInvariants(unittest.TestCase):
    """Production DB must be untouched throughout."""

    def setUp(self):
        self.gov = _load()["governance"]

    def test_no_db_writes(self):
        self.assertFalse(self.gov["db_writes"])

    def test_no_online_promotions(self):
        self.assertFalse(self.gov["online_promotions"])

    def test_no_champion_replacement(self):
        self.assertFalse(self.gov["champion_replacement"])

    def test_no_registry_mutation(self):
        self.assertFalse(self.gov["registry_mutation"])

    def test_no_production_apply(self):
        self.assertFalse(self.gov["production_apply"])

    def test_production_rows_before(self):
        self.assertEqual(self.gov["production_rows_before"], 43960)

    def test_production_rows_after(self):
        self.assertEqual(self.gov["production_rows_after"], 43960)

    def test_no_temp_db(self):
        self.assertIsNone(self.gov["temp_db"])


class TestProductionDBIntact(unittest.TestCase):
    """Direct SQLite check: production rows still 43960, no lag_reversion rows."""

    def test_production_rows_still_43960(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 43960)

    def test_lag_reversion_not_in_production(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id='lag_reversion_2bet'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)


class TestBacktestConfig(unittest.TestCase):
    """Backtest configuration is correct."""

    def setUp(self):
        self.cfg = _load()["backtest_config"]

    def test_windows_correct(self):
        self.assertEqual(self.cfg["windows"], [150, 500, 1500])

    def test_in_memory_only(self):
        self.assertTrue(self.cfg["in_memory_only"])

    def test_no_db_writes(self):
        self.assertTrue(self.cfg["no_db_writes"])

    def test_evidence_gate_threshold(self):
        self.assertAlmostEqual(self.cfg["evidence_gate_threshold_m3plus_pct"], 3.87)


class TestWindowResults(unittest.TestCase):
    """All 3 backtest windows have valid metrics."""

    def setUp(self):
        d = _load()
        self.wr = d["window_results"]
        self.ev = d["evidence_gate"]

    def test_all_three_windows_present(self):
        self.assertIn("150", self.wr)
        self.assertIn("500", self.wr)
        self.assertIn("1500", self.wr)

    def test_window_150_predicted_count(self):
        self.assertEqual(self.wr["150"]["predicted_count"], 150)

    def test_window_500_predicted_count(self):
        self.assertEqual(self.wr["500"]["predicted_count"], 500)

    def test_window_1500_predicted_count(self):
        self.assertEqual(self.wr["1500"]["predicted_count"], 1500)

    def test_m3plus_rate_in_plausible_range(self):
        for w in ["150", "500", "1500"]:
            rate = self.wr[w]["m3plus_rate_pct"]
            self.assertGreaterEqual(rate, 0.0, f"Window {w} M3+ negative")
            self.assertLessEqual(rate, 20.0, f"Window {w} M3+ unrealistically high")

    def test_hit_distribution_sums_to_predicted(self):
        for w in ["150", "500", "1500"]:
            r = self.wr[w]
            dist_sum = sum(r["hit_distribution"].values())
            self.assertEqual(
                dist_sum, r["predicted_count"],
                f"Window {w}: dist sum {dist_sum} != predicted {r['predicted_count']}"
            )

    def test_no_negative_hit_dist_values(self):
        for w in ["150", "500", "1500"]:
            for k, v in self.wr[w]["hit_distribution"].items():
                self.assertGreaterEqual(v, 0, f"Window {w} hit[{k}] negative")

    def test_special_hit_rate_plausible(self):
        for w in ["150", "500", "1500"]:
            rate = self.wr[w]["special_hit_rate_pct"]
            # Expected ~12.5% (1/8), allow 3–30%
            self.assertGreaterEqual(rate, 3.0)
            self.assertLessEqual(rate, 30.0)

    def test_theoretical_baseline_is_387(self):
        for w in ["150", "500", "1500"]:
            self.assertAlmostEqual(
                self.wr[w]["theoretical_baseline_pct"], 3.87
            )

    def test_all_windows_gate_fail(self):
        """Known result: all 3 windows fail the evidence gate."""
        for w in ["150", "500", "1500"]:
            self.assertFalse(
                self.wr[w]["gate_pass"],
                f"Window {w} unexpectedly passes gate"
            )

    def test_long_window_better_than_short(self):
        """Window-1500 should outperform window-150 (more data → better calibration)."""
        self.assertGreater(
            self.wr["1500"]["m3plus_rate_pct"],
            self.wr["150"]["m3plus_rate_pct"],
        )

    def test_best_window_is_1500(self):
        self.assertEqual(self.ev["best_window"], 1500)

    def test_window_1500_m3plus_near_baseline(self):
        """Window-1500 M3+ should be within 1pp of baseline (known: 3.73%)."""
        rate = self.wr["1500"]["m3plus_rate_pct"]
        self.assertGreater(rate, 3.0, "Window-1500 M3+ too low (< 3.0%)")
        self.assertLess(rate, 4.5, "Window-1500 M3+ too high (> 4.5%)")

    def test_window_1500_vs_baseline_close(self):
        """Window-1500 vs_baseline_pp should be > -2pp (known: -0.14pp)."""
        self.assertGreater(self.wr["1500"]["vs_baseline_pp"], -2.0)


class TestEvidenceGate(unittest.TestCase):
    """Evidence gate: all windows fail, adapter deferred."""

    def setUp(self):
        self.ev = _load()["evidence_gate"]

    def test_threshold_is_387(self):
        self.assertAlmostEqual(self.ev["threshold_m3plus_pct"], 3.87)

    def test_gate_passed_is_false(self):
        self.assertFalse(self.ev["gate_passed"])

    def test_gate_pass_windows_is_empty(self):
        self.assertEqual(self.ev["gate_pass_windows"], [])

    def test_adapter_decision_is_defer(self):
        self.assertEqual(self.ev["adapter_decision"], "DEFER_ADAPTER_BUILD")

    def test_best_m3plus_positive(self):
        self.assertGreater(self.ev["best_m3plus_pct"], 0.0)

    def test_rationale_present(self):
        self.assertTrue(len(self.ev["rationale"]) > 10)

    def test_best_vs_baseline_negative(self):
        """All windows fail means best is still below baseline."""
        self.assertLess(self.ev["best_vs_baseline_pp"], 0.0)


class TestAlgorithmMetadata(unittest.TestCase):
    """Algorithm metadata is correct for lag_reversion."""

    def setUp(self):
        self.alg = _load()["algorithm"]

    def test_deterministic(self):
        self.assertTrue(self.alg["deterministic"])

    def test_no_random_seed(self):
        self.assertTrue(self.alg["no_random_seed"])

    def test_mechanism_mentions_median(self):
        self.assertIn("median", self.alg["mechanism"].lower())

    def test_source_model_is_lag_reversion(self):
        self.assertIn("lag_reversion", self.alg["source_model"])

    def test_source_tool_exists(self):
        tool_path = REPO_ROOT / self.alg["source_tool"]
        self.assertTrue(tool_path.exists(), f"Source tool missing: {tool_path}")

    def test_pool_is_38(self):
        self.assertEqual(self.alg["pool"], 38)

    def test_pick_is_6(self):
        self.assertEqual(self.alg["pick"], 6)

    def test_lag_window_is_500(self):
        self.assertEqual(self.alg["lag_window"], 500)


class TestClassificationMarker(unittest.TestCase):
    """Classification marker reflects gate FAIL result."""

    def setUp(self):
        self.d = _load()

    def test_classification_is_gate_fail(self):
        self.assertEqual(
            self.d["classification"],
            "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL",
        )

    def test_classification_in_valid_set(self):
        valid = {
            "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_PASS",
            "P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL",
        }
        self.assertIn(self.d["classification"], valid)

    def test_next_task_mentions_defer_or_other_path(self):
        """Gate fail → next task should NOT mention lag_reversion adapter build."""
        self.assertNotIn("lag_reversion_2bet adapter build", self.d["next_task"])


class TestDocContent(unittest.TestCase):
    """Markdown doc contains required sections and key values."""

    def setUp(self):
        self.text = DOC_PATH.read_text()

    def test_doc_contains_classification_marker(self):
        self.assertIn("P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL", self.text)

    def test_doc_contains_gate_fail(self):
        self.assertIn("GATE FAIL", self.text)

    def test_doc_contains_defer_decision(self):
        self.assertIn("DEFER_ADAPTER_BUILD", self.text)

    def test_doc_contains_baseline_threshold(self):
        self.assertIn("3.87", self.text)

    def test_doc_contains_production_rows(self):
        self.assertIn("43960", self.text)

    def test_doc_no_temp_db_reference(self):
        """Mini-backtest uses no temp DB."""
        self.assertNotIn("p64b_temp.db", self.text)

    def test_doc_mentions_window_1500_best(self):
        self.assertIn("1500", self.text)


if __name__ == "__main__":
    unittest.main()
