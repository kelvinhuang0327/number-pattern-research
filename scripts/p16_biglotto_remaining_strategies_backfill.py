#!/usr/bin/env python3
"""
P16 — Big Lotto Remaining ONLINE Strategies Backfill.

Extends the replay table with 1500-draw coverage for the two remaining
ONLINE BIG_LOTTO strategies (after ts3_regime_3bet was handled by P14D):

    - biglotto_triple_strike
    - biglotto_deviation_2bet

Each strategy already has ~70 legacy rows; only non-duplicate rows are inserted.

Modes
-----
--dry-run          (default) Generate candidates, no DB write.
--temp-rehearsal   Copy production DB then apply/rerun/rollback in temp DB.
--apply            Insert into production DB. Requires --allow-production.
--rollback         Delete rows by controlled_apply_id from the target DB.

Key Safety Rules
----------------
- Production DB is never written unless --apply AND --allow-production are set.
- DB path must not end with production path unless --allow-production is set.
- Duplicate detection key: strategy_id + lottery_type + target_draw.
- No fabricated predicted_numbers or actual_numbers.
- RETIRED / NO_DATA / ARTIFACT_ONLY rows are never applied.
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

_PROD_DB   = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR   = _REPO_ROOT / "outputs" / "replay"

LOTTERY_TYPE    = "BIG_LOTTO"
TARGET_WINDOW   = 1500
APPLY_ID        = "P16_BIGLOTTO_REMAINING_1500_PROD_20260520"
TRUTH_LEVEL     = "BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"
SOURCE          = "P16_BIGLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY"
PHASE_DRY       = "P16_BIGLOTTO_REMAINING_STRATEGIES_DRY_RUN"
PHASE_REHEARSAL = "P16_BIGLOTTO_REMAINING_STRATEGIES_TEMP_REHEARSAL"
PHASE_APPLY     = "P16_BIGLOTTO_REMAINING_STRATEGIES_PRODUCTION_APPLY"
PHASE_DECISION  = "P16_BIGLOTTO_REMAINING_STRATEGIES_APPLY_DECISION"

STRATEGY_IDS    = ["biglotto_triple_strike", "biglotto_deviation_2bet"]

S_READY     = "READY"
S_NO_HIST   = "BLOCKED_INSUFFICIENT_HISTORY"
S_NO_PAY    = "BLOCKED_NO_PREDICTION_PAYLOAD"
S_PARSE_ERR = "BLOCKED_DRAW_PARSE_ERROR"
S_DUPLICATE = "BLOCKED_DUPLICATE_REPLAY_ROW"
S_NO_RUN    = "BLOCKED_NO_STRATEGY_RUNNER"


# ── DB helpers ─────────────────────────────────────────────────────────────────

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
            """
            SELECT strategy_id || '|' || target_draw
            FROM strategy_prediction_replays
            WHERE strategy_id = ? AND lottery_type = ?
            """,
            (strategy_id, LOTTERY_TYPE),
        ).fetchall()
        return {r[0] for r in rows}
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


def _assert_not_prod(db: Path) -> None:
    prod = _PROD_DB.resolve()
    if db.resolve() == prod:
        raise RuntimeError(
            "SAFETY STOP: refusing to write to production DB in rehearsal mode.\n"
            f"  db={db}\nUse --allow-production for explicit production write."
        )


def _provenance_hash(strategy_id: str, draw_number: str, predicted: list[int]) -> str:
    raw = f"{strategy_id}:{draw_number}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── draw loading ───────────────────────────────────────────────────────────────

def _load_biglotto_draws(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT draw, date, numbers, special
            FROM draws
            WHERE lottery_type = 'BIG_LOTTO'
            ORDER BY CAST(draw AS INTEGER) ASC
            """
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers)
            draws.append({
                "draw":    draw,
                "date":    date,
                "numbers": [int(n) for n in nums],
                "special": int(special) if special is not None else None,
            })
        except Exception:
            pass
    return draws


# ── candidate generation ───────────────────────────────────────────────────────

