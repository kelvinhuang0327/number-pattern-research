#!/usr/bin/env python3
"""Inspect P239-A result-only paper workflow artifacts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_strategy_workflow_inspector import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_WORKFLOW_DIR,
    PaperWorkflowInspectorError,
    inspect_paper_strategy_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect existing result-only paper workflow outputs without regenerating them."
    )
    parser.add_argument("--workflow-dir", type=Path, default=DEFAULT_WORKFLOW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic inspector outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = inspect_paper_strategy_workflow(
            workflow_dir=args.workflow_dir,
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperWorkflowInspectorError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Inspection {result.summary['overall_status']}: "
            f"{result.summary['decisions_count']} decisions, "
            f"{result.summary['learning_segments_count']} learning segments"
        )
    return 0 if result.summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
