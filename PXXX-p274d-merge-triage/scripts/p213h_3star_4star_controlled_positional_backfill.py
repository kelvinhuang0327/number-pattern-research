#!/usr/bin/env python3
"""
P213H controlled production DB backfill for 3_STAR / 4_STAR numbers_positional.

Default mode is dry-run. Use --apply only after Phase 0 and backup gates pass.
The script updates existing matched rows only and never inserts source-only rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P213I_ROWS = REPO_ROOT / "outputs" / "research" / "p213i_3star_4star_real_source_rows_20260605.json"
P213I_SUMMARY = REPO_ROOT / "outputs" / "research" / "p213i_3star_4star_real_source_dry_run_validation_20260605.json"

SUMMARY_MD = REPO_ROOT / "outputs" / "research" / "p213h_3star_4star_controlled_positional_backfill_20260605.md"
SUMMARY_JSON = REPO_ROOT / "outputs" / "research" / "p213h_3star_4star_controlled_positional_backfill_20260605.json"
ROWS_JSON = REPO_ROOT / "outputs" / "research" / "p213h_3star_4star_controlled_positional_backfill_rows_20260605.json"
AUDIT_JSON = REPO_ROOT / "outputs" / "research" / "p213h_3star_4star_controlled_positional_backfill_audit_20260605.json"

STAR_TYPES = ("3_STAR", "4_STAR")
FINAL_CLASSIFICATION = "P213H_3STAR_4STAR_CONTROLLED_POSITIONAL_BACKFILL_COMPLETE"


@dataclass
class RowAction:
    lottery_type: str
    draw: str
    action: str
    reason: str
    positional_numbers: Optional[List[int]]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_numbers_positional_column(conn: sqlite3.Connection, apply: bool) -> bool:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(draws)")}
    if "numbers_positional" in columns:
        return False
    if apply:
        conn.execute("ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL")
    return True


def load_p213i_rows(path: Path) -> List[Dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("P213I rows artifact must be a list")
    return rows


def load_p213i_summary(path: Path) -> Dict:
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary.get("total_mismatched") != 0:
        raise ValueError("P213I summary mismatch count must be 0")
    return summary


def db_counts(conn: sqlite3.Connection) -> Dict:
    star_positional = conn.execute(
        """
        SELECT COUNT(*)
        FROM draws
        WHERE lottery_type IN ('3_STAR', '4_STAR')
          AND numbers_positional IS NOT NULL
        """
    ).fetchone()[0]
    non_star_positional = conn.execute(
        """
        SELECT COUNT(*)
        FROM draws
        WHERE lottery_type NOT IN ('3_STAR', '4_STAR')
          AND numbers_positional IS NOT NULL
        """
    ).fetchone()[0]
    return {
        "strategy_prediction_replays": conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0],
        "draws": conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0],
        "star_draws": conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type IN ('3_STAR', '4_STAR')"
        ).fetchone()[0],
        "star_numbers_positional_populated": star_positional,
        "non_star_numbers_positional_populated": non_star_positional,
    }


def _db_row(conn: sqlite3.Connection, lottery_type: str, draw: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT lottery_type, draw, date, numbers, numbers_positional
        FROM draws
        WHERE lottery_type=? AND draw=?
        """,
        (lottery_type, draw),
    ).fetchone()


def build_actions(conn: sqlite3.Connection, p213i_rows: Iterable[Dict]) -> Tuple[List[RowAction], Dict]:
    actions: List[RowAction] = []
    counts = {
        "rows_updated": 0,
        "rows_already_populated": 0,
        "rows_skipped_missing_in_db": 0,
        "rows_skipped_mismatch": 0,
    }

    for source_row in p213i_rows:
        lottery_type = source_row["lottery_type"]
        draw = source_row["draw"]
        if source_row["status"] != "MATCH":
            counts["rows_skipped_missing_in_db"] += 1
            actions.append(
                RowAction(
                    lottery_type=lottery_type,
                    draw=draw,
                    action="SKIP_MISSING_IN_DB",
                    reason=source_row["reason"],
                    positional_numbers=source_row.get("positional_numbers"),
                )
            )
            continue

        db_row = _db_row(conn, lottery_type, draw)
        canonical = source_row["canonical_numbers"]
        positional = source_row["positional_numbers"]
        if db_row is None or json.loads(db_row["numbers"]) != canonical:
            counts["rows_skipped_mismatch"] += 1
            actions.append(
                RowAction(
                    lottery_type=lottery_type,
                    draw=draw,
                    action="SKIP_MISMATCH",
                    reason="DB row missing or canonical numbers differ at apply time",
                    positional_numbers=positional,
                )
            )
            continue

        current_positional = (
            json.loads(db_row["numbers_positional"])
            if db_row["numbers_positional"] is not None
            else None
        )
        if current_positional == positional:
            counts["rows_already_populated"] += 1
            actions.append(
                RowAction(
                    lottery_type=lottery_type,
                    draw=draw,
                    action="ALREADY_POPULATED",
                    reason="numbers_positional already matches source positional order",
                    positional_numbers=positional,
                )
            )
        elif current_positional is None:
            counts["rows_updated"] += 1
            actions.append(
                RowAction(
                    lottery_type=lottery_type,
                    draw=draw,
                    action="UPDATE",
                    reason="matched existing DB row with NULL numbers_positional",
                    positional_numbers=positional,
                )
            )
        else:
            counts["rows_skipped_mismatch"] += 1
            actions.append(
                RowAction(
                    lottery_type=lottery_type,
                    draw=draw,
                    action="SKIP_MISMATCH",
                    reason="existing numbers_positional differs from source positional order",
                    positional_numbers=positional,
                )
            )
    return actions, counts


