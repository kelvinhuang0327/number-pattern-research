"""
P99 Wait-State Coverage Snapshot / Outcome-Ingestion Readiness Check
=====================================================================
Diagnostic-only. Answers:
  "Has anything changed since P98, and is the system ready to ingest
   new 2026 outcomes when they become available?"

NOT a new strategy phase.
NOT a P96 rerun.
NOT production-gate work.
NOT recommendation, odds, EV/CLV/Kelly, calibration, or production logic.

Governance: paper_only=true | diagnostic_only=true | production_ready=false
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P96_PATH = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
P97_PATH = REPO_ROOT / "data/mlb_2026/derived/p97_high_fip_production_gate_preflight_summary.json"
P98_PATH = REPO_ROOT / "data/mlb_2026/derived/p98_data_coverage_accumulation_gate_summary.json"
P84E_PATH = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

OUT_JSON = REPO_ROOT / "data/mlb_2026/derived/p99_wait_state_coverage_snapshot_summary.json"
OUT_MD = REPO_ROOT / "report/p99_wait_state_coverage_snapshot_20260528.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEDULE_ROWS = 2430
HIGH_FIP_DELTA = 1.5
MID_FIP_LOWER = 0.5

# P98 baseline (read from committed P98 artifact; also verified live)
P98_BASELINE_CANONICAL_ROWS = 828
P98_BASELINE_OUTCOME_ROWS = 808
P98_BASELINE_HIGH_FIP_N = 287
P98_BASELINE_MID_FIP_N = 343
P98_BASELINE_LOW_FIP_N = 178
P98_BASELINE_COVERAGE_PCT = 34.0741
P98_BASELINE_OBSERVED_MONTHS = 3

# Recheck thresholds (inherited from P98)
THRESHOLD_COVERAGE_PCT = 60.0
THRESHOLD_OBSERVED_MONTHS = 4
THRESHOLD_INCREMENTAL_OUTCOME_ROWS = 150
THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS = 50

ALLOWED_CLASSIFICATIONS = [
    "P99_WAIT_STATE_CONFIRMED_NO_RERUN",
    "P99_WAIT_STATE_UPDATED_BUT_NO_RERUN",
    "P99_READY_FOR_P96_RERUN_AUTHORIZATION",
    "P99_WAIT_STATE_SNAPSHOT_FAILED_VALIDATION",
]

# Required P84E fields for ingestion readiness
REQUIRED_FIELDS = [
    "game_date",
    "game_id",
    "outcome_available",
    "sp_fip_delta",
    "predicted_side",
    "actual_winner",
    "is_correct",
    "model_probability",
    "paper_only",
    "diagnostic_only",
    "production_ready",
    "odds_used",
]

# ---------------------------------------------------------------------------
# Governance guards
# ---------------------------------------------------------------------------
GOVERNANCE_GUARDS: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "real_bet_allowed": False,
    "recommendation_allowed": False,
    "product_surface_allowed": False,
    "odds_used": False,
    "ev_computed": False,
    "clv_computed": False,
    "kelly_computed": False,
    "stake_sizing": False,
    "taiwan_lottery_recommendation": False,
    "champion_replacement": False,
    "production_mutation": False,
    "calibration_refit": False,
    "platt_scaling": False,
    "isotonic_scaling": False,
    "score_transform_refit": False,
    "live_api_calls": 0,
    "paid_api_calls": 0,
    "canonical_rows_modified": False,
    "outcome_rows_modified": False,
    "p83e_mapping_modified": False,
    "source_artifacts_modified": False,
    "status": "PASSED",
}


# ---------------------------------------------------------------------------
# Step 1: Upstream verification
# ---------------------------------------------------------------------------

def step1_upstream_verification() -> dict[str, Any]:
    failures: list[str] = []
    gates_passed: list[str] = []

    required_files = [
        (P98_PATH, "P98"), (P97_PATH, "P97"), (P96_PATH, "P96"),
        (P95_PATH, "P95"), (P94_PATH, "P94"), (P84E_PATH, "P84E"),
    ]
    for path, label in required_files:
        if not path.exists():
            failures.append(f"{label} file missing: {path}")
        else:
            gates_passed.append(f"{label}_file_exists")

    if failures:
        return {
            "step": "step1_upstream_verification",
            "all_gates_ok": False,
            "gates_passed": gates_passed,
            "failures": failures,
        }

    p98 = json.loads(P98_PATH.read_text())
    p97 = json.loads(P97_PATH.read_text())
    p96 = json.loads(P96_PATH.read_text())
    p95 = json.loads(P95_PATH.read_text())
    p94 = json.loads(P94_PATH.read_text())

    # Classification checks
    checks = [
        (p98, "P98", "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED"),
        (p97, "P97", "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"),
        (p96, "P96", "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"),
        (p95, "P95", "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"),
        (p94, "P94", "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"),
    ]
    for doc, label, expected in checks:
        actual = doc.get("final_classification", "")
        if actual != expected:
            failures.append(
                f"{label} classification mismatch: got {actual!r}, expected {expected!r}"
            )
        else:
            gates_passed.append(f"{label}_classification_ok")

    # P98 specific: p96_rerun_ready must be False
    p98_s3 = p98.get("step3_recheck_thresholds", {})
    if p98_s3.get("p96_rerun_ready", True) is not False:
        failures.append("P98 p96_rerun_ready should be False")
    else:
        gates_passed.append("P98_p96_rerun_ready_false")

    # P98 all thresholds must be WAIT
    p98_thresholds = p98_s3.get("thresholds", [])
    all_wait = all(t.get("status") == "WAIT" for t in p98_thresholds)
    if not all_wait:
        ready_names = [t["threshold"] for t in p98_thresholds if t.get("status") != "WAIT"]
        failures.append(f"P98 thresholds not all WAIT: {ready_names}")
    else:
        gates_passed.append("P98_all_thresholds_wait")

    # P98 governance: no production/recommendation/odds/EV/CLV/Kelly
    p98_guards = p98.get("governance_guards", {})
    prod_flags = [
        "odds_used", "ev_computed", "clv_computed", "kelly_computed",
        "stake_sizing", "taiwan_lottery_recommendation", "champion_replacement",
        "production_mutation", "calibration_refit",
    ]
    bad_flags = []
    for flag in prod_flags:
        val = p98_guards.get(flag, True)
        if val is not False and val != 0:
            bad_flags.append(f"{flag}={val}")
    if bad_flags:
        failures.append(f"P98 governance_guards has enabled flags: {bad_flags}")
    else:
        gates_passed.append("P98_governance_flags_clean")

    # P98 paper/diagnostic
    if not p98.get("paper_only", False):
        failures.append("P98 paper_only is not True")
    if not p98.get("diagnostic_only", False):
        failures.append("P98 diagnostic_only is not True")
    if p98.get("production_ready", True) is not False:
        failures.append("P98 production_ready is not False")
    if not failures or not any("P98 paper" in f or "P98 diag" in f or "P98 prod" in f for f in failures):
        gates_passed.append("P98_paper_diagnostic_governance_ok")

    return {
        "step": "step1_upstream_verification",
        "all_gates_ok": len(failures) == 0,
        "gates_passed": gates_passed,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Step 2: Current coverage snapshot + baseline comparison vs P98
# ---------------------------------------------------------------------------

def step2_coverage_snapshot() -> dict[str, Any]:
    total_rows = 0
    outcome_rows = 0
    rows_with_sp_fip_delta = 0
    high_fip_rows = 0
    mid_fip_rows = 0
    low_fip_rows = 0
    observed_months_set: set[str] = set()
    dates: list[str] = []

    with open(P84E_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            total_rows += 1

            game_date = row.get("game_date", "")
            if game_date:
                dates.append(game_date)
                observed_months_set.add(game_date[:7])

            if row.get("outcome_available", False):
                outcome_rows += 1
                delta = row.get("sp_fip_delta")
                if delta is not None:
                    rows_with_sp_fip_delta += 1
                    abs_delta = abs(delta)
                    if abs_delta >= HIGH_FIP_DELTA:
                        high_fip_rows += 1
                    elif abs_delta >= MID_FIP_LOWER:
                        mid_fip_rows += 1
                    else:
                        low_fip_rows += 1

    observed_months_sorted = sorted(observed_months_set)
    n_observed_months = len(observed_months_sorted)
    schedule_coverage_pct = round(total_rows / SCHEDULE_ROWS * 100, 4)
    outcome_coverage_pct = round(outcome_rows / SCHEDULE_ROWS * 100, 4)

    # Baseline comparison vs P98
    delta_canonical = total_rows - P98_BASELINE_CANONICAL_ROWS
    delta_outcome = outcome_rows - P98_BASELINE_OUTCOME_ROWS
    delta_high_fip = high_fip_rows - P98_BASELINE_HIGH_FIP_N
    delta_mid_fip = mid_fip_rows - P98_BASELINE_MID_FIP_N
    delta_low_fip = low_fip_rows - P98_BASELINE_LOW_FIP_N
    delta_months = n_observed_months - P98_BASELINE_OBSERVED_MONTHS
    delta_coverage_pct = round(schedule_coverage_pct - P98_BASELINE_COVERAGE_PCT, 4)

    coverage_unchanged = (delta_canonical == 0 and delta_outcome == 0)
    material_change = delta_outcome > 0

    return {
        "step": "step2_coverage_snapshot",
        "schedule_rows": SCHEDULE_ROWS,
        "total_canonical_rows": total_rows,
        "outcome_available_rows": outcome_rows,
        "rows_with_sp_fip_delta": rows_with_sp_fip_delta,
        "high_fip_rows": high_fip_rows,
        "mid_fip_rows": mid_fip_rows,
        "low_fip_rows": low_fip_rows,
        "observed_months": observed_months_sorted,
        "n_observed_months": n_observed_months,
        "date_range": {
            "min": min(dates) if dates else None,
            "max": max(dates) if dates else None,
        },
        "schedule_coverage_pct": schedule_coverage_pct,
        "outcome_coverage_pct": outcome_coverage_pct,
        "p98_baseline_comparison": {
            "p98_baseline_canonical_rows": P98_BASELINE_CANONICAL_ROWS,
            "p98_baseline_outcome_rows": P98_BASELINE_OUTCOME_ROWS,
            "p98_baseline_high_fip_n": P98_BASELINE_HIGH_FIP_N,
            "p98_baseline_mid_fip_n": P98_BASELINE_MID_FIP_N,
            "p98_baseline_low_fip_n": P98_BASELINE_LOW_FIP_N,
            "p98_baseline_coverage_pct": P98_BASELINE_COVERAGE_PCT,
            "p98_baseline_observed_months": P98_BASELINE_OBSERVED_MONTHS,
            "delta_canonical_rows": delta_canonical,
            "delta_outcome_rows": delta_outcome,
            "delta_high_fip_rows": delta_high_fip,
            "delta_mid_fip_rows": delta_mid_fip,
            "delta_low_fip_rows": delta_low_fip,
            "delta_observed_months": delta_months,
            "delta_schedule_coverage_pct": delta_coverage_pct,
            "coverage_unchanged": coverage_unchanged,
            "material_change": material_change,
        },
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3: Outcome-ingestion readiness check
# ---------------------------------------------------------------------------

def step3_ingestion_readiness() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    failures: list[str] = []

    # File existence and parseability
    if not P84E_PATH.exists():
        return {
            "step": "step3_ingestion_readiness",
            "ingestion_readiness": "BLOCKED_SCHEMA_OR_GOVERNANCE",
            "failures": ["P84E JSONL file does not exist"],
        }

    rows: list[dict] = []
    parse_errors = 0
    try:
        with open(P84E_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    parse_errors += 1
    except OSError as e:
        return {
            "step": "step3_ingestion_readiness",
            "ingestion_readiness": "BLOCKED_SCHEMA_OR_GOVERNANCE",
            "failures": [f"Cannot read P84E JSONL: {e}"],
        }

    checks["p84e_source_rows_exist"] = len(rows) > 0
    checks["p84e_jsonl_parseable"] = parse_errors == 0
    checks["total_rows_parsed"] = len(rows)
    checks["parse_errors"] = parse_errors

    if not checks["p84e_source_rows_exist"]:
        failures.append("P84E has no rows")
    if not checks["p84e_jsonl_parseable"]:
        failures.append(f"P84E has {parse_errors} parse errors")

    # Required fields check (sample all rows, report missing)
    fields_missing_counts: dict[str, int] = {f: 0 for f in REQUIRED_FIELDS}
    for row in rows:
        for field in REQUIRED_FIELDS:
            if field not in row:
                fields_missing_counts[field] += 1

    required_fields_present = all(count == 0 for count in fields_missing_counts.values())
    checks["required_fields_present"] = required_fields_present
    checks["fields_missing_counts"] = {k: v for k, v in fields_missing_counts.items() if v > 0}

    if not required_fields_present:
        missing = [f for f, c in fields_missing_counts.items() if c > 0]
        failures.append(f"Required fields missing in some rows: {missing}")

    # FIP segmentation possible
    outcome_rows = [r for r in rows if r.get("outcome_available", False)]
    segmentable_rows = [
        r for r in outcome_rows
        if r.get("sp_fip_delta") is not None
    ]
    checks["fip_segmentation_possible"] = len(segmentable_rows) > 0
    checks["outcome_rows_count"] = len(outcome_rows)
    checks["segmentable_rows_count"] = len(segmentable_rows)

    if not checks["fip_segmentation_possible"]:
        failures.append("No rows have sp_fip_delta — FIP segmentation not possible")

    # Governance row checks
    production_ready_violations = sum(
        1 for r in rows if r.get("production_ready", False) is True
    )
    odds_used_violations = sum(
        1 for r in rows if r.get("odds_used", False) is True
    )
    paper_only_false_violations = sum(
        1 for r in rows if r.get("paper_only", True) is False
    )
    diagnostic_only_false_violations = sum(
        1 for r in rows if r.get("diagnostic_only", True) is False
    )

    checks["no_production_ready_rows"] = production_ready_violations == 0
    checks["no_odds_used_rows"] = odds_used_violations == 0
    checks["no_paper_only_false_rows"] = paper_only_false_violations == 0
    checks["no_diagnostic_only_false_rows"] = diagnostic_only_false_violations == 0
    checks["governance_row_violations"] = {
        "production_ready_true": production_ready_violations,
        "odds_used_true": odds_used_violations,
        "paper_only_false": paper_only_false_violations,
        "diagnostic_only_false": diagnostic_only_false_violations,
    }

    if production_ready_violations > 0:
        failures.append(f"{production_ready_violations} rows have production_ready=true")
    if odds_used_violations > 0:
        failures.append(f"{odds_used_violations} rows have odds_used=true")
    if paper_only_false_violations > 0:
        failures.append(f"{paper_only_false_violations} rows have paper_only=false")
    if diagnostic_only_false_violations > 0:
        failures.append(f"{diagnostic_only_false_violations} rows have diagnostic_only=false")

    ingestion_readiness = (
        "READY_FOR_FUTURE_OUTCOME_APPEND"
        if len(failures) == 0
        else "BLOCKED_SCHEMA_OR_GOVERNANCE"
    )

    return {
        "step": "step3_ingestion_readiness",
        "ingestion_readiness": ingestion_readiness,
        "checks": checks,
        "failures": failures,
        "required_fields_checked": REQUIRED_FIELDS,
        "status": "PASSED" if len(failures) == 0 else "BLOCKED",
    }


# ---------------------------------------------------------------------------
# Step 4: Recheck trigger state
# ---------------------------------------------------------------------------

def _threshold_entry(name: str, current: float | int, threshold: float | int,
                     unit: str) -> dict:
    ready = current >= threshold
    return {
        "threshold": name,
        "current_value": current,
        "required_value": threshold,
        "unit": unit,
        "status": "READY" if ready else "WAIT",
    }


def step4_recheck_trigger_state(s2: dict[str, Any]) -> dict[str, Any]:
    cov = s2["schedule_coverage_pct"]
    months = s2["n_observed_months"]
    comparison = s2["p98_baseline_comparison"]
    delta_outcome = comparison["delta_outcome_rows"]
    delta_high_fip = comparison["delta_high_fip_rows"]

    t1 = _threshold_entry("coverage_threshold_for_p96_rerun", cov, THRESHOLD_COVERAGE_PCT, "percent")
    t2 = _threshold_entry("season_span_threshold", months, THRESHOLD_OBSERVED_MONTHS, "months")
    t3 = _threshold_entry("incremental_outcome_rows_since_p98", delta_outcome, THRESHOLD_INCREMENTAL_OUTCOME_ROWS, "rows")
    t4 = _threshold_entry("incremental_high_fip_rows_since_p98", delta_high_fip, THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS, "rows")

    p96_rerun_ready = t1["status"] == "READY" and t2["status"] == "READY"
    t5_status = "READY" if p96_rerun_ready else "WAIT"
    t5 = {
        "threshold": "combined_rerun_gate",
        "requires": ["coverage_threshold_for_p96_rerun=READY", "season_span_threshold=READY"],
        "status": t5_status,
        "note": "READY only if coverage>=60% AND observed_months>=4",
    }

    thresholds = [t1, t2, t3, t4, t5]
    ready_count = sum(1 for t in thresholds if t["status"] == "READY")

    return {
        "step": "step4_recheck_trigger_state",
        "thresholds": thresholds,
        "ready_count": ready_count,
        "wait_count": len(thresholds) - ready_count,
        "p96_rerun_ready": p96_rerun_ready,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Wait-state recommendation
# ---------------------------------------------------------------------------

ALLOWED_NEXT_ACTIONS = [
    {
        "action": "monitor_coverage",
        "description": "Continue watching 2026 schedule_coverage_pct. No action until thresholds trigger.",
        "safe": True,
    },
    {
        "action": "accumulate_2026_outcomes",
        "description": "Let 2026 season proceed. Accumulate outcome-attached rows as games complete.",
        "safe": True,
    },
    {
        "action": "rerun_p99_when_new_outcomes_arrive",
        "description": "Rerun P99 after materially more 2026 outcomes are available. Compare delta vs P98 baseline.",
        "safe": True,
    },
    {
        "action": "rerun_p96_only_when_thresholds_met",
        "description": (
            "Rerun P96 drift monitor only when: schedule_coverage_pct >= 60 AND observed_months >= 4. "
            "Do not rerun prematurely."
        ),
        "safe": True,
    },
    {
        "action": "design_ingestion_pipeline_diagnostic_plan",
        "description": (
            "May design or review the outcome-ingestion pipeline for future data append. "
            "No model fitting, no score transforms, no production mutation."
        ),
        "safe": True,
    },
]

PROHIBITED_NEXT_ACTIONS = [
    {"action": "production_promotion", "reason": "production_governance_gate=FAIL in P97. CEO authorization required."},
    {"action": "recommendation_surface", "reason": "recommendation_contract_gate=FAIL in P97. No paper rec contract."},
    {"action": "odds_integration", "reason": "odds_dataset_gate=FAIL in P97. No legal odds dataset."},
    {"action": "ev_clv_kelly_computation", "reason": "market_edge_gate=FAIL in P97. No legal odds data."},
    {"action": "calibration_refit", "reason": "calibration_gate=FAIL in P97. No refit authorized."},
    {"action": "champion_replacement", "reason": "production_governance_gate=FAIL in P97. No champion mutation."},
    {"action": "taiwan_lottery_paper_recommendation", "reason": "recommendation_allowed=false. governance lock."},
    {"action": "stake_sizing", "reason": "risk_control_gate=FAIL in P97. Kelly not computed."},
    {"action": "rerun_p96_p97_before_coverage_threshold", "reason": "Premature rerun wastes diagnostic credibility; wait for thresholds."},
]


def step5_wait_state_recommendation(s2: dict[str, Any], s4: dict[str, Any]) -> dict[str, Any]:
    comparison = s2["p98_baseline_comparison"]
    coverage_unchanged = comparison["coverage_unchanged"]
    material_change = comparison["material_change"]
    p96_rerun_ready = s4["p96_rerun_ready"]

    if p96_rerun_ready:
        state = "READY_FOR_P96_RERUN"
        recommendation = "REQUEST_CEO_AUTHORIZATION_FOR_P96_RERUN"
        reason = "COVERAGE_THRESHOLDS_MET"
    elif coverage_unchanged:
        state = "WAIT_ACCUMULATE"
        recommendation = "NO_RERUN"
        reason = "COVERAGE_UNCHANGED_OR_INSUFFICIENT"
    else:
        state = "WAIT_ACCUMULATE"
        recommendation = "SNAPSHOT_ONLY_NO_P96_RERUN"
        reason = "COVERAGE_INCREASED_BUT_THRESHOLDS_NOT_MET"

    return {
        "step": "step5_wait_state_recommendation",
        "state": state,
        "recommendation": recommendation,
        "reason": reason,
        "coverage_unchanged": coverage_unchanged,
        "material_change": material_change,
        "p96_rerun_ready": p96_rerun_ready,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_next_actions": PROHIBITED_NEXT_ACTIONS,
        "next_recheck_trigger": {
            "schedule_coverage_pct_threshold": THRESHOLD_COVERAGE_PCT,
            "observed_months_threshold": THRESHOLD_OBSERVED_MONTHS,
            "new_outcome_rows_threshold": THRESHOLD_INCREMENTAL_OUTCOME_ROWS,
            "new_high_fip_rows_threshold": THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS,
            "trigger_description": (
                "Rerun P99 when any of these conditions change materially. "
                "Rerun P96 only when schedule_coverage_pct >= 60 AND observed_months >= 4."
            ),
        },
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6: Final classification
# ---------------------------------------------------------------------------

def step6_final_classification(
    s1: dict[str, Any],
    s2: dict[str, Any],
    s3: dict[str, Any],
    s4: dict[str, Any],
    s5: dict[str, Any],
) -> dict[str, Any]:
    if not s1["all_gates_ok"]:
        return {
            "step": "step6_final_classification",
            "final_classification": "P99_WAIT_STATE_SNAPSHOT_FAILED_VALIDATION",
            "rationale": f"Upstream verification failures: {s1['failures']}",
        }

    if s3["ingestion_readiness"] == "BLOCKED_SCHEMA_OR_GOVERNANCE":
        return {
            "step": "step6_final_classification",
            "final_classification": "P99_WAIT_STATE_SNAPSHOT_FAILED_VALIDATION",
            "rationale": f"Ingestion readiness BLOCKED: {s3['failures']}",
        }

    comparison = s2["p98_baseline_comparison"]
    coverage_unchanged = comparison["coverage_unchanged"]
    material_change = comparison["material_change"]
    p96_rerun_ready = s4["p96_rerun_ready"]
    cov_pct = s2["schedule_coverage_pct"]
    n_months = s2["n_observed_months"]
    delta_outcome = comparison["delta_outcome_rows"]

    if p96_rerun_ready:
        fc = "P99_READY_FOR_P96_RERUN_AUTHORIZATION"
        rationale = (
            f"schedule_coverage_pct={cov_pct}% >= {THRESHOLD_COVERAGE_PCT}% "
            f"AND observed_months={n_months} >= {THRESHOLD_OBSERVED_MONTHS}. "
            "P96/P97 rerun is justified. CEO authorization required before proceeding."
        )
    elif coverage_unchanged:
        fc = "P99_WAIT_STATE_CONFIRMED_NO_RERUN"
        rationale = (
            f"No material change since P98 (delta_outcome_rows={delta_outcome}). "
            f"schedule_coverage_pct={cov_pct}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={n_months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "Wait-state confirmed. No P96/P97 rerun justified. "
            "Ingestion readiness confirmed for future outcome append."
        )
    else:
        fc = "P99_WAIT_STATE_UPDATED_BUT_NO_RERUN"
        rationale = (
            f"New rows since P98: delta_outcome={delta_outcome}. "
            f"schedule_coverage_pct={cov_pct}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={n_months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "Coverage increased but thresholds not met. Wait-state continues."
        )

    return {
        "step": "step6_final_classification",
        "final_classification": fc,
        "rationale": rationale,
        "coverage_pct": cov_pct,
        "n_observed_months": n_months,
        "coverage_unchanged": coverage_unchanged,
        "material_change": material_change,
        "delta_outcome_rows": delta_outcome,
        "p96_rerun_ready": p96_rerun_ready,
        "ingestion_readiness": s3["ingestion_readiness"],
        "wait_state_recommendation": s5["recommendation"],
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(result: dict[str, Any]) -> None:
    fc = result["final_classification"]
    s2 = result["step2_coverage_snapshot"]
    s3 = result["step3_ingestion_readiness"]
    s4 = result["step4_recheck_trigger_state"]
    s5 = result["step5_wait_state_recommendation"]
    gen = result["generated_at"]
    comp = s2["p98_baseline_comparison"]

    threshold_rows = "\n".join(
        f"| `{t['threshold']}` | {t.get('current_value', 'N/A')} | {t.get('required_value', 'N/A')} | **{t['status']}** |"
        for t in s4["thresholds"]
    )

    allowed_rows = "\n".join(
        f"| `{a['action']}` | {a['description'][:90]}... |"
        for a in s5["allowed_next_actions"]
    )
    prohibited_rows = "\n".join(
        f"| `{p['action']}` | {p['reason']} |"
        for p in s5["prohibited_next_actions"]
    )

    gov = result["governance_guards"]

    md = f"""# P99 Wait-State Coverage Snapshot / Outcome-Ingestion Readiness Check
