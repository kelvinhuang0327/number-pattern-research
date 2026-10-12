"""
P22 Historical Artifact Scanner.

Scans a PAPER base directory across a date range and classifies each date
by artifact availability:

  DATE_READY_P20_EXISTS
  DATE_READY_REPLAYABLE_FROM_P15_P16_P19
  DATE_PARTIAL_SOURCE_AVAILABLE
  DATE_MISSING_REQUIRED_SOURCE
  DATE_BLOCKED_INVALID_ARTIFACTS
  DATE_BLOCKED_UNSAFE_IDENTITY
  DATE_UNKNOWN

Rules:
- Never fabricate missing artifacts.
- Never mark a date replayable unless exact required artifacts are present.
- P20 readiness requires p20_gate == EXPECTED_P20_GATE.

PAPER_ONLY: True
PRODUCTION_READY: False
"""
from __future__ import annotations

import json
from datetime import date, timedelta
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
    EXPECTED_P20_GATE,
    P15_DIR,
    P15_JOINED_OOF_WITH_ODDS,
    P15_SIMULATION_LEDGER,
    P16_6_DIR,
    P16_6_RECOMMENDATION_ROWS,
    P16_6_RECOMMENDATION_SUMMARY,
    P17_DIR,
    P17_REPLAY_LEDGER,
    P17_REPLAY_SUMMARY,
    P19_DIR,
    P19_ENRICHED_LEDGER,
    P19_GATE_RESULT,
    P20_DAILY_SUMMARY,
    P20_DIR,
    P20_GATE_RESULT,
    P22_BLOCKED_NO_AVAILABLE_DATES,
    P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
    P22DateAvailabilityResult,
    P22HistoricalAvailabilitySummary,
    P22PhaseArtifactStatus,
)

# ---------------------------------------------------------------------------
# Internal artifact spec: (artifact_key, subdir, filename)
# ---------------------------------------------------------------------------
_ARTIFACT_SPEC: List[tuple[str, str, str]] = [
    (P15_JOINED_OOF_WITH_ODDS, P15_DIR, "joined_oof_with_odds.csv"),
    (P15_SIMULATION_LEDGER, P15_DIR, "simulation_ledger.csv"),
    (P16_6_RECOMMENDATION_ROWS, P16_6_DIR, "recommendation_rows.csv"),
    (P16_6_RECOMMENDATION_SUMMARY, P16_6_DIR, "recommendation_summary.json"),
    (P19_ENRICHED_LEDGER, P19_DIR, "enriched_simulation_ledger.csv"),
    (P19_GATE_RESULT, P19_DIR, "p19_gate_result.json"),
    (P17_REPLAY_LEDGER, P17_DIR, "paper_recommendation_ledger.csv"),
    (P17_REPLAY_SUMMARY, P17_DIR, "paper_recommendation_ledger_summary.json"),
    (P20_DAILY_SUMMARY, P20_DIR, "daily_paper_summary.json"),
    (P20_GATE_RESULT, P20_DIR, "p20_gate_result.json"),
]

# Keys required for P20-already-exists check
_P20_KEYS: frozenset[str] = frozenset({P20_DAILY_SUMMARY, P20_GATE_RESULT})

# Keys required for full replayability (P15+P16.6+P19 present, P20 absent)
_REPLAY_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        P15_JOINED_OOF_WITH_ODDS,
        P15_SIMULATION_LEDGER,
        P16_6_RECOMMENDATION_ROWS,
        P16_6_RECOMMENDATION_SUMMARY,
        P19_ENRICHED_LEDGER,
        P19_GATE_RESULT,
    }
)


# ---------------------------------------------------------------------------
# Core scanning functions
# ---------------------------------------------------------------------------


def inspect_phase_artifacts(date_dir: Path) -> List[P22PhaseArtifactStatus]:
    """Return a P22PhaseArtifactStatus for every known artifact key."""
    statuses: List[P22PhaseArtifactStatus] = []
    for key, subdir, filename in _ARTIFACT_SPEC:
        full_path = date_dir / subdir / filename
        relative = str(Path(subdir) / filename)
        if full_path.exists():
            try:
                size = full_path.stat().st_size
                statuses.append(
                    P22PhaseArtifactStatus(
                        artifact_key=key,
                        expected_path=relative,
                        exists=True,
                        readable=True,
                        size_bytes=size,
                    )
                )
            except OSError as exc:
                statuses.append(
                    P22PhaseArtifactStatus(
                        artifact_key=key,
                        expected_path=relative,
                        exists=True,
                        readable=False,
                        error_message=str(exc),
                    )
                )
        else:
            statuses.append(
                P22PhaseArtifactStatus(
                    artifact_key=key,
                    expected_path=relative,
                    exists=False,
                    readable=False,
                )
            )
    return statuses


