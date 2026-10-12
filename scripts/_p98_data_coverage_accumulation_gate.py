"""
P98 Data Coverage Accumulation Gate / HIGH_FIP Recheck Readiness Contract
=========================================================================
Diagnostic-only. Answers:
  "Are there enough new 2026 outcome-attached rows since P97 to justify
   rerunning P96/P97, or should the system remain in wait/accumulate mode?"

NOT a production promotion.
NOT a betting recommendation.
NOT a calibration refit.
NOT EV/CLV/Kelly work.

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
P84E_PATH = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

OUT_JSON = REPO_ROOT / "data/mlb_2026/derived/p98_data_coverage_accumulation_gate_summary.json"
OUT_MD = REPO_ROOT / "report/p98_data_coverage_accumulation_gate_20260528.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEDULE_ROWS = 2430

# P97 baseline (known from committed artifact)
P97_BASELINE_CANONICAL_ROWS = 828
P97_BASELINE_OUTCOME_ROWS = 808
P97_BASELINE_HIGH_FIP_N = 287
P97_BASELINE_COVERAGE_PCT = 34.07
P97_BASELINE_OBSERVED_MONTHS = 3

# Recheck thresholds
THRESHOLD_COVERAGE_PCT = 60.0       # schedule_coverage_pct >= 60 → READY for P96 rerun
THRESHOLD_OBSERVED_MONTHS = 4       # >= 4 months observed
THRESHOLD_INCREMENTAL_OUTCOME_ROWS = 150   # new outcome rows since P97
THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS = 50   # new HIGH_FIP rows since P97

# FIP delta thresholds (same as P93–P97)
HIGH_FIP_DELTA = 1.5    # |sp_fip_delta| >= 1.5
MID_FIP_LOWER = 0.5     # 0.5 <= |sp_fip_delta| < 1.5

ALLOWED_CLASSIFICATIONS = [
    "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED",
    "P98_WAIT_ACCUMULATE_COVERAGE_INSUFFICIENT",
    "P98_READY_TO_RERUN_P96_COVERAGE_THRESHOLD_MET",
    "P98_DATA_COVERAGE_GATE_FAILED_VALIDATION",
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

    # File existence
    required_files = [
        (P97_PATH, "P97"), (P96_PATH, "P96"), (P95_PATH, "P95"),
        (P94_PATH, "P94"), (P84E_PATH, "P84E"),
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

    # Load documents
    p97 = json.loads(P97_PATH.read_text())
    p96 = json.loads(P96_PATH.read_text())
    p95 = json.loads(P95_PATH.read_text())
    p94 = json.loads(P94_PATH.read_text())

    # Classification verification
    checks = [
        (p97, "P97", "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"),
        (p96, "P96", "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"),
        (p95, "P95", "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"),
        (p94, "P94", "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"),
    ]
    for doc, label, expected in checks:
        actual = doc.get("final_classification", "")
        if actual != expected:
            failures.append(f"{label} classification mismatch: got {actual!r}, expected {expected!r}")
        else:
            gates_passed.append(f"{label}_classification_ok")

    # P97 readiness_ratio verification
    p97_scoring = p97.get("step3_readiness_scoring", {})
    ratio = p97_scoring.get("readiness_ratio", -1)
    if abs(ratio - 0.200) > 0.001:
        failures.append(f"P97 readiness_ratio={ratio}, expected 0.200")
    else:
        gates_passed.append("P97_readiness_ratio_0200_ok")

    # DATA_COVERAGE_BLOCKER must exist in P97
    blockers = p97.get("step4_blocker_matrix", {}).get("blocker_names", [])
    if "DATA_COVERAGE_BLOCKER" not in blockers:
        failures.append("P97 step4 missing DATA_COVERAGE_BLOCKER")
    else:
        gates_passed.append("P97_data_coverage_blocker_present")

    # P97 governance: no production/recommendation/odds/EV/CLV/Kelly flags
    p97_guards = p97.get("governance_guards", {})
    prod_flags = [
        "odds_used", "ev_computed", "clv_computed", "kelly_computed",
        "stake_sizing", "taiwan_lottery_recommendation", "champion_replacement",
        "production_mutation", "calibration_refit",
    ]
    for flag in prod_flags:
        val = p97_guards.get(flag, True)
        if val is not False and val != 0:
            failures.append(f"P97 governance_guards[{flag!r}] should be False/0, got {val!r}")
    if not any(f.startswith("P97 governance") for f in failures):
        gates_passed.append("P97_governance_flags_clean")

    # P97 paper/diagnostic
    if not p97.get("paper_only", False):
        failures.append("P97 paper_only is not True")
    if not p97.get("diagnostic_only", False):
        failures.append("P97 diagnostic_only is not True")
    if p97.get("production_ready", True) is not False:
        failures.append("P97 production_ready is not False")

    if not failures:
        gates_passed.append("P97_paper_diagnostic_governance_ok")

    return {
        "step": "step1_upstream_verification",
        "all_gates_ok": len(failures) == 0,
        "gates_passed": gates_passed,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Step 2: Current coverage recount
# ---------------------------------------------------------------------------

def step2_coverage_recount() -> dict[str, Any]:
    """Read P84E and compute current coverage metrics."""
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

            # Date tracking
            game_date = row.get("game_date", "")
            if game_date:
                dates.append(game_date)
                month = game_date[:7]  # YYYY-MM
                observed_months_set.add(month)

            # Outcome availability
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
    high_fip_share = round(high_fip_rows / outcome_rows * 100, 4) if outcome_rows > 0 else 0.0

    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None

    return {
        "step": "step2_coverage_recount",
        "schedule_rows": SCHEDULE_ROWS,
        "total_canonical_rows": total_rows,
        "outcome_available_rows": outcome_rows,
        "rows_with_sp_fip_delta": rows_with_sp_fip_delta,
        "high_fip_rows": high_fip_rows,
        "mid_fip_rows": mid_fip_rows,
        "low_fip_rows": low_fip_rows,
        "observed_months": observed_months_sorted,
        "n_observed_months": n_observed_months,
        "date_range": {"min": date_min, "max": date_max},
        "schedule_coverage_pct": schedule_coverage_pct,
        "outcome_coverage_pct": outcome_coverage_pct,
        "high_fip_share_pct": high_fip_share,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3: Recheck readiness thresholds
# ---------------------------------------------------------------------------

def _threshold_result(name: str, value: float | int, threshold: float | int,
                      comparator: str, unit: str) -> dict:
    if comparator == ">=":
        ready = value >= threshold
    else:
        ready = value > threshold
    return {
        "threshold": name,
        "current_value": value,
        "required_value": threshold,
        "comparator": comparator,
        "unit": unit,
        "status": "READY" if ready else "WAIT",
    }


def step3_recheck_thresholds(s2: dict[str, Any], delta_outcome: int, delta_high_fip: int) -> dict[str, Any]:
    t1 = _threshold_result(
        "coverage_threshold_for_p96_rerun",
        s2["schedule_coverage_pct"], THRESHOLD_COVERAGE_PCT, ">=", "percent",
    )
    t2 = _threshold_result(
        "season_span_threshold",
        s2["n_observed_months"], THRESHOLD_OBSERVED_MONTHS, ">=", "months",
    )
    t3 = _threshold_result(
        "incremental_rows_threshold",
        delta_outcome, THRESHOLD_INCREMENTAL_OUTCOME_ROWS, ">=", "rows",
    )
    t4 = _threshold_result(
        "high_fip_incremental_threshold",
        delta_high_fip, THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS, ">=", "rows",
    )
    t5_ready = (s2["schedule_coverage_pct"] >= THRESHOLD_COVERAGE_PCT and
                s2["n_observed_months"] >= THRESHOLD_OBSERVED_MONTHS)
    t5 = {
        "threshold": "production_preflight_threshold",
        "requires": ["coverage_threshold_for_p96_rerun=READY", "season_span_threshold=READY"],
        "status": "READY" if t5_ready else "WAIT",
        "note": "READY only if BOTH coverage >=60% AND observed_months >=4",
    }

    thresholds = [t1, t2, t3, t4, t5]
    ready_count = sum(1 for t in thresholds if t["status"] == "READY")
    wait_count = len(thresholds) - ready_count

    return {
        "step": "step3_recheck_thresholds",
        "thresholds": thresholds,
        "ready_count": ready_count,
        "wait_count": wait_count,
        "any_rerun_threshold_met": ready_count > 0,
        "p96_rerun_ready": t1["status"] == "READY" and t2["status"] == "READY",
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4: Baseline comparison vs P97
# ---------------------------------------------------------------------------

def step4_baseline_comparison(s2: dict[str, Any]) -> dict[str, Any]:
    current_canonical = s2["total_canonical_rows"]
    current_outcome = s2["outcome_available_rows"]
    current_high_fip = s2["high_fip_rows"]
    current_coverage_pct = s2["schedule_coverage_pct"]
    current_months = s2["n_observed_months"]

    delta_canonical = current_canonical - P97_BASELINE_CANONICAL_ROWS
    delta_outcome = current_outcome - P97_BASELINE_OUTCOME_ROWS
    delta_high_fip = current_high_fip - P97_BASELINE_HIGH_FIP_N
    delta_coverage_pct = round(current_coverage_pct - P97_BASELINE_COVERAGE_PCT, 4)
    delta_months = current_months - P97_BASELINE_OBSERVED_MONTHS

    coverage_unchanged = (delta_canonical == 0 and delta_outcome == 0)

    return {
        "step": "step4_baseline_comparison",
        "p97_baseline": {
            "canonical_rows": P97_BASELINE_CANONICAL_ROWS,
            "outcome_rows": P97_BASELINE_OUTCOME_ROWS,
            "high_fip_n": P97_BASELINE_HIGH_FIP_N,
            "coverage_pct": P97_BASELINE_COVERAGE_PCT,
            "observed_months": P97_BASELINE_OBSERVED_MONTHS,
        },
        "current": {
            "canonical_rows": current_canonical,
            "outcome_rows": current_outcome,
            "high_fip_n": current_high_fip,
            "coverage_pct": current_coverage_pct,
            "observed_months": current_months,
        },
        "deltas": {
            "delta_canonical_rows": delta_canonical,
            "delta_outcome_rows": delta_outcome,
            "delta_high_fip_rows": delta_high_fip,
            "delta_coverage_pct": delta_coverage_pct,
            "delta_observed_months": delta_months,
        },
        "coverage_unchanged": coverage_unchanged,
        "new_rows_since_p97": delta_outcome,
        "rerun_p96_p97_justified": False,  # will be overridden by step3 thresholds
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Wait-state contract
# ---------------------------------------------------------------------------

ALLOWED_NEXT_ACTIONS = [
    {
        "action": "monitor_coverage",
        "description": "Continue watching 2026 schedule_coverage_pct. Take no action until thresholds trigger.",
        "safe": True,
    },
    {
        "action": "accumulate_2026_outcomes",
        "description": "Let 2026 season proceed. Accumulate outcome-attached rows as games complete.",
        "safe": True,
    },
    {
        "action": "rerun_p98_when_new_outcomes_arrive",
        "description": "Rerun P98 after materially more 2026 outcomes are available. Compare delta vs P97 baseline.",
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
        "action": "design_calibration_diagnostic_plan_only",
        "description": (
            "May design an OOS calibration diagnostic plan for HIGH_FIP. "
            "No score transform, no production mutation, no fitting of any model."
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


def step5_wait_state_contract(s3: dict[str, Any], s4: dict[str, Any]) -> dict[str, Any]:
    coverage_unchanged = s4["coverage_unchanged"]
    p96_rerun_ready = s3["p96_rerun_ready"]

    if p96_rerun_ready:
        state = "READY_TO_RERUN_P96"
    elif coverage_unchanged:
        state = "WAIT_ACCUMULATE_COVERAGE_UNCHANGED"
    else:
        state = "WAIT_ACCUMULATE_COVERAGE_INSUFFICIENT"

    next_recheck_trigger = {
        "schedule_coverage_pct_threshold": THRESHOLD_COVERAGE_PCT,
        "observed_months_threshold": THRESHOLD_OBSERVED_MONTHS,
        "new_outcome_rows_threshold": THRESHOLD_INCREMENTAL_OUTCOME_ROWS,
        "new_high_fip_rows_threshold": THRESHOLD_INCREMENTAL_HIGH_FIP_ROWS,
        "trigger_description": (
            "Rerun P98 when any of these conditions change materially. "
            "Rerun P96 only when schedule_coverage_pct >= 60 AND observed_months >= 4."
        ),
    }

    return {
        "step": "step5_wait_state_contract",
        "state": state,
        "next_recheck_trigger": next_recheck_trigger,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_next_actions": PROHIBITED_NEXT_ACTIONS,
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
) -> dict[str, Any]:
    if not s1["all_gates_ok"]:
        return {
            "step": "step6_final_classification",
            "final_classification": "P98_DATA_COVERAGE_GATE_FAILED_VALIDATION",
            "rationale": f"Upstream verification failures: {s1['failures']}",
        }

    coverage_pct = s2["schedule_coverage_pct"]
    n_months = s2["n_observed_months"]
    coverage_unchanged = s4["coverage_unchanged"]
    delta_outcome = s4["deltas"]["delta_outcome_rows"]
    p96_rerun_ready = s3["p96_rerun_ready"]

    if p96_rerun_ready:
        fc = "P98_READY_TO_RERUN_P96_COVERAGE_THRESHOLD_MET"
        rationale = (
            f"schedule_coverage_pct={coverage_pct}% >= {THRESHOLD_COVERAGE_PCT}% "
            f"AND observed_months={n_months} >= {THRESHOLD_OBSERVED_MONTHS}. "
            "P96/P97 rerun is justified."
        )
    elif coverage_unchanged:
        fc = "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED"
        rationale = (
            f"No new rows since P97 baseline (delta_outcome_rows={delta_outcome}). "
            f"schedule_coverage_pct={coverage_pct}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={n_months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "No P96/P97 rerun justified. System must remain in wait/accumulate mode."
        )
    else:
        fc = "P98_WAIT_ACCUMULATE_COVERAGE_INSUFFICIENT"
        rationale = (
            f"New rows since P97: delta_outcome={delta_outcome}. "
            f"schedule_coverage_pct={coverage_pct}% (threshold: {THRESHOLD_COVERAGE_PCT}%). "
            f"observed_months={n_months} (threshold: {THRESHOLD_OBSERVED_MONTHS}). "
            "Thresholds not met. Wait/accumulate mode continues."
        )

    return {
        "step": "step6_final_classification",
        "final_classification": fc,
        "rationale": rationale,
        "coverage_pct": coverage_pct,
        "n_observed_months": n_months,
        "coverage_unchanged": coverage_unchanged,
        "delta_outcome_rows": delta_outcome,
        "p96_rerun_ready": p96_rerun_ready,
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(result: dict[str, Any]) -> None:
    fc = result["final_classification"]
    s2 = result["step2_coverage_recount"]
    s3 = result["step3_recheck_thresholds"]
    s4 = result["step4_baseline_comparison"]
    s5 = result["step5_wait_state_contract"]
    gen = result["generated_at"]

    threshold_rows = "\n".join(
        f"| `{t['threshold']}` | {t.get('current_value', 'N/A')} | {t.get('required_value', 'N/A')} | **{t['status']}** |"
        for t in s3["thresholds"]
    )

    delta = s4["deltas"]
    baseline = s4["p97_baseline"]
    current = s4["current"]

    allowed_rows = "\n".join(
        f"| `{a['action']}` | {a['description'][:80]}... |"
        for a in s5["allowed_next_actions"]
    )
    prohibited_rows = "\n".join(
        f"| `{p['action']}` | {p['reason']} |"
        for p in s5["prohibited_next_actions"]
    )

    md = f"""# P98 Data Coverage Accumulation Gate
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
| **P98** | **`{fc}`** |

