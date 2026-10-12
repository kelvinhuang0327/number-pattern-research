#!/usr/bin/env python3
"""
P19B — Power Lotto Temp-DB Rehearsal (and optional production apply).

Rehearses inserting P19 dry-run candidates into a COPY of the production DB.
Never touches the production DB unless --allow-production is explicitly passed.

Modes:
  --apply          Insert candidates (idempotent via dup-detect).
  --rollback       Delete by controlled_apply_id.
  --dry-run        Report what would happen; no DB write.
  --full-rehearsal Apply → rerun → rollback → combined JSON.
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
_P19_INPUT  = _REPO_ROOT / "outputs" / "replay" / "p19_powerlotto_single_strategy_replay_dry_run_20260520.json"
_OUT_DIR    = _REPO_ROOT / "outputs" / "replay"
_OUT_FILE   = _OUT_DIR / "p19b_powerlotto_tempdb_rehearsal_20260520.json"

PHASE        = "P19B_POWERLOTTO_TEMPDB_REHEARSAL"
LOTTERY_TYPE = "POWER_LOTTO"
APPLY_ID     = "P19B_POWERLOTTO_FOURIER_1500_PROD_20260520"
TRUTH_LEVEL  = "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED"
SOURCE       = "P19_POWERLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN"
EXPECTED_READY = 1500


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


def _assert_not_prod(db: Path, allow_production: bool) -> None:
    if db.resolve() == _PROD_DB.resolve() and not allow_production:
        raise RuntimeError(
            f"SAFETY STOP: refusing to write to production DB without --allow-production. DB={db}"
        )


def _generate_candidates(db_path: Path) -> list[dict]:
    """Re-generate all 1500 POWER_LOTTO candidates from the adapter."""
    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """SELECT draw, date, numbers, special FROM draws
               WHERE lottery_type='POWER_LOTTO'
               ORDER BY CAST(draw AS INTEGER) ASC"""
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

    adapter   = get_adapter("fourier_rhythm_3bet")
    min_hist  = adapter.meta.min_history
    window    = all_draws[-1500:]
    run_ts    = datetime.now(timezone.utc).isoformat()

    candidates = []
    for draw_row in window:
        gidx    = all_draws.index(draw_row)
        history = all_draws[:gidx]
        if len(history) < min_hist:
            continue
        try:
            pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
        except Exception:
            continue
        if not pred_numbers or len(pred_numbers) != 6:
            continue

        actual_numbers = list(draw_row["numbers"])
        actual_special = draw_row["special"]
        hit_nums  = sorted(set(pred_numbers) & set(actual_numbers))
        hit_count = len(hit_nums)
        special_hit = (
            bool(pred_special == actual_special)
            if pred_special is not None and actual_special is not None
            else False
        )

        raw    = f"fourier_rhythm_3bet:{draw_row['draw']}:{sorted(pred_numbers)}"
        p_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
        cutoff_date = history[-1]["date"] if history else None

        candidates.append({
            "strategy_id":       "fourier_rhythm_3bet",
            "strategy_name":     "威力彩 Fourier Rhythm 3注",
            "strategy_version":  "v0.1",
            "lottery_type":      LOTTERY_TYPE,
            "draw_number":       draw_row["draw"],
            "draw_date":         draw_row["date"],
            "history_cutoff":    history[-1]["draw"] if history else None,
            "predicted_numbers": sorted(pred_numbers),
            "predicted_special": pred_special,
            "actual_numbers":    sorted(actual_numbers),
            "actual_special":    actual_special,
            "hit_numbers":       hit_nums,
            "hit_count":         hit_count,
            "special_hit":       special_hit,
            "provenance_hash":   p_hash,
            "prediction_cutoff_date":  cutoff_date,
            "prediction_generated_at": run_ts,
        })

    return candidates


def apply_rehearsal(
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
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows, got {rows_before}"
        )
    if len(candidates) != EXPECTED_READY:
        raise RuntimeError(
            f"SAFETY STOP: expected {EXPECTED_READY} candidates, got {len(candidates)}"
        )

    existing = _existing_keys(db, "fourier_rhythm_3bet")
    now_ts   = datetime.now(timezone.utc).isoformat()
    inserted = dupes = errors = 0

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in candidates:
                dup_key = f"fourier_rhythm_3bet|{c['draw_number']}"
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
                        ) VALUES (
                            ?,?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?,?,
                            NULL, ?,?, ?,?, ?,NULL, ?,
                            ?,?
                        )""",
                        (
                            c["lottery_type"], c["draw_number"], c["draw_date"],
                            c["strategy_id"], c["strategy_name"], c["strategy_version"],
                            c["history_cutoff"], "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c["predicted_special"],
                            json.dumps(c["actual_numbers"]), c["actual_special"],
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
                            now_ts, TRUTH_LEVEL, apply_id, SOURCE,
                            c["provenance_hash"],
                            0 if (allow_production and db.resolve() == _PROD_DB.resolve()) else 1,
                            c["prediction_cutoff_date"],
                            c["prediction_generated_at"],
                        ),
                    )
                    existing.add(dup_key)
                    inserted += 1
                except Exception as exc:
                    errors += 1
                    print(f"[P19B] insert error {c['draw_number']}: {exc}", file=sys.stderr)
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":              PHASE,
        "mode":               "apply",
        "temp_db_only":       not allow_production or db.resolve() != _PROD_DB.resolve(),
        "production_apply":   allow_production and db.resolve() == _PROD_DB.resolve(),
        "controlled_apply_id": apply_id,
        "expected_rows_before": expected_rows_before,
        "rows_before":        rows_before,
        "planned_insert_count": len(candidates),
        "inserted_count":     inserted,
        "duplicate_count":    dupes,
        "error_count":        errors,
        "rows_after_apply":   rows_after,
        "fake_success_count": 0,
    }
    if json_out:
        _write(result, json_out)
    return result


