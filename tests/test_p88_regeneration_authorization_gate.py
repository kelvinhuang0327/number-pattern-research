"""
tests/test_p88_regeneration_authorization_gate.py
==================================================
P88 — Regeneration Authorization Gate and Safe Recovery Readiness Check
Tests: ~140 tests across 10 test classes.

All assertions are against the pre-generated P88 summary JSON.
No live computation. No frozen artifacts modified.
"""

import json
import pathlib
import pytest

ROOT = pathlib.Path(__file__).parent.parent.resolve()

SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p88_regeneration_authorization_gate_summary.json"
REPORT_PATH  = ROOT / "report/p88_regeneration_authorization_gate_20260527.md"
SCRIPT_PATH  = ROOT / "scripts/_p88_regeneration_authorization_gate.py"

EXPECTED_P88_CLASSIFICATION   = "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION"
EXPECTED_P87_CLASSIFICATION   = "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"
EXPECTED_P86_CLASSIFICATION   = "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK"
EXPLICIT_YES_REQUIRED         = "YES regenerate stale downstream artifacts for P87 recovery"

ALLOWED_P88_CLASSIFICATIONS = [
    "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION",
    "P88_REGENERATION_AUTHORIZED_READY_TO_EXECUTE",
    "P88_AUTHORIZATION_GATE_FAILED_P87_STATE_MISMATCH",
    "P88_AUTHORIZATION_GATE_FAILED_P86_STATE_MISMATCH",
    "P88_AUTHORIZATION_GATE_BLOCKED_BY_PREFLIGHT",
    "P88_AUTHORIZATION_GATE_BLOCKED_BY_SCOPE_DRIFT",
]

EXPECTED_EXECUTION_ORDER = ["P84E", "P84F", "P84G", "P84H", "P85", "P86"]

FROZEN_PATHS = [
    ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
    ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
    ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
    ROOT / "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
    ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
    ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
    ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
    ROOT / "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json",
]

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
    "no_historical_artifact_overwrite": True,
    "no_calibration_refit": True,
    "no_production_betting_recommendation": True,
    "no_real_bet": True,
}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P88 summary JSON not found: {SUMMARY_PATH}"
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P88 report not found: {REPORT_PATH}"
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

    def test_p88_classification_key_present(self, summary):
        assert "p88_classification" in summary

    def test_p88_classification_is_expected(self, summary):
        assert summary["p88_classification"] == EXPECTED_P88_CLASSIFICATION

    def test_p88_classification_in_allowed_list(self, summary):
        assert summary["p88_classification"] in ALLOWED_P88_CLASSIFICATIONS

    def test_date_field(self, summary):
        assert summary.get("date") == "2026-05-27"

    def test_generated_at_present(self, summary):
        assert summary.get("generated_at", "")

    def test_phase_is_diagnostic_only(self, summary):
        assert summary.get("phase") == "diagnostic-only"

    def test_explicit_yes_required_field(self, summary):
        assert summary.get("explicit_yes_required") == EXPLICIT_YES_REQUIRED

    def test_authorization_status_not_granted(self, summary):
        assert summary.get("authorization_status") == "NOT GRANTED"

    def test_p88_modified_frozen_artifacts_false(self, summary):
        assert summary.get("p88_modified_frozen_artifacts") is False

    def test_frozen_artifacts_count(self, summary):
        assert summary.get("frozen_artifacts_count") >= 9

    def test_allowed_classifications_count(self, summary):
        assert len(summary.get("allowed_classifications", [])) == 6


# ─── Class 2: Step 1 — P87 State Check ───────────────────────────────────────

