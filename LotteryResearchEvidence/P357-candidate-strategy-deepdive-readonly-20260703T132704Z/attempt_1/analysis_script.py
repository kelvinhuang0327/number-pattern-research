"""
P357 read-only deep-dive on the 8 P356 ONLINE candidate strategies.
Read-only sqlite3 (mode=ro, PRAGMA query_only=ON). No writes. No repo edits.
"""
import json
import statistics
import sqlite3
import sys

DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
sys.path.insert(0, "/Users/kelvin/Kelvin-WorkSpace/LotteryNew")

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

WINDOWS = [30, 100, 500, 1500]
N_QUARTILES = 4


def ro_connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def verify_readonly_guarantee(conn):
    try:
        conn.execute("CREATE TABLE __p357_write_probe__ (x INTEGER)")
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


def official_draw_count_in_range(conn, lottery_type, min_draw, max_draw):
    q = """
        SELECT COUNT(*) FROM draws
        WHERE lottery_type = ? AND CAST(draw AS INTEGER) BETWEEN ? AND ?
    """
    return conn.execute(q, [lottery_type, min_draw, max_draw]).fetchone()[0]


def m3_window_rate(draw_hit_map, draws_desc, n):
    if len(draws_desc) < n:
        return None
    w = draws_desc[:n]
    return round(sum(1 for d in w if draw_hit_map[d] >= 3) / n, 4)


def chronological_quartiles(draws_asc, draw_hit_map, draw_meanhit_map):
    n = len(draws_asc)
    if n < N_QUARTILES:
        return []
    size = n // N_QUARTILES
    quartiles = []
    for i in range(N_QUARTILES):
        start = i * size
        end = (i + 1) * size if i < N_QUARTILES - 1 else n
        seg = draws_asc[start:end]
        if not seg:
            continue
        m3 = sum(1 for d in seg if draw_hit_map[d] >= 3) / len(seg)
        mean_hit = statistics.fmean(draw_meanhit_map[d] for d in seg)
        quartiles.append({
            "quartile": f"Q{i+1}",
            "n_draws": len(seg),
            "draw_range": [seg[0], seg[-1]],
            "m3plus_rate": round(m3, 4),
            "mean_hit_count": round(mean_hit, 4),
        })
    return quartiles


def analyze_candidate(conn, strategy_id, lottery_type):
    rows = fetch_rows(conn, strategy_id, lottery_type)
    result = {"strategy_id": strategy_id, "lottery_type": lottery_type, "row_count": len(rows)}

    if not rows:
        result["classification"] = "NO_DATA"
        return result

    # missing/invalid checks
    null_hit = sum(1 for r in rows if r["hit_count"] is None)
    null_pred = sum(1 for r in rows if not r["predicted_numbers"])
    null_actual = sum(1 for r in rows if not r["actual_numbers"])
    null_date = sum(1 for r in rows if not r["target_date"])
    bad_draw = sum(1 for r in rows if not str(r["target_draw"]).isdigit())
    distinct_combo = len({(r["target_draw"], r["bet_index"]) for r in rows})
    distinct_status = sorted({r["replay_status"] for r in rows})

    draws_int = sorted({int(r["target_draw"]) for r in rows if str(r["target_draw"]).isdigit()})
    draws_desc = list(reversed(draws_int))
    dates = sorted({r["target_date"] for r in rows if r["target_date"]})

    draw_hit_map = {}      # draw -> max hit_count across bet_index (M3+ contract)
    draw_meanhit_map = {}  # draw -> list of hit_counts across bet_index (for mean)
    for r in rows:
        if not str(r["target_draw"]).isdigit():
            continue
        d = int(r["target_draw"])
        hc = r["hit_count"] or 0
        draw_hit_map[d] = max(draw_hit_map.get(d, 0), hc)
        draw_meanhit_map.setdefault(d, []).append(hc)
    draw_meanhit_avg = {d: statistics.fmean(v) for d, v in draw_meanhit_map.items()}

    hit_counts = [r["hit_count"] for r in rows if r["hit_count"] is not None]
    hit_hist = {}
    for hc in hit_counts:
        hit_hist[str(hc)] = hit_hist.get(str(hc), 0) + 1

    special_hits = sum(1 for r in rows if r["special_hit"])

    official_count = official_draw_count_in_range(conn, lottery_type, draws_int[0], draws_int[-1]) if draws_int else 0
    draw_gap_count = official_count - len(draws_int) if official_count else None

    windows_result = {str(w): m3_window_rate(draw_hit_map, draws_desc, w) for w in WINDOWS}
    quartiles = chronological_quartiles(draws_int, draw_hit_map, draw_meanhit_avg)

    m3_values = [q["m3plus_rate"] for q in quartiles]
    stability = None
    if len(m3_values) >= 2:
        stability = {
            "quartile_m3plus_min": round(min(m3_values), 4),
            "quartile_m3plus_max": round(max(m3_values), 4),
            "quartile_m3plus_range": round(max(m3_values) - min(m3_values), 4),
            "quartile_m3plus_stdev": round(statistics.pstdev(m3_values), 4) if len(m3_values) > 1 else None,
        }

    result.update({
        "draw_coverage": len(draws_int),
        "bet_indexes": sorted({r["bet_index"] for r in rows}),
        "derived_bet_count": len({r["bet_index"] for r in rows}),
        "draw_range": [draws_int[0], draws_int[-1]] if draws_int else None,
        "date_range": [dates[0], dates[-1]] if dates else None,
        "distinct_replay_status_values": distinct_status,
        "hit_count_mean": round(statistics.fmean(hit_counts), 4) if hit_counts else None,
        "hit_count_stdev": round(statistics.pstdev(hit_counts), 4) if len(hit_counts) > 1 else None,
        "hit_count_histogram": hit_hist,
        "special_hit_count": special_hits,
        "special_hit_rate": round(special_hits / len(rows), 4) if rows else None,
        "m3plus_success_rate_by_recency_window": windows_result,
        "chronological_quartiles": quartiles,
        "chronological_stability": stability,
        "missing_invalid_checks": {
            "null_hit_count_rows": null_hit,
            "null_predicted_numbers_rows": null_pred,
            "null_actual_numbers_rows": null_actual,
            "null_target_date_rows": null_date,
            "non_integer_target_draw_rows": bad_draw,
            "row_count_vs_distinct_draw_bet_combo": [len(rows), distinct_combo],
            "duplicate_combo_rows": len(rows) - distinct_combo,
            "official_draws_in_range": official_count,
            "strategy_distinct_draws_in_range": len(draws_int),
            "possible_missing_draw_rows": draw_gap_count,
        },
    })

    result["classification"] = "SUITABLE_FOR_OOS_DESIGN_CANDIDATE"
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
        "candidates_by_lottery_type": by_lottery,
        "candidates": results,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
