"""
wbc_backend/recommendation/p29_density_expansion_planner.py

Aggregates density diagnosis, policy sensitivity, and source coverage scan
results into a unified P29 density expansion plan and gate decision.

Research only. paper_only=True. production_ready=False.
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29DensityDiagnosis,
    P29DensityExpansionGateResult,
    P29DensityExpansionPlan,
    P29PolicySensitivityCandidate,
    P29SourceCoverageCandidate,
    P29_BLOCKED_NO_SAFE_EXPANSION_PATH,
    P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY,
    P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT,
    P29_DENSITY_EXPANSION_PLAN_READY,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
    DENSITY_EXPANSION_PLAN_FEASIBLE,
    DENSITY_EXPANSION_SOURCE_PATH_FOUND,
    DENSITY_EXPANSION_POLICY_PATH_RISKY,
    DENSITY_EXPANSION_NO_PATH_FOUND,
    DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE,
)


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


def determine_p29_gate(plan: "P29DensityExpansionPlan") -> str:
    """
    Determine P29 gate based on the assembled plan.

    Priority (in order):
    1. Source expansion can reach ≥1500 safely (safe candidates with rows) → PLAN_READY
    2. Policy sensitivity reaches ≥1500 with no risk flags              → PLAN_READY
    3. Policy sensitivity reaches ≥1500 but risk flags high              → POLICY_SENSITIVITY_TOO_RISKY
    4. No safe source expansion path found                               → SOURCE_COVERAGE_INSUFFICIENT
    5. Neither source nor policy can reach target                        → NO_SAFE_EXPANSION_PATH
    """
    source_can_reach = (
        plan.n_source_candidates_safe > 0
        and plan.source_expansion_estimated_entries >= plan.target_active_entries
    )
    policy_can_reach = plan.best_policy_candidate_active_entries >= plan.target_active_entries

    if source_can_reach:
        return P29_DENSITY_EXPANSION_PLAN_READY

    if policy_can_reach:
        # Check risk — we look for HIGH_DRAWDOWN or LOW_EDGE_THRESHOLD flags
        # These are embedded in the audit_status field during planning
        if plan.audit_status == DENSITY_EXPANSION_POLICY_PATH_RISKY:
            return P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY
        return P29_DENSITY_EXPANSION_PLAN_READY

    if not source_can_reach:
        if plan.n_source_candidates_safe == 0:
            if policy_can_reach:
                return P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY
            return P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT

    return P29_BLOCKED_NO_SAFE_EXPANSION_PATH


def _select_audit_status(
    source_feasible: bool,
    policy_can_reach: bool,
    policy_has_risk_flags: bool,
) -> str:
    if source_feasible:
        return DENSITY_EXPANSION_SOURCE_PATH_FOUND
    if policy_can_reach and not policy_has_risk_flags:
        return DENSITY_EXPANSION_PLAN_FEASIBLE
    if policy_can_reach and policy_has_risk_flags:
        return DENSITY_EXPANSION_POLICY_PATH_RISKY
    return DENSITY_EXPANSION_BLOCKED_INSUFFICIENT_SOURCE


def _build_recommended_next_action(
    gate: str,
    best_policy_id: str,
    best_policy_active: int,
    source_candidates_safe: int,
    source_estimated_entries: int,
) -> str:
    if gate == P29_DENSITY_EXPANSION_PLAN_READY:
        if source_candidates_safe > 0:
            return (
                f"PROCEED: Integrate {source_candidates_safe} additional source(s) estimated to "
                f"yield ~{source_estimated_entries} new active entries. Run P25 pipeline on new source."
            )
        return (
            f"PROCEED_EXPLORATORY: Policy candidate {best_policy_id!r} reaches "
            f"{best_policy_active} active entries. Flag as EXPLORATORY before P30."
        )
    if gate == P29_BLOCKED_POLICY_SENSITIVITY_TOO_RISKY:
        return (
            f"BLOCKED: Policy candidate {best_policy_id!r} reaches {best_policy_active} entries "
            "but has high-risk flags (HIGH_DRAWDOWN or LOW_EDGE_THRESHOLD). "
            "Acquire additional historical data to reach 1,500 without policy loosening."
        )
    if gate == P29_BLOCKED_SOURCE_COVERAGE_INSUFFICIENT:
        return (
            "BLOCKED: No safe source expansion found and no policy candidate reaches target. "
            "Acquire additional MLB historical seasons (pre-2025 or 2026 when available) "
            "and re-run P22→P25 pipeline on new data."
        )
    return (
        "BLOCKED: Neither source expansion nor policy sensitivity can safely reach 1,500 entries. "
        "Recommend acquiring additional season data and revisiting after P25 pipeline re-run."
    )


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------


def build_density_expansion_plan(
    diagnosis: P29DensityDiagnosis,
    policy_candidates: List[P29PolicySensitivityCandidate],
    source_coverage_candidates: List[P29SourceCoverageCandidate],
    source_summary: Dict[str, Any],
    source_estimate: Dict[str, Any],
) -> P29DensityExpansionPlan:
    """
    Build the final P29DensityExpansionPlan from all sub-analyses.
    """
    # Best policy candidate
    best_policy = policy_candidates[0] if policy_candidates else None
    best_policy_id = best_policy.policy_id if best_policy else "N/A"
    best_policy_active = best_policy.n_active_entries if best_policy else 0
    policy_has_risk = bool(best_policy.risk_flags) if best_policy else True

    source_feasible = source_summary.get("source_expansion_feasible", False)
    source_estimated = source_estimate.get("estimated_new_active_entries_safe", 0)

    policy_can_reach = best_policy_active >= TARGET_ACTIVE_ENTRIES_DEFAULT

    audit_status = _select_audit_status(source_feasible, policy_can_reach, policy_has_risk)

    # Build a temporary plan to get gate (we re-create below with gate filled in)
    _temp_plan = P29DensityExpansionPlan(
        current_active_entries=diagnosis.current_active_entries,
        target_active_entries=diagnosis.target_active_entries,
        density_gap=diagnosis.density_gap,
        current_active_per_day=diagnosis.current_active_per_day,
        target_active_per_day=diagnosis.target_active_per_day,
        available_true_date_rows=diagnosis.total_source_rows,
        current_policy_id="e0p0500_s0p0025_k0p10_o2p50",
        policy_thresholds_tested=len(policy_candidates),
        best_policy_candidate_id=best_policy_id,
        best_policy_candidate_active_entries=best_policy_active,
        source_expansion_estimated_entries=source_estimated,
        n_source_candidates_found=len(source_coverage_candidates),
        n_source_candidates_safe=source_summary.get("n_candidates_safe", 0),
        recommended_next_action="",
        expansion_feasibility_note="",
        paper_only=True,
        production_ready=False,
        audit_status=audit_status,
        p29_gate=P29_BLOCKED_NO_SAFE_EXPANSION_PATH,  # placeholder
    )

    gate = determine_p29_gate(_temp_plan)
    recommended_action = _build_recommended_next_action(
        gate, best_policy_id, best_policy_active,
        source_summary.get("n_candidates_safe", 0),
        source_estimated,
    )

    feasibility_note = (
        f"Diagnosis: {diagnosis.diagnosis_note} "
        f"Policy analysis: {len(policy_candidates)} configurations tested; "
        f"best reaches {best_policy_active} active entries. "
        f"Source scan: {len(source_coverage_candidates)} candidates found, "
        f"{source_summary.get('n_candidates_safe', 0)} safe. "
        f"Recommended gate: {gate}."
    )

    return P29DensityExpansionPlan(
        current_active_entries=diagnosis.current_active_entries,
        target_active_entries=diagnosis.target_active_entries,
        density_gap=diagnosis.density_gap,
        current_active_per_day=diagnosis.current_active_per_day,
        target_active_per_day=diagnosis.target_active_per_day,
        available_true_date_rows=diagnosis.total_source_rows,
        current_policy_id="e0p0500_s0p0025_k0p10_o2p50",
        policy_thresholds_tested=len(policy_candidates),
        best_policy_candidate_id=best_policy_id,
        best_policy_candidate_active_entries=best_policy_active,
        source_expansion_estimated_entries=source_estimated,
        n_source_candidates_found=len(source_coverage_candidates),
        n_source_candidates_safe=source_summary.get("n_candidates_safe", 0),
        recommended_next_action=recommended_action,
        expansion_feasibility_note=feasibility_note,
        paper_only=True,
        production_ready=False,
        audit_status=audit_status,
        p29_gate=gate,
    )


def validate_density_expansion_plan(plan: P29DensityExpansionPlan) -> bool:
    """
    Validate plan invariants. Returns True if plan passes all checks.
    Raises ValueError if any check fails.
    """
    if not plan.paper_only:
        raise ValueError("plan.paper_only must be True")
    if plan.production_ready:
        raise ValueError("plan.production_ready must be False")
    if plan.current_active_entries < 0:
        raise ValueError("current_active_entries cannot be negative")
    if plan.target_active_entries <= 0:
        raise ValueError("target_active_entries must be positive")
    if plan.density_gap != max(0, plan.target_active_entries - plan.current_active_entries):
        raise ValueError("density_gap does not match target - current")
    if plan.policy_thresholds_tested < 0:
        raise ValueError("policy_thresholds_tested cannot be negative")
    return True


# ---------------------------------------------------------------------------
# Gate result builder
# ---------------------------------------------------------------------------


def build_gate_result(plan: P29DensityExpansionPlan) -> P29DensityExpansionGateResult:
    """Build the final P29 gate result from the expansion plan."""
    is_blocked = plan.p29_gate.startswith("P29_BLOCKED")
    blocker = plan.p29_gate if is_blocked else "none"
    return P29DensityExpansionGateResult(
        p29_gate=plan.p29_gate,
        current_active_entries=plan.current_active_entries,
        target_active_entries=plan.target_active_entries,
        density_gap=plan.density_gap,
        best_policy_candidate_active_entries=plan.best_policy_candidate_active_entries,
        source_expansion_estimated_entries=plan.source_expansion_estimated_entries,
        recommended_next_action=plan.recommended_next_action,
        audit_status=plan.audit_status,
        blocker_reason=blocker,
        paper_only=True,
        production_ready=False,
    )


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------


def write_p29_outputs(
    output_dir: Path,
    gate_result: P29DensityExpansionGateResult,
    diagnosis: P29DensityDiagnosis,
    policy_candidates: List[P29PolicySensitivityCandidate],
    policy_summary: Dict[str, Any],
    source_candidates: List[P29SourceCoverageCandidate],
    source_summary: Dict[str, Any],
    source_estimate: Dict[str, Any],
    plan: P29DensityExpansionPlan,
) -> None:
    """
    Write all 8 P29 output files to output_dir.

    Files written:
    1. density_diagnosis.json
    2. density_diagnosis.md
    3. policy_sensitivity_results.csv
    4. policy_sensitivity_summary.json
    5. source_coverage_expansion.json
    6. source_coverage_expansion.md
    7. density_expansion_plan.json
    8. p29_gate_result.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    # 1. density_diagnosis.json
    diag_dict = {
        "generated_at": ts,
        "current_active_entries": diagnosis.current_active_entries,
        "target_active_entries": diagnosis.target_active_entries,
        "density_gap": diagnosis.density_gap,
        "current_active_per_day": diagnosis.current_active_per_day,
        "target_active_per_day": diagnosis.target_active_per_day,
        "total_source_rows": diagnosis.total_source_rows,
        "active_conversion_rate": diagnosis.active_conversion_rate,
        "n_blocked_edge": diagnosis.n_blocked_edge,
        "n_blocked_odds": diagnosis.n_blocked_odds,
        "n_blocked_unknown": diagnosis.n_blocked_unknown,
        "n_dates_zero_active": diagnosis.n_dates_zero_active,
        "n_dates_sparse_active": diagnosis.n_dates_sparse_active,
        "primary_blocker": diagnosis.primary_blocker,
        "diagnosis_note": diagnosis.diagnosis_note,
        "paper_only": diagnosis.paper_only,
        "production_ready": diagnosis.production_ready,
    }
    (output_dir / "density_diagnosis.json").write_text(
        json.dumps(diag_dict, indent=2), encoding="utf-8"
    )

    # 2. density_diagnosis.md
    md_diag = textwrap.dedent(f"""\
    # P29 Density Diagnosis Report

    **Generated**: {ts}
    **Paper Only**: {diagnosis.paper_only}
    **Production Ready**: {diagnosis.production_ready}

    ## Current Status

    | Metric | Value |
    |---|---|
    | Current Active Entries | {diagnosis.current_active_entries} |
    | Target Active Entries | {diagnosis.target_active_entries} |
    | Density Gap | {diagnosis.density_gap} |
    | Active / Day (current) | {diagnosis.current_active_per_day} |
    | Active / Day (target) | {diagnosis.target_active_per_day} |
    | Total Source Rows | {diagnosis.total_source_rows} |
    | Conversion Rate | {diagnosis.active_conversion_rate:.1%} |

    ## Gate Reason Breakdown

    | Reason | Count |
    |---|---|
    | Active (eligible) | {diagnosis.current_active_entries} |
    | Blocked (edge below threshold) | {diagnosis.n_blocked_edge} |
    | Blocked (odds above cap) | {diagnosis.n_blocked_odds} |
    | Blocked (unknown) | {diagnosis.n_blocked_unknown} |

    ## Primary Blocker

    **{diagnosis.primary_blocker}**

    {diagnosis.diagnosis_note}
    """)
    (output_dir / "density_diagnosis.md").write_text(md_diag, encoding="utf-8")

    # 3. policy_sensitivity_results.csv
    if policy_candidates:
        rows = [
            {
                "policy_id": c.policy_id,
                "edge_threshold": c.edge_threshold,
                "odds_decimal_max": c.odds_decimal_max,
                "max_stake_cap": c.max_stake_cap,
                "kelly_fraction": c.kelly_fraction,
                "n_active_entries": c.n_active_entries,
                "active_entry_lift_vs_current": c.active_entry_lift_vs_current,
                "estimated_total_stake_units": c.estimated_total_stake_units,
                "hit_rate": c.hit_rate,
                "roi_units": c.roi_units,
                "max_drawdown_pct": c.max_drawdown_pct,
                "risk_flags": c.risk_flags,
                "exploratory_only": c.exploratory_only,
                "is_deployment_ready": c.is_deployment_ready,
            }
            for c in policy_candidates
        ]
        pd.DataFrame(rows).to_csv(
            output_dir / "policy_sensitivity_results.csv", index=False
        )
    else:
        pd.DataFrame().to_csv(output_dir / "policy_sensitivity_results.csv", index=False)

    # 4. policy_sensitivity_summary.json
    policy_summary_out = dict(policy_summary)
    policy_summary_out["generated_at"] = ts
    policy_summary_out["paper_only"] = True
    policy_summary_out["production_ready"] = False
    (output_dir / "policy_sensitivity_summary.json").write_text(
        json.dumps(policy_summary_out, indent=2), encoding="utf-8"
    )

    # 5. source_coverage_expansion.json
    src_dict = {
        "generated_at": ts,
        "summary": source_summary,
        "sample_gain_estimate": source_estimate,
        "candidates": [
            {
                "source_path": c.source_path,
                "source_type": c.source_type,
                "date_range_start": c.date_range_start,
                "date_range_end": c.date_range_end,
                "estimated_new_rows": c.estimated_new_rows,
                "has_required_columns": c.has_required_columns,
                "has_y_true": c.has_y_true,
                "has_game_id": c.has_game_id,
                "has_odds": c.has_odds,
                "is_safe_to_use": c.is_safe_to_use,
                "coverage_note": c.coverage_note,
            }
            for c in source_candidates
        ],
        "paper_only": True,
        "production_ready": False,
    }
    (output_dir / "source_coverage_expansion.json").write_text(
        json.dumps(src_dict, indent=2), encoding="utf-8"
    )

    # 6. source_coverage_expansion.md
    safe_count = source_summary.get("n_candidates_safe", 0)
    scanned_count = source_summary.get("n_candidates_scanned", 0)
    new_rows_safe = source_estimate.get("estimated_new_rows_safe", 0)
    new_active_safe = source_estimate.get("estimated_new_active_entries_safe", 0)
    md_src = textwrap.dedent(f"""\
    # P29 Source Coverage Expansion Scan

    **Generated**: {ts}
    **Paper Only**: True
    **Production Ready**: False

    ## Scan Summary

    | Metric | Value |
    |---|---|
    | Candidates Scanned | {scanned_count} |
    | Safe to Use Immediately | {safe_count} |
    | Estimated New Rows (safe) | {new_rows_safe} |
    | Estimated New Active Entries | {new_active_safe} |

    ## Recommendation

    {source_summary.get("recommendation", "N/A")}

    ## Candidates

    """)
    for c in source_candidates:
        md_src += f"- **{c.source_type}**: `{c.source_path}`\n"
        md_src += f"  - Safe: {c.is_safe_to_use}, Schema OK: {c.has_required_columns}\n"
        md_src += f"  - Est. new rows: {c.estimated_new_rows}\n"
        md_src += f"  - Note: {c.coverage_note}\n\n"
    (output_dir / "source_coverage_expansion.md").write_text(md_src, encoding="utf-8")

    # 7. density_expansion_plan.json
    plan_dict = {
        "generated_at": ts,
        "p29_gate": plan.p29_gate,
        "audit_status": plan.audit_status,
        "current_active_entries": plan.current_active_entries,
        "target_active_entries": plan.target_active_entries,
        "density_gap": plan.density_gap,
        "current_active_per_day": plan.current_active_per_day,
        "target_active_per_day": plan.target_active_per_day,
        "available_true_date_rows": plan.available_true_date_rows,
        "current_policy_id": plan.current_policy_id,
        "policy_thresholds_tested": plan.policy_thresholds_tested,
        "best_policy_candidate_id": plan.best_policy_candidate_id,
        "best_policy_candidate_active_entries": plan.best_policy_candidate_active_entries,
        "source_expansion_estimated_entries": plan.source_expansion_estimated_entries,
        "n_source_candidates_found": plan.n_source_candidates_found,
        "n_source_candidates_safe": plan.n_source_candidates_safe,
        "recommended_next_action": plan.recommended_next_action,
        "expansion_feasibility_note": plan.expansion_feasibility_note,
        "paper_only": plan.paper_only,
        "production_ready": plan.production_ready,
    }
    (output_dir / "density_expansion_plan.json").write_text(
        json.dumps(plan_dict, indent=2), encoding="utf-8"
    )

    # 8. p29_gate_result.json
    gate_dict = {
        "generated_at": ts,
        "p29_gate": gate_result.p29_gate,
        "current_active_entries": gate_result.current_active_entries,
        "target_active_entries": gate_result.target_active_entries,
        "density_gap": gate_result.density_gap,
        "best_policy_candidate_active_entries": gate_result.best_policy_candidate_active_entries,
        "source_expansion_estimated_entries": gate_result.source_expansion_estimated_entries,
        "recommended_next_action": gate_result.recommended_next_action,
        "audit_status": gate_result.audit_status,
        "blocker_reason": gate_result.blocker_reason,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
    }
    (output_dir / "p29_gate_result.json").write_text(
        json.dumps(gate_dict, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Run orchestration (called by CLI)
# ---------------------------------------------------------------------------


def run_p29_density_expansion_plan(
    p27_dir: Path,
    p25_dir: Path,
    scan_base_paths: List[Path],
    output_dir: Path,
    target_active_entries: int = TARGET_ACTIVE_ENTRIES_DEFAULT,
) -> P29DensityExpansionGateResult:
    """
    Full P29 planning run:
    1. Load P27 date results → density diagnosis
    2. Simulate policy grid on P25 slices → sensitivity candidates
    3. Scan additional sources → coverage candidates
    4. Build expansion plan → gate result
    5. Write 8 output files
    """
    from wbc_backend.recommendation.p29_density_diagnosis_analyzer import (
        load_p27_date_results,
        summarize_density_diagnosis,
    )
    from wbc_backend.recommendation.p29_policy_sensitivity_simulator import (
        rank_policy_candidates,
        simulate_policy_density_on_true_date_slices,
        summarize_policy_candidate,
    )
    from wbc_backend.recommendation.p29_source_coverage_expansion_scanner import (
        build_source_coverage_candidates,
        estimate_sample_gain_from_source_expansion,
        scan_additional_true_date_sources,
        summarize_source_expansion_options,
    )

    # Step 1: Density diagnosis
    date_results_path = p27_dir / "date_results.csv"
    if not date_results_path.exists():
        raise FileNotFoundError(f"P27 date_results.csv not found: {date_results_path}")
    date_results_df = load_p27_date_results(date_results_path)
    diagnosis = summarize_density_diagnosis(date_results_df, p25_dir, target_active_entries)

    # Step 2: Policy sensitivity
    policy_candidates_raw = simulate_policy_density_on_true_date_slices(p25_dir)
    policy_candidates = rank_policy_candidates(policy_candidates_raw)
    policy_summary = summarize_policy_candidate(policy_candidates)

    # Step 3: Source coverage scan
    raw_source_candidates = scan_additional_true_date_sources(
        scan_base_paths, current_p25_dir=p25_dir
    )
    source_coverage_candidates = build_source_coverage_candidates(raw_source_candidates)
    source_summary = summarize_source_expansion_options(raw_source_candidates)
    source_estimate = estimate_sample_gain_from_source_expansion(raw_source_candidates)

    # Step 4: Build plan and gate
    plan = build_density_expansion_plan(
        diagnosis, policy_candidates, source_coverage_candidates,
        source_summary, source_estimate,
    )
    validate_density_expansion_plan(plan)
    gate_result = build_gate_result(plan)

    # Step 5: Write outputs
    write_p29_outputs(
        output_dir=output_dir,
        gate_result=gate_result,
        diagnosis=diagnosis,
        policy_candidates=policy_candidates,
        policy_summary=policy_summary,
        source_candidates=source_coverage_candidates,
        source_summary=source_summary,
        source_estimate=source_estimate,
        plan=plan,
    )

    return gate_result
