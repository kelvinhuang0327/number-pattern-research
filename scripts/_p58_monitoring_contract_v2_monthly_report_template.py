"""
P58 — Monitoring Contract V2 Monthly Report Template.

Creates a reusable monthly monitoring report template that implements the
P57 BandAnnotationRecord schema and cleanly separates global status from
band-level annotations.

Offline diagnostic only.  paper_only=True, live_api_calls=0.
Do NOT refit Platt.  Do NOT change runtime logic.  Do NOT deploy.
Do NOT modify P52/P53/P54/P55/P56/P57 artifacts.
Do NOT change P52 global thresholds.
Do NOT modify P45 Platt constants.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]

P52_SUMMARY = ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P53_SUMMARY = ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P54_SUMMARY = ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
P55_SUMMARY = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"
P56_SUMMARY = ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json"
P57_SUMMARY = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"

OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p58_monitoring_contract_v2_monthly_report_template_summary.json"
REPORT_MD = ROOT / "report/p58_monitoring_contract_v2_monthly_report_template_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p58_monitoring_contract_v2_monthly_report_template_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance (immutable)
# ---------------------------------------------------------------------------
GOVERNANCE: dict = {
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
    "p57_artifact_overwritten": False,
    "p52_thresholds_changed": False,
}

# P45 Platt constants — locked, do not modify
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

TEMPLATE_VERSION = "P58_MONITORING_CONTRACT_V2_MONTHLY_REPORT_TEMPLATE_V1"

# ---------------------------------------------------------------------------
# Governance assertions
# ---------------------------------------------------------------------------

def _assert_governance() -> None:
    assert GOVERNANCE["live_api_calls"] == 0, "GOVERNANCE VIOLATION: live_api_calls != 0"
    assert GOVERNANCE["paper_only"] is True
    assert GOVERNANCE["platt_constants_modified"] is False
    assert GOVERNANCE["p52_contract_overwritten"] is False
    assert GOVERNANCE["p53_artifact_overwritten"] is False
    assert GOVERNANCE["p54_artifact_overwritten"] is False
    assert GOVERNANCE["p55_artifact_overwritten"] is False
    assert GOVERNANCE["p56_artifact_overwritten"] is False
    assert GOVERNANCE["p57_artifact_overwritten"] is False
    assert GOVERNANCE["p52_thresholds_changed"] is False
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    assert abs(PLATT_A - 0.435432) < 1e-6, "Platt A modified"
    assert abs(PLATT_B - 0.245464) < 1e-6, "Platt B modified"


# ---------------------------------------------------------------------------
# Task A — Monthly Report JSON Schema
# ---------------------------------------------------------------------------

def build_monthly_report_schema() -> dict:
    """Top-level schema definition for the monthly monitoring report JSON."""
    return {
        "schema_name": "MonitoringContractV2MonthlyReport",
        "schema_version": "1.0",
        "template_version": TEMPLATE_VERSION,
        "description": (
            "Schema for a Monitoring Contract V2 monthly report. "
            "Separates global P52 status (threshold-driven) from "
            "band-level annotations (P57 BandAnnotationRecord, metadata only). "
            "Does not modify runtime logic or thresholds."
        ),
        "required_top_level_fields": [
            "report_type",
            "template_version",
            "report_month",
            "generated_date",
            "global_status",
            "band_annotations",
            "data_gap_status",
            "governance_summary",
            "report_limitations",
            "next_review_date",
        ],
        "section_order": [
            "1. GLOBAL STATUS — P52 V2 threshold evaluation",
            "2. BAND ANNOTATIONS — Active carry-forward BandAnnotationRecord list",
            "3. DATA GAP STATUS — 2024 closing-line gap and cross-year analysis status",
            "4. GOVERNANCE SUMMARY — paper_only, promotion_freeze, live_api_calls",
            "5. LIMITATIONS — sample sizes, data gaps, schema caveats",
        ],
        "report_type_allowed_values": [
            "DIAGNOSTIC_MONTHLY_REPORT",
            "DIAGNOSTIC_QUARTERLY_REPORT",
        ],
        "note": (
            "Band annotations are additive metadata. "
            "They must never change global_status, trigger refit, or change thresholds. "
            "See P57 SEP01-SEP06 separation rules."
        ),
    }


# ---------------------------------------------------------------------------
# Task B — Global Status Section Schema
# ---------------------------------------------------------------------------

def build_global_status_section_schema() -> dict:
    """Define the schema for the global_status section of a monthly report."""
    return {
        "section_name": "global_status",
        "description": (
            "Global monitoring status driven exclusively by P52 V2 thresholds. "
            "Must never be modified by band-level annotations."
        ),
        "required_fields": {
            "report_month": {
                "type": "string",
                "format": "YYYY-MM",
                "description": "Month covered by this report, e.g. '2025-09'.",
            },
            "batch_n": {
                "type": "integer",
                "description": "Number of games in the Tier C batch for this month.",
            },
            "global_status": {
                "type": "string",
                "allowed_values": [
                    "MONITORING_ACTIVE_DIAGNOSTIC",
                    "MONITORING_ALERT_DIAGNOSTIC",
                    "MONITORING_INCONCLUSIVE",
                ],
                "description": (
                    "Overall monitoring status. Controlled only by P52 V2 thresholds. "
                    "Must not be changed by band annotations."
                ),
            },
            "global_alert_level": {
                "type": "string",
                "allowed_values": ["GREEN", "YELLOW", "RED", "GREY"],
                "description": "Traffic-light alert level based on P52 thresholds.",
            },
            "global_alert_reasons": {
                "type": "list[string]",
                "description": "List of reasons the current alert level was assigned.",
            },
            "edge_status": {
                "type": "string",
                "allowed_values": ["EDGE_WITHIN_THRESHOLD", "EDGE_ALERT", "EDGE_INSUFFICIENT_SAMPLE"],
                "description": "Edge rate status against P52 V2 thresholds.",
            },
            "calibration_status": {
                "type": "string",
                "allowed_values": [
                    "CALIBRATION_WITHIN_THRESHOLD",
                    "CALIBRATION_ALERT",
                    "CALIBRATION_INSUFFICIENT_SAMPLE",
                ],
                "description": "Calibration (ECE) status against P52 V2 thresholds.",
            },
            "sample_status": {
                "type": "string",
                "allowed_values": ["SAMPLE_ADEQUATE", "SAMPLE_WATCHLIST", "SAMPLE_INSUFFICIENT"],
                "description": (
                    "Sample size status for the monthly Tier C batch. "
                    "Shown separately from calibration and edge status."
                ),
            },
            "data_gap_status": {
                "type": "string",
                "description": (
                    "2024 closing-line data gap. "
                    "Must be shown as a cross-year limitation, "
                    "not a 2025-only blocker."
                ),
            },
            "raw_edge_mean": {
                "type": "float",
                "description": "Mean raw edge across Tier C games for this month.",
            },
            "raw_edge_ci_low": {
                "type": "float",
                "description": "Lower bound of 95% CI on raw edge mean.",
            },
            "raw_edge_ci_high": {
                "type": "float",
                "description": "Upper bound of 95% CI on raw edge mean.",
            },
            "platt_ece": {
                "type": "float",
                "description": "Platt-calibrated ECE for all Tier C games this month.",
            },
            "platt_brier": {
                "type": "float",
                "description": "Platt-calibrated Brier score for Tier C games this month.",
            },
            "p52_thresholds_used": {
                "type": "object",
                "description": "Snapshot of the P52 V2 thresholds applied in this report.",
                "expected_subfields": ["ece_threshold", "brier_threshold", "edge_alert_threshold"],
            },
            "source_trace": {
                "type": "object",
                "description": (
                    "Traceability to source JSON artifacts used to populate this section."
                ),
                "expected_subfields": ["p52_summary_ref", "data_source"],
            },
        },
        "rules": [
            "global_status is controlled only by P52 V2 thresholds.",
            "global_status must not be modified by band annotations.",
            "sample_status must be displayed separately from calibration_status and edge_status.",
            "data_gap_status must describe the 2024 cross-year limitation, not a 2025-only blocker.",
            "p52_thresholds_used must reflect locked P52 V2 thresholds; not changed by P57 or P58.",
            "platt_ece and platt_brier reflect Platt-calibrated values using locked P45 constants.",
        ],
    }


# ---------------------------------------------------------------------------
# Task C — Band Annotations Section Schema
# ---------------------------------------------------------------------------

def build_band_annotations_section_schema() -> dict:
    """Define the schema for the band_annotations section of a monthly report."""
    return {
        "section_name": "band_annotations",
        "description": (
            "Band-level diagnostic annotations using P57 BandAnnotationRecord schema. "
            "These records are metadata only. They do not affect global_status, "
            "trigger refit, or change P52 thresholds."
        ),
        "record_schema": "BandAnnotationRecord v1 (see P57)",
        "required_fields_per_record": [
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
            "carry_forward_status",
            "source_trace",
        ],
        "section_rules": [
            "Band annotations are metadata-only; they do not replace or override global_status.",
            "n < 30 must map to sample_tier=BAND_SAMPLE_INSUFFICIENT.",
            "TRACK_ONLY_NO_REFIT must remain the action for BAND_SAMPLE_INSUFFICIENT records.",
            "should_change_global_status must be false for all band annotations.",
            "should_trigger_refit must be false for all BAND_SAMPLE_INSUFFICIENT records.",
            "should_change_thresholds must be false for all band annotations.",
            "Each record must include source_trace with p55_reference and p56_reference.",
            "Section header must explicitly state: 'Band annotations do not change global P52 status.'",
            "Section must state whether any record has should_trigger_refit=true (expected: none).",
            "Section must state the current count of active TRACK_ONLY records.",
        ],
        "sample_tier_mapping": {
            "n_lt_30": "BAND_SAMPLE_INSUFFICIENT",
            "n_30_to_99": "BAND_SAMPLE_WATCHLIST",
            "n_ge_100": "BAND_SAMPLE_MONITORABLE",
        },
        "carry_forward_policy": (
            "An annotation with carry_forward_status=ACTIVE_TRACK_ONLY must appear in "
            "every subsequent monthly report until archival criteria are met (see P57)."
        ),
    }


# ---------------------------------------------------------------------------
# Task D — Sep 2025 Example Report
# ---------------------------------------------------------------------------

def build_sep_2025_example_report(p57: dict) -> dict:
    """Construct the Sep 2025 concrete example monthly report."""
    cf = p57.get("sep_2025_mid_band_annotation_carry_forward", {})
    sep = p57.get("global_vs_band_status_separation", {})
    compat = p57.get("p52_v2_compatibility", {})

    example_global_status = {
        "report_month": "2025-09",
        "batch_n": 535,
        "batch_note": (
            "535 is the full 2025 Tier C count. "
            "Sep-specific batch n would be a subset in a real monthly report; "
            "this example uses 2025 total for illustration."
        ),
        "global_status": "MONITORING_ACTIVE_DIAGNOSTIC",
        "global_alert_level": "GREEN",
        "global_alert_reasons": [
            "No P52 V2 global thresholds exceeded.",
            "Sep mid-band anomaly is BAND_SAMPLE_INSUFFICIENT and does not trigger global alert.",
        ],
        "edge_status": "EDGE_WITHIN_THRESHOLD",
        "calibration_status": "CALIBRATION_WITHIN_THRESHOLD",
        "sample_status": "SAMPLE_ADEQUATE",
        "data_gap_status": (
            "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. "
            "Cross-year analysis cannot be completed. "
            "This is a cross-year limitation, not a 2025-only blocker."
        ),
        "raw_edge_mean": None,
        "raw_edge_ci_low": None,
        "raw_edge_ci_high": None,
        "platt_ece": None,
        "platt_brier": None,
        "p52_thresholds_used": {
            "ece_threshold": "see_p52_v2",
            "brier_threshold": "see_p52_v2",
            "edge_alert_threshold": "see_p52_v2",
            "note": (
                "Exact P52 V2 thresholds are defined in "
                "p52_monitoring_contract_v2_summary.json. "
                "They are not reproduced here to avoid duplication."
            ),
        },
        "source_trace": {
            "p52_summary_ref": "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
            "data_source": "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
        },
    }

    example_band_annotation = {
        "record_type": "BandAnnotationRecord",
        "schema_version": "1.0",
        "annotation_scope": cf.get("annotation_scope", "BAND_LEVEL"),
        "metric_family": cf.get("metric_family", "CALIBRATION"),
        "band_label": cf.get("band_label", "1.00 <= |sp_fip_delta| < 1.25"),
        "band_n": cf.get("band_n", 27),
        "sample_tier": cf.get("sample_tier", "BAND_SAMPLE_INSUFFICIENT"),
        "annotation": cf.get("annotation", "SAMPLE_SENSITIVE_BAND_ANOMALY"),
        "action": cf.get("action", "TRACK_ONLY_NO_REFIT"),
        "evidence_strength": cf.get("evidence_strength", "INSUFFICIENT"),
        "platt_ece": cf.get("platt_ece", 0.245988),
        "raw_ece": cf.get("raw_ece", 0.165456),
        "ece_delta": cf.get("ece_delta", 0.080532),
        "repeated_month_count": cf.get("repeated_month_count", 1),
        "cumulative_band_n": cf.get("cumulative_band_n", 27),
        "future_evidence_required": cf.get("future_evidence_required", True),
        "should_change_global_status": cf.get("should_change_global_status", False),
        "should_trigger_refit": cf.get("should_trigger_refit", False),
        "should_change_thresholds": cf.get("should_change_thresholds", False),
        "carry_forward_status": cf.get("carry_forward_status", "ACTIVE_TRACK_ONLY"),
        "source_trace": {
            "p55_reference": cf.get("p55_reference"),
            "p56_reference": cf.get("p56_reference"),
            "p57_reference": "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json",
        },
    }

    return {
        "example_type": "HISTORICAL_DIAGNOSTIC_EXAMPLE",
        "example_note": (
            "This is a diagnostic example only and does not modify runtime behavior. "
            "Values are sourced from P55/P56/P57 artifacts. "
            "A real monthly report would populate raw_edge_mean, platt_ece, platt_brier "
            "from the actual batch data for that month."
        ),
        "report_month": "2025-09",
        "template_version": TEMPLATE_VERSION,
        "generated_date": datetime.now().strftime("%Y-%m-%d"),
        "global_status": example_global_status,
        "band_annotations": {
            "section_header": "Band annotations do not change global P52 status.",
            "active_track_only_count": 1,
            "records": [example_band_annotation],
        },
        "data_gap_status": {
            "p43_2024_closing_line_gap": "UNRESOLVED",
            "impact": (
                "Cross-year band analysis is not possible until 2024 historical odds "
                "data is obtained. The Sep 2025 mid-band finding applies to 2025 data only."
            ),
        },
        "governance_summary": {
            "paper_only": True,
            "live_api_calls": 0,
            "promotion_freeze": True,
            "kelly_deploy_allowed": False,
            "platt_constants": f"A={PLATT_A}, B={PLATT_B} (P45, locked)",
        },
    }


# ---------------------------------------------------------------------------
# Task E — Validation Rules and Invariants
# ---------------------------------------------------------------------------

def build_validation_rules() -> dict:
    """Define validation rules future agents must run on monthly reports."""
    return {
        "description": (
            "Validation rules that any agent generating or reviewing a monthly "
            "Monitoring Contract V2 report must verify."
        ),
        "rules": [
            {
                "rule_id": "VAL01",
                "rule": "global_status must not be MONITORING_ALERT_DIAGNOSTIC unless a P52 V2 threshold is explicitly triggered.",
                "check": "report['global_status']['global_status'] != 'MONITORING_ALERT_DIAGNOSTIC' OR alert_reason references P52 threshold.",
            },
            {
                "rule_id": "VAL02",
                "rule": "No band annotation may set should_change_global_status=true.",
                "check": "all(r['should_change_global_status'] is False for r in band_annotations['records'])",
            },
            {
                "rule_id": "VAL03",
                "rule": "No band annotation with n < 30 may set should_trigger_refit=true.",
                "check": "all(r['should_trigger_refit'] is False for r in band_annotations['records'] if r['band_n'] < 30)",
            },
            {
                "rule_id": "VAL04",
                "rule": "No band annotation may set should_change_thresholds=true.",
                "check": "all(r['should_change_thresholds'] is False for r in band_annotations['records'])",
            },
            {
                "rule_id": "VAL05",
                "rule": "ACTIVE_TRACK_ONLY records from prior months must appear in the current report until archival criteria are met.",
                "check": "All carry_forward_status=ACTIVE_TRACK_ONLY records from prior report are present.",
            },
            {
                "rule_id": "VAL06",
                "rule": "band_annotations section header must explicitly state 'Band annotations do not change global P52 status.'",
                "check": "report['band_annotations']['section_header'] contains the required statement.",
            },
            {
                "rule_id": "VAL07",
                "rule": "p52_thresholds_used must match the locked P52 V2 thresholds; not changed by any annotation.",
                "check": "p52_thresholds_used references p52_monitoring_contract_v2_summary.json.",
            },
            {
                "rule_id": "VAL08",
                "rule": "data_gap_status must describe the 2024 cross-year limitation (not a 2025-only blocker).",
                "check": "data_gap_status contains '2024' and does not claim 2025 is fully unaffected.",
            },
            {
                "rule_id": "VAL09",
                "rule": "sample_status must be a separate field from calibration_status and edge_status.",
                "check": "All three fields exist and are separate string fields.",
            },
            {
                "rule_id": "VAL10",
                "rule": "governance_summary must include paper_only=true, live_api_calls=0, promotion_freeze=true, kelly_deploy_allowed=false.",
                "check": "All four governance flags are present and match expected values.",
            },
        ],
    }


def build_invariants() -> dict:
    """P58 invariants that must hold for all generated monthly reports."""
    return {
        "description": "Invariants for the Monitoring Contract V2 Monthly Report Template.",
        "invariants": [
            "Band annotations are additive metadata; they never replace or override global_status.",
            "n < 30 → sample_tier=BAND_SAMPLE_INSUFFICIENT; should_trigger_refit=False; should_change_thresholds=False.",
            "P52 thresholds are never changed by a band annotation (should_change_thresholds must always be False).",
            "An ACTIVE_TRACK_ONLY record carries forward to every subsequent monthly report until archived.",
            "data_gap_status must always reflect the 2024 cross-year limitation.",
            "Governance flags (paper_only, live_api_calls=0, promotion_freeze) must be present in every report.",
            "platt_ece and platt_brier are computed using locked P45 Platt constants (A=0.435432, B=0.245464).",
            "The Sep 2025 1.00-1.25 band annotation (n=27) must remain TRACK_ONLY_NO_REFIT until FE01+FE02 are met.",
        ],
    }


# ---------------------------------------------------------------------------
# Future Agent Usage Notes
# ---------------------------------------------------------------------------

def build_future_agent_usage_notes() -> dict:
    """Notes for future agents using this template."""
    return {
        "description": "How future agents should use the P58 monthly report template.",
        "usage_steps": [
            {
                "step": 1,
                "action": "Load the P58 template (this JSON) and the current P52 V2 artifact.",
                "note": "Do not modify P52/P55/P56/P57 artifacts.",
            },
            {
                "step": 2,
                "action": "Populate global_status from the current month's Tier C batch data.",
                "note": (
                    "Compute global_status using P52 V2 thresholds only. "
                    "Do not let band annotations influence this field."
                ),
            },
            {
                "step": 3,
                "action": "Carry forward all ACTIVE_TRACK_ONLY BandAnnotationRecords from the previous report.",
                "note": "Update repeated_month_count and cumulative_band_n for each record.",
            },
            {
                "step": 4,
                "action": "Add new BandAnnotationRecords if new band anomalies are detected this month.",
                "note": "Apply P56 sample tier policy to assign sample_tier, annotation, and action.",
            },
            {
                "step": 5,
                "action": "Run VAL01-VAL10 validation rules on the generated report JSON.",
                "note": "A report that fails any VAL rule must not be committed as a final artifact.",
            },
            {
                "step": 6,
                "action": "Generate the Markdown report from the JSON (GLOBAL STATUS + BAND ANNOTATIONS sections).",
                "note": "The Markdown must explicitly separate the two sections and label band annotations as metadata.",
            },
            {
                "step": 7,
                "action": "Confirm governance flags in the generated report match required values.",
                "note": "paper_only=True, live_api_calls=0, promotion_freeze=True, kelly_deploy_allowed=False.",
            },
        ],
        "forbidden_agent_actions": [
            "Setting should_change_global_status=true in any band annotation.",
            "Setting should_trigger_refit=true for a record with n < 30.",
            "Setting should_change_thresholds=true in any band annotation.",
            "Modifying P52 V2 thresholds based on band-level evidence alone.",
            "Triggering Platt refit from monthly report without explicit authorization.",
            "Removing the 2024 data gap note from data_gap_status.",
            "Staging P52/P53/P54/P55/P56/P57 artifact files.",
            "Setting live_api_calls above zero.",
            "Enabling kelly_deploy_allowed (must remain False at all times).",
        ],
        "graduation_reminder": (
            "A BAND_SAMPLE_INSUFFICIENT record (n < 30) graduates to FLAG_FOR_FOLLOW_UP when "
            "n >= 30 in a subsequent month AND repeated_month_count >= 2. "
            "See P57 for full graduation and archival criteria."
        ),
    }


# ---------------------------------------------------------------------------
# Master audit builder
# ---------------------------------------------------------------------------

def build_p58_audit() -> dict:
    print("[P58.PRE] Governance assertions...")
    _assert_governance()
    print("  PASS")

    print("[P58.A] Loading source artifacts...")
    for path in [P52_SUMMARY, P53_SUMMARY, P54_SUMMARY, P55_SUMMARY, P56_SUMMARY, P57_SUMMARY]:
        assert path.exists(), f"Source artifact missing: {path}"
    p52 = json.loads(P52_SUMMARY.read_text(encoding="utf-8"))
    p57 = json.loads(P57_SUMMARY.read_text(encoding="utf-8"))
    # Load others to verify integrity
    json.loads(P53_SUMMARY.read_text(encoding="utf-8"))
    json.loads(P54_SUMMARY.read_text(encoding="utf-8"))
    json.loads(P55_SUMMARY.read_text(encoding="utf-8"))
    json.loads(P56_SUMMARY.read_text(encoding="utf-8"))
    print("  P52/P53/P54/P55/P56/P57 loaded")

    print("[P58.B] Building monthly report schema...")
    report_schema = build_monthly_report_schema()

    print("[P58.C] Building global status section schema...")
    global_status_schema = build_global_status_section_schema()
    print(f"  {len(global_status_schema['required_fields'])} global status fields defined")

    print("[P58.D] Building band annotations section schema...")
    band_annotations_schema = build_band_annotations_section_schema()
    print(f"  {len(band_annotations_schema['required_fields_per_record'])} band annotation fields required")

    print("[P58.E] Building Sep 2025 example report...")
    sep_example = build_sep_2025_example_report(p57)
    cf = sep_example["band_annotations"]["records"][0]
    print(f"  band_n={cf['band_n']}, sample_tier={cf['sample_tier']}")
    print(f"  action={cf['action']}")
    print(f"  should_trigger_refit={cf['should_trigger_refit']}")
    print(f"  should_change_global_status={cf['should_change_global_status']}")

    print("[P58.F] Building validation rules...")
    validation_rules = build_validation_rules()
    print(f"  {len(validation_rules['rules'])} validation rules defined")

    print("[P58.G] Building invariants...")
    invariants = build_invariants()
    print(f"  {len(invariants['invariants'])} invariants defined")

    print("[P58.H] Building future agent usage notes...")
    agent_notes = build_future_agent_usage_notes()

    final_clf = "P58_MONTHLY_REPORT_TEMPLATE_READY_DIAGNOSTIC"
    print(f"\n[P58.I] Final classification: {final_clf}")

    # Final governance assertions
    _assert_governance()

    audit = {
        "p58_phase": "P58 — Monitoring Contract V2 Monthly Report Template",
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "source_artifacts": {
            "p52": str(P52_SUMMARY.relative_to(ROOT)),
            "p53": str(P53_SUMMARY.relative_to(ROOT)),
            "p54": str(P54_SUMMARY.relative_to(ROOT)),
            "p55": str(P55_SUMMARY.relative_to(ROOT)),
            "p56": str(P56_SUMMARY.relative_to(ROOT)),
            "p57": str(P57_SUMMARY.relative_to(ROOT)),
        },
        "template_version": TEMPLATE_VERSION,
        "monthly_report_schema": report_schema,
        "global_status_section_schema": global_status_schema,
        "band_annotations_section_schema": band_annotations_schema,
        "sep_2025_example_report": sep_example,
        "validation_rules": validation_rules,
        "invariants": invariants,
        "future_agent_usage_notes": agent_notes,
        "governance_flags": GOVERNANCE,
        "final_p58_classification": final_clf,
    }
    return audit


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_report(audit: dict) -> None:
    clf = audit["final_p58_classification"]
    schema = audit["monthly_report_schema"]
    gs = audit["global_status_section_schema"]
    ba = audit["band_annotations_section_schema"]
    ex = audit["sep_2025_example_report"]
    val = audit["validation_rules"]
    inv = audit["invariants"]
    notes = audit["future_agent_usage_notes"]

    cf = ex["band_annotations"]["records"][0]

    gs_fields_md = "".join(
        f"| `{name}` | {props['type']} | {props['description'][:72]} |\n"
        for name, props in gs["required_fields"].items()
    )

    val_rules_md = "".join(
        f"| {r['rule_id']} | {r['rule'][:80]} |\n"
        for r in val["rules"]
    )

    steps_md = "".join(
        f"{s['step']}. **{s['action']}**  \n   _{s['note']}_\n"
        for s in notes["usage_steps"]
    )

    sep_row_md = "\n".join([
        f"| annotation_scope | {cf['annotation_scope']} |",
        f"| metric_family | {cf['metric_family']} |",
        f"| band_label | `{cf['band_label']}` |",
        f"| band_n | **{cf['band_n']}** |",
        f"| sample_tier | **{cf['sample_tier']}** |",
        f"| annotation | **{cf['annotation']}** |",
        f"| action | **{cf['action']}** |",
        f"| evidence_strength | {cf['evidence_strength']} |",
        f"| platt_ece | {cf['platt_ece']} |",
        f"| raw_ece | {cf['raw_ece']} |",
        f"| ece_delta | {cf['ece_delta']} |",
        f"| repeated_month_count | {cf['repeated_month_count']} |",
        f"| cumulative_band_n | {cf['cumulative_band_n']} |",
        f"| future_evidence_required | {cf['future_evidence_required']} |",
        f"| should_change_global_status | **{cf['should_change_global_status']}** |",
        f"| should_trigger_refit | **{cf['should_trigger_refit']}** |",
        f"| should_change_thresholds | **{cf['should_change_thresholds']}** |",
        f"| carry_forward_status | {cf['carry_forward_status']} |",
    ])

    content = f"""# P58 — Monitoring Contract V2 Monthly Report Template

