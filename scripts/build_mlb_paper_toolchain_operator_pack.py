#!/usr/bin/env python3
"""Render a local operator pack manifest from committed P248/P249/P250/P251 artifacts.

This script only reads existing committed P248 dashboard, P249 launch
index, P250 CLI help smoke, and P251 quickstart outputs. It never
executes any P237-P251 operator script.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_operator_pack import (  # noqa: E402
    DEFAULT_CLI_HELP_SUMMARY_JSON,
    DEFAULT_DASHBOARD_SUMMARY_JSON,
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_INDEX_LINKS_CSV,
    DEFAULT_INDEX_SUMMARY_JSON,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QUICKSTART_COMMANDS_CSV,
    DEFAULT_QUICKSTART_MD,
    DEFAULT_QUICKSTART_SUMMARY_JSON,
    PaperToolchainOperatorPackError,
    build_paper_toolchain_operator_pack,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render a local, result-only operator pack manifest from committed "
            "P248 dashboard, P249 launch index, P250 CLI help smoke, and P251 quickstart artifacts."
        )
    )
    parser.add_argument("--dashboard-summary-json", type=Path, default=DEFAULT_DASHBOARD_SUMMARY_JSON)
    parser.add_argument("--index-summary-json", type=Path, default=DEFAULT_INDEX_SUMMARY_JSON)
    parser.add_argument("--index-links-csv", type=Path, default=DEFAULT_INDEX_LINKS_CSV)
    parser.add_argument("--cli-help-summary-json", type=Path, default=DEFAULT_CLI_HELP_SUMMARY_JSON)
    parser.add_argument("--quickstart-summary-json", type=Path, default=DEFAULT_QUICKSTART_SUMMARY_JSON)
    parser.add_argument("--quickstart-commands-csv", type=Path, default=DEFAULT_QUICKSTART_COMMANDS_CSV)
    parser.add_argument("--quickstart-md", type=Path, default=DEFAULT_QUICKSTART_MD)
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
        result = build_paper_toolchain_operator_pack(
            dashboard_summary_json=args.dashboard_summary_json,
            index_summary_json=args.index_summary_json,
            index_links_csv=args.index_links_csv,
            cli_help_summary_json=args.cli_help_summary_json,
            quickstart_summary_json=args.quickstart_summary_json,
            quickstart_commands_csv=args.quickstart_commands_csv,
            quickstart_md=args.quickstart_md,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperToolchainOperatorPackError as exc:
        print(f"Paper toolchain operator pack failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        summary = result.summary
        print(
            f"Operator pack {summary['operator_pack_status']}: "
            f"{summary['file_count']} pack files; {summary['local_link_count']} P249 links; "
            f"{summary['command_count']} P251 commands; "
            f"{summary['warning_count']} warnings; {summary['failure_count']} failures"
        )
    return 1 if result.summary["operator_pack_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
