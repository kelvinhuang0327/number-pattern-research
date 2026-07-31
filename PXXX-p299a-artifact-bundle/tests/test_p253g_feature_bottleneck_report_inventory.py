"""
Tests for P253G Feature Bottleneck Report Inventory.

Verifies the JSON artifact is well-formed, complete, and contains
required overclaim-risk and safety fields. Does not compute MI,
modify DB, modify registry, promote strategies, or give betting advice.
"""

import json
import os
import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JSON_PATH = os.path.join(
    _REPO_ROOT,
    "outputs", "research",
    "p253g_feature_bottleneck_report_inventory_20260607.json",
)


@pytest.fixture(scope="module")
def report():
    assert os.path.exists(_JSON_PATH), f"P253G JSON not found: {_JSON_PATH}"
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
    assert report.get("task_id") == "P253G"


def test_classification(report):
    assert report.get("classification") == "FEATURE_BOTTLENECK_REPORT_INVENTORY_COMPLETE"


def test_generated_at_present(report):
    assert "generated_at" in report
    assert report["generated_at"]


# ---------------------------------------------------------------------------
# Phase 0
# ---------------------------------------------------------------------------

def test_phase0_summary_present(report):
    assert "phase0_summary" in report
    p0 = report["phase0_summary"]
    assert isinstance(p0, dict)
    assert p0.get("stop_conditions_triggered") == "NONE"


def test_phase0_prior_tasks_visible(report):
    p0 = report["phase0_summary"]
    assert p0.get("p253a_visible") is True
    assert p0.get("p252i_visible") is True


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def test_p253a_dependency_verified(report):
    dep = report.get("p253a_dependency_verified", {})
    assert dep.get("found") is True
    assert dep.get("m8_readiness_in_p253a") == "DEFER"
    assert isinstance(dep.get("m8_blocking_issues_in_p253a"), list)
    assert len(dep["m8_blocking_issues_in_p253a"]) > 0


def test_p252b_dependency_verified(report):
    dep = report.get("p252b_dependency_verified", {})
    assert dep.get("found") is True
    assert "PARTIAL" in dep.get("m8_status_in_p252b", "")


# ---------------------------------------------------------------------------
# Artifact inventory
# ---------------------------------------------------------------------------

def test_artifact_inventory_exists_and_nonempty(report):
    inv = report.get("artifact_inventory")
    assert isinstance(inv, list)
    assert len(inv) > 0, "artifact_inventory must be non-empty"


def test_artifact_inventory_has_required_fields(report):
    required_fields = {"artifact_id", "path", "task", "classifications", "description",
                       "lottery_types_covered", "key_findings", "do_not_edit"}
    for art in report["artifact_inventory"]:
        missing = required_fields - set(art.keys())
        assert not missing, f"Artifact {art.get('artifact_id')} missing: {missing}"


def test_artifact_inventory_classifications_valid(report):
    valid_labels = {
        "FEATURE_BOTTLENECK_LIKE_ARTIFACT",
        "MI_OR_CHANNEL_METRIC_PRESENT",
        "ENTROPY_OR_COMPRESSION_DIAGNOSTIC",
        "NULL_OR_NO_EDGE_EVIDENCE",
        "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "ARCHIVED_OR_EXPLORATORY_DEFER",
        "UNKNOWN_NEEDS_SCOPE",
    }
    for art in report["artifact_inventory"]:
        for cls in art["classifications"]:
            assert cls in valid_labels, f"Unknown classification: {cls}"


def test_artifact_inventory_has_p219_mi_artifact(report):
    paths = [a["path"] for a in report["artifact_inventory"]]
    assert any("p219" in p for p in paths), "P219 MI sweep artifact should be inventoried"


def test_artifact_inventory_has_schema_artifact(report):
    paths = [a["path"] for a in report["artifact_inventory"]]
    assert any("statistical_diagnostics_schema" in p for p in paths)


def test_artifact_inventory_has_feature_bottleneck_like(report):
    all_classes = []
    for art in report["artifact_inventory"]:
        all_classes.extend(art["classifications"])
    assert "FEATURE_BOTTLENECK_LIKE_ARTIFACT" in all_classes


def test_artifact_inventory_has_mi_channel_metric(report):
    all_classes = []
    for art in report["artifact_inventory"]:
        all_classes.extend(art["classifications"])
    assert "MI_OR_CHANNEL_METRIC_PRESENT" in all_classes


