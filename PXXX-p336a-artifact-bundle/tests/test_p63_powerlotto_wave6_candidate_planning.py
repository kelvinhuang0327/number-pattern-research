"""
P63 POWER_LOTTO Wave 6 Candidate Planning — Governance Tests
=============================================================
Classification: P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_COMPLETED

Test matrix:
  TestP63PlanningDocExists        — doc and JSON files exist and are non-empty
  TestP63JSONSchemaIntegrity      — JSON structure, required fields, types
  TestP63WaveShortlistGovernance  — shortlist has 3 candidates, all required fields
  TestP63ScoreConstraints         — scores are consistent with dimension scores
  TestP63AdapterInventory         — adapter file assertions (exists vs not exists)
  TestP63ProductionRowsUnchanged  — DB still has 43960 rows, no new rows added
  TestP63NoBranchGovernanceViolation — production rows exactly match expected
  TestP63CandidateMechanismDiversity — no two shortlisted candidates share primary mechanism
  TestP63WatchlistStatusPreserved — cold_complement + zonal_entropy remain WATCHLIST
  TestP63LagReversionGovernance   — lag_reversion_2bet has no adapter, evidence gate documented
"""
import json
import os
import sqlite3
import unittest
from pathlib import Path

# ─── Paths ─────────────────────────────────────────────────────────────────────

_REPO = Path(__file__).parent.parent
_JSON_PATH = _REPO / "outputs" / "replay" / "p63_powerlotto_wave6_candidate_planning_20260525.json"
_DOC_PATH = _REPO / "docs" / "replay" / "p63_powerlotto_wave6_candidate_planning_20260525.md"
_DB_PATH = _REPO / "lottery_api" / "data" / "lottery_v2.db"
_P56_ADAPTER = _REPO / "lottery_api" / "models" / "p56_wave5_powerlotto_adapters.py"

_EXPECTED_PROD_ROWS = 43960


# ─── TestP63PlanningDocExists ────────────────────────────────────────────────

class TestP63PlanningDocExists(unittest.TestCase):
    """P63 output files must exist and contain meaningful content."""

    def test_json_output_exists(self):
        self.assertTrue(_JSON_PATH.exists(), f"JSON output missing: {_JSON_PATH}")

    def test_doc_output_exists(self):
        self.assertTrue(_DOC_PATH.exists(), f"Doc output missing: {_DOC_PATH}")

    def test_json_not_empty(self):
        self.assertGreater(_JSON_PATH.stat().st_size, 500, "JSON is suspiciously small")

    def test_doc_not_empty(self):
        self.assertGreater(_DOC_PATH.stat().st_size, 2000, "Doc is suspiciously small")

    def test_json_parseable(self):
        with open(_JSON_PATH) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_doc_contains_classification_marker(self):
        content = _DOC_PATH.read_text()
        self.assertIn("P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_COMPLETED", content)

    def test_doc_contains_wave6_shortlist_section(self):
        content = _DOC_PATH.read_text()
        self.assertIn("Wave 6 Shortlist", content)

    def test_doc_contains_cold_complement(self):
        content = _DOC_PATH.read_text()
        self.assertIn("cold_complement_2bet", content)

    def test_doc_contains_zonal_entropy(self):
        content = _DOC_PATH.read_text()
        self.assertIn("zonal_entropy_2bet", content)

    def test_doc_contains_lag_reversion(self):
        content = _DOC_PATH.read_text()
        self.assertIn("lag_reversion_2bet", content)


# ─── TestP63JSONSchemaIntegrity ──────────────────────────────────────────────

