"""
Targeted tests for P214B 3_STAR/4_STAR straight-play read-only diagnostic.
Validates the script, artifact files, and governance booleans.
No DB write. Uses injected temp DB where real DB is not available.
"""
import json
import math
import os
import sqlite3
import sys
import tempfile
import unittest

# Ensure script can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

SCRIPT_MODULE = "p214b_3star_4star_straight_play_readonly_diagnostic"
ARTIFACT_JSON = "outputs/research/p214b_3star_4star_straight_play_readonly_diagnostic_20260605.json"
ARTIFACT_MD = "outputs/research/p214b_3star_4star_straight_play_readonly_diagnostic_20260605.md"
ARTIFACT_ROWS = "outputs/research/p214b_3star_4star_straight_play_readonly_diagnostic_rows_20260605.json"


def load_script():
    import importlib
    return importlib.import_module(SCRIPT_MODULE)


def load_json():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


def load_md():
    with open(ARTIFACT_MD) as f:
        return f.read()


def make_temp_db(star_rows: list) -> str:
    """
    Create a minimal temp SQLite DB with the draws table.
    star_rows: list of (draw, date, lottery_type, numbers_positional) tuples.
    Returns temp file path.
    """
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
# Import tests
# ---------------------------------------------------------------------------

class TestScriptImports(unittest.TestCase):
    def test_script_imports_successfully(self):
        mod = load_script()
        self.assertIsNotNone(mod)

    def test_script_has_main(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "main"), "Script must have a main() function")

    def test_script_has_open_db_readonly(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "open_db_readonly"))

    def test_script_has_load_star_draws(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "load_star_draws"))

    def test_script_has_run_diagnostic(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "run_diagnostic"))

    def test_script_has_compute_per_position_distribution(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "compute_per_position_distribution"))

    def test_script_has_compute_chi_squared_descriptive(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "compute_chi_squared_descriptive"))

    def test_script_has_compute_entropy(self):
        mod = load_script()
        self.assertTrue(hasattr(mod, "compute_entropy"))


# ---------------------------------------------------------------------------
# Baseline constant tests
# ---------------------------------------------------------------------------

class TestBaselines(unittest.TestCase):
    def test_3star_exact_baseline_is_1_in_1000(self):
        mod = load_script()
        cfg = mod.LOTTERY_CONFIGS["3_STAR"]
        self.assertAlmostEqual(cfg["exact_baseline"], 1 / 1000, places=6)

    def test_4star_exact_baseline_is_1_in_10000(self):
        mod = load_script()
        cfg = mod.LOTTERY_CONFIGS["4_STAR"]
        self.assertAlmostEqual(cfg["exact_baseline"], 1 / 10000, places=7)

    def test_per_position_baseline_is_1_in_10(self):
        mod = load_script()
        for lt in ("3_STAR", "4_STAR"):
            cfg = mod.LOTTERY_CONFIGS[lt]
            self.assertAlmostEqual(cfg["per_position_baseline"], 1 / 10, places=6,
                                   msg=f"{lt} per_position_baseline must be 1/10")

    def test_3star_combination_space_is_1000(self):
        mod = load_script()
        self.assertEqual(mod.LOTTERY_CONFIGS["3_STAR"]["combination_space"], 1000)

    def test_4star_combination_space_is_10000(self):
        mod = load_script()
        self.assertEqual(mod.LOTTERY_CONFIGS["4_STAR"]["combination_space"], 10000)

    def test_3star_n_positions_is_3(self):
        mod = load_script()
        self.assertEqual(mod.LOTTERY_CONFIGS["3_STAR"]["n_positions"], 3)

    def test_4star_n_positions_is_4(self):
        mod = load_script()
        self.assertEqual(mod.LOTTERY_CONFIGS["4_STAR"]["n_positions"], 4)


# ---------------------------------------------------------------------------
# No-DB-write tests via temp DB
# ---------------------------------------------------------------------------

