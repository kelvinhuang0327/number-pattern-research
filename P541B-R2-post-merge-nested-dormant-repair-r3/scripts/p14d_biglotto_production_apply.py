#!/usr/bin/env python3
"""
P14D — Big Lotto Single Strategy Production Apply.

EXPLICITLY authorized to write to the production DB.
Authorization: YES apply Big Lotto single strategy replay rows

Inserts 1500 ts3_regime_3bet replay rows into the production
strategy_prediction_replays table. Idempotent via duplicate detection on
(strategy_id, lottery_type, target_draw).

Safety requirements:
  - --expected-rows must match actual production row count before apply.
  - Rollback available by running with --rollback.
  - truth_level = BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED
  - source     = P14D_BIGLOTTO_PRODUCTION_APPLY
  - dry_run    = 0 (this is a real production apply, not rehearsal)
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
_OUT_FILE  = _OUT_DIR / "p14d_biglotto_production_apply_result_20260520.json"

PHASE       = "P14D_BIGLOTTO_PRODUCTION_APPLY"
APPLY_ID    = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
TRUTH_LEVEL = "BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
SOURCE      = "P14D_BIGLOTTO_PRODUCTION_APPLY"
LOTTERY_TYPE = "BIG_LOTTO"
EXPECTED_CANDIDATES = 1500


# ── candidate generation (shared with P14C) ───────────────────────────────────

def _generate_candidates(db_path: Path) -> list[dict]:
    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT draw, date, numbers, special
            FROM draws WHERE lottery_type='BIG_LOTTO'
            ORDER BY CAST(draw AS INTEGER) ASC
            """
        ).fetchall()
    finally:
        conn.close()

    all_draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers)
            all_draws.append({
                "draw":    draw,
                "date":    date,
                "numbers": [int(n) for n in nums],
                "special": int(special) if special is not None else None,
            })
        except Exception:
            pass

    adapter = get_adapter("ts3_regime_3bet")
    window  = all_draws[-1500:]

    candidates = []
    for draw_row in window:
        draw_global_idx = all_draws.index(draw_row)
        history = all_draws[:draw_global_idx]
        if len(history) < adapter.meta.min_history:
            continue
        try:
            pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
        except Exception:
            continue
        if not pred_numbers or len(pred_numbers) != 6:
            continue

        actual_numbers = list(draw_row["numbers"])
        actual_special = draw_row["special"]
        hit_nums   = sorted(set(pred_numbers) & set(actual_numbers))
        hit_count  = len(hit_nums)
        special_hit = bool(pred_special == actual_special) if (
            pred_special is not None and actual_special is not None
        ) else False

        raw = f"ts3_regime_3bet:{draw_row['draw']}:{sorted(pred_numbers)}"
        p_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

        candidates.append({
            "strategy_id":      "ts3_regime_3bet",
            "strategy_name":    "大樂透 TS3+Regime 3注",
            "strategy_version": "v0.1",
            "lottery_type":     LOTTERY_TYPE,
            "draw_number":      draw_row["draw"],
            "draw_date":        draw_row["date"],
            "history_cutoff":   all_draws[draw_global_idx - 1]["draw"] if draw_global_idx > 0 else None,
            "predicted_numbers": sorted(pred_numbers),
            "predicted_special": pred_special,
            "actual_numbers":    sorted(actual_numbers),
            "actual_special":    actual_special,
            "hit_numbers":       hit_nums,
            "hit_count":         hit_count,
            "special_hit":       special_hit,
            "provenance_hash":   p_hash,
        })

    return candidates


# ── DB helpers ────────────────────────────────────────────────────────────────

def _row_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
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


# ── apply ─────────────────────────────────────────────────────────────────────

