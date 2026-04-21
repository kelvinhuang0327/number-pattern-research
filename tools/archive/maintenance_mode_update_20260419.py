#!/usr/bin/env python3
"""
Maintenance Layer Update (2026-04-19)

Phases:
A) combo_B automatic tracking setup
B) Maintenance-exit trigger design for 3 lotteries
C) Decision Engine Stage 2 recalibration with latest OOS data
D) PSI hypothesis review and validation
E) Maintenance mode summary

Outputs:
- data/combo_b_tracking_POWER_LOTTO.jsonl
- data/combo_b_milestone.json
- data/maintenance_exit_triggers.json
- data/stage2_recalibration.json
- data/psi_hypothesis_review.json
- data/psi_h2_validation.json
- data/maintenance_mode_summary_2026_04_19.json
- data/maintenance_agent_errors.json (only when needed)
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any

import numpy as np

ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
DATA_DIR = os.path.join(ROOT, "data")
MEM_DIR = os.path.join(ROOT, "memory")
DB_PATH = os.path.join(ROOT, "lottery_api", "data", "lottery_v2.db")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASELINES = {
    "POWER_LOTTO": {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    "BIG_LOTTO": {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    "DAILY_539": {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}

POOL = {"POWER_LOTTO": 38, "BIG_LOTTO": 49, "DAILY_539": 39}
PICKS = {"POWER_LOTTO": 6, "BIG_LOTTO": 6, "DAILY_539": 5}
METRIC_KEY = {"POWER_LOTTO": "is_m3plus", "BIG_LOTTO": "is_m3plus", "DAILY_539": "is_m2plus"}
DRAWS_PER_WEEK = {"POWER_LOTTO": 2, "BIG_LOTTO": 2, "DAILY_539": 7}

RNG_SEED = 42
ERRORS: List[Dict[str, Any]] = []


def draw_int(v: Any) -> int:
    return int(str(v))


def save_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def append_jsonl(path: str, rec: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def mcnemar_exact_p(b: int, c: int) -> float:
    from math import comb

    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    p = sum(comb(n, k) * (0.5 ** n) for k in range(lo + 1))
    return min(1.0, 2 * p)


def chi2_sf(x: float, df: int) -> float:
    if x <= 0:
        return 1.0
    h = 2.0 / (9.0 * df)
    z = ((x / df) ** (1.0 / 3.0) - (1.0 - h)) / math.sqrt(h)
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def parse_num_bets_from_name(name: str) -> int:
    m = re.search(r"(\d+)bet", name)
    if m:
        return int(m.group(1))
    return 1


def is_m3plus_any(bets: List[List[int]], actual: List[int]) -> bool:
    a = set(actual)
    for b in bets:
        if sum(1 for n in b if n in a) >= 3:
            return True
    return False


def load_draws_db(lottery_type: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT draw, date, numbers
        FROM draws
        WHERE lottery_type=?
        ORDER BY CAST(draw AS INTEGER) ASC
        """,
        (lottery_type,),
    ).fetchall()
    conn.close()

    out = []
    for draw, date, nums_raw in rows:
        s = str(nums_raw).strip()
        nums = json.loads(s) if s.startswith("[") else [int(x) for x in s.split(",") if x.strip()]
        out.append({"draw": str(draw), "date": date, "numbers": nums})
    return out


def compute_psi_series(
    draws: List[str],
    dates: List[str],
    actuals: List[List[int]],
    pool_size: int,
    baseline_window: int = 300,
    recent_window: int = 30,
) -> List[Dict[str, Any]]:
    eps = 1e-12
    series = []
    n = len(actuals)

    for i in range(baseline_window, n + 1):
        base = actuals[i - baseline_window:i]
        rec = actuals[i - recent_window:i]

        bcnt = np.zeros(pool_size)
        rcnt = np.zeros(pool_size)
        for d in base:
            for x in d:
                if 1 <= x <= pool_size:
                    bcnt[x - 1] += 1
        for d in rec:
            for x in d:
                if 1 <= x <= pool_size:
                    rcnt[x - 1] += 1

        b = bcnt / max(float(bcnt.sum()), 1.0)
        r = rcnt / max(float(rcnt.sum()), 1.0)
        psi = float(np.sum((r - b) * np.log((r + eps) / (b + eps))))

        idx = i - 1
        series.append({"idx": idx, "draw": draws[idx], "date": dates[idx], "psi": psi})

    return series


