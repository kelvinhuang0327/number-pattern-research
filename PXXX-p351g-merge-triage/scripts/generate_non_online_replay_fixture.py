#!/usr/bin/env python3
"""
Generate deterministic fixture-only replay artifacts for non-ONLINE strategies.

Hard rules:
- No sqlite3 imports
- No DB access
- No adapter execution (no get_adapter / get_one_bet)
- Output-only JSON artifact under outputs/replay/

Marker: P21_NON_ONLINE_FIXTURE_ARTIFACT_READY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/replay/non_online_replay_fixture_20260511.json"
FIXTURE_VERSION = "p21_20260511"
FIXTURE_NAME = "non_online_lifecycle_replay_fixture"
FIXTURE_SOURCE = "non_online_lifecycle_fixture"
GOVERNANCE_MARKER = "P21_NON_ONLINE_FIXTURE_ROW"
ALLOWED_STATUSES = {"REJECTED", "RETIRED", "OBSERVATION"}

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lottery_api.models.replay_strategy_registry import (  # noqa: E402
    list_non_executable_strategy_ids,
    list_strategy_lifecycle_metadata,
)


def _normalize_lottery_type(value: str | None) -> str:
    return value if value else "UNKNOWN"


def _record_identity(strategy_id: str, lifecycle_status: str) -> str:
    token = f"{strategy_id}|{lifecycle_status}|{FIXTURE_VERSION}".encode("utf-8")
    return hashlib.sha256(token).hexdigest()[:12]


def _build_record(strategy_id: str, lottery_type: str, lifecycle_status: str) -> dict:
    token = _record_identity(strategy_id, lifecycle_status)
    pick_a = int(token[0:2], 16) % 39 + 1
    pick_b = int(token[2:4], 16) % 39 + 1
    pick_c = int(token[4:6], 16) % 39 + 1
    actual_a = int(token[6:8], 16) % 39 + 1
    actual_b = int(token[8:10], 16) % 39 + 1
    actual_c = int(token[10:12], 16) % 39 + 1

    prediction_numbers = sorted({pick_a, pick_b, pick_c})
    actual_numbers = sorted({actual_a, actual_b, actual_c})
    overlap = sorted(set(prediction_numbers) & set(actual_numbers))

    return {
        "strategy_id": strategy_id,
        "lottery_type": lottery_type,
        "lifecycle_status": lifecycle_status,
        "fixture_row_id": f"fixture-{strategy_id}-{token}",
        "draw_id": f"fixture-draw-{token[:8]}",
        "draw_date": "2026-05-11",
        "prediction_payload": {
            "numbers": prediction_numbers,
            "note": "Synthetic fixture prediction only. Not a production replay row.",
        },
        "actual_result_payload": {
            "numbers": actual_numbers,
            "note": "Synthetic fixture result only. Not sourced from production DB.",
        },
        "comparison_result": {
            "hit_count": len(overlap),
            "matched_numbers": overlap,
            "edge_claim": False,
        },
        "synthetic_only": True,
        "fixture_only": True,
        "fixture_source": FIXTURE_SOURCE,
        "governance_marker": GOVERNANCE_MARKER,
    }


def build_fixture() -> dict:
    metadata = list_strategy_lifecycle_metadata()
    non_executable = set(list_non_executable_strategy_ids())

    filtered = []
    for item in metadata:
        strategy_id = item.get("strategy_id")
        lifecycle_status = item.get("lifecycle_status")
        if strategy_id in non_executable and lifecycle_status in ALLOWED_STATUSES:
            filtered.append(
                {
                    "strategy_id": strategy_id,
                    "lottery_type": _normalize_lottery_type(item.get("lottery_type")),
                    "lifecycle_status": lifecycle_status,
                }
            )

    filtered.sort(
        key=lambda x: (x["lifecycle_status"], x["lottery_type"], x["strategy_id"])
    )

    records = [
        _build_record(x["strategy_id"], x["lottery_type"], x["lifecycle_status"])
        for x in filtered
    ]

    return {
        "fixture_name": FIXTURE_NAME,
        "fixture_version": FIXTURE_VERSION,
        "synthetic_only": True,
        "fixture_only": True,
        "source": FIXTURE_SOURCE,
        "production_db_write": False,
        "backfill": False,
        "promotion_action": False,
        "generated_at": "2026-05-11T00:00:00Z",
        "strategy_count": len(filtered),
        "records": records,
        "markers": [
            "P21_NON_ONLINE_FIXTURE_ARTIFACT_READY",
            "P21_NO_DB_WRITE_NO_BACKFILL_CONFIRMED",
            "P21_NO_PROMOTION_ACTION_CONFIRMED",
        ],
    }


def _assert_output_path(path: Path) -> None:
    resolved = path.resolve()
    parts = list(resolved.parts)
    has_outputs_replay = any(
        i + 1 < len(parts) and parts[i] == "outputs" and parts[i + 1] == "replay"
        for i in range(len(parts) - 1)
    )
    if not has_outputs_replay:
        raise ValueError(
            f"Output must include an outputs/replay segment, got: {resolved}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate non-ONLINE lifecycle replay fixture artifact (JSON)."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path (must be under outputs/replay).",
    )
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    _assert_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fixture = build_fixture()
    output_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")

    print(str(output_path))
    print("P21_NON_ONLINE_FIXTURE_ARTIFACT_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