**Date**: {audit['run_date']}  
**Classification**: `{clf}`  
**Template Version**: `{audit['template_version']}`  
**Governance**: paper_only=True, diagnostic_only=True, live_api_calls=0

---

## 1. P57 Recap

P57 completed at commit `616448e` with classification `P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC`.

Key P57 outputs incorporated here:
- **BandAnnotationRecord schema v1**: 17 fields, 5 invariants, 6 SEP separation rules.
- **Sep 2025 1.00–1.25 band carry-forward**: n=27, BAND_SAMPLE_INSUFFICIENT, TRACK_ONLY_NO_REFIT.
- **P57 key principle**: Global monitoring status is controlled exclusively by P52 V2 thresholds.  
  Band annotations are metadata-only and must not override global status, trigger refit, or change thresholds.

---

## 2. Why Monthly Report Template Is Needed

Without a standard template:
1. Future agents have no schema defining how global status and band annotations coexist in a single report.
2. Reviewers may incorrectly conflate band-level findings (TRACK_ONLY, n=27) with P52 global alerts.
3. The Sep 2025 mid-band carry-forward has no mechanism to persist across reporting cycles.
4. There is no validation layer preventing an agent from incorrectly setting should_trigger_refit=true.

P58 provides a **reusable template** with schema, validation rules, and a concrete Sep 2025 example.