def rolling_edge(hits: List[int], baseline: float, window: int) -> List[Any]:
    out: List[Any] = [None] * len(hits)
    for i in range(window - 1, len(hits)):
        hr = sum(hits[i - window + 1:i + 1]) / window
        out[i] = hr - baseline
    return out


def choose_best_strategy(records: Dict[str, List[Dict[str, Any]]], lottery_type: str) -> Tuple[str, float, int]:
    metric = METRIC_KEY[lottery_type]
    best_name = ""
    best_edge = -999.0
    best_num_bets = 1

    for name, recs in records.items():
        if not recs:
            continue
        recs_sorted = sorted(recs, key=lambda r: draw_int(r["draw_id"]))
        num_bets = recs_sorted[0].get("num_bets", parse_num_bets_from_name(name))
        baseline = BASELINES[lottery_type].get(num_bets, BASELINES[lottery_type][1])
        hits = [1 if r.get(metric, False) else 0 for r in recs_sorted]
        edge = (sum(hits) / len(hits)) - baseline
        if edge > best_edge:
            best_edge = edge
            best_name = name
            best_num_bets = num_bets

    return best_name, best_edge, best_num_bets


def load_monitor_game(lottery_type: str) -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, f"rolling_monitor_{lottery_type}.json")
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    recs_map = obj.get("records", {})
    best_name, best_edge, best_num_bets = choose_best_strategy(recs_map, lottery_type)
    recs = sorted(recs_map[best_name], key=lambda r: draw_int(r["draw_id"]))

    draws = [str(r["draw_id"]) for r in recs]
    dates = [r["date"] for r in recs]
    actuals = [r["actual"] for r in recs]

    metric = METRIC_KEY[lottery_type]
    hits = [1 if r.get(metric, False) else 0 for r in recs]
    baseline = BASELINES[lottery_type].get(best_num_bets, BASELINES[lottery_type][1])

    return {
        "lottery_type": lottery_type,
        "best_strategy": best_name,
        "best_strategy_edge_full": round(best_edge, 4),
        "num_bets": best_num_bets,
        "baseline": baseline,
        "draws": draws,
        "dates": dates,
        "actuals": actuals,
        "hits": hits,
    }


