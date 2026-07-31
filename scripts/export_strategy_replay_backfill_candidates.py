#!/usr/bin/env python3
"""Read-only historical backfill candidate export for strategy replay."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_adapter import load_postgame_outcome_entries, load_prediction_registry_entries  # noqa: E402
from wbc_backend.reporting.strategy_replay_instrumentation import build_backfill_candidate_export_rows  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export strategy replay historical backfill candidates")
    parser.add_argument("--prediction-registry", required=True, help="Prediction registry JSONL path.")
    parser.add_argument("--postgame-outcomes", required=True, help="Postgame outcomes JSONL path.")
    parser.add_argument("--output", required=True, help="Output path for the exported candidates.")
    parser.add_argument("--format", choices=("jsonl", "json"), default="jsonl", help="Export format.")
    return parser.parse_args()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    prediction_registry_path = Path(args.prediction_registry)
    postgame_outcomes_path = Path(args.postgame_outcomes)
    output_path = Path(args.output)

    prediction_entries = load_prediction_registry_entries(prediction_registry_path)
    outcome_entries = load_postgame_outcome_entries(postgame_outcomes_path)
    rows = build_backfill_candidate_export_rows(prediction_entries, outcome_entries)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "jsonl":
        _write_jsonl(output_path, rows)
    else:
        _write_json(output_path, rows)

    print("READ_ONLY_BACKFILL_EXPORT")
    print(f"prediction_registry_rows: {len(prediction_entries)}")
    print(f"postgame_outcome_rows: {len(outcome_entries)}")
    print(f"exported_candidates: {len(rows)}")
    print(f"format: {args.format}")
    print(f"output_path: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())