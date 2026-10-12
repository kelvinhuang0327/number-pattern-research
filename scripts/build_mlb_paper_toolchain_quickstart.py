#!/usr/bin/env python3
"""Render a local operator quickstart pack from committed P249/P250 artifacts.

This script only reads existing committed P249 launch index and P250 CLI
help smoke outputs. It never executes any P237-P250 operator script, not
even with `--help`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_quickstart import (  # noqa: E402
    DEFAULT_CLI_HELP_ENTRIES_CSV,
    DEFAULT_CLI_HELP_SUMMARY_JSON,
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_INDEX_LINKS_CSV,
    DEFAULT_INDEX_SUMMARY_JSON,
    DEFAULT_OUTPUT_DIR,
    PaperToolchainQuickstartError,
    build_paper_toolchain_quickstart,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render a local, result-only operator quickstart pack from committed "
            "P249 launch index and P250 CLI help smoke artifacts."
        )
    )
    parser.add_argument("--index-summary-json", type=Path, default=DEFAULT_INDEX_SUMMARY_JSON)
    parser.add_argument("--index-links-csv", type=Path, default=DEFAULT_INDEX_LINKS_CSV)
    parser.add_argument("--cli-help-summary-json", type=Path, default=DEFAULT_CLI_HELP_SUMMARY_JSON)
    parser.add_argument("--cli-help-entries-csv", type=Path, default=DEFAULT_CLI_HELP_ENTRIES_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_paper_toolchain_quickstart(
            index_summary_json=args.index_summary_json,
            index_links_csv=args.index_links_csv,
            cli_help_summary_json=args.cli_help_summary_json,
            cli_help_entries_csv=args.cli_help_entries_csv,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperToolchainQuickstartError as exc:
        print(f"Paper toolchain quickstart failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        summary = result.summary
        print(
            f"Quickstart {summary['quickstart_status']}: "
            f"{summary['local_link_count']} viewing links; {summary['help_command_count']} help commands; "
            f"{summary['warning_count']} warnings; {summary['failure_count']} failures"
        )
    return 1 if result.summary["quickstart_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
