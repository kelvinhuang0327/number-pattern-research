"""
wbc_backend/recommendation/p28_true_date_stability_auditor.py

P28 True-Date Backfill Performance Stability Auditor.

Orchestrates all P28 analysis modules:
  1. Load P27 date_results.csv and segment_results.csv
  2. Run sample density analysis
  3. Run performance variance analysis (bootstrap CI, seed=42)
  4. Run risk/drawdown analysis
  5. Determine gate decision (priority order: sample_size → drawdown → variance → ready)
  6. Write 8 output files to the designated output directory

Output files:
  p28_stability_audit_summary.json
  p28_stability_audit_summary.md
  sample_density_profile.json
  performance_variance_profile.json
  risk_drawdown_profile.json
  sparse_dates.csv
  sparse_segments.csv
  p28_gate_result.json

Gate policy:
  1. total_active_entries < min_sample_size  → P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
  2. max_drawdown_pct > 25%                  → P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT
  3. segment ROI std unusually high          → P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE
  4. else                                    → P28_TRUE_DATE_STABILITY_AUDIT_READY

Even if blocked, all 8 output files are produced.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from wbc_backend.recommendation.p28_true_date_stability_contract import (
    MIN_SAMPLE_SIZE_ADVISORY,
    MAX_DRAWDOWN_PCT_LIMIT,
    P28GateResult,
    P28StabilityAuditSummary,
    P28_TRUE_DATE_STABILITY_AUDIT_READY,
    P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT,
    P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE,
    P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT,
    P28_FAIL_INPUT_MISSING,
    STABILITY_ACCEPTABLE_FOR_RESEARCH,
    STABILITY_SAMPLE_SIZE_INSUFFICIENT,
    STABILITY_SEGMENT_VARIANCE_UNSTABLE,
    STABILITY_DRAWDOWN_RISK_HIGH,
)
from wbc_backend.recommendation.p28_sample_density_analyzer import (
    load_p27_date_results,
    load_p27_segment_results,
    summarize_sample_density,
    identify_sparse_dates,
    identify_sparse_segments,
)
from wbc_backend.recommendation.p28_performance_variance_analyzer import (
    summarize_performance_variance,
)
from wbc_backend.recommendation.p28_risk_drawdown_analyzer import (
    summarize_risk_profile,
)

# Segment ROI std threshold for variance instability flag
_SEGMENT_ROI_STD_UNSTABLE_THRESHOLD: float = 0.50  # 50% std relative to stake


# ---------------------------------------------------------------------------
# Gate determination
# ---------------------------------------------------------------------------


def determine_p28_gate(summary: P28StabilityAuditSummary) -> str:
    """
    Determine gate decision from the audit summary.

    Priority:
      1. Sample size insufficient → P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
      2. Drawdown exceeds limit   → P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT
      3. Variance unstable        → P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE
      4. All checks pass          → P28_TRUE_DATE_STABILITY_AUDIT_READY
    """
    if not summary.sample_size_pass:
        return P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
    if summary.max_drawdown_pct > MAX_DRAWDOWN_PCT_LIMIT:
        return P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT
    if summary.segment_roi_std > _SEGMENT_ROI_STD_UNSTABLE_THRESHOLD:
        return P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE
    return P28_TRUE_DATE_STABILITY_AUDIT_READY


def _gate_to_audit_status(gate: str) -> str:
    mapping = {
        P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT: STABILITY_SAMPLE_SIZE_INSUFFICIENT,
        P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT: STABILITY_DRAWDOWN_RISK_HIGH,
        P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE: STABILITY_SEGMENT_VARIANCE_UNSTABLE,
        P28_TRUE_DATE_STABILITY_AUDIT_READY: STABILITY_ACCEPTABLE_FOR_RESEARCH,
    }
    return mapping.get(gate, STABILITY_SAMPLE_SIZE_INSUFFICIENT)


def _gate_to_blocker_reason(gate: str, summary: P28StabilityAuditSummary) -> str:
    if gate == P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT:
        return (
            f"total_active_entries={summary.total_active_entries} < "
            f"min_sample_size_advisory={summary.min_sample_size_advisory}"
        )
    if gate == P28_BLOCKED_DRAWDOWN_EXCEEDS_LIMIT:
        return (
            f"max_drawdown_pct={summary.max_drawdown_pct:.2f}% > "
            f"limit={MAX_DRAWDOWN_PCT_LIMIT:.1f}%"
        )
    if gate == P28_BLOCKED_SEGMENT_VARIANCE_UNSTABLE:
        return (
            f"segment_roi_std={summary.segment_roi_std:.4f} > "
            f"threshold={_SEGMENT_ROI_STD_UNSTABLE_THRESHOLD:.2f}"
        )
    return ""


# ---------------------------------------------------------------------------
# Combine modules into summary
# ---------------------------------------------------------------------------


def combine_density_variance_risk(
    density,
    variance,
    risk,
    p27_gate_data: dict,
) -> P28StabilityAuditSummary:
    """
    Assemble P28StabilityAuditSummary from the three analysis module results.
    p27_gate_data is the parsed JSON dict from p27_gate_result.json.
    """
    total_active = density.total_active_entries
    sample_size_pass = density.sample_size_pass

    aggregate_roi = float(p27_gate_data.get("aggregate_roi_units", 0.0))
    aggregate_hit = float(p27_gate_data.get("aggregate_hit_rate", 0.0))

    n_dates_total = density.n_dates_total
    n_dates_ready = density.n_dates_ready
    n_dates_blocked = density.n_dates_blocked
    n_segments = density.n_segments

    placeholder_gate = (
        P28_BLOCKED_SAMPLE_SIZE_INSUFFICIENT
        if not sample_size_pass
        else P28_TRUE_DATE_STABILITY_AUDIT_READY
    )
    placeholder_status = _gate_to_audit_status(placeholder_gate)

    summary = P28StabilityAuditSummary(
        n_dates_total=n_dates_total,
        n_dates_ready=n_dates_ready,
        n_dates_blocked=n_dates_blocked,
        n_segments=n_segments,
        total_active_entries=total_active,
        min_sample_size_advisory=density.min_sample_size_advisory,
        sample_size_pass=sample_size_pass,
        aggregate_roi_units=aggregate_roi,
        aggregate_hit_rate=aggregate_hit,
        segment_roi_min=variance.segment_roi_min,
        segment_roi_max=variance.segment_roi_max,
        segment_roi_std=variance.segment_roi_std,
        daily_active_min=density.daily_active_min,
        daily_active_max=density.daily_active_max,
        daily_active_std=density.daily_active_std,
        max_drawdown_units=risk.max_drawdown_units,
        max_drawdown_pct=risk.max_drawdown_pct,
        max_consecutive_losing_days=risk.max_consecutive_losing_days,
        bootstrap_roi_ci_low_95=variance.bootstrap_roi_ci_low_95,
        bootstrap_roi_ci_high_95=variance.bootstrap_roi_ci_high_95,
        paper_only=True,
        production_ready=False,
        audit_status=placeholder_status,
        blocker_reason="",  # filled in after gate
    )
    return summary


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _float_safe(v) -> float:
    try:
        f = float(v)
        return f if f == f else 0.0  # NaN guard
    except Exception:
        return 0.0


def write_p28_outputs(
    output_dir: Path,
    gate_result: P28GateResult,
    density,
    variance,
    risk,
    date_results_df: pd.DataFrame,
    segment_results_df: pd.DataFrame,
) -> None:
    """Write all 8 P28 output files to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. p28_gate_result.json
    gate_dict = asdict(gate_result)
    (output_dir / "p28_gate_result.json").write_text(
        json.dumps(gate_dict, indent=2, default=str), encoding="utf-8"
    )

    # 2. p28_stability_audit_summary.json
    summary_dict = {
        "p28_gate": gate_result.p28_gate,
        "audit_status": gate_result.audit_status,
        "blocker_reason": gate_result.blocker_reason,
        "n_dates_total": gate_result.n_dates_total,
        "n_dates_ready": gate_result.n_dates_ready,
        "n_dates_blocked": gate_result.n_dates_blocked,
        "n_segments": gate_result.n_segments,
        "total_active_entries": gate_result.total_active_entries,
        "min_sample_size_advisory": gate_result.min_sample_size_advisory,
        "sample_size_pass": gate_result.sample_size_pass,
        "aggregate_roi_units": gate_result.aggregate_roi_units,
        "aggregate_hit_rate": gate_result.aggregate_hit_rate,
        "segment_roi_std": gate_result.segment_roi_std,
        "max_drawdown_pct": gate_result.max_drawdown_pct,
        "max_consecutive_losing_days": gate_result.max_consecutive_losing_days,
        "bootstrap_roi_ci_low_95": gate_result.bootstrap_roi_ci_low_95,
        "bootstrap_roi_ci_high_95": gate_result.bootstrap_roi_ci_high_95,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
        "generated_at": gate_result.generated_at,
    }
    (output_dir / "p28_stability_audit_summary.json").write_text(
        json.dumps(summary_dict, indent=2, default=str), encoding="utf-8"
    )

    # 3. p28_stability_audit_summary.md
    md_lines = [
        "# P28 True-Date Backfill Stability Audit Summary",
        "",
        f"**Gate**: `{gate_result.p28_gate}`",
        f"**Audit Status**: `{gate_result.audit_status}`",
        f"**Blocker Reason**: {gate_result.blocker_reason or 'None'}",
        "",
        "## Coverage",
        f"- Dates total: {gate_result.n_dates_total}",
        f"- Dates ready: {gate_result.n_dates_ready}",
        f"- Dates blocked: {gate_result.n_dates_blocked}",
        f"- Segments: {gate_result.n_segments}",
        "",
        "## Sample Density",
        f"- Total active entries: {gate_result.total_active_entries}",
        f"- Min sample advisory: {gate_result.min_sample_size_advisory}",
        f"- Sample size pass: {gate_result.sample_size_pass}",
        f"- Daily active min: {density.daily_active_min:.1f}",
        f"- Daily active max: {density.daily_active_max:.1f}",
        f"- Daily active std: {density.daily_active_std:.2f}",
        "",
        "## Performance Variance",
        f"- Aggregate ROI: {gate_result.aggregate_roi_units:.4f}",
        f"- Aggregate hit rate: {gate_result.aggregate_hit_rate:.4f}",
        f"- Segment ROI std: {gate_result.segment_roi_std:.4f}",
        f"- Bootstrap 95% CI: [{gate_result.bootstrap_roi_ci_low_95:.4f}, "
        f"{gate_result.bootstrap_roi_ci_high_95:.4f}]",
        "- Note: ROI CI is for research stability only — not proof of edge",
        "",
        "## Risk / Drawdown",
        f"- Max drawdown: {gate_result.max_drawdown_units:.4f} units "
        f"({gate_result.max_drawdown_pct:.2f}%)",
        f"- Max consecutive losing days: {gate_result.max_consecutive_losing_days}",
        "",
        "## Policy",
        f"- paper_only: {gate_result.paper_only}",
        f"- production_ready: {gate_result.production_ready}",
        f"- Generated at: {gate_result.generated_at}",
    ]
    (output_dir / "p28_stability_audit_summary.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8"
    )

    # 4. sample_density_profile.json
    density_dict = asdict(density)
    # Convert tuples to lists for JSON serialization
    density_dict["sparse_date_list"] = list(density_dict.get("sparse_date_list", []))
    density_dict["sparse_segment_list"] = list(density_dict.get("sparse_segment_list", []))
    (output_dir / "sample_density_profile.json").write_text(
        json.dumps(density_dict, indent=2, default=str), encoding="utf-8"
    )

    # 5. performance_variance_profile.json
    variance_dict = asdict(variance)
    (output_dir / "performance_variance_profile.json").write_text(
        json.dumps(variance_dict, indent=2, default=str), encoding="utf-8"
    )

    # 6. risk_drawdown_profile.json
    risk_dict = asdict(risk)
    (output_dir / "risk_drawdown_profile.json").write_text(
        json.dumps(risk_dict, indent=2, default=str), encoding="utf-8"
    )

    # 7. sparse_dates.csv
    sparse_dates = list(density.sparse_date_list)
    sparse_dates_df = pd.DataFrame({"sparse_date": sparse_dates})
    sparse_dates_df.to_csv(output_dir / "sparse_dates.csv", index=False)

    # 8. sparse_segments.csv
    sparse_segs = list(density.sparse_segment_list)
    sparse_segs_df = pd.DataFrame({"sparse_segment": sparse_segs})
    sparse_segs_df.to_csv(output_dir / "sparse_segments.csv", index=False)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_p28_true_date_stability_audit(
    p27_dir: Path,
    output_dir: Path,
    min_sample_size: int = MIN_SAMPLE_SIZE_ADVISORY,
) -> P28GateResult:
    """
    Run the full P28 True-Date Backfill Stability Audit.

    Args:
        p27_dir: Path to the P27 output directory containing date_results.csv,
                 segment_results.csv, p27_gate_result.json, blocked_segments.json
        output_dir: Path to write P28 output files
        min_sample_size: Advisory minimum sample size (default 1500)

    Returns:
        P28GateResult with all audit fields populated.

    Gate priority:
      sample_size_insufficient → drawdown → variance → ready
    """
    p27_dir = Path(p27_dir)
    output_dir = Path(output_dir)

    # --- Load inputs ---
    date_results_path = p27_dir / "date_results.csv"
    segment_results_path = p27_dir / "segment_results.csv"
    gate_result_path = p27_dir / "p27_gate_result.json"
    blocked_path = p27_dir / "blocked_segments.json"

    if not date_results_path.exists() or not segment_results_path.exists():
        raise FileNotFoundError(
            f"P28: Required P27 input files not found in {p27_dir}"
        )

    date_df = load_p27_date_results(date_results_path)
    segment_df = load_p27_segment_results(segment_results_path)

    p27_gate_data: dict = {}
    if gate_result_path.exists():
        p27_gate_data = json.loads(gate_result_path.read_text(encoding="utf-8"))

    blocked_data: dict = {}
    if blocked_path.exists():
        blocked_data = json.loads(blocked_path.read_text(encoding="utf-8"))

    # Parse blocked date counts from p27 gate data
    n_dates_total = int(p27_gate_data.get("n_dates_requested", len(date_df)))
    n_dates_ready = int(p27_gate_data.get("n_dates_ready", 0))
    n_dates_blocked = int(p27_gate_data.get("n_dates_blocked", 0))

    # --- Run analysis modules ---
    density = summarize_sample_density(
        date_df, segment_df,
        n_dates_total=n_dates_total,
        n_dates_ready=n_dates_ready,
        n_dates_blocked=n_dates_blocked,
        min_sample_size=min_sample_size,
    )

    variance = summarize_performance_variance(
        date_df, segment_df,
        bootstrap_n_iter=2000,
        bootstrap_seed=42,
    )

    risk = summarize_risk_profile(date_df)

    # --- Combine and determine gate ---
    summary = combine_density_variance_risk(density, variance, risk, p27_gate_data)
    gate = determine_p28_gate(summary)
    audit_status = _gate_to_audit_status(gate)
    blocker_reason = _gate_to_blocker_reason(gate, summary)

    generated_at = datetime.now(timezone.utc).isoformat()

    gate_result = P28GateResult(
        p28_gate=gate,
        n_dates_total=summary.n_dates_total,
        n_dates_ready=summary.n_dates_ready,
        n_dates_blocked=summary.n_dates_blocked,
        n_segments=summary.n_segments,
        total_active_entries=summary.total_active_entries,
        min_sample_size_advisory=summary.min_sample_size_advisory,
        sample_size_pass=summary.sample_size_pass,
        aggregate_roi_units=summary.aggregate_roi_units,
        aggregate_hit_rate=summary.aggregate_hit_rate,
        segment_roi_std=summary.segment_roi_std,
        daily_active_std=density.daily_active_std,
        max_drawdown_units=risk.max_drawdown_units,
        max_drawdown_pct=risk.max_drawdown_pct,
        max_consecutive_losing_days=risk.max_consecutive_losing_days,
        bootstrap_roi_ci_low_95=variance.bootstrap_roi_ci_low_95,
        bootstrap_roi_ci_high_95=variance.bootstrap_roi_ci_high_95,
        paper_only=True,
        production_ready=False,
        audit_status=audit_status,
        blocker_reason=blocker_reason,
        generated_at=generated_at,
    )

    # --- Write outputs (always, even if blocked) ---
    write_p28_outputs(
        output_dir=output_dir,
        gate_result=gate_result,
        density=density,
        variance=variance,
        risk=risk,
        date_results_df=date_df,
        segment_results_df=segment_df,
    )

    return gate_result
