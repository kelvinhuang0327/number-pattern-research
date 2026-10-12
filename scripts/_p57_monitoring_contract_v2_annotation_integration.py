"""
P57 — Monitoring Contract V2 Annotation Integration.

Integrates P56 sample-sensitive band annotation policy into the P52 Monitoring
Contract V2 as a metadata / interpretive layer only.

Offline diagnostic only.  paper_only=True, live_api_calls=0.
Do NOT refit Platt.  Do NOT change runtime logic.  Do NOT deploy.
Do NOT modify P52/P53/P54/P55/P56 artifacts.
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

OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"
REPORT_MD = ROOT / "report/p57_monitoring_contract_v2_annotation_integration_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p57_monitoring_contract_v2_annotation_integration_20260526.md"
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
    "p52_thresholds_changed": False,
}

# P45 Platt constants — locked, do not modify
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# ---------------------------------------------------------------------------
# Governance assertions (called at start and end)
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
    assert GOVERNANCE["p52_thresholds_changed"] is False
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    assert abs(PLATT_A - 0.435432) < 1e-6, "Platt A modified"
    assert abs(PLATT_B - 0.245464) < 1e-6, "Platt B modified"


# ---------------------------------------------------------------------------
# Task A — P52 contract recap
# ---------------------------------------------------------------------------

def build_p52_contract_recap(p52: dict) -> dict:
    """Summarise the key P52 V2 monitoring contract details."""
    return {
        "contract_version": p52.get("contract_version", "v2"),
        "final_p52_classification": p52.get("final_p52_classification"),
        "global_status": "MONITORING_ACTIVE_DIAGNOSTIC",
        "thresholds_unchanged": True,
        "scope": (
            "Tier C games: |sp_fip_delta| >= 0.5, "
            "market_home_prob_no_vig in (0,1), home_win defined. "
            "Total n=535 (2025 season)."
        ),
        "tier_c_n": 535,
        "platt_a": PLATT_A,
        "platt_b": PLATT_B,
        "note": (
            "P52 owns global calibration monitoring. "
            "Band-level annotations (P56/P57) are metadata only. "
            "P57 does not add runtime monitoring or change P52 thresholds."
        ),
    }


# ---------------------------------------------------------------------------
# Task A — P56 policy recap
# ---------------------------------------------------------------------------

def build_p56_policy_recap(p56: dict) -> dict:
    """Summarise the P56 band annotation policy."""
    app = p56.get("p55_application", {})
    policy = p56.get("band_annotation_policy", {})
    return {
        "final_p56_classification": p56.get("final_p56_classification"),
        "policy_name": policy.get("policy_name"),
        "policy_version": policy.get("policy_version"),
        "tiers_defined": list(p56.get("sample_size_tiers", {}).keys()),
        "rules_count": len(p56.get("interpretation_rules", [])),
        "sep_2025_mid_band": {
            "band": app.get("band"),
            "n": app.get("n"),
            "sample_tier": app.get("sample_tier"),
            "annotation": app.get("annotation"),
            "action": app.get("action"),
            "platt_ece": app.get("platt_ece"),
            "raw_ece": app.get("raw_ece"),
            "ece_delta": app.get("ece_delta_platt_minus_raw"),
        },
    }


# ---------------------------------------------------------------------------
# Task B — Annotation Metadata Schema
# ---------------------------------------------------------------------------

def build_annotation_metadata_schema() -> dict:
    """Define schema for band-level annotation records in future monitoring reports."""
    return {
        "schema_name": "BandAnnotationRecord v1",
        "schema_version": "1.0",
        "description": (
            "Schema for attaching band-level diagnostic annotations to monitoring "
            "reports. These records are metadata only and do not affect P52 global "
            "monitoring status or runtime recommendation logic."
        ),
        "fields": {
            "annotation_scope": {
                "type": "string",
                "allowed_values": ["BAND_LEVEL", "GLOBAL_LEVEL"],
                "description": "Scope of the annotation; BAND_LEVEL for sp_fip_delta sub-bands.",
            },
            "metric_family": {
                "type": "string",
                "allowed_values": ["CALIBRATION", "EDGE_RATE", "BRIER_SCORE", "FEATURE_DRIFT"],
                "description": "Metric domain this annotation belongs to.",
            },
            "band_label": {
                "type": "string",
                "description": "Human-readable band definition, e.g. '1.00 <= |sp_fip_delta| < 1.25'.",
            },
            "band_n": {
                "type": "integer",
                "description": "Number of games in this band for the reporting period.",
            },
            "sample_tier": {
                "type": "string",
                "allowed_values": [
                    "BAND_SAMPLE_INSUFFICIENT",
                    "BAND_SAMPLE_WATCHLIST",
                    "BAND_SAMPLE_MONITORABLE",
                ],
                "description": "Sample size tier per P56 policy.",
            },
            "annotation": {
                "type": "string",
                "allowed_values": [
                    "SAMPLE_SENSITIVE_BAND_ANOMALY",
                    "BAND_WATCHLIST",
                    "BAND_DRIFT_CANDIDATE",
                    "STABLE_BAND_EVIDENCE",
                    "PLATT_BAND_DEGRADATION_NOTE",
                ],
                "description": "Annotation label for the band finding.",
            },
            "action": {
                "type": "string",
                "allowed_values": [
                    "TRACK_ONLY_NO_REFIT",
                    "FLAG_FOR_FOLLOW_UP",
                    "PROMOTE_TO_DRIFT_CANDIDATE_IF_CI_ELEVATED",
                ],
                "description": "Prescribed action from P56 policy.",
            },
            "evidence_strength": {
                "type": "string",
                "allowed_values": ["INSUFFICIENT", "PRELIMINARY", "MODERATE", "STRONG"],
                "description": "Evidence strength level for this annotation.",
            },
            "platt_ece": {
                "type": "float",
                "description": "Platt-calibrated ECE for this band in the reporting period.",
            },
            "raw_ece": {
                "type": "float",
                "description": "Raw (uncalibrated) model ECE for this band.",
            },
            "ece_delta": {
                "type": "float",
                "description": "platt_ece minus raw_ece. Positive = Platt worsened ECE in this band.",
            },
            "repeated_month_count": {
                "type": "integer",
                "description": "Number of separate months this band has shown elevated ECE.",
            },
            "cumulative_band_n": {
                "type": "integer",
                "description": "Total games in this band across all monitored months.",
            },
            "future_evidence_required": {
                "type": "boolean",
                "description": "Whether future evidence is required before any action escalation.",
            },
            "should_change_global_status": {
                "type": "boolean",
                "description": "Whether this annotation should change P52 global monitoring status.",
                "constraint": "MUST be false when sample_tier=BAND_SAMPLE_INSUFFICIENT.",
            },
            "should_trigger_refit": {
                "type": "boolean",
                "description": "Whether this annotation should trigger a model refit.",
                "constraint": "MUST be false when n < 30.",
            },
            "should_change_thresholds": {
                "type": "boolean",
                "description": "Whether this annotation should change P52 global thresholds.",
                "constraint": "MUST always be false for band-level annotations alone.",
            },
        },
        "invariants": [
            "should_change_global_status MUST be false when sample_tier=BAND_SAMPLE_INSUFFICIENT.",
            "should_trigger_refit MUST be false when n < 30.",
            "should_change_thresholds MUST be false for all band-level annotations.",
            "Band annotations are additive metadata only; they do not replace P52 status fields.",
            "Records must preserve trace to source phase (e.g., p55_reference, p56_reference).",
        ],
    }


# ---------------------------------------------------------------------------
# Task C — Global vs Band Status Separation
# ---------------------------------------------------------------------------

def build_global_vs_band_separation() -> dict:
    """Define explicit separation between P52 global status and band annotations."""
    return {
        "separation_principle": (
            "P52 global monitoring status is governed by P52 V2 thresholds. "
            "Band-level annotations (P56, P57) are diagnostic metadata only. "
            "They coexist in monitoring reports without overriding global status."
        ),
        "rules": [
            {
                "rule_id": "SEP01",
                "rule": "Global monitoring status is controlled exclusively by P52 V2 thresholds.",
                "implication": "A band anomaly cannot change global status unless P52 thresholds are triggered.",
            },
            {
                "rule_id": "SEP02",
                "rule": "Band annotation does not override global status unless future evidence requirements are met.",
                "implication": (
                    "P55 Sep mid-band finding (n=27, SAMPLE_SENSITIVE_BAND_ANOMALY) "
                    "leaves global status as P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC."
                ),
            },
            {
                "rule_id": "SEP03",
                "rule": "Band annotations appear in reports as warning metadata sections, clearly labelled.",
                "implication": "Reports must distinguish 'GLOBAL STATUS' from 'BAND ANNOTATIONS' sections.",
            },
            {
                "rule_id": "SEP04",
                "rule": "n < 30 cannot trigger model refit.",
                "implication": "Sep 2025 1.00-1.25 band (n=27) → no refit, regardless of ECE value.",
            },
            {
                "rule_id": "SEP05",
                "rule": "n < 30 cannot change P52 thresholds.",
                "implication": (
                    "Even if platt_ece=0.246 in the Sep mid-band, P52 global ECE "
                    "thresholds remain unchanged until n >= 100 and multi-month evidence exists."
                ),
            },
            {
                "rule_id": "SEP06",
                "rule": "Band-level annotation records must preserve trace to P55/P56 source evidence.",
                "implication": (
                    "Each BandAnnotationRecord in a monitoring report must include "
                    "p55_reference and p56_reference fields pointing to the source JSON artifacts."
                ),
            },
        ],
        "current_global_status": {
            "p52_classification": "P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC",
            "global_thresholds_changed": False,
            "band_annotations_present": True,
            "band_annotations_affect_global_status": False,
        },
    }


# ---------------------------------------------------------------------------
# Task D — Sep 2025 Mid-Band Carry-Forward
# ---------------------------------------------------------------------------

def build_sep_2025_carry_forward(p56: dict) -> dict:
    """Construct the carry-forward annotation record for Sep 2025 1.00-1.25 band."""
    app = p56.get("p55_application", {})
    fe = app.get("required_future_evidence", {})
    pdn = app.get("platt_degradation_note") or {}

    return {
        "record_type": "BandAnnotationRecord",
        "schema_version": "1.0",
        "source_phase": "P55 + P56",
        "p55_reference": "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json",
        "p56_reference": "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json",
        "annotation_scope": "BAND_LEVEL",
        "metric_family": "CALIBRATION",
        "band_label": "1.00 <= |sp_fip_delta| < 1.25",
        "band_n": app.get("n", 27),
        "sample_tier": app.get("sample_tier", "BAND_SAMPLE_INSUFFICIENT"),
        "annotation": app.get("annotation", "SAMPLE_SENSITIVE_BAND_ANOMALY"),
        "action": app.get("action", "TRACK_ONLY_NO_REFIT"),
        "evidence_strength": "INSUFFICIENT",
        "platt_ece": app.get("platt_ece"),
        "raw_ece": app.get("raw_ece"),
        "ece_delta": app.get("ece_delta_platt_minus_raw"),
        "repeated_month_count": 1,
        "cumulative_band_n": app.get("n", 27),
        "future_evidence_required": True,
        "should_change_global_status": False,
        "should_trigger_refit": False,
        "should_change_thresholds": False,
        "platt_degradation_note": pdn.get("observation") if pdn else None,
        "platt_degradation_ece_delta": pdn.get("ece_delta") if pdn else None,
        "carry_forward_status": "ACTIVE_TRACK_ONLY",
        "carry_forward_reason": (
            "n=27 < 30 (BAND_SAMPLE_INSUFFICIENT). Evidence is insufficient for "
            "any action escalation. This record is carried forward into future "
            "monitoring reports as TRACK_ONLY metadata until future evidence "
            "criteria are met."
        ),
        "required_future_evidence": fe.get("criteria", []),
        "refit_trigger_conditions": fe.get("refit_trigger_conditions", ""),
        "current_status": fe.get("current_status", ""),
    }


# ---------------------------------------------------------------------------
# Task E — Future Monitoring Report Requirements
# ---------------------------------------------------------------------------

def build_future_monitoring_report_requirements() -> dict:
    """Define requirements for how future monitoring reports must include P57 annotations."""
    return {
        "description": (
            "Future Monitoring Contract V2 reports (monthly or quarterly) must include "
            "a BAND ANNOTATIONS section when any active carry-forward records exist."
        ),
        "required_report_sections": [
            "GLOBAL STATUS — P52 V2 threshold evaluation (ECE, Brier, edge rate)",
            "BAND ANNOTATIONS — Active carry-forward BandAnnotationRecord list",
            "DATA GAP STATUS — 2024 closing-line gap and cross-year analysis status",
            "GOVERNANCE SUMMARY — paper_only, promotion_freeze, live_api_calls",
        ],
        "band_annotation_section_rules": [
            "Each BandAnnotationRecord must show sample_tier, annotation, action, n, platt_ece.",
            "Records with sample_tier=BAND_SAMPLE_INSUFFICIENT must be clearly labelled as TRACK_ONLY.",
            "Records must show evidence progress toward future_evidence_required criteria.",
            "The section must explicitly state: 'Band annotations do not change global P52 status.'",
            "The section must state whether should_trigger_refit and should_change_thresholds are false.",
        ],
        "graduation_criteria": (
            "A BandAnnotationRecord graduates from TRACK_ONLY to FLAG_FOR_FOLLOW_UP when: "
            "band n >= 30 in a subsequent month AND repeated_month_count >= 2. "
            "A record graduates to PROMOTE_TO_DRIFT_CANDIDATE_IF_CI_ELEVATED when: "
            "cumulative_band_n >= 100 AND ECE CI lower bound > 0.08."
        ),
        "archival_criteria": (
            "A BandAnnotationRecord is archived (removed from active list) when: "
            "6 consecutive months pass without band n >= 10, OR "
            "when an explicit senior review concludes no systematic pattern exists."
        ),
    }


# ---------------------------------------------------------------------------
# Task F — Future Evidence Requirements
# ---------------------------------------------------------------------------

def build_future_evidence_requirements() -> dict:
    """Define what evidence is required before Platt band calibration can be revisited."""
    return {
        "for_sep_2025_mid_band": {
            "description": "Evidence required to revisit the Sep 2025 1.00-1.25 band finding.",
            "criteria": [
                {
                    "criterion_id": "FE01",
                    "description": "Same band (1.00 <= |sp_fip_delta| < 1.25) achieves n >= 30 in a future month.",
                    "required": True,
                    "current_status": "NOT_MET — n=27 in Sep 2025 only.",
                },
                {
                    "criterion_id": "FE02",
                    "description": "Repeated elevated platt_ece in at least 2 separate months within the same band.",
                    "required": True,
                    "current_status": "NOT_MET — single month observation only.",
                },
                {
                    "criterion_id": "FE03",
                    "description": "Cumulative band n >= 100 across all months, with ECE CI lower bound > 0.08.",
                    "required": False,
                    "note": "Alternative stronger path to BAND_DRIFT_CANDIDATE.",
                    "current_status": "NOT_MET — cumulative_band_n=27.",
                },
                {
                    "criterion_id": "FE04",
                    "description": "Platt worsening ece_delta > 0.05 confirmed at n >= 30.",
                    "required": False,
                    "note": "If met, warrants PLATT_BAND_DEGRADATION_CANDIDATE flag.",
                    "current_status": "NOT_MET — n < 30 prevents reliable ece_delta attribution.",
                },
            ],
        },
        "for_platt_refit_consideration": {
            "description": "Evidence required before a future task may consider Platt refit.",
            "minimum_requirements": [
                "FE01 AND FE02 both met.",
                "Global P52 calibration alert triggered (not just band-level).",
                "Explicit senior review approval.",
                "paper_only constraint lifted by authorized user.",
                "promotion_freeze removed by authorized user.",
            ],
            "note": (
                "None of these conditions are currently met. "
                "No Platt refit is warranted or proposed."
            ),
        },
        "for_p52_threshold_change": {
            "description": "Evidence required before P52 global thresholds may be changed.",
            "minimum_requirements": [
                "Multiple global calibration alerts across different months.",
                "Systematic ECE degradation confirmed at Tier C level (n=535 equivalent).",
                "Explicit CTO authorization.",
                "New diagnostic phase P5x completed with evidence.",
            ],
            "note": "P52 thresholds are unchanged and will remain so based on current evidence.",
        },
    }


# ---------------------------------------------------------------------------
# Task G — P52 V2 Compatibility
# ---------------------------------------------------------------------------

def build_p52_compatibility() -> dict:
    """P52 V2 compatibility statement for P57."""
    return {
        "statement": "P57 does not supersede P52 and does not change P52 thresholds.",
        "details": [
            "P57 adds a BandAnnotationRecord schema to the P52 V2 reporting metadata layer.",
            "P52 global monitoring thresholds (Tier C ECE, Brier score, edge rate) remain unchanged.",
            "P52 global status remains P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC.",
            "P57 annotation integration is additive; it does not replace any P52 field.",
            "P57 must not modify runtime recommendation logic.",
            "P57 must not change P45 Platt constants (A=0.435432, B=0.245464).",
            "P57 must not overwrite P52/P53/P54/P55/P56 artifacts.",
            "P57 must not change P52 thresholds.",
            "The Sep 2025 mid-band annotation (SAMPLE_SENSITIVE_BAND_ANOMALY, TRACK_ONLY_NO_REFIT) "
            "does not affect P52 global monitoring status.",
            "Future monitoring reports using P57 schema must explicitly state "
            "'Band annotations do not change global P52 status.'",
        ],
        "p52_threshold_status": "UNCHANGED",
        "p52_artifact_status": "PRESERVED",
        "p53_artifact_status": "PRESERVED",
        "p54_artifact_status": "PRESERVED",
        "p55_artifact_status": "PRESERVED",
        "p56_artifact_status": "PRESERVED",
        "platt_constants_status": "UNCHANGED — A=0.435432, B=0.245464 (P45 locked)",
        "global_monitoring_status": "P52_MONITORING_CONTRACT_V2_READY_DIAGNOSTIC",
    }


# ---------------------------------------------------------------------------
# Master audit builder
# ---------------------------------------------------------------------------

def build_p57_audit() -> dict:
    print("[P57.PRE] Governance assertions...")
    _assert_governance()
    print("  PASS")

    print("[P57.A] Loading source artifacts...")
    for path in [P52_SUMMARY, P53_SUMMARY, P54_SUMMARY, P55_SUMMARY, P56_SUMMARY]:
        assert path.exists(), f"Source artifact missing: {path}"
    p52 = json.loads(P52_SUMMARY.read_text(encoding="utf-8"))
    p53 = json.loads(P53_SUMMARY.read_text(encoding="utf-8"))
    p54 = json.loads(P54_SUMMARY.read_text(encoding="utf-8"))
    p55 = json.loads(P55_SUMMARY.read_text(encoding="utf-8"))
    p56 = json.loads(P56_SUMMARY.read_text(encoding="utf-8"))
    print("  P52/P53/P54/P55/P56 loaded")

    print("[P57.B] Building P52 contract recap...")
    p52_recap = build_p52_contract_recap(p52)

    print("[P57.C] Building P56 policy recap...")
    p56_recap = build_p56_policy_recap(p56)

    print("[P57.D] Building annotation metadata schema...")
    schema = build_annotation_metadata_schema()
    print(f"  {len(schema['fields'])} schema fields defined")

    print("[P57.E] Building global vs band status separation...")
    separation = build_global_vs_band_separation()
    print(f"  {len(separation['rules'])} separation rules defined")

    print("[P57.F] Building Sep 2025 mid-band carry-forward...")
    carry_forward = build_sep_2025_carry_forward(p56)
    print(f"  annotation={carry_forward['annotation']}")
    print(f"  action={carry_forward['action']}")
    print(f"  should_trigger_refit={carry_forward['should_trigger_refit']}")
    print(f"  should_change_global_status={carry_forward['should_change_global_status']}")

    print("[P57.G] Building future monitoring report requirements...")
    report_reqs = build_future_monitoring_report_requirements()

    print("[P57.H] Building future evidence requirements...")
    future_evidence = build_future_evidence_requirements()

    print("[P57.I] P52 V2 compatibility statement...")
    p52_compat = build_p52_compatibility()

    final_clf = "P57_ANNOTATION_INTEGRATION_READY_DIAGNOSTIC"
    print(f"\n[P57.J] Final classification: {final_clf}")

    # Final governance assertions
    _assert_governance()

    audit = {
        "p57_phase": "P57 — Monitoring Contract V2 Annotation Integration",
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "source_artifacts": {
            "p52": str(P52_SUMMARY.relative_to(ROOT)),
            "p53": str(P53_SUMMARY.relative_to(ROOT)),
            "p54": str(P54_SUMMARY.relative_to(ROOT)),
            "p55": str(P55_SUMMARY.relative_to(ROOT)),
            "p56": str(P56_SUMMARY.relative_to(ROOT)),
        },
        "p52_contract_recap": p52_recap,
        "p56_policy_recap": p56_recap,
        "annotation_metadata_schema": schema,
        "global_vs_band_status_separation": separation,
        "sep_2025_mid_band_annotation_carry_forward": carry_forward,
        "future_monitoring_report_requirements": report_reqs,
        "future_evidence_requirements": future_evidence,
        "p52_v2_compatibility": p52_compat,
        "data_gap_status": {
            "p43_2024_closing_line_gap": "UNRESOLVED",
            "note": (
                "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. "
                "Cross-year band analysis cannot be completed until 2024 historical odds "
                "are obtained. P57 annotation integration applies to 2025 Tier C data only."
            ),
        },
        "final_p57_classification": final_clf,
        "governance_flags": GOVERNANCE,
    }
    return audit


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_report(audit: dict) -> None:
    clf = audit["final_p57_classification"]
    p52r = audit["p52_contract_recap"]
    p56r = audit["p56_policy_recap"]
    schema = audit["annotation_metadata_schema"]
    sep = audit["global_vs_band_status_separation"]
    cf = audit["sep_2025_mid_band_annotation_carry_forward"]
    fe = audit["future_evidence_requirements"]["for_sep_2025_mid_band"]
    compat = audit["p52_v2_compatibility"]
    rr = audit["future_monitoring_report_requirements"]

    schema_fields_table = "".join(
        f"| `{name}` | {props['type']} | {props['description'][:70]} |\n"
        for name, props in schema["fields"].items()
    )

    sep_rules_table = "".join(
        f"| {r['rule_id']} | {r['rule'][:70]} | {r['implication'][:70]} |\n"
        for r in sep["rules"]
    )

    fe_criteria_md = "".join(
        f"- **{c['criterion_id']}** ({'REQUIRED' if c['required'] else 'OPTIONAL'}): "
        f"{c['description']}  \n  *Current status: {c['current_status']}*\n"
        for c in fe["criteria"]
    )

    compat_details_md = "".join(f"- {d}\n" for d in compat["details"])

    sep_2025_row = "\n".join([
        f"| annotation_scope | {cf['annotation_scope']} |",
        f"| metric_family | {cf['metric_family']} |",
        f"| band_label | {cf['band_label']} |",
        f"| band_n | {cf['band_n']} |",
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
        f"| platt_degradation_note | {cf.get('platt_degradation_note')} |",
        f"| carry_forward_status | {cf['carry_forward_status']} |",
    ])

    content = f"""# P57 — Monitoring Contract V2 Annotation Integration