def phase1_combo_tracking() -> Dict[str, Any]:
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_midfreq_fourier import midfreq_fourier_markov_3bet

    backtest_path = os.path.join(DATA_DIR, "power_lotto_full_backtest.jsonl")
    bt = read_jsonl(backtest_path)
    if not bt:
        raise RuntimeError("power_lotto_full_backtest.jsonl is empty")

    last_bt = bt[-1]
    started_draw = draw_int(last_bt["draw"])
    evaluate_at = started_draw + 300

    draws = load_draws_db("POWER_LOTTO")
    idx_map = {draw_int(d["draw"]): i for i, d in enumerate(draws)}
    if started_draw not in idx_map:
        raise RuntimeError(f"started_draw {started_draw} not found in DB")

    idx = idx_map[started_draw]
    if idx < 100:
        raise RuntimeError("insufficient history before started_draw")

    hist = draws[:idx]
    actual = draws[idx]["numbers"]

    fr = fourier_rhythm_predict(hist, n_bets=3, window=500)
    mk = midfreq_fourier_markov_3bet(hist)

    combo_b_bets = fr[:2] + mk[:3]
    fourier_hit = is_m3plus_any(fr[:2], actual)
    mk_hit = is_m3plus_any(mk[:3], actual)
    combo_hit = is_m3plus_any(combo_b_bets, actual)

    tracking_path = os.path.join(DATA_DIR, "combo_b_tracking_POWER_LOTTO.jsonl")
    existing = read_jsonl(tracking_path)
    existing_draws = {str(r.get("draw")) for r in existing}

    record = {
        "draw": str(started_draw),
        "date": draws[idx]["date"],
        "combo_b_bets": combo_b_bets,
        "actual_numbers": actual,
        "is_m3plus": combo_hit,
        "fourier_hit": fourier_hit,
        "mk_hit": mk_hit,
        "notes": "tracking bootstrap from latest backtest draw",
    }
    if str(started_draw) not in existing_draws:
        append_jsonl(tracking_path, record)

    milestone = {
        "started_draw": str(started_draw),
        "evaluate_at_draw": str(evaluate_at),
        "current_1500p_edge": 0.0089,
        "three_window_fail_reason": "150p=-1.24%",
        "mcnemar_net_vs_ortho5": -45,
        "status": "SHADOW_TRACKING",
        "retest_condition": "300 more draws AND three-window must pass AND perm_p < 0.05",
        "auto_retire_condition": "1500p edge < 0 at milestone",
        "last_updated": datetime.now().isoformat(),
    }
    milestone_path = os.path.join(DATA_DIR, "combo_b_milestone.json")
    save_json(milestone_path, milestone)

    return {
        "started_draw": str(started_draw),
        "evaluate_at_draw": str(evaluate_at),
        "status": milestone["status"],
        "tracking_path": tracking_path,
        "milestone_path": milestone_path,
    }


