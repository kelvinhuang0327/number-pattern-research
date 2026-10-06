"""
Tests for P253H Feature Vocabulary Design.

Verifies the JSON artifact is well-formed, complete, and contains
all required vocabulary groups, MI metrics, evidence statuses,
and overclaim guard fields. Does not compute MI, modify DB,
modify registry, promote strategies, or give betting advice.
"""

import json
import os
import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JSON_PATH = os.path.join(
    _REPO_ROOT,
    "outputs", "research",
    "p253h_feature_vocabulary_design_20260607.json",
)


@pytest.fixture(scope="module")
def report():
    assert os.path.exists(_JSON_PATH), f"P253H JSON not found: {_JSON_PATH}"
    with open(_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------

def test_json_parses(report):
    assert isinstance(report, dict)


def test_schema_version(report):
    assert report.get("schema_version") == "1.0"


def test_task_id(report):
    assert report.get("task_id") == "P253H"


def test_classification(report):
    assert report.get("classification") == "FEATURE_VOCABULARY_DESIGN_COMPLETE"


def test_generated_at_present(report):
    assert report.get("generated_at")


# ---------------------------------------------------------------------------
# Phase 0
# ---------------------------------------------------------------------------

def test_phase0_stop_conditions_none(report):
    p0 = report.get("phase0_summary", {})
    assert p0.get("stop_conditions_triggered") == "NONE"


def test_phase0_p253g_visible(report):
    p0 = report.get("phase0_summary", {})
    assert p0.get("p253g_visible") is True


def test_phase0_p252i_visible(report):
    p0 = report.get("phase0_summary", {})
    assert p0.get("p252i_visible") is True


# ---------------------------------------------------------------------------
# P253G dependency
# ---------------------------------------------------------------------------

def test_p253g_dependency_verified(report):
    dep = report.get("p253g_dependency_verified", {})
    assert dep.get("found") is True
    assert dep.get("classification") == "FEATURE_BOTTLENECK_REPORT_INVENTORY_COMPLETE"


def test_p253g_terminology_gaps_resolved(report):
    dep = report.get("p253g_dependency_verified", {})
    resolved = dep.get("terminology_gaps_resolved", [])
    for tg in ["TG1", "TG2", "TG3", "TG4", "TG5", "TG6"]:
        assert tg in resolved, f"TG {tg} must be resolved"


def test_p253g_overclaim_risks_addressed(report):
    dep = report.get("p253g_dependency_verified", {})
    addressed = dep.get("overclaim_risks_addressed", [])
    for risk in ["OR1", "OR2", "OR3", "OR4", "OR5", "OR6"]:
        assert risk in addressed, f"OR {risk} must be addressed"


# ---------------------------------------------------------------------------
# Feature vocabulary
# ---------------------------------------------------------------------------

def test_feature_vocabulary_exists(report):
    fv = report.get("feature_vocabulary")
    assert isinstance(fv, dict)
    assert fv


def test_feature_vocabulary_has_groups(report):
    groups = report["feature_vocabulary"].get("groups", {})
    assert isinstance(groups, dict)
    assert len(groups) >= 10, "Must define at least 10 feature groups"


def test_feature_vocabulary_required_groups(report):
    groups = report["feature_vocabulary"]["groups"]
    required = [
        "draw_history_feature",
        "frequency_feature",
        "position_frequency_feature",
        "rolling_window_feature",
        "stability_feature",
        "parser_quality_feature",
        "data_integrity_feature",
        "entropy_compression_feature",
        "mi_channel_feature",
        "artifact_only_feature",
    ]
    for g in required:
        assert g in groups, f"Required feature group missing: {g}"


def test_feature_vocabulary_frequency_group_has_p219_result(report):
    freq_group = report["feature_vocabulary"]["groups"]["frequency_feature"]
    assert freq_group.get("p219_tested") is True
    assert freq_group.get("p219_result")
    result = freq_group["p219_result"]
    assert "DAILY_539" in result or "trailing_freq" in result


def test_feature_vocabulary_position_frequency_blocked(report):
    pos_group = report["feature_vocabulary"]["groups"]["position_frequency_feature"]
    assert pos_group.get("blocker") or "BLOCKED" in pos_group.get("p219_note", "")


def test_feature_vocabulary_has_terminology_resolutions(report):
    resolutions = report["feature_vocabulary"].get("terminology_resolutions", {})
    assert isinstance(resolutions, dict)
    assert len(resolutions) >= 6


def test_feature_vocabulary_tg5_resolved(report):
    resolutions = report["feature_vocabulary"].get("terminology_resolutions", {})
    assert any("TG5" in k for k in resolutions.keys())


# ---------------------------------------------------------------------------
# MI/channel vocabulary
# ---------------------------------------------------------------------------

def test_mi_channel_vocabulary_exists(report):
    mv = report.get("mi_channel_vocabulary")
    assert isinstance(mv, dict)
    assert mv


def test_mi_channel_vocabulary_has_metrics(report):
    metrics = report["mi_channel_vocabulary"].get("metrics", {})
    assert isinstance(metrics, dict)
    assert len(metrics) >= 5


def test_mi_channel_vocabulary_null_mi_95th_pct(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "null_mi_95th_pct" in metrics


def test_mi_channel_vocabulary_null_mi_99th_pct(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "null_mi_99th_pct" in metrics


def test_mi_channel_vocabulary_feature_to_hit_binary(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "feature_to_hit_binary_mi" in metrics


def test_mi_channel_vocabulary_sequence_autocorrelation(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "sequence_autocorrelation_mi" in metrics


def test_mi_channel_vocabulary_above_null_floor(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "above_null_floor" in metrics


def test_mi_channel_vocabulary_below_detection_floor(report):
    metrics = report["mi_channel_vocabulary"]["metrics"]
    assert "below_detection_floor" in metrics


def test_mi_channel_vocabulary_has_channel_status_taxonomy(report):
    mv = report["mi_channel_vocabulary"]
    taxonomy = mv.get("channel_status_taxonomy", {})
    assert isinstance(taxonomy, dict)
    assert "EMPTY_CHANNEL" in taxonomy
    assert "BLOCKED_CHANNEL" in taxonomy


def test_mi_channel_vocabulary_p219_results_documented(report):
    metric = report["mi_channel_vocabulary"]["metrics"]["feature_to_hit_binary_mi"]
    results = metric.get("p219_results", {})
    assert "DAILY_539" in results
    assert "POWER_LOTTO" in results


# ---------------------------------------------------------------------------
# Evidence status vocabulary
# ---------------------------------------------------------------------------

def test_evidence_status_vocabulary_exists(report):
    ev = report.get("evidence_status_vocabulary")
    assert isinstance(ev, dict)
    assert ev


def test_evidence_status_vocabulary_has_statuses(report):
    statuses = report["evidence_status_vocabulary"].get("statuses", {})
    assert isinstance(statuses, dict)
    assert len(statuses) >= 8


def test_evidence_status_tested_null(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "TESTED_NULL" in statuses


def test_evidence_status_underpowered(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "UNDERPOWERED" in statuses


def test_evidence_status_artifact_only(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "ARTIFACT_ONLY" in statuses


def test_evidence_status_not_tested(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "NOT_TESTED" in statuses


def test_evidence_status_data_quality_blocked(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "DATA_QUALITY_BLOCKED" in statuses


def test_evidence_status_needs_preregistration(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "NEEDS_PREREGISTRATION" in statuses


def test_evidence_status_needs_walk_forward(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "NEEDS_WALK_FORWARD" in statuses


def test_evidence_status_corrected_significant_not_promotable(report):
    statuses = report["evidence_status_vocabulary"]["statuses"]
    assert "CORRECTED_SIGNIFICANT_BUT_NOT_PROMOTABLE" in statuses


def test_evidence_status_current_matrix_has_tested_null(report):
    matrix = report["evidence_status_vocabulary"].get("current_status_matrix", {})
    daily = matrix.get("DAILY_539", {})
    assert daily.get("trailing_freq") == "TESTED_NULL"


def test_evidence_status_current_matrix_3star_underpowered(report):
    matrix = report["evidence_status_vocabulary"].get("current_status_matrix", {})
    star3 = matrix.get("3_STAR", {})
    all_features = star3.get("all_features") or ""
    assert "UNDERPOWERED" in all_features


# ---------------------------------------------------------------------------
# Overclaim guard fields
# ---------------------------------------------------------------------------

def test_overclaim_guard_fields_exists(report):
    og = report.get("overclaim_guard_fields")
    assert isinstance(og, dict)
    assert og


def test_overclaim_guard_has_required_fields(report):
    guards = report["overclaim_guard_fields"].get("required_guard_fields", {})
    required = [
        "no_edge_claim",
        "no_betting_advice",
        "random_compatible_does_not_imply_predictive_edge",
        "anomaly_not_predictor",
        "near_zero_mi_not_feature_space_exhausted",
        "artifact_signal_not_strategy",
    ]
    for g in required:
        assert g in guards, f"Required overclaim guard missing: {g}"


def test_overclaim_guard_all_values_true(report):
    guards = report["overclaim_guard_fields"]["required_guard_fields"]
    for name, field in guards.items():
        assert field.get("value") is True, f"Guard {name} must have value=True"


def test_overclaim_guard_has_validation_rule(report):
    og = report["overclaim_guard_fields"]
    assert og.get("validation_rule")


# ---------------------------------------------------------------------------
# Future M8 report schema
# ---------------------------------------------------------------------------

def test_future_m8_report_schema_exists(report):
    schema = report.get("future_m8_report_schema")
    assert isinstance(schema, dict)
    assert schema


def test_future_m8_report_schema_has_artifact_fields(report):
    schema = report["future_m8_report_schema"]
    af = schema.get("artifact_level_fields", [])
    assert isinstance(af, list)
    assert len(af) >= 10


def test_future_m8_report_schema_has_per_feature_fields(report):
    schema = report["future_m8_report_schema"]
    pf = schema.get("per_feature_fields", [])
    assert isinstance(pf, list)
    assert len(pf) >= 10


def test_future_m8_schema_has_evidence_status_field(report):
    schema = report["future_m8_report_schema"]
    field_names = [f["field"] for f in schema.get("per_feature_fields", [])]
    assert "evidence_status" in field_names


def test_future_m8_schema_has_mi_type_field(report):
    schema = report["future_m8_report_schema"]
    field_names = [f["field"] for f in schema.get("per_feature_fields", [])]
    assert "mi_type" in field_names


def test_future_m8_schema_has_null_mi_fields(report):
    schema = report["future_m8_report_schema"]
    field_names = [f["field"] for f in schema.get("per_feature_fields", [])]
    assert "null_mi_95th_pct" in field_names
    assert "null_mi_99th_pct" in field_names


def test_future_m8_schema_has_overclaim_guards_in_artifact(report):
    schema = report["future_m8_report_schema"]
    af_names = [f["field"] for f in schema.get("artifact_level_fields", [])]
    assert "no_edge_claim" in af_names
    assert "no_betting_advice" in af_names
    assert "anomaly_not_predictor" in af_names


def test_future_m8_schema_has_null_mi_procedure(report):
    schema = report["future_m8_report_schema"]
    proc = schema.get("null_mi_computation_procedure", {})
    assert proc.get("method")
    assert proc.get("n_simulations")


def test_future_m8_schema_null_mi_procedure_warns_about_l96(report):
    schema = report["future_m8_report_schema"]
    proc = schema.get("null_mi_computation_procedure", {})
    warning = proc.get("warning", "").lower()
    assert "l96" in warning or "shuffle" in warning or "label" in warning


def test_future_m8_schema_has_feature_group_field(report):
    schema = report["future_m8_report_schema"]
    pf_names = [f["field"] for f in schema.get("per_feature_fields", [])]
    assert "feature_group" in pf_names


def test_future_m8_schema_note_says_supersedes_p253g(report):
    schema = report["future_m8_report_schema"]
    note = schema.get("design_note", "").lower()
    assert "p253g" in note or "supersedes" in note or "incorporates" in note


# ---------------------------------------------------------------------------
# Readiness decision
# ---------------------------------------------------------------------------

def test_readiness_decision_exists(report):
    rd = report.get("readiness_decision")
    assert isinstance(rd, dict)
    assert rd


def test_readiness_decision_ready_for_design(report):
    rd = report["readiness_decision"]
    assert "READY" in rd.get("decision", "").upper()


def test_readiness_decision_has_prerequisites(report):
    rd = report["readiness_decision"]
    pre = rd.get("remaining_prerequisites_for_p253i", [])
    assert isinstance(pre, list)
    assert len(pre) >= 3


# ---------------------------------------------------------------------------
# Recommended next task
# ---------------------------------------------------------------------------

def test_recommended_next_task_exists_exactly_once(report):
    assert "recommended_next_task" in report
    rnt = report["recommended_next_task"]
    assert isinstance(rnt, dict)
    rec = rnt.get("recommendation", "")
    assert rec


def test_recommended_next_task_p253i_or_hold(report):
    rnt = report["recommended_next_task"]
    rec = rnt.get("recommendation", "")
    assert "P253I" in rec or "HOLD" in rec


def test_recommended_next_task_has_authorization_phrase(report):
    rnt = report["recommended_next_task"]
    phrase = rnt.get("authorization_phrase", "")
    assert "P253I" in phrase or "feature bottleneck" in phrase.lower()


def test_recommended_next_task_no_predictive_edge_claim(report):
    rnt = report["recommended_next_task"]
    text = str(rnt).lower()
    forbidden = ["deployable edge found", "prediction edge found",
                 "betting advice is given", "strategy promoted"]
    for kw in forbidden:
        assert kw not in text, f"recommended_next_task must not contain: '{kw}'"


# ---------------------------------------------------------------------------
# Safety booleans
# ---------------------------------------------------------------------------

def test_no_db_write_confirmed(report):
    assert report.get("no_db_write_confirmed") is True


def test_no_registry_mutation_confirmed(report):
    assert report.get("no_registry_mutation_confirmed") is True


def test_no_strategy_promotion_confirmed(report):
    assert report.get("no_strategy_promotion_confirmed") is True


def test_no_betting_advice_confirmed(report):
    assert report.get("no_betting_advice_confirmed") is True


# ---------------------------------------------------------------------------
# Final decision
# ---------------------------------------------------------------------------

def test_final_decision_present(report):
    fd = report.get("final_decision")
    assert fd
    assert len(fd) > 50


def test_final_decision_does_not_claim_predictive_edge(report):
    fd = report.get("final_decision", "").lower()
    affirmative_forbidden = [
        "betting advice is given",
        "strategy is promoted",
        "strategy promoted",
        "win rate improvement",
        "prediction edge found",
        "deployable edge found",
    ]
    for kw in affirmative_forbidden:
        assert kw not in fd, f"final_decision must not contain affirmative claim: '{kw}'"
    if "deployable prediction edge" in fd:
        idx = fd.index("deployable prediction edge")
        context = fd[max(0, idx - 5):idx]
        assert "no " in context or "not" in context


def test_final_decision_contains_vocabulary_design_complete(report):
    fd = report.get("final_decision", "").upper()
    assert "VOCABULARY" in fd or "DESIGN" in fd or "COMPLETE" in fd


def test_final_decision_references_p253i(report):
    fd = report.get("final_decision", "")
    assert "P253I" in fd
