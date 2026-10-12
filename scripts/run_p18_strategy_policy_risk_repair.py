"""
scripts/run_p18_strategy_policy_risk_repair.py

P18 CLI — Strategy policy risk repair after P16 drawdown violation.

Usage:
    .venv/bin/python scripts/run_p18_strategy_policy_risk_repair.py \\
        --p15-ledger outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/simulation_ledger.csv \\
        --p16-summary outputs/predictions/PAPER/2026-05-12/p16_recommendation_gate/recommendation_summary.json \\
        --output-dir outputs/predictions/PAPER/2026-05-12/p18_strategy_policy_risk_repair \\
        --paper-only true \\
        --min-bets-floor 50 \\
        --max-drawdown-limit 0.25 \\
        --sharpe-floor 0.0

Outputs (6 files):
    strategy_policy_grid.csv
    strategy_policy_grid_summary.json
    strategy_policy_grid_summary.md
    selected_strategy_policy.json
    drawdown_diagnostics.json
    drawdown_diagnostics.md

PAPER_ONLY=true | PRODUCTION_READY=false always.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _resolve_modules() -> None:
    """Ensure project root is on sys.path."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_resolve_modules()

import pandas as pd

from wbc_backend.simulation.p18_drawdown_diagnostics import run_drawdown_diagnostics
from wbc_backend.simulation.p18_strategy_policy_contract import (
    GATE_BLOCKED,
    GATE_INPUT_MISSING,
    GATE_REPAIRED,
    build_recommendation,
)
from wbc_backend.simulation.p18_strategy_policy_grid import (
    DEFAULT_EDGE_THRESHOLDS,
    DEFAULT_KELLY_FRACTIONS,
    DEFAULT_MAX_STAKE_CAPS,
    DEFAULT_MIN_BETS_FLOOR,
    DEFAULT_ODDS_DECIMAL_MAXES,
    run_policy_grid_search,
)


# ── Argument parsing ───────────────────────────────────────────────────────────

def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P18 Strategy Policy Risk Repair CLI"
    )
    parser.add_argument(
        "--p15-ledger", required=True,
        help="Path to P15 simulation_ledger.csv",
    )
    parser.add_argument(
        "--p16-summary", required=True,
        help="Path to P16 recommendation_summary.json",
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Directory to write all outputs",
    )
    parser.add_argument(
        "--paper-only", default="true",
        help="Must be 'true' (safety guard)",
    )
    parser.add_argument(
        "--min-bets-floor", type=int, default=DEFAULT_MIN_BETS_FLOOR,
    )
    parser.add_argument(
        "--max-drawdown-limit", type=float, default=0.25,
    )
    parser.add_argument(
        "--sharpe-floor", type=float, default=0.0,
    )
    parser.add_argument(
        "--bootstrap-n-iter", type=int, default=2000,
        help="Bootstrap iterations for CI (default 2000; use smaller for testing)",
    )
    return parser.parse_args(argv)


# ── Writers ────────────────────────────────────────────────────────────────────

