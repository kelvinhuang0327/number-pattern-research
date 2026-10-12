"""
P358 read-only chronological holdout-stability screen on the 8 P357 candidates.
Read-only sqlite3 (mode=ro, PRAGMA query_only=ON). No writes. No repo edits.

Split rule (deterministic, documented):
  1. Take the candidate's distinct target_draw values, sorted ascending
     (oldest -> newest) by integer draw number.
  2. size = n // 3
  3. early   = draws[0 : size]                 (oldest third)
     middle  = draws[size : 2*size]            (middle third)
     holdout = draws[2*size : ]                (newest third; gets any remainder)
  This guarantees holdout is strictly the most recent contiguous segment and
  never overlaps early/middle -- no shuffling, no random sampling.
"""
import json
import statistics
import sqlite3
import sys

DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"

CANDIDATES = {
    "power_precision_3bet": "POWER_LOTTO",
    "power_orthogonal_5bet": "POWER_LOTTO",
    "fourier_rhythm_3bet": "POWER_LOTTO",
    "biglotto_triple_strike": "BIG_LOTTO",
    "biglotto_deviation_2bet": "BIG_LOTTO",
    "ts3_regime_3bet": "BIG_LOTTO",
    "daily539_f4cold": "DAILY_539",
    "daily539_markov_cold": "DAILY_539",
}


def ro_connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def verify_readonly_guarantee(conn):
    try:
        conn.execute("CREATE TABLE __p358_write_probe__ (x INTEGER)")
        return {"write_attempt_rejected": False, "reason": "UNEXPECTED: write succeeded"}
    except sqlite3.OperationalError as e:
        return {"write_attempt_rejected": True, "reason": str(e)}


def fetch_rows(conn, strategy_id, lottery_type):
    q = """
        SELECT target_draw, target_date, bet_index, hit_count, special_hit,
               predicted_numbers, actual_numbers, replay_status
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = ?
    """
    return conn.execute(q, [strategy_id, lottery_type]).fetchall()


def segment_stats(draws_seg, draw_hit_map, draw_date_map, draw_meanhit_map):
    if not draws_seg:
        return None
    m3 = sum(1 for d in draws_seg if draw_hit_map[d] >= 3) / len(draws_seg)
    per_draw_means = [statistics.fmean(draw_meanhit_map[d]) for d in draws_seg]
    mean_hit = statistics.fmean(per_draw_means)
    dates = [draw_date_map[d] for d in draws_seg if draw_date_map.get(d)]
    return {
        "n_draws": len(draws_seg),
        "draw_range": [draws_seg[0], draws_seg[-1]],
        "date_range": [min(dates), max(dates)] if dates else None,
        "m3plus_rate": round(m3, 4),
        "mean_hit_count": round(mean_hit, 4),
    }


def analyze_candidate(conn, strategy_id, lottery_type):
    rows = fetch_rows(conn, strategy_id, lottery_type)
    result = {"strategy_id": strategy_id, "lottery_type": lottery_type, "row_count": len(rows)}
    if not rows:
        result["classification"] = "NO_DATA"
        return result

    null_hit = sum(1 for r in rows if r["hit_count"] is None)
    null_pred = sum(1 for r in rows if not r["predicted_numbers"])
    null_actual = sum(1 for r in rows if not r["actual_numbers"])
    null_date = sum(1 for r in rows if not r["target_date"])
    bad_draw = sum(1 for r in rows if not str(r["target_draw"]).isdigit())
    distinct_combo = len({(r["target_draw"], r["bet_index"]) for r in rows})

    draws_asc = sorted({int(r["target_draw"]) for r in rows if str(r["target_draw"]).isdigit()})
    draw_hit_map, draw_meanhit_map, draw_date_map = {}, {}, {}
    for r in rows:
        if not str(r["target_draw"]).isdigit():
            continue
        d = int(r["target_draw"])
        hc = r["hit_count"] or 0
        draw_hit_map[d] = max(draw_hit_map.get(d, 0), hc)
        draw_meanhit_map.setdefault(d, []).append(hc)
        if r["target_date"]:
            draw_date_map[d] = r["target_date"]

    n = len(draws_asc)
    size = n // 3
    early = draws_asc[0:size]
    middle = draws_asc[size:2 * size]
    holdout = draws_asc[2 * size:]

    early_stats = segment_stats(early, draw_hit_map, draw_date_map, draw_meanhit_map)
    middle_stats = segment_stats(middle, draw_hit_map, draw_date_map, draw_meanhit_map)
    holdout_stats = segment_stats(holdout, draw_hit_map, draw_date_map, draw_meanhit_map)

    m3_values = [s["m3plus_rate"] for s in (early_stats, middle_stats, holdout_stats) if s]
    pooled_early_middle_draws = early + middle
    pooled_m3 = (
        sum(1 for d in pooled_early_middle_draws if draw_hit_map[d] >= 3) / len(pooled_early_middle_draws)
        if pooled_early_middle_draws else None
    )
    holdout_delta_vs_pooled = (
        round(holdout_stats["m3plus_rate"] - pooled_m3, 4)
        if (holdout_stats and pooled_m3 is not None) else None
    )
    holdout_delta_vs_early = (
        round(holdout_stats["m3plus_rate"] - early_stats["m3plus_rate"], 4)
        if (holdout_stats and early_stats) else None
    )
    holdout_delta_vs_middle = (
        round(holdout_stats["m3plus_rate"] - middle_stats["m3plus_rate"], 4)
        if (holdout_stats and middle_stats) else None
    )

    result.update({
        "draw_coverage": n,
        "draw_range": [draws_asc[0], draws_asc[-1]] if draws_asc else None,
        "missing_invalid_checks": {
            "null_hit_count_rows": null_hit,
            "null_predicted_numbers_rows": null_pred,
            "null_actual_numbers_rows": null_actual,
            "null_target_date_rows": null_date,
            "non_integer_target_draw_rows": bad_draw,
            "duplicate_combo_rows": len(rows) - distinct_combo,
        },
        "split_sizes": {"early": len(early), "middle": len(middle), "holdout": len(holdout)},
        "early_window": early_stats,
        "middle_window": middle_stats,
        "holdout_window": holdout_stats,
        "holdout_delta_vs_pooled_early_middle": holdout_delta_vs_pooled,
        "holdout_delta_vs_early": holdout_delta_vs_early,
        "holdout_delta_vs_middle": holdout_delta_vs_middle,
        "three_segment_m3plus_range": round(max(m3_values) - min(m3_values), 4) if len(m3_values) >= 2 else None,
        "three_segment_m3plus_stdev": round(statistics.pstdev(m3_values), 4) if len(m3_values) > 1 else None,
    })
    result["classification"] = "SCREENED_FOR_OOS_PROTOCOL_DESIGN"
    return result


def main():
    conn = ro_connect()
    ro_check = verify_readonly_guarantee(conn)
    results = [analyze_candidate(conn, sid, lt) for sid, lt in CANDIDATES.items()]
    conn.close()

    by_lottery = {}
    for r in results:
        by_lottery.setdefault(r["lottery_type"], []).append(r["strategy_id"])

    out = {
        "read_only_guarantee_check": ro_check,
        "split_rule": "distinct target_draw sorted ascending; size=n//3; early=[0:size], middle=[size:2*size], holdout=[2*size:] (remainder goes to holdout)",
        "candidates_by_lottery_type": by_lottery,
        "candidates": results,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
