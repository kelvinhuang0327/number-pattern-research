#!/usr/bin/env python3
"""
P21 — Daily 539 Replay Dry-Run (both ONLINE strategies, read-only).

Generates causal predictions for both daily539_f4cold and daily539_markov_cold
over the most recent 1500 draws and writes a page-ready JSON report.

DAILY_539 notes:
- 5 main numbers per draw (pool 1-39)
- No special number (predicted_special = None, special_hit = False)
- hit_count = len(predicted_numbers ∩ actual_numbers)
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

_DB_PATH  = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR  = _REPO_ROOT / "outputs" / "replay"
_OUT_FILE = _OUT_DIR / "p21_daily539_replay_dry_run_20260520.json"

LOTTERY_TYPE   = "DAILY_539"
TARGET_WINDOW  = 1500
PHASE          = "P21_DAILY539_REPLAY_DRY_RUN"
TRUTH_LEVEL    = "DRY_RUN_REPLAY_BACKFILL"
DISPLAY_STATUS = "SHOW_REPLAY_DRY_RUN"
STRATEGIES     = ["daily539_f4cold", "daily539_markov_cold"]

S_READY     = "READY"
S_NO_HIST   = "BLOCKED_INSUFFICIENT_HISTORY"
S_NO_RUN    = "BLOCKED_NO_STRATEGY_RUNNER"
S_NO_PAY    = "BLOCKED_NO_PREDICTION_PAYLOAD"
S_PARSE_ERR = "BLOCKED_DRAW_PARSE_ERROR"
S_DUPLICATE = "BLOCKED_DUPLICATE_REPLAY_ROW"


def _load_draws(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws WHERE lottery_type='DAILY_539' ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()
    draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers)
            # DAILY_539 has no special number; treat 0 / empty / None as None
            sp = None
            if special and str(special).strip() not in ("", "0", "None"):
                try:
                    sp = int(special)
                except Exception:
                    sp = None
            draws.append({"draw": draw, "date": date, "numbers": [int(n) for n in nums], "special": sp})
        except Exception:
            pass
    return draws


def _production_row_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


def _existing_keys(db_path: Path, strategy_id: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT strategy_id || '|' || target_draw FROM strategy_prediction_replays WHERE strategy_id=? AND lottery_type=?",
            (strategy_id, LOTTERY_TYPE),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def run(db_path: Path = _DB_PATH, out_file: Path = _OUT_FILE) -> dict:
    run_ts    = datetime.now(timezone.utc).isoformat()
    rows_before = _production_row_count(db_path)

    # Load draws once
    all_draws = _load_draws(db_path)
    total     = len(all_draws)
    available = min(total, TARGET_WINDOW)
    window    = all_draws[-available:]

    from lottery_api.models.replay_strategy_registry import get_adapter, list_strategies, _REGISTRY  # type: ignore[attr-defined]

    # Find executable strategies
    online = [s for s in list_strategies(lottery_type=LOTTERY_TYPE, lifecycle_status="ONLINE") if s["strategy_id"] in _REGISTRY]
    if not online:
        result = {
            "phase": PHASE, "generated_at": run_ts,
            "dry_run_only": True, "no_db_write": True,
            "production_rows_before": rows_before, "production_rows_after": rows_before,
            "lottery_type": LOTTERY_TYPE, "target_draw_window": TARGET_WINDOW,
            "available_draw_count": available, "strategies": [],
            "generated_candidates": 0, "ready_candidates": 0, "blocked_candidates": 0,
            "fake_success_count": 0, "by_status": {}, "block_reasons": {},
            "final_classification": "P21_BLOCKED_BY_NO_EXECUTABLE_DAILY539_STRATEGY",
            "candidates_sample": [], "page_ready_sample": [],
        }
        _write(result, out_file)
        return result

    strategy_ids  = [s["strategy_id"] for s in online]
    candidates: list[dict] = []
    by_status: dict[str, int] = {}
    block_reasons: dict[str, int] = {}

    for strategy_meta in online:
        strategy_id   = strategy_meta["strategy_id"]
        strategy_name = strategy_meta["strategy_name"]
        adapter       = get_adapter(strategy_id)
        min_hist      = adapter.meta.min_history
        existing_keys = _existing_keys(db_path, strategy_id)

        for draw_row in window:
            draw_number = draw_row["draw"]
            draw_date   = draw_row["date"]
            gidx        = all_draws.index(draw_row)
            history     = all_draws[:gidx]

            # parse actual
            actual_numbers = list(draw_row["numbers"])
            actual_special = draw_row["special"]  # None for DAILY_539

            # duplicate check
            if f"{strategy_id}|{draw_number}" in existing_keys:
                _add(candidates, by_status, block_reasons, {
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE, "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": S_DUPLICATE,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": "duplicate_in_production_table", "provenance_hash": None,
                    "truth_level": TRUTH_LEVEL, "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            # history sufficiency
            if len(history) < min_hist:
                _add(candidates, by_status, block_reasons, {
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE, "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": S_NO_HIST,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"need={min_hist},have={len(history)}", "provenance_hash": None,
                    "truth_level": TRUTH_LEVEL, "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            # call adapter
            try:
                pred_numbers, pred_special = adapter.get_one_bet(history, LOTTERY_TYPE)
            except Exception as exc:
                ename  = type(exc).__name__
                status = S_NO_RUN if ("Lifecycle" in ename or "Binding" in ename) else S_NO_PAY
                _add(candidates, by_status, block_reasons, {
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE, "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": status,
                    "predicted_numbers": None, "predicted_special": None,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"{ename}:{exc}", "provenance_hash": None,
                    "truth_level": TRUTH_LEVEL, "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            if not pred_numbers or len(pred_numbers) != 5:
                _add(candidates, by_status, block_reasons, {
                    "strategy_id": strategy_id, "strategy_name": strategy_name,
                    "lottery_type": LOTTERY_TYPE, "target_draw": draw_number, "target_date": draw_date,
                    "prediction_status": S_NO_PAY,
                    "predicted_numbers": pred_numbers, "predicted_special": pred_special,
                    "actual_numbers": actual_numbers, "actual_special": actual_special,
                    "hit_numbers": None, "hit_count": None, "special_hit": None,
                    "prediction_cutoff_date": None, "prediction_generated_at": run_ts,
                    "source_trace": f"bad_pred_len={len(pred_numbers) if pred_numbers else 0}", "provenance_hash": None,
                    "truth_level": TRUTH_LEVEL, "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                })
                continue

            # compute hit (DAILY_539: 5 numbers, no special)
            hit_nums  = sorted(set(pred_numbers) & set(actual_numbers))
            hit_count = len(hit_nums)
            special_hit = False  # DAILY_539 has no special number
            cutoff_date = history[-1]["date"] if history else None
            p_hash = hashlib.sha256(f"{strategy_id}:{draw_number}:{sorted(pred_numbers)}".encode()).hexdigest()[:16]

            _add(candidates, by_status, block_reasons, {
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE, "target_draw": draw_number, "target_date": draw_date,
                "prediction_status": S_READY,
                "predicted_numbers": sorted(pred_numbers), "predicted_special": None,
                "actual_numbers": sorted(actual_numbers), "actual_special": actual_special,
                "hit_numbers": hit_nums, "hit_count": hit_count, "special_hit": special_hit,
                "prediction_cutoff_date": cutoff_date, "prediction_generated_at": run_ts,
                "source_trace": f"{strategy_id}:get_one_bet:hist={len(history)}",
                "provenance_hash": p_hash,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True, "would_insert": False, "counts_as_success": False,
                "_history_cutoff_draw": history[-1]["draw"] if history else None,
                "_strategy_version": adapter.meta.strategy_version,
            }, is_success=True)

    n_ready   = by_status.get(S_READY, 0)
    n_blocked = len(candidates) - n_ready

    # sample
    seen: dict[str, int] = {}
    sample: list[dict] = []
    for c in candidates:
        s = c["prediction_status"]
        if seen.get(s, 0) < 5:
            sample.append(c)
            seen[s] = seen.get(s, 0) + 1

    ready_rows  = [c for c in candidates if c["prediction_status"] == S_READY]
    page_sample = [
        {"target_draw": r["target_draw"], "target_date": r["target_date"],
         "strategy_id": r["strategy_id"], "strategy_name": r["strategy_name"],
         "predicted_numbers": r["predicted_numbers"], "actual_numbers": r["actual_numbers"],
         "hit_numbers": r["hit_numbers"], "hit_count": r["hit_count"],
         "special_hit": r["special_hit"],
         "prediction_cutoff_date": r["prediction_cutoff_date"],
         "prediction_generated_at": r["prediction_generated_at"],
         "display_status": DISPLAY_STATUS, "truth_level": TRUTH_LEVEL}
        for r in ready_rows[-20:]
    ]

    rows_after = _production_row_count(db_path)
    if rows_after != rows_before:
        classification = "P21_BLOCKED_BY_PRODUCTION_DB_DRIFT"
    elif n_ready == 0:
        classification = "P21_BLOCKED_BY_NO_EXECUTABLE_DAILY539_STRATEGY"
    elif available < TARGET_WINDOW:
        classification = "P21_DAILY539_PARTIAL_WINDOW_READY"
    else:
        classification = "P21_DAILY539_DRY_RUN_READY"

    output = {
        "phase":                    PHASE,
        "generated_at":             run_ts,
        "dry_run_only":             True,
        "no_db_write":              True,
        "production_rows_before":   rows_before,
        "production_rows_after":    rows_after,
        "lottery_type":             LOTTERY_TYPE,
        "target_draw_window":       TARGET_WINDOW,
        "available_draw_count":     available,
        "strategies":               strategy_ids,
        "generated_candidates":     len(candidates),
        "ready_candidates":         n_ready,
        "blocked_candidates":       n_blocked,
        "fake_success_count":       0,
        "by_status":                by_status,
        "block_reasons":            block_reasons,
        "final_classification":     classification,
        "candidates_sample":        sample,
        "page_ready_sample":        page_sample,
    }
    _write(output, out_file)
    return output


def _add(candidates, by_status, block_reasons, entry, *, is_success=False):
    candidates.append(entry)
    s = entry["prediction_status"]
    by_status[s] = by_status.get(s, 0) + 1
    if not is_success:
        block_reasons[s] = block_reasons.get(s, 0) + 1


def _write(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P21] written → {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P21 Daily 539 replay dry-run")
    parser.add_argument("--db",  default=str(_DB_PATH))
    parser.add_argument("--out", default=str(_OUT_FILE))
    args = parser.parse_args()
    result = run(db_path=Path(args.db), out_file=Path(args.out))
    print(f"[P21] classification={result['final_classification']}")
    print(f"[P21] strategies={result['strategies']}")
    print(f"[P21] generated={result['generated_candidates']} ready={result['ready_candidates']} blocked={result['blocked_candidates']}")
    print(f"[P21] rows_before={result['production_rows_before']} rows_after={result['production_rows_after']}")
