#!/usr/bin/env python3
"""Read-only review workflow for Strategy Replay backfill candidates."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_backfill_review import build_safe_migration_proposal, load_backfill_candidates  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Strategy Replay backfill candidates")
    parser.add_argument("--candidates", required=True, help="Backfill candidates JSON or JSONL path.")
    parser.add_argument("--approval-manifest", default=None, help="Optional approval manifest JSON path.")
    return parser.parse_args()


def _load_manifest(path_value: str | None) -> dict[str, object] | None:
    if not path_value:
        return None
    manifest_path = Path(path_value)
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def main() -> int:
    args = parse_args()
    candidates = load_backfill_candidates(args.candidates)
    manifest = _load_manifest(args.approval_manifest)
    proposal = build_safe_migration_proposal(candidates, manifest)
    summary = proposal["summary"]

    print("READ_ONLY_BACKFILL_REVIEW")
    print(f"total_candidates: {summary['total_candidates']}")
    print(f"review_required_count: {summary['review_required_count']}")
    print(f"auto_approvable_count: {summary['auto_approvable_count']}")
    print(f"write_ready_count: {summary['write_ready_count']}")
    print(f"rejected_count: {summary['rejected_count']}")
    print("unsafe_to_infer_fields:")
    for field_name, count in (summary.get("unsafe_to_infer_field_counts") or {}).items():
        print(f"- {field_name}: {count}")
    print(f"migration_allowed: {str(bool(proposal['migration_allowed'])).lower()}")
    if proposal["manifest_errors"]:
        print("manifest_errors:")
        for error in proposal["manifest_errors"]:
            print(f"- {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())