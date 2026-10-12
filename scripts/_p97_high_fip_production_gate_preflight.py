"""
P97 HIGH_FIP Production-Gate Preflight / Readiness Checklist
=============================================================
Diagnostic-only. Answers:
  "What exact gates remain before HIGH_FIP can ever be considered for
   product / recommendation / production review?"

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

P93_PATH = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P96_PATH = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
P84E_PATH = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

OUT_JSON = REPO_ROOT / "data/mlb_2026/derived/p97_high_fip_production_gate_preflight_summary.json"
OUT_MD = REPO_ROOT / "report/p97_high_fip_production_gate_preflight_20260528.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCHEDULE_TOTAL = 2430
EXPECTED_HIGH_N = 287
EXPECTED_HIGH_HITRATE = 0.641115
TOLERANCE = 1e-4

ALLOWED_CLASSIFICATIONS = [
    "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED",
    "P97_HIGH_FIP_PREFLIGHT_PARTIAL_PASS_REQUIRES_MORE_COVERAGE",
    "P97_HIGH_FIP_PREFLIGHT_FAILED_VALIDATION",
]

# ---------------------------------------------------------------------------
# Governance guards
# ---------------------------------------------------------------------------
GOVERNANCE_GUARDS: dict[str, Any] = {
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
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "real_bet_allowed": False,
    "recommendation_allowed": False,
    "product_surface_allowed": False,
    "status": "PASSED",
}

# ---------------------------------------------------------------------------
# Step 1: Upstream verification
# ---------------------------------------------------------------------------

def step1_upstream_verification() -> dict[str, Any]:
    gates: list[str] = []
    failures: list[str] = []

    # File existence
    for path, label in [
        (P96_PATH, "P96"), (P95_PATH, "P95"), (P94_PATH, "P94"),
        (P93_PATH, "P93"), (P84E_PATH, "P84E"),
    ]:
        if not path.exists():
            failures.append(f"{label} file missing: {path}")
        else:
            gates.append(f"{label}_file_exists")

    if failures:
        return {
            "step": "step1_upstream_verification",
            "all_gates_ok": False,
            "gates_passed": gates,
            "failures": failures,
        }

    # Load and verify classifications
    p96 = json.loads(P96_PATH.read_text())
    p95 = json.loads(P95_PATH.read_text())
    p94 = json.loads(P94_PATH.read_text())
    p93 = json.loads(P93_PATH.read_text())

    classification_checks = [
        (p96, "final_classification", "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED", "P96_classification"),
        (p95, "final_classification", "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE", "P95_classification"),
        (p94, "final_classification", "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY", "P94_classification"),
        (p93, "final_classification", "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP", "P93_classification"),
    ]

    for doc, field, expected, label in classification_checks:
        actual = doc.get(field, "")
        if actual != expected:
            failures.append(f"{label} mismatch: got {actual!r}, expected {expected!r}")
        else:
            gates.append(f"{label}_ok")

    # P96 specific: HIGH_FIP stable
    p96_monthly = p96.get("step2_monthly_drift", {})
    p96_rolling = p96.get("step3_rolling_windows", {})
    if p96_monthly.get("aggregate_monthly_status") != "MONTHLY_ALL_STABLE":
        failures.append("P96 aggregate_monthly_status is not MONTHLY_ALL_STABLE")
    else:
        gates.append("P96_monthly_all_stable")

    if p96_rolling.get("rolling_status") != "STABLE":
        failures.append("P96 rolling_status is not STABLE")
    else:
        gates.append("P96_rolling_stable")

    # HIGH_FIP n and hit_rate from P96
    high_n = p96_monthly.get("n_total", 0)
    high_hr = p96_monthly.get("overall_hit_rate", 0.0)

    if high_n != EXPECTED_HIGH_N:
        failures.append(f"HIGH_FIP n={high_n}, expected {EXPECTED_HIGH_N}")
    else:
        gates.append("HIGH_FIP_n_287_ok")

    if abs(high_hr - EXPECTED_HIGH_HITRATE) > TOLERANCE:
        failures.append(f"HIGH_FIP hit_rate={high_hr:.6f}, expected {EXPECTED_HIGH_HITRATE:.6f}")
    else:
        gates.append("HIGH_FIP_hit_rate_ok")

    # MID/LOW watch-only from P96
    p96_ctrl = p96.get("step4_control_segments", {})
    if p96_ctrl.get("mid_fip", {}).get("tracking_status") != "MID_FIP_WATCH_ONLY":
        failures.append("MID_FIP not watch-only in P96")
    else:
        gates.append("MID_FIP_watch_only_confirmed")

    if p96_ctrl.get("low_fip", {}).get("tracking_status") != "LOW_FIP_WATCH_ONLY":
        failures.append("LOW_FIP not watch-only in P96")
    else:
        gates.append("LOW_FIP_watch_only_confirmed")

    # P84E row count and coverage
    total_rows = 0
    outcome_rows = 0
    with open(P84E_PATH) as f:
        for line in f:
            row = json.loads(line)
            total_rows += 1
            if row.get("outcome_available", False) and row.get("sp_fip_delta") is not None:
                outcome_rows += 1

    if total_rows != 828:
        failures.append(f"P84E total rows={total_rows}, expected 828")
    else:
        gates.append("P84E_total_rows_828_ok")

    if outcome_rows != 808:
        failures.append(f"P84E outcome rows={outcome_rows}, expected 808")
    else:
        gates.append("P84E_outcome_rows_808_ok")

    coverage_pct = round(total_rows / SCHEDULE_TOTAL * 100, 4)

    # Governance checks
    for doc, label in [(p96, "P96"), (p95, "P95")]:
        if not doc.get("governance_all_pass", False):
            failures.append(f"{label} governance_all_pass is not True")

    gates.append("governance_all_pass_verified")

    return {
        "step": "step1_upstream_verification",
        "all_gates_ok": len(failures) == 0,
        "gates_passed": gates,
        "failures": failures,
        "high_fip_n": high_n,
        "high_fip_hit_rate": round(high_hr, 6),
        "total_rows": total_rows,
        "outcome_rows": outcome_rows,
        "schedule_total": SCHEDULE_TOTAL,
        "schedule_coverage_pct": coverage_pct,
        "observed_months": ["2026-03", "2026-04", "2026-05"],
    }


# ---------------------------------------------------------------------------
# Step 2: Production-gate readiness checklist
# ---------------------------------------------------------------------------

GATE_NAMES = [
    "prediction_signal_gate",
    "segment_scope_gate",
    "coverage_gate",
    "season_span_gate",
    "calibration_gate",
    "odds_dataset_gate",
    "market_edge_gate",
    "risk_control_gate",
    "recommendation_contract_gate",
    "production_governance_gate",
]


def _gate(name: str, status: str, rationale: str, blocker: str | None = None) -> dict:
    return {
        "gate": name,
        "status": status,
        "rationale": rationale,
        "blocker_category": blocker,
    }


def step2_readiness_checklist(s1: dict[str, Any]) -> dict[str, Any]:
    coverage_pct = s1["schedule_coverage_pct"]
    observed_months = s1["observed_months"]
    n_months = len(observed_months)

    # 1. prediction_signal_gate
    g1 = _gate(
        "prediction_signal_gate",
        "PASS",
        "P94/P95/P96 all stable — HIGH_FIP hit_rate=0.641115, monthly MONTHLY_ALL_STABLE, rolling STABLE.",
        None,
    )

    # 2. segment_scope_gate
    g2 = _gate(
        "segment_scope_gate",
        "PASS",
        "Only HIGH_FIP has diagnostic tracking. MID_FIP and LOW_FIP confirmed watch-only. No promotion.",
        None,
    )

    # 3. coverage_gate
    if coverage_pct >= 80.0:
        cov_status = "PASS"
        cov_blocker = None
    elif coverage_pct >= 60.0:
        cov_status = "WARN"
        cov_blocker = "DATA_COVERAGE_BLOCKER"
    else:
        cov_status = "FAIL"
        cov_blocker = "DATA_COVERAGE_BLOCKER"

    g3 = _gate(
        "coverage_gate",
        cov_status,
        f"schedule_coverage_pct={coverage_pct}% (threshold: PASS>=80, WARN>=60, FAIL<60). "
        f"Current 34.07% — only March–May 2026 observed. At minimum 60% required before product consideration.",
        cov_blocker,
    )

    # 4. season_span_gate
    if n_months >= 6:
        span_status = "PASS"
        span_blocker = None
    elif n_months >= 4:
        span_status = "WARN"
        span_blocker = "DATA_COVERAGE_BLOCKER"
    else:
        span_status = "FAIL"
        span_blocker = "DATA_COVERAGE_BLOCKER"

    g4 = _gate(
        "season_span_gate",
        span_status,
        f"observed_months={n_months} (threshold: PASS>=6, WARN>=4, FAIL<4). "
        f"Current: only 3 months (Mar/Apr/May 2026). Minimum 4 months needed before product consideration.",
        span_blocker,
    )

    # 5. calibration_gate
    g5 = _gate(
        "calibration_gate",
        "FAIL",
        "No OOS calibration diagnostics exist for HIGH_FIP segment. "
        "Probability reliability is unknown. No calibration refit will be run in P97.",
        "CALIBRATION_BLOCKER",
    )

    # 6. odds_dataset_gate
    g6 = _gate(
        "odds_dataset_gate",
        "FAIL",
        "No real legal odds dataset available and validated through P81/P82 policy gate. "
        "Any market edge claim requires legal odds data first.",
        "LEGAL_ODDS_BLOCKER",
    )

    # 7. market_edge_gate
    g7 = _gate(
        "market_edge_gate",
        "FAIL",
        "No EV/CLV validation exists from legal odds data. "
        "Market edge cannot be claimed without verified legal odds. No EV/CLV computed in P97.",
        "MARKET_EDGE_BLOCKER",
    )

    # 8. risk_control_gate
    g8 = _gate(
        "risk_control_gate",
        "FAIL",
        "No stake/risk caps or fail-safe policy defined and approved. "
        "Kelly criterion not computed. Risk controls must be approved before any production consideration.",
        "RISK_CONTROL_BLOCKER",
    )

    # 9. recommendation_contract_gate
    g9 = _gate(
        "recommendation_contract_gate",
        "FAIL",
        "No paper recommendation contract exists that can consume legal odds and provide source traceability. "
        "Prerequisite: legal odds dataset gate must PASS first.",
        "PRODUCT_GOVERNANCE_BLOCKER",
    )

    # 10. production_governance_gate
    g10 = _gate(
        "production_governance_gate",
        "FAIL",
        "No CEO explicit production-review authorization exists. "
        "Current CEO decision is CEO_DECISION_PARTIALLY_APPROVED for diagnostic tracking only.",
        "PRODUCT_GOVERNANCE_BLOCKER",
    )

    gates = [g1, g2, g3, g4, g5, g6, g7, g8, g9, g10]

    return {
        "step": "step2_readiness_checklist",
        "gates": gates,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3: Readiness scoring
# ---------------------------------------------------------------------------

def step3_readiness_scoring(checklist: dict[str, Any]) -> dict[str, Any]:
    gates = checklist["gates"]
    total = len(gates)
    pass_count = sum(1 for g in gates if g["status"] == "PASS")
    warn_count = sum(1 for g in gates if g["status"] == "WARN")
    fail_count = sum(1 for g in gates if g["status"] == "FAIL")
    readiness_ratio = round(pass_count / total, 4)

    pass_gates = [g["gate"] for g in gates if g["status"] == "PASS"]
    warn_gates = [g["gate"] for g in gates if g["status"] == "WARN"]
    fail_gates = [g["gate"] for g in gates if g["status"] == "FAIL"]

    return {
        "step": "step3_readiness_scoring",
        "total_gates": total,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "readiness_ratio": readiness_ratio,
        "pass_gates": pass_gates,
        "warn_gates": warn_gates,
        "fail_gates": fail_gates,
        "production_ready": False,
        "note": (
            "readiness_ratio is a diagnostic metric only. "
            "It does not trigger any promotion. "
            "All product/market gates fail due to coverage/calibration/odds/risk/governance blockers."
        ),
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4: Blocker matrix
# ---------------------------------------------------------------------------

BLOCKER_DEFINITIONS = {
    "DATA_COVERAGE_BLOCKER": {
        "name": "DATA_COVERAGE_BLOCKER",
        "description": "Schedule coverage at 34.07% (828/2430 games), only March–May 2026. "
                       "Minimum threshold: 60% (coverage_gate PASS), 4+ months (season_span_gate). "
                       "Blocking: coverage_gate, season_span_gate.",
        "blocking_gates": ["coverage_gate", "season_span_gate"],
        "resolution": "Continue accumulating 2026 game results. Rerun P96 when coverage reaches >=60% and >=4 months are observed.",
    },
    "CALIBRATION_BLOCKER": {
        "name": "CALIBRATION_BLOCKER",
        "description": "HIGH_FIP probability reliability not OOS-calibrated. "
                       "No calibration diagnostic exists. No refit will be run until this is explicitly commissioned.",
        "blocking_gates": ["calibration_gate"],
        "resolution": "Design and run an OOS calibration diagnostic for HIGH_FIP segment only. No refit, no production mutation.",
    },
    "LEGAL_ODDS_BLOCKER": {
        "name": "LEGAL_ODDS_BLOCKER",
        "description": "No real legal odds dataset available and validated through P81/P82 policy. "
                       "No market edge claim possible without legal odds.",
        "blocking_gates": ["odds_dataset_gate"],
        "resolution": "Acquire legal odds dataset, validate through P81/P82 pipeline before any EV/CLV work.",
    },
    "MARKET_EDGE_BLOCKER": {
        "name": "MARKET_EDGE_BLOCKER",
        "description": "No EV/CLV validation. Market edge cannot be claimed from hit_rate alone without odds context.",
        "blocking_gates": ["market_edge_gate"],
        "resolution": "Complete LEGAL_ODDS_BLOCKER first. Then design EV/CLV validation pipeline (separate phase).",
    },
    "RISK_CONTROL_BLOCKER": {
        "name": "RISK_CONTROL_BLOCKER",
        "description": "No stake/risk caps or fail-safe policy defined. Kelly criterion not computed. "
                       "No risk controls approved.",
        "blocking_gates": ["risk_control_gate"],
        "resolution": "Design and approve a risk control framework before any product consideration.",
    },
    "PRODUCT_GOVERNANCE_BLOCKER": {
        "name": "PRODUCT_GOVERNANCE_BLOCKER",
        "description": "No paper recommendation contract and no CEO production-review authorization. "
                       "Current CEO approval covers diagnostic tracking only.",
        "blocking_gates": ["recommendation_contract_gate", "production_governance_gate"],
        "resolution": "Explicit CEO authorization required for production review. Cannot self-authorize.",
    },
}


def step4_blocker_matrix() -> dict[str, Any]:
    return {
        "step": "step4_blocker_matrix",
        "blocker_count": len(BLOCKER_DEFINITIONS),
        "blockers": BLOCKER_DEFINITIONS,
        "blocker_names": list(BLOCKER_DEFINITIONS.keys()),
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Allowed next actions
# ---------------------------------------------------------------------------

ALLOWED_NEXT_ACTIONS = [
    {
        "action": "continue_accumulating_2026_coverage",
        "description": "Let the 2026 season proceed. Re-run P96 and P97 when schedule_coverage_pct reaches >=60% or >=4 months are observed.",
        "safe": True,
    },
    {
        "action": "rerun_p96_at_60pct_coverage",
        "description": "Rerun P96 drift monitor when coverage >=60%. Check if stability holds over a larger sample.",
        "safe": True,
    },
    {
        "action": "design_calibration_diagnostic_only",
        "description": "Design an OOS calibration diagnostic for HIGH_FIP. No refit, no production mutation. Diagnostic artifact only.",
        "safe": True,
    },
    {
        "action": "keep_high_fip_shadow_tracker_diagnostic_only",
        "description": "Continue HIGH_FIP diagnostic shadow tracking per P95 contract. Do not promote.",
        "safe": True,
    },
    {
        "action": "keep_mid_low_watch_only",
        "description": "MID_FIP and LOW_FIP remain watch-only. No promotion, no action.",
        "safe": True,
    },
]

PROHIBITED_NEXT_ACTIONS = [
    {
        "action": "production_promotion",
        "reason": "production_governance_gate=FAIL, CEO authorization not obtained.",
    },
    {
        "action": "recommendation_surface",
        "reason": "recommendation_contract_gate=FAIL, no legal odds, no EV/CLV validation.",
    },
    {
        "action": "odds_integration",
        "reason": "odds_dataset_gate=FAIL, no legal odds dataset validated.",
    },
    {
        "action": "ev_clv_kelly_computation",
        "reason": "market_edge_gate=FAIL, risk_control_gate=FAIL, no legal odds.",
    },
    {
        "action": "calibration_refit",
        "reason": "calibration_gate=FAIL, no OOS calibration diagnostic exists; refit not authorized.",
    },
    {
        "action": "champion_replacement",
        "reason": "production_governance_gate=FAIL, production_ready=false.",
    },
    {
        "action": "taiwan_lottery_paper_recommendation",
        "reason": "recommendation_contract_gate=FAIL, governance locks: taiwan_lottery_recommendation=false.",
    },
    {
        "action": "stake_sizing",
        "reason": "risk_control_gate=FAIL, kelly_computed=false.",
    },
]


def step5_next_actions() -> dict[str, Any]:
    return {
        "step": "step5_next_actions",
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_next_actions": PROHIBITED_NEXT_ACTIONS,
        "allowed_count": len(ALLOWED_NEXT_ACTIONS),
        "prohibited_count": len(PROHIBITED_NEXT_ACTIONS),
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6: Final classification
# ---------------------------------------------------------------------------

def step6_final_classification(
    s1: dict[str, Any],
    checklist: dict[str, Any],
    scoring: dict[str, Any],
) -> dict[str, Any]:
    if not s1["all_gates_ok"]:
        return {
            "step": "step6_final_classification",
            "final_classification": "P97_HIGH_FIP_PREFLIGHT_FAILED_VALIDATION",
            "rationale": f"Upstream verification failures: {s1['failures']}",
        }

    pass_gates = set(scoring["pass_gates"])
    fail_gates = set(scoring["fail_gates"])

    # Signal and segment must pass
    signal_ok = "prediction_signal_gate" in pass_gates
    segment_ok = "segment_scope_gate" in pass_gates

    if signal_ok and segment_ok and len(fail_gates) > 0:
        fc = "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"
        rationale = (
            f"Signal gate PASS (P94/P95/P96 all stable, HIGH_FIP hit_rate={s1['high_fip_hit_rate']:.6f}). "
            f"Segment gate PASS (HIGH_FIP diagnostic-only, MID/LOW watch-only). "
            f"Production BLOCKED by {len(fail_gates)} failing gates: "
            + ", ".join(sorted(fail_gates))
            + ". "
            f"readiness_ratio={scoring['readiness_ratio']:.4f} ({scoring['pass_count']}/{scoring['total_gates']}). "
            "No production promotion, no recommendation, no odds/EV/CLV/Kelly."
        )
    elif not signal_ok or not segment_ok:
        fc = "P97_HIGH_FIP_PREFLIGHT_PARTIAL_PASS_REQUIRES_MORE_COVERAGE"
        rationale = "Signal or segment gate did not pass. Coverage or sample limitations prevent readiness assessment."
    else:
        fc = "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"
        rationale = "All gates passed — but this state is not expected given current coverage constraints."

    return {
        "step": "step6_final_classification",
        "final_classification": fc,
        "rationale": rationale,
        "pass_gates": scoring["pass_gates"],
        "warn_gates": scoring["warn_gates"],
        "fail_gates": scoring["fail_gates"],
        "readiness_ratio": scoring["readiness_ratio"],
    }


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(result: dict) -> None:
    fc = result["final_classification"]
    s2 = result["step2_readiness_checklist"]
    s3 = result["step3_readiness_scoring"]
    s4 = result["step4_blocker_matrix"]
    s5 = result["step5_next_actions"]
    gen = result["generated_at"]

    gate_rows = "\n".join(
        f"| {g['gate']} | **{g['status']}** | {g['blocker_category'] or '—'} |"
        for g in s2["gates"]
    )

    blocker_rows = "\n".join(
        f"| `{b['name']}` | {', '.join(b['blocking_gates'])} | {b['resolution'][:80]}... |"
        for b in s4["blockers"].values()
    )

    allowed_rows = "\n".join(
        f"| `{a['action']}` | {a['description'][:80]}... |"
        for a in s5["allowed_next_actions"]
    )

    prohibited_rows = "\n".join(
        f"| `{p['action']}` | {p['reason']} |"
        for p in s5["prohibited_next_actions"]
    )

    md = f"""# P97 HIGH_FIP Production-Gate Preflight
