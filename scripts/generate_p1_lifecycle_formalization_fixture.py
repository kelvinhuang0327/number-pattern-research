#!/usr/bin/env python3
"""
Generate the minimal product-acceptance fixture for P1 lifecycle formalization.

Hard rules:
- No sqlite3 imports
- No DB access
- No strategy execution
- No replay row generation

The generated JSON is used by replay history fixture_mode to prove the endpoint
can represent the formal replay lifecycle contract:
PRODUCTION / WATCHING / PROVISIONAL / REJECTED / OFFLINE / EXPERIMENTAL / UNKNOWN
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/replay/p1_lifecycle_formalization_fixture_20260517.json"
FIXTURE_NAME = "p1_lifecycle_formalization_fixture"
FIXTURE_VERSION = "p1_20260517"
FIXTURE_SOURCE = "p1_lifecycle_formalization_fixture"
GOVERNANCE_MARKER = "P1_LIFECYCLE_FORMALIZATION_FIXTURE_ROW"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lottery_api.models.replay_lifecycle_contract import FORMAL_LIFECYCLE_STATES


_FIXTURE_ROWS = [
    {
        "strategy_id": "biglotto_triple_strike",
        "strategy_name": "大樂透 Triple Strike",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "PRODUCTION",
        "draw_date": "2026-05-15",
        "prediction_numbers": [1, 2, 3, 4, 5, 6],
        "actual_numbers": [2, 3, 4, 5, 6, 7],
    },
    {
        "strategy_id": "daily539_f4cold_watch",
        "strategy_name": "今彩539 F4 Cold Watch",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "WATCHING",
        "draw_date": "2026-05-15",
        "prediction_numbers": [3, 7, 11, 19, 27, 33],
        "actual_numbers": [1, 3, 9, 19, 21, 33],
    },
    {
        "strategy_id": "power_orthogonal_5bet_provisional",
        "strategy_name": "威力彩 Orthogonal 5注 Provisional",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "PROVISIONAL",
        "draw_date": "2026-05-15",
        "prediction_numbers": [2, 5, 11, 17, 23, 29],
        "actual_numbers": [2, 4, 11, 18, 23, 30],
    },
    {
        "strategy_id": "biglotto_ts3_acb_4bet",
        "strategy_name": "大樂透 TS3+ACB 4注",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "REJECTED",
        "draw_date": "2026-05-15",
        "prediction_numbers": [4, 8, 12, 16, 20, 24],
        "actual_numbers": [1, 4, 8, 12, 20, 31],
    },
    {
        "strategy_id": "offline_shadow_539",
        "strategy_name": "今彩539 Offline Shadow",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "OFFLINE",
        "draw_date": "2026-05-15",
        "prediction_numbers": [5, 10, 15, 20, 25, 30],
        "actual_numbers": [1, 6, 11, 16, 21, 30],
    },
    {
        "strategy_id": "experimental_biglotto_freq_grid",
        "strategy_name": "大樂透 Frequency Grid",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "EXPERIMENTAL",
        "draw_date": "2026-05-15",
        "prediction_numbers": [7, 13, 19, 25, 31, 37],
        "actual_numbers": [7, 12, 19, 26, 31, 38],
    },
    {
        "strategy_id": "unknown_inventory_probe",
        "strategy_name": "Unknown Inventory Probe",
        "lottery_type": "BIG_LOTTO",
        "lifecycle_status": "UNKNOWN",
        "draw_date": "2026-05-15",
        "prediction_numbers": [6, 9, 18, 27, 33, 42],
        "actual_numbers": [1, 8, 17, 26, 35, 44],
    },
]


def _record_identity(strategy_id: str, lifecycle_status: str) -> str:
    token = f"{strategy_id}|{lifecycle_status}|{FIXTURE_VERSION}".encode("utf-8")
    return sha256(token).hexdigest()[:12]


def _build_record(row: dict) -> dict:
    token = _record_identity(row["strategy_id"], row["lifecycle_status"])
    predicted = sorted({int(n) for n in row["prediction_numbers"]})
    actual = sorted({int(n) for n in row["actual_numbers"]})
    overlap = sorted(set(predicted) & set(actual))
    return {
        "strategy_id": row["strategy_id"],
        "strategy_name": row["strategy_name"],
        "lottery_type": row["lottery_type"],
        "lifecycle_status": row["lifecycle_status"],
        "fixture_row_id": f"fixture-{row['strategy_id']}-{token}",
        "draw_id": f"fixture-draw-{token[:8]}",
        "draw_date": row["draw_date"],
        "prediction_payload": {
            "numbers": predicted,
            "note": "Synthetic P1 lifecycle formalization fixture row.",
        },
        "actual_result_payload": {
            "numbers": actual,
            "note": "Synthetic P1 lifecycle formalization fixture row.",
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
    records = [_build_record(row) for row in _FIXTURE_ROWS]
    lifecycle_counts = {state: 0 for state in FORMAL_LIFECYCLE_STATES}
    for row in _FIXTURE_ROWS:
        lifecycle_counts[row["lifecycle_status"]] += 1

    return {
        "fixture_name": FIXTURE_NAME,
        "fixture_version": FIXTURE_VERSION,
        "generated_at": "2026-05-17T00:00:00+08:00",
        "synthetic_only": True,
        "fixture_only": True,
        "production_db_write": False,
        "backfill": False,
        "promotion_action": False,
        "strategy_count": len(records),
        "lifecycle_counts": lifecycle_counts,
        "records": records,
        "markers": [
            "P1_LIFECYCLE_FORMALIZATION_FIXTURE_READY",
            "P1_NO_DB_WRITE_CONFIRMED",
            "P1_NO_REPLAY_ROW_GENERATION_CONFIRMED",
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
        raise ValueError(f"Output must include an outputs/replay segment, got: {resolved}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate replay lifecycle formalization fixture artifact (JSON)."
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
    output_path.write_text(json.dumps(build_fixture(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(output_path))
    print("P1_LIFECYCLE_FORMALIZATION_FIXTURE_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
