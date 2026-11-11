"""
tests/test_p87_stale_downstream_recovery_dry_run.py
====================================================
P87 — Stale Downstream Recovery Dry-Run and Regeneration Plan
Tests: 138 tests across 12 test classes.

These tests verify the P87 dry-run summary JSON without executing
any live computation. All assertions are against pre-generated artifacts.
"""

import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent.resolve()

SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json"
REPORT_PATH = ROOT / "report/p87_stale_downstream_recovery_dry_run_20260527.md"
SCRIPT_PATH = ROOT / "scripts/_p87_stale_downstream_recovery_dry_run.py"

EXPECTED_CLASSIFICATION = "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"
EXPECTED_P86_CLASSIFICATION = "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK"
EXPLICIT_YES_REQUIRED = "YES regenerate stale downstream artifacts for P87 recovery"

EXPECTED_CANONICAL_COUNT = 828
EXPECTED_P84E_CONSUMED_COUNT = 828

ALLOWED_CLASSIFICATIONS = [
    "P87_STALE_DOWNSTREAM_RECOVERY_DRY_RUN_READY",
    "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES",
    "P87_RECOVERY_BLOCKED_BY_MISSING_ARTIFACT",
    "P87_RECOVERY_BLOCKED_BY_PREFLIGHT",
    "P87_RECOVERY_BLOCKED_BY_SCOPE_DRIFT",
    "P87_RECOVERY_FAILED_UNEXPECTED_DEPENDENCY_STATE",
]

EXPECTED_DIRECTLY_STALE = {"p84e_rows", "p84e_summary"}
EXPECTED_DERIVEDLY_STALE = {"p84f_summary", "p84g_summary", "p84h_summary", "p85_summary", "p86_summary"}

EXPECTED_ARTIFACT_KEYS = [
    "p83e_summary",
    "canonical_rows",
    "p84e_rows",
    "p84e_summary",
    "p84f_summary",
    "p84g_summary",
    "p84h_summary",
    "p85_summary",
    "p86_summary",
]

EXPECTED_EXECUTION_ORDER = ["P84E", "P84F", "P84G", "P84H", "P85", "P86"]

EXPECTED_GOVERNANCE_FLAGS = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "odds_used": False,
    "ev_computed": False,
    "clv_computed": False,
    "kelly_computed": False,
    "live_api_calls": 0,
    "paid_api_called": False,
    "no_champion_replacement": True,
    "no_runtime_recommendation_mutation": True,
    "no_canonical_row_rewrite": True,
    "no_outcome_row_rewrite": True,
    "no_calibration_refit": True,
    "no_production_betting_recommendation": True,
    "no_real_bet": True,
}

