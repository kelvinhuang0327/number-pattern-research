"""
P100 Special3 Prospective Result Evaluation Gate
=================================================
Evaluates P99 prospective predictions against actual 3_STAR draw (if available).
If no new draw is available: produces HOLD artifact.
If new draw is available: evaluates all P99 predictions and produces EVALUATED artifact.

GOVERNANCE:
  - DO NOT write to DB
  - DO NOT insert replay rows
  - DO NOT ingest actual draw into production DB
  - DO NOT promote strategies
  - DO NOT backtest 4_STAR
  - DB: read-only
"""

import json
import sqlite3
import os
import sys
from datetime import datetime, timezone
from itertools import product as iterproduct

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


# ─────────────────── paths ───────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")
P99_JSON = os.path.join(
    REPO_ROOT, "outputs", "replay",
    "special3_prospective_dryrun_plan_20260527.json"
)
OUT_DIR = os.path.join(REPO_ROOT, "outputs", "replay")
OUT_JSON = os.path.join(OUT_DIR, "special3_prospective_evaluation_20260527.json")

# ─────────────────── governance ───────────────────
DRY_RUN = True
EXPECTED_REPLAY_ROWS = 54462
EXPECTED_POWER_LOTTO_MAX = 115000041

# ─────────────────── helpers ───────────────────
def ts() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_p99() -> dict:
    with open(P99_JSON, "r") as f:
        return json.load(f)

def db_query(sql: str, params=()):
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()

def db_scalar(sql: str, params=()):
    rows = db_query(sql, params)
    return rows[0][0] if rows else None

