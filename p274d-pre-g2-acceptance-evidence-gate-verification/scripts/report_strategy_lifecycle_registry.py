#!/usr/bin/env python3
"""
scripts/report_strategy_lifecycle_registry.py
=============================================
CLI report helper: outputs lifecycle metadata summary from the in-memory registry.

HARD RULES:
  - No DB connections (sqlite3 NEVER imported or called)
  - No file writes unless --output is specified
  - No replay execution
  - No adapter instances returned to caller

Usage:
  python3 scripts/report_strategy_lifecycle_registry.py           # text report
  python3 scripts/report_strategy_lifecycle_registry.py --json    # JSON output
  python3 scripts/report_strategy_lifecycle_registry.py --json --output path/out.json

Marker: P3_LIFECYCLE_REPORT_CLI_READY
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Resolve project root ────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Import registry metadata API (no DB, no adapters) ───────────────────────
from lottery_api.models.replay_strategy_registry import (
    list_strategy_lifecycle_metadata,
    summarize_strategy_lifecycle_counts,
    list_executable_strategy_ids,
    list_non_executable_strategy_ids,
)

_NO_DB_WRITE_NOTE = (
    "All data sourced from in-memory registry. "
    "No sqlite3 connection opened. No file written (unless --output specified). "
    "No replay execution performed."
)
_MARKER = "P3_LIFECYCLE_REPORT_CLI_READY"


def _build_report_data() -> dict:
    counts = summarize_strategy_lifecycle_counts()
    executable = list_executable_strategy_ids()
    non_exec_all = list_non_executable_strategy_ids()

    # Group non-executable by status
    non_exec_by_status: dict[str, list[str]] = {}
    for entry in list_strategy_lifecycle_metadata():
        sid = entry["strategy_id"]
        status = entry["lifecycle_status"]
        if sid in non_exec_all:
            non_exec_by_status.setdefault(status, [])
            non_exec_by_status[status].append(sid)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lifecycle_counts": counts,
        "total": sum(counts.values()),
        "executable_strategy_ids": executable,
        "non_executable_strategy_ids_by_status": non_exec_by_status,
        "no_db_write": True,
        "no_db_write_note": _NO_DB_WRITE_NOTE,
        "marker": _MARKER,
    }


def _print_text(data: dict) -> None:
    print("=" * 60)
    print("  Strategy Lifecycle Registry Report")
    print(f"  Generated: {data['generated_at']}")
    print("=" * 60)
    print()
    print("Lifecycle Counts:")
    for status, count in data["lifecycle_counts"].items():
        marker = " <-- executable (ONLINE)" if status == "ONLINE" else ""
        print(f"  {status:12s}: {count}{marker}")
    print(f"  {'TOTAL':12s}: {data['total']}")
    print()
    print("Executable Strategy IDs (ONLINE only):")
    for sid in data["executable_strategy_ids"]:
        print(f"  + {sid}")
    print()
    print("Non-Executable Strategy IDs (by status):")
    for status, ids in sorted(data["non_executable_strategy_ids_by_status"].items()):
        print(f"  [{status}]")
        for sid in sorted(ids):
            print(f"    - {sid}")
    print()
    print("Governance Note:")
    print(f"  {data['no_db_write_note']}")
    print()
    print(f"Marker: {data['marker']}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report strategy lifecycle registry metadata"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output as JSON instead of human-readable text"
    )
    parser.add_argument(
        "--output", metavar="PATH", default=None,
        help="Write output to this file path (default: stdout only)"
    )
    args = parser.parse_args(argv)

    data = _build_report_data()

    if args.as_json:
        output_str = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        # Capture text output
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        _print_text(data)
        sys.stdout = old_stdout
        output_str = buf.getvalue()

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output_str, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
