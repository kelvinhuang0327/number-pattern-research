#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.research.mlb_regime_feature_redesign import run_regime_feature_redesign


def main() -> None:
    parser = argparse.ArgumentParser(description="Run focused MLB regime feature redesign for small_edge and weak_starter_mismatch.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_regime_feature_redesign_report.json")
    args = parser.parse_args()

    report = run_regime_feature_redesign(
        csv_path=args.csv_path,
        context_path=args.context_path,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "report_path": args.report_path,
                "tradable_regimes_after_redesign": report.get("tradable_regimes_after_redesign", []),
                "final_recommendation": report.get("final_recommendation"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