def generate_candidates(
    db_path: Path,
    strategy_ids: list[str] | None = None,
) -> list[dict]:
    """
    Generate prediction candidates for each strategy over the latest 1500 draws.
    Uses real adapter from registry; actual_numbers from DB.
    No DB writes.
    """
    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]

    if strategy_ids is None:
        strategy_ids = STRATEGY_IDS

    all_draws = _load_biglotto_draws(db_path)
    total = len(all_draws)
    if total < 2:
        return []

    available    = min(total, TARGET_WINDOW)
    window_draws = all_draws[-available:]

    candidates: list[dict] = []

    for strategy_id in strategy_ids:
        try:
            adapter = get_adapter(strategy_id)
        except Exception as exc:
            candidates.append(_blocked_strategy_entry(
                strategy_id, "", "BLOCKED_ADAPTER_NOT_FOUND", str(exc)
            ))
            continue

        strategy_name = adapter.meta.strategy_name
        min_hist      = adapter.meta.min_history
        existing_keys = _existing_keys(db_path, strategy_id)

        for draw_row in window_draws:
            draw_number = draw_row["draw"]
            draw_date   = draw_row["date"]

            draw_global_idx = all_draws.index(draw_row)
            history = all_draws[:draw_global_idx]

            # parse actual
            try:
                actual_numbers = list(draw_row["numbers"])
                actual_special = draw_row["special"]
            except Exception as exc:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "draw_number": draw_number, "draw_date": draw_date,
                    "prediction_status": S_PARSE_ERR,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": None, "actual_special": None,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "source_trace": f"parse_error:{exc}",
                    "provenance_hash": None,
                    "would_insert": False, "counts_as_success": False,
                })
                continue

            # duplicate check
            dedup_key = f"{strategy_id}|{draw_number}"
            if dedup_key in existing_keys:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "draw_number": draw_number, "draw_date": draw_date,
                    "prediction_status": S_DUPLICATE,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "source_trace": "duplicate_in_production_table",
                    "provenance_hash": None,
                    "would_insert": False, "counts_as_success": False,
                })
                continue

            # history sufficiency
            if len(history) < min_hist:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "draw_number": draw_number, "draw_date": draw_date,
                    "prediction_status": S_NO_HIST,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "source_trace": f"need={min_hist},have={len(history)}",
                    "provenance_hash": None,
                    "would_insert": False, "counts_as_success": False,
                })
                continue

            # call adapter
            try:
                pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
            except Exception as exc:
                ename  = type(exc).__name__
                status = S_NO_RUN if ("Lifecycle" in ename or "Binding" in ename) else S_NO_PAY
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "draw_number": draw_number, "draw_date": draw_date,
                    "prediction_status": status,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "source_trace": f"{ename}:{exc}",
                    "provenance_hash": None,
                    "would_insert": False, "counts_as_success": False,
                })
                continue

            if not pred_numbers or len(pred_numbers) != 6:
                candidates.append({
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE,
                    "draw_number": draw_number, "draw_date": draw_date,
                    "prediction_status": S_NO_PAY,
                    "predicted_numbers": pred_numbers, "predicted_special": pred_special,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "source_trace": f"bad_pred_len={len(pred_numbers) if pred_numbers else 0}",
                    "provenance_hash": None,
                    "would_insert": False, "counts_as_success": False,
                })
                continue

            # compute hit
            hit_nums   = sorted(set(pred_numbers) & set(actual_numbers))
            hit_count  = len(hit_nums)
            special_hit = (
                bool(pred_special == actual_special)
                if pred_special is not None and actual_special is not None
                else False
            )
            p_hash = _provenance_hash(strategy_id, draw_number, list(pred_numbers))

            history_cutoff = all_draws[draw_global_idx - 1]["draw"] if draw_global_idx > 0 else None

            candidates.append({
                "strategy_id":      strategy_id,
                "strategy_name":    strategy_name,
                "strategy_version": getattr(adapter.meta, "strategy_version", "v0.1"),
                "lottery_type":     LOTTERY_TYPE,
                "draw_number":      draw_number,
                "draw_date":        draw_date,
                "history_cutoff":   history_cutoff,
                "prediction_status": S_READY,
                "predicted_numbers": sorted(pred_numbers),
                "predicted_special": pred_special,
                "actual_numbers":    sorted(actual_numbers),
                "actual_special":    actual_special,
                "hit_numbers":       hit_nums,
                "hit_count":         hit_count,
                "special_hit":       special_hit,
                "source_trace":      f"{strategy_id}:get_one_bet:hist={len(history)}",
                "provenance_hash":   p_hash,
                "would_insert":      True,
                "counts_as_success": False,
            })

    return candidates


