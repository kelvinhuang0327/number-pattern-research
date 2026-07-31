#!/usr/bin/env python3
"""
Phase 9 — Autonomous Optimization Ops Report CLI

Usage:
  python3 scripts/run_optimization_ops_report.py --window 8h
  python3 scripts/run_optimization_ops_report.py --window 24h
  python3 scripts/run_optimization_ops_report.py --window 8h --json-only
  python3 scripts/run_optimization_ops_report.py --window 8h --print

Outputs:
  docs/orchestration/optimization_ops_report_YYYY-MM-DD_HHMM.md
  data/wbc_backend/reports/optimization_ops_report_YYYY-MM-DD_HHMM.json

HARD RULES: Read-only. Does not modify tasks, memory, or CLV state.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_REPORTS_MD  = _ROOT / "docs" / "orchestration"
_REPORTS_JSON = _ROOT / "data" / "wbc_backend" / "reports"


def _timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")


def run(window: str, print_card: bool = False, json_only: bool = False) -> dict:
    from orchestrator.optimization_ops_report import generate_report, render_markdown

    report = generate_report(window=window)
    ts = _timestamp_suffix()

    # ── Write JSON ──────────────────────────────────────────────────────
    json_path = _REPORTS_JSON / f"optimization_ops_report_{ts}.json"
    _REPORTS_JSON.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OpsReport] JSON → {json_path}", file=sys.stderr)

    if not json_only:
        # ── Write Markdown ──────────────────────────────────────────────
        md = render_markdown(report)
        md_path = _REPORTS_MD / f"optimization_ops_report_{ts}.md"
        _REPORTS_MD.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md, encoding="utf-8")
        print(f"[OpsReport] MD  → {md_path}", file=sys.stderr)

        if print_card:
            print(md)

    print(
        f"[OpsReport] window={window}  classification={report['classification']}  "
        f"completed={report['tasks_completed']}  clv_computed={report['clv_computed']}",
        file=sys.stderr,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Phase 9 autonomous optimization ops report."
    )
    parser.add_argument(
        "--window",
        default="8h",
        choices=["8h", "24h"],
        help="Time window to summarise (default: 8h)",
    )
    parser.add_argument(
        "--print",
        dest="print_card",
        action="store_true",
        help="Print Markdown report to stdout",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Write JSON only, skip Markdown generation",
    )
    args = parser.parse_args()

    report = run(window=args.window, print_card=args.print_card, json_only=args.json_only)
    # Exit code reflects classification severity
    exit_map = {
        "EFFECTIVE": 0,
        "PARTIAL":   0,
        "IDLE":      0,
        "DEGRADED":  1,
        "BLOCKED":   2,
    }
    return exit_map.get(report["classification"], 0)


if __name__ == "__main__":
    sys.exit(main())
