"""
P22.5 P15 Readiness Planner.

Evaluates source candidates to determine which run_dates can have
P15 simulation inputs constructed. Never fabricates missing data.
Only produces a plan — does not execute it.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    SOURCE_CANDIDATE_PARTIAL,
    SOURCE_CANDIDATE_USABLE,
    P225ArtifactBuildPlan,
    P225DateSourceAvailability,
    P225HistoricalSourceCandidate,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_p15_readiness_for_date(
    run_date: str,
    candidates: List[P225HistoricalSourceCandidate],
) -> P225DateSourceAvailability:
    """Assess P15 input readiness for a single run_date given available candidates.

    A date is P15-ready only when USABLE candidates collectively provide:
    - prediction coverage (p_oof or p_model)
    - market odds coverage
    - outcome/y_true coverage
    - deterministic identity mapping (game_id or low/medium-risk team+date)
    """
    usable = [c for c in candidates if c.candidate_status == SOURCE_CANDIDATE_USABLE]
    partial = [c for c in candidates if c.candidate_status == SOURCE_CANDIDATE_PARTIAL]
    all_useful = usable + partial

    has_predictions = any(c.has_p_model_or_p_oof for c in usable)
    has_odds = any(c.has_odds for c in usable)
    has_outcomes = any(c.has_y_true for c in usable)

    # Identity: game_id directly present, OR date+team fields with low/medium risk
    has_identity = any(
        c.has_game_id or c.mapping_risk in (MAPPING_RISK_LOW, MAPPING_RISK_MEDIUM)
        for c in usable
    )

    # Check for unsafe mapping that would block even with otherwise good data
    all_high_risk = bool(usable) and all(
        c.mapping_risk == MAPPING_RISK_HIGH for c in usable
    )

    is_p15_ready = (
        has_predictions and has_odds and has_outcomes and has_identity
        and not all_high_risk
    )

    # Determine blocked_reason
    blocked_reason = ""
    if not usable and not partial:
        blocked_reason = "NO_SOURCE_CANDIDATES"
    elif not has_predictions:
        blocked_reason = "MISSING_MODEL_PREDICTIONS"
    elif not has_odds:
        blocked_reason = "MISSING_MARKET_ODDS"
    elif not has_outcomes:
        blocked_reason = "MISSING_GAME_OUTCOMES"
    elif not has_identity:
        blocked_reason = "MISSING_IDENTITY_MAPPING"
    elif all_high_risk:
        blocked_reason = "UNSAFE_IDENTITY_MAPPING"

    # candidate_status for this date
    if is_p15_ready:
        date_status = SOURCE_CANDIDATE_USABLE
    elif any([has_predictions, has_odds, has_outcomes]):
        date_status = SOURCE_CANDIDATE_PARTIAL
    else:
        date_status = SOURCE_CANDIDATE_USABLE  # fallback

    return P225DateSourceAvailability(
        run_date=run_date,
        candidate_status=date_status,
        has_predictions=has_predictions,
        has_odds=has_odds,
        has_outcomes=has_outcomes,
        has_identity=has_identity,
        is_p15_ready=is_p15_ready,
        blocked_reason=blocked_reason,
        candidates=tuple(c.source_path for c in usable),
        paper_only=True,
        production_ready=False,
    )


def build_source_artifact_build_plan(
    date_results: List[P225DateSourceAvailability],
    candidates: List[P225HistoricalSourceCandidate],
) -> P225ArtifactBuildPlan:
    """Build a P15 input build plan from per-date readiness assessments.

    This plan describes what to do, but does NOT execute anything.
    """
    if not date_results:
        return P225ArtifactBuildPlan(
            date_start="",
            date_end="",
            paper_only=True,
            production_ready=False,
        )

    date_start = min(r.run_date for r in date_results)
    date_end = max(r.run_date for r in date_results)

    ready: List[str] = []
    partial_odds: List[str] = []
    partial_preds: List[str] = []
    partial_outcomes: List[str] = []
    unsafe_identity: List[str] = []
    missing_all: List[str] = []
    blocked_reasons: List[str] = []
    commands: List[str] = []

    usable_candidates = [c for c in candidates if c.candidate_status == SOURCE_CANDIDATE_USABLE]

    for r in sorted(date_results, key=lambda x: x.run_date):
        if r.is_p15_ready:
            ready.append(r.run_date)
        elif "UNSAFE" in r.blocked_reason or "MISSING_IDENTITY" in r.blocked_reason:
            unsafe_identity.append(r.run_date)
            blocked_reasons.append(f"{r.run_date}:{r.blocked_reason}")
        elif "MISSING_MARKET_ODDS" in r.blocked_reason:
            partial_odds.append(r.run_date)
            blocked_reasons.append(f"{r.run_date}:{r.blocked_reason}")
        elif "MISSING_MODEL_PREDICTIONS" in r.blocked_reason:
            partial_preds.append(r.run_date)
            blocked_reasons.append(f"{r.run_date}:{r.blocked_reason}")
        elif "MISSING_GAME_OUTCOMES" in r.blocked_reason:
            partial_outcomes.append(r.run_date)
            blocked_reasons.append(f"{r.run_date}:{r.blocked_reason}")
        else:
            missing_all.append(r.run_date)
            blocked_reasons.append(f"{r.run_date}:{r.blocked_reason or 'MISSING_ALL_SOURCES'}")

    # Generate recommended safe commands for ready dates
    for run_date in ready:
        commands.append(
            f"# P22.5 dry-run preview: {run_date} — "
            f"build_p15_input_preview_for_date('{run_date}', source_candidates, output_dir)"
        )

    if ready:
        commands.append(
            f"# After preview validation, run P21 backfill: "
            f"python scripts/run_p21_multi_day_paper_backfill.py "
            f"--date-start {min(ready)} --date-end {max(ready)} --paper-only true"
        )

    return P225ArtifactBuildPlan(
        date_start=date_start,
        date_end=date_end,
        dates_ready_to_build_p15_inputs=tuple(ready),
        dates_partial_missing_odds=tuple(partial_odds),
        dates_partial_missing_predictions=tuple(partial_preds),
        dates_partial_missing_outcomes=tuple(partial_outcomes),
        dates_unsafe_identity_mapping=tuple(unsafe_identity),
        dates_missing_all_sources=tuple(missing_all),
        recommended_safe_commands=tuple(commands),
        blocked_reason_by_date=tuple(blocked_reasons),
        paper_only=True,
        production_ready=False,
    )


def validate_build_plan(plan: P225ArtifactBuildPlan) -> Tuple[bool, str]:
    """Validate a build plan. Returns (valid, error_code)."""
    if plan.production_ready:
        return False, "PRODUCTION_READY_MUST_BE_FALSE"
    if not plan.paper_only:
        return False, "PAPER_ONLY_MUST_BE_TRUE"

    # Dates should not appear in both ready and blocked lists
    ready_set = set(plan.dates_ready_to_build_p15_inputs)
    blocked_set = (
        set(plan.dates_unsafe_identity_mapping)
        | set(plan.dates_missing_all_sources)
    )
    overlap = ready_set & blocked_set
    if overlap:
        return False, f"DATE_IN_BOTH_READY_AND_BLOCKED:{sorted(overlap)}"

    return True, ""


def generate_safe_next_commands(
    plan: P225ArtifactBuildPlan,
    date_start: str,
    date_end: str,
    paper_base_dir: str = "outputs/predictions/PAPER",
    output_base: str = "outputs/predictions/PAPER/backfill",
) -> List[str]:
    """Generate safe next commands based on the plan."""
    commands = list(plan.recommended_safe_commands)

    if not plan.dates_ready_to_build_p15_inputs:
        commands.insert(0, f"# NO DATES READY — expand source coverage first")
        commands.insert(1, f"# Missing dates: {len(plan.dates_missing_all_sources)}")
    else:
        n_ready = len(plan.dates_ready_to_build_p15_inputs)
        commands.insert(0, f"# {n_ready} date(s) ready for P15 input construction")

    return commands
