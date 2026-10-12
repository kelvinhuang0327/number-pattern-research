"""P35 Dual Source Validation Builder

Aggregates odds license validation, prediction rebuild feasibility, and
validator specs into a unified P35DualSourceValidationSummary.
Determines the P35 gate decision and writes all output artifacts.

Gate priority order (from task spec):
1. Odds license not approved → P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
2. Odds source not provided  → P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED
3. Feature pipeline missing  → P35_BLOCKED_FEATURE_PIPELINE_MISSING
4. Prediction rebuild not feasible → P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE
5. All clear → P35_DUAL_SOURCE_IMPORT_VALIDATION_READY

HARD GUARDS:
- PAPER_ONLY = True always.
- PRODUCTION_READY = False always.
- No joined input may be marked ready in P35.
- No predictions or odds are created here.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_READY,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    LICENSE_APPROVED_INTERNAL_RESEARCH,
    LICENSE_BLOCKED_NOT_APPROVED,
    PAPER_ONLY,
    PRODUCTION_READY,
    P35_BLOCKED_CONTRACT_VIOLATION,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
    VALIDATION_BLOCKED_LICENSE,
    VALIDATION_BLOCKED_SOURCE_MISSING,
    P35DualSourceValidationSummary,
    P35GateResult,
    P35OddsLicenseValidationResult,
    P35PredictionRebuildFeasibilityResult,
)

logger = logging.getLogger(__name__)

# Next-phase determination constants
_NEXT_PHASE_ODDS_BLOCKED = "P36_ODDS_APPROVAL_RECORD_AND_MANUAL_LICENSED_ODDS_IMPORT_GATE"
_NEXT_PHASE_PREDICTION_BLOCKED = "P36_2024_OOF_FEATURE_PIPELINE_FEASIBILITY_REPAIR"
_NEXT_PHASE_DUAL_BLOCKED = "P36_DUAL_BLOCKER_RESOLUTION_PLAN"
_NEXT_PHASE_READY = "P36_BUILD_IMPORT_VALIDATORS_AND_JOINED_INPUT"

# Feasibility statuses that are NOT blocked (allow plan to proceed)
_FEASIBILITY_ACCEPTABLE = frozenset({
    FEASIBILITY_READY,
    FEASIBILITY_REQUIRES_P36_IMPLEMENTATION,
    FEASIBILITY_BLOCKED_ADAPTER_MISSING,  # pipeline exists, adapter needed
})

# Feasibility statuses that are hard-blocked
_FEASIBILITY_BLOCKED = frozenset({
    FEASIBILITY_BLOCKED_PIPELINE_MISSING,
    FEASIBILITY_BLOCKED_LEAKAGE_RISK,
})


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def build_dual_source_validation_summary(
    odds_validation: P35OddsLicenseValidationResult,
    prediction_feasibility: P35PredictionRebuildFeasibilityResult,
    validator_specs_written: bool,
) -> P35DualSourceValidationSummary:
    """Aggregate validation results into a unified summary.

    Does NOT determine the gate — call determine_p35_gate() separately.
    """
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"

    if odds_validation.production_ready or not odds_validation.paper_only:
        gate = P35_BLOCKED_CONTRACT_VIOLATION
    else:
        gate = ""  # placeholder; determine_p35_gate fills this

    odds_license_status = odds_validation.license_status
    odds_source_status = (
        "source_not_provided"
        if not odds_validation.approval_record_found and not odds_validation.implementation_ready
        else odds_validation.license_status
    )
    pred_feasibility_status = prediction_feasibility.feasibility_status
    feature_pipeline_status = (
        "found" if prediction_feasibility.feature_pipeline_found else "not_found"
    )

    blockers: List[str] = []
    if not odds_validation.implementation_ready:
        blockers.append(odds_validation.blocker_reason)
    if prediction_feasibility.feasibility_status in _FEASIBILITY_BLOCKED:
        blockers.append(prediction_feasibility.blocker_reason)

    # Recommended next action
    odds_blocked = not odds_validation.implementation_ready
    pred_blocked = prediction_feasibility.feasibility_status in _FEASIBILITY_BLOCKED

    if odds_blocked and pred_blocked:
        next_phase = _NEXT_PHASE_DUAL_BLOCKED
        rec_action = (
            "Both odds license and prediction pipeline are blocked. "
            "P36 must address dual blockers: (1) obtain odds approval record, "
            "(2) build 2024 feature engineering adapter."
        )
    elif odds_blocked:
        next_phase = _NEXT_PHASE_ODDS_BLOCKED
        rec_action = (
            "Obtain odds license approval: review sportsbookreviewsonline.com ToS, "
            "create approval_record.json, then re-run P35 with --odds-approval-record."
        )
    elif pred_blocked:
        next_phase = _NEXT_PHASE_PREDICTION_BLOCKED
        rec_action = (
            "Build 2024 feature engineering adapter for Retrosheet P32 game log format."
        )
    else:
        next_phase = _NEXT_PHASE_READY
        rec_action = "Proceed to P36: build import validators and joined input."

    plan_summary = (
        f"PAPER_ONLY=True | season=2024 | validator_specs_written={validator_specs_written}\n"
        f"odds_license_status: {odds_license_status}\n"
        f"odds_source_status:  {odds_source_status}\n"
        f"prediction_feasibility: {pred_feasibility_status}\n"
        f"feature_pipeline: {feature_pipeline_status}\n"
        f"blockers: {len(blockers)}\n"
        f"recommended_next: {next_phase}"
    )

    return P35DualSourceValidationSummary(
        odds_license_status=odds_license_status,
        odds_source_status=odds_source_status,
        prediction_feasibility_status=pred_feasibility_status,
        feature_pipeline_status=feature_pipeline_status,
        validator_specs_written=validator_specs_written,
        gate=gate or "PENDING",
        blocker_reasons=blockers,
        paper_only=True,
        production_ready=False,
        season=2024,
        plan_summary=plan_summary,
        recommended_next_action=rec_action,
    )


# ---------------------------------------------------------------------------
# Gate determiner
# ---------------------------------------------------------------------------


def determine_p35_gate(summary: P35DualSourceValidationSummary) -> P35GateResult:
    """Determine the P35 gate from the validation summary.

    Priority order (strict):
    1. CONTRACT_VIOLATION if production_ready or not paper_only
    2. BLOCKED_ODDS_LICENSE_NOT_APPROVED if odds license is not approved
    3. BLOCKED_ODDS_SOURCE_NOT_PROVIDED if odds source not provided
    4. BLOCKED_FEATURE_PIPELINE_MISSING if no pipeline exists
    5. BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE if pipeline blocked
    6. DUAL_SOURCE_IMPORT_VALIDATION_READY
    """
    if summary.production_ready or not summary.paper_only:
        gate = P35_BLOCKED_CONTRACT_VIOLATION
        blocker = "PAPER_ONLY must be True and PRODUCTION_READY must be False."
        next_phase = "HALT_CONTRACT_VIOLATION"
        license_risk = "CONTRACT_VIOLATION"
    elif summary.odds_license_status == LICENSE_BLOCKED_NOT_APPROVED:
        gate = P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
        blocker = (
            "Odds license is not approved. No odds may be downloaded until "
            "explicit approval record is provided."
        )
        next_phase = _NEXT_PHASE_ODDS_BLOCKED
        license_risk = "HIGH — odds cannot be imported without license approval"
    elif summary.odds_source_status == "source_not_provided":
        gate = P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED
        blocker = "Odds source has not been provided."
        next_phase = _NEXT_PHASE_ODDS_BLOCKED
        license_risk = "HIGH — odds source unknown"
    elif summary.feature_pipeline_status == "not_found":
        gate = P35_BLOCKED_FEATURE_PIPELINE_MISSING
        blocker = "No feature engineering or model training pipeline found."
        next_phase = _NEXT_PHASE_PREDICTION_BLOCKED
        license_risk = "N/A"
    elif summary.prediction_feasibility_status in _FEASIBILITY_BLOCKED:
        gate = P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE
        blocker = (
            f"Prediction rebuild not feasible: {summary.prediction_feasibility_status}"
        )
        next_phase = _NEXT_PHASE_PREDICTION_BLOCKED
        license_risk = "N/A"
    else:
        gate = P35_DUAL_SOURCE_IMPORT_VALIDATION_READY
        blocker = ""
        next_phase = _NEXT_PHASE_READY
        license_risk = (
            "Medium — odds license review still required before data download."
            if summary.odds_license_status != LICENSE_APPROVED_INTERNAL_RESEARCH
            else ""
        )

    summary.gate = gate

    return P35GateResult(
        gate=gate,
        odds_license_status=summary.odds_license_status,
        odds_source_status=summary.odds_source_status,
        prediction_feasibility_status=summary.prediction_feasibility_status,
        feature_pipeline_status=summary.feature_pipeline_status,
        blocker_reason=blocker,
        license_risk=license_risk,
        paper_only=True,
        production_ready=False,
        season=2024,
        next_phase=next_phase,
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_p35_summary(summary: P35DualSourceValidationSummary) -> bool:
    """Return True if summary is internally consistent and valid."""
    if summary.production_ready:
        return False
    if not summary.paper_only:
        return False
    if summary.season != 2024:
        return False
    return True


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------


def _build_validation_markdown(
    summary: P35DualSourceValidationSummary,
    gate: P35GateResult,
    odds_validation: P35OddsLicenseValidationResult,
    prediction_feasibility: P35PredictionRebuildFeasibilityResult,
) -> str:
    """Build markdown content for the P35 validation summary."""
    gate_emoji = "✅" if gate.gate == P35_DUAL_SOURCE_IMPORT_VALIDATION_READY else "⛔"
    lines = [
        "# P35 Dual Source Import Validation Summary",
        "",
        f"**Gate**: `{gate.gate}` {gate_emoji}",
        f"**Season**: {summary.season}  |  **PAPER_ONLY**: {summary.paper_only}  |  **PRODUCTION_READY**: {summary.production_ready}",
        "",
        "## Odds License / Provenance",
        "",
        f"- **License status**: `{gate.odds_license_status}`",
        f"- **Source status**: `{gate.odds_source_status}`",
        f"- **Approval record found**: {odds_validation.approval_record_found}",
        f"- **Schema valid**: {odds_validation.schema_status}",
        f"- **Blocker**: {odds_validation.blocker_reason or 'none'}",
        "",
        "## Prediction Rebuild Feasibility",
        "",
        f"- **Status**: `{gate.prediction_feasibility_status}`",
        f"- **Feature pipeline found**: {prediction_feasibility.feature_pipeline_found}",
        f"- **Model training found**: {prediction_feasibility.model_training_found}",
        f"- **OOF generation found**: {prediction_feasibility.oof_generation_found}",
        f"- **Leakage guard found**: {prediction_feasibility.leakage_guard_found}",
        f"- **Time-aware split found**: {prediction_feasibility.time_aware_split_found}",
        f"- **2024 adapter found**: {prediction_feasibility.adapter_for_2024_format_found}",
        f"- **Blocker**: {prediction_feasibility.blocker_reason}",
        "",
        "## Import Validator Specs",
        "",
        f"- **Validator specs written**: {summary.validator_specs_written}",
        "- `odds_import_validator_spec.json`",
        "- `prediction_import_validator_spec.json`",
        "",
        "## Gate Decision",
        "",
        f"```\ngate: {gate.gate}\nblocker: {gate.blocker_reason}\nlicense_risk: {gate.license_risk}\nnext_phase: {gate.next_phase}\n```",
        "",
        "## Recommended Next Action",
        "",
        f"{summary.recommended_next_action}",
        "",
        "---",
        "",
        f"`{gate.gate}`",
        "",
    ]
    return "\n".join(lines)


def write_p35_outputs(
    output_dir: str,
    summary: P35DualSourceValidationSummary,
    gate: P35GateResult,
    odds_validation: P35OddsLicenseValidationResult,
    prediction_feasibility: P35PredictionRebuildFeasibilityResult,
    validator_spec_files: List[str],
) -> List[str]:
    """Write all P35 output artifacts.

    Returns list of written file paths.
    """
    if not PAPER_ONLY:
        raise RuntimeError("PAPER_ONLY must be True; refusing to write outputs.")
    if PRODUCTION_READY:
        raise RuntimeError("PRODUCTION_READY must be False; refusing to write outputs.")

    os.makedirs(output_dir, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    written: List[str] = []

    # 1. odds_license_validation.json
    odds_path = os.path.join(output_dir, "odds_license_validation.json")
    odds_data: Dict[str, Any] = {
        "source_type": odds_validation.source_type,
        "source_name": odds_validation.source_name,
        "source_path_or_url": odds_validation.source_path_or_url,
        "license_status": odds_validation.license_status,
        "provenance_status": odds_validation.provenance_status,
        "schema_status": odds_validation.schema_status,
        "leakage_risk": odds_validation.leakage_risk,
        "implementation_ready": odds_validation.implementation_ready,
        "blocker_reason": odds_validation.blocker_reason,
        "paper_only": odds_validation.paper_only,
        "production_ready": odds_validation.production_ready,
        "season": odds_validation.season,
        "approval_record_found": odds_validation.approval_record_found,
        "checklist_items": list(odds_validation.checklist_items),
        "notes": odds_validation.notes,
        "generated_at": generated_at,
    }
    with open(odds_path, "w", encoding="utf-8") as fh:
        json.dump(odds_data, fh, indent=2, ensure_ascii=False)
    written.append(odds_path)

    # 2. prediction_rebuild_feasibility.json
    pred_path = os.path.join(output_dir, "prediction_rebuild_feasibility.json")
    pred_data: Dict[str, Any] = {
        "feature_pipeline_found": prediction_feasibility.feature_pipeline_found,
        "model_training_found": prediction_feasibility.model_training_found,
        "oof_generation_found": prediction_feasibility.oof_generation_found,
        "leakage_guard_found": prediction_feasibility.leakage_guard_found,
        "time_aware_split_found": prediction_feasibility.time_aware_split_found,
        "adapter_for_2024_format_found": prediction_feasibility.adapter_for_2024_format_found,
        "feasibility_status": prediction_feasibility.feasibility_status,
        "blocker_reason": prediction_feasibility.blocker_reason,
        "candidate_scripts": list(prediction_feasibility.candidate_scripts),
        "candidate_models": list(prediction_feasibility.candidate_models),
        "paper_only": prediction_feasibility.paper_only,
        "production_ready": prediction_feasibility.production_ready,
        "season": prediction_feasibility.season,
        "notes": prediction_feasibility.notes,
        "generated_at": generated_at,
    }
    with open(pred_path, "w", encoding="utf-8") as fh:
        json.dump(pred_data, fh, indent=2, ensure_ascii=False)
    written.append(pred_path)

    # 3. dual_source_validation_summary.json
    summary_path = os.path.join(output_dir, "dual_source_validation_summary.json")
    summary_data: Dict[str, Any] = {
        "odds_license_status": summary.odds_license_status,
        "odds_source_status": summary.odds_source_status,
        "prediction_feasibility_status": summary.prediction_feasibility_status,
        "feature_pipeline_status": summary.feature_pipeline_status,
        "validator_specs_written": summary.validator_specs_written,
        "gate": gate.gate,
        "blocker_reasons": summary.blocker_reasons,
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "season": summary.season,
        "recommended_next_action": summary.recommended_next_action,
        "generated_at": generated_at,
        "output_dir": output_dir,
    }
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary_data, fh, indent=2, ensure_ascii=False)
    written.append(summary_path)

    # 4. dual_source_validation_summary.md
    md_path = os.path.join(output_dir, "dual_source_validation_summary.md")
    md_content = _build_validation_markdown(summary, gate, odds_validation, prediction_feasibility)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)
    written.append(md_path)

    # 5. p35_gate_result.json
    gate_path = os.path.join(output_dir, "p35_gate_result.json")
    gate_data: Dict[str, Any] = {
        "gate": gate.gate,
        "odds_license_status": gate.odds_license_status,
        "odds_source_status": gate.odds_source_status,
        "prediction_feasibility_status": gate.prediction_feasibility_status,
        "feature_pipeline_status": gate.feature_pipeline_status,
        "blocker_reason": gate.blocker_reason,
        "license_risk": gate.license_risk,
        "paper_only": gate.paper_only,
        "production_ready": gate.production_ready,
        "season": gate.season,
        "next_phase": gate.next_phase,
        "artifacts": [os.path.basename(f) for f in written] + [
            os.path.basename(f) for f in validator_spec_files
        ],
        "generated_at": generated_at,
    }
    with open(gate_path, "w", encoding="utf-8") as fh:
        json.dump(gate_data, fh, indent=2, ensure_ascii=False)
    written.append(gate_path)

    # Also include validator spec files in returned list
    written.extend(validator_spec_files)

    return written