**Date**: {audit['run_date']}  
**Classification**: `{clf}`  
**Governance**: paper_only=True, diagnostic_only=True, live_api_calls=0

---

## 1. P56 Recap

| Item | Value |
|------|-------|
| P56 classification | `{p56r['final_p56_classification']}` |
| Policy name | {p56r['policy_name']} |
| Policy version | {p56r['policy_version']} |
| Tiers defined | {', '.join(p56r['tiers_defined'])} |
| Sep 2025 mid-band n | {p56r['sep_2025_mid_band']['n']} |
| Sep 2025 sample_tier | {p56r['sep_2025_mid_band']['sample_tier']} |
| Sep 2025 annotation | {p56r['sep_2025_mid_band']['annotation']} |
| Sep 2025 action | {p56r['sep_2025_mid_band']['action']} |
| Sep 2025 platt_ece | {p56r['sep_2025_mid_band']['platt_ece']} |
| Sep 2025 ece_delta | {p56r['sep_2025_mid_band']['ece_delta']} |

---

## 2. Why Annotation Integration Is Needed

P53 identified a Sep 2025 global calibration anomaly. P54 isolated it to the
`sp_fip_delta` feature drift in the `1.00-1.25` band. P55 confirmed that n=27
is below the ECE reliability threshold. P56 defined a sample-sensitive band
annotation policy with three tiers (INSUFFICIENT / WATCHLIST / MONITORABLE).

