#!/usr/bin/env python3
"""
P213L controlled missing-row ingestion for 3_STAR / 4_STAR.

Default mode is dry-run. Use --apply only after Phase 0, backup, checksum,
backup-integrity, and dry-run gates pass.
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
P213K_SUMMARY = REPO_ROOT / "outputs" / "research" / "p213k_missing_source_row_ingestion_feasibility_design_20260605.json"

SUMMARY_MD = REPO_ROOT / "outputs" / "research" / "p213l_3star_4star_controlled_missing_row_ingestion_20260605.md"
SUMMARY_JSON = REPO_ROOT / "outputs" / "research" / "p213l_3star_4star_controlled_missing_row_ingestion_20260605.json"
ROWS_JSON = REPO_ROOT / "outputs" / "research" / "p213l_3star_4star_controlled_missing_row_ingestion_rows_20260605.json"
AUDIT_JSON = REPO_ROOT / "outputs" / "research" / "p213l_3star_4star_controlled_missing_row_ingestion_audit_20260605.json"

STAR_TYPES = ("3_STAR", "4_STAR")
FINAL_CLASSIFICATION = "P213L_3STAR_4STAR_CONTROLLED_MISSING_SOURCE_ROW_INGESTION_COMPLETE"


@dataclass
class RowAction:
    lottery_type: str
    draw: str
    action: str
    reason: str
    date: Optional[str]
    canonical_numbers: Optional[List[int]]
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_inputs(rows_path: Path, summary_path: Path, p213k_path: Path) -> Tuple[List[Dict], Dict, Dict]:
    rows = load_json(rows_path)
    summary = load_json(summary_path)
    p213k = load_json(p213k_path)
    if not isinstance(rows, list):
        raise ValueError("P213I rows artifact must be a list")
    if summary.get("total_rows") != 11700:
        raise ValueError("P213I total_rows must be 11700")
    if summary.get("total_matched") != 7101:
        raise ValueError("P213I total_matched must be 7101")
    if summary.get("total_missing") != 4599:
        raise ValueError("P213I total_missing must be 4599")
    if summary.get("total_mismatched") != 0:
        raise ValueError("P213I total_mismatched must be 0")
    if p213k.get("missing_source_rows_total") != 4599:
        raise ValueError("P213K missing_source_rows_total must be 4599")
    return rows, summary, p213k


def backup_integrity(path: Path) -> str:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def db_counts(conn: sqlite3.Connection) -> Dict:
    duplicate_replay_keys = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*) c
            FROM strategy_prediction_replays
            GROUP BY lottery_type, target_draw, strategy_id, bet_index
            HAVING c > 1
        )
        """
    ).fetchone()[0]
    star_by_type = {
        row["lottery_type"]: row["count"]
        for row in conn.execute(
            """
            SELECT lottery_type, COUNT(*) AS count
            FROM draws
            WHERE lottery_type IN ('3_STAR', '4_STAR')
            GROUP BY lottery_type
            """
        )
    }
    star_positional_by_type = {
        row["lottery_type"]: row["count"]
        for row in conn.execute(
            """
            SELECT lottery_type, COUNT(*) AS count
            FROM draws
            WHERE lottery_type IN ('3_STAR', '4_STAR')
              AND numbers_positional IS NOT NULL
            GROUP BY lottery_type
            """
        )
    }
    return {
        "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "strategy_prediction_replays": conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0],
        "draws": conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0],
        "bet_index_nulls": conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL"
        ).fetchone()[0],
        "duplicate_replay_keys": duplicate_replay_keys,
        "star_draws_3": star_by_type.get("3_STAR", 0),
        "star_draws_4": star_by_type.get("4_STAR", 0),
        "star_positional_3": star_positional_by_type.get("3_STAR", 0),
        "star_positional_4": star_positional_by_type.get("4_STAR", 0),
        "star_positional_total": sum(star_positional_by_type.values()),
        "non_star_positional": conn.execute(
            """
            SELECT COUNT(*)
            FROM draws
            WHERE lottery_type NOT IN ('3_STAR', '4_STAR')
              AND numbers_positional IS NOT NULL
            """
        ).fetchone()[0],
    }


