"""
Tests for P57 — Monitoring Contract V2 Annotation Integration.

20 tests:
T01  P56 source artifact exists and is loaded
T02  P57 JSON exists and contains all required top-level sections
T03  Annotation metadata schema contains required fields
T04  Sep 2025 mid-band annotation is carried forward
T05  n=27 remains BAND_SAMPLE_INSUFFICIENT
T06  Action remains TRACK_ONLY_NO_REFIT
T07  should_trigger_refit equals False
T08  should_change_thresholds equals False
T09  should_change_global_status equals False
T10  Global vs band status separation rules exist
T11  P52 compatibility statement exists
T12  Governance flags exist and match required values
T13  live_api_calls equals 0
T14  runtime_recommendation_logic_changed equals False
T15  platt_constants_modified equals False
T16  p52_thresholds_changed equals False
T17  p52/p53/p54/p55/p56 overwrite flags are False
T18  JSON output contains no deployment-readiness classification
T19  Reports contain no affirmative production or profit claims
T20  active_task.md references final P57 classification
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P56_JSON = ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json"
P57_JSON = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"
REPORT_MD = ROOT / "report/p57_monitoring_contract_v2_annotation_integration_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p57_monitoring_contract_v2_annotation_integration_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

REQUIRED_TOP_LEVEL_KEYS = {
    "p57_phase",
    "run_date",
    "source_artifacts",
    "p52_contract_recap",
    "p56_policy_recap",
    "annotation_metadata_schema",
    "global_vs_band_status_separation",
    "sep_2025_mid_band_annotation_carry_forward",
    "future_monitoring_report_requirements",
    "future_evidence_requirements",
    "p52_v2_compatibility",
    "data_gap_status",
    "final_p57_classification",
    "governance_flags",
}

REQUIRED_SCHEMA_FIELDS = {
    "annotation_scope",
    "metric_family",
    "band_label",
    "band_n",
    "sample_tier",
    "annotation",
    "action",
    "evidence_strength",
    "platt_ece",
    "raw_ece",
    "ece_delta",
    "repeated_month_count",
    "cumulative_band_n",
    "future_evidence_required",
    "should_change_global_status",
    "should_trigger_refit",
    "should_change_thresholds",
}

FORBIDDEN_CLASSIFICATIONS = [
    "DEPLOYMENT_READY",
    "PRODUCTION_READY",
    "CHAMPION_PROMOTED",
    "KELLY_LIVE",
    "LIVE_BETTING_APPROVED",
]

FORBIDDEN_REPORT_PHRASES = [
    "guaranteed profit",
    "expected profit",
    "will profit",
    "deploy to production",
    "ready for live betting",
    "champion strategy activated",
    "kelly_deploy_allowed=True",
]


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P57_JSON.exists(), f"P57 JSON not found: {P57_JSON}"
    return json.loads(P57_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T01 — P56 source artifact exists and is loaded
# ---------------------------------------------------------------------------
def test_t01_p56_source_artifact_loaded(summary: dict) -> None:
    """P56 JSON must exist and be referenced in the P57 summary."""
    assert P56_JSON.exists(), f"P56 JSON not found: {P56_JSON}"

    sources = summary.get("source_artifacts", {})
    assert "p56" in sources, "source_artifacts must include p56 key"

    recap = summary.get("p56_policy_recap", {})
    assert recap, "p57 summary must include p56_policy_recap"
    assert recap.get("final_p56_classification") == "P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC"

    # Sep 2025 mid-band data from P56 must be preserved
    sep = recap.get("sep_2025_mid_band", {})
    assert sep.get("n") == 27
    assert sep.get("sample_tier") == "BAND_SAMPLE_INSUFFICIENT"
    assert sep.get("annotation") == "SAMPLE_SENSITIVE_BAND_ANOMALY"


# ---------------------------------------------------------------------------
# T02 — P57 JSON exists and contains all required top-level sections
# ---------------------------------------------------------------------------
def test_t02_required_sections(summary: dict) -> None:
    """P57 JSON must contain all required top-level sections."""
    missing = REQUIRED_TOP_LEVEL_KEYS - set(summary.keys())
    assert not missing, f"P57 JSON missing top-level keys: {missing}"


# ---------------------------------------------------------------------------
# T03 — Annotation metadata schema contains required fields
# ---------------------------------------------------------------------------
def test_t03_annotation_schema_fields(summary: dict) -> None:
    """Annotation metadata schema must contain all 17 required fields."""
    schema = summary.get("annotation_metadata_schema", {})
    assert schema, "annotation_metadata_schema is missing"

    fields = schema.get("fields", {})
    missing = REQUIRED_SCHEMA_FIELDS - set(fields.keys())
    assert not missing, f"Schema missing required fields: {missing}"

    # Each field must have type and description
    for name in REQUIRED_SCHEMA_FIELDS:
        field_def = fields[name]
        assert "type" in field_def, f"Field '{name}' missing 'type'"
        assert "description" in field_def, f"Field '{name}' missing 'description'"

    # Invariants must be defined
    invariants = schema.get("invariants", [])
    assert len(invariants) >= 3, f"Schema must have >= 3 invariants, got {len(invariants)}"

    # Key invariants must be present
    inv_text = " ".join(invariants).lower()
    assert "should_trigger_refit" in inv_text, "Invariants must mention should_trigger_refit"
    assert "should_change_thresholds" in inv_text, "Invariants must mention should_change_thresholds"
    assert "n < 30" in inv_text or "band_sample_insufficient" in inv_text, (
        "Invariants must reference n < 30 or BAND_SAMPLE_INSUFFICIENT constraint"
    )


# ---------------------------------------------------------------------------
# T04 — Sep 2025 mid-band annotation is carried forward
# ---------------------------------------------------------------------------
def test_t04_sep_carry_forward_exists(summary: dict) -> None:
    """Sep 2025 mid-band annotation must be carried forward as BandAnnotationRecord."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf, "sep_2025_mid_band_annotation_carry_forward is missing"

    assert cf.get("record_type") == "BandAnnotationRecord"
    assert cf.get("annotation_scope") == "BAND_LEVEL"
    assert cf.get("metric_family") == "CALIBRATION"
    assert "1.00" in cf.get("band_label", ""), f"band_label should reference 1.00: {cf.get('band_label')}"
    assert cf.get("carry_forward_status") == "ACTIVE_TRACK_ONLY"

    # Source traceability
    assert "p55" in cf.get("p55_reference", "").lower()
    assert "p56" in cf.get("p56_reference", "").lower()

    # Required boolean fields
    assert cf.get("future_evidence_required") is True