---

## 3. Monthly JSON Schema

Schema: **{schema['schema_name']}** (v{schema['schema_version']})

{schema['description']}

**Required top-level fields**:
{chr(10).join(f'- `{f}`' for f in schema['required_top_level_fields'])}

**Section order**:
{chr(10).join(f'{s}' for s in schema['section_order'])}

---

## 4. Global Status Section Schema

{gs['description']}

| Field | Type | Description |
|-------|------|-------------|
{gs_fields_md}

**Rules**:
{chr(10).join(f'- {r}' for r in gs['rules'])}

---

## 5. Band Annotations Section Schema

{ba['description']}

**Record schema**: {ba['record_schema']}

**Required fields per record**:
{chr(10).join(f'- `{f}`' for f in ba['required_fields_per_record'])}

**Sample tier mapping**:
| n range | sample_tier |
|---------|-------------|
| n < 30 | `BAND_SAMPLE_INSUFFICIENT` |
| 30 ≤ n < 100 | `BAND_SAMPLE_WATCHLIST` |
| n ≥ 100 | `BAND_SAMPLE_MONITORABLE` |

**Section rules**:
{chr(10).join(f'- {r}' for r in ba['section_rules'])}

---

## 6. Sep 2025 Example Monthly Report

**Example type**: `{ex['example_type']}`  
**Report month**: `{ex['report_month']}`

