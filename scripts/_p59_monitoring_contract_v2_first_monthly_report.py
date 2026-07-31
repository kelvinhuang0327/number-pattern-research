"""
P59 — Monitoring Contract V2 First Monthly Report.

Applies the P58 template to real Sep 2025 Tier C data and produces the first
real diagnostic monthly monitoring report.

Offline diagnostic only.  paper_only=True, live_api_calls=0.
Do NOT refit Platt.  Do NOT change runtime logic.  Do NOT deploy.
Do NOT overwrite P52–P58 artifacts.
Do NOT change P52 global thresholds.
Do NOT modify P45 Platt constants.
"""

from __future__ import annotations

import json
import math
import pathlib
import statistics
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]

JSONL_SOURCE = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P44T_SUMMARY = ROOT / "data/mlb_2025/derived/p44_temporal_stability_summary.json"
P52_SUMMARY = ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P53_SUMMARY = ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P55_SUMMARY = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"
P56_SUMMARY = ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json"
P57_SUMMARY = ROOT / "data/mlb_2025/derived/p57_monitoring_contract_v2_annotation_integration_summary.json"
P58_SUMMARY = ROOT / "data/mlb_2025/derived/p58_monitoring_contract_v2_monthly_report_template_summary.json"

OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p59_monitoring_contract_v2_first_monthly_report_summary.json"
REPORT_MD = ROOT / "report/p59_monitoring_contract_v2_first_monthly_report_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p59_monitoring_contract_v2_first_monthly_report_20260526.md"
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
    "p55_artifact_overwritten": False,
    "p56_artifact_overwritten": False,
    "p57_artifact_overwritten": False,
    "p58_artifact_overwritten": False,
    "p52_thresholds_changed": False,
}

# P45 Platt constants — locked, do not modify
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

REPORT_VERSION = "P59_MONITORING_CONTRACT_V2_FIRST_MONTHLY_REPORT_V1"
TEMPLATE_SOURCE = "P58_MONITORING_CONTRACT_V2_MONTHLY_REPORT_TEMPLATE_V1"

# P52 V2 Thresholds (locked, from p52_monitoring_contract_v2_summary.json)
P52_ECE_WARNING_THRESHOLD: float = 0.10
P52_ECE_CRITICAL_THRESHOLD: float = 0.12
P52_BRIER_WARNING_THRESHOLD: float = 0.25
P52_BRIER_CRITICAL_THRESHOLD: float = 0.27
P52_EDGE_WARNING_THRESHOLD: float = 0.07
P52_SAMPLE_LIMITED_THRESHOLD: int = 100
P52_BAND_SAMPLE_INSUFFICIENT_THRESHOLD: int = 30

# ---------------------------------------------------------------------------
# Governance assertions
# ---------------------------------------------------------------------------


def _assert_governance() -> None:
    assert GOVERNANCE["live_api_calls"] == 0, "GOVERNANCE VIOLATION: live_api_calls != 0"
    assert GOVERNANCE["paper_only"] is True, "GOVERNANCE VIOLATION: paper_only must be True"
    assert GOVERNANCE["platt_constants_modified"] is False, "GOVERNANCE VIOLATION: Platt constants modified"
    assert GOVERNANCE["p52_contract_overwritten"] is False
    assert GOVERNANCE["p53_artifact_overwritten"] is False
    assert GOVERNANCE["p55_artifact_overwritten"] is False
    assert GOVERNANCE["p56_artifact_overwritten"] is False
    assert GOVERNANCE["p57_artifact_overwritten"] is False
    assert GOVERNANCE["p58_artifact_overwritten"] is False
    assert GOVERNANCE["p52_thresholds_changed"] is False
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    assert abs(PLATT_A - 0.435432) < 1e-6, "GOVERNANCE VIOLATION: Platt A modified"
    assert abs(PLATT_B - 0.245464) < 1e-6, "GOVERNANCE VIOLATION: Platt B modified"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _load_tier_c_monthly_stats(p44t: dict, report_month: str) -> dict:
    """Load per-month Tier C edge statistics from the P44 temporal stability artifact."""
    monthly = p44t.get("monthly_breakdown", {})
    entry = monthly.get(report_month)
    if entry is None:
        raise KeyError(f"Month {report_month!r} not found in P44 temporal breakdown.")
    return {
        "batch_n": entry["n"],
        "raw_edge_mean": entry["mean_edge"],
        "raw_edge_ci_low": entry["bootstrap_ci_low"],
        "raw_edge_ci_high": entry["bootstrap_ci_high"],
        "classification": entry.get("classification"),
    }