def test_artifact_inventory_has_null_no_edge_evidence(report):
    all_classes = []
    for art in report["artifact_inventory"]:
        all_classes.extend(art["classifications"])
    assert "NULL_OR_NO_EDGE_EVIDENCE" in all_classes


# ---------------------------------------------------------------------------
# Metric inventory
# ---------------------------------------------------------------------------

def test_metric_inventory_exists(report):
    inv = report.get("metric_inventory")
    assert isinstance(inv, list)
    assert len(inv) > 0


def test_metric_inventory_has_required_fields(report):
    required = {"metric_id", "metric_name", "definition", "lottery_coverage", "status"}
    for m in report["metric_inventory"]:
        missing = required - set(m.keys())
        assert not missing, f"Metric {m.get('metric_id')} missing: {missing}"


def test_metric_inventory_has_mi_metric(report):
    statuses = [m["status"] for m in report["metric_inventory"]]
    assert any("NEAR_ZERO" in s or "near_zero" in s.lower() or "COMPUTED" in s
               for s in statuses)


def test_metric_inventory_has_schema_field_metric(report):
    statuses = [m.get("status", "") for m in report["metric_inventory"]]
    assert any("SCHEMA_FIELD_ONLY" in s for s in statuses)


# ---------------------------------------------------------------------------
# Lottery-type coverage
# ---------------------------------------------------------------------------

def test_lottery_type_coverage_present(report):
    cov = report.get("lottery_type_coverage")
    assert isinstance(cov, dict)
    assert len(cov) >= 3


def test_lottery_type_coverage_has_daily_539(report):
    cov = report["lottery_type_coverage"]
    assert "DAILY_539" in cov
    assert cov["DAILY_539"]["mi_computed"] is True


def test_lottery_type_coverage_has_power_lotto(report):
    cov = report["lottery_type_coverage"]
    assert "POWER_LOTTO" in cov
    assert cov["POWER_LOTTO"]["mi_computed"] is True


def test_lottery_type_coverage_has_3_star(report):
    cov = report["lottery_type_coverage"]
    assert "3_STAR" in cov
    assert cov["3_STAR"]["mi_computed"] is False


def test_lottery_type_coverage_daily_539_near_zero(report):
    cov = report["lottery_type_coverage"]
    mi_val = cov["DAILY_539"].get("mi_value_bits", "")
    assert mi_val, "DAILY_539 should have mi_value_bits"
    assert "e-" in str(mi_val).lower() or "near" in str(mi_val).lower() or "8.8" in str(mi_val)


# ---------------------------------------------------------------------------
# Terminology gaps
# ---------------------------------------------------------------------------

def test_terminology_gaps_present(report):
    gaps = report.get("terminology_gaps")
    assert isinstance(gaps, list)
    assert len(gaps) > 0


def test_terminology_gap_count_matches(report):
    assert report.get("terminology_gap_count") == len(report["terminology_gaps"])


def test_terminology_gaps_have_required_fields(report):
    required = {"gap_id", "term", "variants_found", "inconsistency", "risk", "resolution_required"}
    for gap in report["terminology_gaps"]:
        missing = required - set(gap.keys())
        assert not missing, f"Gap {gap.get('gap_id')} missing: {missing}"


def test_terminology_gap_feature_bottleneck_naming(report):
    gap_terms = [g["term"] for g in report["terminology_gaps"]]
    assert any("feature bottleneck" in t or "feature_bottleneck" in t for t in gap_terms)


def test_terminology_gap_mi_confusion(report):
    gap_terms = [g["term"] for g in report["terminology_gaps"]]
    assert any("mutual information" in t.lower() or "MI" in t for t in gap_terms)


# ---------------------------------------------------------------------------
# Overclaim risks
# ---------------------------------------------------------------------------

def test_overclaim_risks_present(report):
    risks = report.get("overclaim_risks")
    assert isinstance(risks, list)
    assert len(risks) >= 4


def test_overclaim_risks_have_required_fields(report):
    required = {"risk_id", "label", "title", "description", "mitigation"}
    for r in report["overclaim_risks"]:
        missing = required - set(r.keys())
        assert not missing, f"Risk {r.get('risk_id')} missing: {missing}"


def test_overclaim_risk_random_compatible_not_edge(report):
    labels = [r["label"] for r in report["overclaim_risks"]]
    assert "random-compatible-not-edge" in labels, \
        "Must include random-compatible-not-edge overclaim risk"


def test_overclaim_risk_anomaly_not_predictor(report):
    labels = [r["label"] for r in report["overclaim_risks"]]
    assert "anomaly-not-predictor" in labels, \
        "Must include anomaly-not-predictor overclaim risk"


