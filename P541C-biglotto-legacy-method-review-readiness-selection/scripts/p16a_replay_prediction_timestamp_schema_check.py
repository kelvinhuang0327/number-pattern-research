#!/usr/bin/env python3
"""
P16A — Schema check for prediction timestamp columns.

Checks whether strategy_prediction_replays has:
  - prediction_cutoff_date
  - prediction_generated_at

If missing, reports schema_patch_required=true and emits the ALTER TABLE
statements needed (additive only, no data loss).

Also applies the patch to a target DB if --apply-patch is given.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_REPO  = Path(__file__).resolve().parents[1]
_PROD_DB = _REPO / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR = _REPO / "outputs" / "replay"

PHASE = "P16A_PREDICTION_TIMESTAMP_SCHEMA_CHECK"
TABLE = "strategy_prediction_replays"

REQUIRED_COLUMNS = ["prediction_cutoff_date", "prediction_generated_at"]

PATCH_SQL = [
    f"ALTER TABLE {TABLE} ADD COLUMN prediction_cutoff_date TEXT;",
    f"ALTER TABLE {TABLE} ADD COLUMN prediction_generated_at TEXT;",
]


def check_schema(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(f"PRAGMA table_info({TABLE})").fetchall()
        prod_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()

    existing_cols = {r[1] for r in rows}

    result = {
        "phase":                        PHASE,
        "generated_at":                 datetime.now(timezone.utc).isoformat(),
        "table":                        TABLE,
        "production_rows":              prod_rows,
        "existing_columns":             sorted(existing_cols),
        "has_prediction_cutoff_date":   "prediction_cutoff_date" in existing_cols,
        "has_prediction_generated_at":  "prediction_generated_at" in existing_cols,
        "has_generated_at":             "generated_at" in existing_cols,
        "has_target_date":              "target_date" in existing_cols,
        "has_history_cutoff_draw":      "history_cutoff_draw" in existing_cols,
        "schema_patch_required":        not all(c in existing_cols for c in REQUIRED_COLUMNS),
        "recommended_columns":          REQUIRED_COLUMNS,
        "patch_sql":                    PATCH_SQL if not all(
            c in existing_cols for c in REQUIRED_COLUMNS
        ) else [],
    }
    return result


def apply_patch(db_path: Path, *, dry_run: bool = False) -> dict:
    result = check_schema(db_path)
    if not result["schema_patch_required"]:
        result["patch_applied"] = False
        result["patch_status"] = "NO_PATCH_NEEDED"
        return result

    if dry_run:
        result["patch_applied"] = False
        result["patch_status"] = "DRY_RUN_NOT_APPLIED"
        return result

    conn = sqlite3.connect(str(db_path))
    applied = []
    errors = []
    try:
        existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})").fetchall()}
        for col, sql in zip(REQUIRED_COLUMNS, PATCH_SQL):
            if col in existing_cols:
                continue
            try:
                conn.execute(sql)
                applied.append(col)
            except Exception as exc:
                errors.append(f"{col}: {exc}")
        conn.commit()
    finally:
        conn.close()

    result["patch_applied"] = len(applied) > 0
    result["applied_columns"] = applied
    result["patch_errors"] = errors
    result["patch_status"] = "PATCH_APPLIED" if not errors else "PATCH_PARTIAL_ERROR"
    # re-check
    post = check_schema(db_path)
    result["schema_patch_required_after"] = post["schema_patch_required"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="P16A schema check for prediction timestamps")
    parser.add_argument("--db",          default=str(_PROD_DB))
    parser.add_argument("--json-out",    default=None)
    parser.add_argument("--apply-patch", action="store_true", default=False,
                        help="Apply additive ALTER TABLE statements to target DB.")
    args = parser.parse_args()

    db = Path(args.db)

    if args.apply_patch:
        result = apply_patch(db)
    else:
        result = check_schema(db)

    out = Path(args.json_out) if args.json_out else (
        _OUT_DIR / "p16a_prediction_timestamp_schema_check_20260520.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"[P16A] written → {out}")

    if result.get("schema_patch_required"):
        print(f"[P16A] schema_patch_required=true — columns missing: "
              f"{[c for c in REQUIRED_COLUMNS if not result.get(f'has_{c}', False)]}")
    else:
        print("[P16A] schema OK — all required columns present")


if __name__ == "__main__":
    main()