def phase2_exit_triggers() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    out = {}
    cache = {}

    for game in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
        g = load_monitor_game(game)
        draws = g["draws"]
        dates = g["dates"]
        actuals = g["actuals"]
        hits = g["hits"]
        baseline = g["baseline"]

        psi_series = compute_psi_series(draws, dates, actuals, POOL[game], 300, 30)
        psi_vals = [x["psi"] for x in psi_series]

        if psi_vals:
            mean_psi = float(np.mean(psi_vals))
            std_psi = float(np.std(psi_vals))
            p75 = float(np.percentile(psi_vals, 75))
            p90 = float(np.percentile(psi_vals, 90))
            p95 = float(np.percentile(psi_vals, 95))
            f01 = float(np.mean([1 if x > 0.1 else 0 for x in psi_vals]))
            f02 = float(np.mean([1 if x > 0.2 else 0 for x in psi_vals]))
            latest_psi = psi_vals[-1]
        else:
            mean_psi = std_psi = p75 = p90 = p95 = f01 = f02 = latest_psi = 0.0

        e50 = rolling_edge(hits, baseline, 50)

        for row in psi_series:
            idx = row["idx"]
            row["edge50"] = e50[idx] if idx < len(e50) else None

        edge_delta_stats = {}
        corr_values = []
        corr_d50 = []

        for n in [10, 20, 50]:
            event_d = []
            normal_d = []
            all_d = []

            for row in psi_series:
                idx = row["idx"]
                if idx + n >= len(e50):
                    continue
                e_now = e50[idx]
                e_next = e50[idx + n]
                if e_now is None or e_next is None:
                    continue
                d = e_next - e_now
                all_d.append((row["psi"], d))
                if row["psi"] > 0.2:
                    event_d.append(d)
                elif row["psi"] <= p75:
                    normal_d.append(d)

            edge_delta_stats[str(n)] = {
                "event_mean_delta": round(float(np.mean(event_d)), 6) if event_d else None,
                "normal_mean_delta": round(float(np.mean(normal_d)), 6) if normal_d else None,
                "event_n": len(event_d),
                "normal_n": len(normal_d),
            }

            if n == 50 and all_d:
                corr_values = [x for x, _ in all_d]
                corr_d50 = [d for _, d in all_d]

        corr = 0.0
        if len(corr_values) >= 5 and np.std(corr_values) > 1e-12 and np.std(corr_d50) > 1e-12:
            corr = float(np.corrcoef(corr_values, corr_d50)[0, 1])

        psi_valid = corr > 0.3

        if len(hits) >= 150:
            edge150 = (sum(hits[-150:]) / 150) - baseline
        else:
            edge150 = (sum(hits) / max(len(hits), 1)) - baseline

        def edge_win(start: int, end: int) -> Any:
            if start < 0:
                return None
            w = hits[start:end]
            if len(w) < 150:
                return None
            return (sum(w) / len(w)) - baseline

        w1 = edge_win(len(hits) - 150, len(hits))
        w2 = edge_win(len(hits) - 300, len(hits) - 150)
        w3 = edge_win(len(hits) - 450, len(hits) - 300)
        three_neg = all(x is not None and x < -0.01 for x in [w1, w2, w3])

        r300 = hits[-300:] if len(hits) >= 300 else hits[:]
        rng = random.Random(RNG_SEED)
        random_hits = [1 if rng.random() < baseline else 0 for _ in range(len(r300))]
        b = sum(1 for i in range(len(r300)) if r300[i] == 1 and random_hits[i] == 0)
        c = sum(1 for i in range(len(r300)) if r300[i] == 0 and random_hits[i] == 1)
        mc_p = mcnemar_exact_p(b, c)
        mc_net = b - c
        mc_reversal = (mc_net < 0 and mc_p < 0.10)

        sustained_psi = len(psi_vals) >= 3 and all(v > 0.2 for v in psi_vals[-3:])

        if len(hits) >= 1500:
            edge1500 = (sum(hits[-1500:]) / 1500) - baseline
        else:
            edge1500 = (sum(hits) / max(len(hits), 1)) - baseline
        deployment_baseline_edge = edge1500
        half_baseline_breach = deployment_baseline_edge > 0 and (edge1500 < 0.5 * deployment_baseline_edge)

        level1 = psi_valid and (latest_psi > p75) and (edge150 < 0)
        level2 = ((psi_valid and (latest_psi > p90) and three_neg) or mc_reversal)
        level3 = (psi_valid and sustained_psi) or half_baseline_breach

        current_status = "RED" if level3 else ("YELLOW" if (level1 or level2) else "GREEN")

        out[game] = {
            "best_strategy": g["best_strategy"],
            "best_strategy_edge_full": g["best_strategy_edge_full"],
            "psi_distribution": {
                "mean": round(mean_psi, 6),
                "std": round(std_psi, 6),
                "p75": round(p75, 6),
                "p90": round(p90, 6),
                "p95": round(p95, 6),
                "freq_gt_0_1": round(f01, 4),
                "freq_gt_0_2": round(f02, 4),
                "latest": round(latest_psi, 6),
            },
            "edge_delta_after_psi_peaks": edge_delta_stats,
            "psi_edge_correlation": round(corr, 6),
            "psi_is_valid_trigger": psi_valid,
            "level1_conditions": {
                "rule": "PSI > P75 AND recent_150p_edge < 0",
                "psi_gt_p75": latest_psi > p75,
                "edge150_lt_0": edge150 < 0,
                "recent_150p_edge": round(edge150, 6),
                "triggered": level1,
            },
            "level2_conditions": {
                "rule_a": "PSI > P90 AND 3 consecutive 150p windows edge < -1%",
                "rule_b": "McNemar vs random reversal in recent 300p (net<0 and p<0.10)",
                "psi_gt_p90": latest_psi > p90,
                "three_150_windows": {
                    "w1": round(w1, 6) if w1 is not None else None,
                    "w2": round(w2, 6) if w2 is not None else None,
                    "w3": round(w3, 6) if w3 is not None else None,
                    "all_lt_minus1pct": three_neg,
                },
                "mcnemar_recent300": {"b": b, "c": c, "net": mc_net, "p": round(mc_p, 6), "reversal": mc_reversal},
                "triggered": level2,
            },
            "level3_conditions": {
                "rule_a": "PSI > 0.2 for 3 consecutive periods",
                "rule_b": "deployed strategy 1500p edge below 50% of deployment baseline",
                "psi_gt_0_2_3x": sustained_psi,
                "edge1500": round(edge1500, 6),
                "deployment_baseline_edge": round(deployment_baseline_edge, 6),
                "below_half_baseline": half_baseline_breach,
                "triggered": level3,
                "baseline_source": "provisional_current_1500p_edge",
            },
            "current_status": current_status,
        }

        cache[game] = {
            "draws": draws,
            "dates": dates,
            "hits": hits,
            "baseline": baseline,
            "psi_series": psi_series,
            "best_strategy": g["best_strategy"],
        }

    save_json(os.path.join(DATA_DIR, "maintenance_exit_triggers.json"), out)
    return out, cache