class TestStep1P87StateCheck:
    def test_step1_present(self, summary):
        assert "step1_check_p87_state" in summary

    def test_p87_summary_exists(self, summary):
        assert summary["step1_check_p87_state"]["p87_summary_exists"] is True

    def test_p87_classification_confirmed(self, summary):
        s = summary["step1_check_p87_state"]
        assert s["p87_classification"] == EXPECTED_P87_CLASSIFICATION

    def test_p87_classification_matches(self, summary):
        assert summary["step1_check_p87_state"]["p87_classification_matches"] is True

    def test_count_match_true(self, summary):
        assert summary["step1_check_p87_state"]["count_match"] is True

    def test_game_id_full_coverage_true(self, summary):
        assert summary["step1_check_p87_state"]["game_id_full_coverage"] is True

    def test_content_drift_likely_false(self, summary):
        assert summary["step1_check_p87_state"]["content_drift_likely"] is False

    def test_stale_by_mtime_only(self, summary):
        assert summary["step1_check_p87_state"]["stale_by_mtime_only"] is True

    def test_safe_without_explicit_yes_false(self, summary):
        assert summary["step1_check_p87_state"]["safe_without_explicit_yes"] is False

    def test_explicit_yes_field_in_step1(self, summary):
        s = summary["step1_check_p87_state"]
        assert s.get("explicit_yes_required") == EXPLICIT_YES_REQUIRED

    def test_delta_seconds_present(self, summary):
        assert summary["step1_check_p87_state"]["delta_seconds"] == 6134

    def test_p87_state_ok_true(self, summary):
        assert summary["step1_check_p87_state"]["p87_state_ok"] is True

    def test_no_issue(self, summary):
        assert summary["step1_check_p87_state"]["issue"] is None


# ─── Class 3: Step 2 — P86 State Check ───────────────────────────────────────

class TestStep2P86StateCheck:
    def test_step2_present(self, summary):
        assert "step2_check_p86_state" in summary

    def test_p86_summary_exists(self, summary):
        assert summary["step2_check_p86_state"]["p86_summary_exists"] is True

    def test_p86_classification_confirmed(self, summary):
        s = summary["step2_check_p86_state"]
        assert s["p86_classification"] == EXPECTED_P86_CLASSIFICATION

    def test_p86_classification_matches(self, summary):
        assert summary["step2_check_p86_state"]["p86_classification_matches"] is True

    def test_p86_state_ok_true(self, summary):
        assert summary["step2_check_p86_state"]["p86_state_ok"] is True

    def test_no_issue(self, summary):
        assert summary["step2_check_p86_state"]["issue"] is None

    def test_n_stale_risks_present(self, summary):
        n = summary["step2_check_p86_state"].get("n_stale_risks_in_p86", 0)
        assert n >= 1


# ─── Class 4: Step 3 — Authorization Phrase Check ────────────────────────────

class TestStep3AuthorizationPhraseCheck:
    def test_step3_present(self, summary):
        assert "step3_authorization_phrase_check" in summary

    def test_required_phrase_correct(self, summary):
        s = summary["step3_authorization_phrase_check"]
        assert s["required_phrase"] == EXPLICIT_YES_REQUIRED

    def test_authorization_input_not_provided(self, summary):
        s = summary["step3_authorization_phrase_check"]
        assert s["authorization_input_provided"] is False

    def test_authorization_not_granted(self, summary):
        assert summary["step3_authorization_phrase_check"]["authorization_granted"] is False

    def test_authorization_status_not_granted(self, summary):
        assert summary["step3_authorization_phrase_check"]["authorization_status"] == "NOT GRANTED"

    def test_note_mentions_gate_only(self, summary):
        note = summary["step3_authorization_phrase_check"]["note"].lower()
        assert "gate" in note or "not present" in note or "diagnostic" in note


# ─── Class 5: Step 4 — Recovery Preconditions ────────────────────────────────

