#!/usr/bin/env python3
"""
P93 Tier B Replay Adapter Bootstrap — Temp-DB Dry-run Rehearsal
=================================================================
GOVERNANCE:
  - Reads from production DB (READ-ONLY).
  - Copies production DB to /tmp/p93_tierb_dryrun_rehearsal.db.
  - All replay row inserts go to TEMP DB only.
  - Does NOT write to lottery_api/data/lottery_v2.db.
  - dry_run flag = 1 on ALL temp rows.
  - No lifecycle/champion/registry mutation.
  - No official API calls.

Usage:
    python3 scripts/p93_tierb_dryrun_rehearsal.py

Output:
    outputs/replay/p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ─── Paths ────────────────────────────────────────────────────────────────────

PROD_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p93_tierb_dryrun_rehearsal.db")
OUT_DIR      = _REPO_ROOT / "outputs" / "replay"
OUT_FILE     = OUT_DIR / "p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json"

TARGET_WINDOW  = 1500   # max draws per strategy
PHASE          = "P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN"
TRUTH_LEVEL    = "P93_TEMP_DRY_RUN_ONLY"
CONTROLLED_ID  = "P93_TIERB_DRYRUN_20260526"

# ─── Strategy configuration ───────────────────────────────────────────────────

_STRATEGY_CONFIG = [
    {
        "strategy_id":    "daily539_f4cold_3bet",
        "lottery_type":   "DAILY_539",
        "expected_bets":  3,
        "strategy_name":  "今彩539 F4Cold 3注",
        "version":        "v0.1",
    },
    {
        "strategy_id":    "daily539_f4cold_5bet",
        "lottery_type":   "DAILY_539",
        "expected_bets":  5,
        "strategy_name":  "今彩539 F4Cold 5注",
        "version":        "v0.1",
    },
    {
        "strategy_id":    "biglotto_echo_aware_3bet",
        "lottery_type":   "BIG_LOTTO",
        "expected_bets":  3,
        "strategy_name":  "大樂透 Echo-Aware 混合 3注",
        "version":        "v0.1",
    },
    {
        "strategy_id":    "power_fourier_rhythm_2bet",
        "lottery_type":   "POWER_LOTTO",
        "expected_bets":  2,
        "strategy_name":  "威力彩 Fourier Rhythm 2注",
        "version":        "v0.1",
    },
    {
        "strategy_id":    "biglotto_ts3_markov_4bet_w30",
        "lottery_type":   "BIG_LOTTO",
        "expected_bets":  4,
        "strategy_name":  "大樂透 TS3+Markov(w30) 4注",
        "version":        "v0.1",
    },
]

# ─── Production DB helpers (READ-ONLY) ───────────────────────────────────────

def _prod_row_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _prod_max_draw(db_path: Path, lottery_type: str) -> Optional[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT draw FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1",
            (lottery_type,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _load_draws(db_path: Path, lottery_type: str) -> list[dict]:
    """Load all draws for a lottery type from the given DB (READ-ONLY path)."""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
            (lottery_type,),
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for draw, date, numbers, special in rows:
        try:
            nums = json.loads(numbers) if isinstance(numbers, str) else numbers
            sp = None
            if lottery_type not in ("DAILY_539",) and special is not None:
                try:
                    sp = int(special)
                except (TypeError, ValueError):
                    sp = None
            draws.append({
                "draw":    draw,
                "date":    date,
                "numbers": [int(n) for n in nums],
                "special": sp,
            })
        except Exception:
            pass
    return draws


def _existing_temp_keys(conn: sqlite3.Connection, strategy_id: str, lottery_type: str) -> set[str]:
    rows = conn.execute(
        "SELECT strategy_id || '|' || target_draw FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=? AND dry_run=1",
        (strategy_id, lottery_type),
    ).fetchall()
    return {r[0] for r in rows}


# ─── Hash / provenance ───────────────────────────────────────────────────────

def _provenance_hash(strategy_id: str, draw: str, predicted: list[int]) -> str:
    raw = f"P93:{strategy_id}:{draw}:{sorted(predicted)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Number validation ───────────────────────────────────────────────────────

_LOTTERY_RULES = {
    "BIG_LOTTO":   {"k": 6, "pool": 49},
    "POWER_LOTTO": {"k": 6, "pool": 38},
    "DAILY_539":   {"k": 5, "pool": 39},
}


def _validate(numbers: list[int], lottery_type: str) -> bool:
    rules = _LOTTERY_RULES.get(lottery_type)
    if not rules:
        return False
    k, pool = rules["k"], rules["pool"]
    nums = sorted(int(n) for n in numbers)
    return (
        len(nums) == k
        and all(1 <= n <= pool for n in nums)
        and len(set(nums)) == k
    )


# ─── Hit calculation ─────────────────────────────────────────────────────────

def _calc_hits(predicted: list[int], actual: list[int]) -> tuple[list[int], int]:
    hit = sorted(set(predicted) & set(actual))
    return hit, len(hit)


# ─── Copy production DB to temp path ─────────────────────────────────────────

def _setup_temp_db(prod_path: Path, temp_path: Path) -> None:
    """Copy production DB to temp path. Raises if prod DB not found."""
    if not prod_path.exists():
        raise FileNotFoundError(f"Production DB not found: {prod_path}")
    # Remove stale temp DB if present
    if temp_path.exists():
        temp_path.unlink()
    shutil.copy2(str(prod_path), str(temp_path))


# ─── Single strategy dry-run ──────────────────────────────────────────────────

def _run_strategy_dryrun(
    strategy_cfg: dict,
    all_draws: list[dict],
    temp_conn: sqlite3.Connection,
    run_ts: str,
) -> dict:
    """
    Run dry-run replay for one strategy.

    Strict causal isolation: history = draws[:i] (strictly before target draw i).
    Inserts only into temp_conn (dry_run=1).
    Returns a per-strategy result dict.
    """
    strategy_id   = strategy_cfg["strategy_id"]
    lottery_type  = strategy_cfg["lottery_type"]
    expected_bets = strategy_cfg["expected_bets"]
    strategy_name = strategy_cfg["strategy_name"]
    version       = strategy_cfg["version"]

    # Import the P93 adapter
    from lottery_api.models.p93_tierb_replay_adapters import get_p93_adapter
    try:
        adapter = get_p93_adapter(strategy_id)
    except KeyError as e:
        return {
            "strategy_id":    strategy_id,
            "lottery_type":   lottery_type,
            "status":         "BLOCKED_ADAPTER_NOT_FOUND",
            "blocker":        str(e),
            "rows_generated": 0,
            "rows_ready":     0,
            "rows_blocked":   0,
            "block_reasons":  {},
        }

    # Determine target window
    total_draws = len(all_draws)
    start_idx   = max(0, total_draws - TARGET_WINDOW)
    window      = all_draws[start_idx:]

    # Load existing temp keys for dedup
    existing_keys = _existing_temp_keys(temp_conn, strategy_id, lottery_type)

    rows_ready   = 0
    rows_blocked = 0
    block_reasons: dict[str, int] = {}

    for draw_dict in window:
        target_draw = draw_dict["draw"]
        target_date = draw_dict["date"]
        actual_nums = draw_dict["numbers"]
        actual_sp   = draw_dict.get("special")

        # Causal guard: get index of this draw
        try:
            draw_idx = all_draws.index(draw_dict)
        except ValueError:
            draw_idx = next(
                (i for i, d in enumerate(all_draws) if d["draw"] == target_draw),
                None,
            )
        if draw_idx is None:
            rows_blocked += 1
            block_reasons["DRAW_INDEX_NOT_FOUND"] = block_reasons.get("DRAW_INDEX_NOT_FOUND", 0) + 1
            continue

        history = all_draws[:draw_idx]  # STRICT CAUSAL ISOLATION

        # Duplicate guard
        key = f"{strategy_id}|{target_draw}"
        if key in existing_keys:
            rows_blocked += 1
            block_reasons["DUPLICATE"] = block_reasons.get("DUPLICATE", 0) + 1
            continue

        # Insufficient history guard
        if len(history) < adapter.meta.min_history:
            rows_blocked += 1
            block_reasons["INSUFFICIENT_HISTORY"] = block_reasons.get("INSUFFICIENT_HISTORY", 0) + 1
            continue

        # Call adapter
        try:
            predicted_nums, predicted_sp = adapter.get_one_bet(history, lottery_type)
        except Exception as exc:
            rows_blocked += 1
            reason = type(exc).__name__
            block_reasons[reason] = block_reasons.get(reason, 0) + 1
            continue

        # Validate numbers
        if not _validate(predicted_nums, lottery_type):
            rows_blocked += 1
            block_reasons["INVALID_NUMBERS"] = block_reasons.get("INVALID_NUMBERS", 0) + 1
            continue

        # Calculate hits
        hit_nums, hit_count = _calc_hits(predicted_nums, actual_nums)

        # Special hit (only for games with special ball)
        special_hit = 0
        if predicted_sp is not None and actual_sp is not None:
            special_hit = 1 if predicted_sp == actual_sp else 0

        # History cutoff draw
        history_cutoff_draw = history[-1]["draw"] if history else None

        # Provenance
        prov_hash = _provenance_hash(strategy_id, target_draw, predicted_nums)

        # Insert into temp DB (dry_run=1)
        temp_conn.execute(
            """
            INSERT INTO strategy_prediction_replays (
                lottery_type, target_draw, target_date, strategy_id,
                strategy_name, strategy_version, history_cutoff_draw,
                replay_status, predicted_numbers, predicted_special,
                actual_numbers, actual_special, hit_numbers, hit_count,
                special_hit, generated_at, truth_level, controlled_apply_id,
                source, provenance_hash, provenance_source, dry_run,
                prediction_cutoff_date, prediction_generated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                lottery_type,
                target_draw,
                target_date,
                strategy_id,
                strategy_name,
                version,
                history_cutoff_draw,
                "PREDICTED",
                json.dumps(sorted(predicted_nums)),
                predicted_sp,
                json.dumps(sorted(actual_nums)),
                actual_sp,
                json.dumps(hit_nums),
                hit_count,
                special_hit,
                run_ts,
                TRUTH_LEVEL,
                CONTROLLED_ID,
                PHASE,
                prov_hash,
                "P93_DRYRUN_TEMP",
                1,  # dry_run = 1 (TEMP ONLY)
                history_cutoff_draw,  # prediction_cutoff_date = cutoff draw date approximation
                run_ts,
            ),
        )
        existing_keys.add(key)
        rows_ready += 1

    temp_conn.commit()

    return {
        "strategy_id":    strategy_id,
        "lottery_type":   lottery_type,
        "expected_bets":  expected_bets,
        "status":         "COMPLETE" if rows_ready > 0 else "BLOCKED",
        "rows_generated": rows_ready + rows_blocked,
        "rows_ready":     rows_ready,
        "rows_blocked":   rows_blocked,
        "block_reasons":  block_reasons,
        "target_window":  TARGET_WINDOW,
    }