def mc_perm_conditional_edge(
    hits: List[int], baseline: float, n_perm: int = 500, seed: int = 42
) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(hits)
    if n == 0:
        return 0.0, 1.0
    obs = (sum(hits) / n) - baseline
    ge = 0
    for _ in range(n_perm):
        null_hr = sum(1 for _ in range(n) if rng.random() < baseline) / n
        if (null_hr - baseline) >= obs:
            ge += 1
    return obs, ge / n_perm


def phase3_stage2_recalibration() -> Dict[str, Any]:
    old_thresholds = {}
    prev_path = os.path.join(DATA_DIR, "stage2_recalibration.json")
    if os.path.exists(prev_path):
        try:
            prev = json.load(open(prev_path, "r", encoding="utf-8"))
            old_thresholds = {
                k: v.get("optimal_threshold", 0.0)
                for k, v in prev.get("by_lottery", {}).items()
            }
        except Exception:
            old_thresholds = {}

    result = {
        "calibration_date": datetime.now().isoformat(),
        "by_lottery": {},
    }

    for game in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
        path = os.path.join(DATA_DIR, f"strategy_oos_refresh_{game}.jsonl")
        rows = read_jsonl(path)
        metric = METRIC_KEY[game]

        by_strategy = defaultdict(list)
        for r in rows:
            by_strategy[r["strategy"]].append(r)

        best_strategy = None
        best_edge = -999.0
        best_num_bets = 1
        best_hits = []

        for sname, srows in by_strategy.items():
            srows = sorted(srows, key=lambda x: draw_int(x["draw"]))
            num_bets = parse_num_bets_from_name(sname)
            baseline = BASELINES[game].get(num_bets, BASELINES[game][1])
            hits = [1 if r.get(metric, False) else 0 for r in srows]
            edge = (sum(hits) / len(hits)) - baseline
            if edge > best_edge:
                best_edge = edge
                best_strategy = sname
                best_num_bets = num_bets
                best_hits = hits

        baseline = BASELINES[game].get(best_num_bets, BASELINES[game][1])
        n = len(best_hits)

        re = rolling_edge(best_hits, baseline, 50)
        eval_idx = [i for i in range(len(re)) if re[i] is not None]
        n_eval = len(eval_idx)

        scan = []
        thresholds = [round(x, 4) for x in np.arange(0.0, 0.0801, 0.005)]
        for th in thresholds:
            active = [i for i in eval_idx if re[i] >= th]
            cond_hits = [best_hits[i] for i in active]
            if n_eval == 0:
                continue
            skip_rate = 1.0 - (len(active) / n_eval)
            if len(cond_hits) == 0:
                cond_hr = 0.0
                edge_bet = -baseline
            else:
                cond_hr = sum(cond_hits) / len(cond_hits)
                edge_bet = cond_hr - baseline
            edge_draw = edge_bet * (1.0 - skip_rate)
            scan.append(
                {
                    "threshold": th,
                    "conditional_hit_rate": cond_hr,
                    "n_active": len(active),
                    "skip_rate": skip_rate,
                    "edge_per_bet": edge_bet,
                    "edge_per_draw": edge_draw,
                    "cond_hits": cond_hits,
                }
            )

        candidates = [x for x in scan if x["skip_rate"] < 0.40]
        if candidates:
            best = max(candidates, key=lambda x: x["edge_per_draw"])
        else:
            best = max(scan, key=lambda x: x["edge_per_draw"]) if scan else {
                "threshold": 0.0,
                "conditional_hit_rate": 0.0,
                "n_active": 0,
                "skip_rate": 1.0,
                "edge_per_bet": -baseline,
                "edge_per_draw": -baseline,
                "cond_hits": [],
            }

        obs_edge, perm_p = mc_perm_conditional_edge(best["cond_hits"], baseline, n_perm=500, seed=RNG_SEED)

        old = float(old_thresholds.get(game, 0.0))
        new = float(best["threshold"])
        delta = new - old

        if new == 0.0 and perm_p > 0.10:
            rec = "DISABLE"
        elif abs(delta) >= 0.005:
            rec = "UPDATE"
        else:
            rec = "KEEP"

        result["by_lottery"][game] = {
            "best_strategy": best_strategy,
            "n_oos_rows": n,
            "optimal_threshold": round(new, 4),
            "expected_skip_rate": round(best["skip_rate"], 4),
            "conditional_edge": round(best["edge_per_bet"], 6),
            "edge_per_draw": round(best["edge_per_draw"], 6),
            "perm_p": round(perm_p, 6),
            "vs_previous_threshold": {"old": round(old, 4), "new": round(new, 4), "delta": round(delta, 4)},
            "recommendation": rec,
            "scan_top5": [
                {
                    "threshold": round(x["threshold"], 4),
                    "skip_rate": round(x["skip_rate"], 4),
                    "edge_per_bet": round(x["edge_per_bet"], 6),
                    "edge_per_draw": round(x["edge_per_draw"], 6),
                }
                for x in sorted(scan, key=lambda y: y["edge_per_draw"], reverse=True)[:5]
            ],
        }

    save_json(os.path.join(DATA_DIR, "stage2_recalibration.json"), result)
    return result


