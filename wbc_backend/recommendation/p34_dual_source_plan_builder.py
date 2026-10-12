"""
P34 Dual Source Plan Builder
==============================
Aggregates prediction options, odds options, and schema package into a
unified P34DualSourcePlan and determines the P34 gate.

Gate policy:
- READY if at least one prediction path AND one odds path are safe enough
  for implementation planning (even if license review is still pending).
- BLOCKED_NO_SAFE_PREDICTION_PATH if no prediction path exists.
- BLOCKED_NO_SAFE_ODDS_PATH if no odds path exists at all.
- BLOCKED_LICENSE_PROVENANCE_UNSAFE if the best odds path has an unresolved
  license concern that makes it unsafe to proceed with data acquisition.
- BLOCKED_CONTRACT_VIOLATION if PAPER_ONLY or PRODUCTION_READY guards are violated.
- "This is a plan, not data readiness."

PAPER_ONLY=True  PRODUCTION_READY=False
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    OPTION_BLOCKED_PROVENANCE,
    OPTION_BLOCKED_SCHEMA_GAP,
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    P34_BLOCKED_CONTRACT_VIOLATION,
    P34_BLOCKED_LICENSE_PROVENANCE_UNSAFE,
    P34_BLOCKED_NO_SAFE_ODDS_PATH,
    P34_BLOCKED_NO_SAFE_PREDICTION_PATH,
    P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
    PAPER_ONLY,
    PRODUCTION_READY,
    P34DualSourcePlan,
    P34GateResult,
    P34OddsAcquisitionOption,
    P34PredictionAcquisitionOption,
)
from wbc_backend.recommendation.p34_joined_input_schema_package import (
    OUT_ODDS_TEMPLATE,
    OUT_PREDICTION_TEMPLATE,
    OUT_VALIDATION_RULES,
    build_joined_input_validation_rules,
    validate_schema_templates,
    write_schema_templates,
)
from wbc_backend.recommendation.p34_prediction_source_planner import rank_prediction_options
from wbc_backend.recommendation.p34_odds_source_planner import rank_odds_options

# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

_USABLE_FOR_PLAN = frozenset(
    [
        OPTION_READY_FOR_IMPLEMENTATION_PLAN,
        OPTION_REQUIRES_MANUAL_APPROVAL,
        OPTION_REQUIRES_LICENSE_REVIEW,
    ]
)

_BLOCKED_STATUSES = frozenset(
    [OPTION_BLOCKED_PROVENANCE, OPTION_BLOCKED_SCHEMA_GAP, OPTION_REJECTED_FAKE_OR_LEAKAGE]
)


def build_dual_source_acquisition_plan(
    prediction_options: List[P34PredictionAcquisitionOption],
    odds_options: List[P34OddsAcquisitionOption],
    schema_written: bool = False,
) -> P34DualSourcePlan:
    """
    Combine prediction + odds options into a P34DualSourcePlan.
    Selects the best option from each category.
    """
    if not PAPER_ONLY:
        raise RuntimeError("P34 plan builder must run with PAPER_ONLY=True.")

    ranked_pred = rank_prediction_options(prediction_options)
    ranked_odds = rank_odds_options(odds_options)

    best_pred = ranked_pred[0] if ranked_pred else None
    best_odds = ranked_odds[0] if ranked_odds else None

    pred_status = best_pred.status if best_pred else OPTION_BLOCKED_PROVENANCE
    odds_status = best_odds.status if best_odds else OPTION_BLOCKED_PROVENANCE

    summary_parts = []
    if best_pred:
        summary_parts.append(
            f"Best prediction option: [{best_pred.option_id}] {best_pred.source_name} "
            f"(status={pred_status}, coverage={best_pred.estimated_coverage:.0%})."
        )
    if best_odds:
        summary_parts.append(
            f"Best odds option: [{best_odds.option_id}] {best_odds.source_name} "
            f"(status={odds_status}, license={best_odds.license_status})."
        )
    if schema_written:
        summary_parts.append("Schema templates written (prediction + odds import templates).")
    summary_parts.append("PAPER_ONLY=True, PRODUCTION_READY=False.")

    return P34DualSourcePlan(
        prediction_options=prediction_options,
        odds_options=odds_options,
        best_prediction_option_id=best_pred.option_id if best_pred else "",
        best_odds_option_id=best_odds.option_id if best_odds else "",
        prediction_path_status=pred_status,
        odds_path_status=odds_status,
        paper_only=True,
        production_ready=False,
        plan_summary=" ".join(summary_parts),
        season=2024,
    )


def determine_p34_gate(plan: P34DualSourcePlan) -> P34GateResult:
    """
    Apply gate policy to the plan and return a P34GateResult.

    Policy (in priority order):
    1. Contract violation (PAPER_ONLY=False or PRODUCTION_READY=True) → BLOCKED_CONTRACT_VIOLATION
    2. No usable prediction path → BLOCKED_NO_SAFE_PREDICTION_PATH
    3. No usable odds path → BLOCKED_NO_SAFE_ODDS_PATH
    4. Odds path exists but license is unclear/unsafe → BLOCKED_LICENSE_PROVENANCE_UNSAFE
    5. Both paths usable → READY
    """
    # Guard 1: contract violation
    if not plan.paper_only or plan.production_ready:
        return P34GateResult(
            gate=P34_BLOCKED_CONTRACT_VIOLATION,
            blocker_reason="Contract violation: PAPER_ONLY must be True and PRODUCTION_READY must be False.",
            paper_only=plan.paper_only,
            production_ready=plan.production_ready,
            prediction_path_status=plan.prediction_path_status,
            odds_path_status=plan.odds_path_status,
        )

    pred_usable = plan.prediction_path_status in _USABLE_FOR_PLAN
    odds_usable = plan.odds_path_status in _USABLE_FOR_PLAN

    # Guard 2: no prediction path
    if not pred_usable:
        return P34GateResult(
            gate=P34_BLOCKED_NO_SAFE_PREDICTION_PATH,
            prediction_path_status=plan.prediction_path_status,
            odds_path_status=plan.odds_path_status,
            blocker_reason=(
                f"No safe prediction acquisition path found. "
                f"Best prediction status: {plan.prediction_path_status}."
            ),
            paper_only=True,
            production_ready=False,
        )

    # Guard 3: no odds path
    if not odds_usable:
        return P34GateResult(
            gate=P34_BLOCKED_NO_SAFE_ODDS_PATH,
            prediction_path_status=plan.prediction_path_status,
            odds_path_status=plan.odds_path_status,
            blocker_reason=(
                f"No safe odds acquisition path found. "
                f"Best odds status: {plan.odds_path_status}."
            ),
            paper_only=True,
            production_ready=False,
        )

    # Guard 4: odds path exists but license needs review — document risk but READY for planning
    # (The plan itself is ready; license review is the first step of P35.)
    license_risk = ""
    if plan.odds_path_status == OPTION_REQUIRES_LICENSE_REVIEW:
        license_risk = (
            "Odds acquisition path requires license review before data can be downloaded. "
            "Do NOT download or use odds until ToS is confirmed."
        )

    return P34GateResult(
        gate=P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
        prediction_path_status=plan.prediction_path_status,
        odds_path_status=plan.odds_path_status,
        license_risk=license_risk,
        blocker_reason="",
        paper_only=True,
        production_ready=False,
        next_phase="P35_DUAL_SOURCE_IMPORT_VALIDATION",
    )


def validate_dual_source_plan(plan: P34DualSourcePlan) -> bool:
    """
    Safety validation: ensure the plan does not claim production readiness
    and has the required safety flags.
    Returns True if plan is safe, False otherwise.
    """
    if plan.production_ready:
        return False
    if not plan.paper_only:
        return False
    if plan.season != 2024:
        return False
    return True


def write_p34_outputs(
    output_dir: str,
    plan: P34DualSourcePlan,
    gate: P34GateResult,
    schema_written_files: List[str],
) -> List[str]:
    """
    Write all P34 output JSON/CSV files to output_dir.
    Returns list of written artifact paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    written: List[str] = []

    # Helper: convert dataclass to JSON-safe dict
    def _to_dict(obj) -> dict:
        if dataclasses.is_dataclass(obj):
            d = dataclasses.asdict(obj)
            # Serialize tuples as lists for JSON
            return d
        return obj

    now_str = datetime.now(timezone.utc).isoformat()

    # --- prediction_acquisition_options.json ---
    pred_opts = [_to_dict(o) for o in plan.prediction_options]
    for o in pred_opts:
        o.setdefault("paper_only", True)
        o.setdefault("production_ready", False)
    pred_opts_path = os.path.join(output_dir, "prediction_acquisition_options.json")
    with open(pred_opts_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "season": 2024,
                "paper_only": True,
                "production_ready": False,
                "generated_at": now_str,
                "options": pred_opts,
            },
            fh,
            indent=2,
        )
    written.append(pred_opts_path)

    # --- odds_acquisition_options.json ---
    odds_opts = [_to_dict(o) for o in plan.odds_options]
    for o in odds_opts:
        o.setdefault("paper_only", True)
        o.setdefault("production_ready", False)
    odds_opts_path = os.path.join(output_dir, "odds_acquisition_options.json")
    with open(odds_opts_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "season": 2024,
                "paper_only": True,
                "production_ready": False,
                "generated_at": now_str,
                "options": odds_opts,
            },
            fh,
            indent=2,
        )
    written.append(odds_opts_path)

    # --- dual_source_acquisition_plan.json ---
    plan_dict = {
        "season": plan.season,
        "paper_only": plan.paper_only,
        "production_ready": plan.production_ready,
        "generated_at": now_str,
        "best_prediction_option_id": plan.best_prediction_option_id,
        "best_odds_option_id": plan.best_odds_option_id,
        "prediction_path_status": plan.prediction_path_status,
        "odds_path_status": plan.odds_path_status,
        "plan_summary": plan.plan_summary,
        "gate": gate.gate,
        "license_risk": gate.license_risk,
    }
    plan_json_path = os.path.join(output_dir, "dual_source_acquisition_plan.json")
    with open(plan_json_path, "w", encoding="utf-8") as fh:
        json.dump(plan_dict, fh, indent=2)
    written.append(plan_json_path)

    # --- dual_source_acquisition_plan.md ---
    plan_md = _build_plan_markdown(plan, gate)
    plan_md_path = os.path.join(output_dir, "dual_source_acquisition_plan.md")
    with open(plan_md_path, "w", encoding="utf-8") as fh:
        fh.write(plan_md)
    written.append(plan_md_path)

    # --- Schema template files (already written; just record paths) ---
    written.extend(schema_written_files)

    # --- p34_gate_result.json ---
    gate_dict = {
        "gate": gate.gate,
        "season": gate.season,
        "prediction_path_status": gate.prediction_path_status,
        "odds_path_status": gate.odds_path_status,
        "license_risk": gate.license_risk,
        "blocker_reason": gate.blocker_reason,
        "paper_only": gate.paper_only,
        "production_ready": gate.production_ready,
        "next_phase": gate.next_phase,
        "artifacts": written,
    }
    gate_path = os.path.join(output_dir, "p34_gate_result.json")
    with open(gate_path, "w", encoding="utf-8") as fh:
        json.dump(gate_dict, fh, indent=2)
    written.append(gate_path)

    return written