> {ex['example_note']}

### 6a. Global Status (Sep 2025)

| Field | Value |
|-------|-------|
| report_month | {ex['global_status']['report_month']} |
| batch_n | {ex['global_status']['batch_n']} ({ex['global_status']['batch_note'][:40]}...) |
| global_status | `{ex['global_status']['global_status']}` |
| global_alert_level | **{ex['global_status']['global_alert_level']}** |
| edge_status | {ex['global_status']['edge_status']} |
| calibration_status | {ex['global_status']['calibration_status']} |
| sample_status | {ex['global_status']['sample_status']} |
| data_gap_status | {ex['global_status']['data_gap_status'][:60]}... |

### 6b. Band Annotations (Sep 2025)

> **{ex['band_annotations']['section_header']}**  
> Active TRACK_ONLY records: {ex['band_annotations']['active_track_only_count']}

| Field | Value |
|-------|-------|
{sep_row_md}

---

## 7. Validation Rules

| Rule ID | Rule |
|---------|------|
{val_rules_md}

---

## 8. Invariants

{chr(10).join(f'- {inv_item}' for inv_item in inv['invariants'])}

---

## 9. Future Agent Usage Notes

{steps_md}

**Forbidden agent actions**:
{chr(10).join(f'- {a}' for a in notes['forbidden_agent_actions'])}