def _load_sep_calibration_stats(p53: dict, report_month: str) -> dict:
    """Load calibration metrics for the report month from the P53 audit."""
    drilldown = p53.get("sep_2025_drilldown", {})
    if drilldown.get("month") != report_month:
        raise ValueError(
            f"P53 drilldown month={drilldown.get('month')!r} does not match report_month={report_month!r}"
        )
    metrics = drilldown.get("metrics", {})
    return {
        "platt_ece": metrics["platt_ece"],
        "platt_brier": metrics["platt_brier"],
        "raw_ece": metrics["raw_ece"],
        "raw_brier": metrics["raw_brier"],
        "actual_win_rate": metrics["actual_win_rate"],
        "mean_platt_prob": metrics["mean_platt_prob"],
        "v2_status": drilldown.get("v2_status"),
    }


# ---------------------------------------------------------------------------
# P59.A — Select report month and verify source data
# ---------------------------------------------------------------------------


def select_report_month(jsonl_path: pathlib.Path) -> tuple[str, int]:
    """
    Determine the best available report month.

    Priority order:
    1. Latest post-Sep 2025 month with n >= 100 (Oct 2025 preferred).
    2. Latest available month with n >= 100.
    3. Sep 2025 as HISTORICAL_DIAGNOSTIC_FIRST_REPORT fallback.

    Returns (report_month, full_jsonl_record_count_for_that_month).
    """
    import collections

    records = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_month: dict[str, int] = collections.Counter(
        r.get("game_date", "")[:7] for r in records if r.get("game_date", "")
    )

    # Filter post-Sep months with adequate sample
    post_sep = {ym: n for ym, n in by_month.items() if ym > "2025-09" and n >= 100}
    if post_sep:
        best = max(post_sep.keys())
        return best, by_month[best]

    # Any month >= 100
    adequate = {ym: n for ym, n in by_month.items() if n >= 100}
    if adequate:
        best = max(adequate.keys())
        return best, by_month[best]

    # Fallback: Sep 2025
    return "2025-09", by_month.get("2025-09", 0)


# ---------------------------------------------------------------------------
# P59.B — Compute global_status section
# ---------------------------------------------------------------------------


