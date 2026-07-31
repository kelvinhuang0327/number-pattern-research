#!/usr/bin/env python3
"""
P20 — Power Lotto Remaining ONLINE Strategies Backfill.

Handles power_precision_3bet and power_orthogonal_5bet in one pass.
All rows share the same controlled_apply_id.

Modes:
  --dry-run         Generate candidates, no DB write.
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

_PROD_DB    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR    = _REPO_ROOT / "outputs" / "replay"

PHASE        = "P20_POWERLOTTO_REMAINING_STRATEGIES"
LOTTERY_TYPE = "POWER_LOTTO"
APPLY_ID     = "P20_POWERLOTTO_REMAINING_1500_PROD_20260520"
TRUTH_LEVEL  = "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
SOURCE       = "P20_POWERLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY"
STRATEGIES   = ["power_precision_3bet", "power_orthogonal_5bet"]
TARGET_WINDOW = 1500


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


def _load_draws(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws WHERE lottery_type='POWER_LOTTO' ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()
    draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers)
            draws.append({"draw": draw, "date": date, "numbers": [int(n) for n in nums],
                          "special": int(special) if special is not None else None})
        except Exception:
            pass
    return draws


def _generate_all_candidates(db_path: Path) -> list[dict]:
    """Generate dry-run candidates for all remaining strategies."""
    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    all_draws = _load_draws(db_path)
    window    = all_draws[-TARGET_WINDOW:]
    run_ts    = datetime.now(timezone.utc).isoformat()
    candidates = []

    for strategy_id in STRATEGIES:
        adapter     = get_adapter(strategy_id)
        min_hist    = adapter.meta.min_history
        strategy_name = adapter.meta.strategy_name

        existing_keys = _existing_keys(db_path, strategy_id)

        for draw_row in window:
            gidx    = all_draws.index(draw_row)
            history = all_draws[:gidx]

            actual_numbers = list(draw_row["numbers"])
            actual_special = draw_row["special"]
            draw_number    = draw_row["draw"]
            draw_date      = draw_row["date"]

            if len(history) < min_hist:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": "BLOCKED_INSUFFICIENT_HISTORY",
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"need={min_hist},have={len(history)}",
                    "provenance_hash": None, "truth_level": "DRY_RUN_REPLAY_BACKFILL",
                    "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            dup_key = f"{strategy_id}|{draw_number}"
            if dup_key in existing_keys:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": "BLOCKED_DUPLICATE_REPLAY_ROW",
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": "existing_in_production_table",
                    "provenance_hash": None, "truth_level": "DRY_RUN_REPLAY_BACKFILL",
                    "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            try:
                pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
            except Exception as exc:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": "BLOCKED_NO_PREDICTION_PAYLOAD",
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"{type(exc).__name__}:{exc}",
                    "provenance_hash": None, "truth_level": "DRY_RUN_REPLAY_BACKFILL",
                    "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            if not pred_numbers or len(pred_numbers) != 6:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": "BLOCKED_NO_PREDICTION_PAYLOAD",
                    "predicted_numbers": pred_numbers, "predicted_special": pred_special,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"bad_pred_len={len(pred_numbers) if pred_numbers else 0}",
                    "provenance_hash": None, "truth_level": "DRY_RUN_REPLAY_BACKFILL",
                    "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            hit_nums    = sorted(set(pred_numbers) & set(actual_numbers))
            hit_count   = len(hit_nums)
            special_hit = bool(pred_special == actual_special) if (
                pred_special is not None and actual_special is not None
            ) else False
            cutoff_date = history[-1]["date"] if history else None
            p_hash = hashlib.sha256(f"{strategy_id}:{draw_number}:{sorted(pred_numbers)}".encode()).hexdigest()[:16]

            candidates.append({
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE,
                "target_draw": draw_number, "target_date": draw_date,
                "prediction_status": "READY",
                "predicted_numbers": sorted(pred_numbers), "predicted_special": pred_special,
                "actual_numbers": sorted(actual_numbers), "actual_special": actual_special,
                "hit_numbers": hit_nums, "hit_count": hit_count, "special_hit": special_hit,
                "prediction_cutoff_date": cutoff_date, "prediction_generated_at": run_ts,
                "source_trace": f"{strategy_id}:get_one_bet:hist={len(history)}",
                "provenance_hash": p_hash, "truth_level": "DRY_RUN_REPLAY_BACKFILL",
                "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                # apply metadata
                "_history_cutoff_draw": history[-1]["draw"] if history else None,
                "_strategy_version": adapter.meta.strategy_version,
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

    ready = [c for c in candidates if c["prediction_status"] == "READY"]
    now_ts = datetime.now(timezone.utc).isoformat()
    is_prod = allow_production and db.resolve() == _PROD_DB.resolve()

    # Build per-strategy existing keys from the target DB (re-query for idempotency)
    existing: set[str] = set()
    for sid in STRATEGIES:
        existing |= _existing_keys(db, sid)

    inserted = dupes = errors = 0
    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in ready:
                dup_key = f"{c['strategy_id']}|{c['target_draw']}"
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
                            c["lottery_type"], c["target_draw"], c["target_date"],
                            c["strategy_id"], c["strategy_name"], c.get("_strategy_version", "v0.1"),
                            c.get("_history_cutoff_draw"), "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c["predicted_special"],
                            json.dumps(c["actual_numbers"]), c["actual_special"],
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
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
                    print(f"[P20] insert error {c['strategy_id']}:{c['target_draw']}: {exc}", file=sys.stderr)
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":             PHASE,
        "mode":              "apply",
        "production_apply":  is_prod,
        "temp_db_only":      not is_prod,
        "controlled_apply_id": apply_id,
        "expected_rows_before": expected_rows_before,
        "rows_before":       rows_before,
        "planned_insert_count": len(ready),
        "inserted_count":    inserted,
        "duplicate_count":   dupes,
        "error_count":       errors,
        "rows_after_apply":  rows_after,
        "fake_success_count": 0,
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
    print(f"[P20] written → {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P20 Power Lotto remaining strategies backfill")
    parser.add_argument("--db",                  default=str(_PROD_DB))
    parser.add_argument("--backup",              default=None)
    parser.add_argument("--json-out",            default=None)
    parser.add_argument("--expected-rows",       type=int, default=6460)
    parser.add_argument("--controlled-apply-id", default=APPLY_ID)
    parser.add_argument("--allow-production",    action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run",       action="store_true")
    mode.add_argument("--temp-rehearsal", action="store_true")
    mode.add_argument("--apply",         action="store_true")
    mode.add_argument("--rollback",      action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    apply_id = args.controlled_apply_id
    json_out = Path(args.json_out) if args.json_out else None

    # Generate candidates (always from production draw data)
    candidates = _generate_all_candidates(_PROD_DB)
    ready      = [c for c in candidates if c["prediction_status"] == "READY"]
    by_status  = {}
    for c in candidates:
        by_status[c["prediction_status"]] = by_status.get(c["prediction_status"], 0) + 1
    dups_existing  = by_status.get("BLOCKED_DUPLICATE_REPLAY_ROW", 0)
    blocked_other  = sum(v for k, v in by_status.items()
                         if k not in ("READY", "BLOCKED_DUPLICATE_REPLAY_ROW"))

    if args.dry_run:
        rows_before = _row_count(_PROD_DB)
        # Build sample
        seen: dict[str, int] = {}
        sample = []
        for c in candidates:
            s = c["prediction_status"]
            if seen.get(s, 0) < 5:
                sample.append(c)
                seen[s] = seen.get(s, 0) + 1

        ready_rows   = [c for c in candidates if c["prediction_status"] == "READY"]
        page_sample  = [
            {"target_draw": r["target_draw"], "target_date": r["target_date"],
             "strategy_id": r["strategy_id"], "strategy_name": r["strategy_name"],
             "predicted_numbers": r["predicted_numbers"], "actual_numbers": r["actual_numbers"],
             "hit_numbers": r["hit_numbers"], "hit_count": r["hit_count"],
             "special_hit": r["special_hit"], "prediction_cutoff_date": r["prediction_cutoff_date"],
             "prediction_generated_at": r["prediction_generated_at"],
             "display_status": "SHOW_REPLAY_DRY_RUN", "truth_level": "DRY_RUN_REPLAY_BACKFILL"}
            for r in ready_rows[-20:]
        ]

        result = {
            "phase": f"{PHASE}_DRY_RUN",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "production_apply": False, "dry_run_only": True,
            "production_rows_before": rows_before, "production_rows_after": rows_before,
            "lottery_type": LOTTERY_TYPE,
            "target_draw_window": TARGET_WINDOW,
            "strategies": STRATEGIES,
            "generated_candidates": len(candidates),
            "ready_candidates": len(ready),
            "blocked_candidates": len(candidates) - len(ready),
            "duplicate_existing_count": dups_existing,
            "planned_insert_count": len(ready),
            "by_status": by_status,
            "fake_success_count": 0,
            "candidates_sample": sample,
            "page_ready_sample": page_sample,
        }
        if json_out:
            _write(result, json_out)
        print(f"[P20] dry-run: ready={len(ready)} blocked={len(candidates)-len(ready)} dups={dups_existing}")
        return

    if args.temp_rehearsal or args.apply:
        r = apply_to_db(db, candidates, apply_id, args.expected_rows,
                        allow_production=args.allow_production, json_out=json_out)
        print(f"[P20] {'apply' if args.apply else 'temp-rehearsal'}: inserted={r['inserted_count']} dupes={r['duplicate_count']} rows={r['rows_after_apply']}")

    elif args.rollback:
        r = rollback_from_db(db, apply_id, args.expected_rows,
                             allow_production=args.allow_production, json_out=json_out)
        print(f"[P20] rollback: deleted={r['rollback_deleted_count']} rows={r['rows_after_rollback']}")


if __name__ == "__main__":
    main()