**Generated:** {gen}
**Classification:** `{fc}`

---

## Governance

> ⚠️ **DIAGNOSTIC ONLY — PRODUCTION BLOCKED**
>
> `paper_only=true` | `diagnostic_only=true` | `production_ready=false`
> `real_bet_allowed=false` | `recommendation_allowed=false` | `product_surface_allowed=false`
> `odds_used=false` | `ev_computed=false` | `clv_computed=false` | `kelly_computed=false`

---

## Upstream Chain

| Phase | Classification |
|-------|----------------|
| P93 | `P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP` |
| P94 | `P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY` |
| P95 | `P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE` |
| P96 | `P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED` |
| **P97** | **`{fc}`** |

---

## Readiness Summary

| Metric | Value |
|--------|-------|
| total_gates | {s3['total_gates']} |
| pass_count | **{s3['pass_count']}** |
| warn_count | {s3['warn_count']} |
| fail_count | {s3['fail_count']} |
| readiness_ratio | {s3['readiness_ratio']:.4f} ({s3['pass_count']}/{s3['total_gates']}) |
| production_ready | **false** |

---

## Gate Checklist

| Gate | Status | Blocker |
|------|--------|---------|
{gate_rows}

---

## Blocker Matrix

| Blocker | Blocking Gates | Resolution |
|---------|----------------|------------|
{blocker_rows}