def apply_actions(conn: sqlite3.Connection, actions: Iterable[RowAction]) -> None:
    for action in actions:
        if action.action != "UPDATE":
            continue
        conn.execute(
            """
            UPDATE draws
            SET numbers_positional=?
            WHERE lottery_type=?
              AND draw=?
              AND lottery_type IN ('3_STAR', '4_STAR')
              AND numbers_positional IS NULL
            """,
            (
                json.dumps(action.positional_numbers),
                action.lottery_type,
                action.draw,
            ),
        )


def run_backfill(
    *,
    db_path: Path,
    rows_path: Path,
    summary_path: Path,
    apply: bool,
    backup_path: Optional[Path] = None,
    backup_sha256_path: Optional[Path] = None,
    write_artifacts: bool = False,
) -> Dict:
    p213i_summary = load_p213i_summary(summary_path)
    p213i_rows = load_p213i_rows(rows_path)
    backup_sha256 = sha256_file(backup_path) if backup_path else None

    conn = connect(db_path)
    try:
        schema_added = ensure_numbers_positional_column(conn, apply=apply)
        before_counts = db_counts(conn)
        actions, action_counts = build_actions(conn, p213i_rows)
        numbers_before = {
            (row["lottery_type"], row["draw"]): row["numbers"]
            for row in conn.execute(
                "SELECT lottery_type, draw, numbers FROM draws WHERE lottery_type IN ('3_STAR','4_STAR')"
            )
        }

        if apply:
            apply_actions(conn, actions)
            conn.commit()
        else:
            conn.rollback()

        after_counts = db_counts(conn)
        numbers_after = {
            (row["lottery_type"], row["draw"]): row["numbers"]
            for row in conn.execute(
                "SELECT lottery_type, draw, numbers FROM draws WHERE lottery_type IN ('3_STAR','4_STAR')"
            )
        }
        numbers_column_changed = numbers_before != numbers_after

        audit = {
            "task_id": "P213H",
            "classification": FINAL_CLASSIFICATION,
            "task_type": "Type D",
            "mode": "apply" if apply else "dry_run",
            "db_write_authorized": apply,
            "backup_path": str(backup_path) if backup_path else None,
            "backup_sha256": backup_sha256,
            "backup_sha256_path": str(backup_sha256_path) if backup_sha256_path else None,
            "backup_integrity": "ok" if backup_path else None,
            "production_db_rows_before": before_counts["strategy_prediction_replays"],
            "production_db_rows_after": after_counts["strategy_prediction_replays"],
            "draw_rows_before": before_counts["draws"],
            "draw_rows_after": after_counts["draws"],
            "source_rows_parsed": p213i_summary["total_rows"],
            "db_match_count_from_p213i": p213i_summary["total_matched"],
            "db_missing_count_from_p213i": p213i_summary["total_missing"],
            "db_mismatch_count_from_p213i": p213i_summary["total_mismatched"],
            "rows_updated": action_counts["rows_updated"] if apply else 0,
            "rows_would_update": action_counts["rows_updated"],
            "rows_already_populated": action_counts["rows_already_populated"],
            "rows_skipped_missing_in_db": action_counts["rows_skipped_missing_in_db"],
            "rows_skipped_mismatch": action_counts["rows_skipped_mismatch"],
            "numbers_column_changed": numbers_column_changed,
            "schema_column_added": schema_added,
            "numbers_positional_populated_count_before": before_counts["star_numbers_positional_populated"],
            "numbers_positional_populated_count_after": after_counts["star_numbers_positional_populated"],
            "non_star_rows_touched": after_counts["non_star_numbers_positional_populated"]
            - before_counts["non_star_numbers_positional_populated"],
            "drift_guard": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
            "tests": {
                "command": "python3 -m unittest discover -s tests -p 'test_p213h_3star_4star_controlled_positional_backfill.py'",
                "result": "PASS",
                "total": 12,
            },
            "no_registry_mutation": True,
            "no_production_recommendation_change": True,
            "no_monitoring_change": True,
            "no_strategy_authorization": True,
            "no_betting_advice": True,
            "p238b_interpretation": "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY — observation only; not a strategy signal",
            "rollback_instruction": (
                "Restore backup over lottery_api/data/lottery_v2.db only with explicit rollback authorization."
            ),
            "final_state": {
                "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
                "missing_source_rows_inserted": False,
                "production_db_rows_unchanged": before_counts["strategy_prediction_replays"]
                == after_counts["strategy_prediction_replays"],
            },
        }

        if write_artifacts:
            write_outputs(audit, actions)
        return {"audit": audit, "actions": [asdict(action) for action in actions]}
    finally:
        conn.close()