# ---------------------------------------------------------------------------
# T05 — n=27 remains BAND_SAMPLE_INSUFFICIENT
# ---------------------------------------------------------------------------
def test_t05_n27_remains_insufficient(summary: dict) -> None:
    """Sep 2025 mid-band carry-forward must show n=27 as BAND_SAMPLE_INSUFFICIENT."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf.get("band_n") == 27, f"band_n expected 27, got {cf.get('band_n')}"
    assert cf.get("sample_tier") == "BAND_SAMPLE_INSUFFICIENT", (
        f"sample_tier expected BAND_SAMPLE_INSUFFICIENT, got {cf.get('sample_tier')}"
    )
    assert cf.get("cumulative_band_n") == 27


# ---------------------------------------------------------------------------
# T06 — Action remains TRACK_ONLY_NO_REFIT
# ---------------------------------------------------------------------------
def test_t06_action_track_only(summary: dict) -> None:
    """Action in carry-forward must be TRACK_ONLY_NO_REFIT."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf.get("action") == "TRACK_ONLY_NO_REFIT", (
        f"Expected TRACK_ONLY_NO_REFIT, got {cf.get('action')}"
    )
    assert cf.get("annotation") == "SAMPLE_SENSITIVE_BAND_ANOMALY"


# ---------------------------------------------------------------------------
# T07 — should_trigger_refit equals False
# ---------------------------------------------------------------------------
def test_t07_no_refit(summary: dict) -> None:
    """should_trigger_refit must be False in the carry-forward record."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf.get("should_trigger_refit") is False, (
        f"should_trigger_refit must be False, got {cf.get('should_trigger_refit')}"
    )

    # Schema invariant must also prohibit refit at n<30
    schema = summary.get("annotation_metadata_schema", {})
    refit_field = schema.get("fields", {}).get("should_trigger_refit", {})
    constraint = refit_field.get("constraint", "")
    assert "30" in constraint or "n < 30" in constraint, (
        f"should_trigger_refit field must reference n < 30 constraint: {constraint}"
    )


# ---------------------------------------------------------------------------
# T08 — should_change_thresholds equals False
# ---------------------------------------------------------------------------
def test_t08_no_threshold_change(summary: dict) -> None:
    """should_change_thresholds must be False in the carry-forward record."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf.get("should_change_thresholds") is False, (
        f"should_change_thresholds must be False, got {cf.get('should_change_thresholds')}"
    )

    # Schema must declare constraint
    schema = summary.get("annotation_metadata_schema", {})
    thresh_field = schema.get("fields", {}).get("should_change_thresholds", {})
    constraint = thresh_field.get("constraint", "")
    assert "false" in constraint.lower() or "must" in constraint.lower(), (
        f"should_change_thresholds field must have a 'false' constraint: {constraint}"
    )


