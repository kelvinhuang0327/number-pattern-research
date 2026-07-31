"""
Targeted tests for P214 3_STAR/4_STAR straight-play feasibility and diagnostic protocol design.
Validates the artifact files and their content without touching the DB.
"""
import json
import os
import re
import unittest

ARTIFACT_MD = "outputs/research/p214_3star_4star_straight_play_feasibility_protocol_design_20260605.md"
ARTIFACT_JSON = "outputs/research/p214_3star_4star_straight_play_feasibility_protocol_design_20260605.json"


def load_json():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


def load_md():
    with open(ARTIFACT_MD) as f:
        return f.read()


class TestArtifactExists(unittest.TestCase):
    def test_markdown_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_MD), f"Markdown artifact not found: {ARTIFACT_MD}")

    def test_json_exists(self):
        self.assertTrue(os.path.isfile(ARTIFACT_JSON), f"JSON artifact not found: {ARTIFACT_JSON}")

    def test_json_parses(self):
        d = load_json()
        self.assertIsInstance(d, dict)
        self.assertGreater(len(d), 0)


class TestClassification(unittest.TestCase):
    def test_json_classification_approved(self):
        d = load_json()
        approved = {
            "P214_3STAR_4STAR_STRAIGHT_PLAY_FEASIBILITY_PROTOCOL_DESIGN_COMPLETE",
            "P214_STRAIGHT_PLAY_NOT_RECOMMENDED_AFTER_POWER_REVIEW",
            "P214_STRAIGHT_PLAY_BLOCKED_BY_BASELINE_AMBIGUITY",
            "P214_STRAIGHT_PLAY_REQUIRES_SEPARATE_DIAGNOSTIC_AUTHORIZATION",
        }
        self.assertIn(d["classification"], approved, f"Unexpected classification: {d['classification']}")

    def test_json_task_id(self):
        d = load_json()
        self.assertEqual(d["task_id"], "P214")

    def test_json_task_type_is_type_b(self):
        d = load_json()
        self.assertEqual(d["task_type"], "Type B")


class TestNoClaims(unittest.TestCase):
    def test_production_db_write_false(self):
        d = load_json()
        self.assertIs(d["production_db_write"], False)

    def test_ingestion_performed_false(self):
        d = load_json()
        self.assertIs(d["ingestion_performed"], False)

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


class TestBaselines(unittest.TestCase):
    def test_3star_baseline_includes_1_in_1000(self):
        d = load_json()
        baseline_3star = d["straight_play_baselines"]["3_STAR_exact_ordered_match"]
        self.assertIn("1/1000", baseline_3star, f"3_STAR baseline must include 1/1000, got: {baseline_3star}")

    def test_4star_baseline_includes_1_in_10000(self):
        d = load_json()
        baseline_4star = d["straight_play_baselines"]["4_STAR_exact_ordered_match"]
        self.assertIn("1/10000", baseline_4star, f"4_STAR baseline must include 1/10000, got: {baseline_4star}")

    def test_per_position_baseline_in_json(self):
        d = load_json()
        per_pos = d["straight_play_baselines"]["per_position_digit_accuracy"]
        self.assertIn("1/10", per_pos)

    def test_md_mentions_3star_1000(self):
        md = load_md()
        self.assertIn("1/1000", md, "Markdown must mention 3_STAR baseline 1/1000")

    def test_md_mentions_4star_10000(self):
        md = load_md()
        self.assertIn("1/10000", md, "Markdown must mention 4_STAR baseline 1/10000")


class TestP213LDataReadyState(unittest.TestCase):
    def test_json_p213l_data_ready_confirmed(self):
        d = load_json()
        self.assertIs(d["p213l_data_ready_confirmed"], True)

    def test_md_mentions_p213l(self):
        md = load_md()
        self.assertIn("P213L", md, "Markdown must reference P213L data recovery")

    def test_md_mentions_data_ready(self):
        md = load_md()
        self.assertTrue(
            "DATA_READY" in md or "data ready" in md.lower() or "positional" in md.lower(),
            "Markdown must mention data-ready state after P213L"
        )

    def test_json_star_rows_5850(self):
        d = load_json()
        self.assertEqual(d["star_rows_by_lottery"]["3_STAR"], 5850)
        self.assertEqual(d["star_rows_by_lottery"]["4_STAR"], 5850)