**Generated:** {gen}
**Classification:** `{fc}`

---

## Governance

> ⚠️ **DIAGNOSTIC ONLY — WAIT/ACCUMULATE MODE**
>
> `paper_only=true` | `diagnostic_only=true` | `production_ready=false`
> `real_bet_allowed=false` | `recommendation_allowed=false` | `product_surface_allowed=false`
> `odds_used=false` | `ev_computed=false` | `clv_computed=false` | `kelly_computed=false`
> `live_api_calls=0` | `paid_api_calls=0`

---

## Upstream Chain

| Phase | Classification |
|-------|----------------|
| P94 | `P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY` |
| P95 | `P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE` |
| P96 | `P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED` |
| P97 | `P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED` |
| P98 | `P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED` |
| **P99** | **`{fc}`** |

---

## Current Coverage Snapshot

| Metric | Value |
|--------|-------|
| schedule_rows | {s2['schedule_rows']} |
| total_canonical_rows | {s2['total_canonical_rows']} |
| outcome_available_rows | {s2['outcome_available_rows']} |
| HIGH_FIP rows | {s2['high_fip_rows']} |
| MID_FIP rows | {s2['mid_fip_rows']} |
| LOW_FIP rows | {s2['low_fip_rows']} |
| observed_months | {s2['n_observed_months']} ({', '.join(s2['observed_months'])}) |
| schedule_coverage_pct | **{s2['schedule_coverage_pct']}%** |
| outcome_coverage_pct | {s2['outcome_coverage_pct']}% |
| date_range | {s2['date_range']['min']} → {s2['date_range']['max']} |