# ---------------------------------------------------------------------------
# T09 — should_change_global_status equals False
# ---------------------------------------------------------------------------
def test_t09_no_global_status_change(summary: dict) -> None:
    """should_change_global_status must be False for BAND_SAMPLE_INSUFFICIENT."""
    cf = summary.get("sep_2025_mid_band_annotation_carry_forward", {})
    assert cf.get("should_change_global_status") is False, (
        f"should_change_global_status must be False, got {cf.get('should_change_global_status')}"
    )

    # Separation rules must confirm this
    sep = summary.get("global_vs_band_status_separation", {})
    global_status = sep.get("current_global_status", {})
    assert global_status.get("band_annotations_affect_global_status") is False, (
        "band_annotations_affect_global_status must be False"
    )


# ---------------------------------------------------------------------------
# T10 — Global vs band status separation rules exist
# ---------------------------------------------------------------------------
def test_t10_separation_rules(summary: dict) -> None:
    """Global vs band status separation must define at least 5 rules."""
    sep = summary.get("global_vs_band_status_separation", {})
    assert sep, "global_vs_band_status_separation is missing"

    rules = sep.get("rules", [])
    assert len(rules) >= 5, f"Expected >= 5 separation rules, got {len(rules)}"

    rule_ids = [r.get("rule_id") for r in rules]
    for expected_id in ["SEP01", "SEP02", "SEP03", "SEP04", "SEP05"]:
        assert expected_id in rule_ids, f"Missing separation rule {expected_id}"

    # SEP04 must mention n < 30 cannot trigger refit
    sep04 = next(r for r in rules if r.get("rule_id") == "SEP04")
    rule_text = (sep04.get("rule", "") + sep04.get("implication", "")).lower()
    assert "refit" in rule_text or "30" in rule_text, (
        f"SEP04 must mention refit and n<30: {rule_text}"
    )

    # SEP05 must mention thresholds
    sep05 = next(r for r in rules if r.get("rule_id") == "SEP05")
    rule_text = (sep05.get("rule", "") + sep05.get("implication", "")).lower()
    assert "threshold" in rule_text, f"SEP05 must mention threshold: {rule_text}"


# ---------------------------------------------------------------------------
# T11 — P52 compatibility statement exists
# ---------------------------------------------------------------------------
def test_t11_p52_compatibility(summary: dict) -> None:
    """P52 V2 compatibility statement must exist with required content."""
    compat = summary.get("p52_v2_compatibility", {})
    assert compat, "p52_v2_compatibility is missing"

    stmt = compat.get("statement", "")
    assert "not supersede" in stmt.lower() or "does not supersede" in stmt.lower(), (
        f"Compatibility statement must say P57 does not supersede P52: {stmt}"
    )
    assert "thresholds" in stmt.lower() or "threshold" in stmt.lower(), (
        f"Statement must mention thresholds: {stmt}"
    )

    details = compat.get("details", [])
    assert len(details) >= 5, f"Compatibility details must have >= 5 items, got {len(details)}"

    assert compat.get("p52_threshold_status") == "UNCHANGED"
    assert compat.get("p52_artifact_status") == "PRESERVED"
    assert compat.get("p53_artifact_status") == "PRESERVED"
    assert compat.get("p54_artifact_status") == "PRESERVED"
    assert compat.get("p55_artifact_status") == "PRESERVED"
    assert compat.get("p56_artifact_status") == "PRESERVED"

    platt_status = compat.get("platt_constants_status", "")
    assert "UNCHANGED" in platt_status or "unchanged" in platt_status.lower()


# ---------------------------------------------------------------------------
# T12 — Governance flags exist and match required values
# ---------------------------------------------------------------------------
def test_t12_governance_flags(summary: dict) -> None:
    """All governance flags must be present and correct."""
    gov = summary.get("governance_flags", {})
    required = {
        "paper_only": True,
        "diagnostic_only": True,
        "promotion_freeze": True,
        "kelly_deploy_allowed": False,
        "live_api_calls": 0,
        "tsl_crawler_modified": False,
        "champion_strategy_changed": False,
        "production_usage_proposed": False,
        "runtime_recommendation_logic_changed": False,
        "platt_constants_modified": False,
        "p52_contract_overwritten": False,
        "p53_artifact_overwritten": False,
        "p54_artifact_overwritten": False,
        "p55_artifact_overwritten": False,
        "p56_artifact_overwritten": False,
        "p52_thresholds_changed": False,
    }
    for key, expected in required.items():
        assert key in gov, f"governance_flags missing key: {key}"
        assert gov[key] == expected, (
            f"governance_flags.{key} expected {expected}, got {gov[key]}"
        )


