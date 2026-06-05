"""
Targeted tests for P214C 3_STAR/4_STAR straight-play Bonferroni-corrected diagnostic scan.
Validates script functions, artifact content, and governance booleans.
"""
import json
import math
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

SCRIPT = "p214c_3star_4star_straight_play_bonferroni_diagnostic_scan"
ARTIFACT_JSON = "outputs/research/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_20260605.json"
ARTIFACT_MD = "outputs/research/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_20260605.md"
ARTIFACT_ROWS = "outputs/research/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan_rows_20260605.json"


def mod():
    import importlib
    return importlib.import_module(SCRIPT)


def js():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


def md():
    with open(ARTIFACT_MD) as f:
        return f.read()


def rows_js():
    with open(ARTIFACT_ROWS) as f:
        return json.load(f)


def make_temp_db(star_rows: list) -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL DEFAULT '[]',
            special INTEGER DEFAULT 0,
            numbers_positional TEXT DEFAULT NULL
        )
    """)
    conn.executemany(
        "INSERT INTO draws (draw, date, lottery_type, numbers, numbers_positional) VALUES (?,?,?,?,?)",
        star_rows,
    )
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Script import tests
# ---------------------------------------------------------------------------

class TestScriptImports(unittest.TestCase):
    def test_imports(self):
        m = mod()
        self.assertIsNotNone(m)

    def test_has_run_scan(self):
        self.assertTrue(hasattr(mod(), "run_scan"))

    def test_has_chi2_sf(self):
        self.assertTrue(hasattr(mod(), "chi2_sf"))

    def test_has_run_position_tests(self):
        self.assertTrue(hasattr(mod(), "run_position_tests"))

    def test_has_apply_bonferroni(self):
        self.assertTrue(hasattr(mod(), "apply_bonferroni"))

    def test_has_run_chi2_uniformity(self):
        self.assertTrue(hasattr(mod(), "run_chi2_uniformity"))

    def test_has_walk_forward_oos_check(self):
        self.assertTrue(hasattr(mod(), "walk_forward_oos_check"))


# ---------------------------------------------------------------------------
# Baseline constant tests
# ---------------------------------------------------------------------------

class TestConstants(unittest.TestCase):
    def test_3star_exact_baseline_1_in_1000(self):
        m = mod()
        self.assertAlmostEqual(m.LOTTERY_CONFIGS["3_STAR"]["exact_baseline"], 0.001, places=6)

    def test_4star_exact_baseline_1_in_10000(self):
        m = mod()
        self.assertAlmostEqual(m.LOTTERY_CONFIGS["4_STAR"]["exact_baseline"], 0.0001, places=7)

    def test_4star_exact_excluded_true(self):
        m = mod()
        self.assertTrue(m.LOTTERY_CONFIGS["4_STAR"]["exact_excluded"])

    def test_3star_exact_excluded_false(self):
        m = mod()
        self.assertFalse(m.LOTTERY_CONFIGS["3_STAR"]["exact_excluded"])

    def test_alpha_is_0_05(self):
        m = mod()
        self.assertAlmostEqual(m.ALPHA, 0.05, places=5)

    def test_3star_n_positions_3(self):
        m = mod()
        self.assertEqual(m.LOTTERY_CONFIGS["3_STAR"]["n_positions"], 3)

    def test_4star_n_positions_4(self):
        m = mod()
        self.assertEqual(m.LOTTERY_CONFIGS["4_STAR"]["n_positions"], 4)


# ---------------------------------------------------------------------------
# chi2_sf accuracy tests
# ---------------------------------------------------------------------------

class TestChi2SF(unittest.TestCase):
    def test_chi2_zero_gives_1(self):
        p = mod().chi2_sf(0.0, 9)
        self.assertAlmostEqual(p, 1.0, places=3)

    def test_chi2_large_gives_small_p(self):
        p = mod().chi2_sf(50.0, 9)
        self.assertLess(p, 0.0001)

    def test_chi2_at_critical_95(self):
        # chi2(9) critical at alpha=0.05 is 16.919
        p = mod().chi2_sf(16.919, 9)
        self.assertAlmostEqual(p, 0.05, delta=0.005)

    def test_known_value(self):
        # chi2=9.443, df=9: p ≈ 0.40
        p = mod().chi2_sf(9.443, 9)
        self.assertGreater(p, 0.3)
        self.assertLess(p, 0.5)


# ---------------------------------------------------------------------------
# Uniformity test logic
# ---------------------------------------------------------------------------

class TestChi2Uniformity(unittest.TestCase):
    def setUp(self):
        self.m = mod()

    def test_uniform_counts_low_chi2(self):
        counts = {d: 100 for d in range(10)}
        counts["total"] = 1000
        result = self.m.run_chi2_uniformity(counts)
        self.assertAlmostEqual(result["chi2"], 0.0, places=5)
        self.assertGreater(result["p_raw"], 0.9)

    def test_concentrated_counts_high_chi2(self):
        counts = {d: 0 for d in range(10)}
        counts[5] = 1000
        counts["total"] = 1000
        result = self.m.run_chi2_uniformity(counts)
        self.assertGreater(result["chi2"], 100)
        self.assertLess(result["p_raw"], 0.0001)

    def test_empty_returns_p1(self):
        counts = {d: 0 for d in range(10)}
        counts["total"] = 0
        result = self.m.run_chi2_uniformity(counts)
        self.assertEqual(result["p_raw"], 1.0)


# ---------------------------------------------------------------------------
# Bonferroni correction
# ---------------------------------------------------------------------------

class TestBonferroniApplication(unittest.TestCase):
    def setUp(self):
        self.m = mod()

    def test_bonferroni_alpha_equals_alpha_over_family(self):
        tests = [{"p_raw": 0.01, "uncorrected_pass": False, "bonferroni_pass": False}]
        result = self.m.apply_bonferroni(tests, family_size=7)
        expected_ba = 0.05 / 7
        self.assertAlmostEqual(result[0]["bonferroni_alpha"], expected_ba, places=6)

    def test_bonferroni_pass_when_p_below_threshold(self):
        ba = 0.05 / 7  # ≈ 0.00714
        tests = [{"p_raw": 0.001, "uncorrected_pass": True, "bonferroni_pass": False}]
        result = self.m.apply_bonferroni(tests, family_size=7)
        self.assertTrue(result[0]["bonferroni_pass"])

    def test_bonferroni_fail_when_p_above_threshold(self):
        tests = [{"p_raw": 0.03, "uncorrected_pass": True, "bonferroni_pass": False}]
        result = self.m.apply_bonferroni(tests, family_size=7)
        self.assertFalse(result[0]["bonferroni_pass"])
        self.assertEqual(result[0]["classification"], "UNCORRECTED_WEAK")

    def test_family_size_recorded_in_each_test(self):
        tests = [{"p_raw": 0.5, "uncorrected_pass": False, "bonferroni_pass": False}]
        result = self.m.apply_bonferroni(tests, family_size=7)
        self.assertEqual(result[0]["family_size"], 7)


# ---------------------------------------------------------------------------
# No-DB-write via temp DB
# ---------------------------------------------------------------------------

class TestNoDatabaseWrite(unittest.TestCase):
    def setUp(self):
        self.m = mod()
        rows = []
        for i in range(100):
            digits = [i % 10, (i + 3) % 10, (i + 7) % 10]
            rows.append((str(100000 + i), "2026-01-01", "3_STAR", "[]", json.dumps(digits)))
        for i in range(80):
            digits = [i % 10, (i + 2) % 10, (i + 5) % 10, (i + 8) % 10]
            rows.append((str(100000 + i), "2026-01-01", "4_STAR", "[]", json.dumps(digits)))
        self.db_path = make_temp_db(rows)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_load_draws_does_not_write(self):
        before = sqlite3.connect(self.db_path).execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        conn = self.m.open_db_readonly(self.db_path)
        _ = self.m.load_star_draws(conn, "3_STAR")
        conn.close()
        after = sqlite3.connect(self.db_path).execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        self.assertEqual(before, after)

    def test_position_tests_do_not_write(self):
        conn = self.m.open_db_readonly(self.db_path)
        draws = self.m.load_star_draws(conn, "3_STAR")
        conn.close()
        before = sqlite3.connect(self.db_path).execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        _ = self.m.run_position_tests("3_STAR", draws)
        after = sqlite3.connect(self.db_path).execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        self.assertEqual(before, after)

    def test_position_tests_return_correct_count_3star(self):
        conn = self.m.open_db_readonly(self.db_path)
        draws = self.m.load_star_draws(conn, "3_STAR")
        conn.close()
        tests = self.m.run_position_tests("3_STAR", draws)
        self.assertEqual(len(tests), 3)

    def test_position_tests_return_correct_count_4star(self):
        conn = self.m.open_db_readonly(self.db_path)
        draws = self.m.load_star_draws(conn, "4_STAR")
        conn.close()
        tests = self.m.run_position_tests("4_STAR", draws)
        self.assertEqual(len(tests), 4)


# ---------------------------------------------------------------------------
# Family size equals tests run
# ---------------------------------------------------------------------------

class TestFamilySize(unittest.TestCase):
    def test_json_family_size_is_7(self):
        d = js()
        self.assertEqual(d["family_size"], 7)

    def test_json_tests_run_count_equals_family_size(self):
        d = js()
        self.assertEqual(len(d["tests_run"]), d["family_size"])

    def test_rows_test_rows_count_equals_family_size(self):
        r = rows_js()
        self.assertEqual(len(r["test_rows"]), r["family_size"])

    def test_rows_family_size_matches_json(self):
        d = js()
        r = rows_js()
        self.assertEqual(d["family_size"], r["family_size"])

    def test_3star_has_3_tests(self):
        d = js()
        n = sum(1 for t in d["tests_run"] if t["lottery_type"] == "3_STAR")
        self.assertEqual(n, 3)

    def test_4star_has_4_tests(self):
        d = js()
        n = sum(1 for t in d["tests_run"] if t["lottery_type"] == "4_STAR")
        self.assertEqual(n, 4)


# ---------------------------------------------------------------------------
# Bonferroni alpha in artifact
# ---------------------------------------------------------------------------

class TestBonferroniAlphaInArtifact(unittest.TestCase):
    def test_bonferroni_alpha_correct_value(self):
        d = js()
        expected = round(0.05 / 7, 8)
        self.assertAlmostEqual(d["bonferroni_alpha"], expected, places=6)

    def test_all_tests_have_bonferroni_alpha(self):
        r = rows_js()
        for t in r["test_rows"]:
            self.assertIn("bonferroni_pass", t)

    def test_corrected_p_values_present_in_tests_run(self):
        d = js()
        for t in d["tests_run"]:
            self.assertIn("p_raw", t)
            self.assertIn("bonferroni_pass", t)
            self.assertIn("bonferroni_alpha", t)


# ---------------------------------------------------------------------------
# 4_STAR exact excluded
# ---------------------------------------------------------------------------

class TestFourStarExactExcluded(unittest.TestCase):
    def test_4star_exact_excluded_in_json(self):
        d = js()
        self.assertTrue(d["findings_by_lottery"]["4_STAR"]["exact_match_excluded"])

    def test_4star_power_inoperable(self):
        d = js()
        self.assertEqual(d["findings_by_lottery"]["4_STAR"]["exact_match_power"], "INOPERABLE")

    def test_md_mentions_4star_excluded(self):
        text = md()
        self.assertIn("excluded", text.lower())
        self.assertIn("INOPERABLE", text)

    def test_md_mentions_4star_exact_baseline(self):
        text = md()
        self.assertIn("1/10000", text)


# ---------------------------------------------------------------------------
# Artifact existence and content
# ---------------------------------------------------------------------------

class TestArtifacts(unittest.TestCase):
    def test_json_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_JSON))

    def test_md_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_MD))

    def test_rows_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_ROWS))

    def test_json_parses(self):
        d = js()
        self.assertIsInstance(d, dict)

    def test_rows_parses(self):
        r = rows_js()
        self.assertIsInstance(r, dict)

    def test_classification_approved(self):
        d = js()
        approved = {
            "P214C_3STAR_4STAR_STRAIGHT_PLAY_BONFERRONI_DIAGNOSTIC_SCAN_COMPLETE",
            "P214C_STRAIGHT_PLAY_DIAGNOSTIC_NULL_OR_UNDERPOWERED",
            "P214C_STRAIGHT_PLAY_DIAGNOSTIC_POWER_LIMITED",
            "P214C_STRAIGHT_PLAY_DIAGNOSTIC_BLOCKED_BY_DATA_INCONSISTENCY",
        }
        self.assertIn(d["classification"], approved)

    def test_task_id_p214c(self):
        d = js()
        self.assertEqual(d["task_id"], "P214C")

    def test_task_type_type_c(self):
        d = js()
        self.assertEqual(d["task_type"], "Type C")


# ---------------------------------------------------------------------------
# No-claim booleans
# ---------------------------------------------------------------------------

class TestNoClaims(unittest.TestCase):
    def test_production_db_write_false(self):
        self.assertIs(js()["production_db_write"], False)

    def test_ingestion_performed_false(self):
        self.assertIs(js()["ingestion_performed"], False)

    def test_replay_generation_performed_false(self):
        self.assertIs(js()["replay_generation_performed"], False)

    def test_strategy_scan_performed_false(self):
        self.assertIs(js()["strategy_scan_performed"], False)

    def test_no_registry_mutation_true(self):
        self.assertIs(js()["no_registry_mutation"], True)

    def test_no_production_recommendation_change_true(self):
        self.assertIs(js()["no_production_recommendation_change"], True)

    def test_no_monitoring_change_true(self):
        self.assertIs(js()["no_monitoring_change"], True)

    def test_no_strategy_authorization_true(self):
        self.assertIs(js()["no_strategy_authorization"], True)

    def test_no_betting_advice_true(self):
        self.assertIs(js()["no_betting_advice"], True)

    def test_no_recommended_numbers_true(self):
        self.assertIs(js()["no_recommended_numbers"], True)


# ---------------------------------------------------------------------------
# No replay rows generated
# ---------------------------------------------------------------------------

class TestNoReplayGeneration(unittest.TestCase):
    def test_star_replay_rows_zero(self):
        d = js()
        self.assertEqual(d["star_replay_rows_by_lottery"]["3_STAR"], 0)
        self.assertEqual(d["star_replay_rows_by_lottery"]["4_STAR"], 0)

    def test_md_no_strategy_claim(self):
        text = md()
        self.assertNotIn("guaranteed win", text.lower())
        self.assertNotIn("will improve", text.lower())

    def test_md_has_no_claim_attestation(self):
        text = md()
        self.assertIn("No-Claim Attestation", text)

    def test_json_draw_rows_total(self):
        d = js()
        self.assertEqual(d["draw_rows_total"], 64361)

    def test_json_star_rows_5850(self):
        d = js()
        self.assertEqual(d["star_rows_by_lottery"]["3_STAR"], 5850)
        self.assertEqual(d["star_rows_by_lottery"]["4_STAR"], 5850)


# ---------------------------------------------------------------------------
# Corrected significant findings
# ---------------------------------------------------------------------------

class TestSignificantFindings(unittest.TestCase):
    def test_corrected_significant_list_length_matches_count(self):
        d = js()
        n_bonf = d["multiple_testing_policy"]["n_bonferroni_significant"]
        self.assertEqual(len(d["corrected_significant_findings"]), n_bonf)

    def test_p238b_observation_only(self):
        d = js()
        self.assertIn("RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY", d["p238b_interpretation"])

    def test_uncorrected_weak_label_present(self):
        d = js()
        label = d["multiple_testing_policy"]["uncorrected_weak_label"]
        self.assertIn("EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED", label)
        self.assertIn("does not authorize", label)

    def test_oos_checks_key_in_json(self):
        d = js()
        self.assertIn("oos_checks", d)

    def test_bonferroni_alpha_in_rows(self):
        r = rows_js()
        self.assertIn("bonferroni_alpha", r)
        expected = round(0.05 / 7, 8)
        self.assertAlmostEqual(r["bonferroni_alpha"], expected, places=6)


# ---------------------------------------------------------------------------
# Baselines in MD
# ---------------------------------------------------------------------------

class TestMarkdownContent(unittest.TestCase):
    def test_md_mentions_bonferroni(self):
        self.assertIn("Bonferroni", md())

    def test_md_mentions_family_size_7(self):
        self.assertIn("7", md())

    def test_md_mentions_p227c(self):
        self.assertIn("P227C", md())

    def test_md_mentions_3star_1000(self):
        self.assertIn("1/1000", md())

    def test_md_mentions_walk_forward(self):
        self.assertIn("walk-forward", md().lower())


if __name__ == "__main__":
    unittest.main()