def _read_p20_gate(date_dir: Path) -> str:
    """Load p20_gate field from p20_gate_result.json; return '' on error."""
    gate_path = date_dir / P20_DIR / "p20_gate_result.json"
    try:
        data = json.loads(gate_path.read_text(encoding="utf-8"))
        return str(data.get("p20_gate", ""))
    except Exception:
        return ""


def _check_p19_safe(date_dir: Path) -> bool:
    """Return False if p19_gate_result.json explicitly flags unsafe identity."""
    gate_path = date_dir / P19_DIR / "p19_gate_result.json"
    if not gate_path.exists():
        return True  # absent = not explicitly unsafe
    try:
        data = json.loads(gate_path.read_text(encoding="utf-8"))
        # If gate is READY we consider identity safe
        gate_val = str(data.get("p19_gate", ""))
        if "FAIL" in gate_val or "BLOCKED" in gate_val:
            return False
        return True
    except Exception:
        return False  # unreadable → treat as unsafe


def classify_date_availability(
    phase_statuses: List[P22PhaseArtifactStatus],
    p20_gate: str,
    p19_safe: bool,
) -> str:
    """
    Classify a date given its phase artifact statuses.

    Priority order:
    1. DATE_READY_P20_EXISTS         — P20 summary+gate present AND gate==READY
    2. DATE_BLOCKED_INVALID_ARTIFACTS — P20 files present but gate invalid
    3. DATE_BLOCKED_UNSAFE_IDENTITY   — P19 gate flags unsafe identity
    4. DATE_READY_REPLAYABLE_FROM_P15_P16_P19 — all replay sources present
    5. DATE_PARTIAL_SOURCE_AVAILABLE  — some but not all sources present
    6. DATE_MISSING_REQUIRED_SOURCE   — no sources present
    """
    by_key: dict[str, P22PhaseArtifactStatus] = {s.artifact_key: s for s in phase_statuses}

    # Check P20 existence
    p20_summary_ok = by_key.get(P20_DAILY_SUMMARY, None)
    p20_gate_ok = by_key.get(P20_GATE_RESULT, None)

    p20_files_present = (
        p20_summary_ok is not None
        and p20_summary_ok.exists
        and p20_gate_ok is not None
        and p20_gate_ok.exists
    )

    if p20_files_present:
        if p20_gate == EXPECTED_P20_GATE:
            return DATE_READY_P20_EXISTS
        else:
            return DATE_BLOCKED_INVALID_ARTIFACTS

    # P20 not present — check for unsafe identity before replay
    if not p19_safe:
        return DATE_BLOCKED_UNSAFE_IDENTITY

    # Check full replayability
    replay_present = all(
        by_key.get(k) is not None
        and by_key[k].exists
        and by_key[k].readable
        for k in _REPLAY_REQUIRED_KEYS
    )
    if replay_present:
        return DATE_READY_REPLAYABLE_FROM_P15_P16_P19

    # Count any existing readable artifacts
    n_found = sum(1 for s in phase_statuses if s.exists and s.readable)
    if n_found > 0:
        return DATE_PARTIAL_SOURCE_AVAILABLE

    return DATE_MISSING_REQUIRED_SOURCE


def scan_single_paper_date(base_dir: Path, run_date: str) -> P22DateAvailabilityResult:
    """
    Scan a single run_date directory.

    Returns P22DateAvailabilityResult with availability_status set.
    Never fabricates missing artifacts.
    """
    date_dir = base_dir / run_date

    if not date_dir.exists():
        return P22DateAvailabilityResult(
            run_date=run_date,
            availability_status=DATE_MISSING_REQUIRED_SOURCE,
            n_artifacts_found=0,
            n_artifacts_required=len(_ARTIFACT_SPEC),
            error_message=f"Directory not found: {date_dir}",
        )

    if not date_dir.is_dir():
        return P22DateAvailabilityResult(
            run_date=run_date,
            availability_status=DATE_BLOCKED_INVALID_ARTIFACTS,
            error_message=f"Path exists but is not a directory: {date_dir}",
        )

    phase_statuses = inspect_phase_artifacts(date_dir)
    p20_gate = _read_p20_gate(date_dir)
    p19_safe = _check_p19_safe(date_dir)

    status = classify_date_availability(phase_statuses, p20_gate, p19_safe)

    n_found = sum(1 for s in phase_statuses if s.exists and s.readable)

    return P22DateAvailabilityResult(
        run_date=run_date,
        availability_status=status,
        phase_statuses=tuple(phase_statuses),
        p20_gate=p20_gate,
        n_artifacts_found=n_found,
        n_artifacts_required=len(_ARTIFACT_SPEC),
    )


