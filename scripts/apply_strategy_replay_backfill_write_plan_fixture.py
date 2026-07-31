#!/usr/bin/env python3
"""Fixture-only apply for approved Strategy Replay backfill write plans."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_backfill_apply import apply_write_plan_to_rows, load_jsonl_rows  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a Strategy Replay write plan to fixture rows only")
    parser.add_argument("--input", required=True, help="Input fixture JSON or JSONL path.")
    parser.add_argument("--write-plan", required=True, help="Approved write plan JSON or JSONL path.")
    parser.add_argument("--output", required=True, help="Output path for the applied fixture rows.")
    return parser.parse_args()


def _load_payload(path_value: str) -> dict[str, object] | list[dict[str, object]] | None:
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, (dict, list)) else None


def _load_write_plan(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    if path.suffix.lower() == ".jsonl":
        items = load_jsonl_rows(path)
        return {"summary": {"dry_run_only": True}, "write_plan_items": items}
    payload = _load_payload(path_value)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"summary": {"dry_run_only": True}, "write_plan_items": payload}
    return {"summary": {"dry_run_only": True}, "write_plan_items": []}


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    write_plan_path = Path(args.write_plan)
    output_path = Path(args.output)

    if input_path.resolve() == output_path.resolve():
        raise SystemExit("output path must not equal input path")

    rows = load_jsonl_rows(input_path)
    write_plan = _load_write_plan(str(write_plan_path))
    result = apply_write_plan_to_rows(rows, write_plan)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".jsonl":
        _write_jsonl(output_path, list(result.get("rows") or []))
    else:
        _write_json(output_path, list(result.get("rows") or []))

    print("FIXTURE_ONLY_BACKFILL_APPLY")
    print(f"applied_count: {result['applied_count']}")
    print(f"skipped_count: {result['skipped_count']}")
    print(f"unchanged_count: {result['unchanged_count']}")
    print(f"dry_run_only: {str(bool(result['dry_run_only'])).lower()}")
    print(f"mutation_allowed: {str(bool(result['mutation_allowed'])).lower()}")
    print(f"output_path: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())