Without integration into the Monitoring Contract V2 reporting layer:
1. Future reports lack a standard way to present band-level findings alongside global status.
2. Reviewers may incorrectly interpret band anomalies as global P52 alerts.
3. The Sep 2025 mid-band TRACK_ONLY finding has no formal carry-forward mechanism.
4. There is no schema defining which fields distinguish band annotations from global status.

P57 solves all four problems by adding a `BandAnnotationRecord` schema as metadata
to the P52 V2 reporting layer — without changing any P52 thresholds or runtime logic.

---

## 3. Annotation Metadata Schema

Schema: **{schema['schema_name']}** (v{schema['schema_version']})

{schema['description']}

| Field | Type | Description |
|-------|------|-------------|
{schema_fields_table}

**Invariants**:
{chr(10).join(f'- {inv}' for inv in schema['invariants'])}

---

## 4. Global vs Band Status Separation

**Principle**: {sep['separation_principle']}

| Rule | Rule Statement | Implication |
|------|---------------|-------------|
{sep_rules_table}

**Current global status**: `{sep['current_global_status']['p52_classification']}`  
**Band annotations affect global status**: {sep['current_global_status']['band_annotations_affect_global_status']}

---

## 5. Sep 2025 Mid-Band Carry-Forward Example

This is the first active `BandAnnotationRecord` in the Monitoring Contract V2 annotation layer.