def _blocked_strategy_entry(
    strategy_id: str, strategy_name: str, status: str, trace: str
) -> dict:
    return {
        "strategy_id": strategy_id, "strategy_name": strategy_name,
        "lottery_type": LOTTERY_TYPE,
        "draw_number": None, "draw_date": None,
        "prediction_status": status,
        "predicted_numbers": None, "predicted_special": None,
        "actual_numbers": None, "actual_special": None,
        "hit_numbers": None, "hit_count": None, "special_hit": None,
        "source_trace": trace,
        "provenance_hash": None,
        "would_insert": False, "counts_as_success": False,
    }


def _summarize(candidates: list[dict]) -> dict:
    by_strategy: dict[str, dict] = {}
    total_ready = total_blocked = total_dup = fake_success = 0

    for c in candidates:
        sid = c["strategy_id"] or "UNKNOWN"
        if sid not in by_strategy:
            by_strategy[sid] = {"ready": 0, "blocked": 0, "duplicate": 0, "by_status": {}}
        s = c["prediction_status"]
        by_strategy[sid]["by_status"][s] = by_strategy[sid]["by_status"].get(s, 0) + 1
        if s == S_READY:
            by_strategy[sid]["ready"] += 1
            total_ready += 1
        else:
            by_strategy[sid]["blocked"] += 1
            total_blocked += 1
        if s == S_DUPLICATE:
            by_strategy[sid]["duplicate"] += 1
            total_dup += 1
        if c.get("counts_as_success"):
            fake_success += 1

    strategies = []
    for sid, info in by_strategy.items():
        strategies.append({
            "strategy_id":       sid,
            "ready":             info["ready"],
            "blocked":           info["blocked"],
            "duplicate_count":   info["duplicate"],
            "by_status":         info["by_status"],
        })

    return {
        "strategies":              strategies,
        "generated_candidates":    len(candidates),
        "ready_candidates":        total_ready,
        "blocked_candidates":      total_blocked,
        "duplicate_existing_count": total_dup,
        "planned_insert_count":    total_ready,
        "fake_success_count":      fake_success,
    }


# ── dry-run ────────────────────────────────────────────────────────────────────

def run_dry_run(
    db_path: Path,
    json_out: Path | None = None,
) -> dict:
    if json_out is None:
        json_out = _OUT_DIR / "p16_biglotto_remaining_strategies_dry_run_20260520.json"

    rows_before = _row_count(db_path)

    candidates = generate_candidates(db_path)

    # Mark all as dry-run (would_insert=False for output; already set in generator for dups)
    for c in candidates:
        c["would_insert"] = False
        c["counts_as_success"] = False

    summary = _summarize(candidates)

    result = {
        "phase":                   PHASE_DRY,
        "generated_at":            datetime.now(timezone.utc).isoformat(),
        "production_apply":        False,
        "dry_run_only":            True,
        "production_rows_before":  rows_before,
        "lottery_type":            LOTTERY_TYPE,
        "target_draw_window":      TARGET_WINDOW,
        **summary,
    }

    _write_json(result, json_out)
    return result


# ── temp rehearsal: apply ──────────────────────────────────────────────────────

