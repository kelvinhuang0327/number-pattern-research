"""
test_p58_powerlotto_wave5_controlled_apply_proposal.py
======================================================
P58 POWER_LOTTO Wave 5 controlled apply proposal — governance tests.

Validates:
  - P57 evidence integrity (classification, cohort, commit)
  - Duplicate check (fourier30_markov30_2bet not in POWER_LOTTO production)
  - P58 JSON structure and required fields
  - Governance constraints (no prod write, no lifecycle promotion, etc.)
  - Cohort constraints (only fourier30; cold/zonal excluded)
  - Proposal validity (authorization phrase, rollback plan, pre-apply checklist)
  - Production DB row count unchanged (42460)
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
P57_JSON = PROJECT_ROOT / "outputs" / "replay" / \
    "p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json"
P58_JSON = PROJECT_ROOT / "outputs" / "replay" / \
    "p58_powerlotto_wave5_controlled_apply_proposal_20260525.json"
PROD_DB = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

P58_STRATEGY = "fourier30_markov30_2bet"
WATCHLIST = {"cold_complement_2bet", "zonal_entropy_2bet"}
CONTROLLED_APPLY_ID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
EXPECTED_PROD_ROWS = 42460
EXPECTED_NEW_ROWS = 1500
EXPECTED_ROWS_AFTER = 43960


def _load_p57() -> dict:
    with open(P57_JSON) as f:
        return json.load(f)


def _load_p58() -> dict:
    with open(P58_JSON) as f:
        return json.load(f)


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ─── 1. P57 Evidence Integrity ────────────────────────────────────────────────

class TestP57EvidenceIntegrity(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P57_JSON.exists(), f"P57 JSON missing: {P57_JSON}")
        self.p57 = _load_p57()

    def test_p57_file_exists(self):
        self.assertTrue(P57_JSON.exists())

    def test_p57_classification(self):
        self.assertEqual(
            self.p57.get("classification"),
            "P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED",
        )

    def test_p57_cohort_decision_partial(self):
        self.assertEqual(self.p57.get("cohort_decision"), "PARTIAL_COHORT_P58")

    def test_p57_cohort_contains_only_fourier30(self):
        cohort = self.p57.get("p58_cohort", [])
        self.assertIn(P58_STRATEGY, cohort)
        self.assertNotIn("cold_complement_2bet", cohort)
        self.assertNotIn("zonal_entropy_2bet", cohort)

    def test_p57_watchlist_correct(self):
        watchlist = self.p57.get("watchlist", [])
        self.assertIn("cold_complement_2bet", watchlist)
        self.assertIn("zonal_entropy_2bet", watchlist)

    def test_p57_overall_ok(self):
        self.assertTrue(self.p57.get("overall_ok"))

    def test_p57_governance_no_prod_write(self):
        gov = self.p57.get("governance", {})
        self.assertFalse(gov.get("production_db_write", True))

    def test_p57_governance_no_promotion(self):
        gov = self.p57.get("governance", {})
        self.assertFalse(gov.get("lifecycle_promotion", True))

    def test_p57_governance_no_champion_replace(self):
        gov = self.p57.get("governance", {})
        self.assertFalse(gov.get("champion_replacement", True))

    def test_p57_governance_no_registry_mutation(self):
        gov = self.p57.get("governance", {})
        self.assertFalse(gov.get("registry_mutation", True))

    def test_p57_theoretical_baseline(self):
        b = self.p57.get("theoretical_m3_baseline", 0)
        self.assertAlmostEqual(b, 0.0387, places=3)

    def test_p57_fourier30_classification(self):
        sr = self.p57.get("strategy_readiness", {})
        cls = sr.get(P58_STRATEGY, {}).get("classification", "")
        self.assertEqual(cls, "READY_FOR_P58_WITH_CAUTION")

    def test_p57_cold_complement_watchlist(self):
        sr = self.p57.get("strategy_readiness", {})
        cls = sr.get("cold_complement_2bet", {}).get("classification", "")
        self.assertEqual(cls, "WATCHLIST_REHEARSAL_ONLY")

    def test_p57_zonal_entropy_watchlist(self):
        sr = self.p57.get("strategy_readiness", {})
        cls = sr.get("zonal_entropy_2bet", {}).get("classification", "")
        self.assertEqual(cls, "WATCHLIST_REHEARSAL_ONLY")

    def test_p57_p56_commit_ref(self):
        commit = self.p57.get("p56_ref", {}).get("commit", "")
        self.assertEqual(commit, "c3f0325")

    def test_p57_production_rows_before(self):
        rows = self.p57.get("pre_flight", {}).get("production_rows", 0)
        self.assertEqual(rows, EXPECTED_PROD_ROWS)


# ─── 2. Duplicate Check ────────────────────────────────────────────────────────

class TestDuplicateCheck(unittest.TestCase):

    def setUp(self):
        self.assertTrue(PROD_DB.exists(), f"Production DB missing: {PROD_DB}")
        self.conn = _db_connect()

    def tearDown(self):
        self.conn.close()

    def test_fourier30_not_in_production(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = ? AND lottery_type = 'POWER_LOTTO'",
            (P58_STRATEGY,),
        ).fetchone()[0]
        self.assertEqual(count, 0, f"{P58_STRATEGY} already in POWER_LOTTO production")

    def test_cold_complement_not_in_power_lotto(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = 'cold_complement_2bet' AND lottery_type = 'POWER_LOTTO'",
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_zonal_entropy_not_in_power_lotto(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = 'zonal_entropy_2bet' AND lottery_type = 'POWER_LOTTO'",
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_wave5_not_in_power_lotto_distinct(self):
        """Wave 5 strategy IDs must not appear in POWER_LOTTO distinct strategy list."""
        rows = self.conn.execute(
            "SELECT DISTINCT strategy_id FROM strategy_prediction_replays "
            "WHERE lottery_type = 'POWER_LOTTO'"
        ).fetchall()
        strategy_ids = {r["strategy_id"] for r in rows}
        wave5 = {P58_STRATEGY, "cold_complement_2bet", "zonal_entropy_2bet"}
        self.assertEqual(len(wave5 & strategy_ids), 0,
                         f"Wave 5 strategies found in POWER_LOTTO: {wave5 & strategy_ids}")

    def test_total_production_rows_unchanged(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        self.assertEqual(count, EXPECTED_PROD_ROWS)

    def test_champion_still_present(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = 'fourier_rhythm_3bet' AND lottery_type = 'POWER_LOTTO'"
        ).fetchone()[0]
        self.assertGreater(count, 0, "Champion fourier_rhythm_3bet missing from POWER_LOTTO")


# ─── 3. P58 JSON Structure ────────────────────────────────────────────────────

class TestP58JSONStructure(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P58_JSON.exists(), f"P58 JSON missing: {P58_JSON}")
        self.p58 = _load_p58()

    def test_p58_file_exists(self):
        self.assertTrue(P58_JSON.exists())

    def test_phase_is_p58(self):
        self.assertEqual(self.p58.get("phase"), "P58")

    def test_lottery_type_power_lotto(self):
        self.assertEqual(self.p58.get("lottery_type"), "POWER_LOTTO")

    def test_strategy_field(self):
        self.assertEqual(self.p58.get("strategy"), P58_STRATEGY)

    def test_controlled_apply_id(self):
        self.assertEqual(self.p58.get("controlled_apply_id"), CONTROLLED_APPLY_ID)

    def test_mode_proposal_only(self):
        self.assertEqual(self.p58.get("mode"), "PROPOSAL_ONLY")

    def test_overall_ok_true(self):
        self.assertTrue(self.p58.get("overall_ok"))

    def test_pre_flight_section_present(self):
        self.assertIn("pre_flight", self.p58)
        pf = self.p58["pre_flight"]
        self.assertIn("production_rows", pf)
        self.assertIn("duplicate_check_pass", pf)

    def test_proposal_section_present(self):
        self.assertIn("proposal", self.p58)
        prop = self.p58["proposal"]
        for key in ["controlled_apply_id", "mode", "hit_stats", "governance",
                    "pre_apply_checklist", "rollback_plan", "sample_rows"]:
            self.assertIn(key, prop, f"proposal.{key} missing")

    def test_governance_section_present(self):
        self.assertIn("governance", self.p58)

    def test_p57_ref_section_present(self):
        self.assertIn("p57_ref", self.p58)
        ref = self.p58["p57_ref"]
        self.assertEqual(ref.get("commit"), "aea8ff7")

    def test_required_top_level_keys(self):
        required = [
            "classification", "phase", "lottery_type", "strategy",
            "controlled_apply_id", "mode", "overall_ok",
            "pre_flight", "proposal", "governance", "p57_ref",
        ]
        for k in required:
            self.assertIn(k, self.p58, f"Top-level key missing: {k}")

    def test_json_is_valid(self):
        # Already loaded without error; confirm key count
        self.assertGreater(len(self.p58), 5)

    def test_p58_strategy_matches_p57_cohort(self):
        p57 = _load_p57()
        cohort = p57.get("p58_cohort", [])
        self.assertIn(self.p58.get("strategy"), cohort)


# ─── 4. Governance Constraints ────────────────────────────────────────────────

class TestP58GovernanceConstraints(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P58_JSON.exists())
        self.p58 = _load_p58()

    def test_no_production_db_write(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("production_db_write", True))

    def test_no_lifecycle_promotion(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("lifecycle_promotion", True))

    def test_no_champion_replacement(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("champion_replacement", True))

    def test_no_registry_mutation(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("registry_mutation", True))

    def test_no_live_api_call(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("live_api_call", True))

    def test_no_online_promotion(self):
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("online_promotion", True))

    def test_watchlist_strategies_excluded_from_governance(self):
        gov = self.p58.get("governance", {})
        excluded = set(gov.get("watchlist_strategies_excluded", []))
        self.assertIn("cold_complement_2bet", excluded)
        self.assertIn("zonal_entropy_2bet", excluded)

    def test_proposal_governance_no_prod_write(self):
        prop_gov = self.p58.get("proposal", {}).get("governance", {})
        self.assertFalse(prop_gov.get("production_db_write", True))

    def test_proposal_governance_no_online_promotion(self):
        prop_gov = self.p58.get("proposal", {}).get("governance", {})
        self.assertFalse(prop_gov.get("online_promotion", True))

    def test_production_db_rows_unchanged_in_preflight(self):
        rows = self.p58.get("pre_flight", {}).get("production_rows", -1)
        self.assertEqual(rows, EXPECTED_PROD_ROWS)

    def test_mode_is_proposal_only(self):
        self.assertEqual(self.p58.get("mode"), "PROPOSAL_ONLY")


# ─── 5. Cohort Constraints ────────────────────────────────────────────────────

class TestP58CohortConstraints(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P58_JSON.exists())
        self.p58 = _load_p58()
        self.prop = self.p58.get("proposal", {})

    def test_only_fourier30_in_p58_strategy(self):
        self.assertEqual(self.p58.get("strategy"), P58_STRATEGY)

    def test_excluded_strategies_in_proposal(self):
        excluded = self.prop.get("excluded_strategies", [])
        self.assertIn("cold_complement_2bet", excluded)
        self.assertIn("zonal_entropy_2bet", excluded)

    def test_cold_complement_not_referenced_as_apply(self):
        # controlled_apply_id must not reference cold_complement
        caid = self.p58.get("controlled_apply_id", "")
        self.assertNotIn("cold_complement", caid)

    def test_zonal_entropy_not_referenced_as_apply(self):
        caid = self.p58.get("controlled_apply_id", "")
        self.assertNotIn("zonal_entropy", caid)

    def test_expected_new_rows_correct(self):
        rows = self.prop.get("expected_new_rows", 0)
        self.assertEqual(rows, EXPECTED_NEW_ROWS)

    def test_rows_generated_correct(self):
        rows_gen = self.prop.get("rows_generated", 0)
        self.assertEqual(rows_gen, EXPECTED_NEW_ROWS)

    def test_projected_rows_after_correct(self):
        projected = self.prop.get("projected_rows_after", 0)
        self.assertEqual(projected, EXPECTED_ROWS_AFTER)

    def test_production_rows_before_correct(self):
        rows_before = self.prop.get("production_rows_before", 0)
        self.assertEqual(rows_before, EXPECTED_PROD_ROWS)

    def test_draw_range_both_keys_present(self):
        dr = self.prop.get("draw_range", {})
        self.assertIn("first", dr)
        self.assertIn("last", dr)
        self.assertIsNotNone(dr.get("first"))
        self.assertIsNotNone(dr.get("last"))


# ─── 6. Proposal Validity ─────────────────────────────────────────────────────

class TestP58ProposalValidity(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P58_JSON.exists())
        self.p58 = _load_p58()
        self.prop = self.p58.get("proposal", {})

    def test_authorization_phrase_present(self):
        phrase = self.prop.get("authorization_phrase", "")
        self.assertIn("YES apply Wave 5 POWER_LOTTO strategies to production DB", phrase)

    def test_authorization_required_true(self):
        self.assertTrue(self.prop.get("authorization_required", False))

    def test_rollback_plan_not_empty(self):
        plan = self.prop.get("rollback_plan", [])
        self.assertGreater(len(plan), 0)

    def test_rollback_sql_present(self):
        sql = self.prop.get("rollback_sql", "")
        self.assertIn("DELETE FROM strategy_prediction_replays", sql)
        self.assertIn(CONTROLLED_APPLY_ID, sql)

    def test_pre_apply_checklist_not_empty(self):
        checklist = self.prop.get("pre_apply_checklist", [])
        self.assertGreater(len(checklist), 5)

    def test_pre_apply_checklist_includes_backup(self):
        checklist = " ".join(self.prop.get("pre_apply_checklist", []))
        self.assertIn("backup", checklist.lower())

    def test_pre_apply_checklist_includes_duplicate_check(self):
        checklist = " ".join(self.prop.get("pre_apply_checklist", []))
        self.assertIn("duplicate", checklist.lower())

    def test_pre_apply_checklist_includes_drift_guard(self):
        checklist = " ".join(self.prop.get("pre_apply_checklist", []))
        self.assertIn("drift", checklist.lower())

    def test_sample_rows_present(self):
        samples = self.prop.get("sample_rows", [])
        self.assertGreaterEqual(len(samples), 2)

    def test_sample_rows_correct_fields(self):
        samples = self.prop.get("sample_rows", [])
        if samples:
            s = samples[0]
            for field in ["target_draw", "predicted", "predicted_special", "hit_count"]:
                self.assertIn(field, s, f"sample_rows[0] missing: {field}")

    def test_insert_sql_template_present(self):
        sql = self.prop.get("insert_sql_template", "")
        self.assertIn("INSERT INTO strategy_prediction_replays", sql)

    def test_insert_sql_no_execute_in_proposal(self):
        # Verify the SQL is a template, not executed (mode=PROPOSAL_ONLY)
        self.assertEqual(self.p58.get("mode"), "PROPOSAL_ONLY")
        gov = self.p58.get("governance", {})
        self.assertFalse(gov.get("production_db_write", True))


# ─── 7. Statistical Validity ──────────────────────────────────────────────────

class TestP58StatisticalValidity(unittest.TestCase):

    def setUp(self):
        self.assertTrue(P58_JSON.exists())
        self.p58 = _load_p58()
        self.prop = self.p58.get("proposal", {})

    def test_hit_stats_present(self):
        hs = self.prop.get("hit_stats", {})
        for key in ["predicted", "hit_3plus", "hit_3plus_rate", "special_hits",
                    "special_hit_rate", "hit_count_distribution"]:
            self.assertIn(key, hs, f"hit_stats.{key} missing")

    def test_predicted_count_is_1500(self):
        hs = self.prop.get("hit_stats", {})
        self.assertEqual(hs.get("predicted", 0), 1500)

    def test_m3plus_rate_in_valid_range(self):
        hs = self.prop.get("hit_stats", {})
        rate = hs.get("hit_3plus_rate", 0)
        self.assertGreater(rate, 0.0, "M3+ rate must be > 0")
        self.assertLess(rate, 1.0, "M3+ rate must be < 1")

    def test_m3plus_rate_above_or_near_baseline(self):
        # P57 result: 4.07% vs baseline 3.87% — directional positive
        hs = self.prop.get("hit_stats", {})
        rate = hs.get("hit_3plus_rate", 0)
        baseline = self.prop.get("theoretical_m3_baseline", 0.0387)
        delta = rate - baseline
        # Ensure not catastrophically below baseline (>-2%)
        self.assertGreater(delta, -0.02, f"M3+ rate too far below baseline: {rate} vs {baseline}")

    def test_theoretical_baseline_present(self):
        baseline = self.prop.get("theoretical_m3_baseline", 0)
        self.assertAlmostEqual(baseline, 0.0387, places=3)

    def test_theoretical_special_baseline(self):
        sb = self.prop.get("theoretical_special_baseline", 0)
        self.assertAlmostEqual(sb, 0.125, places=3)

    def test_z_test_present(self):
        zt = self.prop.get("z_test", {})
        for key in ["z", "p_value", "significant_at_05", "baseline", "observed_rate"]:
            self.assertIn(key, zt, f"z_test.{key} missing")

    def test_schema_validation_pass(self):
        sv = self.prop.get("schema_validation", {})
        self.assertTrue(sv.get("valid", False), f"Schema errors: {sv.get('errors', [])}")

    def test_leakage_check_pass(self):
        lc = self.prop.get("leakage_check", {})
        self.assertTrue(lc.get("pass", False), f"Leakage violations: {lc.get('violations', [])}")

    def test_duplicate_check_in_proposal_pass(self):
        dc = self.prop.get("duplicate_check", {})
        self.assertTrue(dc.get("pass", False))
        self.assertEqual(dc.get("existing_in_prod", -1), 0)


# ─── 8. Production DB State ───────────────────────────────────────────────────

class TestP58ProductionDBState(unittest.TestCase):

    def setUp(self):
        self.assertTrue(PROD_DB.exists())
        self.conn = _db_connect()

    def tearDown(self):
        self.conn.close()

    def test_total_rows_still_42460(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        self.assertEqual(count, EXPECTED_PROD_ROWS,
                         f"Production rows changed: expected {EXPECTED_PROD_ROWS}, got {count}")

    def test_power_lotto_rows_unchanged(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type = 'POWER_LOTTO'"
        ).fetchone()[0]
        self.assertEqual(count, 9140)

    def test_no_p58_controlled_apply_id_in_db(self):
        """controlled_apply_id for P58 must NOT appear in production DB (proposal mode)."""
        count = self.conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        self.assertEqual(count, 0,
                         f"P58 controlled_apply_id found in production DB: {count} rows")

    def test_power_lotto_strategy_count_unchanged(self):
        """Still exactly 6 distinct strategy IDs in POWER_LOTTO."""
        count = self.conn.execute(
            "SELECT COUNT(DISTINCT strategy_id) FROM strategy_prediction_replays "
            "WHERE lottery_type = 'POWER_LOTTO'"
        ).fetchone()[0]
        self.assertEqual(count, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
