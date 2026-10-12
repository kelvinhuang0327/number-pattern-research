#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.research.mlb_paper_monitor import run_mlb_paper_tracking_monitor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLB strict-only paper tracking monitor (weekly/monthly governance report).")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--decision-quality-report-path", default="data/wbc_backend/reports/mlb_decision_quality_report.json")
    parser.add_argument("--regime-paper-report-path", default="data/wbc_backend/reports/mlb_regime_paper_report.json")
    parser.add_argument("--redesign-report-path", default="data/wbc_backend/reports/mlb_regime_feature_redesign_report.json")
    parser.add_argument("--output-path", default="data/wbc_backend/reports/mlb_paper_tracking_report.json")
    args = parser.parse_args()

    summary = run_mlb_paper_tracking_monitor(
        csv_path=args.csv_path,
        context_path=args.context_path,
        decision_quality_report_path=args.decision_quality_report_path,
        regime_paper_report_path=args.regime_paper_report_path,
        redesign_report_path=args.redesign_report_path,
        output_path=args.output_path,
    )
    payload = json.loads(Path(summary.report_path).read_text(encoding="utf-8"))
    visibility = payload.get("governance_visibility", {})
    overall = payload.get("overall_strict_metrics", {})
    spring = payload.get("spring_training_tracking", {})
    print("=== MLB PAPER TRACKING ===")
    print(f"report_path: {summary.report_path}")
    print(f"status: {summary.status}")
    print(f"execution_mode: {visibility.get('execution_mode', 'PAPER_ONLY')}")
    print(f"decision_quality_scale: {visibility.get('decision_quality_scale', 'UNKNOWN')}")
    print(f"strict_sample_count: {overall.get('sample_count', 0)}")
    print(f"strict_roi: {overall.get('strict_only_roi', 'n/a')}")
    if spring:
        print(f"spring_training_tracking: sample_count={spring.get('sample_count', 0)} roi={spring.get('roi', 'unavailable')}")
    print(
        json.dumps(
            {
                "status": summary.status,
                "report_path": summary.report_path,
                "regimes_monitored": summary.regimes_monitored,
                "governance_visibility": visibility,
                "overall_strict_metrics": overall,
                "frozen_recommendation": payload.get("frozen_recommendation"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
