#!/usr/bin/env python3
"""Run the local MLB prediction -> paper-market -> result workflow snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.mlb_product_workflow_snapshot import (  # noqa: E402
    DEFAULT_KELLY_CAP,
    DEFAULT_KELLY_FRACTION,
    DEFAULT_MONEYLINE_MIN_EDGE,
    DEFAULT_MONEYLINE_MIN_EV,
    run_workflow_snapshot,
    write_workflow_reports,
)


DEFAULT_WARMUP = ROOT / "data" / "mlb_2025" / "mlb-2024-asplayed.csv"
DEFAULT_EVAL = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
DEFAULT_2026_PREDICTIONS = ROOT / "data" / "mlb_2026" / "predictions" / "mlb_2026_prediction_rows.jsonl"
DEFAULT_2026_OUTCOMES = ROOT / "data" / "mlb_2026" / "derived" / "p84e_2026_outcome_attached_prediction_rows.jsonl"
DEFAULT_OUT_DIR = ROOT / "report"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local MLB retrain + paper Moneyline workflow snapshot."
    )
    parser.add_argument("--warmup-path", default=str(DEFAULT_WARMUP))
    parser.add_argument("--eval-path", default=str(DEFAULT_EVAL))
    parser.add_argument("--prediction-2026-path", default=str(DEFAULT_2026_PREDICTIONS))
    parser.add_argument("--outcome-2026-path", default=str(DEFAULT_2026_OUTCOMES))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--moneyline-min-ev", type=float, default=DEFAULT_MONEYLINE_MIN_EV)
    parser.add_argument("--moneyline-min-edge", type=float, default=DEFAULT_MONEYLINE_MIN_EDGE)
    parser.add_argument("--kelly-fraction", type=float, default=DEFAULT_KELLY_FRACTION)
    parser.add_argument("--kelly-cap", type=float, default=DEFAULT_KELLY_CAP)
    args = parser.parse_args()

    warmup_path = Path(args.warmup_path)
    eval_path = Path(args.eval_path)
    prediction_path = Path(args.prediction_2026_path)
    outcome_path = Path(args.outcome_2026_path) if args.outcome_2026_path else None
    out_dir = Path(args.out_dir)

    missing = [p for p in (warmup_path, eval_path, prediction_path) if not p.exists()]
    if missing:
        print("MLB_WORKFLOW_BLOCKED_MISSING_INPUTS", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 2

    payload = run_workflow_snapshot(
        warmup_path=warmup_path,
        eval_path=eval_path,
        prediction_2026_path=prediction_path,
        outcome_2026_path=outcome_path if outcome_path and outcome_path.exists() else None,
        min_ev=args.moneyline_min_ev,
        min_edge=args.moneyline_min_edge,
        kelly_fraction=args.kelly_fraction,
        kelly_cap=args.kelly_cap,
    )
    paths = write_workflow_reports(payload, out_dir)

    retrain = payload["retrain_scorecard"]
    moneyline = payload["moneyline_strategy"]["summary"]
    latest = payload["local_2026_prediction_snapshot"]
    print("=" * 78)
    print("MLB LOCAL PREDICTION WORKFLOW SNAPSHOT")
    print("=" * 78)
    print(f"best_model_by_brier     : {retrain['best_by_brier']}")
    print(
        "train/test              : "
        f"{retrain['split']['train_rows']} / {retrain['split']['test_rows']}"
    )
    print(f"eval_rows               : {retrain['eval_rows']}")
    print(f"moneyline_rows_scored   : {moneyline['prediction_rows_scored']}")
    print(f"paper_candidates        : {moneyline['paper_candidate_count']}")
    print(f"paper_hit_rate          : {moneyline['hit_rate']:.2%}")
    roi = moneyline["roi_on_staked_units"]
    print(f"paper_roi_on_staked     : {roi:.2%}" if roi is not None else "paper_roi_on_staked     : N/A")
    print(f"net_result_units        : {moneyline['net_result_units']}")
    print(f"latest_2026_local_date  : {latest.get('latest_local_prediction_date')}")
    outcome = latest.get("outcome_attached_summary")
    if outcome:
        all_outcomes = outcome["all_outcome_attached"]
        print(
            "2026_outcome_accuracy   : "
            f"{all_outcomes['accuracy']:.2%} ({all_outcomes['correct']}/{all_outcomes['n']})"
        )
    print("-" * 78)
    for name, path in paths.items():
        print(f"{name:<24}: {path}")
    print("=" * 78)
    print("Paper-only local workflow validation. No live provider call and no real bet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

