#!/usr/bin/env python3
"""
Phase 13 — Optimization Readiness CLI

Generates the autonomous optimization readiness dashboard and writes output
to canonical artifact paths.

Usage:
  python3 scripts/run_optimization_readiness.py --print
  python3 scripts/run_optimization_readiness.py --json
  python3 scripts/run_optimization_readiness.py --print --json

Artifacts written:
  data/wbc_backend/reports/optimization_readiness_latest.json
  docs/orchestration/optimization_readiness_latest.md

Read-only — does not trigger pipelines or consume API credits.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Artifact paths ────────────────────────────────────────────────────────
REPORTS_DIR   = ROOT / "data" / "wbc_backend" / "reports"
DOCS_ORCH_DIR = ROOT / "docs" / "orchestration"
JSON_OUT      = REPORTS_DIR / "optimization_readiness_latest.json"
MD_OUT        = DOCS_ORCH_DIR / "optimization_readiness_latest.md"


def _write_artifacts(summary: dict, md: str) -> None:
    """Write JSON + Markdown artifacts (create dirs if missing)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_ORCH_DIR.mkdir(parents=True, exist_ok=True)

    JSON_OUT.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    MD_OUT.write_text(md, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autonomous optimization readiness dashboard (read-only).",
    )
    parser.add_argument("--print", dest="do_print", action="store_true",
                        help="Print human-readable dashboard to stdout.")
    parser.add_argument("--json", dest="do_json", action="store_true",
                        help="Print machine-readable JSON to stdout.")
    args = parser.parse_args(argv)

    # Default: if neither flag, print human-readable
    if not args.do_print and not args.do_json:
        args.do_print = True

    from orchestrator.optimization_readiness import (
        get_readiness_summary,
        render_readiness_markdown,
    )

    summary = get_readiness_summary()
    md      = render_readiness_markdown(summary)

    # Always write artifacts
    _write_artifacts(summary, md)

    if args.do_print:
        print(md)

    if args.do_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))

    # Emit a concise log line for CI / cron
    rs  = summary.get("readiness_state", "UNKNOWN")
    sev = summary.get("severity", "?")
    print(
        f"[Readiness] {rs} [{sev}] — {summary.get('reason', '')}",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
