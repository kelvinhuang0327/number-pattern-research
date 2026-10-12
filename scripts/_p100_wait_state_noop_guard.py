"""
P100 Wait-State Continuity / No-Op Guard
=========================================
Answers: "Should the agent do any work today, or confirm WAIT_ACCUMULATE and stop?"

Intentionally lightweight. Prevents phase drift, unnecessary artifacts, and
repeated pseudo-progress while no new 2026 outcome data exists.

P100 must NOT:
- rerun P96/P97
- create new strategy logic
- compute EV/CLV/Kelly
- integrate odds
- perform calibration refit
- promote production readiness
- mutate champion or runtime recommendation logic

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
P99_PATH = REPO_ROOT / "data/mlb_2026/derived/p99_wait_state_coverage_snapshot_summary.json"
P84E_PATH = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

OUT_JSON = REPO_ROOT / "data/mlb_2026/derived/p100_wait_state_noop_guard_summary.json"
OUT_MD = REPO_ROOT / "report/p100_wait_state_noop_guard_20260529.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEDULE_ROWS = 2430
HIGH_FIP_DELTA = 1.5
MID_FIP_LOWER = 0.5

# P99 baseline values (from committed P99 artifact)
P99_BASELINE_CANONICAL_ROWS = 828
P99_BASELINE_OUTCOME_ROWS = 808
P99_BASELINE_HIGH_FIP_N = 287
P99_BASELINE_MID_FIP_N = 343
P99_BASELINE_LOW_FIP_N = 178
P99_BASELINE_COVERAGE_PCT = 34.0741
P99_BASELINE_OBSERVED_MONTHS = 3

# Recheck thresholds (inherited from P98/P99)
THRESHOLD_COVERAGE_PCT = 60.0
THRESHOLD_OBSERVED_MONTHS = 4

ALLOWED_CLASSIFICATIONS = [
    "P100_WAIT_STATE_NOOP_CONFIRMED",
    "P100_WAIT_STATE_UPDATED_SNAPSHOT_REQUIRED",
    "P100_READY_FOR_CEO_RERUN_AUTHORIZATION",
    "P100_WAIT_STATE_NOOP_FAILED_VALIDATION",
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

ALLOWED_NEXT_ACTIONS = [
    {
        "action": "wait_for_new_2026_outcomes",
        "description": "No active work. Wait for 2026 season games to complete and produce new outcome rows.",
        "safe": True,
    },
    {
        "action": "monitor_schedule_coverage",
        "description": "Passively monitor schedule_coverage_pct. No action until thresholds trigger.",
        "safe": True,
    },
    {
        "action": "rerun_p99_when_new_outcomes_arrive",
        "description": "Rerun P99 snapshot check when delta_outcome_rows > 0. Compare baseline vs P99.",
        "safe": True,
    },
    {
        "action": "rerun_p100_to_confirm_noop",
        "description": "Rerun P100 no-op guard periodically to confirm wait-state is still valid.",
        "safe": True,
    },
    {
        "action": "request_ceo_authorization_when_thresholds_met",
        "description": (
            "Request CEO authorization for P96 rerun ONLY when schedule_coverage_pct >= 60 "
            "AND observed_months >= 4. Do not proceed without authorization."
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
    {"action": "rerun_p96_before_thresholds", "reason": "Premature rerun wastes diagnostic credibility; wait for thresholds."},
    {"action": "rerun_p97_before_thresholds", "reason": "Premature rerun wastes diagnostic credibility; wait for thresholds."},
]


# ---------------------------------------------------------------------------
# Step 1: Upstream verification
# ---------------------------------------------------------------------------

def step1_upstream_verification() -> dict[str, Any]:
    failures: list[str] = []
    gates_passed: list[str] = []

    required_files = [
        (P99_PATH, "P99"), (P98_PATH, "P98"), (P97_PATH, "P97"),
        (P96_PATH, "P96"), (P95_PATH, "P95"), (P94_PATH, "P94"),
        (P84E_PATH, "P84E"),
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

    p99 = json.loads(P99_PATH.read_text())
    p98 = json.loads(P98_PATH.read_text())
    p97 = json.loads(P97_PATH.read_text())
    p96 = json.loads(P96_PATH.read_text())
    p95 = json.loads(P95_PATH.read_text())
    p94 = json.loads(P94_PATH.read_text())

    checks = [
        (p99, "P99", "P99_WAIT_STATE_CONFIRMED_NO_RERUN"),
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

    # P99 specific checks
    p99_s4 = p99.get("step4_recheck_trigger_state", {})
    if p99_s4.get("p96_rerun_ready", True) is not False:
        failures.append("P99 p96_rerun_ready should be False")
    else:
        gates_passed.append("P99_p96_rerun_ready_false")

    p99_s3 = p99.get("step3_ingestion_readiness", {})
    if p99_s3.get("ingestion_readiness") != "READY_FOR_FUTURE_OUTCOME_APPEND":
        failures.append(
            f"P99 ingestion_readiness mismatch: {p99_s3.get('ingestion_readiness')!r}"
        )
    else:
        gates_passed.append("P99_ingestion_readiness_ok")

    # P99 governance flags
    p99_guards = p99.get("governance_guards", {})
    forbidden = [
        "odds_used", "ev_computed", "clv_computed", "kelly_computed",
        "stake_sizing", "taiwan_lottery_recommendation", "champion_replacement",
        "production_mutation", "calibration_refit",
    ]
    bad = [f for f in forbidden if p99_guards.get(f, True) not in (False, 0)]
    if bad:
        failures.append(f"P99 governance_guards has enabled flags: {bad}")
    else:
        gates_passed.append("P99_governance_flags_clean")

    return {
        "step": "step1_upstream_verification",
        "all_gates_ok": len(failures) == 0,
        "gates_passed": gates_passed,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Step 2: Recount current data vs P99 baseline
# ---------------------------------------------------------------------------

def step2_data_recount() -> dict[str, Any]:
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

    # Compare against P99 baseline
    delta_canonical = total_rows - P99_BASELINE_CANONICAL_ROWS
    delta_outcome = outcome_rows - P99_BASELINE_OUTCOME_ROWS
    delta_high_fip = high_fip_rows - P99_BASELINE_HIGH_FIP_N
    delta_mid_fip = mid_fip_rows - P99_BASELINE_MID_FIP_N
    delta_low_fip = low_fip_rows - P99_BASELINE_LOW_FIP_N
    delta_months = n_observed_months - P99_BASELINE_OBSERVED_MONTHS
    delta_coverage_pct = round(schedule_coverage_pct - P99_BASELINE_COVERAGE_PCT, 4)

    return {
        "step": "step2_data_recount",
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
        "p99_baseline_comparison": {
            "p99_baseline_canonical_rows": P99_BASELINE_CANONICAL_ROWS,
            "p99_baseline_outcome_rows": P99_BASELINE_OUTCOME_ROWS,
            "p99_baseline_high_fip_n": P99_BASELINE_HIGH_FIP_N,
            "p99_baseline_mid_fip_n": P99_BASELINE_MID_FIP_N,
            "p99_baseline_low_fip_n": P99_BASELINE_LOW_FIP_N,
            "p99_baseline_coverage_pct": P99_BASELINE_COVERAGE_PCT,
            "p99_baseline_observed_months": P99_BASELINE_OBSERVED_MONTHS,
            "delta_canonical_rows": delta_canonical,
            "delta_outcome_rows": delta_outcome,
            "delta_high_fip_rows": delta_high_fip,
            "delta_mid_fip_rows": delta_mid_fip,
            "delta_low_fip_rows": delta_low_fip,
            "delta_observed_months": delta_months,
            "delta_schedule_coverage_pct": delta_coverage_pct,
        },
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3: No-op decision rule
# ---------------------------------------------------------------------------

def step3_noop_decision(s2: dict[str, Any]) -> dict[str, Any]:
    comp = s2["p99_baseline_comparison"]
    delta_outcome = comp["delta_outcome_rows"]
    delta_high_fip = comp["delta_high_fip_rows"]
    cov = s2["schedule_coverage_pct"]
    months = s2["n_observed_months"]

    above_coverage = cov >= THRESHOLD_COVERAGE_PCT
    above_months = months >= THRESHOLD_OBSERVED_MONTHS
    no_new_data = delta_outcome == 0 and delta_high_fip == 0
    new_data_exists = delta_outcome > 0 or delta_high_fip > 0
    ceo_gate = above_coverage and above_months

    if ceo_gate:
        noop_state = "CEO_RERUN_AUTH_REQUIRED"
    elif no_new_data:
        noop_state = "NOOP_CONFIRMED"
    elif new_data_exists:
        noop_state = "UPDATED_SNAPSHOT_REQUIRED"
    else:
        noop_state = "NOOP_CONFIRMED"

    return {
        "step": "step3_noop_decision",
        "noop_state": noop_state,
        "delta_outcome_rows": delta_outcome,
        "delta_high_fip_rows": delta_high_fip,
        "schedule_coverage_pct": cov,
        "observed_months": months,
        "above_coverage_threshold": above_coverage,
        "above_months_threshold": above_months,
        "no_new_data": no_new_data,
        "new_data_exists": new_data_exists,
        "ceo_gate_triggered": ceo_gate,
        "thresholds": {
            "coverage_pct": {"required": THRESHOLD_COVERAGE_PCT, "current": cov,
                             "status": "READY" if above_coverage else "WAIT"},
            "observed_months": {"required": THRESHOLD_OBSERVED_MONTHS, "current": months,
                                "status": "READY" if above_months else "WAIT"},
        },
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4: Wait-state instruction
# ---------------------------------------------------------------------------

def step4_wait_state_instruction(s3: dict[str, Any]) -> dict[str, Any]:
    noop_state = s3["noop_state"]

    if noop_state == "NOOP_CONFIRMED":
        action = "DO_NOT_RUN_NEW_PHASE"
        reason = "NO_NEW_DATA_AND_THRESHOLDS_NOT_MET"
        recommended_next = "wait for new 2026 outcomes"
        next_check_trigger = {
            "trigger_1": "delta_outcome_rows > 0 (new outcome rows have arrived)",
            "trigger_2": f"schedule_coverage_pct >= {THRESHOLD_COVERAGE_PCT} (currently {s3['schedule_coverage_pct']}%)",
            "trigger_3": f"observed_months >= {THRESHOLD_OBSERVED_MONTHS} (currently {s3['observed_months']})",
            "trigger_4": "explicit CEO authorization for P96 rerun",
        }
    elif noop_state == "UPDATED_SNAPSHOT_REQUIRED":
        action = "RERUN_P99_ONLY"
        reason = "NEW_DATA_BUT_THRESHOLDS_NOT_MET"
        recommended_next = "rerun P99 snapshot to record updated baseline; do not rerun P96/P97"
        next_check_trigger = {
            "trigger_1": f"schedule_coverage_pct >= {THRESHOLD_COVERAGE_PCT}",
            "trigger_2": f"observed_months >= {THRESHOLD_OBSERVED_MONTHS}",
            "trigger_3": "explicit CEO authorization for P96 rerun",
        }
    else:  # CEO_RERUN_AUTH_REQUIRED
        action = "REQUEST_CEO_AUTHORIZATION_FOR_P96_RERUN"
        reason = "COVERAGE_THRESHOLDS_MET"
        recommended_next = (
            "Request CEO authorization for P96/P97 rerun. "
            "Do NOT rerun P96/P97 without explicit CEO authorization."
        )
        next_check_trigger = {
            "trigger_1": "CEO authorization received",
        }

    return {
        "step": "step4_wait_state_instruction",
        "noop_state": noop_state,
        "action": action,
        "reason": reason,
        "recommended_next": recommended_next,
        "next_check_trigger": next_check_trigger,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_next_actions": PROHIBITED_NEXT_ACTIONS,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Final classification
# ---------------------------------------------------------------------------

def step5_final_classification(
    s1: dict[str, Any],
    s2: dict[str, Any],
    s3: dict[str, Any],
    s4: dict[str, Any],
) -> dict[str, Any]:
    if not s1["all_gates_ok"]:
        return {
            "step": "step5_final_classification",
            "final_classification": "P100_WAIT_STATE_NOOP_FAILED_VALIDATION",
            "rationale": f"Upstream verification failures: {s1['failures']}",
        }

    noop_state = s3["noop_state"]
    comp = s2["p99_baseline_comparison"]
    cov = s2["schedule_coverage_pct"]
    months = s2["n_observed_months"]
    delta_outcome = comp["delta_outcome_rows"]
    delta_canonical = comp["delta_canonical_rows"]

    if noop_state == "CEO_RERUN_AUTH_REQUIRED":
        fc = "P100_READY_FOR_CEO_RERUN_AUTHORIZATION"
        rationale = (
            f"schedule_coverage_pct={cov}% >= {THRESHOLD_COVERAGE_PCT}% "
            f"AND observed_months={months} >= {THRESHOLD_OBSERVED_MONTHS}. "
            "Coverage thresholds met. CEO authorization required before P96/P97 rerun."
        )
    elif noop_state == "UPDATED_SNAPSHOT_REQUIRED":
        fc = "P100_WAIT_STATE_UPDATED_SNAPSHOT_REQUIRED"
        rationale = (
            f"New rows since P99: delta_outcome={delta_outcome}, delta_canonical={delta_canonical}. "
            f"schedule_coverage_pct={cov}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "Coverage increased but thresholds not met. Rerun P99 to update snapshot."
        )
    else:  # NOOP_CONFIRMED
        fc = "P100_WAIT_STATE_NOOP_CONFIRMED"
        rationale = (
            f"No new data since P99 (delta_outcome={delta_outcome}, delta_canonical={delta_canonical}). "
            f"schedule_coverage_pct={cov}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "No-op confirmed. Agent should NOT run any new phase today. "
            "Await new 2026 outcome rows."
        )

    return {
        "step": "step5_final_classification",
        "final_classification": fc,
        "rationale": rationale,
        "noop_state": noop_state,
        "action": s4["action"],
        "reason": s4["reason"],
        "schedule_coverage_pct": cov,
        "observed_months": months,
        "delta_outcome_rows": delta_outcome,
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(result: dict[str, Any]) -> None:
    fc = result["final_classification"]
    s2 = result["step2_data_recount"]
    s3 = result["step3_noop_decision"]
    s4 = result["step4_wait_state_instruction"]
    gen = result["generated_at"]
    comp = s2["p99_baseline_comparison"]
    gov = result["governance_guards"]

    allowed_rows = "\n".join(
        f"| `{a['action']}` | {a['description'][:90]}... |"
        for a in s4["allowed_next_actions"]
    )
    prohibited_rows = "\n".join(
        f"| `{p['action']}` | {p['reason']} |"
        for p in s4["prohibited_next_actions"]
    )

    md = f"""# P100 Wait-State Continuity / No-Op Guard
