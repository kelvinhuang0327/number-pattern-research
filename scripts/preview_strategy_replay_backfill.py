#!/usr/bin/env python3
"""Dry-run preview for strategy replay backfill instrumentation.

Reads sample records or explicit fixture/sample files, prints counts, and never writes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_adapter import (  # noqa: E402
    build_strategy_replay_rows,
    load_postgame_outcome_entries,
    load_prediction_registry_entries,
    summarize_strategy_replay_rows,
)


DEFAULT_PREDICTION_RECORDS: list[dict[str, object]] = [
    {
        "strategy_id": "strat_001",
        "strategy_name": "Conservative Moneyline",
        "lifecycle_state_at_prediction_time": "online",
        "current_lifecycle_state": "online",
        "prediction_timestamp": "2026-05-10T08:00:00Z",
        "game_id": "G20260510_001",
        "market_type": "moneyline",
        "recommendation": "HOME",
        "confidence": 0.61,
        "edge": 0.03,
        "actual_result": "win",
        "source_refs": {"prediction": "fixture:prediction:1", "outcome": "fixture:outcome:1"},
    },
    {
        "strategy_id": "",
        "strategy_name": "Missing Strategy",
        "lifecycle_state_at_prediction_time": "offline",
        "current_lifecycle_state": "offline",
        "prediction_timestamp": "2026-05-10T09:00:00Z",
        "game_id": "G20260510_002",
        "market_type": "total",
        "recommendation": "OVER",
        "actual_result": "loss",
        "source_refs": {"prediction": "fixture:prediction:2", "outcome": "fixture:outcome:2"},
    },
    {
        "strategy_id": "strat_003",
        "strategy_name": "Missing Lifecycle",
        "lifecycle_state_at_prediction_time": "",
        "current_lifecycle_state": "rejected",
        "prediction_timestamp": "2026-05-10T10:00:00Z",
        "game_id": "G20260510_003",
        "market_type": "run_line",
        "recommendation": "AWAY",
        "actual_result": None,
        "source_refs": {"prediction": "fixture:prediction:3", "outcome": "fixture:outcome:3"},
    },
    {
        "strategy_id": "strat_004",
        "strategy_name": "Fallback Join",
        "lifecycle_state_at_prediction_time": "observation",
        "current_lifecycle_state": "observation",
        "prediction_timestamp": "2026-05-10T11:00:00Z",
        "game_id": "G20260510_004",
        "canonical_outcome_key": "tmp",
        "market_type": "moneyline",
        "recommendation": "HOME",
        "actual_result": "push",
        "source_refs": {"prediction": "fixture:prediction:4", "outcome": "fixture:outcome:4"},
    },
]

DEFAULT_POSTGAME_RECORDS: list[dict[str, object]] = [
    {"game_id": "G20260510_001", "canonical_outcome_key": "G20260510_001", "actual_result": "win"},
    {"game_id": "G20260510_002", "canonical_outcome_key": "G20260510_002", "actual_result": "loss"},
    {"game_id": "G20260510_003", "canonical_outcome_key": "G20260510_003", "actual_result": None},
    {"game_id": "G20260510_004", "canonical_outcome_key": "G20260510_004", "actual_result": "push"},
]


def _load_jsonl_or_sample(path_value: str | None, sample_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if path_value:
        return load_prediction_registry_entries(path_value)
    return list(sample_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy replay backfill dry-run preview")
    parser.add_argument(
        "--prediction-registry",
        default=None,
        help="Optional prediction registry JSONL path.",
    )
    parser.add_argument(
        "--postgame-outcomes",
        default=None,
        help="Optional postgame outcomes JSONL path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prediction_entries = _load_jsonl_or_sample(args.prediction_registry, DEFAULT_PREDICTION_RECORDS)
    outcome_entries = (
        load_postgame_outcome_entries(args.postgame_outcomes)
        if args.postgame_outcomes
        else list(DEFAULT_POSTGAME_RECORDS)
    )

    rows = build_strategy_replay_rows(prediction_entries, outcome_entries)
    summary = summarize_strategy_replay_rows(rows)

    print("DRY_RUN_ONLY")
    print("Strategy Replay Backfill Preview")
    print(f"total candidate rows: {summary['total_candidate_rows']}")
    print(f"rows missing strategy_id: {summary['rows_missing_strategy_id']}")
    print(
        "rows missing lifecycle_state_at_prediction_time: "
        f"{summary['rows_missing_lifecycle_state_at_prediction_time']}"
    )
    print(f"rows missing canonical_outcome_key: {summary['rows_missing_canonical_outcome_key']}")
    print(f"rows missing actual_result: {summary['rows_missing_actual_result']}")
    print(f"rows MVP-ready: {summary['rows_mvp_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