def rollback_rehearsal(
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
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows, got {rows_before}"
        )

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?",
                (apply_id,),
            )
            deleted = cur.rowcount
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                  PHASE,
        "mode":                   "rollback",
        "temp_db_only":           not allow_production or db.resolve() != _PROD_DB.resolve(),
        "controlled_apply_id":    apply_id,
        "rows_before":            rows_before,
        "rollback_deleted_count": deleted,
        "rows_after_rollback":    rows_after,
    }
    if json_out:
        _write(result, json_out)
    return result


def full_rehearsal(
    db: Path,
    apply_id: str,
    initial_expected_rows: int,
    candidates: list[dict],
    *,
    json_out_r1: Path | None = None,
    json_out_r2: Path | None = None,
    json_out_rb: Path | None = None,
    json_out_combined: Path | None = None,
) -> dict:
    r1 = apply_rehearsal(db, candidates, apply_id,
                         expected_rows_before=initial_expected_rows,
                         json_out=json_out_r1)
    rows_mid = r1["rows_after_apply"]
    print(f"[P19B] R1 apply: inserted={r1['inserted_count']} dupes={r1['duplicate_count']} rows={rows_mid}")

    r2 = apply_rehearsal(db, candidates, apply_id,
                         expected_rows_before=rows_mid,
                         json_out=json_out_r2)
    rows_after_rerun = r2["rows_after_apply"]
    print(f"[P19B] R2 rerun: inserted={r2['inserted_count']} dupes={r2['duplicate_count']} rows={rows_after_rerun}")

    rb = rollback_rehearsal(db, apply_id,
                            expected_rows_before=rows_after_rerun,
                            json_out=json_out_rb)
    rows_final = rb["rows_after_rollback"]
    print(f"[P19B] Rollback: deleted={rb['rollback_deleted_count']} rows={rows_final}")

    prod_rows = _row_count(_PROD_DB)

    def _classify():
        if prod_rows not in (4960, 6460):
            return "P19B_BLOCKED_BY_PRODUCTION_DB_DRIFT"
        if r1["inserted_count"] != EXPECTED_READY:
            return f"P19B_BLOCKED_BY_APPLY_FAILURE_inserted={r1['inserted_count']}"
        if r1["rows_after_apply"] != initial_expected_rows + EXPECTED_READY:
            return "P19B_BLOCKED_BY_IDEMPOTENCY_FAILURE"
        if r2["inserted_count"] != 0 or r2["duplicate_count"] != EXPECTED_READY:
            return "P19B_BLOCKED_BY_IDEMPOTENCY_FAILURE"
        if rb["rollback_deleted_count"] != EXPECTED_READY or rb["rows_after_rollback"] != initial_expected_rows:
            return "P19B_BLOCKED_BY_ROLLBACK_FAILURE"
        return "P19B_TEMP_DB_REHEARSAL_READY"

    combined = {
        "phase":                    PHASE,
        "generated_at":             datetime.now(timezone.utc).isoformat(),
        "production_apply":         False,
        "temp_db_only":             True,
        "controlled_apply_id":      apply_id,
        "expected_rows_before":     initial_expected_rows,
        "rows_before":              r1["rows_before"],
        "planned_insert_count":     r1["planned_insert_count"],
        "inserted_count":           r1["inserted_count"],
        "duplicate_count":          r1["duplicate_count"],
        "error_count":              r1["error_count"],
        "rows_after_apply":         rows_mid,
        "rerun_inserted_count":     r2["inserted_count"],
        "rerun_duplicate_count":    r2["duplicate_count"],
        "rows_after_rerun":         rows_after_rerun,
        "rollback_deleted_count":   rb["rollback_deleted_count"],
        "rows_after_rollback":      rows_final,
        "production_rows_after":    prod_rows,
        "fake_success_count":       0,
        "final_classification":     _classify(),
    }

    if json_out_combined:
        _write(combined, json_out_combined)
    return combined