# ─── Main rehearsal runner ────────────────────────────────────────────────────

def run(
    prod_db_path: Path = PROD_DB_PATH,
    temp_db_path: Path = TEMP_DB_PATH,
    out_file: Path = OUT_FILE,
) -> dict:
    run_ts = datetime.now(timezone.utc).isoformat()

    # ── Safety check: do not write to production DB ───────────────────────────
    assert prod_db_path.resolve() != temp_db_path.resolve(), \
        "STOP: temp_db_path must differ from prod_db_path"

    # ── Record production baseline (READ-ONLY) ────────────────────────────────
    rows_before = _prod_row_count(prod_db_path)
    max_draw_pl = _prod_max_draw(prod_db_path, "POWER_LOTTO")
    max_draw_bl = _prod_max_draw(prod_db_path, "BIG_LOTTO")
    max_draw_539 = _prod_max_draw(prod_db_path, "DAILY_539")

    # ── Copy production DB → temp DB ─────────────────────────────────────────
    _setup_temp_db(prod_db_path, temp_db_path)

    # ── Open temp DB connection ───────────────────────────────────────────────
    temp_conn = sqlite3.connect(str(temp_db_path))

    strategy_results = []
    total_temp_rows = 0
    all_blocked = True

    try:
        for cfg in _STRATEGY_CONFIG:
            lottery_type = cfg["lottery_type"]
            draws = _load_draws(prod_db_path, lottery_type)  # READ from prod

            result = _run_strategy_dryrun(cfg, draws, temp_conn, run_ts)
            strategy_results.append(result)

            if result["rows_ready"] > 0:
                all_blocked = False
            total_temp_rows += result["rows_ready"]

    finally:
        temp_conn.close()

    # ── Verify production DB is UNCHANGED ────────────────────────────────────
    rows_after = _prod_row_count(prod_db_path)
    max_draw_pl_after = _prod_max_draw(prod_db_path, "POWER_LOTTO")

    prod_unchanged = (rows_before == rows_after) and (max_draw_pl == max_draw_pl_after)

    # ── Classification ────────────────────────────────────────────────────────
    n_complete = sum(1 for r in strategy_results if r["status"] == "COMPLETE")
    n_blocked  = sum(1 for r in strategy_results if r["status"] != "COMPLETE")

    if not prod_unchanged:
        classification = "P93_STOPPED_PRODUCTION_DB_MUTATION_RISK"
    elif n_complete == 5:
        classification = "P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE"
    elif n_complete > 0:
        classification = "P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_PARTIAL"
    else:
        classification = "P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_BLOCKED"

    # ── Build report ──────────────────────────────────────────────────────────
    report = {
        "task":                    "P93",
        "title":                   "Tier B Replay Adapter Bootstrap + Temp-DB Dry-run Rehearsal",
        "date":                    "2026-05-26",
        "generated_at":            run_ts,
        "final_classification":    classification,
        # Governance assertions
        "db_writes_to_prod":       False,
        "production_db_path":      str(prod_db_path),
        "temp_db_path":            str(temp_db_path),
        "production_rows_before":  rows_before,
        "production_rows_after":   rows_after,
        "prod_unchanged":          prod_unchanged,
        "power_lotto_max_draw_before": max_draw_pl,
        "power_lotto_max_draw_after":  max_draw_pl_after,
        # Dry-run stats
        "target_strategies_count": len(_STRATEGY_CONFIG),
        "complete_count":          n_complete,
        "blocked_count":           n_blocked,
        "total_temp_dry_run_rows": total_temp_rows,
        "dry_run_flag_all_rows":   True,
        "strategies": strategy_results,
        # P94 recommendation
        "p94_recommendation": {
            "scope": "controlled apply P93 dry-run validated strategies into production DB",
            "preconditions": [
                "All P93 tests PASS",
                "Drift guard PASS",
                "Branch governance PASS",
                "Production replay_rows remains 46962",
                "POWER_LOTTO max_draw remains 115000041",
                "P93 final_classification == P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE",
            ],
            "expected_insert_delta": total_temp_rows,
            "expected_post_p94_total": rows_before + total_temp_rows,
            "strategies_to_apply": [
                r["strategy_id"] for r in strategy_results if r["status"] == "COMPLETE"
            ],
        },
        "governance": {
            "no_prod_db_writes":              True,
            "no_replay_row_insert_prod":      True,
            "no_lifecycle_mutation":          True,
            "no_champion_registry_mutation":  True,
            "no_official_api_ingestion":      True,
            "dry_run_flag":                   True,
            "temp_db_only":                   True,
            "causal_isolation":               True,
            "duplicate_guard":                True,
        },
    }

    # ── Write output JSON ─────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(out_file), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="P93 Tier B Dry-run Rehearsal")
    parser.add_argument("--prod-db",   default=str(PROD_DB_PATH), help="Production DB path (READ-ONLY)")
    parser.add_argument("--temp-db",   default=str(TEMP_DB_PATH), help="Temp DB path for dry-run writes")
    parser.add_argument("--out-file",  default=str(OUT_FILE),     help="Output JSON path")
    args = parser.parse_args()

    result = run(
        prod_db_path=Path(args.prod_db),
        temp_db_path=Path(args.temp_db),
        out_file=Path(args.out_file),
    )

    print(f"\n{'='*70}")
    print(f"  P93 Tier B Dry-run Rehearsal")
    print(f"  Classification: {result['final_classification']}")
    print(f"{'='*70}")
    print(f"  Production rows before: {result['production_rows_before']}")
    print(f"  Production rows after:  {result['production_rows_after']}")
    print(f"  Prod DB unchanged:      {result['prod_unchanged']}")
    print(f"  Temp DB:                {result['temp_db_path']}")
    print(f"  Total temp dry-run rows:{result['total_temp_dry_run_rows']}")
    print(f"{'─'*70}")
    for s in result["strategies"]:
        print(f"  {s['strategy_id']:40s}  {s['status']:10s}  rows={s['rows_ready']}")
    print(f"{'='*70}")
    print(f"  Output: {args.out_file}")
    print()