class TestP63JSONSchemaIntegrity(unittest.TestCase):
    """JSON output must have required top-level fields."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)

    def test_schema_version_present(self):
        self.assertIn("schema_version", self.data)

    def test_task_id_is_p63(self):
        self.assertEqual(self.data["task_id"], "P63")

    def test_classification_correct(self):
        self.assertEqual(
            self.data["classification"],
            "P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING_COMPLETED"
        )

    def test_marker_correct(self):
        self.assertIn("P63_POWERLOTTO_WAVE6_CANDIDATE_PLANNING", self.data["marker"])

    def test_governance_block_present(self):
        self.assertIn("governance", self.data)

    def test_governance_no_db_writes(self):
        self.assertFalse(self.data["governance"]["db_writes"])

    def test_governance_no_online_promotions(self):
        self.assertFalse(self.data["governance"]["online_promotions"])

    def test_governance_no_champion_replacement(self):
        self.assertFalse(self.data["governance"]["champion_replacement"])

    def test_governance_no_registry_mutation(self):
        self.assertFalse(self.data["governance"]["registry_mutation"])

    def test_governance_no_production_apply(self):
        self.assertFalse(self.data["governance"]["production_apply"])

    def test_production_rows_before_matches_expected(self):
        self.assertEqual(
            self.data["governance"]["production_rows_before"],
            _EXPECTED_PROD_ROWS
        )

    def test_production_rows_after_matches_expected(self):
        self.assertEqual(
            self.data["governance"]["production_rows_after"],
            _EXPECTED_PROD_ROWS
        )

    def test_wave6_shortlist_present(self):
        self.assertIn("wave6_shortlist", self.data)

    def test_non_selected_candidates_present(self):
        self.assertIn("non_selected_candidates", self.data)

    def test_p64_sequencing_present(self):
        self.assertIn("p64_sequencing", self.data)

    def test_current_coverage_present(self):
        self.assertIn("current_powerlotto_coverage", self.data)

    def test_base_commit_referenced(self):
        self.assertEqual(self.data.get("base_commit"), "57f9ec3")

    def test_preceding_task_is_p62(self):
        self.assertEqual(self.data.get("preceding_task"), "P62")

    def test_next_task_is_p64(self):
        self.assertEqual(self.data.get("next_task"), "P64")


# ─── TestP63WaveShortlistGovernance ─────────────────────────────────────────

class TestP63WaveShortlistGovernance(unittest.TestCase):
    """Wave 6 shortlist must contain exactly 3 candidates with required fields."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]

    def test_shortlist_has_three_candidates(self):
        self.assertEqual(len(self.shortlist), 3)

    def test_ranks_are_1_2_3(self):
        ranks = sorted(c["rank"] for c in self.shortlist)
        self.assertEqual(ranks, [1, 2, 3])

    def test_all_have_strategy_id(self):
        for c in self.shortlist:
            self.assertIn("strategy_id", c)
            self.assertIsInstance(c["strategy_id"], str)
            self.assertGreater(len(c["strategy_id"]), 0)

    def test_all_have_mechanism(self):
        for c in self.shortlist:
            self.assertIn("mechanism", c)

    def test_all_have_total_score(self):
        for c in self.shortlist:
            self.assertIn("total_score", c)

    def test_total_scores_positive(self):
        for c in self.shortlist:
            self.assertGreater(c["total_score"], 0)

    def test_total_scores_max_100(self):
        for c in self.shortlist:
            self.assertLessEqual(c["total_score"], 100)

    def test_shortlist_contains_cold_complement(self):
        ids = [c["strategy_id"] for c in self.shortlist]
        self.assertIn("cold_complement_2bet", ids)

    def test_shortlist_contains_zonal_entropy(self):
        ids = [c["strategy_id"] for c in self.shortlist]
        self.assertIn("zonal_entropy_2bet", ids)

    def test_shortlist_contains_lag_reversion(self):
        ids = [c["strategy_id"] for c in self.shortlist]
        self.assertIn("lag_reversion_2bet", ids)

    def test_cold_complement_is_rank_1(self):
        for c in self.shortlist:
            if c["strategy_id"] == "cold_complement_2bet":
                self.assertEqual(c["rank"], 1)

    def test_all_have_wave6_rationale(self):
        for c in self.shortlist:
            self.assertIn("wave6_rationale", c)
            self.assertGreater(len(c["wave6_rationale"]), 10)

    def test_all_have_bets_per_draw(self):
        for c in self.shortlist:
            self.assertIn("bets_per_draw", c)
            self.assertEqual(c["bets_per_draw"], 2)


# ─── TestP63ScoreConstraints ─────────────────────────────────────────────────