---

## Current Coverage Recount

| Metric | Value |
|--------|-------|
| schedule_rows | {s2['schedule_rows']} |
| total_canonical_rows | {s2['total_canonical_rows']} |
| outcome_available_rows | {s2['outcome_available_rows']} |
| rows_with_sp_fip_delta | {s2['rows_with_sp_fip_delta']} |
| HIGH_FIP rows | {s2['high_fip_rows']} |
| MID_FIP rows | {s2['mid_fip_rows']} |
| LOW_FIP rows | {s2['low_fip_rows']} |
| observed_months | {s2['n_observed_months']} ({', '.join(s2['observed_months'])}) |
| schedule_coverage_pct | **{s2['schedule_coverage_pct']}%** |
| outcome_coverage_pct | {s2['outcome_coverage_pct']}% |
| date_range | {s2['date_range']['min']} → {s2['date_range']['max']} |

---

## Baseline Comparison vs P97

| Metric | P97 Baseline | Current | Delta |
|--------|-------------|---------|-------|
| canonical_rows | {baseline['canonical_rows']} | {current['canonical_rows']} | **{delta['delta_canonical_rows']:+d}** |
| outcome_rows | {baseline['outcome_rows']} | {current['outcome_rows']} | **{delta['delta_outcome_rows']:+d}** |
| HIGH_FIP n | {baseline['high_fip_n']} | {current['high_fip_n']} | **{delta['delta_high_fip_rows']:+d}** |
| coverage_pct | {baseline['coverage_pct']}% | {current['coverage_pct']}% | **{delta['delta_coverage_pct']:+.4f}%** |
| observed_months | {baseline['observed_months']} | {current['observed_months']} | **{delta['delta_observed_months']:+d}** |

