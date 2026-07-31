#!/usr/bin/env python3
"""Read-only migration gate checklist for Strategy Replay."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.reporting.strategy_replay_migration_gate import build_migration_verification_checklist  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Strategy Replay migration gate checklist")
    parser.add_argument("--fixture-apply-summary", default=None, help="Optional fixture apply summary JSON path.")
    parser.add_argument("--write-plan-summary", default=None, help="Optional write plan summary JSON path.")
    parser.add_argument("--approval-manifest-summary", default=None, help="Optional approval manifest summary JSON path.")
    parser.add_argument("--readiness-summary", default=None, help="Optional readiness summary JSON path.")
    parser.add_argument("--human-approved", action="store_true", help="Mark the gate as explicitly human approved.")
    parser.add_argument("--output", default=None, help="Optional output path for the checklist JSON.")
    return parser.parse_args()


def _load_json(path_value: str | None) -> dict[str, object] | list[object] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, (dict, list)) else None


def _load_dict(path_value: str | None) -> dict[str, object] | None:
    payload = _load_json(path_value)
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"items": payload}
    return None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    fixture_apply_summary = _load_dict(args.fixture_apply_summary)
    write_plan_summary = _load_dict(args.write_plan_summary)
    approval_manifest_summary = _load_dict(args.approval_manifest_summary)
    readiness_summary = _load_dict(args.readiness_summary)

    checklist = build_migration_verification_checklist(
        fixture_apply_summary,
        write_plan_summary,
        approval_manifest_summary,
        readiness_summary,
        human_approved=args.human_approved,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output_path, checklist)

    print("READ_ONLY_MIGRATION_GATE_CHECKLIST")
    print(f"migration_allowed: {str(bool(checklist['migration_allowed'])).lower()}")
    print(f"rollback_required: {str(bool(checklist['rollback_required'])).lower()}")
    print(f"ui_can_start: {str(bool(checklist['ui_can_start'])).lower()}")
    print(f"readiness_level: {checklist['readiness_level']}")
    print("no_go_reasons:")
    for reason in checklist["no_go_reasons"] or ["none"]:
        print(f"- {reason}")
    print("required_human_approvals:")
    for approval in checklist["required_human_approvals"] or ["none"]:
        print(f"- {approval}")
    if args.output:
        print(f"output_path: {Path(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