| Field | Value |
|-------|-------|
{sep_2025_row}

**Carry-forward reason**: {cf['carry_forward_reason']}

---

## 6. Future Evidence Requirements

{fe_criteria_md}

**Refit trigger condition**: {fe.get('refit_trigger_conditions', 'See P56 criteria')}

---

## 7. Future Monitoring Report Requirements

Required report sections:
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(rr['required_report_sections']))}

Band annotation section rules:
{chr(10).join(f'- {r}' for r in rr['band_annotation_section_rules'])}

**Graduation criteria**: {rr['graduation_criteria']}

**Archival criteria**: {rr['archival_criteria']}

---

## 8. P52 V2 Compatibility Statement

{compat['statement']}

{compat_details_md}

| Item | Status |
|------|--------|
| P52 thresholds | {compat['p52_threshold_status']} |
| P52 artifact | {compat['p52_artifact_status']} |
| P53 artifact | {compat['p53_artifact_status']} |
| P54 artifact | {compat['p54_artifact_status']} |
| P55 artifact | {compat['p55_artifact_status']} |
| P56 artifact | {compat['p56_artifact_status']} |
| Platt constants | {compat['platt_constants_status']} |
| Global monitoring status | `{compat['global_monitoring_status']}` |

---

## 9. Limitations

