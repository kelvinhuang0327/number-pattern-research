"""Tests for Phase 72 — Paper-only Market De-risk Guard Proposal.

All 15+ required test cases from the Phase 72 spec.
No data files required; orchestrator builds proposal in memory.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ─── Import orchestrator ──────────────────────────────────────────
from orchestrator.phase72_market_derisk_guard_proposal import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    MARKET_DERISK_GUARD_SPEC_READY,
    MARKET_DERISK_REPLAY_READY,
    MARKET_DERISK_SPEC_DATA_LIMITED,
    MARKET_DERISK_SPEC_GOVERNANCE_RISK,
    MARKET_DERISK_SPEC_NOT_ACTIONABLE,
    MARKET_DERISK_SPEC_OVERFIT_RISK,
    PHASE70_GATE_ANCHOR,
    PHASE71_GATE_ANCHOR,
    PHASE_VERSION,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    PIT_SAFE_VALIDATION,
    STOP_PATCH_SEARCH_RETURN_TO_P1,
    _VALID_GATES,
    _P71_TARGET_BAND_N,
    _P71_BRIER_DELTA,
    _P71_CI_LO,
    _P71_CI_HI,
    _P71_CI_STABLE,
    _P71_CI_EXCLUDES_ZERO,
    _P71_COMPRESSION_RATIO,
    _P71_WINDOWS_MARKET_SUPERIOR,
    _P71_WINDOWS_TOTAL,
    _P71_NC_OVERFIT_RISK_COUNT,
    _PROPOSAL_BAND_LO,
    _PROPOSAL_BAND_HI,
    _build_guard_candidates,
    _build_risk_register,
    _build_pit_safe_rules,
    _build_success_failure_criteria,
    _build_governance_rules,
    _build_phase73_design,
    _determine_gate,
    _to_dict,
    run_phase72_market_derisk_guard_proposal,
    GuardCandidate,
    RiskEntry,
    PitSafeRule,
    SuccessFailureCriteria,
    GovernanceRule,
    Phase73SimulationDesign,
    Phase72Report,
)

_EXPECTED_FEATURE_PROBE_COUNT = 6  # number of pit_safe_rules expected


# ═══════════════════════════════════════════════════════════════════
# TestSafetyConstants
# ═══════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    """Test 1 — All safety constants are correctly set."""

    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_prediction_jsonl_overwritten_is_false(self):
        assert PREDICTION_JSONL_OVERWRITTEN is False

    def test_pit_safe_validation_is_true(self):
        assert PIT_SAFE_VALIDATION is True

    def test_alpha_is_frozen_at_040(self):
        assert ALPHA == 0.40

    def test_safety_constants_are_bool_not_int(self):
        assert isinstance(CANDIDATE_PATCH_CREATED, bool)
        assert isinstance(PRODUCTION_MODIFIED, bool)
        assert isinstance(ALPHA_MODIFIED, bool)


# ═══════════════════════════════════════════════════════════════════
# TestPhaseIdentity
# ═══════════════════════════════════════════════════════════════════

class TestPhaseIdentity:
    """Test 2 — Phase identity and gate constants."""

    def test_phase_version_contains_phase72(self):
        assert "phase72" in PHASE_VERSION

    def test_completion_marker_contains_phase72(self):
        assert "PHASE_72" in COMPLETION_MARKER

    def test_phase70_gate_anchor_correct(self):
        assert PHASE70_GATE_ANCHOR == "MARKET_ONLY_SUPERIOR"

    def test_phase71_gate_anchor_correct(self):
        assert PHASE71_GATE_ANCHOR == "MARKET_DE_RISK_GUARD_PROMISING"

    def test_valid_gates_count(self):
        assert len(_VALID_GATES) == 7

    def test_all_gate_constants_in_valid_gates(self):
        assert MARKET_DERISK_GUARD_SPEC_READY in _VALID_GATES
        assert MARKET_DERISK_REPLAY_READY in _VALID_GATES
        assert MARKET_DERISK_SPEC_DATA_LIMITED in _VALID_GATES
        assert MARKET_DERISK_SPEC_OVERFIT_RISK in _VALID_GATES
        assert MARKET_DERISK_SPEC_GOVERNANCE_RISK in _VALID_GATES
        assert MARKET_DERISK_SPEC_NOT_ACTIONABLE in _VALID_GATES
        assert STOP_PATCH_SEARCH_RETURN_TO_P1 in _VALID_GATES

    def test_proposal_band_range(self):
        assert _PROPOSAL_BAND_LO == 0.65
        assert _PROPOSAL_BAND_HI == 0.70
        assert _PROPOSAL_BAND_LO < _PROPOSAL_BAND_HI


# ═══════════════════════════════════════════════════════════════════
# TestPhase71EvidenceConstants
# ═══════════════════════════════════════════════════════════════════

class TestPhase71EvidenceConstants:
    """Test 3 — Phase 71 evidence constants are consistent."""

    def test_p71_target_band_n_positive(self):
        assert _P71_TARGET_BAND_N > 0

    def test_p71_brier_delta_positive(self):
        # Market should be better than model → model_brier - market_brier > 0
        assert _P71_BRIER_DELTA > 0

    def test_p71_ci_bounds_ordered(self):
        assert _P71_CI_LO < _P71_CI_HI

    def test_p71_ci_excludes_zero(self):
        # If CI excludes zero, both bounds must be same sign
        if _P71_CI_EXCLUDES_ZERO:
            assert _P71_CI_LO > 0 or _P71_CI_HI < 0

    def test_p71_ci_stable_flag(self):
        assert isinstance(_P71_CI_STABLE, bool)

    def test_p71_compression_ratio_below_1(self):
        # Model should be more compressed than market
        assert 0 < _P71_COMPRESSION_RATIO < 1.0

    def test_p71_windows_consistent(self):
        assert _P71_WINDOWS_MARKET_SUPERIOR == _P71_WINDOWS_TOTAL

    def test_p71_nc_overfit_count_below_threshold(self):
        # Phase 71 found 2/6, threshold is 4
        assert _P71_NC_OVERFIT_RISK_COUNT < 4


# ═══════════════════════════════════════════════════════════════════
# TestGuardCandidates
# ═══════════════════════════════════════════════════════════════════

class TestGuardCandidates:
    """Test 4, 5, 6, 7, 8 — Guard matrix requirements."""

    def setup_method(self):
        self.guards = _build_guard_candidates()

    def test_at_least_5_guard_candidates(self):
        """Test 4: guard matrix 至少 5 個候選 guard"""
        assert len(self.guards) >= 5

    def test_all_guards_have_required_fields(self):
        """Test 6: 每個 guard 有 trigger/action/required_inputs/pit_safe/recommended"""
        for g in self.guards:
            assert isinstance(g, GuardCandidate)
            assert g.guard_id
            assert g.trigger_definition
            assert g.action_definition
            assert isinstance(g.required_inputs, list)
            assert len(g.required_inputs) >= 1
            assert isinstance(g.pit_safe, bool)
            assert isinstance(g.recommended, bool)

    def test_at_least_one_flag_or_shadow_only_guard(self):
        """Test 7: 至少一個 guard 是 flag-only 或 shadow-only"""
        flag_or_shadow = [
            g for g in self.guards
            if "shadow" in g.action_definition.lower()
            or "flag" in g.action_definition.lower()
            or "de_risk_flag" in g.guard_id
        ]
        assert len(flag_or_shadow) >= 1

    def test_no_automatic_betting_skip_or_stake_adjustment(self):
        """Test 8: 不允許 automatic betting skip / stake adjustment"""
        forbidden_terms = [
            "betting skip", "stake adjustment", "skip bet", "auto skip",
            "kelly", "bankroll", "stake sizing", "execution skip",
        ]
        for g in self.guards:
            text = (g.action_definition + g.trigger_definition).lower()
            for term in forbidden_terms:
                assert term not in text, (
                    f"Guard {g.guard_id} contains forbidden term '{term}'"
                )

    def test_no_production_mutation_in_actions(self):
        """Test 4 additional: 不允許 production probability replacement"""
        # These patterns indicate an AFFIRMATIVE mutation instruction.
        # We allow "do not modify ...", "do NOT modify ...", etc.
        # We detect forbidden patterns by stripping negation prefixes first.
        import re
        # Remove "do not", "do NOT", "never", "must not" + the following word(s)
        _neg_strip = re.compile(
            r"(do\s+not|do\s+NOT|never|must\s+not|not)\s+\S+\s+", re.IGNORECASE
        )
        forbidden_terms = [
            "model_home_prob ==", "model_home_prob =",
            "update production",
            "modify stacking_model",
            "production alpha patch",
        ]
        for g in self.guards:
            # Strip negation phrases before checking
            text = _neg_strip.sub("", g.action_definition.lower())
            for term in forbidden_terms:
                assert term not in text, (
                    f"Guard {g.guard_id} action contains forbidden: '{term}'"
                )

    def test_at_least_4_recommended_guards(self):
        recommended = [g for g in self.guards if g.recommended]
        assert len(recommended) >= 4

    def test_all_recommended_guards_are_pit_safe(self):
        for g in self.guards:
            if g.recommended:
                assert g.pit_safe is True, (
                    f"Recommended guard {g.guard_id} must be pit_safe"
                )

    def test_all_guards_have_pit_safe_notes(self):
        for g in self.guards:
            assert g.pit_safe_notes, f"Guard {g.guard_id} missing pit_safe_notes"

    def test_all_guards_have_rejection_reason_or_empty(self):
        for g in self.guards:
            assert isinstance(g.rejection_reason, str)

    def test_guard_ids_unique(self):
        ids = [g.guard_id for g in self.guards]
        assert len(ids) == len(set(ids))

    def test_required_inputs_are_lists(self):
        for g in self.guards:
            assert isinstance(g.required_inputs, list)
            for inp in g.required_inputs:
                assert isinstance(inp, str)

    def test_band_trigger_in_all_recommended_guards(self):
        """All recommended guards must include the 0.65-0.70 band in trigger."""
        for g in self.guards:
            if g.recommended:
                trig = g.trigger_definition.lower()
                assert "0.65" in trig or "65" in trig, (
                    f"Recommended guard {g.guard_id} missing band 0.65 in trigger"
                )

    def test_market_prob_in_required_inputs_for_recommended(self):
        """All recommended guards must require market_home_prob_no_vig."""
        for g in self.guards:
            if g.recommended:
                assert "market_home_prob_no_vig" in g.required_inputs, (
                    f"Recommended guard {g.guard_id} missing market_home_prob_no_vig"
                )


# ═══════════════════════════════════════════════════════════════════
# TestRiskRegister
# ═══════════════════════════════════════════════════════════════════

class TestRiskRegister:
    """Test 9 — Risk register 至少 8 個 risk."""

    def setup_method(self):
        self.risks = _build_risk_register()

    def test_at_least_8_risks(self):
        """Test 9: risk register 至少 8 個 risk"""
        assert len(self.risks) >= 8

    def test_all_risks_have_required_fields(self):
        required_fields = [
            "risk_name", "severity", "likelihood", "mitigation", "phase73_required_check"
        ]
        for r in self.risks:
            for field in required_fields:
                val = getattr(r, field, None)
                assert val, f"Risk missing or empty field '{field}'"

    def test_severity_values_valid(self):
        valid = {"HIGH", "MEDIUM", "LOW"}
        for r in self.risks:
            assert r.severity in valid, f"Invalid severity: {r.severity}"

    def test_likelihood_values_valid(self):
        valid = {"HIGH", "MEDIUM", "LOW"}
        for r in self.risks:
            assert r.likelihood in valid, f"Invalid likelihood: {r.likelihood}"

    def test_leakage_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("leakage" in n for n in names)

    def test_overfit_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("overfit" in n for n in names)

    def test_market_over_reliance_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("market" in n for n in names)

    def test_model_devaluation_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("model" in n for n in names)

    def test_sample_concentration_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("sample" in n or "concentration" in n for n in names)

    def test_threshold_mining_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("threshold" in n for n in names)

    def test_governance_bypass_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("governance" in n for n in names)

    def test_production_mutation_risk_present(self):
        names = [r.risk_name for r in self.risks]
        assert any("production" in n or "mutation" in n for n in names)

    def test_risk_names_unique(self):
        names = [r.risk_name for r in self.risks]
        assert len(names) == len(set(names))


# ═══════════════════════════════════════════════════════════════════
# TestPitSafeRules
# ═══════════════════════════════════════════════════════════════════

class TestPitSafeRules:
    """PIT-safe evidence rules."""

    def setup_method(self):
        self.rules = _build_pit_safe_rules()

    def test_at_least_5_rules(self):
        assert len(self.rules) >= 5

    def test_expected_feature_probe_count(self):
        assert len(self.rules) == _EXPECTED_FEATURE_PROBE_COUNT

    def test_all_required_rules_present(self):
        required = [r for r in self.rules if r.required]
        assert len(required) >= 5

    def test_all_rules_have_fields(self):
        for r in self.rules:
            assert r.rule_id
            assert r.description
            assert isinstance(r.required, bool)
            assert r.verification_method

    def test_train_before_eval_rule_present(self):
        ids = [r.rule_id for r in self.rules]
        assert any("train" in i.lower() or "PIT1" in i for i in ids)

    def test_no_production_overwrite_rule_present(self):
        assert any(
            "jsonl" in r.description.lower() or "overwrite" in r.description.lower()
            for r in self.rules
        )

    def test_rule_ids_unique(self):
        ids = [r.rule_id for r in self.rules]
        assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════
# TestSuccessFailureCriteria
# ═══════════════════════════════════════════════════════════════════

class TestSuccessFailureCriteria:
    """Phase 73 success/failure criteria."""

    def setup_method(self):
        self.criteria = _build_success_failure_criteria()

    def test_at_least_5_success_criteria(self):
        sc = [c for c in self.criteria if c.criterion_type == "success"]
        assert len(sc) >= 5

    def test_at_least_5_failure_criteria(self):
        fc = [c for c in self.criteria if c.criterion_type == "failure"]
        assert len(fc) >= 5

    def test_all_criteria_have_fields(self):
        for c in self.criteria:
            assert c.criterion_id
            assert c.criterion_type in {"success", "failure"}
            assert c.description
            assert c.measurement

    def test_brier_improvement_criterion_present(self):
        texts = [c.description.lower() + c.measurement.lower() for c in self.criteria]
        assert any("brier" in t for t in texts)

    def test_no_production_mutation_criterion_present(self):
        texts = [c.description.lower() + c.measurement.lower() for c in self.criteria]
        assert any("production" in t or "patch" in t for t in texts)

    def test_ci_excludes_zero_failure_criterion(self):
        fc_texts = [
            c.measurement.lower() for c in self.criteria if c.criterion_type == "failure"
        ]
        assert any("ci" in t or "confidence interval" in t for t in fc_texts)

    def test_criterion_ids_unique(self):
        ids = [c.criterion_id for c in self.criteria]
        assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════
# TestGovernanceRules
# ═══════════════════════════════════════════════════════════════════

class TestGovernanceRules:
    """Governance rules presence and correctness."""

    def setup_method(self):
        self.rules = _build_governance_rules()

    def test_at_least_5_governance_rules(self):
        assert len(self.rules) >= 5

    def test_no_edge_claim_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("edge" in t for t in texts)

    def test_no_profit_claim_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("profit" in t for t in texts)

    def test_no_production_patch_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("production patch" in t for t in texts)

    def test_no_automatic_execution_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("automatic" in t or "execution" in t for t in texts)

    def test_replay_only_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("replay" in t for t in texts)

    def test_human_review_required_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("human" in t for t in texts)

    def test_rollback_plan_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("rollback" in t for t in texts)

    def test_audit_log_rule_present(self):
        texts = [r.rule_text.lower() for r in self.rules]
        assert any("audit" in t for t in texts)

    def test_all_rules_have_enforced_by(self):
        for r in self.rules:
            assert r.enforced_by, f"Rule {r.rule_id} missing enforced_by"

    def test_rule_ids_unique(self):
        ids = [r.rule_id for r in self.rules]
        assert len(ids) == len(set(ids))


# ═══════════════════════════════════════════════════════════════════
# TestPhase73Design
# ═══════════════════════════════════════════════════════════════════

class TestPhase73Design:
    """Test 10 — Phase73 simulation design exists and is complete."""

    def setup_method(self):
        self.design = _build_phase73_design()

    def test_phase73_design_exists(self):
        """Test 10: Phase73 simulation design 存在"""
        assert self.design is not None

    def test_input_jsonl_specified(self):
        assert self.design.input_jsonl
        assert "jsonl" in self.design.input_jsonl

    def test_output_json_path_specified(self):
        assert self.design.output_json_report_path
        assert "phase73" in self.design.output_json_report_path.lower()

    def test_output_markdown_path_specified(self):
        assert self.design.output_markdown_report_path
        assert "phase73" in self.design.output_markdown_report_path.lower()

    def test_replay_method_specified(self):
        assert self.design.replay_method
        assert "replay" in self.design.replay_method.lower()

    def test_train_eval_split_specified(self):
        assert self.design.train_eval_split

    def test_at_least_4_trigger_candidates(self):
        assert len(self.design.trigger_candidates) >= 4

    def test_at_least_4_action_candidates(self):
        assert len(self.design.action_candidates) >= 4

    def test_at_least_5_metrics(self):
        assert len(self.design.metrics) >= 5

    def test_at_least_5_negative_controls(self):
        assert len(self.design.negative_controls) >= 5

    def test_bootstrap_plan_specified(self):
        assert self.design.bootstrap_plan
        assert "bootstrap" in self.design.bootstrap_plan.lower()

    def test_gate_candidates_specified(self):
        assert len(self.design.gate_candidates) >= 4

    def test_completion_marker_specified(self):
        assert "PHASE_73" in self.design.completion_marker

    def test_execution_phase_is_phase73(self):
        # Design is Phase 73, not Phase 72
        assert "Phase73" in self.design.execution_phase or "73" in self.design.execution_phase

    def test_output_not_production_jsonl(self):
        # Output path must not be the source prediction file
        assert "phase56" not in self.design.output_json_report_path
        assert "predictions" not in self.design.output_json_report_path

    def test_no_live_pipeline_modification(self):
        assert "live" not in self.design.replay_method.lower()


# ═══════════════════════════════════════════════════════════════════
# TestGateDetermination
# ═══════════════════════════════════════════════════════════════════

class TestGateDetermination:
    """Test 11 — Gate must be one of seven."""

    def setup_method(self):
        self.guards = _build_guard_candidates()
        self.risks = _build_risk_register()
        self.pit_rules = _build_pit_safe_rules()
        self.criteria = _build_success_failure_criteria()

    def test_gate_is_one_of_seven(self):
        """Test 11: gate 只能是七選一"""
        gate, rationale, risk_notes = _determine_gate(
            self.guards, self.risks, self.pit_rules, self.criteria
        )
        assert gate in _VALID_GATES, f"Invalid gate: {gate}"

    def test_gate_rationale_is_non_empty(self):
        gate, rationale, risk_notes = _determine_gate(
            self.guards, self.risks, self.pit_rules, self.criteria
        )
        assert rationale

    def test_risk_notes_is_list(self):
        gate, rationale, risk_notes = _determine_gate(
            self.guards, self.risks, self.pit_rules, self.criteria
        )
        assert isinstance(risk_notes, list)

    def test_expected_gate_spec_ready(self):
        """With Phase71 evidence strong + complete spec, expect SPEC_READY."""
        gate, _, _ = _determine_gate(
            self.guards, self.risks, self.pit_rules, self.criteria
        )
        assert gate == MARKET_DERISK_GUARD_SPEC_READY

    def test_gate_with_empty_guards_returns_data_limited(self):
        gate, _, _ = _determine_gate([], self.risks, self.pit_rules, self.criteria)
        assert gate in _VALID_GATES
        # With 0 guards, spec is not complete → should not be SPEC_READY
        assert gate != MARKET_DERISK_GUARD_SPEC_READY


# ═══════════════════════════════════════════════════════════════════
# TestSerialization
# ═══════════════════════════════════════════════════════════════════

class TestSerialization:
    """Report is JSON-serializable."""

    def setup_method(self):
        self.report = run_phase72_market_derisk_guard_proposal()

    def test_report_is_json_serializable(self):
        """Full report can be serialized to JSON."""
        result = json.dumps(
            {
                "gate": self.report.gate,
                "guard_candidates": self.report.guard_candidates,
                "risk_register": self.report.risk_register,
                "pit_safe_rules": self.report.pit_safe_rules,
                "success_failure_criteria": self.report.success_failure_criteria,
                "governance_rules": self.report.governance_rules,
                "phase73_simulation_design": self.report.phase73_simulation_design,
            }
        )
        assert result

    def test_to_dict_helper_works(self):
        d = _to_dict(GuardCandidate(
            guard_id="test_G",
            trigger_definition="test trigger",
            action_definition="test action",
            required_inputs=["x"],
            pit_safe=True,
            pit_safe_notes="ok",
            expected_risk_reduction="none",
            production_risk="low",
            phase73_testability="yes",
            rejection_reason="",
            recommended=True,
        ))
        assert d["guard_id"] == "test_G"
        assert isinstance(d["required_inputs"], list)


# ═══════════════════════════════════════════════════════════════════
# TestFullReportIntegrity
# ═══════════════════════════════════════════════════════════════════

class TestFullReportIntegrity:
    """Integration test: full report from run_phase72."""

    def setup_method(self):
        self.report = run_phase72_market_derisk_guard_proposal()

    def test_safety_constants_in_report(self):
        assert self.report.candidate_patch_created is False
        assert self.report.production_modified is False
        assert self.report.alpha_modified is False
        assert self.report.diagnostic_only is True
        assert self.report.prediction_jsonl_overwritten is False
        assert self.report.pit_safe_validation is True
        assert self.report.alpha == 0.40

    def test_gate_in_valid_set(self):
        assert self.report.gate in _VALID_GATES

    def test_completion_marker_in_report(self):
        assert self.report.completion_marker == COMPLETION_MARKER
        assert "PHASE_72" in self.report.completion_marker

    def test_phase71_evidence_matches_constants(self):
        assert self.report.p71_n_target_band == _P71_TARGET_BAND_N
        assert self.report.p71_brier_delta == _P71_BRIER_DELTA
        assert self.report.p71_ci_lo == _P71_CI_LO
        assert self.report.p71_ci_hi == _P71_CI_HI
        assert self.report.p71_compression_ratio == _P71_COMPRESSION_RATIO

    def test_guard_candidates_count(self):
        assert len(self.report.guard_candidates) >= 5

    def test_risk_register_count(self):
        assert len(self.report.risk_register) >= 8

    def test_pit_safe_rules_count(self):
        assert len(self.report.pit_safe_rules) >= 5

    def test_success_failure_criteria_present(self):
        sc = [c for c in self.report.success_failure_criteria if c["criterion_type"] == "success"]
        fc = [c for c in self.report.success_failure_criteria if c["criterion_type"] == "failure"]
        assert len(sc) >= 5
        assert len(fc) >= 5

    def test_governance_rules_present(self):
        assert len(self.report.governance_rules) >= 5

    def test_phase73_design_present(self):
        d = self.report.phase73_simulation_design
        assert d
        assert "input_jsonl" in d

    def test_recommended_guards_nonempty(self):
        assert len(self.report.recommended_guards) >= 4

    def test_phase73_recommended_matches_gate(self):
        if self.report.gate in {MARKET_DERISK_GUARD_SPEC_READY, MARKET_DERISK_REPLAY_READY}:
            assert self.report.phase73_recommended is True
        else:
            assert self.report.phase73_recommended is False

    def test_run_timestamp_present(self):
        assert self.report.run_timestamp_utc
        assert "T" in self.report.run_timestamp_utc  # ISO format

    def test_phase_chain_anchors_in_report(self):
        assert self.report.phase70_gate_anchor == "MARKET_ONLY_SUPERIOR"
        assert self.report.phase71_gate_anchor == "MARKET_DE_RISK_GUARD_PROMISING"


# ═══════════════════════════════════════════════════════════════════
# TestMarkdownRequirements (proxy checks via governance rules)
# ═══════════════════════════════════════════════════════════════════

class TestMarkdownRequirements:
    """Test 12, 13, 14 — Markdown report content requirements (proxy via report fields)."""

    def setup_method(self):
        self.report = run_phase72_market_derisk_guard_proposal()

    def test_no_edge_claim_governance_rule_exists(self):
        """Test 12: markdown report 包含 no edge claim"""
        texts = [r["rule_text"].lower() for r in self.report.governance_rules]
        assert any("edge" in t for t in texts), "no_edge_claim rule not found"

    def test_phase73_recommendation_present(self):
        """Test 13: markdown report 包含 Phase73 recommendation"""
        assert self.report.phase73_recommendation_note
        assert "Phase 73" in self.report.phase73_recommendation_note

    def test_completion_marker_in_report(self):
        """Test 14: markdown report 包含 completion marker"""
        assert "PHASE_72" in self.report.completion_marker
        assert "VERIFIED" in self.report.completion_marker


# ═══════════════════════════════════════════════════════════════════
# TestNoProductionModelImport
# ═══════════════════════════════════════════════════════════════════

class TestNoProductionModelImport:
    """Test 4 additional — no production model import mutation."""

    def test_stacking_model_not_imported(self):
        """stacking_model is not imported by the orchestrator."""
        import orchestrator.phase72_market_derisk_guard_proposal as mod
        assert not hasattr(mod, "stacking_model"), (
            "stacking_model should not be imported in Phase 72 orchestrator"
        )

    def test_no_live_pipeline_import(self):
        """stacking_model must not be imported (docstring/comment mentions are OK)."""
        import orchestrator.phase72_market_derisk_guard_proposal as mod
        import inspect
        src = inspect.getsource(mod)
        # Only check actual import statements, not docstrings/comments
        import_lines = [
            line for line in src.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        assert not any("stacking_model" in line for line in import_lines), (
            "stacking_model is imported in Phase 72 orchestrator"
        )

    def test_no_mlb_live_pipeline_import(self):
        import orchestrator.phase72_market_derisk_guard_proposal as mod
        import inspect
        src = inspect.getsource(mod)
        assert "mlb_live_pipeline" not in src


# ═══════════════════════════════════════════════════════════════════
# TestReportJsonFile (if runner has already been executed)
# ═══════════════════════════════════════════════════════════════════

class TestReportJsonFile:
    """Test JSON report file if it exists (generated by runner)."""

    _REPORT_PATH = (
        Path(__file__).parent.parent
        / "reports"
        / "phase72_market_derisk_guard_proposal_20260507.json"
    )

    def test_json_report_is_valid_json(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated; run runner first")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data

    def test_json_report_gate_is_valid(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["gate"] in _VALID_GATES

    def test_json_report_safety_constants(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        safety = data["safety"]
        assert safety["candidate_patch_created"] is False
        assert safety["production_modified"] is False
        assert safety["alpha_modified"] is False
        assert safety["alpha"] == 0.40

    def test_json_report_completion_marker(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert "PHASE_72" in data["completion_marker"]

    def test_json_report_guard_count(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["guard_candidates"]) >= 5

    def test_json_report_risk_register_count(self):
        if not self._REPORT_PATH.exists():
            pytest.skip("JSON report not yet generated")
        with open(self._REPORT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["risk_register"]) >= 8