def apply_rehearsal(
    db: Path,
    candidates: list[dict],
    apply_id: str,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before rehearsal apply, "
            f"got {rows_before}"
        )

    now_ts   = datetime.now(timezone.utc).isoformat()
    inserted = dupes = errors = 0

    conn = sqlite3.connect(str(db))
    try:
        for sid in STRATEGY_IDS:
            existing = _existing_keys(db, sid)
            for c in candidates:
                if c["strategy_id"] != sid:
                    continue
                if c["prediction_status"] != S_READY:
                    continue
                dedup_key = f"{sid}|{c['draw_number']}"
                if dedup_key in existing:
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
                            LOTTERY_TYPE, c["draw_number"], c["draw_date"],
                            sid, c["strategy_name"], c.get("strategy_version", "v0.1"),
                            c.get("history_cutoff"), "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c.get("predicted_special"),
                            json.dumps(c["actual_numbers"]), c.get("actual_special"),
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
                            now_ts, TRUTH_LEVEL, apply_id, SOURCE,
                            c["provenance_hash"], 0,
                        ),
                    )
                    existing.add(dedup_key)
                    inserted += 1
                except Exception as exc:
                    print(f"[P16] insert error {c['draw_number']}: {exc}", file=sys.stderr)
                    errors += 1
        conn.commit()
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "mode":                  "temp_rehearsal_apply",
        "controlled_apply_id":   apply_id,
        "rows_before":           rows_before,
        "rows_after":            rows_after,
        "inserted_count":        inserted,
        "duplicate_count":       dupes,
        "error_count":           errors,
    }
    if json_out:
        _write_json(result, json_out)
    return result


# ── temp rehearsal: rollback ───────────────────────────────────────────────────

def rollback_rehearsal(
    db: Path,
    apply_id: str,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db)

    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before rollback, "
            f"got {rows_before}"
        )

    conn = sqlite3.connect(str(db))
    try:
        deleted = conn.execute(
            "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (apply_id,),
        ).rowcount
        conn.commit()
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "mode":                   "rollback",
        "controlled_apply_id":    apply_id,
        "rows_before":            rows_before,
        "rollback_deleted_count": deleted,
        "rows_after_rollback":    rows_after,
    }
    if json_out:
        _write_json(result, json_out)
    return result


# ── full temp rehearsal (apply + rerun + rollback) ─────────────────────────────

def full_rehearsal(
    db: Path,
    candidates: list[dict],
    apply_id: str,
    initial_rows: int,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db)
    summary = _summarize(candidates)
    planned = summary["planned_insert_count"]

    print(f"[P16] Rehearsal round 1 (apply) …")
    r1 = apply_rehearsal(db, candidates, apply_id, initial_rows)
    print(f"[P16] R1: inserted={r1['inserted_count']} dupes={r1['duplicate_count']} "
          f"rows={r1['rows_after']}")

    rows_after_r1 = r1["rows_after"]

    print(f"[P16] Rehearsal round 2 (idempotency rerun) …")
    r2 = apply_rehearsal(db, candidates, apply_id, rows_after_r1)
    print(f"[P16] R2: inserted={r2['inserted_count']} dupes={r2['duplicate_count']}")

    print(f"[P16] Rehearsal rollback …")
    rb = rollback_rehearsal(db, apply_id, rows_after_r1)
    print(f"[P16] Rollback: deleted={rb['rollback_deleted_count']} rows={rb['rows_after_rollback']}")

    rows_final = rb["rows_after_rollback"]

    idempotency_pass = r2["inserted_count"] == 0 and r2["duplicate_count"] == r1["inserted_count"]
    rollback_pass    = rb["rollback_deleted_count"] == r1["inserted_count"] and rows_final == initial_rows

    classification = _classify_rehearsal(r1, r2, rb, initial_rows, planned)

    result = {
        "phase":                   PHASE_REHEARSAL,
        "generated_at":            datetime.now(timezone.utc).isoformat(),
        "controlled_apply_id":     apply_id,
        "initial_rows":            initial_rows,
        "planned_insert_count":    planned,
        "temp_applied_rows":       rows_after_r1,
        "r1_inserted_count":       r1["inserted_count"],
        "r1_duplicate_count":      r1["duplicate_count"],
        "r2_inserted_count":       r2["inserted_count"],
        "r2_duplicate_count":      r2["duplicate_count"],
        "rollback_deleted_count":  rb["rollback_deleted_count"],
        "rows_after_rollback":     rows_final,
        "idempotency_pass":        idempotency_pass,
        "rollback_pass":           rollback_pass,
        "final_classification":    classification,
    }
    if json_out:
        _write_json(result, json_out)
    return result


