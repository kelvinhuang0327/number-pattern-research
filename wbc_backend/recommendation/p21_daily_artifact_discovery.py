"""
wbc_backend/recommendation/p21_daily_artifact_discovery.py

P21 — Discovery of per-date P20 artifacts within a PAPER base directory.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    EXPECTED_P20_DAILY_GATE,
    P21BackfillDateResult,
    P21MissingArtifactReport,
    P21_BLOCKED_DAILY_GATE_NOT_READY,
    P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)

# ---------------------------------------------------------------------------
# Artifact names required per date
# ---------------------------------------------------------------------------

REQUIRED_DAILY_ARTIFACTS = [
    "daily_paper_summary.json",
    "artifact_manifest.json",
    "p20_gate_result.json",
]

P20_DATE_SUBDIR = "p20_daily_paper_orchestrator"


# ---------------------------------------------------------------------------
# ValidationResult (local)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error_code: str = ""
    error_message: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _date_range(start: str, end: str) -> list[str]:
    """Return list of YYYY-MM-DD strings from start to end inclusive."""
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    out: list[str] = []
    current = d0
    while current <= d1:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _sha256_file(path: Path) -> str:
    try:
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        return h
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def validate_daily_artifact_set(date_dir: Path) -> ValidationResult:
    """
    Check whether all required P20 artifacts exist for a given date directory.

    Args:
        date_dir: Path to outputs/predictions/PAPER/<date>/p20_daily_paper_orchestrator/

    Returns:
        ValidationResult
    """
    missing = [
        name for name in REQUIRED_DAILY_ARTIFACTS
        if not (date_dir / name).exists()
    ]
    if missing:
        return ValidationResult(
            valid=False,
            error_code=P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS,
            error_message=f"Missing artifacts in {date_dir}: {missing}",
        )
    return ValidationResult(valid=True)


def load_daily_gate(date_dir: Path) -> dict:
    """Load p20_gate_result.json from a date directory."""
    gate_path = date_dir / "p20_gate_result.json"
    with open(gate_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_daily_summary(date_dir: Path) -> dict:
    """Load daily_paper_summary.json from a date directory."""
    summary_path = date_dir / "daily_paper_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_date_result(
    run_date: str,
    date_dir: Path,
    gate_data: dict,
    summary_data: dict,
) -> P21BackfillDateResult:
    """Build a P21BackfillDateResult from loaded gate + summary dicts."""
    p20_gate = gate_data.get("p20_gate", "")
    n_win = int(summary_data.get("n_settled_win", 0))
    n_loss = int(summary_data.get("n_settled_loss", 0))
    n_unsettled = int(summary_data.get("n_unsettled", 0))
    n_active = int(summary_data.get("n_active_paper_entries", 0))
    n_recommended = int(summary_data.get("n_recommended_rows", n_active))

    # Derive stake/pnl — P20 summary may store roi_units directly
    # Compute stake from active * 1 unit (default), pnl from roi * stake
    total_stake = float(summary_data.get("total_stake_units", float(n_active)))
    total_pnl = float(summary_data.get("total_pnl_units", 0.0))
    roi_units = float(summary_data.get("roi_units", 0.0))
    hit_rate = float(summary_data.get("hit_rate", 0.0))
    game_id_coverage = float(summary_data.get("game_id_coverage", 0.0))
    settlement_join_method = str(
        summary_data.get("settlement_join_method", "UNKNOWN")
    )
    paper_only = bool(summary_data.get("paper_only", True))
    production_ready = bool(summary_data.get("production_ready", False))

    # Compute manifest SHA-256 from artifact_manifest.json
    manifest_sha = _sha256_file(date_dir / "artifact_manifest.json")

    # Gate for this date
    if p20_gate == EXPECTED_P20_DAILY_GATE:
        daily_gate = P21_MULTI_DAY_PAPER_BACKFILL_READY
    else:
        daily_gate = P21_BLOCKED_DAILY_GATE_NOT_READY

    return P21BackfillDateResult(
        run_date=run_date,
        daily_gate=daily_gate,
        p20_gate=p20_gate,
        n_recommended_rows=n_recommended,
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=n_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi_units,
        hit_rate=hit_rate,
        game_id_coverage=game_id_coverage,
        settlement_join_method=settlement_join_method,
        artifact_manifest_sha256=manifest_sha,
        paper_only=paper_only,
        production_ready=production_ready,
    )


def discover_p20_daily_artifacts(
    base_dir: str | Path,
    date_range: tuple[str, str],
) -> list[P21BackfillDateResult | P21MissingArtifactReport]:
    """
    Discover P20 daily artifacts across a date range.

    Args:
        base_dir: Path to outputs/predictions/PAPER/
        date_range: (date_start, date_end) as YYYY-MM-DD strings (inclusive)

    Returns:
        List of P21BackfillDateResult (for found dates) and
        P21MissingArtifactReport (for missing/invalid dates).
        Missing dates are NEVER fabricated.
    """
    base = Path(base_dir)
    dates = _date_range(date_range[0], date_range[1])
    results: list[P21BackfillDateResult | P21MissingArtifactReport] = []

    for run_date in dates:
        date_dir = base / run_date / P20_DATE_SUBDIR

        # Check directory exists
        if not date_dir.exists():
            results.append(
                P21MissingArtifactReport(
                    run_date=run_date,
                    missing_files=tuple(REQUIRED_DAILY_ARTIFACTS),
                    error_message=f"Directory not found: {date_dir}",
                )
            )
            continue

        # Check required files
        validation = validate_daily_artifact_set(date_dir)
        if not validation.valid:
            missing_files = tuple(
                name for name in REQUIRED_DAILY_ARTIFACTS
                if not (date_dir / name).exists()
            )
            results.append(
                P21MissingArtifactReport(
                    run_date=run_date,
                    missing_files=missing_files,
                    error_message=validation.error_message,
                )
            )
            continue

        # Load and build result
        try:
            gate_data = load_daily_gate(date_dir)
            summary_data = load_daily_summary(date_dir)
            result = _build_date_result(run_date, date_dir, gate_data, summary_data)
            results.append(result)
        except Exception as exc:
            results.append(
                P21MissingArtifactReport(
                    run_date=run_date,
                    invalid_files=tuple(REQUIRED_DAILY_ARTIFACTS),
                    error_message=f"Failed to load artifacts: {exc}",
                )
            )

    return results


def summarize_missing_artifacts(
    date_range: tuple[str, str],
    discovered: list[P21BackfillDateResult | P21MissingArtifactReport],
) -> list[dict]:
    """
    Return JSON-serialisable list of missing artifact reports.

    Args:
        date_range: (date_start, date_end)
        discovered: output of discover_p20_daily_artifacts

    Returns:
        List of dicts, one per missing / invalid date.
    """
    missing: list[dict] = []
    for item in discovered:
        if isinstance(item, P21MissingArtifactReport):
            missing.append(
                {
                    "run_date": item.run_date,
                    "missing_files": list(item.missing_files),
                    "invalid_files": list(item.invalid_files),
                    "error_message": item.error_message,
                }
            )
    return missing