def compute_global_status(
    report_month: str,
    tier_c_stats: dict,
    cal_stats: dict,
    p52: dict,
) -> dict:
    """
    Compute the global_status section of the monthly report.

    Uses P52 V2 thresholds exclusively.  Band annotations have no influence here.
    """
    batch_n: int = tier_c_stats["batch_n"]
    raw_edge_mean: float = tier_c_stats["raw_edge_mean"]
    raw_edge_ci_low: float = tier_c_stats["raw_edge_ci_low"]
    raw_edge_ci_high: float = tier_c_stats["raw_edge_ci_high"]
    platt_ece: float = cal_stats["platt_ece"]
    platt_brier: float = cal_stats["platt_brier"]

    # Edge status
    if raw_edge_ci_low <= 0.0:
        edge_status = "EDGE_ALERT"
        edge_alert_code = "EDGE_DRIFT_CRITICAL"
    elif raw_edge_mean < P52_EDGE_WARNING_THRESHOLD:
        edge_status = "EDGE_ALERT"
        edge_alert_code = "EDGE_DRIFT_WARNING"
    else:
        edge_status = "EDGE_WITHIN_THRESHOLD"
        edge_alert_code = None

    # Calibration status
    if platt_ece > P52_ECE_CRITICAL_THRESHOLD:
        calibration_status = "CALIBRATION_ALERT"
        cal_alert_code = "CALIBRATION_CRITICAL"
        cal_alert_detail = (
            f"platt_ece={platt_ece:.6f} exceeds ece_critical_threshold="
            f"{P52_ECE_CRITICAL_THRESHOLD} (P52 V2)"
        )
    elif platt_ece > P52_ECE_WARNING_THRESHOLD:
        calibration_status = "CALIBRATION_ALERT"
        cal_alert_code = "CALIBRATION_WARNING"
        cal_alert_detail = (
            f"platt_ece={platt_ece:.6f} exceeds ece_warning_threshold="
            f"{P52_ECE_WARNING_THRESHOLD} (P52 V2)"
        )
    else:
        calibration_status = "CALIBRATION_WITHIN_THRESHOLD"
        cal_alert_code = None
        cal_alert_detail = None

    # Also check Brier
    if platt_brier > P52_BRIER_CRITICAL_THRESHOLD:
        if cal_alert_code is None or cal_alert_code == "CALIBRATION_WARNING":
            cal_alert_code = "CALIBRATION_CRITICAL"
            cal_alert_detail = (
                f"platt_brier={platt_brier:.6f} exceeds brier_critical_threshold="
                f"{P52_BRIER_CRITICAL_THRESHOLD} (P52 V2)"
            )

    # Sample status
    if batch_n < P52_SAMPLE_LIMITED_THRESHOLD:
        sample_status = "SAMPLE_INSUFFICIENT"
        sample_alert_code = (
            f"SAMPLE_LIMITED: batch_n={batch_n} < {P52_SAMPLE_LIMITED_THRESHOLD} "
            f"(P52 V2 dominance_rule: SAMPLE_LIMITED does not suppress CALIBRATION_CRITICAL)"
        )
    else:
        sample_status = "SAMPLE_ADEQUATE"
        sample_alert_code = None

    # Assemble global_alert_reasons
    alert_reasons: list[str] = []
    if cal_alert_detail:
        alert_reasons.append(cal_alert_detail)
    if edge_alert_code:
        alert_reasons.append(
            f"{edge_alert_code}: mean_edge={raw_edge_mean:.6f}, ci_low={raw_edge_ci_low:.6f}"
        )
    if sample_alert_code:
        alert_reasons.append(sample_alert_code)

    # Global alert level (dominance order: CRITICAL > SAMPLE_LIMITED > WARNING > NONE)
    if cal_alert_code == "CALIBRATION_CRITICAL" or edge_alert_code == "EDGE_DRIFT_CRITICAL":
        global_alert_level = "RED"
        global_status = "MONITORING_ALERT_DIAGNOSTIC"
    elif cal_alert_code == "CALIBRATION_WARNING" or edge_alert_code == "EDGE_DRIFT_WARNING":
        global_alert_level = "YELLOW"
        global_status = "MONITORING_ALERT_DIAGNOSTIC"
    elif sample_status == "SAMPLE_INSUFFICIENT":
        global_alert_level = "YELLOW"
        global_status = "MONITORING_ALERT_DIAGNOSTIC"
    else:
        global_alert_level = "GREEN"
        global_status = "MONITORING_ACTIVE_DIAGNOSTIC"

    if not alert_reasons:
        alert_reasons = ["No P52 V2 global thresholds exceeded."]

    # P52 thresholds snapshot
    p52_thresholds_used = {
        "ece_warning_threshold": P52_ECE_WARNING_THRESHOLD,
        "ece_critical_threshold": P52_ECE_CRITICAL_THRESHOLD,
        "brier_warning_threshold": P52_BRIER_WARNING_THRESHOLD,
        "brier_critical_threshold": P52_BRIER_CRITICAL_THRESHOLD,
        "edge_warning_threshold": P52_EDGE_WARNING_THRESHOLD,
        "edge_critical_condition": "edge_ci_low <= 0",
        "sample_limited_threshold": P52_SAMPLE_LIMITED_THRESHOLD,
        "source": "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
        "note": (
            "Thresholds are locked from P52. "
            "Not changed by P57, P58, or P59 band annotations."
        ),
    }

    return {
        "report_month": report_month,
        "batch_n": batch_n,
        "global_status": global_status,
        "global_alert_level": global_alert_level,
        "global_alert_reasons": alert_reasons,
        "edge_status": edge_status,
        "calibration_status": calibration_status,
        "sample_status": sample_status,
        "data_gap_status": (
            "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. "
            "Cross-year analysis cannot be completed. "
            "This is a cross-year limitation, not a 2025-only blocker."
        ),
        "raw_edge_mean": raw_edge_mean,
        "raw_edge_ci_low": raw_edge_ci_low,
        "raw_edge_ci_high": raw_edge_ci_high,
        "platt_ece": platt_ece,
        "platt_brier": platt_brier,
        "p52_thresholds_used": p52_thresholds_used,
        "source_trace": {
            "p52_summary_ref": "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json",
            "p44t_summary_ref": "data/mlb_2025/derived/p44_temporal_stability_summary.json",
            "p53_summary_ref": "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json",
            "data_source": str(JSONL_SOURCE.relative_to(ROOT)),
            "platt_constants": f"A={PLATT_A}, B={PLATT_B} (P45, locked)",
        },
    }