def _write_grid_csv(candidates, out_path: Path) -> None:
    if not candidates:
        out_path.write_text("")
        return
    rows = []
    for c in candidates:
        rows.append({
            "policy_id": c.policy_id,
            "edge_threshold": c.edge_threshold,
            "max_stake_cap": c.max_stake_cap,
            "kelly_fraction": c.kelly_fraction,
            "odds_decimal_max": c.odds_decimal_max,
            "n_bets": c.n_bets,
            "roi_mean": c.roi_mean,
            "roi_ci_low_95": c.roi_ci_low_95,
            "roi_ci_high_95": c.roi_ci_high_95,
            "max_drawdown_pct": c.max_drawdown_pct,
            "sharpe_ratio": c.sharpe_ratio,
            "hit_rate": c.hit_rate,
            "max_consecutive_loss": c.max_consecutive_loss,
            "avg_edge": c.avg_edge,
            "avg_stake_fraction": c.avg_stake_fraction,
            "total_turnover": c.total_turnover,
            "policy_pass": c.policy_pass,
            "fail_reasons": "|".join(c.fail_reasons),
        })
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_grid_summary_json(
    grid_report,
    recommendation,
    p16_summary: dict,
    out_path: Path,
) -> dict:
    best = grid_report.best_candidate
    summary = {
        "p18_gate": grid_report.gate_decision,
        "p16_prior_gate": p16_summary.get("p16_gate", "UNKNOWN"),
        "p16_prior_max_drawdown": p16_summary.get("strategy_max_drawdown", None),
        "p16_prior_sharpe": p16_summary.get("strategy_sharpe", None),
        "p16_prior_n_bets": p16_summary.get("strategy_n_bets", None),
        "n_candidates_evaluated": grid_report.n_candidates_evaluated,
        "n_candidates_passing": grid_report.n_candidates_passing,
        "selection_reason": grid_report.selection_reason,
        "selected_policy_id": recommendation.selected_policy_id,
        "selected_edge_threshold": recommendation.edge_threshold,
        "selected_max_stake_cap": recommendation.max_stake_cap,
        "selected_kelly_fraction": recommendation.kelly_fraction,
        "selected_odds_decimal_max": recommendation.odds_decimal_max,
        "selected_n_bets": recommendation.n_bets,
        "selected_roi_mean": recommendation.roi_mean,
        "selected_roi_ci_low_95": recommendation.roi_ci_low_95,
        "selected_roi_ci_high_95": recommendation.roi_ci_high_95,
        "selected_max_drawdown_pct": recommendation.max_drawdown_pct,
        "selected_sharpe_ratio": recommendation.sharpe_ratio,
        "selected_hit_rate": recommendation.hit_rate,
        "production_ready": False,
        "paper_only": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    return summary


def _write_grid_summary_md(summary: dict, grid_report, out_path: Path) -> None:
    lines = [
        "# P18 Strategy Policy Risk Repair — Grid Summary",
        "",
        f"**P18 Gate**: `{summary['p18_gate']}`",
        f"**P16 Prior Gate**: `{summary['p16_prior_gate']}`",
        f"**P16 Prior Max Drawdown**: {summary.get('p16_prior_max_drawdown', 'N/A'):.2f}%"
        if summary.get("p16_prior_max_drawdown") else "**P16 Prior Max Drawdown**: N/A",
        "",
        f"**Candidates evaluated**: {summary['n_candidates_evaluated']}",
        f"**Candidates passing**: {summary['n_candidates_passing']}",
        "",
        "## Selected Policy",
        "",
    ]
    if summary.get("selected_policy_id"):
        lines += [
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| policy_id | `{summary['selected_policy_id']}` |",
            f"| edge_threshold | {summary['selected_edge_threshold']} |",
            f"| max_stake_cap | {summary['selected_max_stake_cap']} |",
            f"| kelly_fraction | {summary['selected_kelly_fraction']} |",
            f"| odds_decimal_max | {summary['selected_odds_decimal_max']} |",
            f"| n_bets | {summary['selected_n_bets']} |",
            f"| roi_mean | {summary['selected_roi_mean']:.4f}% |",
            f"| roi_ci_low_95 | {summary['selected_roi_ci_low_95']:.4f}% |",
            f"| roi_ci_high_95 | {summary['selected_roi_ci_high_95']:.4f}% |",
            f"| max_drawdown_pct | {summary['selected_max_drawdown_pct']:.4f}% |",
            f"| sharpe_ratio | {summary['selected_sharpe_ratio']:.4f} |",
            f"| hit_rate | {summary['selected_hit_rate']:.4f} |",
        ]
    else:
        lines.append(f"**NO POLICY SELECTED**: {summary['selection_reason']}")

    lines += [
        "",
        f"**production_ready**: {summary['production_ready']}",
        f"**paper_only**: {summary['paper_only']}",
        "",
        f"*Generated*: {summary.get('generated_at_utc', 'N/A')}",
    ]
    out_path.write_text("\n".join(lines))


def _write_selected_policy_json(recommendation, out_path: Path) -> None:
    out_path.write_text(
        json.dumps(recommendation.as_dict(), indent=2, default=str)
    )


def _write_diagnostics_json(diag, selected_threshold: float, out_path: Path) -> None:
    worst = diag.worst_segment
    data = {
        "threshold": diag.threshold,
        "n_eligible_bets": diag.n_eligible_bets,
        "max_drawdown_pct": diag.max_drawdown_pct,
        "worst_segment": {
            "start_row": worst.start_row,
            "end_row": worst.end_row,
            "peak_equity": worst.peak_equity,
            "trough_equity": worst.trough_equity,
            "drawdown_pct": worst.drawdown_pct,
            "n_bets_in_segment": worst.n_bets_in_segment,
        } if worst else None,
        "n_loss_clusters": len(diag.loss_clusters),
        "largest_cluster_consecutive_losses": (
            diag.loss_clusters[0].consecutive_losses if diag.loss_clusters else 0
        ),
        "top_outlier_losses": [
            {
                "row_idx": o.row_idx,
                "stake_fraction": o.stake_fraction,
                "decimal_odds": o.decimal_odds,
                "pnl": o.pnl,
            }
            for o in diag.top_outlier_losses[:5]
        ],
        "exposure_profile": {
            "n_bets": diag.exposure_profile.n_bets,
            "mean_stake": diag.exposure_profile.mean_stake,
            "max_stake": diag.exposure_profile.max_stake,
            "median_stake": diag.exposure_profile.median_stake,
            "mean_odds": diag.exposure_profile.mean_odds,
            "max_odds": diag.exposure_profile.max_odds,
            "hit_rate": diag.exposure_profile.hit_rate,
            "mean_edge": diag.exposure_profile.mean_edge,
        },
        "root_cause_flags": diag.root_cause_flags,
        "root_cause_summary": diag.root_cause_summary,
        "paper_only": True,
        "production_ready": False,
    }
    out_path.write_text(json.dumps(data, indent=2, default=str))


def _write_diagnostics_md(diag, out_path: Path) -> None:
    worst = diag.worst_segment
    lines = [
        "# P18 Drawdown Diagnostics",
        "",
        f"**P16 threshold analysed**: {diag.threshold}",
        f"**n_eligible_bets**: {diag.n_eligible_bets}",
        f"**max_drawdown_pct**: {diag.max_drawdown_pct:.2f}%",
        "",
        "## Worst Drawdown Segment",
        "",
    ]
    if worst:
        lines += [
            f"- start_row: {worst.start_row}",
            f"- end_row: {worst.end_row}",
            f"- peak_equity: {worst.peak_equity:.4f}",
            f"- trough_equity: {worst.trough_equity:.4f}",
            f"- drawdown_pct: {worst.drawdown_pct:.2f}%",
            f"- n_bets_in_segment: {worst.n_bets_in_segment}",
        ]
    else:
        lines.append("No drawdown segments detected.")

    lines += [
        "",
        "## Loss Clusters",
        f"- Total clusters (>=2 consecutive losses): {len(diag.loss_clusters)}",
    ]
    if diag.loss_clusters:
        c = diag.loss_clusters[0]
        lines.append(
            f"- Longest streak: {c.consecutive_losses} consecutive losses "
            f"(rows {c.start_row}–{c.end_row}, total_loss={c.total_loss:.4f})"
        )

    lines += [
        "",
        "## Exposure Profile",
        f"- mean_stake: {diag.exposure_profile.mean_stake:.4f}",
        f"- max_stake: {diag.exposure_profile.max_stake:.4f}",
        f"- mean_odds: {diag.exposure_profile.mean_odds:.2f}",
        f"- max_odds: {diag.exposure_profile.max_odds:.2f}",
        f"- hit_rate: {diag.exposure_profile.hit_rate:.3f}",
        f"- mean_edge: {diag.exposure_profile.mean_edge:.4f}",
        "",
        "## Root Cause",
        f"**Summary**: {diag.root_cause_summary}",
        "",
        f"**paper_only**: True | **production_ready**: False",
    ]
    out_path.write_text("\n".join(lines))


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    # Safety guard
    if args.paper_only.lower() != "true":
        print("ERROR: --paper-only must be 'true'. PAPER_ONLY is enforced.", file=sys.stderr)
        return 1

    # Validate inputs
    ledger_path = Path(args.p15_ledger)
    summary_path = Path(args.p16_summary)
    if not ledger_path.exists():
        print(f"ERROR: p15-ledger not found: {ledger_path}", file=sys.stderr)
        return 2
    if not summary_path.exists():
        print(f"ERROR: p16-summary not found: {summary_path}", file=sys.stderr)
        return 2

    # Load inputs
    ledger_df = pd.read_csv(ledger_path)
    p16_summary = json.loads(summary_path.read_text())
    p16_prior_threshold = float(p16_summary.get("selected_edge_threshold", 0.08))

    # Output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Run drawdown diagnostics on P16 prior threshold
    diag = run_drawdown_diagnostics(ledger_df, threshold=p16_prior_threshold)

    # Step 2: Run policy grid search
    grid_report = run_policy_grid_search(
        ledger_df=ledger_df,
        min_bets_floor=args.min_bets_floor,
        max_drawdown_limit=args.max_drawdown_limit,
        sharpe_floor=args.sharpe_floor,
        bootstrap_n_iter=args.bootstrap_n_iter,
    )

    # Step 3: Build recommendation
    recommendation = build_recommendation(grid_report)

    # Step 4: Write outputs
    _write_grid_csv(
        grid_report.candidates, out_dir / "strategy_policy_grid.csv"
    )
    summary = _write_grid_summary_json(
        grid_report, recommendation, p16_summary,
        out_dir / "strategy_policy_grid_summary.json",
    )
    _write_grid_summary_md(
        summary, grid_report,
        out_dir / "strategy_policy_grid_summary.md",
    )
    _write_selected_policy_json(
        recommendation, out_dir / "selected_strategy_policy.json"
    )
    _write_diagnostics_json(
        diag, p16_prior_threshold,
        out_dir / "drawdown_diagnostics.json",
    )
    _write_diagnostics_md(diag, out_dir / "drawdown_diagnostics.md")

    # Step 5: Print summary
    _print_summary(summary, diag, grid_report)

    return 0


def _print_summary(summary: dict, diag, grid_report) -> None:
    print()
    print("=" * 60)
    print("P18 STRATEGY POLICY RISK REPAIR")
    print("=" * 60)
    print(f"p18_gate:                    {summary['p18_gate']}")
    print(f"p16_prior_gate:              {summary['p16_prior_gate']}")
    print(
        f"p16_prior_max_drawdown:      "
        f"{summary.get('p16_prior_max_drawdown', 'N/A'):.2f}%"
        if summary.get("p16_prior_max_drawdown") else
        "p16_prior_max_drawdown:      N/A"
    )
    print()
    if summary.get("selected_policy_id"):
        print(f"selected_policy_id:          {summary['selected_policy_id']}")
        print(f"selected_edge_threshold:     {summary['selected_edge_threshold']}")
        print(f"selected_max_stake_cap:      {summary['selected_max_stake_cap']}")
        print(f"selected_kelly_fraction:     {summary['selected_kelly_fraction']}")
        print(f"selected_odds_decimal_max:   {summary['selected_odds_decimal_max']}")
        print(f"selected_n_bets:             {summary['selected_n_bets']}")
        print(
            f"selected_roi_mean:           {summary['selected_roi_mean']:.4f}% "
            f"(95% CI: [{summary['selected_roi_ci_low_95']:.4f}%, "
            f"{summary['selected_roi_ci_high_95']:.4f}%])"
        )
        print(f"selected_max_drawdown_pct:   {summary['selected_max_drawdown_pct']:.4f}%")
        print(f"selected_sharpe_ratio:       {summary['selected_sharpe_ratio']:.4f}")
        print(f"selected_hit_rate:           {summary['selected_hit_rate']:.4f}")
    else:
        print("NO POLICY SELECTED")
        print(f"reason: {summary['selection_reason']}")
    print()
    print(f"Drawdown diagnosis (threshold={diag.threshold}):")
    print(f"  max_drawdown_pct:          {diag.max_drawdown_pct:.2f}%")
    print(f"  n_eligible_bets:           {diag.n_eligible_bets}")
    print(f"  root_cause:                {diag.root_cause_summary}")
    print(f"  loss_clusters:             {len(diag.loss_clusters)}")
    if diag.loss_clusters:
        print(
            f"  longest_streak:            "
            f"{diag.loss_clusters[0].consecutive_losses} consecutive losses"
        )
    print()
    print(f"n_candidates_evaluated:      {summary['n_candidates_evaluated']}")
    print(f"n_candidates_passing:        {summary['n_candidates_passing']}")
    print(f"production_ready:            {summary['production_ready']}")
    print(f"paper_only:                  {summary['paper_only']}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    sys.exit(main())