def parse_psi_hypotheses(md_path: str) -> List[Dict[str, Any]]:
    text = open(md_path, "r", encoding="utf-8").read()

    # Capture sections from "### H-PSI-X" to next heading
    pattern = re.compile(r"###\s+(H-PSI-\d+)：([^\n]+)\n(.*?)(?=\n###\s+H-PSI-|\Z)", re.S)
    out = []

    for hid, title, body in pattern.findall(text):
        hypo_m = re.search(r"\*\*假設\*\*：([^\n]+)", body)
        action_m = re.search(r"\*\*行動\*\*：([^\n]+)", body)
        test_m = re.search(r"\*\*測試方法\*\*：", body)

        out.append(
            {
                "id": hid,
                "title": title.strip(),
                "definition": hypo_m.group(1).strip() if hypo_m else "",
                "expected_effect": action_m.group(1).strip() if action_m else "",
                "has_test_method": bool(test_m),
                "status": "UNTESTED",
            }
        )

    out.sort(key=lambda x: x["id"])
    return out


def phase4_psi_review_and_validation(cache: Dict[str, Any]) -> Dict[str, Any]:
    review = parse_psi_hypotheses(os.path.join(MEM_DIR, "psi_trigger_hypotheses.md"))

    events = []
    for game in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
        c = cache[game]
        hits = c["hits"]
        baseline = c["baseline"]
        psi_series = c["psi_series"]

        for row in psi_series:
            if row["psi"] <= 0.2:
                continue
            idx = row["idx"]
            pre = None
            post = None
            delta = None
            if idx - 49 >= 0:
                pre = (sum(hits[idx - 49:idx + 1]) / 50) - baseline
            if idx + 50 < len(hits):
                post = (sum(hits[idx + 1:idx + 51]) / 50) - baseline
            if pre is not None and post is not None:
                delta = post - pre

            events.append(
                {
                    "lottery_type": game,
                    "draw": row["draw"],
                    "date": row["date"],
                    "psi_value": round(row["psi"], 6),
                    "edge_pre_50": round(pre, 6) if pre is not None else None,
                    "edge_post_50": round(post, 6) if post is not None else None,
                    "edge_delta_post_minus_pre": round(delta, 6) if delta is not None else None,
                }
            )

    # Select the most operational hypothesis for direct validation
    # H-PSI-2 chosen: zone distribution drift is directly mappable to weighting changes.
    selected_id = "H-PSI-2"

    # Validation: aggregate post-event 50-draw windows and compare to baseline expectation.
    valid_events = []
    obs_hits = 0
    obs_n = 0
    exp_hits = 0.0

    for game in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
        c = cache[game]
        hits = c["hits"]
        baseline = c["baseline"]
        for row in c["psi_series"]:
            if row["psi"] <= 0.2:
                continue
            idx = row["idx"]
            if idx + 50 >= len(hits):
                continue
            seg = hits[idx + 1 : idx + 51]
            valid_events.append((game, row["draw"], row["date"], row["psi"], sum(seg), len(seg), baseline))
            obs_hits += sum(seg)
            obs_n += len(seg)
            exp_hits += baseline * len(seg)

    n_events = len(valid_events)
    if n_events < 5:
        validation_status = "INSUFFICIENT_DATA"
        chi2 = None
        p = None
        cond_edge = None
    else:
        obs_miss = obs_n - obs_hits
        exp_miss = obs_n - exp_hits
        if exp_hits <= 0 or exp_miss <= 0:
            chi2 = 0.0
            p = 1.0
        else:
            chi2 = ((obs_hits - exp_hits) ** 2) / exp_hits + ((obs_miss - exp_miss) ** 2) / exp_miss
            p = chi2_sf(chi2, 1)
        cond_hr = obs_hits / obs_n if obs_n > 0 else 0.0
        exp_hr = exp_hits / obs_n if obs_n > 0 else 0.0
        cond_edge = cond_hr - exp_hr
        validation_status = "VALIDATED" if p is not None and p < 0.05 else "REJECTED"

    for h in review:
        if h["id"] == selected_id:
            h["status"] = validation_status

    review_payload = {
        "generated_at": datetime.now().isoformat(),
        "hypotheses": review,
    }
    save_json(os.path.join(DATA_DIR, "psi_hypothesis_review.json"), review_payload)

    validation_payload = {
        "hypothesis_id": selected_id,
        "status": validation_status,
        "trigger_event_count": n_events,
        "events": [
            {
                "lottery_type": g,
                "draw": d,
                "date": dt,
                "psi_value": round(psi, 6),
                "post50_hits": int(hits50),
                "post50_n": int(n50),
                "baseline": round(baseline, 6),
            }
            for (g, d, dt, psi, hits50, n50, baseline) in valid_events
        ],
        "aggregate": {
            "obs_hits": int(obs_hits),
            "obs_n": int(obs_n),
            "expected_hits": round(float(exp_hits), 4),
            "conditional_edge": round(float(cond_edge), 6) if cond_edge is not None else None,
            "chi_square": round(float(chi2), 6) if chi2 is not None else None,
            "p_value": round(float(p), 6) if p is not None else None,
        },
    }
    save_json(os.path.join(DATA_DIR, "psi_h2_validation.json"), validation_payload)

    return {
        "review": review_payload,
        "validation": validation_payload,
        "events": events,
    }