def apply_production(
    db: Path,
    candidates: list[dict],
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before apply, got {rows_before}"
        )

    existing = _existing_keys(db, "ts3_regime_3bet")
    now_ts   = datetime.now(timezone.utc).isoformat()
    inserted = dupes = errors = 0

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in candidates:
                dup_key = f"ts3_regime_3bet|{c['draw_number']}"
                if dup_key in existing:
                    dupes += 1
                    continue
                try:
                    conn.execute(
                        """
                        INSERT INTO strategy_prediction_replays (
                            lottery_type, target_draw, target_date,
                            strategy_id, strategy_name, strategy_version,
                            history_cutoff_draw, replay_status,
                            predicted_numbers, predicted_special,
                            actual_numbers, actual_special,
                            hit_numbers, hit_count, special_hit,
                            replay_run_id, generated_at, truth_level,
                            controlled_apply_id, source,
                            provenance_hash, provenance_source, dry_run
                        ) VALUES (
                            ?,?,?,  ?,?,?,  ?,?,  ?,?,  ?,?,  ?,?,?,
                            NULL, ?,?,  ?,?,  ?,NULL, ?
                        )
                        """,
                        (
                            c["lottery_type"], c["draw_number"], c["draw_date"],
                            c["strategy_id"], c["strategy_name"], c["strategy_version"],
                            c["history_cutoff"], "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c["predicted_special"],
                            json.dumps(c["actual_numbers"]), c["actual_special"],
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
                            now_ts, TRUTH_LEVEL, APPLY_ID, SOURCE,
                            c["provenance_hash"], 0,  # dry_run=0 for production
                        ),
                    )
                    existing.add(dup_key)
                    inserted += 1
                except Exception as exc:
                    errors += 1
                    print(f"[P14D] insert error {c['draw_number']}: {exc}", file=sys.stderr)
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                  PHASE,
        "generated_at":           datetime.now(timezone.utc).isoformat(),
        "production_apply":       True,
        "temp_db_only":           False,
        "controlled_apply_id":    APPLY_ID,
        "expected_rows_before":   expected_rows_before,
        "rows_before":            rows_before,
        "planned_insert_count":   EXPECTED_CANDIDATES,
        "inserted_count":         inserted,
        "duplicate_count":        dupes,
        "error_count":            errors,
        "rows_after_apply":       rows_after,
        "fake_success_count":     0,
        "final_classification":   "P14D_PRODUCTION_APPLY_COMPLETE" if (
            inserted == EXPECTED_CANDIDATES and errors == 0 and rows_after == rows_before + inserted
        ) else f"P14D_BLOCKED_BY_APPLY_FAILURE_inserted={inserted}_errors={errors}",
    }
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"[P14D] written → {json_out}")
    return result


# ── rollback ──────────────────────────────────────────────────────────────────

def rollback_production(
    db: Path,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before rollback, got {rows_before}"
        )
    conn = sqlite3.connect(str(db))
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?",
                (APPLY_ID,),
            )
            deleted = cur.rowcount
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                   PHASE + "_ROLLBACK",
        "generated_at":            datetime.now(timezone.utc).isoformat(),
        "controlled_apply_id":     APPLY_ID,
        "rows_before":             rows_before,
        "rollback_deleted_count":  deleted,
        "rows_after_rollback":     rows_after,
    }
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"[P14D] rollback written → {json_out}")
    return result


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P14D Big Lotto production apply")
    parser.add_argument("--db",             default=str(_PROD_DB))
    parser.add_argument("--json-out",       default=str(_OUT_FILE))
    parser.add_argument("--expected-rows",  type=int, default=460)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",    action="store_true")
    mode.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    json_out = Path(args.json_out)

    if args.apply:
        print(f"[P14D] Generating {EXPECTED_CANDIDATES} candidates …")
        candidates = _generate_candidates(db)
        print(f"[P14D] Generated {len(candidates)} candidates")
        result = apply_production(db, candidates, args.expected_rows, json_out=json_out)
        print(f"[P14D] classification: {result['final_classification']}")
        print(f"[P14D] inserted={result['inserted_count']} dupes={result['duplicate_count']} "
              f"errors={result['error_count']} rows_after={result['rows_after_apply']}")
    elif args.rollback:
        result = rollback_production(db, args.expected_rows, json_out=json_out)
        print(f"[P14D] rollback deleted={result['rollback_deleted_count']} rows={result['rows_after_rollback']}")


if __name__ == "__main__":
    main()