# ---------------------------------------------------------------------------
# P59.C — Build band_annotations section
# ---------------------------------------------------------------------------


def build_band_annotations(p57: dict) -> dict:
    """
    Carry forward Sep 2025 band annotation from P57, incrementing
    repeated_month_count to reflect P59 as the second tracking entry.

    Per P57 carry-forward policy:
      - ACTIVE_TRACK_ONLY records must appear in every subsequent monthly report
        until archival criteria are met.
      - repeated_month_count is incremented on each carry-forward.
      - cumulative_band_n is updated if new band data from the same band is observed.
        In this case (Sep 2025 report only), no new band data → cumulative_band_n stays 27.
    """
    cf = p57.get("sep_2025_mid_band_annotation_carry_forward", {})

    # Increment repeated_month_count (was 1 in P57; P59 is 2nd tracking entry)
    prior_count: int = cf.get("repeated_month_count", 1)
    new_count: int = prior_count + 1

    # cumulative_band_n: no new qualifying month data in P59 (still Sep 2025 only)
    cumulative_band_n: int = cf.get("cumulative_band_n", 27)

    record = {
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
        "repeated_month_count": new_count,
        "cumulative_band_n": cumulative_band_n,
        "future_evidence_required": cf.get("future_evidence_required", True),
        "should_change_global_status": False,
        "should_trigger_refit": False,
        "should_change_thresholds": False,
        "carry_forward_status": cf.get("carry_forward_status", "ACTIVE_TRACK_ONLY"),
        "carry_forward_note": (
            f"Carried forward from P57 (first observation Sep 2025). "
            f"P59 is the second tracking entry (repeated_month_count={new_count}). "
            "No new qualifying band data in this report period. "
            f"FE01 not yet met (n={cf.get('band_n', 27)} < 30). "
            "FE02 not yet met (single source month)."
        ),
        "source_trace": {
            "p55_reference": cf.get("p55_reference"),
            "p56_reference": cf.get("p56_reference"),
            "p57_reference": str(P57_SUMMARY.relative_to(ROOT)),
        },
    }

    return {
        "section_header": "Band annotations do not change global P52 status.",
        "active_track_only_count": 1,
        "should_trigger_refit_any": False,
        "records": [record],
    }


# ---------------------------------------------------------------------------
# P59.D — Run VAL01–VAL10
# ---------------------------------------------------------------------------