class TestNoDatabaseWrite(unittest.TestCase):
    def setUp(self):
        self.mod = load_script()
        # Minimal 3_STAR rows
        rows = []
        for i in range(20):
            digits = [i % 10, (i + 1) % 10, (i + 2) % 10]
            rows.append((str(115000000 + i), "2026-01-01", "3_STAR", "[]", json.dumps(digits)))
        for i in range(15):
            digits = [i % 10, (i + 1) % 10, (i + 2) % 10, (i + 3) % 10]
            rows.append((str(115000000 + i), "2026-01-01", "4_STAR", "[]", json.dumps(digits)))
        self.db_path = make_temp_db(rows)

    def tearDown(self):
        if os.path.exists(self.db_path):
            # Verify no writes happened (size won't have grown by an insertion)
            os.remove(self.db_path)

    def test_load_draws_does_not_write_db(self):
        mtime_before = os.path.getmtime(self.db_path)
        conn = self.mod.open_db_readonly(self.db_path)
        draws = self.mod.load_star_draws(conn, "3_STAR")
        conn.close()
        mtime_after = os.path.getmtime(self.db_path)
        # mtime should not change (read-only access)
        self.assertGreaterEqual(len(draws), 0)
        # We don't assert exact mtime equality (WAL checkpoint) but verify no INSERT
        # Re-open and verify count unchanged
        conn2 = sqlite3.connect(self.db_path)
        count = conn2.execute("SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'").fetchone()[0]
        conn2.close()
        self.assertEqual(count, 20)

    def test_run_diagnostic_does_not_write_db(self):
        conn = self.mod.open_db_readonly(self.db_path)
        draws = self.mod.load_star_draws(conn, "3_STAR")
        conn.close()
        count_before = sqlite3.connect(self.db_path).execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        _ = self.mod.run_diagnostic("3_STAR", draws)
        count_after = sqlite3.connect(self.db_path).execute("SELECT COUNT(*) FROM draws").fetchone()[0]
        self.assertEqual(count_before, count_after, "run_diagnostic must not modify DB")

    def test_draws_loaded_correctly(self):
        conn = self.mod.open_db_readonly(self.db_path)
        draws = self.mod.load_star_draws(conn, "3_STAR")
        conn.close()
        self.assertEqual(len(draws), 20)
        for row in draws:
            self.assertIn("digits", row)
            self.assertEqual(len(row["digits"]), 3)
            for d in row["digits"]:
                self.assertIn(d, range(10))

    def test_draws_with_none_positional_excluded(self):
        """Rows with NULL numbers_positional must be excluded."""
        import sqlite3 as sq
        conn2 = sq.connect(self.db_path)
        conn2.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, numbers_positional) "
            "VALUES ('999999999', '2026-01-01', '3_STAR', '[]', NULL)"
        )
        conn2.commit()
        conn2.close()
        conn = self.mod.open_db_readonly(self.db_path)
        draws = self.mod.load_star_draws(conn, "3_STAR")
        conn.close()
        self.assertEqual(len(draws), 20, "NULL positional rows must not be included")


# ---------------------------------------------------------------------------
# Metric unit tests
# ---------------------------------------------------------------------------