def _classify_rehearsal(
    r1: dict, r2: dict, rb: dict, initial: int, planned: int
) -> str:
    if r1["error_count"] > 0:
        return f"P16_BLOCKED_BY_TEMP_REHEARSAL_FAILURE_errors={r1['error_count']}"
    if r2["inserted_count"] != 0:
        return f"P16_BLOCKED_BY_IDEMPOTENCY_FAILURE_r2_inserted={r2['inserted_count']}"
    if rb["rollback_deleted_count"] != r1["inserted_count"]:
        return f"P16_BLOCKED_BY_ROLLBACK_FAILURE_deleted={rb['rollback_deleted_count']}"
    if rb["rows_after_rollback"] != initial:
        return f"P16_BLOCKED_BY_ROLLBACK_ROW_MISMATCH_after={rb['rows_after_rollback']}"
    return "P16_TEMP_REHEARSAL_PASS"


# ── production apply ───────────────────────────────────────────────────────────

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
            f"SAFETY STOP: expected {expected_rows_before} rows before apply, "
            f"got {rows_before}"
        )

    now_ts   = datetime.now(timezone.utc).isoformat()
    inserted = dupes = errors = 0

    conn = sqlite3.connect(str(db))
    try:
        for sid in STRATEGY_IDS:
            existing = _existing_keys(db, sid)
            for c in candidates:
                if c["strategy_id"] != sid:
                    continue
                if c["prediction_status"] != S_READY:
                    continue
                dedup_key = f"{sid}|{c['draw_number']}"
                if dedup_key in existing:
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
                            LOTTERY_TYPE, c["draw_number"], c["draw_date"],
                            sid, c["strategy_name"], c.get("strategy_version", "v0.1"),
                            c.get("history_cutoff"), "PREDICTED",
                            json.dumps(c["predicted_numbers"]), c.get("predicted_special"),
                            json.dumps(c["actual_numbers"]), c.get("actual_special"),
                            json.dumps(c["hit_numbers"]), c["hit_count"],
                            1 if c["special_hit"] else 0,
                            now_ts, TRUTH_LEVEL, APPLY_ID, SOURCE,
                            c["provenance_hash"], 0,
                        ),
                    )
                    existing.add(dedup_key)
                    inserted += 1
                except Exception as exc:
                    print(f"[P16] insert error {c['draw_number']}: {exc}", file=sys.stderr)
                    errors += 1
        conn.commit()
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                  PHASE_APPLY,
        "generated_at":           datetime.now(timezone.utc).isoformat(),
        "controlled_apply_id":    APPLY_ID,
        "rows_before":            rows_before,
        "rows_after":             rows_after,
        "inserted_count":         inserted,
        "duplicate_count":        dupes,
        "error_count":            errors,
        "final_classification":   "P16_PRODUCTION_APPLY_COMPLETE" if errors == 0
                                  else f"P16_BLOCKED_BY_APPLY_FAILURE_errors={errors}",
    }
    if json_out:
        _write_json(result, json_out)
    return result


def rollback_production(
    db: Path,
    apply_id: str,
    expected_rows_before: int,
    *,
    json_out: Path | None = None,
) -> dict:
    rows_before = _row_count(db)
    if rows_before != expected_rows_before:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows_before} rows before rollback, "
            f"got {rows_before}"
        )

    conn = sqlite3.connect(str(db))
    try:
        deleted = conn.execute(
            "DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (apply_id,),
        ).rowcount
        conn.commit()
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "mode":                   "production_rollback",
        "controlled_apply_id":    apply_id,
        "rows_before":            rows_before,
        "rollback_deleted_count": deleted,
        "rows_after_rollback":    rows_after,
    }
    if json_out:
        _write_json(result, json_out)
    return result


