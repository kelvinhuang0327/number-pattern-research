#!/usr/bin/env python3
"""MLB Paper Evaluation Runner — offline, paper-only.

Connects P141 PAPER recommendation outputs to the P142 paper quality evaluator.
Reads paper rows from outputs/recommendations/PAPER/<date>/ and evaluates them
against ground-truth outcomes, producing a JSON evaluation artifact.

Supports single-date daily evaluation and all-dates batch evaluation.

Safety hard-gates (must all remain True):
  - Offline execution only: no live API calls.
  - No DB writes.
  - No production betting unlock.
  - No EV/CLV/Kelly unlock.
  - paper_only evaluation only.

Usage:
    # Single-date evaluation
    .venv/bin/python scripts/run_mlb_paper_evaluation.py --date 2026-05-11

    # Batch evaluation over all PAPER dates
    .venv/bin/python scripts/run_mlb_paper_evaluation.py --all-dates

    # Explicit paths
    .venv/bin/python scripts/run_mlb_paper_evaluation.py \\
        --paper-dir outputs/recommendations/PAPER/2026-05-11 \\
        --outcome-path data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl \\
        --output data/mlb_2026/derived/p143_eval_20260511.json

    # Batch with explicit outcome
    .venv/bin/python scripts/run_mlb_paper_evaluation.py --all-dates \\
        --outcome-path data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.mlb_paper_evaluator import (
    discover_paper_dates,
    execute_batch_evaluation,
    execute_evaluation,
)

# ── Hard-gates ────────────────────────────────────────────────────────────────
_NO_DB_WRITES: bool = True
_NO_LIVE_API_CALLS: bool = True
_NO_PROVIDER_UNLOCK: bool = True
_NO_PRODUCTION_BETTING: bool = True
_NO_EV_CLV_KELLY_UNLOCK: bool = True
_PAPER_ONLY: bool = True

# ── Default paths ─────────────────────────────────────────────────────────────
DEFAULT_PAPER_ROOT: str = "outputs/recommendations/PAPER"
DEFAULT_OUTCOME_PATH: str = (
    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
)


def _date_nodash(date_str: str) -> str:
    return date_str.replace("-", "")


def _default_single_output(date_str: str) -> str:
    return f"data/mlb_2026/derived/p143_paper_eval_{_date_nodash(date_str)}.json"


def _default_batch_output(run_ts: str) -> str:
    ts = run_ts.replace(":", "").replace("-", "").split("T")[0]
    return f"data/mlb_2026/derived/p143_paper_eval_batch_{ts}.json"


def run_single_date(
    date_str: str,
    paper_dir: str | None,
    outcome_path: str,
    output: str | None,
) -> int:
    """Evaluate a single date's PAPER recommendations. Returns exit code."""
    resolved_paper_dir = paper_dir or str(ROOT / DEFAULT_PAPER_ROOT / date_str)
    resolved_outcome = outcome_path if Path(outcome_path).is_absolute() else str(ROOT / outcome_path)
    resolved_output = output or _default_single_output(date_str)
    if not Path(resolved_output).is_absolute():
        resolved_output = str(ROOT / resolved_output)

    print(f"[PAPER-EVAL] Single-date mode | date={date_str}")
    print(f"[PAPER-EVAL] paper_dir={resolved_paper_dir}")
    print(f"[PAPER-EVAL] outcome_path={resolved_outcome}")
    print(f"[PAPER-EVAL] output={resolved_output}")

    result = execute_evaluation(
        paper_dir=resolved_paper_dir,
        outcome_path=resolved_outcome,
        summary_output_path=resolved_output,
    )

    metrics = result.get("metrics", {})
    evaluated = metrics.get("evaluated_count", 0)
    matched = metrics.get("matched_outcome_count", 0)
    hit_rate = metrics.get("hit_rate", 0.0)
    brier = metrics.get("brier_score")
    shadow_roi = metrics.get("shadow_unit_roi", 0.0)

    if evaluated == 0:
        print(
            f"[PAPER-EVAL] WARNING: No paper rows found in {resolved_paper_dir}. "
            "Evaluation produced empty metrics.",
            file=sys.stderr,
        )
    else:
        print(
            f"[PAPER-EVAL] evaluated={evaluated} matched={matched} "
            f"hit_rate={hit_rate:.4f} brier={brier} shadow_roi={shadow_roi:.4f}"
        )

    print(f"[PAPER-EVAL] artifact written to {resolved_output}")
    return 0


