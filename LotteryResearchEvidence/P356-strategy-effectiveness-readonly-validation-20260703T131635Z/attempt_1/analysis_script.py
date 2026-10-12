"""
P356 read-only strategy-effectiveness inventory + descriptive analysis.
Read-only sqlite3 (mode=ro, PRAGMA query_only=ON) against the canonical DB.
No writes. No repo edits. Uses only the existing in-repo registry module
(imported, not modified) plus stdlib.
"""
import json
import math
import sqlite3
import statistics
import sys

DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"

sys.path.insert(0, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew")
from lottery_api.models.replay_strategy_registry import (
    list_strategy_lifecycle_metadata,
    summarize_strategy_lifecycle_counts,
)

WINDOWS = [30, 100, 500, 1500]
CANDIDATE_MIN_COVERAGE = 30  # smallest window used elsewhere in this project's own success-rate contract
CANDIDATE_LIFECYCLE = {"ONLINE", "OBSERVATION"}


def ro_connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def verify_readonly_guarantee(conn):
    try:
        conn.execute("CREATE TABLE __p356_write_probe__ (x INTEGER)")
        return {"write_attempt_rejected": False, "reason": "UNEXPECTED: write succeeded"}
    except sqlite3.OperationalError as e:
        return {"write_attempt_rejected": True, "reason": str(e)}


def fetch_strategy_rows(conn, strategy_id, lottery_types):
    placeholders = ",".join("?" for _ in lottery_types)
    q = f"""
        SELECT lottery_type, target_draw, bet_index, hit_count, special_hit, replay_status
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type IN ({placeholders})
    """
    cur = conn.execute(q, [strategy_id, *lottery_types])
    return cur.fetchall()


def m3_window_success_rate(draw_hit_map, sorted_draws_desc, window_n):
    if len(sorted_draws_desc) < window_n:
        return None
    window_draws = sorted_draws_desc[:window_n]
    successes = sum(1 for d in window_draws if draw_hit_map[d] >= 3)
    return round(successes / window_n, 4)


def analyze_strategy(conn, meta):
    strategy_id = meta["strategy_id"]
    lottery_types = meta["supported_lottery_types"]
    rows = fetch_strategy_rows(conn, strategy_id, lottery_types)

    result = {
        "strategy_id": strategy_id,
        "strategy_name": meta["strategy_name"],
        "strategy_version": meta.get("strategy_version"),
        "lifecycle_status": meta["lifecycle_status"],
        "supported_lottery_types": lottery_types,
        "min_history": meta.get("min_history"),
        "row_count": len(rows),
    }

    if not rows:
        result["draw_coverage"] = 0
        result["classification"] = "NO_DATA"
        return result

    by_lottery = {}
    for r in rows:
        by_lottery.setdefault(r["lottery_type"], []).append(r)

    lottery_summaries = {}
    for lt, lt_rows in by_lottery.items():
        draws = sorted({int(r["target_draw"]) for r in lt_rows}, reverse=True)
        bet_indexes = sorted({r["bet_index"] for r in lt_rows})
        hit_counts = [r["hit_count"] for r in lt_rows if r["hit_count"] is not None]
        special_hits = sum(1 for r in lt_rows if r["special_hit"])

        draw_hit_map = {}
        for r in lt_rows:
            d = int(r["target_draw"])
            hc = r["hit_count"] or 0
            draw_hit_map[d] = max(draw_hit_map.get(d, 0), hc)

        hit_hist = {}
        for hc in hit_counts:
            hit_hist[str(hc)] = hit_hist.get(str(hc), 0) + 1

        windows_result = {}
        for w in WINDOWS:
            windows_result[str(w)] = m3_window_success_rate(draw_hit_map, draws, w)

        lottery_summaries[lt] = {
            "row_count": len(lt_rows),
            "draw_coverage": len(draws),
            "bet_indexes": bet_indexes,
            "derived_bet_count": len(bet_indexes),
            "min_target_draw": min(draws) if draws else None,
            "max_target_draw": max(draws) if draws else None,
            "hit_count_mean": round(statistics.fmean(hit_counts), 4) if hit_counts else None,
            "hit_count_stdev": round(statistics.pstdev(hit_counts), 4) if len(hit_counts) > 1 else None,
            "hit_count_histogram": hit_hist,
            "special_hit_count": special_hits,
            "special_hit_rate": round(special_hits / len(lt_rows), 4) if lt_rows else None,
            "m3plus_success_rate_by_window": windows_result,
            "distinct_replay_status_values": sorted({r["replay_status"] for r in lt_rows}),
        }

    result["draw_coverage"] = max(s["draw_coverage"] for s in lottery_summaries.values())
    result["by_lottery_type"] = lottery_summaries

    is_candidate = (
        meta["lifecycle_status"] in CANDIDATE_LIFECYCLE
        and result["draw_coverage"] >= CANDIDATE_MIN_COVERAGE
    )
    if meta["lifecycle_status"] not in CANDIDATE_LIFECYCLE:
        result["classification"] = f"EXCLUDED_LIFECYCLE_{meta['lifecycle_status']}"
    elif result["draw_coverage"] < CANDIDATE_MIN_COVERAGE:
        result["classification"] = "EXCLUDED_INSUFFICIENT_COVERAGE"
    else:
        result["classification"] = "CANDIDATE_FOR_FURTHER_RESEARCH"

    return result


def main():
    conn = ro_connect()
    ro_check = verify_readonly_guarantee(conn)

    registry = list_strategy_lifecycle_metadata()
    lifecycle_counts = summarize_strategy_lifecycle_counts()

    all_results = [analyze_strategy(conn, meta) for meta in registry]

    total_rows_in_table = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    distinct_status_overall = [
        r[0] for r in conn.execute("SELECT DISTINCT replay_status FROM strategy_prediction_replays").fetchall()
    ]

    conn.close()

    out = {
        "read_only_guarantee_check": ro_check,
        "registry_lifecycle_counts": lifecycle_counts,
        "total_rows_in_strategy_prediction_replays": total_rows_in_table,
        "distinct_row_level_replay_status_values": distinct_status_overall,
        "candidate_min_coverage_threshold": CANDIDATE_MIN_COVERAGE,
        "candidate_lifecycle_statuses": sorted(CANDIDATE_LIFECYCLE),
        "windows_used": WINDOWS,
        "strategies": all_results,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
