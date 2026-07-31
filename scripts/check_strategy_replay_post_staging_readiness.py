#!/usr/bin/env python3
"""Read-only post-staging readiness recheck for Strategy Replay."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_backfill_apply import load_jsonl_rows  # noqa: E402
from wbc_backend.reporting.strategy_replay_post_staging_readiness import build_post_staging_readiness_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Strategy Replay post-staging readiness")
    parser.add_argument("--staging-output", required=True, help="Staging output JSON or JSONL path.")
    parser.add_argument("--staging-result", default=None, help="Optional staging result JSON path.")
    parser.add_argument("--output", default=None, help="Optional output path for the recheck summary.")
    return parser.parse_args()


def _load_payload(path_value: str | None) -> dict[str, object] | list[object] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, (dict, list)) else None


def _load_staging_result(staging_output_path: str, staging_result_path: str | None) -> dict[str, object] | None:
    if staging_result_path:
        payload = _load_payload(staging_result_path)
        return payload if isinstance(payload, dict) else None

    payload = _load_payload(staging_output_path)
    if isinstance(payload, dict):
        return payload
    return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    staging_output_path = Path(args.staging_output)
    output_path = Path(args.output) if args.output else None

    rows = load_jsonl_rows(staging_output_path)
    staging_result = _load_staging_result(args.staging_output, args.staging_result)
    summary = build_post_staging_readiness_summary(rows, staging_result)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output_path, summary)

    print("POST_STAGING_READINESS_RECHECK")
    print(f"readiness_level: {summary['readiness_level']}")
    print(f"ui_can_start: {str(bool(summary['ui_can_start'])).lower()}")
    print(f"ui_mode: {summary['ui_mode']}")
    print("blockers:")
    for blocker in summary["blockers"] or ["none"]:
        print(f"- {blocker}")
    print("required_next_actions:")
    for action in summary["required_next_actions"] or ["none"]:
        print(f"- {action}")
    if output_path:
        print(f"output_path: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