def run_batch(
    paper_root: str | None,
    outcome_path: str,
    output: str | None,
) -> int:
    """Evaluate all date folders under paper_root. Returns exit code."""
    resolved_root = paper_root or str(ROOT / DEFAULT_PAPER_ROOT)
    resolved_outcome = outcome_path if Path(outcome_path).is_absolute() else str(ROOT / outcome_path)
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    resolved_output = output or _default_batch_output(run_ts)
    if not Path(resolved_output).is_absolute():
        resolved_output = str(ROOT / resolved_output)

    dates = discover_paper_dates(resolved_root)
    print(f"[PAPER-EVAL] Batch mode | paper_root={resolved_root}")
    print(f"[PAPER-EVAL] dates_found={dates}")
    print(f"[PAPER-EVAL] outcome_path={resolved_outcome}")
    print(f"[PAPER-EVAL] output={resolved_output}")

    if not dates:
        print(
            f"[PAPER-EVAL] WARNING: No date folders found under {resolved_root}. "
            "Batch evaluation produced empty results.",
            file=sys.stderr,
        )

    result = execute_batch_evaluation(
        paper_root=resolved_root,
        outcome_path=resolved_outcome,
        summary_output_path=resolved_output,
    )

    total = result.get("total_rows", 0)
    dates_eval = result.get("dates_evaluated", 0)
    agg = result.get("aggregate", {})
    print(
        f"[PAPER-EVAL] dates_evaluated={dates_eval} total_rows={total} "
        f"aggregate_hit_rate={agg.get('hit_rate', 0.0):.4f} "
        f"aggregate_shadow_roi={agg.get('shadow_unit_roi', 0.0):.4f}"
    )
    print(f"[PAPER-EVAL] artifact written to {resolved_output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "MLB Paper Evaluation Runner — offline, paper-only. "
            "Connects P141 PAPER outputs to P142 evaluator."
        )
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Single-date evaluation (YYYY-MM-DD). Mutually exclusive with --all-dates.",
    )
    mode_group.add_argument(
        "--all-dates",
        action="store_true",
        help="Batch evaluation over all date folders under --paper-dir root. "
             "Mutually exclusive with --date.",
    )

    parser.add_argument(
        "--paper-dir",
        default=None,
        help=(
            "Explicit paper recommendation directory. "
            "For --date: path to a specific date folder. "
            f"For --all-dates: path to root containing date subfolders "
            f"(default: {DEFAULT_PAPER_ROOT})."
        ),
    )
    parser.add_argument(
        "--outcome-path",
        default=DEFAULT_OUTCOME_PATH,
        help=f"Path to outcome JSONL file (default: {DEFAULT_OUTCOME_PATH}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Explicit output artifact path. Defaults to a dated path under data/mlb_2026/derived/.",
    )

    args = parser.parse_args()

    # Validate: at least one mode must be specified
    if not args.date and not args.all_dates:
        print(
            "ERROR: Specify either --date YYYY-MM-DD or --all-dates.",
            file=sys.stderr,
        )
        parser.print_help(sys.stderr)
        return 2

    # Enforce hard-gates
    if not _PAPER_ONLY or not _NO_DB_WRITES or not _NO_LIVE_API_CALLS:
        print("FATAL: Safety hard-gates are not set. Aborting.", file=sys.stderr)
        return 2

    if args.all_dates:
        return run_batch(
            paper_root=args.paper_dir,
            outcome_path=args.outcome_path,
            output=args.output,
        )
    else:
        return run_single_date(
            date_str=args.date,
            paper_dir=args.paper_dir,
            outcome_path=args.outcome_path,
            output=args.output,
        )


if __name__ == "__main__":
    sys.exit(main())