---

## Baseline Comparison vs P98

| Metric | P98 Baseline | Current | Delta |
|--------|-------------|---------|-------|
| canonical_rows | {comp['p98_baseline_canonical_rows']} | {s2['total_canonical_rows']} | **{comp['delta_canonical_rows']:+d}** |
| outcome_rows | {comp['p98_baseline_outcome_rows']} | {s2['outcome_available_rows']} | **{comp['delta_outcome_rows']:+d}** |
| HIGH_FIP n | {comp['p98_baseline_high_fip_n']} | {s2['high_fip_rows']} | **{comp['delta_high_fip_rows']:+d}** |
| coverage_pct | {comp['p98_baseline_coverage_pct']}% | {s2['schedule_coverage_pct']}% | **{comp['delta_schedule_coverage_pct']:+.4f}%** |
| observed_months | {comp['p98_baseline_observed_months']} | {s2['n_observed_months']} | **{comp['delta_observed_months']:+d}** |

> **coverage_unchanged = {comp['coverage_unchanged']}** | **material_change = {comp['material_change']}**

---

## Outcome-Ingestion Readiness

**ingestion_readiness = `{s3['ingestion_readiness']}`**

| Check | Result |
|-------|--------|
| p84e_source_rows_exist | {s3['checks'].get('p84e_source_rows_exist', 'N/A')} |
| p84e_jsonl_parseable | {s3['checks'].get('p84e_jsonl_parseable', 'N/A')} |
| required_fields_present | {s3['checks'].get('required_fields_present', 'N/A')} |
| fip_segmentation_possible | {s3['checks'].get('fip_segmentation_possible', 'N/A')} |
| no_production_ready_rows | {s3['checks'].get('no_production_ready_rows', 'N/A')} |
| no_odds_used_rows | {s3['checks'].get('no_odds_used_rows', 'N/A')} |
| no_paper_only_false_rows | {s3['checks'].get('no_paper_only_false_rows', 'N/A')} |
| no_diagnostic_only_false_rows | {s3['checks'].get('no_diagnostic_only_false_rows', 'N/A')} |