def _build_plan_markdown(plan: P34DualSourcePlan, gate: P34GateResult) -> str:
    """Build a human-readable Markdown summary of the P34 plan."""
    lines = [
        "# P34 Dual Source Acquisition Plan",
        "",
        f"**Gate**: `{gate.gate}`",
        f"**Season**: {plan.season}",
        f"**PAPER_ONLY**: {plan.paper_only}  |  **PRODUCTION_READY**: {plan.production_ready}",
        "",
        "## Prediction Acquisition",
        f"- **Best option**: `{plan.best_prediction_option_id}`",
        f"- **Path status**: `{plan.prediction_path_status}`",
        "",
    ]
    for opt in plan.prediction_options:
        lines.append(f"### [{opt.option_id}] {opt.source_name}")
        lines.append(f"- Status: `{opt.status}`")
        lines.append(f"- Leakage risk: {opt.leakage_risk}")
        lines.append(f"- Coverage: {opt.estimated_coverage:.0%}")
        lines.append(f"- Notes: {opt.notes}")
        lines.append("")

    lines += [
        "## Odds Acquisition",
        f"- **Best option**: `{plan.best_odds_option_id}`",
        f"- **Path status**: `{plan.odds_path_status}`",
    ]
    if gate.license_risk:
        lines.append(f"- **License risk**: {gate.license_risk}")
    lines.append("")
    for opt in plan.odds_options:
        lines.append(f"### [{opt.option_id}] {opt.source_name}")
        lines.append(f"- Status: `{opt.status}`")
        lines.append(f"- License: {opt.license_status}")
        lines.append(f"- Coverage: {opt.estimated_coverage:.0%}")
        lines.append(f"- Notes: {opt.notes}")
        lines.append("")

    lines += [
        "## Summary",
        plan.plan_summary,
        "",
        f"**Next phase**: `{gate.next_phase}`",
    ]

    return "\n".join(lines) + "\n"
