#!/usr/bin/env python3
"""Build a result-only paper decision ledger from local historical rows."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_strategy_simulator import (  # noqa: E402
    DEFAULT_LEDGER,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_OUTPUT_JSON,
    ExplorerError,
    build_output_payload,
    load_paper_strategy_dataset,
    write_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate result-only historical paper decisions without odds or P/L."
    )
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--date-from", help="inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        dataset = load_paper_strategy_dataset(args.source_csv)
        payload, decisions = build_output_payload(
            dataset,
            min_confidence=args.min_confidence,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        write_outputs(payload, decisions, args.output_json, args.output_csv)
    except ExplorerError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Wrote {len(decisions)} result-only decisions to {args.output_csv} "
            f"and summary to {args.output_json}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
