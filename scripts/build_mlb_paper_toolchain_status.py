#!/usr/bin/env python3
"""Build a deterministic status pack for P237-P246 paper-only artifacts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_toolchain_status import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    build_paper_toolchain_status,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export result-only status for committed P237-P246 paper tooling."
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
    result = build_paper_toolchain_status(
        output_dir=args.output_dir,
        generated_at_utc=args.generated_at_utc,
    )
    status = result.status["toolchain_status"]
    if not args.quiet:
        print(
            f"Toolchain {status}: "
            f"{result.status['present_artifact_root_count']} / "
            f"{result.status['artifact_root_count']} artifact roots present; "
            f"latest gate {result.status['latest_gate_status']}"
        )
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
