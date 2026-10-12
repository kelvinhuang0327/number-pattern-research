#!/usr/bin/env python3
"""
P21B — Daily 539 Temp-DB Rehearsal (and optional production apply).

Handles both ONLINE DAILY_539 strategies (daily539_f4cold + daily539_markov_cold)
in one pass. 3000 rows total (1500 per strategy).

Modes:
  --temp-rehearsal  Insert into temp DB only (refuses production DB).
  --apply           Insert into specified DB (requires --allow-production for prod).
  --rollback        Delete by controlled_apply_id.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_PROD_DB   = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR   = _REPO_ROOT / "outputs" / "replay"

PHASE        = "P21B_DAILY539_TEMPDB_REHEARSAL"
LOTTERY_TYPE = "DAILY_539"
APPLY_ID     = "P21B_DAILY539_BOTH_1500_PROD_20260520"
TRUTH_LEVEL  = "DAILY539_BACKFILL_VERIFIED"
SOURCE       = "P21_DAILY539_REPLAY_DRY_RUN"
STRATEGIES   = ["daily539_f4cold", "daily539_markov_cold"]
TARGET_WINDOW = 1500
EXPECTED_READY = 3000


def _row_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


def _existing_keys(db: Path, strategy_id: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT strategy_id || '|' || target_draw FROM strategy_prediction_replays WHERE strategy_id=?",
            (strategy_id,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def _assert_not_prod(db: Path, allow_production: bool) -> None:
    if db.resolve() == _PROD_DB.resolve() and not allow_production:
        raise RuntimeError(f"SAFETY STOP: refusing to write to production DB without --allow-production")


def _generate_candidates(db_path: Path, draw_db: Path | None = None) -> list[dict]:
    """
    Generate all 3000 DAILY_539 candidates from both adapters.
    draw_db: source of draw history (defaults to _PROD_DB).
             Separate from db_path which is used for duplicate checking.
    """
    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    _draw_src = draw_db or _PROD_DB
    conn = sqlite3.connect(str(_draw_src))
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws WHERE lottery_type='DAILY_539' ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    all_draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers)
            sp = None  # DAILY_539 has no special number
            all_draws.append({"draw": draw, "date": date, "numbers": [int(n) for n in nums], "special": sp})
        except Exception:
            pass

    window  = all_draws[-TARGET_WINDOW:]
    run_ts  = datetime.now(timezone.utc).isoformat()
    candidates = []

    for strategy_id in STRATEGIES:
        adapter       = get_adapter(strategy_id)
        min_hist      = adapter.meta.min_history
        strategy_name = adapter.meta.strategy_name
        strategy_ver  = adapter.meta.strategy_version

        existing_keys = _existing_keys(db_path, strategy_id)

        for draw_row in window:
            gidx    = all_draws.index(draw_row)
            history = all_draws[:gidx]
            if len(history) < min_hist:
                continue
            dup_key = f"{strategy_id}|{draw_row['draw']}"
            if dup_key in existing_keys:
                continue
            try:
                pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
            except Exception:
                continue
            if not pred_numbers or len(pred_numbers) != 5:
                continue

            actual_numbers = list(draw_row["numbers"])
            hit_nums  = sorted(set(pred_numbers) & set(actual_numbers))
            hit_count = len(hit_nums)
            raw = f"{strategy_id}:{draw_row['draw']}:{sorted(pred_numbers)}"
            p_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
            cutoff_date = history[-1]["date"] if history else None

            candidates.append({
                "strategy_id":      strategy_id,
                "strategy_name":    strategy_name,
                "strategy_version": strategy_ver,
                "lottery_type":     LOTTERY_TYPE,
                "draw_number":      draw_row["draw"],
                "draw_date":        draw_row["date"],
                "history_cutoff":   history[-1]["draw"] if history else None,
                "predicted_numbers": sorted(pred_numbers),
                "predicted_special": None,
                "actual_numbers":    sorted(actual_numbers),
                "actual_special":    None,
                "hit_numbers":       hit_nums,
                "hit_count":         hit_count,
                "special_hit":       False,
                "provenance_hash":   p_hash,
                "prediction_cutoff_date":  cutoff_date,
                "prediction_generated_at": run_ts,
            })

    return candidates


def apply_to_db(
    db: Path,
    candidates: list[dict],
    apply_id: str,
    expected_rows_before: int,
    *,
    allow_production: bool = False,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db, allow_production)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(f"SAFETY STOP: expected {expected_rows_before} rows, got {rows_before}")

    is_prod = allow_production and db.resolve() == _PROD_DB.resolve()

    existing: set[str] = set()
    for sid in STRATEGIES:
        existing |= _existing_keys(db, sid)

    now_ts = datetime.now(timezone.utc).isoformat()
    inserted = dupes = errors = 0

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in candidates:
                dup_key = f"{c['strategy_id']}|{c['draw_number']}"
                if dup_key in existing:
                    dupes += 1
                    continue
                try:
                    conn.execute(
                        """INSERT INTO strategy_prediction_replays (
                            lottery_type, target_draw, target_date,
                            strategy_id, strategy_name, strategy_version,
                            history_cutoff_draw, replay_status,
                            predicted_numbers, predicted_special,
                            actual_numbers, actual_special,
                            hit_numbers, hit_count, special_hit,
                            replay_run_id, generated_at, truth_level,
                            controlled_apply_id, source,
                            provenance_hash, provenance_source, dry_run,
                            prediction_cutoff_date, prediction_generated_at
                        ) VALUES (?,?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?,?,
                                  NULL, ?,?, ?,?, ?,NULL, ?, ?,?)""",
                        (
                            c["lottery_type"], c["draw_number"], c["draw_date"],
                            c["strategy_id"], c["strategy_name"], c["strategy_version"],
                            c["history_cutoff"], "PREDICTED",
                            json.dumps(c["predicted_numbers"]), None,
                            json.dumps(c["actual_numbers"]), None,
                            json.dumps(c["hit_numbers"]), c["hit_count"], 0,
                            now_ts, TRUTH_LEVEL, apply_id, SOURCE,
                            c["provenance_hash"],
                            0 if is_prod else 1,
                            c["prediction_cutoff_date"], c["prediction_generated_at"],
                        ),
                    )
                    existing.add(dup_key)
                    inserted += 1
                except Exception as exc:
                    errors += 1
                    print(f"[P21B] insert error {c['strategy_id']}:{c['draw_number']}: {exc}", file=sys.stderr)
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":               PHASE,
        "mode":                "apply",
        "production_apply":    is_prod,
        "temp_db_only":        not is_prod,
        "controlled_apply_id": apply_id,
        "expected_rows_before": expected_rows_before,
        "rows_before":         rows_before,
        "planned_insert_count": len(candidates),
        "inserted_count":      inserted,
        "duplicate_count":     dupes,
        "error_count":         errors,
        "rows_after_apply":    rows_after,
        "fake_success_count":  0,
    }
    if json_out:
        _write(result, json_out)
    return result


def rollback_from_db(
    db: Path,
    apply_id: str,
    expected_rows_before: int,
    *,
    allow_production: bool = False,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db, allow_production)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(f"SAFETY STOP: expected {expected_rows_before} rows, got {rows_before}")

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            cur = conn.execute("DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?", (apply_id,))
            deleted = cur.rowcount
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                  PHASE,
        "mode":                   "rollback",
        "controlled_apply_id":    apply_id,
        "rows_before":            rows_before,
        "rollback_deleted_count": deleted,
        "rows_after_rollback":    rows_after,
    }
    if json_out:
        _write(result, json_out)
    return result


def _write(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P21B] written → {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P21B Daily 539 temp-DB rehearsal")
    parser.add_argument("--db",                  default="/tmp/lottery_v2_p21b_daily539_rehearsal.db")
    parser.add_argument("--backup",              default=None)
    parser.add_argument("--json-out",            default=None)
    parser.add_argument("--expected-rows",       type=int, default=9460)
    parser.add_argument("--controlled-apply-id", default=APPLY_ID)
    parser.add_argument("--allow-production",    action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--temp-rehearsal", action="store_true")
    mode.add_argument("--apply",          action="store_true")
    mode.add_argument("--rollback",       action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    apply_id = args.controlled_apply_id
    json_out = Path(args.json_out) if args.json_out else None

    candidates = _generate_candidates(_PROD_DB)
    print(f"[P21B] generated {len(candidates)} candidates")

    if args.temp_rehearsal or args.apply:
        r = apply_to_db(db, candidates, apply_id, args.expected_rows,
                        allow_production=args.allow_production, json_out=json_out)
        print(f"[P21B] inserted={r['inserted_count']} dupes={r['duplicate_count']} rows={r['rows_after_apply']}")
    elif args.rollback:
        r = rollback_from_db(db, apply_id, args.expected_rows,
                             allow_production=args.allow_production, json_out=json_out)
        print(f"[P21B] rollback: deleted={r['rollback_deleted_count']} rows={r['rows_after_rollback']}")


if __name__ == "__main__":
    main()