class TestP63ScoreConstraints(unittest.TestCase):
    """Score dimensions and totals must be internally consistent."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]

    def test_dimension_scores_sum_near_total(self):
        """Sum of 10 dimension scores should equal total_score."""
        for c in self.shortlist:
            if "dimension_scores" not in c:
                continue
            dims = c["dimension_scores"]
            s = sum(dims.values())
            total = c["total_score"]
            self.assertEqual(s, total,
                f"{c['strategy_id']}: dimension sum={s} != total_score={total}")

    def test_dimension_scores_in_valid_range(self):
        for c in self.shortlist:
            if "dimension_scores" not in c:
                continue
            for dim, score in c["dimension_scores"].items():
                self.assertGreaterEqual(score, 0, f"{c['strategy_id']}.{dim} < 0")
                self.assertLessEqual(score, 10, f"{c['strategy_id']}.{dim} > 10")

    def test_rank1_has_highest_score(self):
        by_rank = {c["rank"]: c["total_score"] for c in self.shortlist}
        self.assertGreater(by_rank[1], by_rank[2],
            "Rank 1 score should be higher than rank 2")

    def test_rank2_higher_than_rank3(self):
        by_rank = {c["rank"]: c["total_score"] for c in self.shortlist}
        self.assertGreater(by_rank[2], by_rank[3],
            "Rank 2 score should be higher than rank 3")


# ─── TestP63AdapterInventory ─────────────────────────────────────────────────

class TestP63AdapterInventory(unittest.TestCase):
    """Adapter assertions must match actual filesystem state."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]
        cls.by_id = {c["strategy_id"]: c for c in cls.shortlist}

    def test_cold_complement_adapter_exists_flag_true(self):
        c = self.by_id["cold_complement_2bet"]
        self.assertTrue(c["adapter_exists"])

    def test_cold_complement_adapter_file_is_p56(self):
        c = self.by_id["cold_complement_2bet"]
        self.assertIn("p56_wave5_powerlotto_adapters", c["adapter_file"])

    def test_cold_complement_adapter_file_actually_exists(self):
        c = self.by_id["cold_complement_2bet"]
        path = _REPO / c["adapter_file"]
        self.assertTrue(path.exists(), f"Adapter file not found: {path}")

    def test_cold_complement_adapter_contains_class(self):
        with open(_P56_ADAPTER) as f:
            content = f.read()
        c = self.by_id["cold_complement_2bet"]
        self.assertIn(c["adapter_class"], content)

    def test_zonal_entropy_adapter_exists_flag_true(self):
        c = self.by_id["zonal_entropy_2bet"]
        self.assertTrue(c["adapter_exists"])

    def test_zonal_entropy_adapter_file_is_p56(self):
        c = self.by_id["zonal_entropy_2bet"]
        self.assertIn("p56_wave5_powerlotto_adapters", c["adapter_file"])

    def test_zonal_entropy_adapter_class_in_p56(self):
        with open(_P56_ADAPTER) as f:
            content = f.read()
        c = self.by_id["zonal_entropy_2bet"]
        self.assertIn(c["adapter_class"], content)

    def test_lag_reversion_adapter_exists_flag_false(self):
        c = self.by_id["lag_reversion_2bet"]
        self.assertFalse(c["adapter_exists"])

    def test_lag_reversion_adapter_file_is_null(self):
        c = self.by_id["lag_reversion_2bet"]
        self.assertIsNone(c["adapter_file"])

    def test_lag_reversion_source_tool_exists(self):
        c = self.by_id["lag_reversion_2bet"]
        path = _REPO / c["source_tool"]
        self.assertTrue(path.exists(), f"Source tool not found: {path}")

    def test_lag_reversion_source_model_exists(self):
        c = self.by_id["lag_reversion_2bet"]
        path = _REPO / c["source_model"]
        self.assertTrue(path.exists(), f"Source model not found: {path}")

    def test_cold_complement_source_tool_exists(self):
        c = self.by_id["cold_complement_2bet"]
        path = _REPO / c["source_tool"]
        self.assertTrue(path.exists(), f"Source tool not found: {path}")

    def test_zonal_entropy_source_tool_exists(self):
        c = self.by_id["zonal_entropy_2bet"]
        path = _REPO / c["source_tool"]
        self.assertTrue(path.exists(), f"Source tool not found: {path}")


# ─── TestP63ProductionRowsUnchanged ─────────────────────────────────────────

