"""
P22 Backfill Execution Plan Generator.

Generates a P22BackfillExecutionPlan from a P22HistoricalAvailabilitySummary
and the raw per-date scan results.

This module ONLY emits the plan — it does not execute any replay.

PAPER_ONLY: True
PRODUCTION_READY: False
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from wbc_backend.recommendation.p22_historical_availability_contract import (
    DATE_BLOCKED_INVALID_ARTIFACTS,
    DATE_BLOCKED_UNSAFE_IDENTITY,
    DATE_MISSING_REQUIRED_SOURCE,
    DATE_PARTIAL_SOURCE_AVAILABLE,
    DATE_READY_P20_EXISTS,
    DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
    DATE_UNKNOWN,
    P22BackfillExecutionPlan,
    P22DateAvailabilityResult,
    P22HistoricalAvailabilitySummary,
)


# ---------------------------------------------------------------------------
# Local ValidationResult (mirrors P21 pattern — no cross-phase import)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_code: str = ""
    error_message: str = ""


# ---------------------------------------------------------------------------
# Command builder helpers
# ---------------------------------------------------------------------------


def build_daily_command_for_date(
    run_date: str,
    availability_status: str,
    paper_base_dir: str = "outputs/predictions/PAPER",
    output_base: str = "outputs/predictions/PAPER",
) -> List[str]:
    """
    Return the list of CLI commands recommended for a single date.

    Order:
    1. P19 identity repair (if date is replayable — must have P15/P16.6)
    2. P17 replay with P19 identity
    3. P20 daily orchestrator
    4. P21 aggregate (emitted as a note — must be run after all dates)

    Returns [] for already-ready or blocked/missing dates.
    """
    if availability_status == DATE_READY_P20_EXISTS:
        return [f"# {run_date}: SKIP — P20 already ready"]

    if availability_status == DATE_READY_REPLAYABLE_FROM_P15_P16_P19:
        return [
            (
                f"PYTHONPATH=. .venv/bin/python scripts/run_p19_odds_identity_join_repair.py"
                f" --run-date {run_date}"
                f" --paper-base-dir {paper_base_dir}"
                f" --output-dir {output_base}/{run_date}/p19_odds_identity_join_repair"
                f" --paper-only true"
            ),
            (
                f"PYTHONPATH=. .venv/bin/python scripts/run_p17_replay_with_p19_enriched_ledger.py"
                f" --run-date {run_date}"
                f" --paper-base-dir {paper_base_dir}"
                f" --output-dir {output_base}/{run_date}/p17_replay_with_p19_identity"
                f" --paper-only true"
            ),
            (
                f"PYTHONPATH=. .venv/bin/python scripts/run_p20_daily_paper_mlb_orchestrator.py"
                f" --run-date {run_date}"
                f" --paper-base-dir {paper_base_dir}"
                f" --output-dir {output_base}/{run_date}/p20_daily_paper_orchestrator"
                f" --paper-only true"
            ),
        ]

    if availability_status == DATE_PARTIAL_SOURCE_AVAILABLE:
        return [
            (
                f"# {run_date}: PARTIAL — build missing P15/P16.6/P19 artifacts first before replay"
            )
        ]

    if availability_status in (
        DATE_MISSING_REQUIRED_SOURCE,
        DATE_BLOCKED_INVALID_ARTIFACTS,
        DATE_BLOCKED_UNSAFE_IDENTITY,
        DATE_UNKNOWN,
    ):
        return [f"# {run_date}: BLOCKED/MISSING — no replay possible without source artifacts"]

    return [f"# {run_date}: UNKNOWN status {availability_status!r}"]


def build_p21_command_for_range(date_start: str, date_end: str) -> List[str]:
    """Return the P21 aggregate CLI command for a date range."""
    return [
        (
            f"PYTHONPATH=. .venv/bin/python scripts/run_p21_multi_day_paper_backfill.py"
            f" --date-start {date_start}"
            f" --date-end {date_end}"
            f" --paper-base-dir outputs/predictions/PAPER"
            f" --output-dir outputs/predictions/PAPER/backfill/p21_multi_day_paper_backfill_{date_start}_{date_end}"
            f" --paper-only true"
        )
    ]


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------


def build_backfill_execution_plan(
    scan_summary: P22HistoricalAvailabilitySummary,
    date_results: List[P22DateAvailabilityResult],
) -> P22BackfillExecutionPlan:
    """
    Build a P22BackfillExecutionPlan from scan results.

    - Skips already-ready dates (P20 exists).
    - Emits replay commands for replayable dates.
    - Lists partial/missing/blocked separately.
    - Emits P21 aggregate command at the end if any replay was planned.
    - Does NOT execute anything.
    """
    dates_ready: List[str] = []
    dates_replay: List[str] = []
    dates_missing: List[str] = []
    dates_blocked: List[str] = []

    all_commands: List[str] = []
    execution_order: List[str] = []
    risk_notes: List[str] = [
        "PAPER_ONLY=true — no real bets, no production DB, no live TSL",
        "production_ready=false — never promote to production without further validation",
        "Do not replay a date unless all required source artifacts are verified present",
        "Replay order: P19 → P17 → P20 per date; then P21 aggregate across range",
    ]

    by_date: dict[str, P22DateAvailabilityResult] = {r.run_date: r for r in date_results}

    for result in sorted(date_results, key=lambda r: r.run_date):
        run_date = result.run_date
        status = result.availability_status

        if status == DATE_READY_P20_EXISTS:
            dates_ready.append(run_date)
            cmds = build_daily_command_for_date(run_date, status)
            all_commands.extend(cmds)
            execution_order.append(f"SKIP {run_date}: already P20-ready")

        elif status == DATE_READY_REPLAYABLE_FROM_P15_P16_P19:
            dates_replay.append(run_date)
            cmds = build_daily_command_for_date(run_date, status)
            all_commands.extend(cmds)
            execution_order.append(f"REPLAY {run_date}: P19 → P17 → P20")

        elif status == DATE_PARTIAL_SOURCE_AVAILABLE:
            # Partial: not replayable yet, not fully blocked
            dates_missing.append(run_date)  # treat as missing for plan purposes
            cmds = build_daily_command_for_date(run_date, status)
            all_commands.extend(cmds)
            execution_order.append(f"PARTIAL {run_date}: needs artifact repair first")

        elif status in (
            DATE_MISSING_REQUIRED_SOURCE,
            DATE_BLOCKED_INVALID_ARTIFACTS,
            DATE_BLOCKED_UNSAFE_IDENTITY,
            DATE_UNKNOWN,
        ):
            if status == DATE_MISSING_REQUIRED_SOURCE:
                dates_missing.append(run_date)
                execution_order.append(f"MISSING {run_date}: no source artifacts")
            else:
                dates_blocked.append(run_date)
                execution_order.append(f"BLOCKED {run_date}: {status}")
            cmds = build_daily_command_for_date(run_date, status)
            all_commands.extend(cmds)

    # Add P21 aggregate if any replay was planned
    if dates_replay:
        p21_cmds = build_p21_command_for_range(
            scan_summary.date_start, scan_summary.date_end
        )
        all_commands.extend(p21_cmds)
        execution_order.append(
            f"P21 AGGREGATE: {scan_summary.date_start} → {scan_summary.date_end}"
        )

    return P22BackfillExecutionPlan(
        date_start=scan_summary.date_start,
        date_end=scan_summary.date_end,
        dates_to_skip_already_ready=tuple(sorted(dates_ready)),
        dates_to_replay_from_existing_sources=tuple(sorted(dates_replay)),
        dates_missing_required_sources=tuple(sorted(dates_missing)),
        dates_blocked=tuple(sorted(dates_blocked)),
        recommended_commands=tuple(all_commands),
        execution_order=tuple(execution_order),
        risk_notes=tuple(risk_notes),
    )


def validate_execution_plan(plan: P22BackfillExecutionPlan) -> ValidationResult:
    """Validate plan safety invariants."""
    if plan.production_ready:
        return ValidationResult(
            valid=False,
            error_code="PLAN_PRODUCTION_READY",
            error_message="Execution plan must have production_ready=False",
        )
    if not plan.paper_only:
        return ValidationResult(
            valid=False,
            error_code="PLAN_NOT_PAPER_ONLY",
            error_message="Execution plan must have paper_only=True",
        )
    # Overlap check: a date cannot be in both ready and replay lists
    ready_set = set(plan.dates_to_skip_already_ready)
    replay_set = set(plan.dates_to_replay_from_existing_sources)
    overlap = ready_set & replay_set
    if overlap:
        return ValidationResult(
            valid=False,
            error_code="PLAN_DATE_OVERLAP",
            error_message=f"Dates appear in both ready and replay lists: {sorted(overlap)}",
        )
    return ValidationResult(valid=True)
