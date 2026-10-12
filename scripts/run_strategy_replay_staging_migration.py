#!/usr/bin/env python3
"""Staging-only / fixture-only Strategy Replay migration runner skeleton."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_backfill_apply import load_jsonl_rows  # noqa: E402
from wbc_backend.reporting.strategy_replay_staging_migration_runner import run_staging_migration_simulation  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Strategy Replay staging-only migration simulation")
    parser.add_argument("--input", required=True, help="Input fixture JSON or JSONL path.")
    parser.add_argument("--write-plan", required=True, help="Approved write plan JSON or JSONL path.")
    parser.add_argument("--migration-gate-summary", required=True, help="Migration gate summary JSON path.")
    parser.add_argument("--output", required=True, help="Output path for the staging simulation result.")
    parser.add_argument("--target-mode", required=True, help="Target mode: STAGING or FIXTURE.")
    return parser.parse_args()


def _load_payload(path_value: str) -> dict[str, object] | list[dict[str, object]] | None:
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, (dict, list)) else None


def _load_dict(path_value: str) -> dict[str, object] | None:
    payload = _load_payload(path_value)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    write_plan_path = Path(args.write_plan)
    migration_gate_path = Path(args.migration_gate_summary)
    output_path = Path(args.output)
    target_mode = args.target_mode.strip().upper()

    if target_mode == "PRODUCTION":
        raise SystemExit("PRODUCTION target mode is refused")

    if target_mode not in {"STAGING", "FIXTURE"}:
        raise SystemExit("target_mode must be STAGING or FIXTURE")

    if input_path.resolve() == output_path.resolve():
        raise SystemExit("output path must not equal input path")

    input_rows = load_jsonl_rows(input_path)
    write_plan = _load_dict(str(write_plan_path)) or {"summary": {"dry_run_only": False}, "write_plan_items": []}
    migration_gate_summary = _load_dict(str(migration_gate_path)) or {}

    print("STAGING_ONLY_MIGRATION_RUNNER")
    result = run_staging_migration_simulation(
        input_rows,
        write_plan,
        migration_gate_summary,
        target_mode=target_mode,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, result)

    print(f"target_mode: {target_mode}")
    print(f"staging_only: {str(bool(result['staging_only'])).lower()}")
    print(f"production_write_allowed: {str(bool(result['production_write_allowed'])).lower()}")
    print(f"applied_count: {result['applied_count']}")
    print(f"skipped_count: {result['skipped_count']}")
    print(f"unchanged_count: {result['unchanged_count']}")
    print("blocked_reasons:")
    for reason in result.get("blocked_reasons") or ["none"]:
        print(f"- {reason}")
    print(f"rollback_plan_ref: {result['rollback_plan_ref']}")
    print(f"output_path: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