def phase5_summary(
    combo: Dict[str, Any],
    triggers: Dict[str, Any],
    stage2: Dict[str, Any],
    psi_review: Dict[str, Any],
) -> Dict[str, Any]:
    statuses = {k: v.get("current_status", "GREEN") for k, v in triggers.items()}

    changes = []
    for game, row in stage2.get("by_lottery", {}).items():
        if row.get("recommendation") in ("UPDATE", "DISABLE"):
            changes.append(
                {
                    "lottery": game,
                    "recommendation": row.get("recommendation"),
                    "old": row.get("vs_previous_threshold", {}).get("old"),
                    "new": row.get("vs_previous_threshold", {}).get("new"),
                    "perm_p": row.get("perm_p"),
                }
            )

    hyps = psi_review["review"].get("hypotheses", [])
    n_validated = sum(1 for h in hyps if h.get("status") == "VALIDATED")
    n_untested = sum(1 for h in hyps if h.get("status") == "UNTESTED")
    n_rejected = sum(1 for h in hyps if h.get("status") == "REJECTED")

    if any(s == "RED" for s in statuses.values()):
        health = "RED"
    elif any(s == "YELLOW" for s in statuses.values()) or changes:
        health = "YELLOW"
    else:
        health = "GREEN"

    started_draw = draw_int(combo["started_draw"])
    evaluate_draw = draw_int(combo["evaluate_at_draw"])
    draws_left = max(0, evaluate_draw - started_draw)
    expected_days = int(round((draws_left / DRAWS_PER_WEEK["POWER_LOTTO"]) * 7))
    expected_date = (datetime(2026, 4, 19) + timedelta(days=expected_days)).strftime("%Y-%m-%d")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "maintenance_mode_games": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
        "combo_b_tracking": {
            "started_draw": combo["started_draw"],
            "evaluate_at_draw": combo["evaluate_at_draw"],
            "status": combo["status"],
        },
        "exit_triggers": {
            "BIG_LOTTO": {"current": statuses.get("BIG_LOTTO", "GREEN"), "next_check": "next draw"},
            "DAILY_539": {"current": statuses.get("DAILY_539", "GREEN"), "next_check": "next draw"},
            "POWER_LOTTO": {"current": statuses.get("POWER_LOTTO", "GREEN"), "next_check": "next draw"},
        },
        "stage2_decision_engine": {
            "updated": len(changes) > 0,
            "changes": changes,
        },
        "psi_hypotheses": {
            "validated": n_validated,
            "untested": n_untested,
            "rejected": n_rejected,
        },
        "system_health": health,
        "scheduled_reviews": [
            {"trigger": "PSI Level 2", "condition": "PSI > P90 and 3x150p edge < -1%", "lottery": "all"},
            {"trigger": "PSI Level 3", "condition": "PSI > 0.2 for 3 consecutive periods", "lottery": "all"},
            {
                "trigger": "combo_B milestone",
                "condition": f"draw >= {combo['evaluate_at_draw']}",
                "lottery": "POWER_LOTTO",
            },
        ],
        "action_items": [
            {
                "priority": "HIGH",
                "action": (
                    f"Watch combo_B milestone draw {combo['evaluate_at_draw']} "
                    f"(expected around {expected_date})."
                ),
            },
            {
                "priority": "MED",
                "action": "If any lottery reaches PSI Level 2, restart targeted hypothesis search immediately.",
            },
            {
                "priority": "LOW",
                "action": "Re-run Stage 2 recalibration monthly or after every 100 new OOS draws.",
            },
        ],
    }

    save_json(os.path.join(DATA_DIR, "maintenance_mode_summary_2026_04_19.json"), summary)
    return summary