class TestP63ProductionRowsUnchanged(unittest.TestCase):
    """Production DB must not have changed. 43960 rows exactly."""

    def _query(self, sql):
        con = sqlite3.connect(str(_DB_PATH))
        cur = con.execute(sql)
        result = cur.fetchone()[0]
        con.close()
        return result

    def test_total_rows_unchanged(self):
        rows = self._query("SELECT COUNT(*) FROM strategy_prediction_replays")
        self.assertEqual(rows, _EXPECTED_PROD_ROWS,
            f"Expected {_EXPECTED_PROD_ROWS} rows, got {rows}. P63 must not write to DB.")

    def test_powerlotto_rows_unchanged(self):
        rows = self._query(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='POWER_LOTTO'"
        )
        self.assertEqual(rows, 10640,
            f"POWER_LOTTO rows changed from expected 10640 to {rows}")

    def test_cold_complement_rows_still_zero(self):
        rows = self._query(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet'"
        )
        self.assertEqual(rows, 0,
            "cold_complement_2bet should still have 0 rows in production DB")

    def test_zonal_entropy_rows_still_zero(self):
        rows = self._query(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='zonal_entropy_2bet'"
        )
        self.assertEqual(rows, 0,
            "zonal_entropy_2bet should still have 0 rows in production DB")

    def test_lag_reversion_rows_still_zero(self):
        rows = self._query(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='lag_reversion_2bet'"
        )
        self.assertEqual(rows, 0,
            "lag_reversion_2bet should still have 0 rows in production DB")

    def test_fourier30_markov30_rows_unchanged(self):
        rows = self._query(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='fourier30_markov30_2bet'"
        )
        self.assertEqual(rows, 1500,
            f"fourier30_markov30_2bet P59 rows should still be exactly 1500, got {rows}")


# ─── TestP63NoBranchGovernanceViolation ──────────────────────────────────────

class TestP63NoBranchGovernanceViolation(unittest.TestCase):
    """Cross-check JSON governance block against actual DB row count."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)

    def test_json_after_rows_matches_db(self):
        """JSON 'after' row count must match actual DB row count."""
        con = sqlite3.connect(str(_DB_PATH))
        actual_rows = con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        con.close()

        stated = self.data["governance"]["production_rows_after"]
        self.assertEqual(stated, actual_rows,
            f"JSON states {stated} rows, DB has {actual_rows}")

    def test_json_before_equals_after(self):
        """P63 is planning-only; before == after must hold."""
        gov = self.data["governance"]
        self.assertEqual(
            gov["production_rows_before"],
            gov["production_rows_after"],
            "Planning task must not change row count: before != after"
        )

    def test_drift_guard_pass(self):
        self.assertEqual(self.data["governance"]["drift_guard"], "PASS")

    def test_branch_governance_pass(self):
        self.assertEqual(self.data["governance"]["branch_governance_guard"], "PASS")


# ─── TestP63CandidateMechanismDiversity ──────────────────────────────────────

class TestP63CandidateMechanismDiversity(unittest.TestCase):
    """Shortlisted candidates must use different primary mechanisms."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]

    def test_mechanisms_are_unique(self):
        mechanisms = [c["mechanism"].split("—")[0].strip() for c in self.shortlist]
        self.assertEqual(len(mechanisms), len(set(mechanisms)),
            "Two or more shortlist candidates have identical mechanism descriptions")

    def test_no_fourier_primary_mechanism(self):
        """Wave 6 should not introduce another Fourier-primary strategy."""
        for c in self.shortlist:
            mech_lower = c["mechanism"].lower()
            # Allow Fourier as secondary but not primary mechanism name
            self.assertFalse(
                mech_lower.startswith("fourier"),
                f"{c['strategy_id']} starts with 'fourier' — would duplicate Wave 5 champion axis"
            )

    def test_cold_complement_mechanism_is_cold_reversion(self):
        for c in self.shortlist:
            if c["strategy_id"] == "cold_complement_2bet":
                self.assertIn("cold", c["mechanism"].lower())

    def test_zonal_entropy_mechanism_is_entropy_based(self):
        for c in self.shortlist:
            if c["strategy_id"] == "zonal_entropy_2bet":
                self.assertIn("entropy", c["mechanism"].lower())

    def test_lag_reversion_mechanism_is_temporal(self):
        for c in self.shortlist:
            if c["strategy_id"] == "lag_reversion_2bet":
                mech = c["mechanism"].lower()
                self.assertTrue(
                    "lag" in mech or "interval" in mech or "overdue" in mech,
                    f"Expected temporal mechanism, got: {c['mechanism']}"
                )


# ─── TestP63WatchlistStatusPreserved ────────────────────────────────────────