def scan_paper_date_range(
    base_dir: Path,
    date_start: str,
    date_end: str,
) -> List[P22DateAvailabilityResult]:
    """
    Scan all dates from date_start to date_end (inclusive).

    Returns exactly (date_end - date_start + 1) results.
    Never fabricates missing dates.
    """
    start = date.fromisoformat(date_start)
    end = date.fromisoformat(date_end)
    results: List[P22DateAvailabilityResult] = []

    current = start
    while current <= end:
        run_date = current.isoformat()
        result = scan_single_paper_date(base_dir, run_date)
        results.append(result)
        current += timedelta(days=1)

    return results


def _recommend_next_action(summary_counts: dict[str, int]) -> str:
    """Generate a recommended_next_action string from counts."""
    n_ready = summary_counts.get("n_dates_p20_ready", 0)
    n_replay = summary_counts.get("n_dates_replayable", 0)
    n_partial = summary_counts.get("n_dates_partial", 0)
    n_missing = summary_counts.get("n_dates_missing", 0)

    if n_replay > 0:
        return (
            f"Run P19→P17→P20 replay for {n_replay} replayable date(s), "
            "then re-run P21 aggregate backfill."
        )
    if n_partial > 0:
        return (
            f"Build missing P15/P16.6/P19 artifacts for {n_partial} partial date(s) "
            "before replay is possible."
        )
    if n_missing > 0 and n_ready > 0:
        return (
            f"{n_ready} date(s) already P20-ready. {n_missing} date(s) lack source "
            "artifacts — consider historical source artifact expansion (P22.5 or TSL)."
        )
    if n_missing > 0 and n_ready == 0:
        return (
            "No dates are P20-ready or replayable. "
            "Historical source artifact discovery required before backfill can proceed."
        )
    if n_ready > 0:
        return f"All {n_ready} date(s) are P20-ready. Run P21 aggregate backfill."
    return "No actionable dates found. Inspect blocked dates."


def summarize_scan_results(
    date_results: List[P22DateAvailabilityResult],
    date_start: str,
    date_end: str,
) -> P22HistoricalAvailabilitySummary:
    """
    Aggregate per-date scan results into a P22HistoricalAvailabilitySummary.
    """
    n_p20_ready = 0
    n_replayable = 0
    n_partial = 0
    n_missing = 0
    n_blocked = 0
    candidate_dates: list[str] = []
    missing_dates: list[str] = []
    blocked_dates: list[str] = []
    partial_dates: list[str] = []

    for r in date_results:
        s = r.availability_status
        if s == DATE_READY_P20_EXISTS:
            n_p20_ready += 1
            candidate_dates.append(r.run_date)
        elif s == DATE_READY_REPLAYABLE_FROM_P15_P16_P19:
            n_replayable += 1
            candidate_dates.append(r.run_date)
        elif s == DATE_PARTIAL_SOURCE_AVAILABLE:
            n_partial += 1
            partial_dates.append(r.run_date)
        elif s == DATE_MISSING_REQUIRED_SOURCE:
            n_missing += 1
            missing_dates.append(r.run_date)
        elif s in (DATE_BLOCKED_INVALID_ARTIFACTS, DATE_BLOCKED_UNSAFE_IDENTITY, DATE_UNKNOWN):
            n_blocked += 1
            blocked_dates.append(r.run_date)

    n_backfill_candidates = len(candidate_dates)

    counts = {
        "n_dates_p20_ready": n_p20_ready,
        "n_dates_replayable": n_replayable,
        "n_dates_partial": n_partial,
        "n_dates_missing": n_missing,
        "n_dates_blocked": n_blocked,
    }
    recommended = _recommend_next_action(counts)

    # Gate determination
    if n_backfill_candidates > 0:
        gate = P22_HISTORICAL_BACKFILL_AVAILABILITY_READY
    else:
        gate = P22_BLOCKED_NO_AVAILABLE_DATES

    return P22HistoricalAvailabilitySummary(
        date_start=date_start,
        date_end=date_end,
        n_dates_scanned=len(date_results),
        n_dates_p20_ready=n_p20_ready,
        n_dates_replayable=n_replayable,
        n_dates_partial=n_partial,
        n_dates_missing=n_missing,
        n_dates_blocked=n_blocked,
        n_backfill_candidate_dates=n_backfill_candidates,
        backfill_candidate_dates=tuple(sorted(candidate_dates)),
        missing_dates=tuple(sorted(missing_dates)),
        blocked_dates=tuple(sorted(blocked_dates)),
        partial_dates=tuple(sorted(partial_dates)),
        recommended_next_action=recommended,
        p22_gate=gate,
    )