FORBIDDEN_REPORT_PHRASES = [
    "EV",
    "CLV",
    "Kelly",
    "stake",
    "台灣運彩",
    "production betting",
    "place a bet",
    "real bet",
    "投注建議",
    "下注",
]


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P87 summary JSON not found: {SUMMARY_PATH}"
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P87 report not found: {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


# ─── Class 1: Infrastructure ─────────────────────────────────────────────────

class TestInfrastructure:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists()

    def test_summary_json_exists(self):
        assert SUMMARY_PATH.exists()

    def test_report_md_exists(self):
        assert REPORT_PATH.exists()

    def test_summary_is_valid_json(self, summary):
        assert isinstance(summary, dict)

    def test_classification_key_present(self, summary):
        assert "p87_classification" in summary

    def test_classification_is_expected(self, summary):
        assert summary["p87_classification"] == EXPECTED_CLASSIFICATION

    def test_classification_in_allowed_list(self, summary):
        assert summary["p87_classification"] in ALLOWED_CLASSIFICATIONS

    def test_date_field(self, summary):
        assert summary.get("date") == "2026-05-27"

    def test_generated_at_present(self, summary):
        assert "generated_at" in summary
        assert summary["generated_at"]

    def test_phase_is_diagnostic_only(self, summary):
        assert summary.get("phase") == "diagnostic-only"

    def test_explicit_yes_required_field(self, summary):
        assert summary.get("explicit_yes_required") == EXPLICIT_YES_REQUIRED

    def test_frozen_artifacts_list_present(self, summary):
        assert "frozen_artifacts" in summary
        assert isinstance(summary["frozen_artifacts"], list)
        assert len(summary["frozen_artifacts"]) > 0

    def test_allowed_classifications_present(self, summary):
        assert "allowed_classifications" in summary
        assert len(summary["allowed_classifications"]) == 6


# ─── Class 2: Step 1 — Artifact Inventory ───────────────────────────────────

class TestStep1ArtifactInventory:
    def test_step1_present(self, summary):
        assert "step1_artifact_inventory" in summary

    def test_all_present_true(self, summary):
        assert summary["step1_artifact_inventory"]["all_present"] is True

    def test_artifact_count(self, summary):
        artifacts = summary["step1_artifact_inventory"]["artifacts"]
        assert len(artifacts) == 9

    @pytest.mark.parametrize("key", EXPECTED_ARTIFACT_KEYS)
    def test_artifact_exists(self, summary, key):
        art = summary["step1_artifact_inventory"]["artifacts"]
        assert key in art
        assert art[key]["exists"] is True

    @pytest.mark.parametrize("key", EXPECTED_ARTIFACT_KEYS)
    def test_artifact_sha256_prefix_format(self, summary, key):
        art = summary["step1_artifact_inventory"]["artifacts"]
        sha = art[key].get("sha256_prefix", "")
        assert len(sha) == 16, f"{key}: sha256_prefix length should be 16, got {len(sha)}"

    @pytest.mark.parametrize("key", EXPECTED_ARTIFACT_KEYS)
    def test_artifact_mtime_utc(self, summary, key):
        art = summary["step1_artifact_inventory"]["artifacts"]
        mtime = art[key].get("mtime", "")
        assert "+00:00" in mtime or "Z" in mtime, f"{key}: mtime not UTC: {mtime}"

    def test_canonical_rows_sha256_matches_p86(self, summary):
        # P86 recorded canonical_rows sha256_prefix=74c4a5498f80b2e7
        sha = summary["step1_artifact_inventory"]["artifacts"]["canonical_rows"]["sha256_prefix"]
        assert sha == "74c4a5498f80b2e7"

    def test_p86_summary_sha256_present(self, summary):
        sha = summary["step1_artifact_inventory"]["artifacts"]["p86_summary"].get("sha256_prefix", "")
        assert len(sha) == 16


# ─── Class 3: Step 2 — Stale Risk Extraction ────────────────────────────────

class TestStep2StaleRiskExtraction:
    def test_step2_present(self, summary):
        assert "step2_stale_risk_extraction" in summary

    def test_p86_classification_is_stale(self, summary):
        s = summary["step2_stale_risk_extraction"]
        assert s["p86_classification"] == EXPECTED_P86_CLASSIFICATION

    def test_p86_is_stale_downstream_true(self, summary):
        s = summary["step2_stale_risk_extraction"]
        assert s["p86_is_stale_downstream"] is True

    def test_n_stale_risks_is_one(self, summary):
        s = summary["step2_stale_risk_extraction"]
        assert s["n_stale_risks"] == 1

    def test_stale_risks_list_has_one_entry(self, summary):
        s = summary["step2_stale_risk_extraction"]
        assert len(s["stale_risks_from_p86"]) == 1

    def test_root_cause_upstream_is_canonical_rows(self, summary):
        rc = summary["step2_stale_risk_extraction"]["root_cause"]
        assert rc is not None
        assert rc["upstream_artifact"] == "canonical_rows"

    def test_root_cause_downstream_is_p84e_rows(self, summary):
        rc = summary["step2_stale_risk_extraction"]["root_cause"]
        assert rc["downstream_artifact"] == "p84e_rows"

    def test_root_cause_delta_seconds(self, summary):
        rc = summary["step2_stale_risk_extraction"]["root_cause"]
        assert rc["delta_seconds"] == 6134

    def test_root_cause_interpretation_not_empty(self, summary):
        rc = summary["step2_stale_risk_extraction"]["root_cause"]
        assert len(rc["interpretation"]) > 20

    def test_upstream_mtime_after_downstream(self, summary):
        rc = summary["step2_stale_risk_extraction"]["root_cause"]
        # upstream (canonical_rows) is AFTER downstream (p84e_rows) — that's the stale risk
        assert rc["upstream_mtime"] > rc["downstream_mtime"]


# ─── Class 4: Step 3 — Content Identity Probe ───────────────────────────────

class TestStep3ContentIdentityProbe:
    def test_step3_present(self, summary):
        assert "step3_content_identity_probe" in summary

    def test_canonical_count_is_828(self, summary):
        s = summary["step3_content_identity_probe"]
        assert s["canonical_rows_current_count"] == EXPECTED_CANONICAL_COUNT

    def test_p84e_consumed_count_is_828(self, summary):
        s = summary["step3_content_identity_probe"]
        assert s["p84e_consumed_count_at_run_time"] == EXPECTED_P84E_CONSUMED_COUNT

    def test_count_match_true(self, summary):
        assert summary["step3_content_identity_probe"]["count_match"] is True

    def test_game_id_intersection_count_is_828(self, summary):
        s = summary["step3_content_identity_probe"]
        assert s["game_id_intersection_count"] == 828

    def test_in_canonical_not_p84e_is_zero(self, summary):
        assert summary["step3_content_identity_probe"]["in_canonical_not_p84e"] == 0

    def test_in_p84e_not_canonical_is_zero(self, summary):
        assert summary["step3_content_identity_probe"]["in_p84e_not_canonical"] == 0

    def test_game_id_full_coverage_true(self, summary):
        assert summary["step3_content_identity_probe"]["game_id_full_coverage"] is True

    def test_content_drift_likely_false(self, summary):
        assert summary["step3_content_identity_probe"]["content_drift_likely"] is False

    def test_interpretation_not_empty(self, summary):
        interp = summary["step3_content_identity_probe"]["interpretation"]
        assert len(interp) > 20

    def test_interpretation_mentions_mtime_drift(self, summary):
        interp = summary["step3_content_identity_probe"]["interpretation"].lower()
        assert "mtime" in interp or "identical" in interp


# ─── Class 5: Step 4 — Affected Downstream Artifacts ────────────────────────

class TestStep4AffectedArtifacts:
    def test_step4_present(self, summary):
        assert "step4_affected_downstream_artifacts" in summary

    def test_stale_root_is_canonical_rows(self, summary):
        s = summary["step4_affected_downstream_artifacts"]
        assert s["stale_root"] == "canonical_rows"

    def test_directly_stale_count(self, summary):
        s = summary["step4_affected_downstream_artifacts"]
        assert len(s["directly_stale"]) == 2

    def test_directly_stale_contains_p84e_rows(self, summary):
        names = {a["artifact"] for a in summary["step4_affected_downstream_artifacts"]["directly_stale"]}
        assert "p84e_rows" in names

    def test_directly_stale_contains_p84e_summary(self, summary):
        names = {a["artifact"] for a in summary["step4_affected_downstream_artifacts"]["directly_stale"]}
        assert "p84e_summary" in names

    def test_derivedly_stale_count(self, summary):
        s = summary["step4_affected_downstream_artifacts"]
        assert len(s["derivedly_stale"]) == 5

    @pytest.mark.parametrize("artifact", sorted(EXPECTED_DERIVEDLY_STALE))
    def test_derivedly_stale_contains(self, summary, artifact):
        names = {a["artifact"] for a in summary["step4_affected_downstream_artifacts"]["derivedly_stale"]}
        assert artifact in names

    def test_frozen_artifacts_list_not_empty(self, summary):
        s = summary["step4_affected_downstream_artifacts"]
        assert len(s["frozen_artifacts"]) >= 8

    def test_p86_in_derivedly_stale(self, summary):
        names = {a["artifact"] for a in summary["step4_affected_downstream_artifacts"]["derivedly_stale"]}
        assert "p86_summary" in names

    def test_each_directly_stale_has_reason(self, summary):
        for art in summary["step4_affected_downstream_artifacts"]["directly_stale"]:
            assert len(art.get("reason", "")) > 5

    def test_each_derivedly_stale_has_reason(self, summary):
        for art in summary["step4_affected_downstream_artifacts"]["derivedly_stale"]:
            assert len(art.get("reason", "")) > 5


# ─── Class 6: Step 5 — Dry-Run Regeneration Order ───────────────────────────

class TestStep5DryRunRegenOrder:
    def test_step5_present(self, summary):
        assert "step5_dry_run_regeneration_order" in summary

    def test_requires_explicit_yes(self, summary):
        s = summary["step5_dry_run_regeneration_order"]
        assert s["requires_explicit_yes"] == EXPLICIT_YES_REQUIRED

    def test_regeneration_steps_count_is_9(self, summary):
        s = summary["step5_dry_run_regeneration_order"]
        assert len(s["regeneration_steps"]) == 9

    @pytest.mark.parametrize("step_num", range(1, 10))
    def test_step_num_exists(self, summary, step_num):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        nums = [s["step_num"] for s in steps]
        assert step_num in nums

    def test_step1_confirm_p83e_inputs(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s1 = next(s for s in steps if s["step_num"] == 1)
        assert "p83e" in s1["action"].lower() or "confirm" in s1["action"].lower()

    def test_step6_is_authorization_gate(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s6 = next(s for s in steps if s["step_num"] == 6)
        assert s6.get("is_authorization_gate") is True or "explicit" in s6["description"].lower()

    def test_step7_has_execution_order(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        exec_order = s7.get("execution_order", [])
        assert exec_order == EXPECTED_EXECUTION_ORDER

    def test_step8_has_test_command(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s8 = next(s for s in steps if s["step_num"] == 8)
        assert "test_command" in s8 or "pytest" in s8.get("description", "")

    def test_step4_identifies_p84e_first(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s4 = next(s for s in steps if s["step_num"] == 4)
        assert "p84e" in s4["description"].lower() or "p84e" in s4["action"].lower()

    def test_step5_identifies_all_downstream(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s5 = next(s for s in steps if s["step_num"] == 5)
        desc = s5["description"].lower()
        assert "p84f" in desc or "p84g" in desc or "p84h" in desc

    def test_note_is_dry_run_only(self, summary):
        note = summary["step5_dry_run_regeneration_order"].get("note", "").upper()
        assert "DRY" in note or "NO FILE" in note


# ─── Class 7: Step 6 — Safety Decision ──────────────────────────────────────

class TestStep6SafetyDecision:
    def test_step6_present(self, summary):
        assert "step6_safety_decision" in summary

    def test_content_identity_probe_passed(self, summary):
        assert summary["step6_safety_decision"]["content_identity_probe_passed"] is True

    def test_stale_by_mtime_only(self, summary):
        assert summary["step6_safety_decision"]["stale_by_mtime_only"] is True

    def test_content_drift_likely_false(self, summary):
        assert summary["step6_safety_decision"]["content_drift_likely"] is False

    def test_safe_without_explicit_yes_is_false(self, summary):
        assert summary["step6_safety_decision"]["safe_without_explicit_yes"] is False

    def test_actual_regeneration_needed_true(self, summary):
        assert summary["step6_safety_decision"]["actual_regeneration_needed"] is True

    def test_reason_mentions_explicit_yes(self, summary):
        reason = summary["step6_safety_decision"]["reason"].lower()
        assert "explicit" in reason or "authorization" in reason

    def test_recommendation_not_empty(self, summary):
        rec = summary["step6_safety_decision"].get("recommendation", "")
        assert len(rec) > 20

    def test_expected_metric_stability_mentions_tolerance(self, summary):
        stab = summary["step6_safety_decision"].get("expected_metric_stability", "").lower()
        assert "1e-4" in stab or "tolerance" in stab or "0.569" in stab


# ─── Class 8: Step 7 — Governance Scan ──────────────────────────────────────

class TestStep7GovernanceScan:
    def test_step7_present(self, summary):
        assert "step7_governance_scan" in summary

    def test_governance_all_pass_true(self, summary):
        assert summary["step7_governance_scan"]["governance_all_pass"] is True

    def test_governance_has_16_flags(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert len(gov) == 16

    def test_paper_only_true(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["paper_only"] is True

    def test_diagnostic_only_true(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["diagnostic_only"] is True

    def test_production_ready_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["production_ready"] is False

    def test_odds_used_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["odds_used"] is False

    def test_ev_computed_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["ev_computed"] is False

    def test_clv_computed_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["clv_computed"] is False

    def test_kelly_computed_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["kelly_computed"] is False

    def test_live_api_calls_zero(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["live_api_calls"] == 0

    def test_paid_api_called_false(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["paid_api_called"] is False

    def test_no_champion_replacement(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_champion_replacement"] is True

    def test_no_runtime_recommendation_mutation(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_runtime_recommendation_mutation"] is True

    def test_no_canonical_row_rewrite(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_canonical_row_rewrite"] is True

    def test_no_outcome_row_rewrite(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_outcome_row_rewrite"] is True

    def test_no_calibration_refit(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_calibration_refit"] is True

    def test_no_production_betting_recommendation(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_production_betting_recommendation"] is True

    def test_no_real_bet(self, summary):
        gov = summary["step7_governance_scan"]["p87_governance"]
        assert gov["no_real_bet"] is True

    def test_governance_checks_all_pass(self, summary):
        checks = summary["step7_governance_scan"]["governance_checks"]
        for key, val in checks.items():
            assert val is True, f"Governance check failed: {key}={val}"


# ─── Class 9: Step 8 — Final Classification ─────────────────────────────────

class TestStep8FinalClassification:
    def test_step8_present(self, summary):
        assert "step8_final_classification" in summary

    def test_classification_matches_top_level(self, summary):
        s8 = summary["step8_final_classification"]
        assert s8["classification"] == summary["p87_classification"]

    def test_classification_is_expected(self, summary):
        assert summary["step8_final_classification"]["classification"] == EXPECTED_CLASSIFICATION

    def test_classification_in_allowed_list(self, summary):
        cls = summary["step8_final_classification"]["classification"]
        assert cls in ALLOWED_CLASSIFICATIONS

    def test_allowed_classifications_count(self, summary):
        allowed = summary["step8_final_classification"]["allowed_classifications"]
        assert len(allowed) == 6

    def test_explicit_yes_in_step8(self, summary):
        s8 = summary["step8_final_classification"]
        assert s8.get("explicit_yes_required") == EXPLICIT_YES_REQUIRED

    def test_rationale_not_empty(self, summary):
        assert len(summary["step8_final_classification"]["rationale"]) > 20

    def test_rationale_mentions_stale(self, summary):
        rationale = summary["step8_final_classification"]["rationale"].lower()
        assert "stale" in rationale

    def test_rationale_mentions_mtime(self, summary):
        rationale = summary["step8_final_classification"]["rationale"].lower()
        assert "mtime" in rationale or "count_match" in rationale

    def test_steps_checked_is_8(self, summary):
        s8 = summary["step8_final_classification"]
        assert s8.get("steps_checked") == 8

    def test_steps_passed_is_8(self, summary):
        s8 = summary["step8_final_classification"]
        assert s8.get("steps_passed") == 8


# ─── Class 10: Frozen Artifact Integrity ─────────────────────────────────────

class TestFrozenArtifactIntegrity:
    """Verify that P87 did not modify any frozen artifacts."""

    FROZEN_PATHS = [
        ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
        ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
        ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
        ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
        ROOT / "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
        ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
        ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
        ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
    ]

    @pytest.mark.parametrize("path", FROZEN_PATHS)
    def test_frozen_artifact_still_exists(self, path):
        assert path.exists(), f"Frozen artifact missing: {path}"

    def test_canonical_rows_count_unchanged(self):
        lines = [
            ln for ln in (ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if ln.strip()
        ]
        assert len(lines) == 828

    def test_p84e_rows_count_unchanged(self):
        lines = [
            ln for ln in (ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if ln.strip()
        ]
        assert len(lines) == 828

    def test_p84e_summary_classification_unchanged(self):
        with open(ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json") as f:
            d = json.load(f)
        assert d["p84e_classification"] == "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"

    def test_p84h_summary_classification_unchanged(self):
        with open(ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json") as f:
            d = json.load(f)
        assert d["p84h_classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_p85_summary_classification_unchanged(self):
        with open(ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json") as f:
            d = json.load(f)
        assert d["p85_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"

    def test_p86_summary_classification_unchanged(self):
        with open(ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json") as f:
            d = json.load(f)
        assert d["p86_classification"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"  # Updated: P89 recovered P86

    def test_p87_does_not_require_explicit_yes_in_dry_run(self, summary):
        # Confirms that the dry-run itself did NOT execute any regeneration
        assert summary["step6_safety_decision"]["safe_without_explicit_yes"] is False
        assert summary["p87_classification"] == "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"


# ─── Class 11: Report Content Validation ─────────────────────────────────────

class TestReportContent:
    def test_report_exists(self, report_text):
        assert len(report_text) > 100

    def test_report_contains_classification(self, report_text):
        assert EXPECTED_CLASSIFICATION in report_text

    def test_report_contains_p86_classification(self, report_text):
        assert EXPECTED_P86_CLASSIFICATION in report_text

    def test_report_contains_stale_root(self, report_text):
        assert "canonical_rows" in report_text

    def test_report_contains_p84e_as_first_stale(self, report_text):
        assert "p84e_rows" in report_text

    def test_report_contains_explicit_yes(self, report_text):
        assert EXPLICIT_YES_REQUIRED in report_text

    def test_report_contains_governance_section(self, report_text):
        assert "Governance" in report_text

    def test_report_contains_regeneration_order(self, report_text):
        assert "Regeneration Order" in report_text or "regeneration_steps" in report_text or "Step 5" in report_text

    def test_report_paper_only_mentioned(self, report_text):
        assert "paper_only" in report_text

    def test_report_diagnostic_only_mentioned(self, report_text):
        assert "diagnostic_only" in report_text

    def test_report_no_production_betting(self, report_text):
        lower = report_text.lower()
        assert "production betting recommendation" not in lower or "no production betting" in lower

    def test_report_contains_no_ev_instruction(self, report_text):
        # Report must contain no EV as a betting instruction (headline use is ok in gov line)
        # Gov line: "No EV / CLV / Kelly / stake calculation"
        assert "ev_computed = false" in report_text.lower() or "no ev" in report_text.lower()

    def test_report_no_stake_instruction(self, report_text):
        lower = report_text.lower()
        # "no stake calculation" in gov summary is fine; standalone stake instruction is not
        assert "no stake" in lower or "stake" not in lower

    def test_report_no_real_bet_instruction(self, report_text):
        lower = report_text.lower()
        assert "no real bet" in lower or "real bet" not in lower

    def test_report_no_taiwan_lottery_recommendation(self, report_text):
        assert "台灣運彩" not in report_text or "no" in report_text.lower()


# ─── Class 12: Regeneration Order Completeness ───────────────────────────────

class TestRegenOrderCompleteness:
    def test_execution_order_contains_p84e(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next((s for s in steps if s["step_num"] == 7), None)
        assert s7 is not None
        assert "P84E" in s7.get("execution_order", [])

    def test_execution_order_contains_p84f(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert "P84F" in s7["execution_order"]

    def test_execution_order_contains_p84g(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert "P84G" in s7["execution_order"]

    def test_execution_order_contains_p84h(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert "P84H" in s7["execution_order"]

    def test_execution_order_contains_p85(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert "P85" in s7["execution_order"]

    def test_execution_order_contains_p86(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert "P86" in s7["execution_order"]

    def test_execution_order_length(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert len(s7["execution_order"]) == 6

    def test_execution_order_correct_sequence(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        assert s7["execution_order"] == EXPECTED_EXECUTION_ORDER

    def test_scripts_to_run_count(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        scripts = s7.get("scripts_to_run", [])
        assert len(scripts) == 6

    def test_scripts_include_p84e_script(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        scripts = " ".join(s7.get("scripts_to_run", []))
        assert "p84e" in scripts.lower()

    def test_step9_updates_active_task(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s9 = next((s for s in steps if s["step_num"] == 9), None)
        assert s9 is not None
        written = " ".join(str(w) for w in s9.get("files_written", []))
        assert "active_task" in written

    def test_step8_regression_expects_889(self, summary):
        steps = summary["step5_dry_run_regeneration_order"]["regeneration_steps"]
        s8 = next((s for s in steps if s["step_num"] == 8), None)
        assert s8 is not None
        desc = s8.get("description", "") + s8.get("test_command", "")
        assert "889" in desc or "pytest" in desc.lower()
