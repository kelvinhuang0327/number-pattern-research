#!/usr/bin/env python3
"""Dry-run approved write plan for Strategy Replay backfill candidates."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_backfill_review import load_backfill_candidates  # noqa: E402
from wbc_backend.reporting.strategy_replay_backfill_write_plan import build_approved_backfill_write_plan  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an approved Strategy Replay backfill write plan")
    parser.add_argument("--candidates", required=True, help="Backfill candidates JSON or JSONL path.")
    parser.add_argument("--approval-manifest", required=True, help="Approval manifest JSON path.")
    parser.add_argument("--output", required=True, help="Output path for the write plan.")
    parser.add_argument("--format", choices=("json", "jsonl"), default="jsonl", help="Output format.")
    return parser.parse_args()


def _load_manifest(path_value: str) -> dict[str, object] | None:
    manifest_path = Path(path_value)
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    candidates = load_backfill_candidates(args.candidates)
    manifest = _load_manifest(args.approval_manifest)
    plan = build_approved_backfill_write_plan(candidates, manifest)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "jsonl":
        _write_jsonl(output_path, list(plan.get("write_plan_items") or []))
    else:
        _write_json(output_path, list(plan.get("write_plan_items") or []))

    summary = plan.get("summary") or {}
    print("DRY_RUN_BACKFILL_WRITE_PLAN")
    print(f"total_candidates: {summary.get('total_candidates', 0)}")
    print(f"write_ready_count: {summary.get('write_ready_count', 0)}")
    print(f"rejected_count: {summary.get('rejected_count', 0)}")
    print(f"migration_allowed: {str(bool(summary.get('migration_allowed', False))).lower()}")
    print(f"dry_run_only: {str(bool(summary.get('dry_run_only', True))).lower()}")
    print(f"output_path: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())