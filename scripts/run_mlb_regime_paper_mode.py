#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.models.mlb_regime_paper import run_mlb_regime_paper_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLB regime-first guarded paper mode validation.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_regime_paper_report.json")
    args = parser.parse_args()

    report = run_mlb_regime_paper_mode(
        csv_path=args.csv_path,
        context_path=args.context_path,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "report_path": args.report_path,
                "governance_flags": report.get("governance_flags", {}),
                "tradable_regimes": report.get("tradable_regimes", []),
                "paper_overall": report.get("paper_mode_reporting", {}).get("overall", {}),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
