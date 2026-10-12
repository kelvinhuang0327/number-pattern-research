from __future__ import annotations

from dataclasses import dataclass


FORMAT_FAILURES = {
    "missing_strategy_output_table",
    "missing_required_outputs",
    "blank_required_fields",
    "malformed_strategy_table",
    "missing_mc_reference",
}

RESEARCH_FAILURES = {
    "all_edges_non_positive",
    "weak_vs_incumbent",
    "promotion_logic_invalid",
    "insufficient_strategy_count",
    "research_evidence_missing",
}


@dataclass(frozen=True)
class WorkerGateClassification:
    legacy_status: str
    refined_status: str
    reason_code: str
    reason_detail: str
    planner_action: str


def classify_failed_acceptance(reason_code: str, reason_detail: str = "") -> WorkerGateClassification:
    normalized = str(reason_code or "unknown").strip().lower()

    if normalized in FORMAT_FAILURES:
        return WorkerGateClassification(
            legacy_status="FAILED_ACCEPTANCE",
            refined_status="FAILED_FORMAT_CONTRACT",
            reason_code=normalized,
            reason_detail=reason_detail or "output format did not satisfy worker contract",
            planner_action="repair_format_contract",
        )

    if normalized in RESEARCH_FAILURES:
        return WorkerGateClassification(
            legacy_status="FAILED_ACCEPTANCE",
            refined_status="FAILED_RESEARCH_CONTRACT",
            reason_code=normalized,
            reason_detail=reason_detail or "research result did not satisfy promotion/research contract",
            planner_action="redirect_research_family",
        )

    return WorkerGateClassification(
        legacy_status="FAILED_ACCEPTANCE",
        refined_status="FAILED_FORMAT_CONTRACT",
        reason_code=normalized or "unknown_failed_acceptance",
        reason_detail=reason_detail or "failed acceptance with unclassified cause",
        planner_action="inspect_failed_acceptance",
    )


def suggest_reason_code_from_text(gate_reason: str) -> str:
    text = (gate_reason or "").lower()
    if "missing required outputs" in text:
        return "missing_required_outputs"
    if "strategy output table" in text and "missing" in text:
        return "missing_strategy_output_table"
    if "blank required fields" in text:
        return "blank_required_fields"
    if "all" in text and "edge" in text and "≤ 0" in text:
        return "all_edges_non_positive"
    if "vs_incumbent" in text and "≤ 0" in text:
        return "weak_vs_incumbent"
    if "t1_mc_pass" in text or "promotion_blocker" in text:
        return "promotion_logic_invalid"
    if "required ≥" in text and "strategy name" in text:
        return "insufficient_strategy_count"
    if "monte carlo" in text and "missing" in text:
        return "missing_mc_reference"
    return "unknown_failed_acceptance"