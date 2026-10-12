#!/usr/bin/env python3
"""Run `--help` smoke checks against committed P239-P249 paper toolchain scripts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_cli_help import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    PaperToolchainCliHelpError,
    build_paper_toolchain_cli_help,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run only `--help` against configured P239-P249 paper toolchain scripts."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="python interpreter used to invoke each configured script's --help",
    )
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic outputs",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="per-script --help timeout in seconds",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_paper_toolchain_cli_help(
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
            python_executable=args.python,
            timeout_seconds=args.timeout_seconds,
        )
    except PaperToolchainCliHelpError as exc:
        print(f"Paper toolchain CLI help smoke failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        summary = result.summary
        print(
            f"CLI help smoke {summary['smoke_status']}: "
            f"{summary['help_pass_count']} / {summary['script_count']} help calls passed; "
            f"{summary['timeout_count']} timeouts; {summary['missing_script_count']} missing scripts; "
            f"{summary['warning_count']} warnings; {summary['failure_count']} failures"
        )
    return 1 if result.summary["smoke_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