class TestMetricComputations(unittest.TestCase):
    def setUp(self):
        self.mod = load_script()

    def test_entropy_uniform_is_log2_10(self):
        dist = {d: 100 for d in range(10)}
        dist["total"] = 1000
        entropy = self.mod.compute_entropy(dist)
        self.assertAlmostEqual(entropy, math.log2(10), places=3)

    def test_entropy_concentrated_is_lower(self):
        dist = {d: 0 for d in range(10)}
        dist[5] = 1000
        dist["total"] = 1000
        entropy = self.mod.compute_entropy(dist)
        self.assertAlmostEqual(entropy, 0.0, places=5)

    def test_chi2_uniform_is_near_zero(self):
        dist = {d: 100 for d in range(10)}
        dist["total"] = 1000
        result = self.mod.compute_chi_squared_descriptive(dist)
        self.assertAlmostEqual(result["chi2"], 0.0, places=5)

    def test_chi2_concentrated_is_large(self):
        dist = {d: 0 for d in range(10)}
        dist[0] = 1000
        dist["total"] = 1000
        result = self.mod.compute_chi_squared_descriptive(dist)
        self.assertGreater(result["chi2"], 100)

    def test_repeated_digit_rate_no_repeats(self):
        draws = [{"digits": [1, 2, 3]} for _ in range(10)]
        result = self.mod.compute_repeated_digit_rate(draws)
        self.assertEqual(result["repeat_rate"], 0.0)

    def test_repeated_digit_rate_all_repeats(self):
        draws = [{"digits": [5, 5, 5]} for _ in range(10)]
        result = self.mod.compute_repeated_digit_rate(draws)
        self.assertEqual(result["repeat_rate"], 1.0)

    def test_per_position_distribution_counts_correctly(self):
        draws = [
            {"digits": [1, 2, 3]},
            {"digits": [1, 3, 2]},
            {"digits": [4, 2, 3]},
        ]
        dist = self.mod.compute_per_position_distribution(draws, 3)
        self.assertEqual(dist[0][1], 2)  # 1 appears twice at pos 0
        self.assertEqual(dist[0][4], 1)  # 4 appears once at pos 0
        self.assertEqual(dist[1]["total"], 3)

    def test_window_summary_returns_none_if_insufficient(self):
        draws = [{"digits": [1, 2, 3]} for _ in range(10)]
        result = self.mod.compute_window_summary(draws, 150, 3)
        self.assertIsNone(result)

    def test_window_summary_returns_data_if_sufficient(self):
        draws = [{"digits": [i % 10, (i + 1) % 10, (i + 2) % 10]} for i in range(200)]
        result = self.mod.compute_window_summary(draws, 150, 3)
        self.assertIsNotNone(result)
        self.assertEqual(result["n_draws_in_window"], 150)
        self.assertIn("pos_0", result["positions"])


# ---------------------------------------------------------------------------
# Diagnostic output tests
# ---------------------------------------------------------------------------

class TestDiagnosticOutput(unittest.TestCase):
    def setUp(self):
        self.mod = load_script()
        draws = [{"draw": str(i), "date": "2026-01-01", "digits": [i % 10, (i + 1) % 10, (i + 2) % 10]}
                 for i in range(200)]
        self.findings = self.mod.run_diagnostic("3_STAR", draws)

    def test_findings_has_draw_count(self):
        self.assertEqual(self.findings["draw_count"], 200)

    def test_findings_has_correct_baseline(self):
        self.assertAlmostEqual(self.findings["exact_ordered_random_baseline"], 0.001, places=6)

    def test_findings_has_position_findings(self):
        pf = self.findings["position_findings"]
        self.assertIn("pos_0", pf)
        self.assertIn("pos_1", pf)
        self.assertIn("pos_2", pf)

    def test_findings_no_claim_note(self):
        note = self.findings["diagnostic_note"]
        self.assertIn("DESCRIPTIVE ONLY", note)
        self.assertIn("does not claim", note)

    def test_findings_power_status_correct(self):
        self.assertEqual(self.findings["power_status_exact"], "MARGINAL")
        self.assertEqual(self.findings["power_status_positional"], "TRACTABLE")

    def test_4star_power_inoperable(self):
        draws_4 = [{"draw": str(i), "date": "2026-01-01",
                    "digits": [i % 10, (i + 1) % 10, (i + 2) % 10, (i + 3) % 10]}
                   for i in range(200)]
        findings_4 = self.mod.run_diagnostic("4_STAR", draws_4)
        self.assertEqual(findings_4["power_status_exact"], "INOPERABLE")