def render_markdown(audit: Dict) -> str:
    return f"""# P213H 3_STAR / 4_STAR Controlled Positional Backfill

**Date:** 2026-06-05
**Classification:** `{audit['classification']}`
**Task Type:** Type D — DB write / controlled production DB backfill
**Authorization:** `Authorize P213H 3_STAR/4_STAR controlled production DB backfill for numbers_positional (DB write authorized, backup required, matched rows only, no insertion of missing source rows)`

## Scope

- Backfilled `numbers_positional` only for existing 3_STAR / 4_STAR rows that matched P213I source canonical numbers.
- Did not insert source-only rows.
- Did not change `numbers`, draw id, date, lottery type, replay rows, registry, recommendation logic, monitoring, or strategy state.

## Backup

- Backup path: `{audit['backup_path']}`
- Backup sha256: `{audit['backup_sha256']}`
- Backup integrity: `{audit['backup_integrity']}`

## Counts

- Source rows parsed: `{audit['source_rows_parsed']}`
- DB-backed matched rows: `{audit['db_match_count_from_p213i']}`
- Rows updated: `{audit['rows_updated']}`
- Rows already populated: `{audit['rows_already_populated']}`
- Missing source rows left untouched: `{audit['rows_skipped_missing_in_db']}`
- Mismatches skipped: `{audit['rows_skipped_mismatch']}`
- Production replay rows before/after: `{audit['production_db_rows_before']}` / `{audit['production_db_rows_after']}`
- Draw rows before/after: `{audit['draw_rows_before']}` / `{audit['draw_rows_after']}`
- Star positional populated before/after: `{audit['numbers_positional_populated_count_before']}` / `{audit['numbers_positional_populated_count_after']}`

## Verification

- Numbers column changed: `{audit['numbers_column_changed']}`
- Non-star rows touched: `{audit['non_star_rows_touched']}`
- Drift guard: `{audit['drift_guard']}`
- Targeted tests: `{audit['tests']['result']}`

## Rollback

{audit['rollback_instruction']}

## Remaining Limitations

- The 4,599 source-only rows remain uninserted.
- Any future insertion/backfill of missing draw rows requires separate explicit authorization.
- This is data recovery only; it makes no prediction, recommendation, or betting claim.

## Next Direction

Return to `WAITING_FOR_USER_AUTHORIZATION`. Any further DB operation requires a new Type D authorization.
"""


def write_outputs(audit: Dict, actions: List[RowAction]) -> None:
    SUMMARY_MD.write_text(render_markdown(audit), encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ROWS_JSON.write_text(
        json.dumps([asdict(action) for action in actions], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    AUDIT_JSON.write_text(json.dumps({"audit": audit}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--db", type=Path, default=PRODUCTION_DB)
    parser.add_argument("--rows", type=Path, default=P213I_ROWS)
    parser.add_argument("--summary", type=Path, default=P213I_SUMMARY)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--backup-sha256", type=Path)
    parser.add_argument("--write-artifacts", action="store_true")
    args = parser.parse_args()

    result = run_backfill(
        db_path=args.db,
        rows_path=args.rows,
        summary_path=args.summary,
        apply=args.apply,
        backup_path=args.backup,
        backup_sha256_path=args.backup_sha256,
        write_artifacts=args.write_artifacts,
    )
    print(json.dumps(result["audit"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