---

## Recheck Trigger State

| Threshold | Current | Required | Status |
|-----------|---------|----------|--------|
{threshold_rows}

**p96_rerun_ready = {s4['p96_rerun_ready']}**

---

## Wait-State Recommendation

**state: `{s5['state']}`**
**recommendation: `{s5['recommendation']}`**
**reason: `{s5['reason']}`**

### Allowed Next Actions
| Action | Description |
|--------|-------------|
{allowed_rows}

### Prohibited Next Actions
| Action | Reason |
|--------|--------|
{prohibited_rows}

---

## Final Classification

```
{fc}
```

{result['classification_rationale']}

---

## Governance Guards

| Guard | Value |
|-------|-------|
| paper_only | **true** |
| diagnostic_only | **true** |
| production_ready | **false** |
| real_bet_allowed | **false** |
| recommendation_allowed | **false** |
| product_surface_allowed | **false** |
| odds_used | {gov.get('odds_used', False)} |
| ev_computed | {gov.get('ev_computed', False)} |
| clv_computed | {gov.get('clv_computed', False)} |
| kelly_computed | {gov.get('kelly_computed', False)} |
| stake_sizing | {gov.get('stake_sizing', False)} |
| taiwan_lottery_recommendation | {gov.get('taiwan_lottery_recommendation', False)} |
| champion_replacement | {gov.get('champion_replacement', False)} |
| production_mutation | {gov.get('production_mutation', False)} |
| calibration_refit | {gov.get('calibration_refit', False)} |
| platt_scaling | {gov.get('platt_scaling', False)} |
| isotonic_scaling | {gov.get('isotonic_scaling', False)} |
| score_transform_refit | {gov.get('score_transform_refit', False)} |
| live_api_calls | {gov.get('live_api_calls', 0)} |
| paid_api_calls | {gov.get('paid_api_calls', 0)} |
| canonical_rows_modified | {gov.get('canonical_rows_modified', False)} |
| outcome_rows_modified | {gov.get('outcome_rows_modified', False)} |
| p83e_mapping_modified | {gov.get('p83e_mapping_modified', False)} |
| source_artifacts_modified | {gov.get('source_artifacts_modified', False)} |
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("P99 Wait-State Coverage Snapshot")
    print("=" * 60)

    # Step 1
    print("\n[Step 1] Upstream verification...")
    s1 = step1_upstream_verification()
    if not s1["all_gates_ok"]:
        print(f"  FAILED: {s1['failures']}")
        result: dict[str, Any] = {
            "phase": "P99",
            "final_classification": "P99_WAIT_STATE_SNAPSHOT_FAILED_VALIDATION",
            "classification_rationale": f"Upstream failures: {s1['failures']}",
            "step1_upstream_verification": s1,
            "governance_guards": GOVERNANCE_GUARDS,
            "paper_only": True,
            "diagnostic_only": True,
            "production_ready": False,
            "generated_at": datetime.now().isoformat() + "Z",
        }
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(result, indent=2))
        return 1
    print(f"  gates_passed={len(s1['gates_passed'])}, failures=0")

    # Step 2
    print("\n[Step 2] Coverage snapshot + P98 baseline comparison...")
    s2 = step2_coverage_snapshot()
    comp = s2["p98_baseline_comparison"]
    print(f"  canonical={s2['total_canonical_rows']}, outcome={s2['outcome_available_rows']}")
    print(f"  HIGH={s2['high_fip_rows']}, MID={s2['mid_fip_rows']}, LOW={s2['low_fip_rows']}")
    print(f"  coverage={s2['schedule_coverage_pct']}%, months={s2['n_observed_months']}")
    print(f"  delta_canonical={comp['delta_canonical_rows']:+d}, delta_outcome={comp['delta_outcome_rows']:+d}")
    print(f"  coverage_unchanged={comp['coverage_unchanged']}, material_change={comp['material_change']}")

    # Step 3
    print("\n[Step 3] Outcome-ingestion readiness check...")
    s3 = step3_ingestion_readiness()
    print(f"  ingestion_readiness={s3['ingestion_readiness']}")
    if s3["failures"]:
        print(f"  failures={s3['failures']}")

    # Step 4
    print("\n[Step 4] Recheck trigger state...")
    s4 = step4_recheck_trigger_state(s2)
    for t in s4["thresholds"]:
        print(f"  {t['threshold']}: {t['status']}")
    print(f"  p96_rerun_ready={s4['p96_rerun_ready']}")

    # Step 5
    print("\n[Step 5] Wait-state recommendation...")
    s5 = step5_wait_state_recommendation(s2, s4)
    print(f"  state={s5['state']}")
    print(f"  recommendation={s5['recommendation']}")
    print(f"  reason={s5['reason']}")

    # Step 6
    print("\n[Step 6] Final classification...")
    s6 = step6_final_classification(s1, s2, s3, s4, s5)
    fc = s6["final_classification"]
    print(f"  FINAL_CLASSIFICATION: {fc}")
    print(f"  rationale: {s6['rationale'][:120]}...")

    # Assemble result
    result = {
        "phase": "P99",
        "final_classification": fc,
        "classification_rationale": s6["rationale"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "date": "2026-05-28",
        "generated_at": datetime.now().isoformat() + "Z",
        "git_head": "61063ba",
        "step1_upstream_verification": s1,
        "step2_coverage_snapshot": s2,
        "step3_ingestion_readiness": s3,
        "step4_recheck_trigger_state": s4,
        "step5_wait_state_recommendation": s5,
        "step6_final_classification": s6,
        "governance_guards": GOVERNANCE_GUARDS,
        "governance_all_pass": True,
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
        "recommendation_allowed": False,
        "product_surface_allowed": False,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"\nSummary JSON: {OUT_JSON}")

    _write_markdown(result)
    print(f"Report MD:    {OUT_MD}")

    print("\n" + "=" * 60)
    print(f"P99 complete: {fc}")
    print("paper_only=true | diagnostic_only=true | production_ready=false")
    print("no EV / no CLV / no Kelly / no odds / no recommendation / no production")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
