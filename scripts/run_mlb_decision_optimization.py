#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.models.mlb_decision_optimizer import optimize_mlb_decision_layer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLB decision optimization on strict-only walk-forward outputs.")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_decision_optimization_report.json")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--n-splits", type=int, default=6)
    args = parser.parse_args()

    report = optimize_mlb_decision_layer(
        csv_path=args.csv_path,
        context_path=args.context_path,
        n_splits=args.n_splits,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "report_path": args.report_path,
                "diagnosis": report.get("diagnosis"),
                "best_method": report.get("calibration_metrics_before_after", {}).get("best_method"),
                "optimal_threshold": report.get("optimal_threshold"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