1. P57 annotation schema is based on 2025 Tier C data only (n=535). Cross-year validation is not yet possible.
2. The `BandAnnotationRecord` schema v1 is a first iteration; field definitions may be refined as evidence accumulates.
3. ECE is computed with 10-bin uniform-width; other binning schemes may yield different band boundaries.
4. Graduation criteria thresholds (n>=30, n>=100, CI>0.08) are heuristic and have not been validated by formal power analysis.
5. P57 is metadata only; runtime logic and monitoring thresholds are unchanged.

---

## 10. 2024 Closing-Line Data Gap

**The 2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved.**

P57 annotation integration applies to 2025 Tier C data only. Cross-year band-level
analysis cannot be completed until 2024 historical odds data is obtained.

---

## 11. Final P57 Classification

```
{clf}
```

---

## 12. Next Recommended Diagnostic Task

**P58 — Monitoring Contract V2 Monthly Report Template**:
- Create a monthly report template that implements the P57 BandAnnotationRecord schema.
- Include GLOBAL STATUS and BAND ANNOTATIONS sections per P57 requirements.
- Populate the Sep 2025 mid-band carry-forward record as a live example.
- Validate that the template enforces all P57 separation rules and invariants.
- Prerequisite: 2024 closing-line data remains unavailable; report scope is 2025 only.