# ---------------------------------------------------------------------------
# Artifact existence and content tests
# ---------------------------------------------------------------------------

class TestArtifactExists(unittest.TestCase):
    def test_json_artifact_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_JSON), f"JSON artifact missing: {ARTIFACT_JSON}")

    def test_md_artifact_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_MD), f"Markdown artifact missing: {ARTIFACT_MD}")

    def test_rows_artifact_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_ROWS), f"Rows artifact missing: {ARTIFACT_ROWS}")

    def test_json_parses(self):
        d = load_json()
        self.assertIsInstance(d, dict)
        self.assertGreater(len(d), 0)

    def test_rows_json_parses(self):
        with open(ARTIFACT_ROWS) as f:
            d = json.load(f)
        self.assertIsInstance(d, dict)


class TestArtifactClassification(unittest.TestCase):
    def test_json_classification_approved(self):
        d = load_json()
        approved = {
            "P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE",
            "P214B_STRAIGHT_PLAY_DIAGNOSTIC_NULL_OR_UNDERPOWERED",
            "P214B_STRAIGHT_PLAY_DIAGNOSTIC_POWER_LIMITED",
            "P214B_STRAIGHT_PLAY_DIAGNOSTIC_BLOCKED_BY_DATA_INCONSISTENCY",
        }
        self.assertIn(d["classification"], approved)

    def test_json_task_id_is_p214b(self):
        d = load_json()
        self.assertEqual(d["task_id"], "P214B")

    def test_json_task_type_is_type_c(self):
        d = load_json()
        self.assertEqual(d["task_type"], "Type C")


class TestArtifactNoClaims(unittest.TestCase):
    def test_production_db_write_false(self):
        d = load_json()
        self.assertIs(d["production_db_write"], False)

    def test_ingestion_performed_false(self):
        d = load_json()
        self.assertIs(d["ingestion_performed"], False)

    def test_replay_generation_performed_false(self):
        d = load_json()
        self.assertIs(d["replay_generation_performed"], False)

    def test_strategy_scan_performed_false(self):
        d = load_json()
        self.assertIs(d["strategy_scan_performed"], False)

    def test_no_registry_mutation_true(self):
        d = load_json()
        self.assertIs(d["no_registry_mutation"], True)

    def test_no_production_recommendation_change_true(self):
        d = load_json()
        self.assertIs(d["no_production_recommendation_change"], True)

    def test_no_monitoring_change_true(self):
        d = load_json()
        self.assertIs(d["no_monitoring_change"], True)

    def test_no_strategy_authorization_true(self):
        d = load_json()
        self.assertIs(d["no_strategy_authorization"], True)

    def test_no_betting_advice_true(self):
        d = load_json()
        self.assertIs(d["no_betting_advice"], True)

    def test_no_recommended_numbers_true(self):
        d = load_json()
        self.assertIs(d["no_recommended_numbers"], True)


class TestArtifactBaselines(unittest.TestCase):
    def test_json_3star_baseline(self):
        d = load_json()
        self.assertIn("1/1000", d["baselines"]["3_STAR_exact_ordered"])

    def test_json_4star_baseline(self):
        d = load_json()
        self.assertIn("1/10000", d["baselines"]["4_STAR_exact_ordered"])

    def test_json_per_position_baseline(self):
        d = load_json()
        self.assertIn("1/10", d["baselines"]["per_position_digit_accuracy"])

    def test_md_mentions_3star_1000(self):
        md = load_md()
        self.assertIn("1/1000", md)

    def test_md_mentions_4star_10000(self):
        md = load_md()
        self.assertIn("1/10000", md)

    def test_json_4star_exact_match_excluded(self):
        d = load_json()
        self.assertIs(d["findings_by_lottery"]["4_STAR"]["exact_match_excluded"], True)


