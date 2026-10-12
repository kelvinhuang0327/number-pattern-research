#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.mlb_data.feed_jobs import run_all_feed_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MLB context feed jobs")
    parser.add_argument("--refresh-external", action="store_true", help="Fetch external MLB context sources before generating feeds")
    args = parser.parse_args()
    summary = run_all_feed_jobs(refresh_external=args.refresh_external)
    report_path = Path("data/wbc_backend/reports/mlb_feed_qa_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "total_failures": summary["total_failures"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