class TestP63WatchlistStatusPreserved(unittest.TestCase):
    """Wave 5 WATCHLIST candidates must remain WATCHLIST (not promoted here)."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]
        cls.by_id = {c["strategy_id"]: c for c in cls.shortlist}

    def test_cold_complement_prior_status_is_watchlist(self):
        c = self.by_id["cold_complement_2bet"]
        self.assertEqual(c["prior_status"], "WATCHLIST_REHEARSAL_ONLY")

    def test_zonal_entropy_prior_status_is_watchlist(self):
        c = self.by_id["zonal_entropy_2bet"]
        self.assertEqual(c["prior_status"], "WATCHLIST_REHEARSAL_ONLY")

    def test_cold_complement_p57_m3plus_below_baseline(self):
        c = self.by_id["cold_complement_2bet"]
        self.assertLess(c["wave5_p57_m3plus"], c["baseline_m3plus"],
            "cold_complement_2bet P57 M3+ should be below baseline (WATCHLIST classification)")

    def test_zonal_entropy_p57_m3plus_below_baseline(self):
        c = self.by_id["zonal_entropy_2bet"]
        self.assertLess(c["wave5_p57_m3plus"], c["baseline_m3plus"],
            "zonal_entropy_2bet P57 M3+ should be below baseline (WATCHLIST classification)")

    def test_cold_complement_p64_work_is_none_adapter_ready(self):
        c = self.by_id["cold_complement_2bet"]
        self.assertEqual(c["p64_work"], "none_adapter_ready")

    def test_zonal_entropy_p64_work_requires_determinism_fix(self):
        c = self.by_id["zonal_entropy_2bet"]
        self.assertIn("determinism", c["p64_work"])


# ─── TestP63LagReversionGovernance ──────────────────────────────────────────

class TestP63LagReversionGovernance(unittest.TestCase):
    """lag_reversion_2bet governance: no adapter, evidence gate documented."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.shortlist = cls.data["wave6_shortlist"]
        cls.lag = next(c for c in cls.shortlist if c["strategy_id"] == "lag_reversion_2bet")

    def test_no_adapter_file(self):
        self.assertIsNone(self.lag["adapter_file"])

    def test_adapter_exists_false(self):
        self.assertFalse(self.lag["adapter_exists"])

    def test_prior_status_is_new_candidate(self):
        self.assertEqual(self.lag["prior_status"], "NEW_CANDIDATE")

    def test_p64_work_requires_mini_backtest(self):
        self.assertIn("mini_backtest", self.lag["p64_work"])

    def test_p64_mini_backtest_windows_present(self):
        self.assertIn("p64_mini_backtest_windows", self.lag)
        windows = self.lag["p64_mini_backtest_windows"]
        self.assertIsInstance(windows, list)
        self.assertGreater(len(windows), 0)

    def test_p64_evidence_gate_documented(self):
        self.assertIn("p64_evidence_gate", self.lag)
        gate = self.lag["p64_evidence_gate"]
        self.assertIsInstance(gate, str)
        self.assertGreater(len(gate), 10)

    def test_determinism_concern_false(self):
        self.assertFalse(self.lag["determinism_concern"])

    def test_score_lower_than_cold_complement(self):
        cold = next(c for c in self.shortlist if c["strategy_id"] == "cold_complement_2bet")
        self.assertLess(self.lag["total_score"], cold["total_score"])


# ─── TestP63CurrentCoverageIntegrity ────────────────────────────────────────

class TestP63CurrentCoverageIntegrity(unittest.TestCase):
    """current_powerlotto_coverage block must match DB reality."""

    @classmethod
    def setUpClass(cls):
        with open(_JSON_PATH) as f:
            cls.data = json.load(f)
        cls.coverage = cls.data["current_powerlotto_coverage"]

    def test_total_rows_matches_db(self):
        con = sqlite3.connect(str(_DB_PATH))
        actual = con.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        con.close()
        self.assertEqual(self.coverage["total_rows"], actual,
            f"coverage.total_rows={self.coverage['total_rows']} != DB={actual}")

    def test_watchlist_zero_rows_has_two_entries(self):
        self.assertEqual(len(self.coverage["watchlist_zero_rows"]), 2)

    def test_watchlist_entries_have_zero_rows(self):
        for entry in self.coverage["watchlist_zero_rows"]:
            self.assertEqual(entry["rows"], 0)

    def test_fourier30_markov30_in_row_backed_list(self):
        ids = [s["strategy_id"] for s in self.coverage["strategies"]]
        self.assertIn("fourier30_markov30_2bet", ids)

    def test_fourier_rhythm_is_champion(self):
        for s in self.coverage["strategies"]:
            if s["strategy_id"] == "fourier_rhythm_3bet":
                self.assertTrue(s["is_champion"])

    def test_strategies_row_count_sums_to_total(self):
        stated = sum(s["rows"] for s in self.coverage["strategies"])
        total = self.coverage["total_rows"]
        self.assertEqual(stated, total,
            f"Sum of strategy rows ({stated}) != total_rows ({total})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