def _write(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P19B] written → {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P19B Power Lotto temp DB rehearsal")
    parser.add_argument("--db",                  default="/tmp/lottery_v2_p19b_powerlotto_rehearsal.db")
    parser.add_argument("--backup",              default=None)
    parser.add_argument("--input",               default=str(_P19_INPUT))
    parser.add_argument("--json-out",            default=None)
    parser.add_argument("--expected-rows",       type=int, default=4960)
    parser.add_argument("--controlled-apply-id", default=APPLY_ID)
    parser.add_argument("--allow-production",    action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",          action="store_true")
    mode.add_argument("--rollback",       action="store_true")
    mode.add_argument("--dry-run",        action="store_true")
    mode.add_argument("--full-rehearsal", action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    apply_id = args.controlled_apply_id
    json_out = Path(args.json_out) if args.json_out else None

    # Validate P19 input
    p19_data = json.loads(Path(args.input).read_text())
    if p19_data.get("ready_candidates", 0) != EXPECTED_READY:
        print(f"SAFETY STOP: P19 input has {p19_data.get('ready_candidates')} ready, expected {EXPECTED_READY}", file=sys.stderr)
        sys.exit(2)

    candidates = _generate_candidates(db if db.resolve() != _PROD_DB.resolve() else _PROD_DB)

    if args.dry_run:
        print(f"[P19B] dry-run: {len(candidates)} candidates, no DB writes")
        if json_out:
            _write({"phase": PHASE, "mode": "dry-run", "candidates_generated": len(candidates), "db_writes": 0}, json_out)
        return

    if args.apply:
        r = apply_rehearsal(db, candidates, apply_id, args.expected_rows,
                            allow_production=args.allow_production, json_out=json_out)
        print(f"[P19B] apply: inserted={r['inserted_count']} dupes={r['duplicate_count']} rows={r['rows_after_apply']}")

    elif args.rollback:
        r = rollback_rehearsal(db, apply_id, args.expected_rows,
                               allow_production=args.allow_production, json_out=json_out)
        print(f"[P19B] rollback: deleted={r['rollback_deleted_count']} rows={r['rows_after_rollback']}")

    elif args.full_rehearsal:
        combined = full_rehearsal(
            db, apply_id, args.expected_rows, candidates,
            json_out_r1=Path("/tmp/p19b_apply_r1.json"),
            json_out_r2=Path("/tmp/p19b_apply_r2.json"),
            json_out_rb=Path("/tmp/p19b_rollback.json"),
            json_out_combined=json_out or _OUT_FILE,
        )
        print(f"[P19B] full_rehearsal classification: {combined['final_classification']}")


if __name__ == "__main__":
    main()