---

*Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True, live_api_calls=0*  
*P45 Platt constants unchanged: A=0.435432, B=0.245464*  
*P52/P53/P54/P55/P56 artifacts not overwritten. P52 thresholds not changed.*
"""

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(content, encoding="utf-8")
    print(f"Report written: {REPORT_MD}")

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(content, encoding="utf-8")
    print(f"BettingPlan report written: {BETTING_PLAN_MD}")


def update_active_task(classification: str) -> None:
    ACTIVE_TASK_MD.parent.mkdir(parents=True, exist_ok=True)
    p57_header = f"""# Active Task — P57 Monitoring Contract V2 Annotation Integration

> **[COMPLETED 2026-05-26]** `{classification}`
> **Issued by**: P56 `P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC` → annotation integration needed
> **HEAD**: `dbdf5b1` → 提交中 | **Branch**: `main` | **Mode**: `paper_only=True`
> **前置 Phase**: P56 `P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC`

## P57 成果摘要

- **BandAnnotationRecord schema v1**: 17 個欄位，包含 annotation_scope, sample_tier, should_trigger_refit, should_change_thresholds 等
- **Global vs Band 分離規則**: 6 條規則 SEP01-SEP06，明確禁止 band annotation 覆蓋 P52 全局狀態
- **Sep 2025 1.00-1.25 帶 Carry-Forward**: sample_tier=BAND_SAMPLE_INSUFFICIENT, annotation=SAMPLE_SENSITIVE_BAND_ANOMALY, action=TRACK_ONLY_NO_REFIT, should_trigger_refit=false, should_change_global_status=false
- **P52 V2 相容性**: P57 不取代 P52，僅添加詮釋性 metadata 層
- **P52 全局閾值**: UNCHANGED（未修改）
- **最終分類**: `{classification}`
- **Governance**: paper_only=True, live_api_calls=0, p52/p53/p54/p55/p56 artifacts preserved
- **P45 Platt 常數**: A=0.435432, B=0.245464（未修改）
- **2024 缺口**: P43 closing-line data gap 仍未解決

---

"""
    existing = ""
    if ACTIVE_TASK_MD.exists():
        existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(p57_header + existing, encoding="utf-8")
    print("active_task.md updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _assert_governance()

    audit = build_p57_audit()
    clf = audit["final_p57_classification"]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON written: {OUTPUT_JSON}")

    write_report(audit)
    update_active_task(clf)

    print()
    print("=" * 60)
    print(f"P57 COMPLETE — {clf}")
    print(f"  live_api_calls={audit['governance_flags']['live_api_calls']}")
    print(f"  paper_only={audit['governance_flags']['paper_only']}")
    print(f"  p52_thresholds_changed={audit['governance_flags']['p52_thresholds_changed']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
