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
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
HISTORICAL_FIXTURE_PATH = (
    PROJECT_ROOT / "outputs/replay/non_online_replay_fixture_20260511.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/replay/non_online_replay_fixture_current.json"
FIXTURE_VERSION = "p21_20260511"
FIXTURE_NAME = "non_online_lifecycle_replay_fixture"
FIXTURE_SOURCE = "non_online_lifecycle_fixture"
GOVERNANCE_MARKER = "P21_NON_ONLINE_FIXTURE_ROW"
ALLOWED_STATUSES = {"REJECTED", "RETIRED", "OBSERVATION"}
KNOWN_LIFECYCLE_STATUSES = {
    "ONLINE",
    "OFFLINE",
    "REJECTED",
    "RETIRED",
    "OBSERVATION",
}
KNOWN_LOTTERY_TYPES = {"BIG_LOTTO", "POWER_LOTTO", "DAILY_539"}

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


def _validated_registry_rows(metadata: list, non_executable_ids: list) -> list[dict]:
    if not isinstance(metadata, list):
        raise ValueError("Strategy lifecycle metadata must be a list.")
    if not isinstance(non_executable_ids, list):
        raise ValueError("Non-executable strategy IDs must be a list.")

    if any(
        not isinstance(strategy_id, str) or not strategy_id.strip()
        for strategy_id in non_executable_ids
    ):
        raise ValueError("Non-executable strategy IDs must be non-empty strings.")
    if len(non_executable_ids) != len(set(non_executable_ids)):
        raise ValueError("Duplicate non-executable strategy ID in registry.")
    non_executable = set(non_executable_ids)

    metadata_by_id: dict[str, dict] = {}
    for item in metadata:
        if not isinstance(item, dict):
            raise ValueError("Each lifecycle metadata entry must be a mapping.")

        strategy_id = item.get("strategy_id")
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise ValueError("Lifecycle metadata requires a non-empty strategy_id.")
        if strategy_id in metadata_by_id:
            raise ValueError(f"Duplicate strategy ID in lifecycle metadata: {strategy_id}")

        lifecycle_status = item.get("lifecycle_status")
        if (
            not isinstance(lifecycle_status, str)
            or lifecycle_status not in KNOWN_LIFECYCLE_STATUSES
        ):
            raise ValueError(
                f"Invalid lifecycle status for {strategy_id}: {lifecycle_status!r}"
            )

        supported_types = item.get("supported_lottery_types")
        if (
            not isinstance(supported_types, list)
            or not supported_types
            or any(
                not isinstance(lottery_type, str)
                or lottery_type not in KNOWN_LOTTERY_TYPES
                for lottery_type in supported_types
            )
            or len(supported_types) != len(set(supported_types))
        ):
            raise ValueError(
                f"Invalid supported_lottery_types metadata for {strategy_id}."
            )

        metadata_by_id[strategy_id] = item

    expected_non_executable = {
        strategy_id
        for strategy_id, item in metadata_by_id.items()
        if item["lifecycle_status"] != "ONLINE"
    }
    if non_executable != expected_non_executable:
        raise ValueError(
            "Non-executable strategy IDs do not match lifecycle metadata."
        )

    filtered = []
    for strategy_id, item in metadata_by_id.items():
        lifecycle_status = item["lifecycle_status"]
        if (
            strategy_id not in non_executable
            or lifecycle_status not in ALLOWED_STATUSES
        ):
            continue

        declared_lottery_type = item.get("lottery_type")
        if declared_lottery_type is not None and (
            not isinstance(declared_lottery_type, str)
            or declared_lottery_type not in KNOWN_LOTTERY_TYPES
        ):
            raise ValueError(f"Invalid lottery_type metadata for {strategy_id}.")
        lottery_type = _normalize_lottery_type(declared_lottery_type)
        if lottery_type == "UNKNOWN":
            lottery_type = sorted(item["supported_lottery_types"])[0]

        filtered.append(
            {
                "strategy_id": strategy_id,
                "lottery_type": lottery_type,
                "lifecycle_status": lifecycle_status,
            }
        )

    filtered.sort(
        key=lambda row: (
            row["lifecycle_status"],
            row["lottery_type"],
            row["strategy_id"],
        )
    )
    return filtered


def build_fixture() -> dict:
    metadata = list_strategy_lifecycle_metadata()
    non_executable_ids = list_non_executable_strategy_ids()
    filtered = _validated_registry_rows(metadata, non_executable_ids)

    records = [
        _build_record(
            row["strategy_id"], row["lottery_type"], row["lifecycle_status"]
        )
        for row in filtered
    ]
    strategy_ids = [record.get("strategy_id") for record in records]
    if len(strategy_ids) != len(set(strategy_ids)):
        raise ValueError("Duplicate strategy ID in generated fixture records.")
    fixture_row_ids = [record.get("fixture_row_id") for record in records]
    if any(not isinstance(row_id, str) or not row_id for row_id in fixture_row_ids):
        raise ValueError("Every generated record must have a fixture_row_id.")
    if len(fixture_row_ids) != len(set(fixture_row_ids)):
        raise ValueError("Duplicate fixture_row_id in generated fixture records.")

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
    candidate = path.expanduser()
    try:
        resolved = candidate.resolve()
        frozen_resolved = HISTORICAL_FIXTURE_PATH.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve output path safely: {candidate}") from exc

    normalized = Path(os.path.abspath(candidate))
    frozen_normalized = Path(os.path.abspath(HISTORICAL_FIXTURE_PATH))
    aliases_frozen_path = (
        normalized == frozen_normalized or resolved == frozen_resolved
    )
    if (
        not aliases_frozen_path
        and candidate.exists()
        and HISTORICAL_FIXTURE_PATH.exists()
    ):
        try:
            aliases_frozen_path = os.path.samefile(candidate, HISTORICAL_FIXTURE_PATH)
        except OSError:
            aliases_frozen_path = False
    if aliases_frozen_path:
        raise ValueError(
            "The historical 20260511 fixture is frozen and cannot be an output target."
        )

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
    _assert_output_path(output_path)
    output_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")

    print(str(output_path))
    print("P21_NON_ONLINE_FIXTURE_ARTIFACT_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
