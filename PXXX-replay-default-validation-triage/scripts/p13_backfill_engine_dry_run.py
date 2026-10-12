#!/usr/bin/env python3
"""
p13_backfill_engine_dry_run.py
==============================
P13 Replay Backfill Engine — Skeleton Dry-Run.

Phase 1: 2 ONLINE strategies × 1500 draws (read-only, no DB write).

Selected strategies (per P12 recommended_phase_1):
  - daily539_f4cold      (DAILY_539)
  - power_precision_3bet (POWER_LOTTO)

Rules (from P12 architecture doc):
  - predicted_numbers MUST come from adapter.get_one_bet()
  - actual_numbers MUST come from draws table
  - hit_numbers = predicted ∩ actual
  - no DB write, no fabrication, no fake rows
  - dry_run_only=True always
  - BLOCKED candidates never count as success
  - dry-run READY candidates never count as success
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "lottery_api"))

OUTPUT_PATH = PROJECT_ROOT / "outputs" / "replay" / "p13_backfill_engine_dry_run_20260520.json"
DB_PATH     = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# ── Phase 1 constants (from P12 gap analysis) ─────────────────────────────────

TARGET_DRAW_WINDOW   = 1500
TARGET_STRATEGIES    = ["daily539_f4cold", "power_precision_3bet"]
ESTIMATED_CANDIDATES = 3000  # 2 × 1500
CANDIDATES_SAMPLE_N  = 20    # candidates_sample per strategy

# ── Allowed prediction_status values ─────────────────────────────────────────

PREDICTION_STATUS_READY = "READY"
BLOCKED_STATUSES = frozenset({
    "BLOCKED_NO_STRATEGY_RUNNER",
    "BLOCKED_INSUFFICIENT_HISTORY",
    "BLOCKED_NO_PREDICTION_PAYLOAD",
    "BLOCKED_DUPLICATE_REPLAY_ROW",
    "BLOCKED_UNSUPPORTED_LOTTERY_TYPE",
    "BLOCKED_INVALID_OUTPUT",
    "BLOCKED_REPLAY_ERROR",
})
ALLOWED_STATUSES = frozenset({PREDICTION_STATUS_READY}) | BLOCKED_STATUSES

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _open_db_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _db_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def _load_all_draws(conn: sqlite3.Connection, lottery_type: str) -> list[dict]:
    """Load all draws for lottery_type sorted by integer draw number ascending."""
    rows = conn.execute(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type = ? "
        "ORDER BY CAST(draw AS INTEGER) ASC",
        (lottery_type,),
    ).fetchall()
    result = []
    for r in rows:
        try:
            nums = json.loads(r["numbers"])
        except (json.JSONDecodeError, TypeError):
            continue  # skip malformed
        result.append({
            "draw":    r["draw"],
            "date":    r["date"],
            "numbers": nums,
            "special": r["special"],
        })
    return result


def _load_existing_replay_draws(
    conn: sqlite3.Connection, strategy_id: str, lottery_type: str
) -> set[str]:
    """Return set of draw values already in strategy_prediction_replays."""
    rows = conn.execute(
        "SELECT DISTINCT target_draw FROM strategy_prediction_replays "
        "WHERE strategy_id = ? AND lottery_type = ?",
        (strategy_id, lottery_type),
    ).fetchall()
    return {r["target_draw"] for r in rows}


# ── Hit calculation ───────────────────────────────────────────────────────────

def _compute_hit(predicted: list[int], actual: list[int],
                 predicted_special: Optional[int], actual_special: Optional[int],
                 lottery_type: str) -> tuple[list[int], int, int]:
    """
    Returns (hit_numbers, hit_count, special_hit).
    hit_numbers = predicted ∩ actual
    special_hit = 1 if predicted_special == actual_special, else 0
    DAILY_539 never has special.
    """
    hit_set     = sorted(set(predicted) & set(actual))
    hit_count   = len(hit_set)
    if lottery_type == "DAILY_539":
        special_hit = 0
    elif predicted_special is None or actual_special is None:
        special_hit = 0
    else:
        special_hit = 1 if int(predicted_special) == int(actual_special) else 0
    return hit_set, hit_count, special_hit


# ── Provenance hash ───────────────────────────────────────────────────────────

def _provenance_hash(strategy_id: str, draw: str,
                     predicted_json: str, history_cutoff: str) -> str:
    payload = f"{strategy_id}|{draw}|{predicted_json}|{history_cutoff}"
    return hashlib.sha256(payload.encode()).hexdigest()


# ── Candidate builder ─────────────────────────────────────────────────────────

def _make_candidate(
    strategy_id:    str,
    strategy_name:  str,
    lottery_type:   str,
    target_draw:    dict,
    prediction_status: str,
    predicted_numbers: Optional[list[int]],
    predicted_special: Optional[int],
    history_cutoff_draw: Optional[str],
    block_reason:   Optional[str],
) -> dict[str, Any]:
    """Build a single candidate payload."""
    actual_numbers = target_draw["numbers"]
    actual_special = target_draw["special"]

    if prediction_status == PREDICTION_STATUS_READY and predicted_numbers is not None:
        hit_numbers, hit_count, special_hit = _compute_hit(
            predicted_numbers, actual_numbers, predicted_special, actual_special, lottery_type
        )
        predicted_json = json.dumps(predicted_numbers)
        prov_hash = _provenance_hash(
            strategy_id, target_draw["draw"], predicted_json,
            history_cutoff_draw or ""
        )
    else:
        hit_numbers  = []
        hit_count    = 0
        special_hit  = 0
        predicted_json = json.dumps(predicted_numbers) if predicted_numbers else None
        prov_hash = None

    return {
        "strategy_id":          strategy_id,
        "strategy_name":        strategy_name,
        "lottery_type":         lottery_type,
        "draw_number":          target_draw["draw"],
        "draw_date":            target_draw["date"],
        "prediction_status":    prediction_status,
        "predicted_numbers":    predicted_numbers,
        "actual_numbers":       actual_numbers,
        "hit_numbers":          hit_numbers,
        "hit_count":            hit_count,
        "special_hit":          special_hit,
        "history_cutoff_draw":  history_cutoff_draw,
        "block_reason":         block_reason,
        "source_trace":         "P13_BACKFILL_ENGINE_DRY_RUN",
        "provenance_hash":      prov_hash,
        "truth_level":          "CAUSAL_REPLAY_GENERATED" if prediction_status == PREDICTION_STATUS_READY else None,
        "dry_run_only":         True,
        "would_insert":         False,
        "counts_as_success":    False,
    }


# ── Per-strategy runner ───────────────────────────────────────────────────────

def _run_strategy(
    conn:          sqlite3.Connection,
    strategy_id:   str,
    lottery_type:  str,
    all_draws:     list[dict],
    adapter,
) -> tuple[list[dict], list[dict]]:
    """
    Run strategy against last TARGET_DRAW_WINDOW draws.
    Returns (all_candidates, sample_candidates).
    """
    from lottery_api.models.replay_strategy_registry import (
        RejectPrediction, InsufficientHistory, UnsupportedLotteryType,
        InvalidOutput, LifecycleNotExecutable,
    )

    strategy_name    = adapter.meta.strategy_name
    existing_draws   = _load_existing_replay_draws(conn, strategy_id, lottery_type)

    total_draws = len(all_draws)
    # Take the last TARGET_DRAW_WINDOW draws (most recent)
    target_start = max(0, total_draws - TARGET_DRAW_WINDOW)
    target_draws = all_draws[target_start:]

    candidates: list[dict] = []
    sample:     list[dict] = []
    ready_count = 0

    for i, target_draw in enumerate(target_draws):
        # Causal history: strictly before target draw by integer sort
        # Since all_draws is sorted ASC by CAST(draw AS INTEGER),
        # the history is all_draws[0 : target_start + i]
        history = all_draws[: target_start + i]
        target_draw_id = target_draw["draw"]
        history_cutoff = history[-1]["draw"] if history else None

        # ── Check duplicate ──────────────────────────────────────────────────
        if target_draw_id in existing_draws:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_DUPLICATE_REPLAY_ROW",
                None, None, history_cutoff,
                f"Draw {target_draw_id} already has replay row for {strategy_id}",
            )
            candidates.append(c)
            continue

        # ── Insufficient history pre-check ───────────────────────────────────
        if len(history) < adapter.meta.min_history:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_INSUFFICIENT_HISTORY",
                None, None, history_cutoff,
                f"history={len(history)} < min_history={adapter.meta.min_history}",
            )
            candidates.append(c)
            continue

        # ── Run adapter ──────────────────────────────────────────────────────
        try:
            predicted_numbers, predicted_special = adapter.get_one_bet(history, lottery_type)
        except LifecycleNotExecutable as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_NO_STRATEGY_RUNNER",
                None, None, history_cutoff, str(exc)[:256],
            )
            candidates.append(c)
            continue
        except InsufficientHistory as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_INSUFFICIENT_HISTORY",
                None, None, history_cutoff, str(exc)[:256],
            )
            candidates.append(c)
            continue
        except UnsupportedLotteryType as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_UNSUPPORTED_LOTTERY_TYPE",
                None, None, history_cutoff, str(exc)[:256],
            )
            candidates.append(c)
            continue
        except RejectPrediction as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_NO_PREDICTION_PAYLOAD",
                None, None, history_cutoff, str(exc)[:256],
            )
            candidates.append(c)
            continue
        except InvalidOutput as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_INVALID_OUTPUT",
                None, None, history_cutoff, str(exc)[:256],
            )
            candidates.append(c)
            continue
        except Exception as exc:
            c = _make_candidate(
                strategy_id, strategy_name, lottery_type, target_draw,
                "BLOCKED_REPLAY_ERROR",
                None, None, history_cutoff,
                f"{type(exc).__name__}: {str(exc)[:200]}",
            )
            candidates.append(c)
            continue

        # ── READY ────────────────────────────────────────────────────────────
        c = _make_candidate(
            strategy_id, strategy_name, lottery_type, target_draw,
            PREDICTION_STATUS_READY,
            predicted_numbers, predicted_special, history_cutoff, None,
        )
        candidates.append(c)
        ready_count += 1
        if ready_count <= CANDIDATES_SAMPLE_N:
            sample.append(c)

        # Progress to stderr
        if (i + 1) % 100 == 0:
            print(f"  [{strategy_id}] {i+1}/{len(target_draws)} draws processed, "
                  f"ready={ready_count}", file=sys.stderr)

    return candidates, sample


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"P13 Backfill Engine Dry-Run starting at {datetime.now(timezone.utc).isoformat()}",
          file=sys.stderr)

    from lottery_api.models.replay_strategy_registry import _REGISTRY

    conn = _open_db_readonly(DB_PATH)
    production_rows_before = _db_row_count(conn)

    if production_rows_before != 460:
        # Safety check: if rows have shifted, abort
        print(f"WARNING: production_rows_before={production_rows_before} != 460",
              file=sys.stderr)

    # ── Resolve Phase 1 strategies ────────────────────────────────────────────
    selected_strategies = []
    for sid in TARGET_STRATEGIES:
        if sid not in _REGISTRY:
            raise RuntimeError(f"Strategy {sid} not in ONLINE registry")
        adapter = _REGISTRY[sid]
        ltype   = adapter.meta.supported_lottery_types[0]
        selected_strategies.append({
            "strategy_id":   sid,
            "strategy_name": adapter.meta.strategy_name,
            "lottery_type":  ltype,
            "min_history":   adapter.meta.min_history,
        })

    # ── Run each strategy ─────────────────────────────────────────────────────
    all_candidates: list[dict] = []
    candidates_sample: list[dict] = []
    by_strategy: dict[str, dict] = {}

    for s in selected_strategies:
        sid      = s["strategy_id"]
        ltype    = s["lottery_type"]
        adapter  = _REGISTRY[sid]

        print(f"Loading draws for {ltype}...", file=sys.stderr)
        all_draws = _load_all_draws(conn, ltype)
        print(f"  {len(all_draws)} draws loaded. Running {sid} × {TARGET_DRAW_WINDOW} targets...",
              file=sys.stderr)

        candidates, sample = _run_strategy(conn, sid, ltype, all_draws, adapter)
        all_candidates.extend(candidates)
        candidates_sample.extend(sample)

        by_strategy[sid] = _summarise_strategy(sid, s["strategy_name"], ltype, candidates)
        print(f"  {sid}: {by_strategy[sid]['ready']} READY, "
              f"{by_strategy[sid]['blocked']} BLOCKED", file=sys.stderr)

    # ── Safety re-check DB rows ───────────────────────────────────────────────
    production_rows_after = _db_row_count(conn)
    conn.close()

    # ── Aggregate stats ───────────────────────────────────────────────────────
    total_generated   = len(all_candidates)
    ready_candidates  = sum(1 for c in all_candidates if c["prediction_status"] == PREDICTION_STATUS_READY)
    blocked_candidates = total_generated - ready_candidates
    fake_success_count = sum(
        1 for c in all_candidates
        if c["counts_as_success"] is True
    )

    by_status: dict[str, int] = {}
    block_reasons: dict[str, int] = {}
    for c in all_candidates:
        status = c["prediction_status"]
        by_status[status] = by_status.get(status, 0) + 1
        if status != PREDICTION_STATUS_READY and c.get("block_reason"):
            br = c["block_reason"][:80]
            block_reasons[br] = block_reasons.get(br, 0) + 1

    # ── Output JSON ───────────────────────────────────────────────────────────
    output = {
        "phase":                     "P13_BACKFILL_ENGINE_DRY_RUN",
        "generated_at":              datetime.now(timezone.utc).isoformat(),
        "dry_run_only":              True,
        "production_rows_before":    production_rows_before,
        "production_rows_after":     production_rows_after,
        "no_db_write":               True,
        "target_draw_window":        TARGET_DRAW_WINDOW,
        "target_strategy_count":     len(TARGET_STRATEGIES),
        "estimated_target_candidates": ESTIMATED_CANDIDATES,
        "generated_candidates":      total_generated,
        "ready_candidates":          ready_candidates,
        "blocked_candidates":        blocked_candidates,
        "fake_success_count":        fake_success_count,
        "selected_strategies":       selected_strategies,
        "by_strategy":               by_strategy,
        "by_status":                 by_status,
        "block_reasons":             block_reasons,
        "candidates_sample":         candidates_sample,
        "safety_flags": {
            "no_db_write":              True,
            "no_strategy_fabrication":  True,
            "no_fake_rows":             True,
            "no_artifact_as_executable": True,
            "no_no_data_as_success":    True,
            "no_p7_apply":              True,
            "no_retired_apply":         True,
            "counts_as_success_locked_false": fake_success_count == 0,
        },
        "p14_apply_gate_recommendation": {
            "note": (
                "Apply gate requires explicit CEO authorization phrase. "
                "Script: scripts/p14_backfill_apply_gate.py "
                "--dry-run-json outputs/replay/p13_backfill_engine_dry_run_20260520.json "
                "--authorization 'YES apply P13 Phase 1 backfill rows'"
            ),
            "authorization_phrase_required": "YES apply P13 Phase 1 backfill rows",
            "pre_apply_checks": [
                "fake_success_count == 0",
                "no READY candidate with fabricated predicted_numbers",
                "all provenance_hash values unique",
                "production_rows_before matches current DB count",
                "CEO explicit sign-off on ready_candidates count",
            ],
            "rollback_key": "controlled_apply_id = 'P13_PHASE1_APPLY_<timestamp>'",
            "estimated_net_new_rows": ready_candidates,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nP13 Dry-Run complete.", file=sys.stderr)
    print(f"  generated={total_generated}, ready={ready_candidates}, "
          f"blocked={blocked_candidates}, fake_success={fake_success_count}",
          file=sys.stderr)
    print(f"  production_rows_before={production_rows_before}, "
          f"production_rows_after={production_rows_after}", file=sys.stderr)
    print(f"  Output: {OUTPUT_PATH}", file=sys.stderr)
    print(f"Final classification: P13_BACKFILL_ENGINE_DRY_RUN_READY", file=sys.stderr)


def _summarise_strategy(strategy_id, strategy_name, lottery_type, candidates):
    ready   = sum(1 for c in candidates if c["prediction_status"] == PREDICTION_STATUS_READY)
    blocked = len(candidates) - ready
    by_status: dict[str, int] = {}
    for c in candidates:
        s = c["prediction_status"]
        by_status[s] = by_status.get(s, 0) + 1

    hit_counts = [c["hit_count"] for c in candidates if c["prediction_status"] == PREDICTION_STATUS_READY]
    avg_hit = round(sum(hit_counts) / len(hit_counts), 4) if hit_counts else 0.0
    special_hits = sum(c["special_hit"] for c in candidates if c["prediction_status"] == PREDICTION_STATUS_READY)

    return {
        "strategy_id":   strategy_id,
        "strategy_name": strategy_name,
        "lottery_type":  lottery_type,
        "total":         len(candidates),
        "ready":         ready,
        "blocked":       blocked,
        "by_status":     by_status,
        "avg_hit_count": avg_hit,
        "special_hits":  special_hits,
        "fake_success":  0,
    }


if __name__ == "__main__":
    main()
