#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4: Recent 30p anti-leakage walkforward simulation.
Outputs: data/recent_30p_performance.json
"""
import sys, os, json, sqlite3
from datetime import datetime
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

DB_PATH = os.path.join(ROOT, "lottery_api", "data", "lottery_v2.db")
DATA_DIR = os.path.join(ROOT, "data")

# Baselines: BIG_LOTTO/POWER_LOTTO use M3+ (hits>=3); DAILY_539 uses M2+ (hits>=2)
BASELINES_M3 = {
    "BIG_LOTTO":   8.96 / 100,   # 5-bet M3+
    "DAILY_539":   30.50 / 100,  # 3-bet M2+ (system uses is_m2plus for 539)
    "POWER_LOTTO": 18.09 / 100,  # 5-bet M3+ (est: 1-(1-0.0387)^5)
}

# Hit threshold per lottery
HIT_THRESHOLD = {
    "BIG_LOTTO": 3,
    "DAILY_539": 2,   # system uses M2+ for 539
    "POWER_LOTTO": 3,
}

# strategy_states 150p edge (from data/strategy_states_{lt}.json)
def get_edge_150p(lt):
    path = os.path.join(DATA_DIR, f"strategy_states_{lt}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    # edge150 field
    for key in ("edge_150p", "edge150", "edge_150", "current_edge"):
        if key in d:
            return d[key]
    return None


def get_all_draws(lt):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT draw, numbers, special FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
        (lt,)
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for draw, numbers_str, special in rows:
        try:
            nums = json.loads(numbers_str)
        except Exception:
            continue
        result.append({"draw": draw, "numbers": nums, "special": special})
    return result


def hits(bet, actual):
    return len(set(bet) & set(actual))


def run_30p_simulation(lt, strategy_func, n_bets_expected, all_draws):
    """
    Anti-leakage walkforward: for each of the last 30 draws,
    predict using only draws[0:i] (before that draw), then compare to draws[i].
    """
    # We need at least 200 draws of history before starting
    MIN_HISTORY = 200
    total = len(all_draws)
    if total < MIN_HISTORY + 30:
        return {"error": f"Not enough draws: {total}"}

    # Test on last 30 draws
    test_start = total - 30
    results = []

    for i in range(test_start, total):
        target = all_draws[i]
        history = all_draws[:i]  # strictly before target — no leakage
        actual_numbers = target["numbers"]

        try:
            bets = strategy_func(history)
            # Normalize: some return list of lists, some list of dicts
            normalized = []
            for b in bets:
                if isinstance(b, dict):
                    normalized.append(b.get("numbers", []))
                elif isinstance(b, (list, tuple)):
                    normalized.append(list(b))
            bets = normalized[:n_bets_expected]
        except Exception as e:
            # Strategy failed for this draw — skip
            results.append({"draw": target["draw"], "error": str(e), "m3plus": False})
            continue

        # Per-draw: any bet M3+?
        best_hit = max((hits(b, actual_numbers) for b in bets), default=0)
        thresh = HIT_THRESHOLD.get(lt, 3)
        m3plus = best_hit >= thresh

        results.append({
            "draw": target["draw"],
            "m3plus": m3plus,
            "best_hit": best_hit,
            "n_bets": len(bets),
        })

    valid = [r for r in results if "error" not in r]
    if not valid:
        return {"error": "All draws failed"}

    n = len(valid)
    m3_count = sum(1 for r in valid if r["m3plus"])
    m3_rate = m3_count / n

    return {
        "n_simulated": n,
        "m3plus_count": m3_count,
        "m3plus_rate": round(m3_rate, 4),
        "errors": len(results) - n,
    }


print("\n=== Phase 4: Recent 30p Anti-Leakage Simulation ===")

# Load strategy functions
from tools.rsm_bootstrap import get_big_lotto_strategies_inline, get_power_lotto_strategies_inline, get_daily_539_strategies_inline

def _get_func(strats, name):
    for s in strats:
        if s["name"] == name:
            return s["predict_func"]
    return None

big_strats   = get_big_lotto_strategies_inline()
power_strats = get_power_lotto_strategies_inline()
daily_strats = get_daily_539_strategies_inline()

func_map = {
    "BIG_LOTTO":   (_get_func(big_strats,   "p1_dev_sum5bet"),          5),
    "DAILY_539":   (_get_func(daily_strats,  "acb_markov_midfreq_3bet"), 3),
    "POWER_LOTTO": (_get_func(power_strats,  "orthogonal_5bet"),         5),
}

output = {
    "audit_date": datetime.utcnow().isoformat() + "Z",
    "by_lottery": {},
}

for lt, (func, n_bets) in func_map.items():
    print(f"\n  {lt} ({n_bets}注):")
    if func is None:
        print(f"    ⚠️  Strategy function not found")
        output["by_lottery"][lt] = {"error": "strategy function not found"}
        continue

    all_draws = get_all_draws(lt)
    print(f"    Total draws in DB: {len(all_draws)}")

    sim = run_30p_simulation(lt, func, n_bets, all_draws)
    if "error" in sim:
        print(f"    ⚠️  {sim['error']}")
        output["by_lottery"][lt] = sim
        continue

    baseline = BASELINES_M3[lt]
    edge_30p = sim["m3plus_rate"] - baseline
    edge_150p = get_edge_150p(lt)

    # Status thresholds
    if edge_30p >= -0.02:
        status = "NORMAL"
    elif edge_30p >= -0.05:
        status = "WATCH"
    else:
        status = "ALERT"

    result = {
        "draws_analyzed": sim["n_simulated"],
        "m3plus_count": sim["m3plus_count"],
        "m3plus_rate_30p": sim["m3plus_rate"],
        "hit_threshold_used": HIT_THRESHOLD.get(lt, 3),
        "baseline_m3plus": round(baseline, 4),
        "edge_30p": round(edge_30p, 4),
        "edge_150p_from_states": edge_150p,
        "status": status,
        "errors_in_sim": sim.get("errors", 0),
    }
    output["by_lottery"][lt] = result

    flag = "✅" if status == "NORMAL" else ("⚠️" if status == "WATCH" else "🔴")
    print(f"    {flag} M3+={sim['m3plus_rate']:.1%}  baseline={baseline:.1%}  edge_30p={edge_30p:+.1%}  status={status}")

out_path = os.path.join(DATA_DIR, "recent_30p_performance.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n✅ Written: {out_path}")
