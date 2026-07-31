from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.mlb_alpha_lab import MLBAlphaLab


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLB alpha discovery research cycle.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_alpha_discovery_report.json")
    args = parser.parse_args()

    lab = MLBAlphaLab(csv_path=args.csv_path, context_path=args.context_path)
    report = lab.run_full_research_cycle(report_path=args.report_path)
    scope = report.get("research_scope", {})
    tiers = report.get("data_tier_summary", {})
    print("=== MLB ALPHA DISCOVERY ===")
    print(f"report_path: {args.report_path}")
    print(f"final_verdict: {report['final_verdict']}")
    print(f"research_scope: {scope.get('framing', 'unknown')}")
    print(f"clv_available: {scope.get('clv_available', False)}")
    print(f"clv_pipeline_status: {tiers.get('clv_pipeline_status', 'unknown')}")
    print(json.dumps({"report_path": args.report_path, "final_verdict": report["final_verdict"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