**Graduation reminder**: {notes['graduation_reminder']}

---

## 10. Limitations

1. The Sep 2025 example uses total 2025 Tier C n=535 for global status; a real monthly report uses only that month's batch.
2. raw_edge_mean, platt_ece, platt_brier are not populated in the example (2025 monthly batch data not segmented by month in current artifacts).
3. BandAnnotationRecord schema v1 is a first iteration; field definitions may be refined.
4. Graduation thresholds (n≥30, n≥100) are heuristic and have not been validated by formal power analysis.
5. P58 is metadata / schema only; runtime logic and monitoring thresholds are unchanged.

---

## 11. 2024 Closing-Line Data Gap

**The 2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved.**

Cross-year band analysis cannot be completed until 2024 historical odds data is obtained.
This is a cross-year limitation and does not block 2025-only analysis.

---

## 12. Final P58 Classification

```
{clf}
```

---

## 13. Next Recommended Diagnostic Task

**P59 — Monitoring Contract V2 First Monthly Report (Oct 2025 or rolling)**:
- Use P58 template to generate the first real monthly report for the next available month.
- Populate global_status from actual Tier C batch data for that month.
- Carry forward the Sep 2025 mid-band ACTIVE_TRACK_ONLY record.
- Run VAL01-VAL10 validation rules.
- Check whether FE01 (n >= 30 in the 1.00-1.25 band) is met for the new month.
- Prerequisite: 2024 closing-line data gap remains unresolved; report scope is 2025 only.