**Generated:** {gen}
**Classification:** `{fc}`

---

## Governance

> ⚠️ **NO-OP — WAIT/ACCUMULATE MODE**
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
| P99 | `P99_WAIT_STATE_CONFIRMED_NO_RERUN` |
| **P100** | **`{fc}`** |

---

## Current Data Recount

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

## Baseline Comparison vs P99

| Metric | P99 Baseline | Current | Delta |
|--------|-------------|---------|-------|
| canonical_rows | {comp['p99_baseline_canonical_rows']} | {s2['total_canonical_rows']} | **{comp['delta_canonical_rows']:+d}** |
| outcome_rows | {comp['p99_baseline_outcome_rows']} | {s2['outcome_available_rows']} | **{comp['delta_outcome_rows']:+d}** |
| HIGH_FIP n | {comp['p99_baseline_high_fip_n']} | {s2['high_fip_rows']} | **{comp['delta_high_fip_rows']:+d}** |
| coverage_pct | {comp['p99_baseline_coverage_pct']}% | {s2['schedule_coverage_pct']}% | **{comp['delta_schedule_coverage_pct']:+.4f}%** |
| observed_months | {comp['p99_baseline_observed_months']} | {s2['n_observed_months']} | **{comp['delta_observed_months']:+d}** |

---