def test_overclaim_risk_mi_zero_not_exhausted(report):
    labels = [r["label"] for r in report["overclaim_risks"]]
    assert any("mi" in l.lower() or "near-zero" in l for l in labels), \
        "Must include MI near-zero overclaim risk"


def test_overclaim_risk_artifact_not_strategy(report):
    labels = [r["label"] for r in report["overclaim_risks"]]
    assert any("artifact" in l or "strategy" in l for l in labels), \
        "Must include artifact-to-strategy overclaim risk"


# ---------------------------------------------------------------------------
# Future M8 schema recommendation
# ---------------------------------------------------------------------------

def test_future_m8_schema_recommendation_exists(report):
    schema = report.get("future_m8_schema_recommendation")
    assert isinstance(schema, dict)
    assert schema


def test_future_m8_schema_has_required_fields_list(report):
    schema = report["future_m8_schema_recommendation"]
    fields = schema.get("required_fields")
    assert isinstance(fields, list)
    assert len(fields) >= 5


def test_future_m8_schema_has_no_edge_claim_field(report):
    schema = report["future_m8_schema_recommendation"]
    field_names = [f["field"] for f in schema.get("required_fields", [])]
    assert "no_edge_claim" in field_names


def test_future_m8_schema_has_mi_bits_field(report):
    schema = report["future_m8_schema_recommendation"]
    field_names = [f["field"] for f in schema.get("required_fields", [])]
    assert "mi_bits" in field_names


def test_future_m8_schema_has_prerequisites(report):
    schema = report["future_m8_schema_recommendation"]
    prereqs = schema.get("design_prerequisites")
    assert isinstance(prereqs, list)
    assert len(prereqs) > 0


def test_future_m8_schema_note_says_not_implemented(report):
    schema = report["future_m8_schema_recommendation"]
    note = schema.get("note", "").lower()
    assert "not implement" in note or "does not implement" in note or "proposed" in note


# ---------------------------------------------------------------------------
# Readiness decision
# ---------------------------------------------------------------------------

def test_readiness_decision_exists(report):
    rd = report.get("readiness_decision")
    assert isinstance(rd, dict)
    assert rd


def test_readiness_decision_has_decision_field(report):
    rd = report["readiness_decision"]
    assert "decision" in rd
    assert rd["decision"]


def test_readiness_decision_is_defer(report):
    rd = report["readiness_decision"]
    decision = rd["decision"].upper()
    assert "DEFER" in decision, f"Expected DEFER, got: {decision}"


def test_readiness_decision_has_rationale(report):
    rd = report["readiness_decision"]
    assert "rationale" in rd
    assert len(rd["rationale"]) > 50


def test_readiness_decision_has_preconditions(report):
    rd = report["readiness_decision"]
    pre = rd.get("preconditions_for_design_start")
    assert isinstance(pre, list)
    assert len(pre) >= 3


# ---------------------------------------------------------------------------
# Recommended next task
# ---------------------------------------------------------------------------

def test_recommended_next_task_exists_exactly_once(report):
    assert "recommended_next_task" in report
    rnt = report["recommended_next_task"]
    assert isinstance(rnt, dict)
    # Exactly one recommendation
    rec = rnt.get("recommendation", "")
    assert rec, "recommendation must be non-empty"
    # Must be either HOLD or a task proposal
    assert "HOLD" in rec or "P253H" in rec or "DESIGN" in rec


def test_recommended_next_task_no_predictive_edge_claim(report):
    rnt = report["recommended_next_task"]
    rec_str = str(rnt).lower()
    forbidden = ["deployable edge", "prediction edge", "betting advice", "strategy promotion"]
    for kw in forbidden:
        assert kw not in rec_str, f"recommended_next_task must not contain: '{kw}'"


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
    # Check for affirmative edge claims — negating phrases like "no deployable edge" are fine
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
    # Verify "no" appears before any edge mention (negation check)
    if "deployable prediction edge" in fd:
        idx = fd.index("deployable prediction edge")
        context = fd[max(0, idx - 5):idx]
        assert "no " in context or "not" in context, \
            "Any 'deployable prediction edge' phrase must be negated"


def test_final_decision_contains_inventory_complete(report):
    fd = report.get("final_decision", "").upper()
    assert "INVENTORY" in fd or "COMPLETE" in fd


def test_final_decision_no_deployable_edge(report):
    fd = report.get("final_decision", "").lower()
    assert "no deployable prediction edge" in fd or "no deployable edge" in fd