---

## Allowed Next Actions

| Action | Description |
|--------|-------------|
{allowed_rows}

---

## Prohibited Next Actions

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

All guards locked. Zero production exposure.

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
| live_api_calls | 0 |
| paid_api_calls | 0 |
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("P97 HIGH_FIP Production-Gate Preflight")
    print("=" * 60)

    # Step 1
    print("\n[Step 1] Upstream verification...")
    s1 = step1_upstream_verification()
    if not s1["all_gates_ok"]:
        print(f"  FAILED: {s1['failures']}")
        result = {
            "phase": "P97",
            "final_classification": "P97_HIGH_FIP_PREFLIGHT_FAILED_VALIDATION",
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

    print(f"  gates_passed: {len(s1['gates_passed'])}, failures: {len(s1['failures'])}")
    print(f"  HIGH_FIP n={s1['high_fip_n']}, hit_rate={s1['high_fip_hit_rate']:.6f}")
    print(f"  coverage: {s1['total_rows']}/{s1['schedule_total']}={s1['schedule_coverage_pct']}%")

    # Step 2
    print("\n[Step 2] Production-gate readiness checklist...")
    s2 = step2_readiness_checklist(s1)
    for g in s2["gates"]:
        print(f"  {g['gate']}: {g['status']}")

    # Step 3
    print("\n[Step 3] Readiness scoring...")
    s3 = step3_readiness_scoring(s2)
    print(f"  PASS={s3['pass_count']}, WARN={s3['warn_count']}, FAIL={s3['fail_count']}")
    print(f"  readiness_ratio={s3['readiness_ratio']:.4f} ({s3['pass_count']}/{s3['total_gates']})")

    # Step 4
    print("\n[Step 4] Blocker matrix...")
    s4 = step4_blocker_matrix()
    for name in s4["blocker_names"]:
        print(f"  {name}")

    # Step 5
    print("\n[Step 5] Allowed next actions...")
    s5 = step5_next_actions()
    print(f"  allowed={s5['allowed_count']}, prohibited={s5['prohibited_count']}")

    # Step 6
    print("\n[Step 6] Final classification...")
    s6 = step6_final_classification(s1, s2, s3)
    fc = s6["final_classification"]
    print(f"  FINAL_CLASSIFICATION: {fc}")
    print(f"  rationale: {s6['rationale'][:120]}...")

    # Assemble output
    result: dict[str, Any] = {
        "phase": "P97",
        "final_classification": fc,
        "classification_rationale": s6["rationale"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "date": "2026-05-28",
        "generated_at": datetime.now().isoformat() + "Z",
        "git_head": "73edb41",
        "step1_upstream_verification": s1,
        "step2_readiness_checklist": s2,
        "step3_readiness_scoring": s3,
        "step4_blocker_matrix": s4,
        "step5_next_actions": s5,
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
    print(f"P97 complete: {fc}")
    print("paper_only=true | diagnostic_only=true | production_ready=false")
    print("no EV / no CLV / no Kelly / no odds / no recommendation / no production")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