## No-Op Decision

**noop_state: `{s3['noop_state']}`**

| Check | Value |
|-------|-------|
| delta_outcome_rows | {s3['delta_outcome_rows']} |
| delta_high_fip_rows | {s3['delta_high_fip_rows']} |
| no_new_data | {s3['no_new_data']} |
| new_data_exists | {s3['new_data_exists']} |
| schedule_coverage_pct | {s3['schedule_coverage_pct']}% (threshold: {THRESHOLD_COVERAGE_PCT}%) |
| observed_months | {s3['observed_months']} (threshold: {THRESHOLD_OBSERVED_MONTHS}) |
| above_coverage_threshold | {s3['above_coverage_threshold']} |
| above_months_threshold | {s3['above_months_threshold']} |
| ceo_gate_triggered | {s3['ceo_gate_triggered']} |

---

## Wait-State Instruction

**action: `{s4['action']}`**
**reason: `{s4['reason']}`**
**recommended_next:** {s4['recommended_next']}

### Next Check Triggers
{chr(10).join(f'- **{k}**: {v}' for k, v in s4['next_check_trigger'].items())}

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
    print("P100 Wait-State Continuity / No-Op Guard")
    print("=" * 60)

    # Step 1
    print("\n[Step 1] Upstream verification...")
    s1 = step1_upstream_verification()
    if not s1["all_gates_ok"]:
        print(f"  FAILED: {s1['failures']}")
        result: dict[str, Any] = {
            "phase": "P100",
            "final_classification": "P100_WAIT_STATE_NOOP_FAILED_VALIDATION",
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
    print("\n[Step 2] Data recount vs P99 baseline...")
    s2 = step2_data_recount()
    comp = s2["p99_baseline_comparison"]
    print(f"  canonical={s2['total_canonical_rows']}, outcome={s2['outcome_available_rows']}")
    print(f"  HIGH={s2['high_fip_rows']}, MID={s2['mid_fip_rows']}, LOW={s2['low_fip_rows']}")
    print(f"  coverage={s2['schedule_coverage_pct']}%, months={s2['n_observed_months']}")
    print(f"  delta_canonical={comp['delta_canonical_rows']:+d}, delta_outcome={comp['delta_outcome_rows']:+d}")
    print(f"  delta_high_fip={comp['delta_high_fip_rows']:+d}, delta_months={comp['delta_observed_months']:+d}")

    # Step 3
    print("\n[Step 3] No-op decision rule...")
    s3 = step3_noop_decision(s2)
    print(f"  noop_state={s3['noop_state']}")
    print(f"  no_new_data={s3['no_new_data']}, ceo_gate_triggered={s3['ceo_gate_triggered']}")

    # Step 4
    print("\n[Step 4] Wait-state instruction...")
    s4 = step4_wait_state_instruction(s3)
    print(f"  action={s4['action']}")
    print(f"  reason={s4['reason']}")
    print(f"  recommended_next={s4['recommended_next']}")

    # Step 5
    print("\n[Step 5] Final classification...")
    s5 = step5_final_classification(s1, s2, s3, s4)
    fc = s5["final_classification"]
    print(f"  FINAL_CLASSIFICATION: {fc}")
    print(f"  rationale: {s5['rationale'][:120]}...")

    result = {
        "phase": "P100",
        "final_classification": fc,
        "classification_rationale": s5["rationale"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "date": "2026-05-29",
        "generated_at": datetime.now().isoformat() + "Z",
        "git_head": "4b62513",
        "step1_upstream_verification": s1,
        "step2_data_recount": s2,
        "step3_noop_decision": s3,
        "step4_wait_state_instruction": s4,
        "step5_final_classification": s5,
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
    print(f"P100 complete: {fc}")
    print("paper_only=true | diagnostic_only=true | production_ready=false")
    print("no EV / no CLV / no Kelly / no odds / no recommendation / no production")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
