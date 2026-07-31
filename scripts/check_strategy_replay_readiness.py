#!/usr/bin/env python3
"""Read-only readiness diagnostic for the strategy replay page."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.preview_strategy_replay_backfill import (  # noqa: E402
    DEFAULT_POSTGAME_RECORDS,
    DEFAULT_PREDICTION_RECORDS,
)
from wbc_backend.reporting.strategy_replay_adapter import build_strategy_replay_rows, load_postgame_outcome_entries, load_prediction_registry_entries
from wbc_backend.reporting.strategy_replay_backfill_plan import build_strategy_replay_backfill_plan, summarize_backfill_requirements
from wbc_backend.reporting.strategy_replay_readiness import (
    build_strategy_replay_gap_closure_plan,
    build_strategy_replay_readiness_summary,
    classify_strategy_replay_readiness,
    identify_strategy_replay_blockers,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy replay readiness read-only diagnostic")
    parser.add_argument("--prediction-registry", default=None, help="Optional prediction registry JSONL path.")
    parser.add_argument("--postgame-outcomes", default=None, help="Optional postgame outcomes JSONL path.")
    return parser.parse_args()


def _load_or_sample(path_value: str | None, sample_rows: list[dict[str, object]], loader) -> list[dict[str, object]]:
    if path_value:
        return loader(path_value)
    return list(sample_rows)


def main() -> int:
    args = parse_args()
    prediction_entries = _load_or_sample(args.prediction_registry, DEFAULT_PREDICTION_RECORDS, load_prediction_registry_entries)
    outcome_entries = _load_or_sample(args.postgame_outcomes, DEFAULT_POSTGAME_RECORDS, load_postgame_outcome_entries)
    rows = build_strategy_replay_rows(prediction_entries, outcome_entries)
    backfill_plan = build_strategy_replay_backfill_plan(rows)
    backfill_summary = summarize_backfill_requirements(backfill_plan)

    summary = build_strategy_replay_readiness_summary(
        rows,
        endpoint_mounted=True,
        endpoint_stable=False,
        ui_ready=False,
        source_mode="READ_ONLY",
    )
    readiness_level = classify_strategy_replay_readiness(summary)
    blockers = identify_strategy_replay_blockers(summary)
    next_actions = build_strategy_replay_gap_closure_plan(summary)

    print("READ_ONLY_DIAGNOSTIC")
    print(f"readiness_level: {readiness_level}")
    print(f"total_rows: {summary['total_rows']}")
    print(f"missing_strategy_id: {summary['missing_strategy_id']}")
    print(f"missing_lifecycle_state_at_prediction_time: {summary['missing_lifecycle_state_at_prediction_time']}")
    print(f"missing_canonical_outcome_key: {summary['missing_canonical_outcome_key']}")
    print(f"missing_actual_result: {summary['missing_actual_result']}")
    print(f"backfill_required_count: {backfill_summary['backfill_required_count']}")
    print(f"p0_gap_count: {backfill_summary['p0_gap_count']}")
    print(f"p1_gap_count: {backfill_summary['p1_gap_count']}")
    print(f"p2_gap_count: {backfill_summary['p2_gap_count']}")
    print("blockers:")
    for blocker in blockers or ["none"]:
        print(f"- {blocker}")
    print("next_actions:")
    for action in (backfill_summary.get("next_actions") or next_actions) or ["none"]:
        print(f"- {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
