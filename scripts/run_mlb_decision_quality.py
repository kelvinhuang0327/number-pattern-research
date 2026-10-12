#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.mlb_decision_quality import evaluate_mlb_decision_quality


def main() -> None:
    parser = argparse.ArgumentParser(description="Run per-game MLB decision quality evaluation in STRICT_ONLY + PAPER_MODE.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--redesign-report-path", default="data/wbc_backend/reports/mlb_regime_feature_redesign_report.json")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_decision_quality_report.json")
    args = parser.parse_args()

    report = evaluate_mlb_decision_quality(
        csv_path=args.csv_path,
        context_path=args.context_path,
        redesign_report_path=args.redesign_report_path,
        report_path=args.report_path,
    )
    summary = report.get("summary", {})
    ratios = summary.get("decision_quality_ratios", {})
    scale = report.get("report_sections", {}).get("decision_quality_scale_status", {})
    clv_diag = report.get("report_sections", {}).get("sandbox_clv_diagnostics", {})
    print("=== MLB DECISION QUALITY ===")
    print(f"report_path: {args.report_path}")
    print(f"execution_mode: {report.get('execution_mode', 'PAPER_ONLY')}")
    print(f"decision_quality_scale: {scale.get('status', 'UNKNOWN')}")
    print(f"clv_status: {clv_diag.get('clv_status', 'UNKNOWN')}")
    print(f"label_counts: {summary.get('label_counts', {})}")
    print(f"good_bet_rate: {ratios.get('good_bet_rate')}")
    print(f"benchmark_source: {summary.get('benchmark_summary', {}).get('benchmark_source', 'single_snapshot')}")
    print(
        json.dumps(
            {
                "report_path": args.report_path,
                "governance_flags": report.get("governance_flags", {}),
                "label_counts": summary.get("label_counts", {}),
                "good_bet_rate": ratios.get("good_bet_rate"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
