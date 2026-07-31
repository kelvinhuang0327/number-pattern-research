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

from wbc_backend.research.mlb_model_rebuild import run_mlb_model_rebuild


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict-only MLB moneyline model rebuild lab.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--context-path", default="data/mlb_context")
    parser.add_argument("--report-path", default="data/wbc_backend/reports/mlb_model_rebuild_report.json")
    args = parser.parse_args()

    report = run_mlb_model_rebuild(
        csv_path=args.csv_path,
        context_path=args.context_path,
        report_path=args.report_path,
    )
    print(
        json.dumps(
            {
                "report_path": args.report_path,
                "final_diagnosis": report.get("final_diagnosis"),
                "best_model": report.get("best_model"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