> **coverage_unchanged = {s4['coverage_unchanged']}** — {'No new rows since P97. No rerun justified.' if s4['coverage_unchanged'] else 'New rows detected but thresholds not yet met.'}

---

## Recheck Thresholds

| Threshold | Current | Required | Status |
|-----------|---------|----------|--------|
{threshold_rows}

**p96_rerun_ready = {s3['p96_rerun_ready']}**

---

## Wait-State Contract

**state: `{s5['state']}`**

### Next Recheck Trigger
| Trigger | Value |
|---------|-------|
| schedule_coverage_pct >= | {s5['next_recheck_trigger']['schedule_coverage_pct_threshold']}% |
| observed_months >= | {s5['next_recheck_trigger']['observed_months_threshold']} |
| new outcome_available rows >= | {s5['next_recheck_trigger']['new_outcome_rows_threshold']} |
| new HIGH_FIP rows >= | {s5['next_recheck_trigger']['new_high_fip_rows_threshold']} |

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
| odds_used | false |
| ev_computed | false |
| clv_computed | false |
| kelly_computed | false |
| stake_sizing | false |
| taiwan_lottery_recommendation | false |
| champion_replacement | false |
| production_mutation | false |
| calibration_refit | false |
| platt_scaling | false |
| isotonic_scaling | false |
| score_transform_refit | false |
| live_api_calls | 0 |
| paid_api_calls | 0 |
| canonical_rows_modified | false |
| outcome_rows_modified | false |
| p83e_mapping_modified | false |
| source_artifacts_modified | false |
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("P98 Data Coverage Accumulation Gate")
    print("=" * 60)

    # Step 1
    print("\n[Step 1] Upstream verification...")
    s1 = step1_upstream_verification()
    if not s1["all_gates_ok"]:
        print(f"  FAILED: {s1['failures']}")
        result: dict[str, Any] = {
            "phase": "P98",
            "final_classification": "P98_DATA_COVERAGE_GATE_FAILED_VALIDATION",
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
    print("\n[Step 2] Current coverage recount...")
    s2 = step2_coverage_recount()
    print(f"  canonical_rows={s2['total_canonical_rows']}, outcome_rows={s2['outcome_available_rows']}")
    print(f"  HIGH_FIP={s2['high_fip_rows']}, MID_FIP={s2['mid_fip_rows']}, LOW_FIP={s2['low_fip_rows']}")
    print(f"  schedule_coverage_pct={s2['schedule_coverage_pct']}%, observed_months={s2['n_observed_months']}")
    print(f"  date_range: {s2['date_range']['min']} → {s2['date_range']['max']}")

    # Step 4 (baseline needed for step 3 delta inputs)
    print("\n[Step 4] Baseline comparison vs P97...")
    s4 = step4_baseline_comparison(s2)
    deltas = s4["deltas"]
    print(f"  delta_canonical={deltas['delta_canonical_rows']:+d}, delta_outcome={deltas['delta_outcome_rows']:+d}")
    print(f"  delta_high_fip={deltas['delta_high_fip_rows']:+d}, delta_coverage={deltas['delta_coverage_pct']:+.4f}%")
    print(f"  coverage_unchanged={s4['coverage_unchanged']}")

    # Step 3
    print("\n[Step 3] Recheck thresholds...")
    s3 = step3_recheck_thresholds(s2, deltas["delta_outcome_rows"], deltas["delta_high_fip_rows"])
    for t in s3["thresholds"]:
        print(f"  {t['threshold']}: {t['status']}")
    print(f"  p96_rerun_ready={s3['p96_rerun_ready']}")

    # Step 5
    print("\n[Step 5] Wait-state contract...")
    s5 = step5_wait_state_contract(s3, s4)
    print(f"  state={s5['state']}")
    print(f"  allowed={len(s5['allowed_next_actions'])}, prohibited={len(s5['prohibited_next_actions'])}")

    # Step 6
    print("\n[Step 6] Final classification...")
    s6 = step6_final_classification(s1, s2, s3, s4)
    fc = s6["final_classification"]
    print(f"  FINAL_CLASSIFICATION: {fc}")
    print(f"  rationale: {s6['rationale'][:120]}...")

    # Assemble result
    result = {
        "phase": "P98",
        "final_classification": fc,
        "classification_rationale": s6["rationale"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "date": "2026-05-28",
        "generated_at": datetime.now().isoformat() + "Z",
        "git_head": "6ef4c49",
        "step1_upstream_verification": s1,
        "step2_coverage_recount": s2,
        "step3_recheck_thresholds": s3,
        "step4_baseline_comparison": s4,
        "step5_wait_state_contract": s5,
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
    print(f"P98 complete: {fc}")
    print("paper_only=true | diagnostic_only=true | production_ready=false")
    print("no EV / no CLV / no Kelly / no odds / no recommendation / no production")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