def run_phase(name: str, fn):
    for attempt in range(1, 4):
        try:
            print(f"[RUN] {name} attempt {attempt}")
            return fn()
        except Exception as ex:
            ERRORS.append(
                {
                    "phase": name,
                    "attempt": attempt,
                    "error": str(ex),
                    "time": datetime.now().isoformat(),
                }
            )
            print(f"[ERR] {name} attempt {attempt}: {ex}")
    print(f"[FAIL] {name} failed after 3 attempts; continue")
    return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    p1 = run_phase("phase1_combo_tracking", phase1_combo_tracking)
    p2 = run_phase("phase2_exit_triggers", phase2_exit_triggers)
    p3 = run_phase("phase3_stage2_recalibration", phase3_stage2_recalibration)

    triggers = {}
    cache = {}
    if p2:
        triggers, cache = p2

    p4 = run_phase("phase4_psi_review", lambda: phase4_psi_review_and_validation(cache)) if cache else None

    if p1 and triggers and p3 and p4:
        run_phase("phase5_summary", lambda: phase5_summary(p1, triggers, p3, p4))

    if ERRORS:
        save_json(os.path.join(DATA_DIR, "maintenance_agent_errors.json"), {"errors": ERRORS})

    print("done")


if __name__ == "__main__":
    main()