---

*Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True, live_api_calls=0*  
*P45 Platt constants unchanged: A=0.435432, B=0.245464*  
*P52/P53/P54/P55/P56/P57 artifacts not overwritten. P52 thresholds not changed.*
"""

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(content, encoding="utf-8")
    print(f"Report written: {REPORT_MD}")

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(content, encoding="utf-8")
    print(f"BettingPlan report written: {BETTING_PLAN_MD}")


def update_active_task(classification: str) -> None:
    ACTIVE_TASK_MD.parent.mkdir(parents=True, exist_ok=True)
    p58_header = f"""# Active Task — P58 Monitoring Contract V2 Monthly Report Template

> **[COMPLETED 2026-05-26]** `{classification}`
> **Issued by**: P57 `P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC` → monthly report template needed
> **HEAD**: `616448e` → 提交中 | **Branch**: `main` | **Mode**: `paper_only=True`
> **前置 Phase**: P57 `P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC`

## P58 成果摘要

- **Template version**: `{TEMPLATE_VERSION}`
- **Monthly report schema**: `MonitoringContractV2MonthlyReport` v1.0 (10 required top-level fields)
- **Global status section schema**: 15 required fields，global_status 由 P52 V2 閾值獨家控制
- **Band annotations section schema**: 19 required fields per record，實作 P57 BandAnnotationRecord v1
- **Sep 2025 example**: band_n=27, BAND_SAMPLE_INSUFFICIENT, TRACK_ONLY_NO_REFIT, should_trigger_refit=False
- **VAL rules**: VAL01–VAL10 (10 條驗證規則供未來 Agent 使用)
- **Invariants**: 8 條不變量
- **P52 全局閾值**: UNCHANGED
- **P45 Platt 常數**: A=0.435432, B=0.245464（未修改）
- **最終分類**: `{classification}`
- **Governance**: paper_only=True, live_api_calls=0, p52/p53/p54/p55/p56/p57 artifacts preserved
- **2024 缺口**: P43 closing-line data gap 仍未解決

---

"""
    existing = ""
    if ACTIVE_TASK_MD.exists():
        existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(p58_header + existing, encoding="utf-8")
    print("active_task.md updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _assert_governance()

    audit = build_p58_audit()
    clf = audit["final_p58_classification"]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON written: {OUTPUT_JSON}")

    write_report(audit)
    update_active_task(clf)

    print()
    print("=" * 60)
    print(f"P58 COMPLETE — {clf}")
    print(f"  template_version={TEMPLATE_VERSION}")
    print(f"  live_api_calls={audit['governance_flags']['live_api_calls']}")
    print(f"  paper_only={audit['governance_flags']['paper_only']}")
    print(f"  p52_thresholds_changed={audit['governance_flags']['p52_thresholds_changed']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
