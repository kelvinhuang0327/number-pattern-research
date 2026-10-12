#!/usr/bin/env python3
"""Verify the committed P252 paper toolchain operator pack manifest."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_pack_integrity import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OPERATOR_PACK_FILES_CSV,
    DEFAULT_OPERATOR_PACK_SUMMARY_JSON,
    DEFAULT_OUTPUT_DIR,
    PaperToolchainPackIntegrityError,
    build_paper_toolchain_pack_integrity,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the committed P252 operator pack manifest without executing "
            "any workflow, status, dashboard, index, help-smoke, quickstart, or operator-pack script."
        )
    )
    parser.add_argument(
        "--operator-pack-summary-json",
        type=Path,
        default=DEFAULT_OPERATOR_PACK_SUMMARY_JSON,
    )
    parser.add_argument(
        "--operator-pack-files-csv",
        type=Path,
        default=DEFAULT_OPERATOR_PACK_FILES_CSV,
    )
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
        result = build_paper_toolchain_pack_integrity(
            operator_pack_summary_json=args.operator_pack_summary_json,
            operator_pack_files_csv=args.operator_pack_files_csv,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperToolchainPackIntegrityError as exc:
        print(f"Paper toolchain pack integrity failed: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        summary = result.summary
        print(
            f"Pack integrity {summary['integrity_status']}: "
            f"{summary['hash_match_count']}/{summary['file_count']} hashes matched; "
            f"{summary['missing_file_count']} missing; {summary['unsafe_path_count']} unsafe; "
            f"{summary['warning_count']} warnings; {summary['failure_count']} failures"
        )
    return 1 if result.summary["integrity_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

