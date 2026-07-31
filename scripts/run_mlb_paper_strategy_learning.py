#!/usr/bin/env python3
"""Build result-only descriptive learning summaries from P237-A decisions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_strategy_learning import (  # noqa: E402
    DEFAULT_DECISIONS_CSV,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_OUTPUT_JSON,
    DEFAULT_THRESHOLDS,
    ExplorerError,
    build_output_payload,
    load_paper_decisions,
    parse_thresholds,
    write_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize result-only historical paper decisions without odds or strategy ranking."
    )
    parser.add_argument("--decisions-csv", type=Path, default=DEFAULT_DECISIONS_CSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument(
        "--thresholds",
        default=",".join(str(value) for value in DEFAULT_THRESHOLDS),
        help="comma-separated confidence thresholds",
    )
    parser.add_argument(
        "--generated-at-utc",
        help="override generated timestamp for deterministic reproduction",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        thresholds = parse_thresholds(args.thresholds)
        dataset = load_paper_decisions(args.decisions_csv)
        payload, segments = build_output_payload(
            dataset,
            thresholds=thresholds,
            generated_at_utc=args.generated_at_utc,
        )
        write_outputs(payload, segments, args.output_json, args.output_csv)
    except ExplorerError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Wrote {len(segments)} result-only descriptive segments to {args.output_csv} "
            f"and summary to {args.output_json}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