class TestP227CBoxPlayReference(unittest.TestCase):
    def test_json_references_p227c_result(self):
        d = load_json()
        result = d["p227c_box_play_prior_result"]
        self.assertIn("UNDERPOWERED", result, f"P227C result must mention UNDERPOWERED: {result}")

    def test_md_mentions_p227c(self):
        md = load_md()
        self.assertIn("P227C", md, "Markdown must reference P227C box-play result")

    def test_md_mentions_underpowered(self):
        md = load_md()
        self.assertIn("UNDERPOWERED", md, "Markdown must mention UNDERPOWERED_NO_SIGNAL from P227C")


class TestMultipleTestingCorrection(unittest.TestCase):
    def test_json_has_multiple_testing_policy(self):
        d = load_json()
        policy = d["multiple_testing_policy"]
        self.assertIsInstance(policy, dict)
        self.assertIn("primary_correction", policy)
        self.assertIn("Bonferroni", policy["primary_correction"])

    def test_md_mentions_bonferroni(self):
        md = load_md()
        self.assertIn("Bonferroni", md, "Markdown must mention Bonferroni correction")

    def test_md_mentions_multiple_testing(self):
        md = load_md()
        self.assertIn("multiple", md.lower(), "Markdown must discuss multiple-testing correction")

    def test_json_family_size_minimum(self):
        d = load_json()
        family_size = d["multiple_testing_policy"]["family_size_minimum"]
        self.assertGreaterEqual(family_size, 32, "Minimum family size should be >= 32")


class TestLeakageGuard(unittest.TestCase):
    def test_json_has_leakage_guard(self):
        d = load_json()
        guard = d["leakage_guard"]
        self.assertIsInstance(guard, dict)
        self.assertIn("feature_window_rule", guard)

    def test_md_mentions_leakage(self):
        md = load_md()
        self.assertTrue(
            "leakage" in md.lower() or "walk-forward" in md.lower(),
            "Markdown must mention leakage guard or walk-forward"
        )

    def test_json_walk_forward_rule(self):
        d = load_json()
        guard = d["leakage_guard"]
        self.assertIn("walk_forward_rule", guard)
        rule = guard["walk_forward_rule"]
        self.assertIn("OOS", rule, "Walk-forward rule must mention OOS")


class TestAuthorizationPhrase(unittest.TestCase):
    def test_json_has_exact_authorization_phrase(self):
        d = load_json()
        phrase = d["exact_authorization_phrase_for_next_direction"]
        self.assertTrue(len(phrase) > 20, "Authorization phrase must be non-trivial")

    def test_authorization_phrase_mentions_p214b(self):
        d = load_json()
        phrase = d["exact_authorization_phrase_for_next_direction"]
        self.assertIn("P214B", phrase, "Authorization phrase must mention P214B")

    def test_md_mentions_authorization_phrase(self):
        md = load_md()
        self.assertIn("Authorize P214B", md, "Markdown must include exact authorization phrase for P214B")


class TestNoBettingOrPromotionClaim(unittest.TestCase):
    def test_md_no_betting_advice_claim(self):
        md = load_md()
        forbidden_patterns = [
            "guaranteed win",
            "will improve hit rate",
        ]
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern.lower(), md.lower(), f"Markdown must not contain: {pattern}")

    def test_md_has_no_claim_attestation(self):
        md = load_md()
        self.assertTrue(
            "no claim" in md.lower() or "No-Claim" in md or "no betting" in md.lower(),
            "Markdown must include no-claim attestation"
        )


if __name__ == "__main__":
    unittest.main()
