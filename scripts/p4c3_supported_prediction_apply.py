#!/usr/bin/env python3
"""
P4C3 Controlled Supported Prediction Apply Path
==============================================

Purpose
-------
Turn quick_predict dry-run JSON artifacts into controlled prediction_runs /
prediction_items rows for supported lotteries only:
  - BIG_LOTTO
  - POWER_LOTTO

Safety guarantees
-----------------
- Default mode is DRY-RUN unless --apply is explicitly passed.
- Requires --controlled-apply-id P4C3_20260516.
- Rejects DAILY_539.
- Validates source artifacts come from quick_predict dry-run output.
- Dry-run mode does not write the DB.
- Apply mode only inserts prediction_runs / prediction_items.
- No replay rows are touched.
- Idempotent guard uses controlled_apply_id + payload fingerprint stored in
  notes / review_json.

This script intentionally does NOT modify strategy logic or prediction
generation. It only converts approved preview artifacts into controlled
database rows after explicit operator approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


AUTHORIZED_APPLY_ID = "P4C3_20260516"
SUPPORTED_LOTTERIES = ("BIG_LOTTO", "POWER_LOTTO")
EXCLUDED_LOTTERIES = ("DAILY_539",)
FINAL_CLASSIFICATION_READY = "P4C3_SUPPORTED_PREDICTION_APPLY_PATH_READY"
FINAL_CLASSIFICATION_APPLIED = "P4C3_SUPPORTED_PREDICTION_APPLY_PATH_APPLIED"
FINAL_CLASSIFICATION_BLOCKED = "P4C3_SUPPORTED_PREDICTION_APPLY_PATH_BLOCKED"
SCRIPT_VERSION = "p4c3.0"

REQUIRED_SOURCE_TOP_LEVEL_KEYS = {
    "generated_at",
    "final_classification",
    "dry_run",
    "db_written",
    "prediction_items_inserted",
    "prediction_runs_inserted",
    "replay_rows_inserted",
    "predictions",
    "warnings",
}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class PlannedPredictionRun:
    lottery_type: str
    latest_known_draw: str
    latest_known_date: str | None
    strategy_name: str
    notes: str
    snapshot_source: str
    analyzed: str
    analysis_note: str
    review_json: str
    items: list[dict[str, Any]]
    source_path: str
    source_sha256: str
    apply_fingerprint: str


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_hash(path: Path) -> str:
    return _sha256_file(path)


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def open_db_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def open_db_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"source JSON not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"source JSON must be an object: {path}")
    return data


def validate_source_payload(payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    missing = REQUIRED_SOURCE_TOP_LEVEL_KEYS - set(payload)
    if missing:
        raise ValueError(f"{source_path}: missing required keys: {sorted(missing)}")

    if payload.get("dry_run") is not True:
        raise ValueError(f"{source_path}: dry_run must be true")
    if payload.get("db_written") is not False:
        raise ValueError(f"{source_path}: db_written must be false")
    if payload.get("prediction_items_inserted") is not False:
        raise ValueError(f"{source_path}: prediction_items_inserted must be false")
    if payload.get("prediction_runs_inserted") is not False:
        raise ValueError(f"{source_path}: prediction_runs_inserted must be false")
    if payload.get("replay_rows_inserted") is not False:
        raise ValueError(f"{source_path}: replay_rows_inserted must be false")

    predictions = payload.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        raise ValueError(f"{source_path}: predictions must be a non-empty list")
    if len(predictions) != 1:
        raise ValueError(f"{source_path}: expected exactly one preview summary, got {len(predictions)}")

    summary = predictions[0]
    if not isinstance(summary, dict):
        raise ValueError(f"{source_path}: preview summary must be an object")

    for key in ("lottery_type", "next_draw", "num_bets", "strategy", "bets", "last_draw", "coverage"):
        if key not in summary:
            raise ValueError(f"{source_path}: preview summary missing {key!r}")

    if not isinstance(summary.get("bets"), list) or not summary["bets"]:
        raise ValueError(f"{source_path}: preview summary bets must be a non-empty list")

    return summary


def validate_supported_scope(lotteries: list[str]) -> list[str]:
    normalized = [lot.upper() for lot in lotteries]
    unsupported = [lot for lot in normalized if lot not in SUPPORTED_LOTTERIES]
    excluded = [lot for lot in normalized if lot in EXCLUDED_LOTTERIES]
    if unsupported or excluded:
        raise ValueError(
            "unsupported scope: "
            + ", ".join(sorted(set(unsupported + excluded)))
            + f" (supported: {', '.join(SUPPORTED_LOTTERIES)})"
        )
    return normalized


def build_apply_fingerprint(controlled_apply_id: str, source_path: Path, summary: dict[str, Any]) -> str:
    canonical = {
        "controlled_apply_id": controlled_apply_id,
        "source_path": str(source_path),
        "source_lottery_type": summary["lottery_type"],
        "next_draw": summary["next_draw"],
        "num_bets": summary["num_bets"],
        "strategy": summary["strategy"],
        "bets": summary["bets"],
        "coverage": summary["coverage"],
        "last_draw": summary.get("last_draw"),
    }
    data = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(data)


def build_planned_run(
    controlled_apply_id: str,
    source_path: Path,
    source_payload: dict[str, Any],
    summary: dict[str, Any],
) -> PlannedPredictionRun:
    source_sha256 = _sha256_file(source_path)
    apply_fingerprint = build_apply_fingerprint(controlled_apply_id, source_path, summary)
    last_draw = summary.get("last_draw") or {}
    latest_known_draw = str(last_draw.get("draw") or summary["next_draw"] or "")
    latest_known_date = last_draw.get("date")
    strategy_name = str(summary.get("strategy") or "").strip()
    if not strategy_name:
        raise ValueError(f"{source_path}: strategy name is empty")

    notes = (
        f"controlled_apply_id={controlled_apply_id};"
        f"source_sha256={source_sha256};"
        f"fingerprint={apply_fingerprint}"
    )
    review_json = json.dumps(
        {
            "controlled_apply_id": controlled_apply_id,
            "source_path": str(source_path),
            "source_sha256": source_sha256,
            "apply_fingerprint": apply_fingerprint,
            "source_summary": summary,
            "source_final_classification": source_payload.get("final_classification"),
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )

    items: list[dict[str, Any]] = []
    for idx, bet in enumerate(summary["bets"], start=1):
        numbers = bet.get("numbers")
        if not isinstance(numbers, list) or not numbers:
            raise ValueError(f"{source_path}: bet {idx} numbers must be a non-empty list")
        if not all(isinstance(num, int) for num in numbers):
            raise ValueError(f"{source_path}: bet {idx} numbers must be integers")
        special = bet.get("special")
        if special is not None and not isinstance(special, int):
            raise ValueError(f"{source_path}: bet {idx} special must be int or null")

        items.append(
            {
                "bet_index": idx,
                "numbers": json.dumps(numbers, ensure_ascii=False),
                "special": special,
                "status": "PENDING",
                "strategy_name": strategy_name,
                "num_bets": int(summary["num_bets"]),
                "zone_coverage": json.dumps(summary.get("coverage"), ensure_ascii=False),
            }
        )

    return PlannedPredictionRun(
        lottery_type=str(summary["lottery_type"]),
        latest_known_draw=str(latest_known_draw),
        latest_known_date=str(latest_known_date) if latest_known_date is not None else None,
        strategy_name=strategy_name,
        notes=notes,
        snapshot_source="VALID",
        analyzed="未研究",
        analysis_note=f"controlled_apply_id={controlled_apply_id}",
        review_json=review_json,
        items=items,
        source_path=str(source_path),
        source_sha256=source_sha256,
        apply_fingerprint=apply_fingerprint,
    )


def get_existing_controlled_rows(cur: sqlite3.Cursor, controlled_apply_id: str, fingerprint: str) -> list[dict[str, Any]]:
    pattern_a = f"%controlled_apply_id={controlled_apply_id}%"
    pattern_b = f"%{fingerprint}%"
    rows = cur.execute(
        """
        SELECT id, lottery_type, latest_known_draw, latest_known_date, strategy_name, notes, review_json
        FROM prediction_runs
        WHERE notes LIKE ? OR review_json LIKE ?
        ORDER BY id
        """,
        (pattern_a, pattern_b),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_planned_run(conn: sqlite3.Connection, planned: PlannedPredictionRun) -> int:
    cur = conn.execute(
        """
        INSERT INTO prediction_runs (
            lottery_type, latest_known_draw, latest_known_date,
            strategy_name, notes, snapshot_source, analyzed,
            analysis_note, review_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            planned.lottery_type,
            planned.latest_known_draw,
            planned.latest_known_date,
            planned.strategy_name,
            planned.notes,
            planned.snapshot_source,
            planned.analyzed,
            planned.analysis_note,
            planned.review_json,
        ),
    )
    return int(cur.lastrowid)