class TestArtifactPowerWarnings(unittest.TestCase):
    def test_json_3star_power_marginal(self):
        d = load_json()
        self.assertEqual(d["findings_by_lottery"]["3_STAR"]["power_status_exact"], "MARGINAL")

    def test_json_4star_power_inoperable(self):
        d = load_json()
        self.assertEqual(d["findings_by_lottery"]["4_STAR"]["power_status_exact"], "INOPERABLE")

    def test_md_mentions_inoperable(self):
        md = load_md()
        self.assertIn("INOPERABLE", md)

    def test_md_mentions_marginal(self):
        md = load_md()
        self.assertIn("MARGINAL", md)

    def test_md_mentions_power_warning(self):
        md = load_md()
        self.assertIn("Power Warning", md)


class TestArtifactNoForbiddenClaims(unittest.TestCase):
    def test_md_no_guaranteed_win(self):
        md = load_md()
        self.assertNotIn("guaranteed win", md.lower())

    def test_md_no_betting_recommendation(self):
        md = load_md()
        # Negation context is OK; check for affirmative claim pattern
        self.assertNotIn("will improve", md.lower())

    def test_md_no_recommended_next_numbers(self):
        md = load_md()
        # The phrase "recommended numbers" as a positive prescription
        self.assertNotIn("the following numbers", md.lower())

    def test_md_has_no_claim_attestation(self):
        md = load_md()
        self.assertTrue(
            "no claim" in md.lower() or "No-Claim" in md,
            "Markdown must include no-claim attestation"
        )

    def test_json_significance_tests_run_zero(self):
        d = load_json()
        self.assertEqual(d["multiple_testing_policy"]["significance_tests_run"], 0)


class TestArtifactDrawCounts(unittest.TestCase):
    def test_json_3star_draw_count_5850(self):
        d = load_json()
        self.assertEqual(d["star_rows_by_lottery"]["3_STAR"], 5850)

    def test_json_4star_draw_count_5850(self):
        d = load_json()
        self.assertEqual(d["star_rows_by_lottery"]["4_STAR"], 5850)

    def test_json_replay_rows_zero(self):
        d = load_json()
        self.assertEqual(d["star_replay_rows_by_lottery"]["3_STAR"], 0)
        self.assertEqual(d["star_replay_rows_by_lottery"]["4_STAR"], 0)

    def test_json_draw_rows_total(self):
        d = load_json()
        self.assertEqual(d["draw_rows_total"], 64361)


class TestArtifactPreRegisteredWindows(unittest.TestCase):
    def test_json_has_window_summaries_in_3star(self):
        d = load_json()
        # The JSON artifact doesn't include raw window summaries but the MD does
        # Verify the leakage guard lists windows
        guard = d["leakage_guard"]
        self.assertIn("pre_registered_windows_used", guard)
        windows = guard["pre_registered_windows_used"]
        for w in ("w150", "w500", "w750", "w1000"):
            self.assertIn(w, windows)

    def test_md_mentions_pre_registered_windows(self):
        md = load_md()
        self.assertIn("w150", md)
        self.assertIn("w500", md)
        self.assertIn("w1000", md)

    def test_md_mentions_p227c(self):
        md = load_md()
        self.assertIn("P227C", md)

    def test_md_mentions_bonferroni(self):
        md = load_md()
        self.assertIn("Bonferroni", md)

    def test_md_mentions_p238b(self):
        d = load_json()
        self.assertIn("RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY", d["p238b_interpretation"])


class TestArtifactAuthorizationPhrase(unittest.TestCase):
    def test_json_has_authorization_phrase(self):
        d = load_json()
        phrase = d["exact_authorization_phrase_for_next_direction"]
        self.assertGreater(len(phrase), 20)

    def test_authorization_phrase_mentions_p214c(self):
        d = load_json()
        phrase = d["exact_authorization_phrase_for_next_direction"]
        self.assertIn("P214C", phrase)

    def test_md_mentions_authorize_p214c(self):
        md = load_md()
        self.assertIn("P214C", md)


if __name__ == "__main__":
    unittest.main()
