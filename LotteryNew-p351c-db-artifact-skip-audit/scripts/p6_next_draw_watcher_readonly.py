#!/usr/bin/env python3
"""Read-only watcher for supported next-draw readiness.

Checks the next required draws for supported production predictions:
- BIG_LOTTO 115000053
- POWER_LOTTO 115000036

This script is intentionally read-only:
- no DB writes
- no draw imports
- no replay backfill
- no prediction item/run updates
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

SUPPORTED_TARGETS = {
    "BIG_LOTTO": "115000053",
    "POWER_LOTTO": "115000036",
}
SUPPORTED_RUNS = {
    "BIG_LOTTO": {"run_id": 176, "item_ids": [1096, 1097, 1098]},
    "POWER_LOTTO": {"run_id": 177, "item_ids": [1099, 1100, 1101]},
}

READY_CLASSIFICATION = "P6_NEXT_DRAW_WATCHER_DRAWS_AVAILABLE_IMPORT_READY"
WAITING_CLASSIFICATION = "P6_NEXT_DRAW_WATCHER_WAITING_FOR_OFFICIAL_DRAWS"
BLOCKED_CLASSIFICATION = "P6_NEXT_DRAW_WATCHER_BLOCKED_VALIDATION_FAIL"


def _ts() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_targets(value: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in [p.strip() for p in value.split(",") if p.strip()]:
        if ":" not in part:
            raise ValueError(f"invalid target format: {part!r}; expected LOTTERY:DRAW")
        lottery, draw = [x.strip().upper() for x in part.split(":", 1)]
        if lottery not in SUPPORTED_TARGETS:
            raise ValueError(f"unsupported lottery: {lottery}")
        out[lottery] = draw
    return out


def open_ro(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to lottery_v2.db")
    parser.add_argument(
        "--targets",
        required=True,
        help="Comma-separated targets like BIG_LOTTO:115000053,POWER_LOTTO:115000036",
    )
    parser.add_argument("--json-out", required=True, help="Output JSON path")
    args = parser.parse_args()

    db_path = Path(args.db)
    targets = parse_targets(args.targets)
    result = {
        "generated_at": _ts(),
        "final_classification": None,
        "db_path": str(db_path),
        "db_sha256": sha256_file(db_path),
        "targets": [],
        "source_preview": None,
        "safety": {
            "db_written": False,
            "draw_imported": False,
            "replay_rows_inserted": False,
            "prediction_items_modified": False,
            "prediction_runs_modified": False,
            "strategy_logic_changed": False,
            "api_ui_backend_changed": False,
        },
        "warnings": [],
    }

    conn = open_ro(str(db_path))
    try:
        cur = conn.cursor()
        failures = []
        for lottery_type, target_draw in targets.items():
            support = SUPPORTED_RUNS[lottery_type]
            run = cur.execute(
                "SELECT id, lottery_type, latest_known_draw, latest_known_date, strategy_name, notes, snapshot_source, analyzed FROM prediction_runs WHERE id=?",
                (support["run_id"],),
            ).fetchone()
            if run is None:
                failures.append(f"missing prediction_run {support['run_id']} for {lottery_type}")
                continue

            pending = cur.execute(
                f"SELECT id, run_id, bet_index, numbers, special, status, strategy_name, num_bets, zone_coverage FROM prediction_items WHERE id IN ({','.join('?' for _ in support['item_ids'])}) ORDER BY id",
                support["item_ids"],
            ).fetchall()
            if len(pending) != len(support["item_ids"]):
                failures.append(f"missing prediction_items for {lottery_type}")
                continue

            latest_draw_row = cur.execute(
                "SELECT draw, date, lottery_type, numbers, special FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1",
                (lottery_type,),
            ).fetchone()
            latest_draw = latest_draw_row["draw"] if latest_draw_row else None
            latest_draw_exists = cur.execute(
                "SELECT 1 FROM draws WHERE lottery_type=? AND CAST(draw AS INTEGER)=CAST(? AS INTEGER) LIMIT 1",
                (lottery_type, target_draw),
            ).fetchone() is not None

            readiness = "READY_FOR_OFFICIAL_DRAW_PROCESSING" if latest_draw_exists else "WAITING_FOR_OFFICIAL_DRAW_PUBLICATION"
            result["targets"].append({
                "lottery_type": lottery_type,
                "support_run_id": support["run_id"],
                "target_draw": target_draw,
                "latest_draw_in_db": latest_draw,
                "target_draw_exists": latest_draw_exists,
                "latest_known_draw_in_prediction_run": run["latest_known_draw"],
                "latest_known_date_in_prediction_run": run["latest_known_date"],
                "strategy_name": run["strategy_name"],
                "prediction_item_ids": support["item_ids"],
                "pending_item_count": len([r for r in pending if r["status"] == "PENDING"]),
                "readiness_state": readiness,
                "prediction_run_status": run["analyzed"],
            })

        if failures:
            result["final_classification"] = BLOCKED_CLASSIFICATION
            result["warnings"].extend(failures)
        else:
            exists = [t["target_draw_exists"] for t in result["targets"]]
            if all(exists):
                result["final_classification"] = READY_CLASSIFICATION
            else:
                result["final_classification"] = WAITING_CLASSIFICATION
    finally:
        conn.close()

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