# ── utilities ──────────────────────────────────────────────────────────────────

def _write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P16] written → {path}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P16 Big Lotto remaining strategies backfill")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run",        action="store_true", default=True)
    mode.add_argument("--temp-rehearsal", action="store_true")
    mode.add_argument("--apply",          action="store_true")
    mode.add_argument("--rollback",       action="store_true")

    parser.add_argument("--db",              default=str(_PROD_DB))
    parser.add_argument("--backup",          default=None)
    parser.add_argument("--json-out",        default=None)
    parser.add_argument("--expected-rows",   type=int, default=1960)
    parser.add_argument(
        "--controlled-apply-id", default=APPLY_ID,
    )
    parser.add_argument(
        "--allow-production", action="store_true", default=False,
        help="Required to write to production DB with --apply.",
    )
    args = parser.parse_args()

    db      = Path(args.db)
    apply_id = args.controlled_apply_id

    # Resolve output path
    if args.json_out:
        json_out = Path(args.json_out)
    else:
        json_out = None

    if args.temp_rehearsal:
        _assert_not_prod(db)
        print(f"[P16] temp rehearsal on {db}")
        candidates = generate_candidates(_PROD_DB)  # always generate from prod
        summary    = _summarize(candidates)
        print(f"[P16] Generated {len(candidates)} candidates, "
              f"planned_insert={summary['planned_insert_count']}")

        out = _OUT_DIR / "p16_biglotto_remaining_strategies_tempdb_rehearsal_20260520.json"
        if json_out:
            out = json_out

        result = full_rehearsal(db, candidates, apply_id, args.expected_rows, json_out=out)
        print(f"[P16] classification: {result['final_classification']}")

    elif args.apply:
        if not args.allow_production:
            print(
                "[P16] ERROR: --apply requires --allow-production.\n"
                "  Production DB write is blocked without explicit authorization.",
                file=sys.stderr,
            )
            sys.exit(1)

        prod_rows = _row_count(_PROD_DB)
        if prod_rows != args.expected_rows:
            print(
                f"[P16] SAFETY STOP: production rows={prod_rows}, expected={args.expected_rows}",
                file=sys.stderr,
            )
            sys.exit(1)

        if args.backup:
            shutil.copy2(str(_PROD_DB), args.backup)
            print(f"[P16] backup → {args.backup}")

        print(f"[P16] Generating candidates …")
        candidates = generate_candidates(_PROD_DB)
        summary    = _summarize(candidates)
        print(f"[P16] planned_insert={summary['planned_insert_count']}")

        out = _OUT_DIR / "p16_biglotto_remaining_strategies_production_apply_20260520.json"
        if json_out:
            out = json_out

        result = apply_production(_PROD_DB, candidates, args.expected_rows, json_out=out)
        print(f"[P16] classification: {result['final_classification']}")
        print(f"[P16] inserted={result['inserted_count']} dupes={result['duplicate_count']} "
              f"rows_after={result['rows_after']}")

    elif args.rollback:
        if args.allow_production:
            target = db
        else:
            _assert_not_prod(db)
            target = db

        print(f"[P16] rollback controlled_apply_id={apply_id} on {target}")
        out = json_out or Path("/tmp/p16_rollback.json")
        result = rollback_rehearsal(target, apply_id, args.expected_rows, json_out=out)
        print(f"[P16] deleted={result['rollback_deleted_count']} "
              f"rows_after={result['rows_after_rollback']}")

    else:
        # dry-run (default)
        out = _OUT_DIR / "p16_biglotto_remaining_strategies_dry_run_20260520.json"
        if json_out:
            out = json_out
        print(f"[P16] dry-run on {db}")
        result = run_dry_run(db, json_out=out)
        summary = result
        print(f"[P16] generated={summary['generated_candidates']} "
              f"ready={summary['ready_candidates']} "
              f"blocked={summary['blocked_candidates']} "
              f"planned_insert={summary['planned_insert_count']}")


if __name__ == "__main__":
    main()