def verify_governance():
    replay_rows = db_scalar("SELECT COUNT(*) FROM strategy_prediction_replays")
    if replay_rows != EXPECTED_REPLAY_ROWS:
        raise RuntimeError(
            f"GOVERNANCE VIOLATION: replay_rows={replay_rows} != {EXPECTED_REPLAY_ROWS}"
        )
    max_pl = db_scalar(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    if max_pl != EXPECTED_POWER_LOTTO_MAX:
        raise RuntimeError(
            f"GOVERNANCE VIOLATION: POWER_LOTTO max_draw={max_pl} != {EXPECTED_POWER_LOTTO_MAX}"
        )
    return replay_rows

# ─────────────────── check actual draw availability ───────────────────
def get_3star_state():
    rows = db_query(
        "SELECT CAST(draw AS INTEGER), draw, date, numbers, special "
        "FROM draws WHERE lottery_type='3_STAR' "
        "ORDER BY CAST(draw AS INTEGER) DESC LIMIT 5"
    )
    if not rows:
        return None, None, None, []
    latest = rows[0]
    max_draw_int = latest[0]
    max_draw_str = latest[1]
    max_date = latest[2]
    recent = [dict(r) for r in rows]
    return max_draw_int, max_draw_str, max_date, recent

def get_draw_after(history_end_draw_str: str):
    """
    Return the first 3_STAR draw with draw > history_end_draw, if any.
    Returns (draw_str, date, numbers_list, special) or None.
    """
    rows = db_query(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type='3_STAR' AND CAST(draw AS INTEGER) > ? "
        "ORDER BY CAST(draw AS INTEGER) ASC LIMIT 1",
        (int(history_end_draw_str),)
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "draw": r[0],
        "date": r[1],
        "numbers": json.loads(r[2]) if isinstance(r[2], str) else list(r[2]),
        "special": r[3],
    }

# ─────────────────── evaluation helpers ───────────────────
def serialize_ticket(t):
    """[d0, d1, d2] → 'xyz' fixed 3-digit"""
    return f"{t[0]}{t[1]}{t[2]}"

def actual_to_str(numbers: list) -> str:
    return f"{numbers[0]}{numbers[1]}{numbers[2]}"

def is_direct_hit(ticket_str: str, actual_str: str) -> bool:
    return ticket_str == actual_str

def is_box_hit(ticket_str: str, actual_str: str) -> bool:
    return sorted(ticket_str) == sorted(actual_str)

def position_digit_hits(ticket_str: str, actual_str: str) -> dict:
    return {
        "pos0": ticket_str[0] == actual_str[0],
        "pos1": ticket_str[1] == actual_str[1],
        "pos2": ticket_str[2] == actual_str[2],
        "any": any(ticket_str[i] == actual_str[i] for i in range(3)),
    }

def evaluate_predictions(predictions: list, actual_str: str) -> list:
    """Evaluate each prediction block against actual draw."""
    results = []
    for pred in predictions:
        strategy = pred["strategy"]
        top_n = pred["top_n"]
        tickets = pred["tickets"]
        n = len(tickets)

        direct_hits = [t for t in tickets if is_direct_hit(t, actual_str)]
        box_hits = [t for t in tickets if is_box_hit(t, actual_str)]
        pos_any_hits = [t for t in tickets if position_digit_hits(t, actual_str)["any"]]
        pos0_hits = sum(1 for t in tickets if t[0] == actual_str[0])
        pos1_hits = sum(1 for t in tickets if t[1] == actual_str[1])
        pos2_hits = sum(1 for t in tickets if t[2] == actual_str[2])

        results.append({
            "strategy": strategy,
            "top_n": top_n,
            "pool_size": n,
            "actual_draw": actual_str,
            "direct_hit": len(direct_hits) > 0,
            "direct_hit_count": len(direct_hits),
            "box_hit": len(box_hits) > 0,
            "box_hit_count": len(box_hits),
            "pos_any_hit_count": len(pos_any_hits),
            "pos0_hit_count": pos0_hits,
            "pos1_hit_count": pos1_hits,
            "pos2_hit_count": pos2_hits,
            "direct_hit_rate": round(len(direct_hits) / n, 6) if n else 0,
            "box_hit_rate": round(len(box_hits) / n, 6) if n else 0,
            "pos_any_hit_rate": round(len(pos_any_hits) / n, 6) if n else 0,
        })
    return results

def build_per_strategy_summary(eval_results: list) -> dict:
    """Aggregate per-strategy across top_n variants."""
    summary = {}
    for r in eval_results:
        s = r["strategy"]
        if s not in summary:
            summary[s] = {
                "strategy": s,
                "top_n_variants": [],
                "any_direct_hit": False,
                "any_box_hit": False,
            }
        summary[s]["top_n_variants"].append({
            "top_n": r["top_n"],
            "direct_hit": r["direct_hit"],
            "box_hit": r["box_hit"],
            "pos_any_hit_count": r["pos_any_hit_count"],
        })
        if r["direct_hit"]:
            summary[s]["any_direct_hit"] = True
        if r["box_hit"]:
            summary[s]["any_box_hit"] = True
    return summary

# ─────────────────── main ───────────────────
def main():
    print(f"[P100] Special3 Prospective Evaluation Gate")
    print(f"[P100] DRY_RUN={DRY_RUN}")

    # Governance pre-check
    replay_rows = verify_governance()
    print(f"[P100] Governance OK: replay_rows={replay_rows}")

    # Load P99
    p99 = load_p99()
    history_end_draw = p99["history_end_draw"]          # "115000024"
    history_end_date = p99["history_end_date"]
    p99_pred_count = len(p99["prospective_predictions"])
    p99_excluded = p99["excluded_strategies"]
    p99_candidates = p99["p99_candidates"]
    p99_ensemble_v2_members = p99["ensemble_v2_members"]
    p99_classification = p99["classification"]

    print(f"[P100] P99 history_end_draw={history_end_draw}, date={history_end_date}")
    print(f"[P100] P99 prediction blocks={p99_pred_count}")

    # 3_STAR state
    max_draw_int, max_draw_str, max_date, recent = get_3star_state()
    print(f"[P100] Current 3_STAR max draw={max_draw_str} ({max_date})")

    # Check for actual draw after P99 history_end
    actual_draw_info = get_draw_after(history_end_draw)
    actual_draw_available = actual_draw_info is not None

    # ─── governance post-check ───
    replay_rows_after = db_scalar("SELECT COUNT(*) FROM strategy_prediction_replays")

    base = {
        "task": "P100_SPECIAL3_PROSPECTIVE_EVALUATION",
        "phase": "P100",
        "date": "20260527",
        "generated_at": ts(),
        "dry_run_only": True,
        "db_writes": False,
        "replay_rows_changed": 0,
        "replay_rows_before": replay_rows,
        "replay_rows_after": replay_rows_after,
        "no_production_promotion": True,
        "star4_backtest": False,
        "special4_status": "DATA_GAP_BLOCKING",
        "special4_star4_draws": 0,
        "lottery_type": "3_STAR",
        "p99_artifact": "outputs/replay/special3_prospective_dryrun_plan_20260527.json",
        "p99_classification": p99_classification,
        "p99_history_end_draw": history_end_draw,
        "p99_history_end_date": history_end_date,
        "p99_target_draw": p99["target_draw"],
        "p99_evaluation_status": p99["evaluation_status"],
        "p99_dry_run_only": p99["dry_run_only"],
        "p99_excluded_strategies": p99_excluded,
        "p99_candidates": p99_candidates,
        "p99_ensemble_v2_members": p99_ensemble_v2_members,
        "p99_prediction_blocks": p99_pred_count,
        "current_db_max_3star_draw": max_draw_str,
        "current_db_max_3star_date": max_date,
        "actual_draw_available": actual_draw_available,
    }

    if not actual_draw_available:
        # ─── HOLD ───
        print(f"[P100] HOLD: no new 3_STAR draw after {history_end_draw}")
        artifact = {
            **base,
            "classification": "P100_SPECIAL3_PROSPECTIVE_EVALUATION_HOLD_NO_ACTUAL_DRAW",
            "evaluation_status": "PENDING_ACTUAL_DRAW",
            "hold_reason": (
                f"No new 3_STAR draw has been ingested since P99 history_end_draw={history_end_draw}. "
                f"Current DB max 3_STAR draw={max_draw_str} equals history_end. "
                "Cannot evaluate prospective predictions without actual draw result. "
                "Do NOT fabricate or infer actual draw."
            ),
            "actual_draw_number": None,
            "actual_numbers_serialized": None,
            "evaluation_results": None,
            "recommended_next_action": (
                f"Rerun {os.path.basename(__file__)} after next 3_STAR draw is ingested "
                f"into DB (draw > {history_end_draw})"
            ),
            "p101_recommendation": {
                "status": "NOT_YET_ELIGIBLE",
                "reason": (
                    "P101 requires P100 EVALUATED status. Current status is HOLD. "
                    "Run P100 again after actual draw is available."
                ),
                "trigger": "P100 evaluation_status == EVALUATED",
            },
        }
    else:
        # ─── EVALUATED ───
        actual_numbers = actual_draw_info["numbers"]
        actual_str = actual_to_str(actual_numbers)
        print(f"[P100] EVALUATED: actual draw={actual_draw_info['draw']}, numbers={actual_str}")

        # Load ticket lists from P99 predictions
        predictions_with_tickets = []
        for pred in p99["prospective_predictions"]:
            predictions_with_tickets.append({
                "strategy": pred["strategy"],
                "top_n": pred["top_n"],
                "tickets": pred["tickets"],
            })

        eval_results = evaluate_predictions(predictions_with_tickets, actual_str)
        per_strategy = build_per_strategy_summary(eval_results)

        # Determine next recommendation
        any_direct = any(r["direct_hit"] for r in eval_results)
        any_box = any(r["box_hit"] for r in eval_results)

        if any_direct:
            next_rec_status = "DIRECT_HIT_ADVANCE_TO_P101"
            next_rec_reason = "At least one strategy produced a direct hit. Eligible for P101 production consideration."
        elif any_box:
            next_rec_status = "BOX_HIT_INVESTIGATE_P101"
            next_rec_reason = "Box hit detected but no direct hit. Investigate top_n coverage before P101."
        else:
            next_rec_status = "NO_HIT_REVIEW_BEFORE_P101"
            next_rec_reason = "No direct or box hit. Review strategy configurations and coverage before P101."

        artifact = {
            **base,
            "classification": "P100_SPECIAL3_PROSPECTIVE_EVALUATION_READY",
            "evaluation_status": "EVALUATED",
            "actual_draw_number": actual_draw_info["draw"],
            "actual_draw_date": actual_draw_info["date"],
            "actual_numbers": actual_numbers,
            "actual_numbers_serialized": actual_str,
            "evaluation_results": eval_results,
            "per_strategy_summary": per_strategy,
            "overall": {
                "any_direct_hit": any_direct,
                "any_box_hit": any_box,
                "total_strategies_evaluated": len(per_strategy),
            },
            "p101_recommendation": {
                "status": next_rec_status,
                "reason": next_rec_reason,
                "trigger": "Manual P101 review with per_strategy_summary evidence",
            },
        }

    # Write artifact
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[P100] Written: {OUT_JSON}")
    print(f"[P100] Classification: {artifact['classification']}")
    print(f"[P100] evaluation_status: {artifact['evaluation_status']}")
    print(f"[P100] actual_draw_available: {actual_draw_available}")
    print(f"[P100] replay_rows before/after: {replay_rows}/{replay_rows_after}")
    print(f"[P100] Done.")

    return artifact

if __name__ == "__main__":
    main()
