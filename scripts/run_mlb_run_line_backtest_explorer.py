#!/usr/bin/env python3
"""Filter and summarize existing local 2025 run-line backtest rows."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.run_line_backtest_explorer import (  # noqa: E402
    ExplorerError,
    build_output_payload,
    filter_rows,
    load_explorer_dataset,
    write_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explore existing 2025 historical paper-only Run Line backtest rows."
    )
    parser.add_argument("--date-from", help="inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--team", help="case-insensitive home/away team substring")
    parser.add_argument("--min-confidence", type=float, help="minimum selected-side probability")
    parser.add_argument("--top-n", type=int, default=25, help="highest-confidence rows (default: 25)")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "report" / "p236a_run_line_backtest_explorer_summary.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ROOT / "report" / "p236a_run_line_backtest_explorer_filtered_games.csv",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        dataset = load_explorer_dataset()
        rows = filter_rows(
            dataset.rows,
            date_from=args.date_from,
            date_to=args.date_to,
            team=args.team,
            min_confidence=args.min_confidence,
            top_n=args.top_n,
        )
        filters = {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "team": args.team,
            "min_confidence": args.min_confidence,
            "top_n": args.top_n,
        }
        payload = build_output_payload(dataset, rows, filters)
        write_outputs(payload, args.output_json, args.output_csv)
    except ExplorerError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Wrote {len(rows)} historical rows to {args.output_csv} and summary to {args.output_json}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
