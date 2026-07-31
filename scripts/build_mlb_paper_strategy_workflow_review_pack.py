#!/usr/bin/env python3
"""Build the P241-A review pack for existing paper workflow artifacts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_strategy_workflow_review_pack import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_INSPECTION_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_WORKFLOW_DIR,
    ReviewPackError,
    build_paper_strategy_workflow_review_pack,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic review pack from existing P239/P240 artifacts."
    )
    parser.add_argument("--workflow-dir", type=Path, default=DEFAULT_WORKFLOW_DIR)
    parser.add_argument("--inspection-dir", type=Path, default=DEFAULT_INSPECTION_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic review-pack outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_paper_strategy_workflow_review_pack(
            workflow_dir=args.workflow_dir,
            inspection_dir=args.inspection_dir,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except ReviewPackError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Review {result.summary['review_status']}: "
            f"{result.summary['decisions_count']} decisions, "
            f"{result.summary['learning_segments_count']} learning segments"
        )
    return 0 if result.summary["review_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
