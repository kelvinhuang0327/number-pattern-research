#!/usr/bin/env python3
"""Build a deterministic static dashboard for the P247 paper toolchain status pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_dashboard import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TOOLCHAIN_REPORT_MD,
    DEFAULT_TOOLCHAIN_STATUS_JSON,
    DEFAULT_TOOLCHAIN_STEPS_CSV,
    PaperToolchainDashboardError,
    build_paper_toolchain_dashboard,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a result-only static dashboard from committed P247 paper toolchain artifacts."
    )
    parser.add_argument("--toolchain-status-json", type=Path, default=DEFAULT_TOOLCHAIN_STATUS_JSON)
    parser.add_argument("--toolchain-steps-csv", type=Path, default=DEFAULT_TOOLCHAIN_STEPS_CSV)
    parser.add_argument("--toolchain-report-md", type=Path, default=DEFAULT_TOOLCHAIN_REPORT_MD)
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
        result = build_paper_toolchain_dashboard(
            toolchain_status_json=args.toolchain_status_json,
            toolchain_steps_csv=args.toolchain_steps_csv,
            toolchain_report_md=args.toolchain_report_md,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperToolchainDashboardError as exc:
        print(f"Paper toolchain dashboard failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        summary = result.summary
        print(
            f"Dashboard {summary['dashboard_status']}: "
            f"toolchain {summary['toolchain_status']}; "
            f"latest gate {summary['latest_gate_status']}; "
            f"{summary['artifact_roots_present']} / {summary['artifact_roots_total']} artifact roots present"
        )
    return 1 if result.summary["dashboard_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