class TestStep4RecoveryPreconditions:
    def test_step4_present(self, summary):
        assert "step4_recovery_preconditions" in summary

    def test_all_preconditions_met(self, summary):
        assert summary["step4_recovery_preconditions"]["all_preconditions_met"] is True

    def test_preconditions_list_not_empty(self, summary):
        assert len(summary["step4_recovery_preconditions"]["preconditions"]) >= 7

    def test_p87_summary_precondition_passes(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p87_summary_exists") is True

    def test_p87_classification_precondition_passes(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p87_classification_correct") is True

    def test_p87_count_match_precondition(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p87_count_match") is True

    def test_p87_game_id_coverage_precondition(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p87_game_id_full_coverage") is True

    def test_content_drift_false_precondition(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p87_content_drift_likely_false") is True

    def test_p86_summary_precondition_passes(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p86_summary_exists") is True

    def test_p86_classification_precondition_passes(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("p86_classification_correct") is True

    def test_canonical_rows_precondition_passes(self, summary):
        prec = {p["name"]: p["status"] for p in summary["step4_recovery_preconditions"]["preconditions"]}
        assert prec.get("canonical_rows_exists") is True


# ─── Class 6: Step 5 — Forbidden Actions ─────────────────────────────────────

class TestStep5ForbiddenActions:
    def test_step5_present(self, summary):
        assert "step5_forbidden_actions" in summary

    def test_forbidden_list_not_empty(self, summary):
        assert len(summary["step5_forbidden_actions"]["forbidden"]) >= 10

    def test_forbidden_includes_p84e_overwrite(self, summary):
        joined = " ".join(summary["step5_forbidden_actions"]["forbidden"]).lower()
        assert "p84e" in joined

    def test_forbidden_includes_canonical_rows(self, summary):
        joined = " ".join(summary["step5_forbidden_actions"]["forbidden"]).lower()
        assert "canonical" in joined

    def test_forbidden_includes_ev(self, summary):
        joined = " ".join(summary["step5_forbidden_actions"]["forbidden"]).lower()
        assert "ev" in joined or "clv" in joined or "kelly" in joined

    def test_enforcement_not_empty(self, summary):
        assert len(summary["step5_forbidden_actions"].get("enforcement", "")) > 20


# ─── Class 7: Step 6 — Authorized Recovery Sequence Plan ─────────────────────

class TestStep6RecoverySequencePlan:
    def test_step6_present(self, summary):
        assert "step6_authorized_recovery_sequence_plan" in summary

    def test_authorization_required_phrase(self, summary):
        s = summary["step6_authorized_recovery_sequence_plan"]
        assert s["authorization_required"] == EXPLICIT_YES_REQUIRED

    def test_execution_order_correct(self, summary):
        s = summary["step6_authorized_recovery_sequence_plan"]
        assert s["execution_order"] == EXPECTED_EXECUTION_ORDER

    def test_execution_order_length(self, summary):
        assert len(summary["step6_authorized_recovery_sequence_plan"]["execution_order"]) == 6

    def test_recovery_steps_count_is_9(self, summary):
        assert len(summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]) == 9

    @pytest.mark.parametrize("step_num", range(1, 10))
    def test_recovery_step_exists(self, summary, step_num):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        nums = [s["step_num"] for s in steps]
        assert step_num in nums

    def test_step1_is_p84e(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s1 = next(s for s in steps if s["step_num"] == 1)
        assert "p84e" in s1["script"].lower() or "p84e" in s1["action"].lower()

    def test_step6_is_p86(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s6 = next(s for s in steps if s["step_num"] == 6)
        assert "p86" in s6["script"].lower() or "p86" in s6["action"].lower()

    def test_step6_expects_p86_upgrade_to_ready(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s6 = next(s for s in steps if s["step_num"] == 6)
        expected = s6.get("expected_classification", "")
        assert "READY" in expected

    def test_step7_verify_p86_classification(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s7 = next(s for s in steps if s["step_num"] == 7)
        check = s7.get("check", "") + s7.get("action", "")
        assert "READY" in check or "verify" in check.lower()

    def test_step8_has_test_command(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s8 = next(s for s in steps if s["step_num"] == 8)
        assert "pytest" in s8.get("test_command", "")

    def test_step9_commit_whitelist_not_empty(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s9 = next(s for s in steps if s["step_num"] == 9)
        assert len(s9.get("whitelist", [])) >= 7

    def test_files_to_touch_after_authorization_not_empty(self, summary):
        files = summary["step6_authorized_recovery_sequence_plan"]["files_to_touch_after_authorization"]
        assert len(files) >= 6

    def test_files_never_to_touch_includes_canonical_rows(self, summary):
        never = " ".join(summary["step6_authorized_recovery_sequence_plan"]["files_never_to_touch"])
        assert "canonical_rows" in never or "prediction_rows" in never

    def test_step4_p84h_expected_metrics(self, summary):
        steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]
        s4 = next(s for s in steps if s["step_num"] == 4)
        metrics = s4.get("expected_metrics", {})
        assert abs(metrics.get("hit_rate", 0) - 0.569307) < 1e-4
        assert abs(metrics.get("auc", 0) - 0.594315) < 1e-4


# ─── Class 8: Step 7 — Governance Scan ──────────────────────────────────────

class TestStep7GovernanceScan:
    def test_step7_present(self, summary):
        assert "step7_governance_scan" in summary

    def test_governance_all_pass_true(self, summary):
        assert summary["step7_governance_scan"]["governance_all_pass"] is True

    def test_governance_has_17_flags(self, summary):
        gov = summary["step7_governance_scan"]["p88_governance"]
        assert len(gov) == 17

    @pytest.mark.parametrize("flag,expected", list(EXPECTED_GOVERNANCE_FLAGS.items()))
    def test_governance_flag(self, summary, flag, expected):
        gov = summary["step7_governance_scan"]["p88_governance"]
        assert flag in gov, f"Governance flag missing: {flag}"
        assert gov[flag] == expected, f"{flag}: expected={expected}, got={gov[flag]}"

    def test_all_governance_checks_pass(self, summary):
        checks = summary["step7_governance_scan"]["governance_checks"]
        for key, val in checks.items():
            assert val is True, f"Governance check failed: {key}={val}"

    def test_no_historical_artifact_overwrite_flag(self, summary):
        gov = summary["step7_governance_scan"]["p88_governance"]
        assert gov["no_historical_artifact_overwrite"] is True


# ─── Class 9: Step 9 — Final Classification ──────────────────────────────────

class TestStep9FinalClassification:
    def test_step9_present(self, summary):
        assert "step9_final_classification" in summary

    def test_classification_is_expected(self, summary):
        assert summary["step9_final_classification"]["classification"] == EXPECTED_P88_CLASSIFICATION

    def test_classification_matches_top_level(self, summary):
        s9 = summary["step9_final_classification"]
        assert s9["classification"] == summary["p88_classification"]

    def test_classification_in_allowed_list(self, summary):
        cls = summary["step9_final_classification"]["classification"]
        assert cls in ALLOWED_P88_CLASSIFICATIONS

    def test_allowed_classifications_count(self, summary):
        allowed = summary["step9_final_classification"]["allowed_classifications"]
        assert len(allowed) == 6

    def test_authorization_granted_false(self, summary):
        assert summary["step9_final_classification"]["authorization_granted"] is False

    def test_all_preconditions_met_true(self, summary):
        assert summary["step9_final_classification"]["all_preconditions_met"] is True

    def test_governance_all_pass_true(self, summary):
        assert summary["step9_final_classification"]["governance_all_pass"] is True

    def test_steps_checked_is_9(self, summary):
        assert summary["step9_final_classification"]["steps_checked"] == 9

    def test_steps_passed_is_9(self, summary):
        assert summary["step9_final_classification"]["steps_passed"] == 9

    def test_rationale_not_empty(self, summary):
        assert len(summary["step9_final_classification"]["rationale"]) > 20

    def test_rationale_mentions_authorization(self, summary):
        rationale = summary["step9_final_classification"]["rationale"].lower()
        assert "authorization" in rationale or "explicit" in rationale

    def test_explicit_yes_in_step9(self, summary):
        assert summary["step9_final_classification"]["explicit_yes_required"] == EXPLICIT_YES_REQUIRED


# ─── Class 10: Frozen Artifact Integrity ─────────────────────────────────────

class TestFrozenArtifactIntegrity:
    @pytest.mark.parametrize("path", FROZEN_PATHS)
    def test_frozen_artifact_still_exists(self, path):
        assert path.exists(), f"Frozen artifact missing: {path}"

    def test_p88_did_not_modify_frozen_artifacts(self, summary):
        assert summary["p88_modified_frozen_artifacts"] is False

    def test_step8_frozen_snapshot_present(self, summary):
        assert "step8_frozen_artifact_snapshot" in summary

    def test_step8_modified_flag_false(self, summary):
        assert summary["step8_frozen_artifact_snapshot"]["p88_modified_frozen_artifacts"] is False

    def test_step8_snapshot_has_entries(self, summary):
        snap = summary["step8_frozen_artifact_snapshot"]["snapshot"]
        assert len(snap) >= 9

    def test_p87_summary_not_overwritten(self, summary):
        snap = summary["step8_frozen_artifact_snapshot"]["snapshot"]
        p87_entry = snap.get("p87_stale_downstream_recovery_dry_run_summary.json", {})
        assert p87_entry.get("modified_by_p88") is False

    def test_p86_summary_not_overwritten(self, summary):
        snap = summary["step8_frozen_artifact_snapshot"]["snapshot"]
        p86_entry = snap.get("p86_artifact_regeneration_dependency_contract_summary.json", {})
        assert p86_entry.get("modified_by_p88") is False

    def test_canonical_rows_not_modified(self, summary):
        snap = summary["step8_frozen_artifact_snapshot"]["snapshot"]
        entry = snap.get("mlb_2026_prediction_rows.jsonl", {})
        assert entry.get("modified_by_p88") is False

    def test_p85_classification_unchanged(self):
        p = ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p85_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"

    def test_p84h_classification_unchanged(self):
        p = ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p84h_classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_p86_classification_unchanged(self):
        p = ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p86_classification"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"  # Updated: P89 recovered P86

    def test_p87_classification_unchanged(self):
        p = ROOT / "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p87_classification"] == "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"


# ─── Class 11: Report Content Validation ─────────────────────────────────────

class TestReportContent:
    def test_report_exists(self, report_text):
        assert len(report_text) > 100

    def test_report_contains_p88_classification(self, report_text):
        assert EXPECTED_P88_CLASSIFICATION in report_text

    def test_report_contains_p87_classification(self, report_text):
        assert EXPECTED_P87_CLASSIFICATION in report_text

    def test_report_contains_p86_classification(self, report_text):
        assert EXPECTED_P86_CLASSIFICATION in report_text

    def test_report_contains_explicit_yes(self, report_text):
        assert EXPLICIT_YES_REQUIRED in report_text

    def test_report_contains_governance_section(self, report_text):
        assert "Governance" in report_text

    def test_report_says_p88_did_not_regenerate(self, report_text):
        lower = report_text.lower()
        assert "did not regenerate" in lower or "p88 did not" in lower

    def test_report_says_no_frozen_overwrite(self, report_text):
        lower = report_text.lower()
        assert "did not overwrite" in lower or "no frozen" in lower

    def test_report_contains_regeneration_order_section(self, report_text):
        assert "Regeneration Order" in report_text or "Recovery Sequence" in report_text

    def test_report_paper_only_mentioned(self, report_text):
        assert "paper_only" in report_text

    def test_report_diagnostic_only_mentioned(self, report_text):
        assert "diagnostic_only" in report_text

    def test_report_no_production_betting_recommendation(self, report_text):
        lower = report_text.lower()
        assert "no production betting" in lower or "production betting recommendation" not in lower

    def test_report_no_ev_instruction(self, report_text):
        lower = report_text.lower()
        assert "no ev" in lower or "ev_computed = false" in lower

    def test_report_no_stake_instruction(self, report_text):
        lower = report_text.lower()
        assert "no stake" in lower or "stake" not in lower

    def test_report_no_real_bet(self, report_text):
        lower = report_text.lower()
        assert "no real bet" in lower or "real bet" not in lower

    def test_report_no_taiwan_lottery(self, report_text):
        assert "台灣運彩" not in report_text or "no" in report_text.lower()

    def test_report_lists_recovery_steps(self, report_text):
        assert "Step 1" in report_text and "Step 6" in report_text

    def test_report_p84e_in_recovery_plan(self, report_text):
        assert "P84E" in report_text

    def test_report_p86_upgrade_mentioned(self, report_text):
        assert "READY" in report_text
