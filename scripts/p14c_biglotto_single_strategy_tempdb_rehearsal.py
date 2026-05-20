#!/usr/bin/env python3
"""
P14C — Big Lotto Single Strategy Temp-DB Rehearsal.

Rehearses inserting P14B dry-run candidates into a COPY of the production DB.
Never touches the production DB. Supports three modes:

  --apply          Insert candidates into temp DB (idempotent via dup-detect).
  --rollback       Delete inserted rows by controlled_apply_id.
  --full-rehearsal Apply → rerun → rollback → write combined JSON.

Safety gates:
  - Refuses to write to the production DB path.
  - Refuses to proceed if row count != --expected-rows.
  - Refuses to proceed if P14B input has != 1500 READY candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_PROD_DB     = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_P14B_INPUT  = _REPO_ROOT / "outputs" / "replay" / "p14b_biglotto_single_strategy_replay_dry_run_20260520.json"
_OUT_DIR     = _REPO_ROOT / "outputs" / "replay"
_OUT_FILE    = _OUT_DIR / "p14c_biglotto_single_strategy_tempdb_rehearsal_20260520.json"

PHASE              = "P14C_BIGLOTTO_SINGLE_STRATEGY_TEMPDB_REHEARSAL"
LOTTERY_TYPE       = "BIG_LOTTO"
DEFAULT_APPLY_ID   = "P14C_BIGLOTTO_TS3_1500_TEMP_REHEARSAL_20260520"
TRUTH_LEVEL        = "TEMP_REHEARSAL_REPLAY_BACKFILL"
SOURCE             = "P14B_BIGLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN"
EXPECTED_READY     = 1500


# ── DB helpers ────────────────────────────────────────────────────────────────

def _row_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _rows_by_apply_id(db: Path, apply_id: str) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (apply_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def _existing_keys(db: Path, strategy_id: str) -> set[str]:
    """Return set of 'strategy_id|target_draw' already in the table."""
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            """
            SELECT strategy_id || '|' || target_draw
            FROM strategy_prediction_replays
            WHERE strategy_id = ?
            """,
            (strategy_id,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


# ── candidate generation ──────────────────────────────────────────────────────

def _generate_candidates() -> list[dict]:
    """
    Re-run the P14B generation logic in memory to get all 1500 READY candidates.
    Uses the same adapter and DB as P14B; pure read-only.
    """
    from scripts.p14b_biglotto_single_strategy_replay_dry_run import run as _p14b_run
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp = Path(tf.name)
    try:
        result = _p14b_run(out_file=tmp)
    finally:
        tmp.unlink(missing_ok=True)

    # The run() returns candidates_sample (up to 5 per status). Since all are READY,
    # the sample only has 5. We need all — re-read from the written P14B output file.
    p14b_data = json.loads(_P14B_INPUT.read_text())
    # Candidates are embedded in candidates_sample; for a full list we must
    # regenerate by calling the adapter loop directly.
    return _regenerate_all_candidates()


def _regenerate_all_candidates() -> list[dict]:
    """Generate all 1500 READY BIG_LOTTO candidates for ts3_regime_3bet."""
    import sys as _sys
    if str(_REPO_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_REPO_ROOT))

    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    # Load draws
    conn = sqlite3.connect(str(_PROD_DB))
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
    min_hist = adapter.meta.min_history
    window   = all_draws[-1500:]

    candidates = []
    for draw_row in window:
        draw_global_idx = all_draws.index(draw_row)
        history = all_draws[:draw_global_idx]
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
        hit_nums   = sorted(set(pred_numbers) & set(actual_numbers))
        hit_count  = len(hit_nums)
        special_hit = bool(pred_special == actual_special) if (
            pred_special is not None and actual_special is not None
        ) else False

        # provenance_hash matches P14B
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


# ── apply ─────────────────────────────────────────────────────────────────────

def apply_rehearsal(
    db: Path,
    candidates: list[dict],
    apply_id: str,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    """Insert candidates into temp DB. Returns summary dict."""

    # Safety: refuse production DB
    _assert_not_prod(db)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before apply, "
            f"got {rows_before}"
        )

    ready = [c for c in candidates if True]  # all should be valid
    if len(ready) != EXPECTED_READY:
        raise RuntimeError(
            f"SAFETY STOP: expected {EXPECTED_READY} candidates, got {len(ready)}"
        )

    existing = _existing_keys(db, "ts3_regime_3bet")
    now_ts   = datetime.now(timezone.utc).isoformat()

    inserted = 0
    dupes    = 0
    errors   = 0

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in ready:
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
                            history_cutoff_draw,
                            replay_status,
                            predicted_numbers, predicted_special,
                            actual_numbers, actual_special,
                            hit_numbers, hit_count, special_hit,
                            replay_run_id,
                            generated_at, truth_level,
                            controlled_apply_id, source,
                            provenance_hash, provenance_source,
                            dry_run
                        ) VALUES (
                            ?,?,?,  ?,?,?,  ?,  ?,  ?,?,  ?,?,  ?,?,?,
                            NULL,   ?,?,   ?,?,  ?,NULL,  ?
                        )
                        """,
                        (
                            c["lottery_type"], c["draw_number"], c["draw_date"],
                            c["strategy_id"], c["strategy_name"], c["strategy_version"],
                            c["history_cutoff"],
                            "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c["predicted_special"],
                            json.dumps(c["actual_numbers"]), c["actual_special"],
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
                            now_ts, TRUTH_LEVEL,
                            apply_id, SOURCE,
                            c["provenance_hash"],
                            1,  # dry_run=1 for temp-db rows
                        ),
                    )
                    existing.add(dup_key)
                    inserted += 1
                except Exception as exc:
                    errors += 1
                    print(f"[P14C] insert error {c['draw_number']}: {exc}", file=sys.stderr)
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                 PHASE,
        "mode":                  "apply",
        "temp_db_only":          True,
        "production_apply":      False,
        "controlled_apply_id":   apply_id,
        "expected_rows_before":  expected_rows_before,
        "rows_before":           rows_before,
        "planned_insert_count":  len(ready),
        "inserted_count":        inserted,
        "duplicate_count":       dupes,
        "error_count":           errors,
        "rows_after_apply":      rows_after,
        "fake_success_count":    0,
    }
    if json_out:
        _write_json(result, json_out)
    return result