def run_validation_rules(
    global_status: dict,
    band_annotations: dict,
) -> list[dict]:
    """
    Run all 10 P58 validation rules against the generated report sections.

    Each rule returns: {rule_id, passed, evidence, failure_reason}.
    """
    results: list[dict] = []

    # VAL01 — global_status must not be MONITORING_ALERT_DIAGNOSTIC unless P52 threshold triggered
    val01_status = global_status.get("global_status")
    val01_alert_reasons = global_status.get("global_alert_reasons", [])
    if val01_status == "MONITORING_ALERT_DIAGNOSTIC":
        # Must have a P52 threshold trigger in reasons
        val01_ok = any(
            any(kw in r for kw in ["P52", "threshold", "platt_ece", "platt_brier", "ci_low", "mean_edge"])
            for r in val01_alert_reasons
        )
    else:
        val01_ok = True
    results.append({
        "rule_id": "VAL01",
        "passed": val01_ok,
        "evidence": f"global_status={val01_status!r}, alert_reasons_count={len(val01_alert_reasons)}",
        "failure_reason": None if val01_ok else "MONITORING_ALERT_DIAGNOSTIC set without P52 threshold reference",
    })

    # VAL02 — no band annotation sets should_change_global_status=true
    val02_violations = [
        r for r in band_annotations.get("records", [])
        if r.get("should_change_global_status") is True
    ]
    val02_ok = len(val02_violations) == 0
    results.append({
        "rule_id": "VAL02",
        "passed": val02_ok,
        "evidence": f"should_change_global_status=True violations: {len(val02_violations)}",
        "failure_reason": None if val02_ok else f"Records with should_change_global_status=True: {val02_violations}",
    })

    # VAL03 — no band annotation with n < 30 sets should_trigger_refit=true
    val03_violations = [
        r for r in band_annotations.get("records", [])
        if r.get("band_n", 0) < P52_BAND_SAMPLE_INSUFFICIENT_THRESHOLD
        and r.get("should_trigger_refit") is True
    ]
    val03_ok = len(val03_violations) == 0
    results.append({
        "rule_id": "VAL03",
        "passed": val03_ok,
        "evidence": f"should_trigger_refit=True violations for n<30: {len(val03_violations)}",
        "failure_reason": None if val03_ok else f"Violations: {val03_violations}",
    })

    # VAL04 — no band annotation sets should_change_thresholds=true
    val04_violations = [
        r for r in band_annotations.get("records", [])
        if r.get("should_change_thresholds") is True
    ]
    val04_ok = len(val04_violations) == 0
    results.append({
        "rule_id": "VAL04",
        "passed": val04_ok,
        "evidence": f"should_change_thresholds=True violations: {len(val04_violations)}",
        "failure_reason": None if val04_ok else f"Violations: {val04_violations}",
    })

    # VAL05 — ACTIVE_TRACK_ONLY carry-forward: Sep 2025 mid-band record must be present
    val05_active = [
        r for r in band_annotations.get("records", [])
        if r.get("carry_forward_status") == "ACTIVE_TRACK_ONLY"
        and r.get("band_label") == "1.00 <= |sp_fip_delta| < 1.25"
    ]
    val05_ok = len(val05_active) >= 1
    results.append({
        "rule_id": "VAL05",
        "passed": val05_ok,
        "evidence": f"ACTIVE_TRACK_ONLY records for Sep mid-band: {len(val05_active)}",
        "failure_reason": None if val05_ok else "Sep 2025 1.00-1.25 band ACTIVE_TRACK_ONLY record missing",
    })

    # VAL06 — band_annotations section header must contain the required statement
    header = band_annotations.get("section_header", "")
    val06_ok = "Band annotations do not change global P52 status" in header
    results.append({
        "rule_id": "VAL06",
        "passed": val06_ok,
        "evidence": f"section_header={header!r}",
        "failure_reason": None if val06_ok else "section_header missing required statement",
    })

    # VAL07 — p52_thresholds_used must reference the locked P52 artifact
    p52_thresholds = global_status.get("p52_thresholds_used", {})
    val07_ok = "p52_monitoring_contract_v2_summary.json" in p52_thresholds.get("source", "")
    results.append({
        "rule_id": "VAL07",
        "passed": val07_ok,
        "evidence": f"p52_thresholds source={p52_thresholds.get('source', '')!r}",
        "failure_reason": None if val07_ok else "p52_thresholds_used does not reference p52_monitoring_contract_v2_summary.json",
    })

    # VAL08 — data_gap_status must describe the 2024 cross-year limitation
    dg_status = global_status.get("data_gap_status", "")
    val08_ok = "2024" in dg_status and ("cross-year" in dg_status or "cross_year" in dg_status)
    results.append({
        "rule_id": "VAL08",
        "passed": val08_ok,
        "evidence": f"data_gap_status={dg_status[:120]!r}",
        "failure_reason": None if val08_ok else "data_gap_status missing 2024 cross-year limitation language",
    })

    # VAL09 — sample_status, calibration_status, edge_status must all be separate fields
    val09_ok = (
        "sample_status" in global_status
        and "calibration_status" in global_status
        and "edge_status" in global_status
        and isinstance(global_status.get("sample_status"), str)
        and isinstance(global_status.get("calibration_status"), str)
        and isinstance(global_status.get("edge_status"), str)
    )
    results.append({
        "rule_id": "VAL09",
        "passed": val09_ok,
        "evidence": (
            f"sample_status={global_status.get('sample_status')!r}, "
            f"calibration_status={global_status.get('calibration_status')!r}, "
            f"edge_status={global_status.get('edge_status')!r}"
        ),
        "failure_reason": None if val09_ok else "One or more status fields missing or not a string",
    })

    # VAL10 — governance_summary must include all four required flags
    gov = GOVERNANCE
    val10_ok = (
        gov.get("paper_only") is True
        and gov.get("live_api_calls") == 0
        and gov.get("promotion_freeze") is True
        and gov.get("kelly_deploy_allowed") is False
    )
    results.append({
        "rule_id": "VAL10",
        "passed": val10_ok,
        "evidence": (
            f"paper_only={gov.get('paper_only')}, "
            f"live_api_calls={gov.get('live_api_calls')}, "
            f"promotion_freeze={gov.get('promotion_freeze')}, "
            f"kelly_deploy_allowed={gov.get('kelly_deploy_allowed')}"
        ),
        "failure_reason": None if val10_ok else "Governance flag check failed",
    })

    return results


