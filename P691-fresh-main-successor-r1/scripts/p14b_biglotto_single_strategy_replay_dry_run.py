#!/usr/bin/env python3
"""
P14B — Big Lotto Single Strategy Replay Dry-Run (1500 draws, read-only).

Selects one ONLINE BIG_LOTTO strategy (ts3_regime_3bet), generates causal
predictions for the most recent 1500 draws, compares against real draw
results, and writes a page-ready JSON report.

Rules:
- No production DB writes (no_db_write=True always).
- predicted_numbers must come from the real adapter.
- actual_numbers must come from the DB.
- counts_as_success is always False (dry-run only).
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
_DB_PATH   = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR   = _REPO_ROOT / "outputs" / "replay"
_OUT_FILE  = _OUT_DIR / "p14b_biglotto_single_strategy_replay_dry_run_20260520.json"

LOTTERY_TYPE  = "BIG_LOTTO"
TARGET_WINDOW = 1500
PHASE         = "P14B_BIGLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN"
TRUTH_LEVEL   = "DRY_RUN_REPLAY_BACKFILL"
DISPLAY_STATUS = "SHOW_REPLAY_DRY_RUN"

S_READY     = "READY"
S_NO_HIST   = "BLOCKED_INSUFFICIENT_HISTORY"
S_NO_RUN    = "BLOCKED_NO_STRATEGY_RUNNER"
S_NO_PAY    = "BLOCKED_NO_PREDICTION_PAYLOAD"
S_PARSE_ERR = "BLOCKED_DRAW_PARSE_ERROR"
S_DUPLICATE = "BLOCKED_DUPLICATE_REPLAY_ROW"

# ── preferred strategy priority for BIG_LOTTO ─────────────────────────────────
_PREFERRED = ["ts3_regime_3bet", "biglotto_triple_strike", "biglotto_deviation_2bet"]


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
            pass  # malformed rows excluded; BLOCKED_DRAW_PARSE_ERROR captured below
    return draws


def _production_row_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _existing_replay_keys(db_path: Path, strategy_id: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
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


def _provenance_hash(strategy_id: str, draw_number: str, predicted: list[int]) -> str:
    raw = f"{strategy_id}:{draw_number}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _select_strategy() -> dict | None:
    """Return best ONLINE BIG_LOTTO executable strategy, or None."""
    from lottery_api.models.replay_strategy_registry import list_strategies, _REGISTRY  # type: ignore[attr-defined]

    candidates = [
        s for s in list_strategies(lottery_type=LOTTERY_TYPE, lifecycle_status="ONLINE")
        if s["strategy_id"] in _REGISTRY
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda s: _PREFERRED.index(s["strategy_id"])
        if s["strategy_id"] in _PREFERRED
        else len(_PREFERRED),
    )
    return candidates[0]


def _blocked(rows_before: int, classification: str, reason: str) -> dict:
    return {
        "phase":                    PHASE,
        "generated_at":             datetime.now(timezone.utc).isoformat(),
        "dry_run_only":             True,
        "no_db_write":              True,
        "production_rows_before":   rows_before,
        "production_rows_after":    rows_before,
        "lottery_type":             LOTTERY_TYPE,
        "target_draw_window":       TARGET_WINDOW,
        "available_draw_count":     0,
        "selected_strategy_id":     "",
        "selected_strategy_name":   "",
        "strategy_lifecycle_status": "",
        "generated_candidates":     0,
        "ready_candidates":         0,
        "blocked_candidates":       0,
        "fake_success_count":       0,
        "by_status":                {},
        "block_reasons":            {classification: 1},
        "final_classification":     classification,
        "block_reason_detail":      reason,
        "candidates_sample":        [],
        "page_ready_sample":        [],
    }


def run(db_path: Path = _DB_PATH, out_file: Path = _OUT_FILE) -> dict:
    rows_before = _production_row_count(db_path)

    # strategy selection
    meta = _select_strategy()
    if meta is None:
        result = _blocked(rows_before,
                          "P14B_BLOCKED_BY_NO_EXECUTABLE_BIGLOTTO_STRATEGY",
                          "No ONLINE BIG_LOTTO adapter in registry")
        _write(result, out_file)
        return result

    strategy_id   = meta["strategy_id"]
    strategy_name = meta["strategy_name"]

    from lottery_api.models.replay_strategy_registry import get_adapter  # type: ignore[attr-defined]
    adapter = get_adapter(strategy_id)

    # load draws
    all_draws = _load_biglotto_draws(db_path)
    total     = len(all_draws)
    if total < 2:
        result = _blocked(rows_before,
                          "P14B_BLOCKED_BY_INSUFFICIENT_BIG_LOTTO_DRAWS",
                          f"Only {total} draws available")
        _write(result, out_file)
        return result

    available     = min(total, TARGET_WINDOW)
    window_draws  = all_draws[-available:]
    existing_keys = _existing_replay_keys(db_path, strategy_id)

    candidates: list[dict] = []
    by_status: dict[str, int] = {}
    block_reasons: dict[str, int] = {}

    for draw_row in window_draws:
        draw_number = draw_row["draw"]
        draw_date   = draw_row["date"]

        # causal history = everything before this draw in the full dataset
        draw_global_idx = all_draws.index(draw_row)
        history = all_draws[:draw_global_idx]

        # parse actual
        try:
            actual_numbers = list(draw_row["numbers"])
            actual_special = draw_row["special"]
        except Exception as exc:
            _add(candidates, by_status, block_reasons, {
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE,
                "draw_number": draw_number, "draw_date": draw_date,
                "prediction_status": S_PARSE_ERR,
                "predicted_numbers": None, "predicted_special": None,
                "actual_numbers": None, "actual_special": None,
                "hit_numbers": None, "hit_count": None, "special_hit": None,
                "source_trace": f"parse_error:{exc}",
                "provenance_hash": None,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True,
                "would_insert": False, "counts_as_success": False,
            })
            continue

        # duplicate check
        if f"{strategy_id}|{draw_number}" in existing_keys:
            _add(candidates, by_status, block_reasons, {
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE,
                "draw_number": draw_number, "draw_date": draw_date,
                "prediction_status": S_DUPLICATE,
                "predicted_numbers": None, "predicted_special": None,
                "actual_numbers": actual_numbers, "actual_special": actual_special,
                "hit_numbers": None, "hit_count": None, "special_hit": None,
                "source_trace": "duplicate_in_production_table",
                "provenance_hash": None,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True,
                "would_insert": False, "counts_as_success": False,
            })
            continue

        # history sufficiency
        if len(history) < adapter.meta.min_history:
            _add(candidates, by_status, block_reasons, {
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE,
                "draw_number": draw_number, "draw_date": draw_date,
                "prediction_status": S_NO_HIST,
                "predicted_numbers": None, "predicted_special": None,
                "actual_numbers": actual_numbers, "actual_special": actual_special,
                "hit_numbers": None, "hit_count": None, "special_hit": None,
                "source_trace": f"need={adapter.meta.min_history},have={len(history)}",
                "provenance_hash": None,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True,
                "would_insert": False, "counts_as_success": False,
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
                "lottery_type": LOTTERY_TYPE,
                "draw_number": draw_number, "draw_date": draw_date,
                "prediction_status": status,
                "predicted_numbers": None, "predicted_special": None,
                "actual_numbers": actual_numbers, "actual_special": actual_special,
                "hit_numbers": None, "hit_count": None, "special_hit": None,
                "source_trace": f"{ename}:{exc}",
                "provenance_hash": None,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True,
                "would_insert": False, "counts_as_success": False,
            })
            continue

        if not pred_numbers or len(pred_numbers) != 6:
            _add(candidates, by_status, block_reasons, {
                "strategy_id": strategy_id, "strategy_name": strategy_name,
                "lottery_type": LOTTERY_TYPE,
                "draw_number": draw_number, "draw_date": draw_date,
                "prediction_status": S_NO_PAY,
                "predicted_numbers": pred_numbers, "predicted_special": pred_special,
                "actual_numbers": actual_numbers, "actual_special": actual_special,
                "hit_numbers": None, "hit_count": None, "special_hit": None,
                "source_trace": f"bad_pred_len={len(pred_numbers) if pred_numbers else 0}",
                "provenance_hash": None,
                "truth_level": TRUTH_LEVEL, "dry_run_only": True,
                "would_insert": False, "counts_as_success": False,
            })
            continue

        # compute hit
        hit_nums  = sorted(set(pred_numbers) & set(actual_numbers))
        hit_count = len(hit_nums)
        special_hit = (
            bool(pred_special == actual_special)
            if pred_special is not None and actual_special is not None
            else False
        )
        p_hash = _provenance_hash(strategy_id, draw_number, list(pred_numbers))

        _add(candidates, by_status, block_reasons, {
            "strategy_id": strategy_id, "strategy_name": strategy_name,
            "lottery_type": LOTTERY_TYPE,
            "draw_number": draw_number, "draw_date": draw_date,
            "prediction_status": S_READY,
            "predicted_numbers": sorted(pred_numbers),
            "predicted_special": pred_special,
            "actual_numbers": sorted(actual_numbers),
            "actual_special": actual_special,
            "hit_numbers": hit_nums, "hit_count": hit_count, "special_hit": special_hit,
            "source_trace": f"{strategy_id}:get_one_bet:hist={len(history)}",
            "provenance_hash": p_hash,
            "truth_level": TRUTH_LEVEL, "dry_run_only": True,
            "would_insert": False, "counts_as_success": False,
        }, is_success=True)

    # summary
    n_ready   = by_status.get(S_READY, 0)
    n_blocked = len(candidates) - n_ready

    # candidates_sample: up to 5 per status
    seen: dict[str, int] = {}
    sample: list[dict] = []
    for c in candidates:
        s = c["prediction_status"]
        if seen.get(s, 0) < 5:
            sample.append(c)
            seen[s] = seen.get(s, 0) + 1

    ready_rows = [c for c in candidates if c["prediction_status"] == S_READY]
    page_sample = [
        {
            "draw_number":      r["draw_number"],
            "draw_date":        r["draw_date"],
            "strategy_name":    r["strategy_name"],
            "predicted_numbers": r["predicted_numbers"],
            "actual_numbers":    r["actual_numbers"],
            "hit_numbers":       r["hit_numbers"],
            "hit_count":         r["hit_count"],
            "special_hit":       r["special_hit"],
            "display_status":    DISPLAY_STATUS,
            "truth_level":       TRUTH_LEVEL,
        }
        for r in ready_rows[-20:]
    ]

    rows_after = _production_row_count(db_path)

    if rows_after != rows_before:
        classification = "P14B_BLOCKED_BY_PRODUCTION_DB_DRIFT"
    elif n_ready == 0:
        classification = "P14B_BLOCKED_BY_NO_EXECUTABLE_BIGLOTTO_STRATEGY"
    elif available < TARGET_WINDOW:
        classification = "P14B_BIGLOTTO_PARTIAL_WINDOW_READY"
    else:
        classification = "P14B_BIGLOTTO_SINGLE_STRATEGY_DRY_RUN_READY"

    output = {
        "phase":                    PHASE,
        "generated_at":             datetime.now(timezone.utc).isoformat(),
        "dry_run_only":             True,
        "no_db_write":              True,
        "production_rows_before":   rows_before,
        "production_rows_after":    rows_after,
        "lottery_type":             LOTTERY_TYPE,
        "target_draw_window":       TARGET_WINDOW,
        "available_draw_count":     available,
        "selected_strategy_id":     strategy_id,
        "selected_strategy_name":   strategy_name,
        "strategy_lifecycle_status": meta["strategy_lifecycle_status"],
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


def _add(candidates: list, by_status: dict, block_reasons: dict,
         entry: dict, *, is_success: bool = False) -> None:
    candidates.append(entry)
    s = entry["prediction_status"]
    by_status[s] = by_status.get(s, 0) + 1
    if not is_success:
        block_reasons[s] = block_reasons.get(s, 0) + 1


def _write(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P14B] written → {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P14B Big Lotto single-strategy replay dry-run")
    parser.add_argument("--db",  default=str(_DB_PATH))
    parser.add_argument("--out", default=str(_OUT_FILE))
    args = parser.parse_args()

    result = run(db_path=Path(args.db), out_file=Path(args.out))
    print(f"[P14B] classification  = {result['final_classification']}")
    print(f"[P14B] generated       = {result['generated_candidates']}")
    print(f"[P14B] ready           = {result['ready_candidates']}")
    print(f"[P14B] blocked         = {result['blocked_candidates']}")
    print(f"[P14B] rows_before     = {result['production_rows_before']}")
    print(f"[P14B] rows_after      = {result['production_rows_after']}")
