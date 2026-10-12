#!/usr/bin/env python3
"""Run the P242-A isolated paper strategy workflow bundle."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_strategy_learning import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    parse_thresholds,
)
from wbc_backend.recommendation.paper_strategy_workflow import DEFAULT_SOURCE_CSV  # noqa: E402
from wbc_backend.recommendation.paper_strategy_workflow_bundle import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    PaperWorkflowBundleError,
    run_bundle_or_raise,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run P239/P240/P241 into one deterministic local P242 bundle."
    )
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument(
        "--thresholds",
        default=",".join(str(value) for value in DEFAULT_THRESHOLDS),
        help="comma-separated confidence thresholds",
    )
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic bundle outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        thresholds = parse_thresholds(args.thresholds)
        result = run_bundle_or_raise(
            source_csv=args.source_csv,
            output_dir=args.output_dir,
            min_confidence=args.min_confidence,
            thresholds=thresholds,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperWorkflowBundleError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Bundle {result.summary['bundle_status']}: "
            f"{result.summary['decisions_count']} decisions, "
            f"{result.summary['learning_segments_count']} learning segments"
        )
    return 0 if result.summary["bundle_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