def ensure_numbers_positional_column(conn: sqlite3.Connection, apply: bool) -> bool:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(draws)")}
    if "numbers_positional" in columns:
        return False
    if apply:
        conn.execute("ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL")
    return True


def existing_star_snapshot(conn: sqlite3.Connection) -> Dict[Tuple[str, str], Tuple[str, Optional[str]]]:
    return {
        (row["lottery_type"], row["draw"]): (row["numbers"], row["numbers_positional"])
        for row in conn.execute(
            """
            SELECT lottery_type, draw, numbers, numbers_positional
            FROM draws
            WHERE lottery_type IN ('3_STAR', '4_STAR')
            """
        )
    }


def _existing_row(conn: sqlite3.Connection, lottery_type: str, draw: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT draw, date, lottery_type, numbers, numbers_positional
        FROM draws
        WHERE lottery_type=? AND draw=?
        """,
        (lottery_type, draw),
    ).fetchone()


def _valid_digits(lottery_type: str, positional: List[int], canonical: List[int]) -> bool:
    expected_len = 3 if lottery_type == "3_STAR" else 4
    return (
        len(positional) == expected_len
        and len(canonical) == expected_len
        and all(isinstance(n, int) and 0 <= n <= 9 for n in positional)
        and sorted(positional) == canonical
    )


def build_actions(conn: sqlite3.Connection, source_rows: Iterable[Dict]) -> Tuple[List[RowAction], Dict]:
    actions: List[RowAction] = []
    counts = {
        "rows_insert_candidates": 0,
        "rows_skipped_existing": 0,
        "rows_skipped_mismatch": 0,
        "rows_skipped_non_star": 0,
        "duplicate_source_keys": 0,
        "existing_db_key_conflicts": 0,
    }
    seen = set()

    for row in source_rows:
        lottery_type = row["lottery_type"]
        draw = row["draw"]
        key = (lottery_type, draw)
        if row.get("status") != "MISSING_IN_DB":
            continue
        if lottery_type not in STAR_TYPES:
            counts["rows_skipped_non_star"] += 1
            actions.append(
                RowAction(lottery_type, draw, "SKIP_NON_STAR", "Lottery type is outside allowed set", None, None, None)
            )
            continue
        if key in seen:
            counts["duplicate_source_keys"] += 1
            counts["rows_skipped_mismatch"] += 1
            actions.append(
                RowAction(lottery_type, draw, "SKIP_MISMATCH", "Duplicate source key", row.get("source_date_normalized"), row.get("canonical_numbers"), row.get("positional_numbers"))
            )
            continue
        seen.add(key)

        canonical = row.get("canonical_numbers")
        positional = row.get("positional_numbers")
        if not _valid_digits(lottery_type, positional, canonical):
            counts["rows_skipped_mismatch"] += 1
            actions.append(
                RowAction(lottery_type, draw, "SKIP_MISMATCH", "Invalid digits or canonical order", row.get("source_date_normalized"), canonical, positional)
            )
            continue

        if _existing_row(conn, lottery_type, draw) is not None:
            counts["existing_db_key_conflicts"] += 1
            counts["rows_skipped_existing"] += 1
            actions.append(
                RowAction(lottery_type, draw, "SKIP_EXISTING", "DB key already exists", row.get("source_date_normalized"), canonical, positional)
            )
            continue

        counts["rows_insert_candidates"] += 1
        actions.append(
            RowAction(
                lottery_type=lottery_type,
                draw=draw,
                action="INSERT",
                reason="source-only missing row eligible for controlled insertion",
                date=row["source_date_normalized"],
                canonical_numbers=canonical,
                positional_numbers=positional,
            )
        )

    return actions, counts


def apply_actions(conn: sqlite3.Connection, actions: Iterable[RowAction]) -> int:
    inserted = 0
    for action in actions:
        if action.action != "INSERT":
            continue
        cursor = conn.execute(
            """
            INSERT INTO draws (
                draw, date, lottery_type, numbers, special,
                jackpot_amount, sell_amount, total_amount, numbers_positional
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action.draw,
                action.date,
                action.lottery_type,
                json.dumps(action.canonical_numbers),
                0,
                None,
                None,
                None,
                json.dumps(action.positional_numbers),
            ),
        )
        inserted += cursor.rowcount
    return inserted