# ---------------------------------------------------------------------------
# T13 — live_api_calls equals 0
# ---------------------------------------------------------------------------
def test_t13_live_api_calls_zero(summary: dict) -> None:
    """live_api_calls must be exactly 0."""
    gov = summary.get("governance_flags", {})
    assert gov.get("live_api_calls") == 0


# ---------------------------------------------------------------------------
# T14 — runtime_recommendation_logic_changed equals False
# ---------------------------------------------------------------------------
def test_t14_runtime_logic_unchanged(summary: dict) -> None:
    """runtime_recommendation_logic_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("runtime_recommendation_logic_changed") is False


# ---------------------------------------------------------------------------
# T15 — platt_constants_modified equals False
# ---------------------------------------------------------------------------
def test_t15_platt_constants_not_modified(summary: dict) -> None:
    """platt_constants_modified must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("platt_constants_modified") is False


# ---------------------------------------------------------------------------
# T16 — p52_thresholds_changed equals False
# ---------------------------------------------------------------------------
def test_t16_p52_thresholds_unchanged(summary: dict) -> None:
    """p52_thresholds_changed must be False."""
    gov = summary.get("governance_flags", {})
    assert gov.get("p52_thresholds_changed") is False


# ---------------------------------------------------------------------------
# T17 — p52/p53/p54/p55/p56 overwrite flags are False
# ---------------------------------------------------------------------------
def test_t17_no_artifact_overwrite(summary: dict) -> None:
    """No prior artifact must be overwritten."""
    gov = summary.get("governance_flags", {})
    for flag in [
        "p52_contract_overwritten",
        "p53_artifact_overwritten",
        "p54_artifact_overwritten",
        "p55_artifact_overwritten",
        "p56_artifact_overwritten",
    ]:
        assert gov.get(flag) is False, f"{flag} must be False, got {gov.get(flag)}"

    # Verify actual files still exist and are readable
    for json_path in [
        ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
        ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json",
        ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json",
    ]:
        assert json_path.exists(), f"Artifact was deleted or moved: {json_path.name}"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data, f"Artifact appears empty: {json_path.name}"


# ---------------------------------------------------------------------------
# T18 — JSON contains no deployment-readiness classification
# ---------------------------------------------------------------------------
def test_t18_no_deployment_classification(summary: dict) -> None:
    """Final P57 classification must not imply deployment readiness."""
    clf = summary.get("final_p57_classification", "")
    for forbidden in FORBIDDEN_CLASSIFICATIONS:
        assert forbidden not in clf, (
            f"Forbidden classification fragment '{forbidden}' found in '{clf}'"
        )
    allowed = {
        "P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC",
        "P57_ANNOTATION_INTEGRATION_INCOMPLETE",
        "P57_BLOCKED_BY_SOURCE_MISSING",
    }
    assert clf in allowed, (
        f"Final classification '{clf}' is not in the allowed set: {allowed}"
    )


# ---------------------------------------------------------------------------
# T19 — Reports contain no affirmative production or profit claims
# ---------------------------------------------------------------------------
def test_t19_reports_no_production_claims() -> None:
    """Reports must not contain affirmative production or profit claims."""
    for report_path in [REPORT_MD, BETTING_PLAN_MD]:
        assert report_path.exists(), f"Report not found: {report_path}"
        text = report_path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_REPORT_PHRASES:
            assert phrase.lower() not in text, (
                f"Forbidden phrase '{phrase}' found in {report_path.name}"
            )


# ---------------------------------------------------------------------------
# T20 — active_task.md references final P57 classification
# ---------------------------------------------------------------------------
def test_t20_active_task_references_p57(summary: dict) -> None:
    """active_task.md must reference the final P57 classification."""
    assert ACTIVE_TASK_MD.exists(), f"active_task.md not found: {ACTIVE_TASK_MD}"
    content = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    clf = summary.get("final_p57_classification", "")
    assert clf in content, (
        f"active_task.md must reference '{clf}' but it was not found"
    )
    assert "P57" in content, "active_task.md must reference P57"
    # Verify prior history is preserved (prepend pattern)
    assert "P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC" in content, (
        "active_task.md must still reference P56 classification (history preserved)"
    )
    assert "P55_INCONCLUSIVE_SAMPLE_LIMITED" in content, (
        "active_task.md must still reference P55 classification (history preserved)"
    )