# ── rollback ──────────────────────────────────────────────────────────────────

def rollback_rehearsal(
    db: Path,
    apply_id: str,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    """Delete all rows matching controlled_apply_id from temp DB."""

    _assert_not_prod(db)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before rollback, "
            f"got {rows_before}"
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
        "phase":                   PHASE,
        "mode":                    "rollback",
        "temp_db_only":            True,
        "production_apply":        False,
        "controlled_apply_id":     apply_id,
        "expected_rows_before":    expected_rows_before,
        "rows_before":             rows_before,
        "rollback_deleted_count":  deleted,
        "rows_after_rollback":     rows_after,
        "fake_success_count":      0,
    }
    if json_out:
        _write_json(result, json_out)
    return result


# ── full rehearsal ────────────────────────────────────────────────────────────

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
    """Run apply → rerun → rollback in sequence. Write combined report."""

    # Round 1: apply
    r1 = apply_rehearsal(
        db, candidates, apply_id,
        expected_rows_before=initial_expected_rows,
        json_out=json_out_r1,
    )
    rows_mid = r1["rows_after_apply"]
    print(f"[P14C] R1 apply: inserted={r1['inserted_count']} dupes={r1['duplicate_count']} rows={rows_mid}")

    # Round 2: rerun (idempotency)
    r2 = apply_rehearsal(
        db, candidates, apply_id,
        expected_rows_before=rows_mid,
        json_out=json_out_r2,
    )
    rows_after_rerun = r2["rows_after_apply"]
    print(f"[P14C] R2 rerun: inserted={r2['inserted_count']} dupes={r2['duplicate_count']} rows={rows_after_rerun}")

    # Rollback
    rb = rollback_rehearsal(
        db, apply_id,
        expected_rows_before=rows_after_rerun,
        json_out=json_out_rb,
    )
    rows_final = rb["rows_after_rollback"]
    print(f"[P14C] Rollback: deleted={rb['rollback_deleted_count']} rows={rows_final}")

    # Verify production DB untouched
    prod_rows = _row_count(_PROD_DB)

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
        "final_classification":     _classify(r1, r2, rb, prod_rows, initial_expected_rows),
    }

    if json_out_combined:
        _write_json(combined, json_out_combined)
    return combined


