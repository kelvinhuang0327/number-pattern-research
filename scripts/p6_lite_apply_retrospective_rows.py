#!/usr/bin/env python3
"""Controlled apply for P3.1 retrospective rows.

Modes:
  --dry-run
  --apply
  --rollback CONTROLLED_APPLY_ID

The script reads the normalized P3.1 JSONL artifact and inserts rows into
strategy_prediction_replays with idempotent skip behavior based on:
  (strategy_id, target_draw, truth_level='REGENERATED_RETROSPECTIVE')
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


INPUT_FILE = Path("outputs/replay/p3_1_retrospective_candidate_rows_normalized_20260514.jsonl")
LOG_DIR = Path("outputs/replay")
DB_PATH = Path("lottery_api/data/lottery_v2.db")
TARGET_TABLE = "strategy_prediction_replays"
TRUTH_LEVEL = "REGENERATED_RETROSPECTIVE"
SOURCE_VALUE = "p6_lite_controlled_apply"
PROVENANCE_SOURCE_VALUE = "p3_1_retrospective_normalized_20260514"


@dataclass
class RunResult:
    mode: str
    controlled_apply_id: str | None
    target_table: str
    input_rows: int
    invalid_rows: int
    would_insert: int = 0
    would_skip_existing: int = 0
    inserted: int = 0
    skipped_existing: int = 0
    per_strategy: dict[str, int] | None = None
    db_hash_before: str | None = None
    db_hash_after: str | None = None
    db_hash_unchanged: bool | None = None
    log_file: str | None = None
    deleted_rows: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", metavar="CONTROLLED_APPLY_ID")
    return parser.parse_args()


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing input file: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_no}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"row {line_no} is not a JSON object")
            rows.append(row)
    return rows


def ensure_list_of_ints(value: Any, field_name: str, line_no: int) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"row {line_no} field {field_name} must be a non-empty list")
    out: list[int] = []
    for item in value:
        if not isinstance(item, int):
            raise ValueError(f"row {line_no} field {field_name} must contain ints only")
        out.append(int(item))
    return out


def ensure_int_or_none(value: Any, field_name: str, line_no: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"row {line_no} field {field_name} must be int or null")
    return int(value)


def parse_draw_date(value: str, field_name: str, line_no: int) -> datetime:
    try:
        return datetime.strptime(value, "%Y/%m/%d")
    except Exception as exc:
        raise ValueError(f"row {line_no} field {field_name} must be YYYY/MM/DD") from exc


def validate_and_prepare_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    prepared: list[dict[str, Any]] = []
    invalid_rows = 0
    for line_no, row in enumerate(rows, start=1):
        strategy_id = str(row.get("strategy_id", "")).strip()
        lottery_type = str(row.get("lottery_type", "")).strip()
        draw_id = str(row.get("draw_id", "")).strip()
        draw_date = str(row.get("draw_date", "")).strip()
        provenance_hash = str(row.get("provenance_hash", "")).strip()
        adapter_file_hash = str(row.get("adapter_file_hash", "")).strip()

        if not strategy_id or not lottery_type or not draw_id or not draw_date:
            invalid_rows += 1
            raise ValueError(f"row {line_no} missing required identity fields")
        if not adapter_file_hash:
            invalid_rows += 1
            raise ValueError(f"row {line_no} missing adapter_file_hash")
        if not provenance_hash:
            invalid_rows += 1
            raise ValueError(f"row {line_no} missing provenance_hash")
        if row.get("truth_level") != TRUTH_LEVEL:
            invalid_rows += 1
            raise ValueError(f"row {line_no} has unexpected truth_level={row.get('truth_level')!r}")
        if row.get("dry_run_only") is not True:
            invalid_rows += 1
            raise ValueError(f"row {line_no} has dry_run_only != true")

        history_window_end = str(row.get("history_window_end", "")).strip()
        if not history_window_end:
            invalid_rows += 1
            raise ValueError(f"row {line_no} missing history_window_end")
        if parse_draw_date(history_window_end, "history_window_end", line_no) >= parse_draw_date(draw_date, "draw_date", line_no):
            invalid_rows += 1
            raise ValueError(f"row {line_no} violates history_window_end < draw_date")

        predicted_numbers = ensure_list_of_ints(row.get("predicted_numbers"), "predicted_numbers", line_no)
        actual_numbers = ensure_list_of_ints(row.get("actual_numbers"), "actual_numbers", line_no)
        predicted_special = ensure_int_or_none(row.get("predicted_special"), "predicted_special", line_no)
        actual_special = ensure_int_or_none(row.get("actual_special"), "actual_special", line_no)
        hit_count = row.get("hit_count")
        if not isinstance(hit_count, int):
            invalid_rows += 1
            raise ValueError(f"row {line_no} missing integer hit_count")
        special_hit = ensure_int_or_none(row.get("special_hit"), "special_hit", line_no)

        prepared.append({
            "source_row": row,
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "target_draw": draw_id,
            "target_date": draw_date,
            "history_cutoff_draw": history_window_end,
            "strategy_name": str(row.get("strategy_name") or strategy_id),
            "strategy_version": row.get("strategy_version"),
            "replay_status": "PREDICTED",
            "reject_reason": None,
            "predicted_numbers": json.dumps(predicted_numbers, ensure_ascii=False),
            "predicted_special": predicted_special,
            "actual_numbers": json.dumps(actual_numbers, ensure_ascii=False),
            "actual_special": actual_special,
            "hit_numbers": json.dumps(sorted(set(predicted_numbers).intersection(actual_numbers)), ensure_ascii=False),
            "hit_count": int(hit_count),
            "special_hit": 0 if special_hit is None else int(special_hit),
            "replay_run_id": None,
            "generated_at": row.get("generated_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "truth_level": TRUTH_LEVEL,
            "source": SOURCE_VALUE,
            "provenance_hash": provenance_hash,
            "provenance_source": PROVENANCE_SOURCE_VALUE,
            "controlled_apply_id": None,
            "dry_run_only": 0,
        })
    return prepared, invalid_rows


def get_table_columns(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({TARGET_TABLE})")
    return [row[1] for row in cur.fetchall()]


def has_column(columns: Iterable[str], name: str) -> bool:
    return name in set(columns)


def existing_match_count(conn: sqlite3.Connection, strategy_id: str, target_draw: str) -> int:
    cur = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {TARGET_TABLE}
        WHERE strategy_id = ?
          AND target_draw = ?
          AND truth_level = ?
        """,
        (strategy_id, target_draw, TRUTH_LEVEL),
    )
    return int(cur.fetchone()[0])


