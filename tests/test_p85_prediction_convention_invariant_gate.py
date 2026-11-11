"""
tests/test_p85_prediction_convention_invariant_gate.py

P85 — Prediction Convention Invariant Gate
Test suite: ~100 tests across 12 test classes.

Governance: paper_only=True, diagnostic_only=True, production_ready=False
These tests lock the semantics of the P84G-corrected FIP convention and guard
against future silent side inversion or label fossilization.
"""
from __future__ import annotations

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"

SUMMARY_PATH = DERIVED / "p85_prediction_convention_invariant_gate_summary.json"
REPORT_PATH  = REPORT_DIR / "p85_prediction_convention_invariant_gate_20260527.md"
SCRIPT_PATH  = ROOT / "scripts" / "_p85_prediction_convention_invariant_gate.py"
P84E_ROWS    = DERIVED / "p84e_2026_outcome_attached_prediction_rows.jsonl"


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P85 summary not found: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P85 report not found: {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    assert P84E_ROWS.exists(), f"P84E JSONL not found: {P84E_ROWS}"
    return [json.loads(l) for l in P84E_ROWS.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture(scope="module")
def outcome_rows(rows) -> list[dict]:
    return [r for r in rows if r.get("outcome_available")]


# ---------------------------------------------------------------------------
# 1. Infrastructure
# ---------------------------------------------------------------------------

class TestInfrastructure:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists()

    def test_summary_exists(self):
        assert SUMMARY_PATH.exists()

    def test_report_exists(self):
        assert REPORT_PATH.exists()

    def test_summary_phase(self, summary):
        assert summary["phase"] == "diagnostic-only"

    def test_summary_date(self, summary):
        assert summary["date"] == "2026-05-27"

    def test_allowed_classifications_count(self, summary):
        assert len(summary["allowed_classifications"]) == 5

    def test_allowed_classifications_contains_ready(self, summary):
        assert "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY" in summary["allowed_classifications"]

    def test_allowed_classifications_contains_artifact_mismatch(self, summary):
        assert "P85_INVARIANT_GATE_FAILED_ARTIFACT_MISMATCH" in summary["allowed_classifications"]

    def test_allowed_classifications_contains_mapping_regression(self, summary):
        assert "P85_INVARIANT_GATE_FAILED_MAPPING_REGRESSION" in summary["allowed_classifications"]


# ---------------------------------------------------------------------------
# 2. Step 1 — Artifact lock
# ---------------------------------------------------------------------------

class TestStep1ArtifactLock:
    def test_step1_status_passed(self, summary):
        assert summary["step1_artifact_lock"]["status"] == "PASSED"

    def test_step1_p83e_exists(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p83e_summary_exists"] is True

    def test_step1_p84e_summary_exists(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84e_summary_exists"] is True

    def test_step1_p84e_rows_exists(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84e_rows_exists"] is True

    def test_step1_p84g_exists(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84g_summary_exists"] is True

    def test_step1_p84h_exists(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84h_summary_exists"] is True

    def test_step1_p83e_class_locked(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p83e_class_locked"] is True

    def test_step1_p84g_class_locked(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84g_class_locked"] is True

    def test_step1_p84h_class_locked(self, summary):
        assert summary["step1_artifact_lock"]["checks"]["p84h_class_locked"] is True

    def test_step1_p84h_classification_value(self, summary):
        cls = summary["step1_artifact_lock"]["checks"]["p84h_classification"]
        assert cls == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_step1_p84g_classification_value(self, summary):
        cls = summary["step1_artifact_lock"]["checks"]["p84g_classification"]
        assert cls == "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"

    def test_step1_p83e_classification_value(self, summary):
        cls = summary["step1_artifact_lock"]["checks"]["p83e_classification"]
        assert cls == "P83E_CANONICAL_ROWS_READY"


# ---------------------------------------------------------------------------
# 3. Step 2 — FIP positive delta invariant
# ---------------------------------------------------------------------------

class TestStep2FipPositiveInvariant:
    def test_step2_status_passed(self, summary):
        assert summary["step2_fip_positive_invariant"]["status"] == "PASSED"

    def test_step2_description_mentions_away(self, summary):
        desc = summary["step2_fip_positive_invariant"]["description"]
        assert "away" in desc.lower()

    def test_step2_n_positive_delta_rows(self, summary):
        assert summary["step2_fip_positive_invariant"]["n_positive_delta_rows"] == 396

    def test_step2_zero_violations(self, summary):
        assert summary["step2_fip_positive_invariant"]["n_violations"] == 0

    def test_step2_violations_list_empty(self, summary):
        assert summary["step2_fip_positive_invariant"]["violations"] == []

    def test_step2_fip_semantics_live(self, outcome_rows):
        """Live check: all positive-delta rows predict 'away'."""
        pos_rows = [r for r in outcome_rows if r["sp_fip_delta"] > 0]
        violations = [r for r in pos_rows if r["predicted_side"] != "away"]
        assert len(violations) == 0, f"FIP positive delta violations: {violations[:3]}"

    def test_step2_pos_rows_coverage_nonzero(self, outcome_rows):
        pos_rows = [r for r in outcome_rows if r["sp_fip_delta"] > 0]
        assert len(pos_rows) > 0, "No positive-delta rows found — gate is vacuous"


# ---------------------------------------------------------------------------
# 4. Step 3 — FIP negative delta invariant
# ---------------------------------------------------------------------------

class TestStep3FipNegativeInvariant:
    def test_step3_status_passed(self, summary):
        assert summary["step3_fip_negative_invariant"]["status"] == "PASSED"

    def test_step3_description_mentions_home(self, summary):
        desc = summary["step3_fip_negative_invariant"]["description"]
        assert "home" in desc.lower()

    def test_step3_n_negative_delta_rows(self, summary):
        assert summary["step3_fip_negative_invariant"]["n_negative_delta_rows"] == 412

    def test_step3_zero_violations(self, summary):
        assert summary["step3_fip_negative_invariant"]["n_violations"] == 0

    def test_step3_violations_list_empty(self, summary):
        assert summary["step3_fip_negative_invariant"]["violations"] == []

    def test_step3_fip_semantics_live(self, outcome_rows):
        """Live check: all negative-delta rows predict 'home'."""
        neg_rows = [r for r in outcome_rows if r["sp_fip_delta"] < 0]
        violations = [r for r in neg_rows if r["predicted_side"] != "home"]
        assert len(violations) == 0, f"FIP negative delta violations: {violations[:3]}"

    def test_step3_neg_rows_coverage_nonzero(self, outcome_rows):
        neg_rows = [r for r in outcome_rows if r["sp_fip_delta"] < 0]
        assert len(neg_rows) > 0, "No negative-delta rows found — gate is vacuous"

    def test_step3_pos_plus_neg_equals_total(self, summary):
        pos = summary["step2_fip_positive_invariant"]["n_positive_delta_rows"]
        neg = summary["step3_fip_negative_invariant"]["n_negative_delta_rows"]
        zero = summary["step4_zero_delta_policy"]["n_zero_delta_rows"]
        outcome_n = summary["step7_is_correct_consistency"]["n_outcome_rows"]
        assert pos + neg + zero == outcome_n


# ---------------------------------------------------------------------------
# 5. Step 4 — Zero-delta policy
# ---------------------------------------------------------------------------

class TestStep4ZeroDeltaPolicy:
    def test_step4_status_passed(self, summary):
        assert summary["step4_zero_delta_policy"]["status"] == "PASSED"

    def test_step4_zero_rows_none_in_dataset(self, summary):
        assert summary["step4_zero_delta_policy"]["n_zero_delta_rows"] == 0

    def test_step4_min_abs_delta_positive(self, summary):
        assert summary["step4_zero_delta_policy"]["min_abs_delta_in_dataset"] > 0

    def test_step4_min_abs_delta_value(self, summary):
        assert abs(summary["step4_zero_delta_policy"]["min_abs_delta_in_dataset"] - 0.0077) < 0.001

    def test_step4_policy_rule_present(self, summary):
        policy = summary["step4_zero_delta_policy"]["zero_delta_policy"]
        assert "rule" in policy

    def test_step4_policy_prob_gt_half(self, summary):
        policy = summary["step4_zero_delta_policy"]["zero_delta_policy"]
        assert "home" in policy.get("prob_gt_half", "").lower()

    def test_step4_policy_prob_lt_half(self, summary):
        policy = summary["step4_zero_delta_policy"]["zero_delta_policy"]
        assert "away" in policy.get("prob_lt_half", "").lower()

    def test_step4_policy_prob_eq_half_abstain(self, summary):
        policy = summary["step4_zero_delta_policy"]["zero_delta_policy"]
        assert "abstain" in policy.get("prob_eq_half", "").lower()

    def test_step4_near_zero_threshold(self, summary):
        assert summary["step4_zero_delta_policy"]["near_zero_threshold"] == 0.01

    def test_step4_zero_violations_empty(self, summary):
        assert summary["step4_zero_delta_policy"]["zero_violations"] == []


# ---------------------------------------------------------------------------
# 6. Step 5 — Probability semantics
# ---------------------------------------------------------------------------

class TestStep5ProbabilitySemantics:
    def test_step5_status_passed(self, summary):
        assert summary["step5_probability_semantics"]["status"] == "PASSED"

    def test_step5_n_rows(self, summary):
        assert summary["step5_probability_semantics"]["n_rows"] == 808

    def test_step5_mean_probability_near_half(self, summary):
        mean_p = summary["step5_probability_semantics"]["mean_model_probability"]
        # Should be near 0.5 — not trivially high (which would signal wrong interpretation)
        assert 0.45 < mean_p < 0.55

    def test_step5_mean_probability_exact(self, summary):
        assert abs(summary["step5_probability_semantics"]["mean_model_probability"] - 0.503383) < 1e-4

    def test_step5_has_below_half_rows(self, summary):
        assert summary["step5_probability_semantics"]["has_below_half_rows"] is True

    def test_step5_n_prob_below_half(self, summary):
        assert summary["step5_probability_semantics"]["n_prob_below_half"] == 396

    def test_step5_n_prob_above_half(self, summary):
        assert summary["step5_probability_semantics"]["n_prob_above_half"] == 412

    def test_step5_trivially_high_false(self, summary):
        assert summary["step5_probability_semantics"]["trivially_high_flag"] is False

    def test_step5_zero_violations(self, summary):
        assert summary["step5_probability_semantics"]["n_prob_violations"] == 0

    def test_step5_prob_above_below_sum(self, summary):
        above = summary["step5_probability_semantics"]["n_prob_above_half"]
        below = summary["step5_probability_semantics"]["n_prob_below_half"]
        n = summary["step5_probability_semantics"]["n_rows"]
        # above + below <= n (some might be exactly 0.5, though unlikely)
        assert above + below <= n

    def test_step5_live_prob_semantics(self, outcome_rows):
        """Live: prob > 0.5 → home, prob < 0.5 → away."""
        violations = []
        for r in outcome_rows:
            p = r["model_probability"]
            s = r["predicted_side"]
            if p > 0.5 and s != "home":
                violations.append(r["game_id"])
            elif p < 0.5 and s != "away":
                violations.append(r["game_id"])
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# 7. Step 6 — actual_winner consistency
# ---------------------------------------------------------------------------

class TestStep6ActualWinnerConsistency:
    def test_step6_status_passed(self, summary):
        assert summary["step6_actual_winner_consistency"]["status"] == "PASSED"

    def test_step6_n_outcome_rows(self, summary):
        assert summary["step6_actual_winner_consistency"]["n_outcome_rows"] == 808

    def test_step6_zero_violations(self, summary):
        assert summary["step6_actual_winner_consistency"]["n_violations"] == 0

    def test_step6_no_tied_scores(self, summary):
        # Baseball ties are rare; document the count
        tied = summary["step6_actual_winner_consistency"]["n_tied_scores"]
        assert tied == 0  # None in current dataset

    def test_step6_live_score_derivation(self, outcome_rows):
        """Live: actual_winner must match score comparison."""
        violations = []
        for r in outcome_rows:
            h, a, w = r["result_home_score"], r["result_away_score"], r["actual_winner"]
            if h > a and w != "home":
                violations.append(r["game_id"])
            elif a > h and w != "away":
                violations.append(r["game_id"])
        assert len(violations) == 0

    def test_step6_winner_values_valid(self, outcome_rows):
        """actual_winner values must all be 'home' or 'away'."""
        invalid = [r["game_id"] for r in outcome_rows if r["actual_winner"] not in ("home", "away")]
        assert len(invalid) == 0


# ---------------------------------------------------------------------------
# 8. Step 7 — is_correct consistency
# ---------------------------------------------------------------------------

class TestStep7IsCorrectConsistency:
    def test_step7_status_passed(self, summary):
        assert summary["step7_is_correct_consistency"]["status"] == "PASSED"

    def test_step7_n_outcome_rows(self, summary):
        assert summary["step7_is_correct_consistency"]["n_outcome_rows"] == 808

    def test_step7_n_correct(self, summary):
        assert summary["step7_is_correct_consistency"]["n_correct"] == 460

    def test_step7_computed_hit_rate(self, summary):
        assert abs(summary["step7_is_correct_consistency"]["computed_hit_rate"] - 0.569307) < 1e-4

    def test_step7_hit_rate_above_half(self, summary):
        assert summary["step7_is_correct_consistency"]["computed_hit_rate"] > 0.5

    def test_step7_zero_violations(self, summary):
        assert summary["step7_is_correct_consistency"]["n_violations"] == 0

    def test_step7_violations_empty(self, summary):
        assert summary["step7_is_correct_consistency"]["violations"] == []

    def test_step7_live_is_correct(self, outcome_rows):
        """Live: is_correct == (predicted_side == actual_winner)."""
        violations = [r["game_id"] for r in outcome_rows
                      if (r["predicted_side"] == r["actual_winner"]) != r["is_correct"]]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# 9. Step 8 — AUC / hit_rate semantic guard
# ---------------------------------------------------------------------------

class TestStep8AucHitRateGuard:
    def test_step8_status_passed(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["status"] == "PASSED"

    def test_step8_recomputed_hit_rate(self, summary):
        assert abs(summary["step8_auc_hit_rate_guard"]["recomputed_hit_rate"] - 0.569307) < 1e-4

    def test_step8_recomputed_auc(self, summary):
        assert abs(summary["step8_auc_hit_rate_guard"]["recomputed_auc"] - 0.594315) < 1e-4

    def test_step8_hit_rate_matches_p84h(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["hit_rate_matches_p84h"] is True

    def test_step8_auc_matches_p84h(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["auc_matches_p84h"] is True

    def test_step8_semantically_consistent(self, summary):
        # AUC > 0.5 and hit_rate > 0.5 — not contradictory
        assert summary["step8_auc_hit_rate_guard"]["semantically_consistent"] is True

    def test_step8_auc_not_vacuous(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["auc_vacuous"] is False

    def test_step8_auc_above_half(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["recomputed_auc"] > 0.5

    def test_step8_auc_below_vacuous_threshold(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["recomputed_auc"] < 0.95

    def test_step8_platt_refit_forbidden(self, summary):
        assert summary["step8_auc_hit_rate_guard"]["platt_isotonic_refit"] == "FORBIDDEN_BY_GOVERNANCE"

    def test_step8_hit_rate_delta_near_zero(self, summary):
        delta = summary["step8_auc_hit_rate_guard"]["hit_rate_delta"]
        assert delta is not None
        assert delta < 1e-4

    def test_step8_auc_delta_near_zero(self, summary):
        delta = summary["step8_auc_hit_rate_guard"]["auc_delta"]
        assert delta is not None
        assert delta < 1e-4

    def test_step8_description_mentions_home_won(self, summary):
        desc = summary["step8_auc_hit_rate_guard"]["description"]
        assert "home_won" in desc or "home won" in desc.lower()


# ---------------------------------------------------------------------------
# 10. Step 9 — Governance scan
# ---------------------------------------------------------------------------

class TestStep9GovernanceScan:
    def test_step9_status_passed(self, summary):
        assert summary["step9_governance_scan"]["status"] == "PASSED"

    def test_step9_n_rows_scanned(self, summary):
        # Scans all rows (including non-outcome)
        assert summary["step9_governance_scan"]["n_rows_scanned"] == 828

    def test_step9_total_row_violations_zero(self, summary):
        assert summary["step9_governance_scan"]["total_row_violations"] == 0

    def test_step9_paper_only_violations_zero(self, summary):
        assert summary["step9_governance_scan"]["row_level_violation_counts"]["paper_only_false"] == 0

    def test_step9_diagnostic_only_violations_zero(self, summary):
        assert summary["step9_governance_scan"]["row_level_violation_counts"]["diagnostic_only_false"] == 0

    def test_step9_production_ready_violations_zero(self, summary):
        assert summary["step9_governance_scan"]["row_level_violation_counts"]["production_ready_true"] == 0

    def test_step9_odds_used_violations_zero(self, summary):
        assert summary["step9_governance_scan"]["row_level_violation_counts"]["odds_used_true"] == 0

    def test_step9_gov_paper_only_true(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["paper_only"] is True

    def test_step9_gov_diagnostic_only_true(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["diagnostic_only"] is True

    def test_step9_gov_production_ready_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["production_ready"] is False

    def test_step9_gov_odds_used_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["odds_used"] is False

    def test_step9_gov_ev_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["ev_computed"] is False

    def test_step9_gov_clv_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["clv_computed"] is False

    def test_step9_gov_kelly_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["kelly_computed"] is False

    def test_step9_gov_live_api_zero(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["live_api_calls"] == 0

    def test_step9_gov_paid_api_false(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["paid_api_called"] is False

    def test_step9_gov_canonical_rows_not_modified(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["canonical_rows_modified"] is False

    def test_step9_gov_outcome_rows_not_modified(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["outcome_rows_modified"] is False

    def test_step9_gov_p83e_mapping_not_modified(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["p83e_mapping_modified"] is False

    def test_step9_gov_champion_not_replaced(self, summary):
        assert summary["step9_governance_scan"]["p85_governance"]["champion_replaced"] is False


# ---------------------------------------------------------------------------
# 11. Step 10 — Final classification
# ---------------------------------------------------------------------------

class TestStep10FinalClassification:
    def test_step10_classification_is_one_of_five(self, summary):
        assert summary["p85_classification"] in summary["allowed_classifications"]

    def test_step10_classification_matches_step10(self, summary):
        assert summary["p85_classification"] == summary["step10_final_classification"]["classification"]

    def test_step10_classification_value(self, summary):
        assert summary["p85_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"

    def test_step10_n_steps_checked(self, summary):
        assert summary["step10_final_classification"]["n_steps_checked"] == 9

    def test_step10_all_steps_passed(self, summary):
        assert summary["step10_final_classification"]["n_steps_passed"] == 9

    def test_step10_zero_steps_failed(self, summary):
        assert summary["step10_final_classification"]["n_steps_failed"] == 0

    def test_step10_rationale_nonempty(self, summary):
        rationale = summary["step10_final_classification"]["rationale"]
        assert isinstance(rationale, str) and len(rationale) > 10

    def test_step10_rationale_mentions_fip(self, summary):
        rationale = summary["step10_final_classification"]["rationale"].lower()
        assert "fip" in rationale

    def test_step10_rationale_mentions_p84g(self, summary):
        rationale = summary["step10_final_classification"]["rationale"]
        assert "P84G" in rationale


# ---------------------------------------------------------------------------
# 12. Report content checks
# ---------------------------------------------------------------------------

class TestReportContent:
    def test_report_contains_classification(self, report_text):
        assert "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY" in report_text

    def test_report_contains_convention_table(self, report_text):
        assert "sp_fip_delta" in report_text

    def test_report_mentions_fip_lower_is_better(self, report_text):
        assert "lower" in report_text.lower() and "fip" in report_text.lower()

    def test_report_mentions_delta_positive_away(self, report_text):
        assert "away" in report_text.lower()

    def test_report_mentions_delta_negative_home(self, report_text):
        assert "home" in report_text.lower()

    def test_report_platt_forbidden(self, report_text):
        assert "FORBIDDEN" in report_text

    def test_report_no_production_claim(self, report_text):
        # Report must NOT claim production betting is allowed.
        # "No production betting recommendation" (scope denial) is acceptable.
        # "production_ready = True" would be a violation.
        assert "production_ready = True" not in report_text
        assert "production_ready`: `True" not in report_text

    def test_report_no_ev_claim(self, report_text):
        lower = report_text.lower()
        assert "ev_computed" not in lower or "false" in lower

    def test_report_mentions_zero_delta_policy(self, report_text):
        lower = report_text.lower()
        assert "zero" in lower and "delta" in lower

    def test_report_mentions_coverage_limited(self, report_text):
        # Coverage constraint from P84H should be referenced
        lower = report_text.lower()
        assert "coverage" in lower


# ---------------------------------------------------------------------------
# 13. Convention documentation integrity
# ---------------------------------------------------------------------------

class TestConventionDocumentation:
    """
    These tests lock the documented semantics so that future contributors
    cannot accidentally change the convention interpretation without failing
    a named test.
    """

    def test_fip_formula_documented(self, summary):
        """sp_fip_delta = home_sp_fip - away_sp_fip must be in script docstring."""
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "sp_fip_delta = home_sp_fip - away_sp_fip" in script_text

    def test_fip_lower_is_better_documented(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "lower" in script_text.lower()

    def test_positive_delta_means_home_worse(self, summary):
        """Gate summary must encode that positive delta → home pitcher is worse."""
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        # Check for the convention comment
        assert "home pitcher" in script_text.lower() or "home_sp_fip" in script_text

    def test_positive_delta_maps_to_away_in_script(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "'away'" in script_text

    def test_negative_delta_maps_to_home_in_script(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "'home'" in script_text

    def test_model_probability_semantics_documented(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "P(home wins)" in script_text

    def test_is_correct_formula_documented(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "predicted_side == actual_winner" in script_text

    def test_actual_winner_from_scores_documented(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "result_home_score" in script_text

    def test_abstain_on_zero_prob_documented(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "abstain" in script_text.lower()

    def test_platt_forbidden_in_script(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "FORBIDDEN" in script_text

    def test_no_kelly_in_script(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "kelly" not in script_text.lower() or "false" in script_text.lower()

    def test_no_ev_computation_in_script(self, summary):
        script_text = SCRIPT_PATH.read_text(encoding="utf-8")
        # ev_computed key exists in governance dict as False; no EV formula
        assert "expected_value" not in script_text.lower()
        assert "ev_formula" not in script_text.lower()

    def test_coverage_limited_not_upgraded_to_full_claim(self, summary):
        """Gate must NOT claim production-ready or full-season validity."""
        assert summary["step9_governance_scan"]["p85_governance"]["production_ready"] is False

    def test_hit_rate_not_packaged_as_betting_edge(self, summary):
        """hit_rate 56.9% must not appear alongside production_ready=True."""
        hit_rate = summary["step7_is_correct_consistency"]["computed_hit_rate"]
        prod_ready = summary["step9_governance_scan"]["p85_governance"]["production_ready"]
        assert hit_rate > 0.56 and prod_ready is False

    def test_p84g_not_regressed(self, summary):
        """P84G fix must still be reflected: all pos-delta → away."""
        assert summary["step2_fip_positive_invariant"]["n_violations"] == 0
        assert summary["step3_fip_negative_invariant"]["n_violations"] == 0