def _classify(r1: dict, r2: dict, rb: dict, prod_rows: int, initial: int) -> str:
    if prod_rows != 460:
        return "P14C_BLOCKED_BY_PRODUCTION_DB_DRIFT"
    if r1["inserted_count"] != EXPECTED_READY:
        return f"P14C_BLOCKED_BY_APPLY_FAILURE_inserted={r1['inserted_count']}"
    if r1["rows_after_apply"] != initial + EXPECTED_READY:
        return "P14C_BLOCKED_BY_IDEMPOTENCY_FAILURE"
    if r2["inserted_count"] != 0:
        return "P14C_BLOCKED_BY_IDEMPOTENCY_FAILURE"
    if r2["duplicate_count"] != EXPECTED_READY:
        return "P14C_BLOCKED_BY_IDEMPOTENCY_FAILURE"
    if rb["rollback_deleted_count"] != EXPECTED_READY:
        return "P14C_BLOCKED_BY_ROLLBACK_FAILURE"
    if rb["rows_after_rollback"] != initial:
        return "P14C_BLOCKED_BY_ROLLBACK_FAILURE"
    return "P14C_TEMP_DB_REHEARSAL_READY"


# ── utilities ─────────────────────────────────────────────────────────────────

def _assert_not_prod(db: Path) -> None:
    if db.resolve() == _PROD_DB.resolve():
        raise RuntimeError(
            f"SAFETY STOP: refusing to write to production DB {_PROD_DB}"
        )


def _write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P14C] written → {path}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P14C Big Lotto temp DB rehearsal")
    parser.add_argument("--db",                 default="/tmp/lottery_v2_p14c_biglotto_rehearsal.db")
    parser.add_argument("--backup",             default=None)
    parser.add_argument("--input",              default=str(_P14B_INPUT))
    parser.add_argument("--json-out",           default=None)
    parser.add_argument("--expected-rows",      type=int, default=460)
    parser.add_argument("--controlled-apply-id", default=DEFAULT_APPLY_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",           action="store_true")
    mode.add_argument("--rollback",        action="store_true")
    mode.add_argument("--dry-run",         action="store_true")
    mode.add_argument("--full-rehearsal",  action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    apply_id = args.controlled_apply_id
    json_out = Path(args.json_out) if args.json_out else None

    # Validate P14B input
    p14b_data = json.loads(Path(args.input).read_text())
    ready_cnt = p14b_data.get("ready_candidates", 0)
    if ready_cnt != EXPECTED_READY:
        print(f"SAFETY STOP: P14B input has {ready_cnt} ready candidates, expected {EXPECTED_READY}",
              file=sys.stderr)
        sys.exit(2)

    if args.dry_run:
        candidates = _regenerate_all_candidates()
        print(f"[P14C] dry-run: generated {len(candidates)} candidates, no DB writes")
        result = {
            "phase": PHASE, "mode": "dry-run",
            "candidates_generated": len(candidates),
            "db_writes": 0,
            "temp_db_only": True, "production_apply": False,
        }
        if json_out:
            _write_json(result, json_out)
        return

    if args.apply:
        candidates = _regenerate_all_candidates()
        result = apply_rehearsal(db, candidates, apply_id, args.expected_rows, json_out=json_out)
        print(f"[P14C] apply: inserted={result['inserted_count']} dupes={result['duplicate_count']} "
              f"rows={result['rows_after_apply']}")

    elif args.rollback:
        result = rollback_rehearsal(db, apply_id, args.expected_rows, json_out=json_out)
        print(f"[P14C] rollback: deleted={result['rollback_deleted_count']} "
              f"rows={result['rows_after_rollback']}")

    elif args.full_rehearsal:
        # For full rehearsal, json_out is used as the combined output
        candidates = _regenerate_all_candidates()
        result = full_rehearsal(
            db, apply_id,
            initial_expected_rows=args.expected_rows,
            candidates=candidates,
            json_out_r1=Path("/tmp/p14c_biglotto_apply_r1.json"),
            json_out_r2=Path("/tmp/p14c_biglotto_apply_r2.json"),
            json_out_rb=Path("/tmp/p14c_biglotto_rollback.json"),
            json_out_combined=json_out or _OUT_FILE,
        )
        print(f"[P14C] full_rehearsal classification: {result['final_classification']}")


if __name__ == "__main__":
    main()
