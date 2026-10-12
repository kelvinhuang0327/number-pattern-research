#!/usr/bin/env python3
"""
scripts/run_p16_recommendation_gate_reevaluation.py

P16 Recommendation Gate Re-Evaluation CLI — CEO-revised scope.

Consumes P15 odds-aware artifacts + sweep results to produce
risk-hardened paper recommendation rows.

Usage:
    python scripts/run_p16_recommendation_gate_reevaluation.py \
        --joined-oof outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/joined_oof_with_odds.csv \
        --p15-summary outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/simulation_summary.json \
        --p15-ledger  outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/simulation_ledger.csv \
        --output-dir  outputs/predictions/PAPER/2026-05-12/p16_recommendation_gate \
        --paper-only true \
        --edge-threshold-grid 0.01,0.02,0.03,0.05,0.08 \
        --min-bets-floor 50 \
        --max-drawdown-limit 0.25 \
        --sharpe-floor 0.0

PAPER_ONLY: Paper simulation only. No production bets. No live TSL.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── Project imports ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.recommendation.p16_recommendation_gate import (
    BLOCKED_DRAWDOWN,
    BLOCKED_EDGE_BELOW,
    BLOCKED_INVALID_ODDS,
    BLOCKED_INVALID_PROB,
    BLOCKED_NEGATIVE_BSS,
    BLOCKED_NOT_PAPER_ONLY,
    BLOCKED_ODDS_NOT_JOINED,
    BLOCKED_PRODUCTION,
    BLOCKED_SHARPE,
    BLOCKED_SWEEP_INSUFFICIENT,
    ELIGIBLE,
    apply_gate,
)
from wbc_backend.recommendation.p16_recommendation_input_adapter import (
    SOURCE_BSS_OOF,
    load_p16_input_rows,
    input_rows_to_dataframe,
)
from wbc_backend.recommendation.p16_recommendation_row_builder import (
    build_all_rows,
)
from wbc_backend.simulation.edge_threshold_sweep import (
    SWEEP_INSUFFICIENT_SAMPLES,
    sweep_edge_thresholds,
)
from wbc_backend.simulation.strategy_risk_metrics import (
    StrategyRiskProfile,
    summarize_strategy_risk,
)


# ── Gate-level decisions ──────────────────────────────────────────────────────

GATE_READY = "P16_PAPER_RECOMMENDATION_GATE_READY"
GATE_NO_ELIGIBLE = "P16_BLOCKED_NO_ELIGIBLE_ROWS"
GATE_INPUT_MISSING = "P16_BLOCKED_INPUT_MISSING"
GATE_SWEEP_INSUFFICIENT = "P16_BLOCKED_SWEEP_INSUFFICIENT_SAMPLES"
GATE_RISK_VIOLATION = "P16_BLOCKED_RISK_PROFILE_VIOLATION"
GATE_FAIL_CONTRACT = "P16_FAIL_CONTRACT_VIOLATION"
GATE_FAIL_NON_DET = "P16_FAIL_NON_DETERMINISTIC"


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P16 Recommendation Gate Re-Evaluation")
    p.add_argument("--joined-oof", required=True)
    p.add_argument("--p15-summary", required=True)
    p.add_argument("--p15-ledger", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--paper-only", default="true")
    p.add_argument("--edge-threshold-grid", default="0.01,0.02,0.03,0.05,0.08")
    p.add_argument("--min-bets-floor", type=int, default=50)
    p.add_argument("--max-drawdown-limit", type=float, default=0.25)
    p.add_argument("--sharpe-floor", type=float, default=0.0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Validate --paper-only
    if args.paper_only.lower() != "true":
        print("ERROR: --paper-only must be 'true'. This script is PAPER_ONLY.")
        return 2

    # ── Input validation ──────────────────────────────────────────────────────
    joined_oof_path = Path(args.joined_oof)
    p15_summary_path = Path(args.p15_summary)
    p15_ledger_path = Path(args.p15_ledger)
    output_dir = Path(args.output_dir)

    for path, label in [
        (joined_oof_path, "joined-oof"),
        (p15_summary_path, "p15-summary"),
        (p15_ledger_path, "p15-ledger"),
    ]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}")
            return 2

    thresholds = [float(t.strip()) for t in args.edge_threshold_grid.split(",")]
    min_bets_floor = args.min_bets_floor
    max_drawdown_limit = args.max_drawdown_limit
    sharpe_floor = args.sharpe_floor

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load P15 summary ──────────────────────────────────────────────────────
    with open(p15_summary_path) as f:
        p15_summary = json.load(f)

    source_bss_oof = float(p15_summary.get("source_bss_oof", SOURCE_BSS_OOF))
    odds_join_coverage_n = int(p15_summary.get("odds_join_coverage", 0))
    n_samples = int(p15_summary.get("n_samples", 0))
    odds_join_coverage_frac = (
        odds_join_coverage_n / n_samples if n_samples > 0 else 0.0
    )

    # ── Load P15 ledger for sweep ─────────────────────────────────────────────
    ledger_df = pd.read_csv(p15_ledger_path)

    # ── Task 3: Edge threshold sweep ──────────────────────────────────────────
    sweep_report = sweep_edge_thresholds(
        ledger_df,
        thresholds=thresholds,
        min_bets_floor=min_bets_floor,
    )

    # ── Determine selected threshold and risk profile ─────────────────────────
    sweep_status = sweep_report.sweep_status

    if sweep_status == SWEEP_INSUFFICIENT_SAMPLES:
        p16_gate = GATE_SWEEP_INSUFFICIENT
        selected_threshold = sweep_report.fallback_threshold or thresholds[0]
        print(f"WARNING: {SWEEP_INSUFFICIENT_SAMPLES} — no threshold met n_bets >= {min_bets_floor}")
    else:
        selected_threshold = sweep_report.recommended_threshold
        assert selected_threshold is not None

    # Risk profile at selected threshold
    from wbc_backend.simulation.edge_threshold_sweep import _filter_ledger_by_edge
    selected_ledger = _filter_ledger_by_edge(ledger_df, selected_threshold)
    risk_profile = summarize_strategy_risk(selected_ledger)

    # Check risk profile against limits
    risk_violation = False
    if risk_profile.max_drawdown_pct > (max_drawdown_limit * 100.0):
        print(
            f"WARNING: max_drawdown={risk_profile.max_drawdown_pct:.2f}% exceeds "
            f"limit={max_drawdown_limit * 100:.1f}%"
        )
        risk_violation = True
    if risk_profile.sharpe_ratio < sharpe_floor:
        print(
            f"WARNING: sharpe={risk_profile.sharpe_ratio:.4f} below floor={sharpe_floor}"
        )
        risk_violation = True

    # ── Task 5: Load P16 input rows ───────────────────────────────────────────
    input_rows = load_p16_input_rows(
        str(joined_oof_path),
        source_bss_oof=source_bss_oof,
        odds_join_coverage=odds_join_coverage_frac,
    )

    n_input_rows = len(input_rows)
    n_joined_rows = sum(1 for r in input_rows if r.odds_join_status == "JOINED")
    n_eligible_input = sum(1 for r in input_rows if r.eligible)

    # ── Task 6: Apply gate to each row ────────────────────────────────────────
    gate_results = [
        apply_gate(
            row=row,
            selected_edge_threshold=selected_threshold,
            risk_profile=risk_profile,
            sweep_status=sweep_status,
            max_drawdown_limit=max_drawdown_limit,
            sharpe_floor=sharpe_floor,
        )
        for row in input_rows
    ]

    # ── Task 7: Build recommendation rows ─────────────────────────────────────
    rec_rows = build_all_rows(
        input_rows=input_rows,
        gate_results=gate_results,
        risk_profile=risk_profile,
        selected_edge_threshold=selected_threshold,
    )

    n_recommended = sum(1 for r in rec_rows if r.gate_decision == ELIGIBLE)
    n_blocked = sum(1 for r in rec_rows if r.gate_decision != ELIGIBLE)

    gate_reason_counts = dict(Counter(r.gate_decision for r in rec_rows))

    # Determine overall gate
    if sweep_status == SWEEP_INSUFFICIENT_SAMPLES:
        p16_gate = GATE_SWEEP_INSUFFICIENT
    elif risk_violation:
        p16_gate = GATE_RISK_VIOLATION
    elif n_recommended == 0:
        p16_gate = GATE_NO_ELIGIBLE
    else:
        p16_gate = GATE_READY

    # ── Write outputs ─────────────────────────────────────────────────────────

    # 1. recommendation_rows.csv
    rows_df = pd.DataFrame([r.to_dict() for r in rec_rows])
    rows_df.to_csv(output_dir / "recommendation_rows.csv", index=False)

    # 2. strategy_risk_profile.json
    risk_dict = {
        "roi_mean": risk_profile.roi_mean,
        "roi_ci_low_95": risk_profile.roi_ci_low_95,
        "roi_ci_high_95": risk_profile.roi_ci_high_95,
        "max_drawdown_pct": risk_profile.max_drawdown_pct,
        "sharpe_ratio": risk_profile.sharpe_ratio,
        "max_consecutive_loss": risk_profile.max_consecutive_loss,
        "n_bets": risk_profile.n_bets,
        "n_winning_bets": risk_profile.n_winning_bets,
        "hit_rate": risk_profile.hit_rate,
        "selected_edge_threshold": selected_threshold,
        "paper_only": True,
        "production_ready": False,
    }
    with open(output_dir / "strategy_risk_profile.json", "w") as f:
        json.dump(risk_dict, f, indent=2)

    # 3. edge_threshold_sweep.json
    sweep_dict = {
        "sweep_status": sweep_report.sweep_status,
        "recommended_threshold": sweep_report.recommended_threshold,
        "recommended_reason": sweep_report.recommended_reason,
        "fallback_threshold": sweep_report.fallback_threshold,
        "min_bets_floor": min_bets_floor,
        "per_threshold": [
            {
                "threshold": tr.threshold,
                "n_eligible_rows": tr.n_eligible_rows,
                "n_bets": tr.risk_profile.n_bets,
                "roi_mean": tr.risk_profile.roi_mean,
                "roi_ci_low_95": tr.risk_profile.roi_ci_low_95,
                "roi_ci_high_95": tr.risk_profile.roi_ci_high_95,
                "max_drawdown_pct": tr.risk_profile.max_drawdown_pct,
                "sharpe_ratio": tr.risk_profile.sharpe_ratio,
                "hit_rate": tr.risk_profile.hit_rate,
            }
            for tr in sweep_report.per_threshold_rows
        ],
    }
    with open(output_dir / "edge_threshold_sweep.json", "w") as f:
        json.dump(sweep_dict, f, indent=2)

    # 4. edge_threshold_sweep.md
    sweep_md_lines = [
        "# P16 Edge Threshold Sweep",
        "",
        f"- **Sweep Status**: {sweep_report.sweep_status}",
        f"- **Recommended Threshold**: {sweep_report.recommended_threshold}",
        f"- **Recommended Reason**: {sweep_report.recommended_reason}",
        f"- **Fallback Threshold**: {sweep_report.fallback_threshold}",
        f"- **Min Bets Floor**: {min_bets_floor}",
        "",
        "## Per-Threshold Results",
        "",
        "| Threshold | N Rows | N Bets | ROI Mean | CI Low | CI High | Max DD | Sharpe | Hit Rate |",
        "|-----------|--------|--------|----------|--------|---------|--------|--------|----------|",
    ]
    for tr in sweep_report.per_threshold_rows:
        rp = tr.risk_profile
        sweep_md_lines.append(
            f"| {tr.threshold:.4f} | {tr.n_eligible_rows} | {rp.n_bets} | "
            f"{rp.roi_mean:.2f}% | {rp.roi_ci_low_95:.2f}% | {rp.roi_ci_high_95:.2f}% | "
            f"{rp.max_drawdown_pct:.2f}% | {rp.sharpe_ratio:.4f} | {rp.hit_rate:.4f} |"
        )
    with open(output_dir / "edge_threshold_sweep.md", "w") as f:
        f.write("\n".join(sweep_md_lines) + "\n")

    # 5. gate_reason_counts.json
    with open(output_dir / "gate_reason_counts.json", "w") as f:
        json.dump(gate_reason_counts, f, indent=2, sort_keys=True)

    # 6. recommendation_summary.json
    top_reasons = sorted(gate_reason_counts.items(), key=lambda x: -x[1])[:5]
    summary = {
        "p16_gate": p16_gate,
        "n_input_rows": n_input_rows,
        "n_joined_rows": n_joined_rows,
        "n_eligible_rows": n_eligible_input,
        "n_recommended_rows": n_recommended,
        "n_blocked_rows": n_blocked,
        "selected_edge_threshold": selected_threshold,
        "sweep_recommended_reason": sweep_report.recommended_reason,
        "sweep_status": sweep_status,
        "strategy_roi_mean": risk_profile.roi_mean,
        "strategy_roi_ci_low_95": risk_profile.roi_ci_low_95,
        "strategy_roi_ci_high_95": risk_profile.roi_ci_high_95,
        "strategy_max_drawdown": risk_profile.max_drawdown_pct,
        "strategy_sharpe": risk_profile.sharpe_ratio,
        "strategy_n_bets": risk_profile.n_bets,
        "source_bss_oof": source_bss_oof,
        "odds_join_coverage": odds_join_coverage_frac,
        "production_ready": False,
        "paper_only": True,
        "top_gate_reasons": dict(top_reasons),
        "generated_from_p15_gate": "P15_ODDS_AWARE_SIMULATION_READY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(output_dir / "recommendation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # 7. recommendation_summary.md
    md_lines = [
        "# P16 Recommendation Gate Re-Evaluation",
        "",
        f"**Gate Decision**: `{p16_gate}`",
        "",
        "## Key Metrics",
        "",
        f"- N input rows: {n_input_rows}",
        f"- N joined rows: {n_joined_rows}",
        f"- N eligible input rows: {n_eligible_input}",
        f"- N recommended rows: **{n_recommended}**",
        f"- N blocked rows: {n_blocked}",
        f"- Selected edge threshold: **{selected_threshold:.4f}** (from sweep)",
        f"- Sweep reason: {sweep_report.recommended_reason}",
        "",
        "## Strategy Risk Profile",
        "",
        f"- ROI mean: {risk_profile.roi_mean:.4f}%",
        f"- ROI 95% CI: [{risk_profile.roi_ci_low_95:.4f}%, {risk_profile.roi_ci_high_95:.4f}%]",
        f"- Max drawdown: {risk_profile.max_drawdown_pct:.4f}%",
        f"- Sharpe: {risk_profile.sharpe_ratio:.4f}",
        f"- N bets: {risk_profile.n_bets}",
        f"- Hit rate: {risk_profile.hit_rate:.4f}",
        "",
        "## Gate Reason Distribution",
        "",
    ]
    for reason, count in sorted(gate_reason_counts.items(), key=lambda x: -x[1]):
        md_lines.append(f"- `{reason}`: {count}")
    md_lines += [
        "",
        "## Safety",
        "",
        "- `production_ready`: **false**",
        "- `paper_only`: **true**",
        "- No live TSL calls. No real bets.",
    ]
    with open(output_dir / "recommendation_summary.md", "w") as f:
        f.write("\n".join(md_lines) + "\n")

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("P16 RECOMMENDATION GATE RE-EVALUATION")
    print(f"{'='*60}")
    print(f"p16_gate:                {p16_gate}")
    print(f"selected_edge_threshold: {selected_threshold:.4f}")
    print(f"sweep_recommended_reason: {sweep_report.recommended_reason}")
    print(f"n_input_rows:            {n_input_rows}")
    print(f"n_joined_rows:           {n_joined_rows}")
    print(f"n_eligible_rows:         {n_eligible_input}")
    print(f"n_recommended_rows:      {n_recommended}")
    print(f"n_blocked_rows:          {n_blocked}")
    print(f"\nStrategy Risk Profile:")
    print(f"  strategy_roi_mean:     {risk_profile.roi_mean:.4f}%")
    print(f"  roi_ci_low_95:         {risk_profile.roi_ci_low_95:.4f}%")
    print(f"  roi_ci_high_95:        {risk_profile.roi_ci_high_95:.4f}%")
    print(f"  strategy_max_drawdown: {risk_profile.max_drawdown_pct:.4f}%")
    print(f"  strategy_sharpe:       {risk_profile.sharpe_ratio:.4f}")
    print(f"  strategy_n_bets:       {risk_profile.n_bets}")
    print(f"\nTop gate reasons:")
    for reason, count in sorted(gate_reason_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"  {reason}: {count}")
    print(f"\nproduction_ready: false")
    print(f"paper_only: true")
    print(f"{'='*60}\n")
    print(f"Outputs written to: {output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