def build_insert_payload(row: dict[str, Any], columns: list[str], controlled_apply_id: str) -> dict[str, Any]:
    payload = dict(row)
    payload["controlled_apply_id"] = controlled_apply_id
    if not has_column(columns, "dry_run_only"):
        payload.pop("dry_run_only", None)
    return payload


def insert_row(conn: sqlite3.Connection, row: dict[str, Any], controlled_apply_id: str, columns: list[str]) -> None:
    insert_map = build_insert_payload(row, columns, controlled_apply_id)
    keys = [key for key in insert_map.keys() if key in columns]
    values = [insert_map[key] for key in keys]
    placeholders = ", ".join(["?"] * len(keys))
    sql = f"INSERT INTO {TARGET_TABLE} ({', '.join(keys)}) VALUES ({placeholders})"
    conn.execute(sql, values)


def write_jsonl_log(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def dry_run(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        hash_before = md5sum(DB_PATH)
        columns = get_table_columns(conn)
        per_strategy = Counter()
        would_insert = 0
        would_skip_existing = 0
        for row in rows:
            existing = existing_match_count(conn, row["strategy_id"], row["target_draw"])
            if existing:
                would_skip_existing += 1
            else:
                would_insert += 1
                per_strategy[row["strategy_id"]] += 1
        hash_after = md5sum(DB_PATH)
        return {
            "mode": "dry-run",
            "target_table": TARGET_TABLE,
            "input_rows": len(rows),
            "invalid_rows": 0,
            "would_insert": would_insert,
            "would_skip_existing": would_skip_existing,
            "per_strategy": dict(sorted(per_strategy.items())),
            "db_hash_before": hash_before,
            "db_hash_after": hash_after,
            "db_hash_unchanged": hash_before == hash_after,
            "columns_seen": columns,
        }
    finally:
        conn.close()


def apply_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    controlled_apply_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:12]
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    log_entries: list[dict[str, Any]] = []
    inserted = 0
    skipped_existing = 0
    per_strategy = Counter()
    hash_before = md5sum(DB_PATH)
    try:
        columns = get_table_columns(conn)
        conn.execute("BEGIN IMMEDIATE;")
        for row in rows:
            existing = existing_match_count(conn, row["strategy_id"], row["target_draw"])
            if existing:
                skipped_existing += 1
                log_entries.append({
                    "action": "skip_existing",
                    "strategy_id": row["strategy_id"],
                    "target_draw": row["target_draw"],
                    "truth_level": TRUTH_LEVEL,
                    "controlled_apply_id": controlled_apply_id,
                })
                continue
            insert_row(conn, row, controlled_apply_id, columns)
            inserted += 1
            per_strategy[row["strategy_id"]] += 1
            log_entries.append({
                "action": "insert",
                "strategy_id": row["strategy_id"],
                "target_draw": row["target_draw"],
                "truth_level": TRUTH_LEVEL,
                "controlled_apply_id": controlled_apply_id,
            })
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()

    hash_after = md5sum(DB_PATH)
    log_file = LOG_DIR / f"p6_lite_apply_log_{controlled_apply_id}.jsonl"
    write_jsonl_log(log_file, log_entries + [{
        "action": "summary",
        "controlled_apply_id": controlled_apply_id,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "target_table": TARGET_TABLE,
        "truth_level": TRUTH_LEVEL,
    }])
    return {
        "mode": "apply",
        "controlled_apply_id": controlled_apply_id,
        "target_table": TARGET_TABLE,
        "input_rows": len(rows),
        "invalid_rows": 0,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "per_strategy": dict(sorted(per_strategy.items())),
        "db_hash_before": hash_before,
        "db_hash_after": hash_after,
        "db_hash_unchanged": hash_before == hash_after,
        "log_file": str(log_file),
    }


def rollback(controlled_apply_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        hash_before = md5sum(DB_PATH)
        cur = conn.execute(
            f"SELECT COUNT(*) FROM {TARGET_TABLE} WHERE controlled_apply_id = ?",
            (controlled_apply_id,),
        )
        target_count = int(cur.fetchone()[0])
        conn.execute("BEGIN IMMEDIATE;")
        cur = conn.execute(
            f"DELETE FROM {TARGET_TABLE} WHERE controlled_apply_id = ?",
            (controlled_apply_id,),
        )
        deleted_rows = int(cur.rowcount)
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()

    hash_after = md5sum(DB_PATH)
    return {
        "mode": "rollback",
        "controlled_apply_id": controlled_apply_id,
        "target_table": TARGET_TABLE,
        "target_rows_before_delete": target_count,
        "deleted_rows": deleted_rows,
        "db_hash_before": hash_before,
        "db_hash_after": hash_after,
        "db_hash_unchanged": hash_before == hash_after,
    }


def main() -> int:
    args = parse_args()
    rows = read_jsonl(INPUT_FILE)
    prepared_rows, invalid_rows = validate_and_prepare_rows(rows)
    if invalid_rows:
        raise SystemExit(1)

    if args.dry_run:
        result = dry_run(prepared_rows)
    elif args.apply:
        result = apply_rows(prepared_rows)
    else:
        result = rollback(args.rollback)

    result["invalid_rows"] = invalid_rows
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