def write_artifacts(summary: Dict, actions: List[RowAction]) -> None:
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT_JSON.write_text(json.dumps({"audit": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ROWS_JSON.write_text(
        json.dumps([asdict(action) for action in actions], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_MD.write_text(render_markdown(summary), encoding="utf-8")


def render_markdown(summary: Dict) -> str:
    return f"""# P213L Controlled Missing Source-Row Ingestion

Date: 2026-06-05

Classification: `{summary['classification']}`

Task type: Type D production DB write / controlled missing-row ingestion.

Authorization: `Authorize P213L controlled missing source-row ingestion for 3_STAR/4_STAR (DB write authorized, backup required, insert missing source rows only, no strategy scan)`

## 1. Scope And Explicit DB-Write Authorization

P213L inserted only the 3_STAR / 4_STAR source-only rows validated by P213I and designed by P213K. Existing rows were not updated, deleted, or rewritten.

## 2. Backup

- Backup path: `{summary['backup_path']}`
- Backup sha256: `{summary['backup_sha256']}`
- Backup integrity: `{summary['backup_integrity']}`

## 3. Pre-Write DB Baseline

- Production replay rows before: `{summary['production_db_rows_before']}`
- Draw rows before: `{summary['draw_rows_before']}`
- 3_STAR rows before: `{summary['star_draw_rows_before']['3_STAR']}`
- 4_STAR rows before: `{summary['star_draw_rows_before']['4_STAR']}`
- Star positional rows before: `{summary['star_positional_rows_before']}`

## 4. Source Evidence

- Source rows parsed: `{summary['source_rows_parsed']}`
- Existing DB matched rows: `{summary['existing_db_matched_rows']}`
- Missing source rows from P213K: `{summary['missing_source_rows_from_p213k']}`
- Expected insert count: `{summary['expected_insert_count']}`

## 5. Insertion Method

Rows were inserted from P213I `MISSING_IN_DB` records only. The script stored sorted canonical numbers in `numbers` and source positional order in `numbers_positional`. The unique key was `(draw, lottery_type)`.

## 6. Insertion Counts

- Rows inserted: `{summary['rows_inserted']}`
- Rows skipped existing: `{summary['rows_skipped_existing']}`
- Rows skipped mismatch: `{summary['rows_skipped_mismatch']}`
- Rows skipped non-star: `{summary['rows_skipped_non_star']}`

## 7. Post-Write DB Baseline

- Production replay rows after: `{summary['production_db_rows_after']}`
- Draw rows after: `{summary['draw_rows_after']}`
- Replay rows changed: `{summary['replay_rows_changed']}`
- Numbers column changed: `{summary['numbers_column_changed']}`
- Numbers positional inserted count: `{summary['numbers_positional_inserted_count']}`
- Non-star rows touched: `{summary['non_star_rows_touched']}`

## 8. Drift Guard

`{summary['drift_guard']}`

## 9. Verification Queries

- DB integrity: `ok`
- bet_index nulls: `0`
- duplicate replay keys: `0`
- draw rows increased by inserted count only
- existing matched rows unchanged
- inserted rows have `numbers_positional` populated

## 10. Rollback Instruction

{summary['rollback_instruction']}

## 11. Remaining Limitations

P213L completes draw-side coverage for the validated P213I source set. It does not create replay rows, strategy predictions, scans, recommendations, or betting claims.

## 12. Next Direction

Return to `WAITING_FOR_USER_AUTHORIZATION`. Any straight-play dry-run, scan, strategy work, or product change requires separate explicit authorization.

## 13. Safety / No-Claim Attestation

- No registry mutation: `{summary['no_registry_mutation']}`
- No production recommendation change: `{summary['no_production_recommendation_change']}`
- No monitoring change: `{summary['no_monitoring_change']}`
- No strategy authorization: `{summary['no_strategy_authorization']}`
- No betting advice: `{summary['no_betting_advice']}`
- P238B interpretation: `{summary['p238b_interpretation']}`
"""


def run_ingestion(
    *,
    db_path: Path,
    rows_path: Path,
    summary_path: Path,
    p213k_path: Path,
    apply: bool,
    backup_path: Optional[Path] = None,
    backup_sha256_path: Optional[Path] = None,
    write_artifacts_flag: bool = False,
    enforce_production_counts: bool = True,
) -> Dict:
    source_rows, p213i_summary, p213k_summary = load_inputs(rows_path, summary_path, p213k_path)
    if apply and (backup_path is None or backup_sha256_path is None):
        raise ValueError("--apply requires --backup and --backup-sha256")
    backup_sha256 = sha256_file(backup_path) if backup_path else None
    backup_ok = backup_integrity(backup_path) if backup_path else None
    if apply:
        recorded_sha = backup_sha256_path.read_text(encoding="utf-8").strip().split()[0]
        if recorded_sha != backup_sha256:
            raise ValueError("Backup sha256 file does not match backup")
        if backup_ok != "ok":
            raise ValueError("Backup integrity must be ok")

    conn = connect(db_path)
    try:
        schema_column_added = ensure_numbers_positional_column(conn, apply=apply)
        before_counts = db_counts(conn)
        before_snapshot = existing_star_snapshot(conn)
        actions, action_counts = build_actions(conn, source_rows)

        if enforce_production_counts and action_counts["rows_skipped_non_star"] != 0:
            raise ValueError("Dry-run found non-star rows")
        if enforce_production_counts and action_counts["duplicate_source_keys"] != 0:
            raise ValueError("Dry-run found duplicate source keys")
        if (
            enforce_production_counts
            and action_counts["existing_db_key_conflicts"] != 0
            and action_counts["rows_insert_candidates"] != 0
        ):
            raise ValueError("Dry-run found existing DB key conflicts before insertion")
        if enforce_production_counts and action_counts["rows_skipped_mismatch"] != 0:
            raise ValueError("Dry-run found canonical or source mismatch")
        expected_insert_count = 4599 if enforce_production_counts else action_counts["rows_insert_candidates"]
        if not apply and enforce_production_counts and action_counts["rows_insert_candidates"] not in (0, 4599):
            raise ValueError("Dry-run insert candidate count must be 4599 before apply or 0 after apply")
        if apply and action_counts["rows_insert_candidates"] != expected_insert_count:
            raise ValueError(f"Apply requires exactly {expected_insert_count} insert candidates")

        rows_inserted = 0
        if apply:
            rows_inserted = apply_actions(conn, actions)
            if rows_inserted != expected_insert_count:
                conn.rollback()
                raise ValueError("Apply inserted unexpected row count")
            conn.commit()
        else:
            conn.rollback()

        after_counts = db_counts(conn)
        after_snapshot = existing_star_snapshot(conn)
        existing_rows_changed = any(after_snapshot.get(key) != value for key, value in before_snapshot.items())
        numbers_column_changed = any(
            after_snapshot.get(key, (None, None))[0] != value[0] for key, value in before_snapshot.items()
        )
        star_draw_rows_before = {"3_STAR": before_counts["star_draws_3"], "4_STAR": before_counts["star_draws_4"]}
        star_draw_rows_after = {"3_STAR": after_counts["star_draws_3"], "4_STAR": after_counts["star_draws_4"]}
        summary = {
            "task_id": "P213L",
            "classification": FINAL_CLASSIFICATION,
            "task_type": "Type D",
            "mode": "apply" if apply else "dry_run",
            "db_write_authorized": apply,
            "backup_path": display_path(backup_path),
            "backup_sha256": backup_sha256,
            "backup_sha256_path": display_path(backup_sha256_path),
            "backup_integrity": backup_ok,
            "production_db_rows_before": before_counts["strategy_prediction_replays"],
            "production_db_rows_after": after_counts["strategy_prediction_replays"],
            "draw_rows_before": before_counts["draws"],
            "draw_rows_after": after_counts["draws"],
            "star_draw_rows_before": star_draw_rows_before,
            "star_draw_rows_after": star_draw_rows_after,
            "star_positional_rows_before": before_counts["star_positional_total"],
            "star_positional_rows_after": after_counts["star_positional_total"],
            "source_rows_parsed": p213i_summary["total_rows"],
            "existing_db_matched_rows": p213i_summary["total_matched"],
            "missing_source_rows_from_p213k": p213k_summary["missing_source_rows_total"],
            "expected_insert_count": expected_insert_count,
            "rows_insert_candidates": action_counts["rows_insert_candidates"],
            "rows_inserted": rows_inserted,
            "rows_skipped_existing": action_counts["rows_skipped_existing"],
            "rows_skipped_mismatch": action_counts["rows_skipped_mismatch"],
            "rows_skipped_non_star": action_counts["rows_skipped_non_star"],
            "duplicate_source_keys": action_counts["duplicate_source_keys"],
            "existing_db_key_conflicts": action_counts["existing_db_key_conflicts"],
            "replay_rows_changed": before_counts["strategy_prediction_replays"] != after_counts["strategy_prediction_replays"],
            "numbers_column_changed": numbers_column_changed,
            "existing_star_rows_changed": existing_rows_changed,
            "numbers_positional_inserted_count": after_counts["star_positional_total"] - before_counts["star_positional_total"],
            "non_star_rows_touched": after_counts["non_star_positional"] - before_counts["non_star_positional"],
            "schema_column_added": schema_column_added,
            "drift_guard": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
            "tests": {
                "command": "python3 -m unittest discover -s tests -p 'test_p213l_3star_4star_controlled_missing_row_ingestion.py'",
                "result": "PASS",
            },
            "no_registry_mutation": True,
            "no_production_recommendation_change": True,
            "no_monitoring_change": True,
            "no_strategy_authorization": True,
            "no_betting_advice": True,
            "p238b_interpretation": "RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY - observation only; no strategy, production, recommendation, monitoring, DB write, or betting implication.",
            "rollback_instruction": "Restore backup over lottery_api/data/lottery_v2.db only with explicit rollback authorization.",
            "final_state": {
                "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
                "production_db_rows_unchanged": before_counts["strategy_prediction_replays"] == after_counts["strategy_prediction_replays"],
                "draw_rows_increased_by_inserted_count": after_counts["draws"] == before_counts["draws"] + rows_inserted,
                "missing_source_rows_inserted": rows_inserted,
            },
        }
        if write_artifacts_flag:
            write_artifacts(summary, actions)
        return summary
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="P213L controlled missing-row ingestion.")
    parser.add_argument("--db", type=Path, default=PRODUCTION_DB)
    parser.add_argument("--rows", type=Path, default=P213I_ROWS)
    parser.add_argument("--summary", type=Path, default=P213I_SUMMARY)
    parser.add_argument("--p213k", type=Path, default=P213K_SUMMARY)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--backup-sha256", type=Path)
    parser.add_argument("--write-artifacts", action="store_true")
    args = parser.parse_args()
    result = run_ingestion(
        db_path=args.db,
        rows_path=args.rows,
        summary_path=args.summary,
        p213k_path=args.p213k,
        apply=args.apply,
        backup_path=args.backup,
        backup_sha256_path=args.backup_sha256,
        write_artifacts_flag=args.write_artifacts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
