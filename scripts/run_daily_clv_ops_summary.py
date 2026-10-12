"""
scripts/run_daily_clv_ops_summary.py
Phase 35 — CLI runner for Daily CLV Ops Summary

Usage:
    python3 scripts/run_daily_clv_ops_summary.py --print
    python3 scripts/run_daily_clv_ops_summary.py --json
    python3 scripts/run_daily_clv_ops_summary.py --date 2026-04-30
    python3 scripts/run_daily_clv_ops_summary.py --print --date 2026-04-30

Outputs:
    docs/orchestration/daily_clv_ops_summary_YYYY-MM-DD.md
    data/wbc_backend/reports/daily_clv_ops_summary_YYYY-MM-DD.json

HARD RULES:
  - Read-only. Does NOT modify CLV files.
  - Does NOT call external LLM.
  - Does NOT trigger live betting.
  - Does NOT create patch tasks.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_DOCS_DIR    = _ROOT / "docs" / "orchestration"
_REPORTS_DIR = _ROOT / "data" / "wbc_backend" / "reports"


def _write_outputs(summary: dict, target_date: str) -> tuple[Path, Path]:
    """Write JSON + Markdown artifacts. Returns (md_path, json_path)."""
    from orchestrator.daily_clv_ops_summary import render_daily_ops_markdown

    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = _REPORTS_DIR / f"daily_clv_ops_summary_{target_date}.json"
    md_path   = _DOCS_DIR    / f"daily_clv_ops_summary_{target_date}.md"

    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_text = render_daily_ops_markdown(summary)
    md_path.write_text(md_text, encoding="utf-8")

    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Daily CLV Ops Summary — Phase 35 (read-only)."
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Target date for the summary (default: today UTC).",
    )
    parser.add_argument(
        "--print",
        dest="print_card",
        action="store_true",
        help="Print the Markdown summary to stdout.",
    )
    parser.add_argument(
        "--json",
        dest="print_json",
        action="store_true",
        help="Print the raw JSON summary to stdout.",
    )
    args = parser.parse_args(argv)

    target_date = args.date or date.today().isoformat()

    from orchestrator.daily_clv_ops_summary import (
        get_daily_ops_summary,
        render_daily_ops_markdown,
    )

    print(f"[Phase 35] Generating daily CLV ops summary for {target_date} …", flush=True)
    summary = get_daily_ops_summary(target_date=target_date)

    md_path, json_path = _write_outputs(summary, target_date)
    print(f"[Phase 35] JSON  → {json_path}", flush=True)
    print(f"[Phase 35] MD    → {md_path}", flush=True)

    highest = summary.get("highest_severity", "INFO")
    alert_counts: dict[str, int] = {}
    for a in summary.get("alerts", []):
        s = a["severity"]
        alert_counts[s] = alert_counts.get(s, 0) + 1

    print(
        f"[Phase 35] Status: {highest} | "
        f"CRITICAL={alert_counts.get('CRITICAL', 0)} "
        f"WARN={alert_counts.get('WARN', 0)} "
        f"INFO={alert_counts.get('INFO', 0)}",
        flush=True,
    )
    print(f"[Phase 35] Action: {summary.get('operator_next_action', '—')}", flush=True)

    if args.print_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.print_card:
        print(render_daily_ops_markdown(summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())