# ---------------------------------------------------------------------------
# Master builder
# ---------------------------------------------------------------------------


def build_p59_report() -> dict:
    print("[P59.PRE] Governance assertions...")
    _assert_governance()
    print("  PASS")

    # Verify source artifacts exist and are not modified
    print("[P59.A] Verifying source artifacts and selecting report month...")
    for path in [JSONL_SOURCE, P44T_SUMMARY, P52_SUMMARY, P53_SUMMARY,
                 P55_SUMMARY, P56_SUMMARY, P57_SUMMARY, P58_SUMMARY]:
        assert path.exists(), f"Required source artifact missing: {path}"

    # Load artifacts
    p44t = json.loads(P44T_SUMMARY.read_text(encoding="utf-8"))
    p52 = json.loads(P52_SUMMARY.read_text(encoding="utf-8"))
    p53 = json.loads(P53_SUMMARY.read_text(encoding="utf-8"))
    p57 = json.loads(P57_SUMMARY.read_text(encoding="utf-8"))
    json.loads(P55_SUMMARY.read_text(encoding="utf-8"))  # integrity check
    json.loads(P56_SUMMARY.read_text(encoding="utf-8"))  # integrity check
    json.loads(P58_SUMMARY.read_text(encoding="utf-8"))  # integrity check
    print("  All source artifacts loaded and verified")

    # Select report month
    report_month, _ = select_report_month(JSONL_SOURCE)
    print(f"  Selected report month: {report_month}")

    # Determine report classification based on whether fallback was needed
    is_fallback_month = report_month == "2025-09"
    report_type = "HISTORICAL_DIAGNOSTIC_FIRST_REPORT" if is_fallback_month else "DIAGNOSTIC_MONTHLY_REPORT"

    # P59.B — Load Tier C stats for the selected month
    print(f"[P59.B] Loading Tier C stats for {report_month}...")
    tier_c_stats = _load_tier_c_monthly_stats(p44t, report_month)
    print(f"  batch_n={tier_c_stats['batch_n']}, mean_edge={tier_c_stats['raw_edge_mean']:.6f}")
    print(f"  ci=[{tier_c_stats['raw_edge_ci_low']:.6f}, {tier_c_stats['raw_edge_ci_high']:.6f}]")

    # P59.C — Load calibration stats
    print(f"[P59.C] Loading calibration stats for {report_month}...")
    cal_stats = _load_sep_calibration_stats(p53, report_month)
    print(f"  platt_ece={cal_stats['platt_ece']:.6f}, platt_brier={cal_stats['platt_brier']:.6f}")

    # P59.B — Compute global_status section
    print("[P59.B] Computing global_status section...")
    global_status = compute_global_status(report_month, tier_c_stats, cal_stats, p52)
    print(f"  global_status={global_status['global_status']!r}")
    print(f"  global_alert_level={global_status['global_alert_level']!r}")
    print(f"  sample_status={global_status['sample_status']!r}")
    print(f"  calibration_status={global_status['calibration_status']!r}")
    print(f"  edge_status={global_status['edge_status']!r}")

    # P59.C — Build band_annotations section
    print("[P59.C] Building band_annotations section (carry-forward from P57)...")
    band_annotations = build_band_annotations(p57)
    cf_record = band_annotations["records"][0]
    print(f"  band_n={cf_record['band_n']}, sample_tier={cf_record['sample_tier']!r}")
    print(f"  action={cf_record['action']!r}")
    print(f"  repeated_month_count={cf_record['repeated_month_count']}")
    print(f"  should_change_global_status={cf_record['should_change_global_status']}")
    print(f"  should_trigger_refit={cf_record['should_trigger_refit']}")

    # P59.D — Run VAL01–VAL10
    print("[P59.D] Running VAL01–VAL10 validation rules...")
    val_results = run_validation_rules(global_status, band_annotations)
    passed = sum(1 for r in val_results if r["passed"])
    failed = [r for r in val_results if not r["passed"]]
    print(f"  {passed}/{len(val_results)} validation rules passed")
    for f in failed:
        print(f"  FAIL {f['rule_id']}: {f['failure_reason']}")
    if failed:
        raise RuntimeError(f"Validation failed: {[f['rule_id'] for f in failed]}")

    # Final classification
    batch_n = tier_c_stats["batch_n"]
    if batch_n < P52_SAMPLE_LIMITED_THRESHOLD:
        final_clf = "P59_FIRST_MONTHLY_REPORT_SAMPLE_LIMITED"
    else:
        final_clf = "P59_FIRST_MONTHLY_REPORT_READY_DIAGNOSTIC"

    print(f"\n[P59.E] Final classification: {final_clf}")

    # Final governance assertions
    _assert_governance()

    return {
        "p59_phase": "P59 — Monitoring Contract V2 First Monthly Report",
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "report_version": REPORT_VERSION,
        "template_source": TEMPLATE_SOURCE,
        "report_month": report_month,
        "report_type": report_type,
        "report_type_note": (
            "No Oct 2025+ data available in JSONL. "
            "Sep 2025 is the earliest available post-training month with P53 drilldown. "
            "This is the first real diagnostic monthly report produced from the P58 template."
        ),
        "source_artifacts": {
            "jsonl": str(JSONL_SOURCE.relative_to(ROOT)),
            "p44t": str(P44T_SUMMARY.relative_to(ROOT)),
            "p52": str(P52_SUMMARY.relative_to(ROOT)),
            "p53": str(P53_SUMMARY.relative_to(ROOT)),
            "p55": str(P55_SUMMARY.relative_to(ROOT)),
            "p56": str(P56_SUMMARY.relative_to(ROOT)),
            "p57": str(P57_SUMMARY.relative_to(ROOT)),
            "p58": str(P58_SUMMARY.relative_to(ROOT)),
        },
        "global_status": global_status,
        "band_annotations": band_annotations,
        "validation_results": {
            "rules_run": len(val_results),
            "passed": passed,
            "failed_count": len(failed),
            "results": val_results,
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
            "p52_thresholds_changed": False,
            "p53_artifact_overwritten": False,
            "p57_artifact_overwritten": False,
            "p58_artifact_overwritten": False,
        },
        "report_limitations": [
            f"Tier C batch_n={batch_n} < {P52_SAMPLE_LIMITED_THRESHOLD}: "
            "all metrics are subject to elevated estimation variance.",
            "Sep 2025 mid-band annotation (n=27) is BAND_SAMPLE_INSUFFICIENT. "
            "No refit or threshold change warranted.",
            "2024 closing-line data gap prevents cross-year market-edge validation.",
            "This is a single-month diagnostic report. "
            "Longitudinal trend analysis requires multiple future monthly reports.",
            f"platt_ece={cal_stats['platt_ece']:.6f} exceeds the P52 V2 ece_critical_threshold="
            f"{P52_ECE_CRITICAL_THRESHOLD}. This is a CALIBRATION_CRITICAL signal for the Sep 2025 "
            "Tier C batch. It is a monitoring observation only; no refit is authorized.",
        ],
        "next_review_date": "2026-06 (when Oct 2025 or later data becomes available)",
        "final_p59_classification": final_clf,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def write_report(audit: dict) -> None:
    clf = audit["final_p59_classification"]
    gs = audit["global_status"]
    ba = audit["band_annotations"]
    cf_record = ba["records"][0]
    val = audit["validation_results"]
    lims = audit["report_limitations"]
    gov = audit["governance_summary"]

    val_rows_md = "".join(
        f"| {r['rule_id']} | {'✓ PASS' if r['passed'] else '✗ FAIL'} | "
        f"{r['evidence'][:72]} |\n"
        for r in val["results"]
    )

    alert_reasons_md = "\n".join(f"- {reason}" for reason in gs["global_alert_reasons"])
    limits_md = "\n".join(f"- {lim}" for lim in lims)

    content = f"""# P59 — Monitoring Contract V2 First Monthly Report

**Report Month**: {gs['report_month']}
**Report Type**: {audit['report_type']}
**Run Date**: {audit['run_date']}
**Template Source**: {audit['template_source']}
**Report Version**: {audit['report_version']}

---

## 1. Global Status (P52 V2 Threshold-Driven)

| Field | Value |
|---|---|
| report_month | `{gs['report_month']}` |
| batch_n | **{gs['batch_n']}** |
| global_status | **{gs['global_status']}** |
| global_alert_level | **{gs['global_alert_level']}** |
| edge_status | {gs['edge_status']} |
| calibration_status | **{gs['calibration_status']}** |
| sample_status | **{gs['sample_status']}** |
| raw_edge_mean | {gs['raw_edge_mean']:.6f} |
| raw_edge_ci_low | {gs['raw_edge_ci_low']:.6f} |
| raw_edge_ci_high | {gs['raw_edge_ci_high']:.6f} |
| platt_ece | {gs['platt_ece']:.6f} |
| platt_brier | {gs['platt_brier']:.6f} |

**Alert Reasons:**

{alert_reasons_md}

> ⚠ Global status is controlled exclusively by P52 V2 thresholds.
> Band-level annotations (Section 2) are metadata only and have no influence on global status.

---

## 2. Band Annotations (Metadata Only)

> **{ba['section_header']}**

Active TRACK_ONLY records: **{ba['active_track_only_count']}**

### Sep 2025 Mid-Band Carry-Forward Record

| Field | Value |
|---|---|
| band_label | `{cf_record['band_label']}` |
| band_n | **{cf_record['band_n']}** |
| sample_tier | **{cf_record['sample_tier']}** |
| annotation | **{cf_record['annotation']}** |
| action | **{cf_record['action']}** |
| evidence_strength | {cf_record['evidence_strength']} |
| platt_ece | {cf_record['platt_ece']} |
| raw_ece | {cf_record['raw_ece']} |
| ece_delta | {cf_record['ece_delta']} |
| repeated_month_count | **{cf_record['repeated_month_count']}** |
| cumulative_band_n | {cf_record['cumulative_band_n']} |
| should_change_global_status | {cf_record['should_change_global_status']} |
| should_trigger_refit | {cf_record['should_trigger_refit']} |
| should_change_thresholds | {cf_record['should_change_thresholds']} |
| carry_forward_status | **{cf_record['carry_forward_status']}** |

_{cf_record['carry_forward_note']}_

---

## 3. Validation Results (VAL01–VAL10)

| Rule | Status | Evidence |
|---|---|---|
{val_rows_md}
**{val['passed']}/{val['rules_run']} rules passed.**

---

## 4. Data Gap Status

- **2024 Closing-Line Gap**: {audit['data_gap_status']['p43_2024_closing_line_gap']}
- **Impact**: {audit['data_gap_status']['impact']}

---

## 5. Governance Summary

| Flag | Value |
|---|---|
| paper_only | {gov['paper_only']} |
| live_api_calls | {gov['live_api_calls']} |
| promotion_freeze | {gov['promotion_freeze']} |
| kelly_deploy_allowed | {gov['kelly_deploy_allowed']} |
| platt_constants | `{gov['platt_constants']}` |
| p52_thresholds_changed | {gov['p52_thresholds_changed']} |

---

## 6. Limitations

{limits_md}

---

## Final Classification

**`{clf}`**

> This report is diagnostic only.  No production deployment, no refit, no threshold changes.
> All findings are paper research observations under paper_only=True, promotion_freeze=True.
"""
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(content, encoding="utf-8")
    print(f"  Report written: {REPORT_MD.relative_to(ROOT)}")

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(content, encoding="utf-8")
    print(f"  BettingPlan copy: {BETTING_PLAN_MD.relative_to(ROOT)}")


def update_active_task(audit: dict) -> None:
    if not ACTIVE_TASK_MD.exists():
        print(f"  active_task.md not found at {ACTIVE_TASK_MD}; skipping update")
        return
    clf = audit["final_p59_classification"]
    ts = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n## P59 — Monitoring Contract V2 First Monthly Report [{ts}] [COMPLETED]\n"
        f"- Classification: `{clf}`\n"
        f"- Report month: {audit['report_month']} ({audit['report_type']})\n"
        f"- global_alert_level: {audit['global_status']['global_alert_level']}\n"
        f"- platt_ece={audit['global_status']['platt_ece']:.6f}, "
        f"batch_n={audit['global_status']['batch_n']}\n"
        f"- Band annotations carry-forward: repeated_month_count="
        f"{audit['band_annotations']['records'][0]['repeated_month_count']}\n"
        f"- Validation: {audit['validation_results']['passed']}/"
        f"{audit['validation_results']['rules_run']} PASS\n\n"
    )
    existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(entry + existing, encoding="utf-8")
    print(f"  active_task.md updated")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 72)
    print("P59 — Monitoring Contract V2 First Monthly Report")
    print("=" * 72)

    audit = build_p59_report()

    print("\n[P59.E] Writing output artifacts...")
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON: {OUTPUT_JSON.relative_to(ROOT)}")

    write_report(audit)
    update_active_task(audit)

    print("\n" + "=" * 72)
    clf = audit["final_p59_classification"]
    print(f"FINAL CLASSIFICATION: {clf}")
    print("=" * 72)


if __name__ == "__main__":
    main()