def insert_planned_item(conn: sqlite3.Connection, run_id: int, item: dict[str, Any], strategy_name: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO prediction_items (
            run_id, bet_index, numbers, special, status,
            strategy_name, num_bets, zone_coverage
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            item["bet_index"],
            item["numbers"],
            item["special"],
            item["status"],
            strategy_name,
            item["num_bets"],
            item["zone_coverage"],
        ),
    )
    return int(cur.lastrowid)


def build_receipt(
    *,
    generated_at: str,
    controlled_apply_id: str,
    mode: str,
    final_classification: str,
    source_results: list[dict[str, Any]],
    planned_runs: list[PlannedPredictionRun],
    db_written: bool,
    db_hash_before: str,
    db_hash_after: str,
    duplicate_rows: list[dict[str, Any]],
    inserted_run_ids: list[int] | None = None,
    inserted_item_ids: list[int] | None = None,
) -> dict[str, Any]:
    supported = [run.lottery_type for run in planned_runs]
    excluded = [lot for lot in EXCLUDED_LOTTERIES if lot not in supported]
    planned_items = sum(len(run.items) for run in planned_runs)
    return {
        "schema_version": "p4c3.0",
        "script_version": SCRIPT_VERSION,
        "generated_at": generated_at,
        "controlled_apply_id": controlled_apply_id,
        "mode": mode,
        "final_classification": final_classification,
        "db_written": db_written,
        "db_hash_before": db_hash_before,
        "db_hash_after": db_hash_after,
        "db_hash_unchanged": db_hash_before == db_hash_after,
        "supported_lotteries": supported,
        "excluded_lotteries": excluded,
        "source_results": source_results,
        "planned_prediction_runs": [
            {
                "lottery_type": run.lottery_type,
                "latest_known_draw": run.latest_known_draw,
                "latest_known_date": run.latest_known_date,
                "strategy_name": run.strategy_name,
                "source_path": run.source_path,
                "source_sha256": run.source_sha256,
                "apply_fingerprint": run.apply_fingerprint,
                "planned_prediction_items": len(run.items),
                "bets": run.items,
            }
            for run in planned_runs
        ],
        "planned_prediction_runs_count": len(planned_runs),
        "planned_prediction_items_count": planned_items,
        "prediction_runs_inserted": bool(inserted_run_ids) if inserted_run_ids is not None else False,
        "prediction_items_inserted": bool(inserted_item_ids) if inserted_item_ids is not None else False,
        "replay_rows_inserted": False,
        "inserted_prediction_run_ids": inserted_run_ids or [],
        "inserted_prediction_item_ids": inserted_item_ids or [],
        "duplicate_rows": duplicate_rows,
        "warnings": [
            "DAILY_539 intentionally excluded from the supported production prediction scope",
        ],
        "safety": {
            "db_written": db_written,
            "prediction_runs_inserted": bool(inserted_run_ids) if inserted_run_ids is not None else False,
            "prediction_items_inserted": bool(inserted_item_ids) if inserted_item_ids is not None else False,
            "replay_rows_inserted": False,
            "strategy_logic_changed": False,
            "api_ui_backend_changed": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled supported prediction apply path")
    parser.add_argument("--db", required=True, help="Path to lottery_v2.db")
    parser.add_argument(
        "--sources",
        required=True,
        help="Comma-separated quick_predict dry-run JSON artifact paths",
    )
    parser.add_argument(
        "--lotteries",
        required=True,
        help="Comma-separated supported lottery types matching --sources order",
    )
    parser.add_argument(
        "--controlled-apply-id",
        required=True,
        help=f"Must be exactly '{AUTHORIZED_APPLY_ID}'",
    )
    parser.add_argument(
        "--json-out",
        required=True,
        help="Receipt JSON output path",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write prediction_runs/prediction_items",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = _ts()
    db_path = Path(args.db)
    source_paths = [Path(p) for p in parse_csv(args.sources)]
    lotteries = validate_supported_scope(parse_csv(args.lotteries))

    if args.controlled_apply_id != AUTHORIZED_APPLY_ID:
        raise SystemExit(
            f"FATAL: --controlled-apply-id must be '{AUTHORIZED_APPLY_ID}', got {args.controlled_apply_id!r}"
        )

    if len(source_paths) != len(lotteries):
        raise SystemExit(
            f"FATAL: source count ({len(source_paths)}) must match lottery count ({len(lotteries)})"
        )

    db_hash_before = _db_hash(db_path)
    conn_ro = open_db_ro(db_path)
    try:
        cur = conn_ro.cursor()
        source_results: list[dict[str, Any]] = []
        planned_runs: list[PlannedPredictionRun] = []
        duplicate_rows: list[dict[str, Any]] = []

        for lottery_type, source_path in zip(lotteries, source_paths):
            payload = read_json(source_path)
            summary = validate_source_payload(payload, source_path)
            actual_lottery_type = str(summary["lottery_type"]).upper()

            if actual_lottery_type != lottery_type:
                raise SystemExit(
                    f"FATAL: {source_path} lottery_type={actual_lottery_type!r} "
                    f"does not match requested lottery {lottery_type!r}"
                )

            planned_run = build_planned_run(args.controlled_apply_id, source_path, payload, summary)
            planned_runs.append(planned_run)

            existing = get_existing_controlled_rows(cur, args.controlled_apply_id, planned_run.apply_fingerprint)
            if existing:
                duplicate_rows.extend(existing)

            source_results.append(
                {
                    "source_path": str(source_path),
                    "lottery_type": lottery_type,
                    "source_final_classification": payload.get("final_classification"),
                    "summary_prediction_count": len(payload.get("predictions") or []),
                    "source_sha256": planned_run.source_sha256,
                    "apply_fingerprint": planned_run.apply_fingerprint,
                    "validated": True,
                }
            )

        if duplicate_rows and args.apply:
            receipt = build_receipt(
                generated_at=generated_at,
                controlled_apply_id=args.controlled_apply_id,
                mode="apply",
                final_classification=FINAL_CLASSIFICATION_BLOCKED,
                source_results=source_results,
                planned_runs=planned_runs,
                db_written=False,
                db_hash_before=db_hash_before,
                db_hash_after=db_hash_before,
                duplicate_rows=duplicate_rows,
            )
            os.makedirs(Path(args.json_out).parent, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            raise SystemExit("FATAL: duplicate controlled_apply_id / fingerprint already exists in prediction_runs")

        if not args.apply:
            db_hash_after = _db_hash(db_path)
            receipt = build_receipt(
                generated_at=generated_at,
                controlled_apply_id=args.controlled_apply_id,
                mode="dry-run",
                final_classification=FINAL_CLASSIFICATION_READY,
                source_results=source_results,
                planned_runs=planned_runs,
                db_written=False,
                db_hash_before=db_hash_before,
                db_hash_after=db_hash_after,
                duplicate_rows=duplicate_rows,
            )
            os.makedirs(Path(args.json_out).parent, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0

        # Apply mode: controlled write of prediction_runs + prediction_items only.
        inserted_run_ids: list[int] = []
        inserted_item_ids: list[int] = []
        conn_rw = open_db_rw(db_path)
        try:
            conn_rw.execute("BEGIN IMMEDIATE")
            for planned_run in planned_runs:
                run_id = insert_planned_run(conn_rw, planned_run)
                inserted_run_ids.append(run_id)
                for item in planned_run.items:
                    item_id = insert_planned_item(conn_rw, run_id, item, planned_run.strategy_name)
                    inserted_item_ids.append(item_id)
            conn_rw.commit()
        except Exception:
            conn_rw.rollback()
            raise
        finally:
            conn_rw.close()

        db_hash_after = _db_hash(db_path)
        receipt = build_receipt(
            generated_at=generated_at,
            controlled_apply_id=args.controlled_apply_id,
            mode="apply",
            final_classification=FINAL_CLASSIFICATION_APPLIED,
            source_results=source_results,
            planned_runs=planned_runs,
            db_written=True,
            db_hash_before=db_hash_before,
            db_hash_after=db_hash_after,
            duplicate_rows=duplicate_rows,
            inserted_run_ids=inserted_run_ids,
            inserted_item_ids=inserted_item_ids,
        )
        os.makedirs(Path(args.json_out).parent, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn_ro.close()


if __name__ == "__main__":
    raise SystemExit(main())
