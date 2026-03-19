#!/usr/bin/env python3
"""
S2 Validation Gates Runner
==========================
Stage 1: signal existence (ACF/PACF summary)
Stage 2: walk-forward edges on 150/500/1500 windows
Stage 3: permutation test
Stage 4: McNemar vs production coordinator
Stage 5: recent-100 Sharpe
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from database import DatabaseManager  # noqa: E402
from engine.perm_test import perm_test  # noqa: E402
from engine.rolling_strategy_monitor import BASELINES, METRIC_KEY  # noqa: E402
from engine.strategy_coordinator import coordinator_predict  # noqa: E402
from engine.s2_markov_weibull import predict_markov2_weibull  # noqa: E402


LOTTERIES = ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539")
BETS_TO_TEST = (2, 3)


def _metric_hit(bets: List[List[int]], actual: List[int], metric_key: str) -> bool:
    actual_set = set(actual)
    if not bets:
        return False
    best = max(len(set(b) & actual_set) for b in bets)
    return best >= 2 if metric_key == "is_m2plus" else best >= 3


def _mcnemar(new_hits: List[bool], base_hits: List[bool]) -> Dict:
    b = sum(1 for a, c in zip(new_hits, base_hits) if a and not c)  # new only
    c = sum(1 for a, c in zip(new_hits, base_hits) if c and not a)  # base only
    n = b + c
    if n == 0:
        return {"new_only": 0, "base_only": 0, "chi2": 0.0, "p": 1.0}
    chi2 = (abs(b - c) - 1.0) ** 2 / n  # Yates corrected
    # df=1 chi-square survival function
    p = math.erfc(math.sqrt(max(chi2, 0.0) / 2.0))
    return {"new_only": b, "base_only": c, "chi2": round(chi2, 4), "p": round(p, 4)}


def _edge_stats(hits: List[bool], baseline: float, windows=(150, 500, 1500)) -> Dict:
    out = {}
    for w in windows:
        h = hits[-w:] if len(hits) >= w else hits
        n = len(h)
        rate = (sum(h) / n) if n else 0.0
        out[f"{w}p"] = {"n": n, "rate": round(rate, 5), "edge": round(rate - baseline, 5)}
    return out


def _rolling_sharpe(hits: List[bool], baseline: float, lookback: int = 100) -> float:
    h = hits[-lookback:] if len(hits) >= lookback else hits
    if not h:
        return 0.0
    rets = [(1.0 if x else 0.0) - baseline for x in h]
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / max(len(rets) - 1, 1)
    std = math.sqrt(max(var, 1e-9))
    return mean / std


def _load_acf_summary() -> Dict:
    p = os.path.join(PROJECT_ROOT, "research", "acf_pacf_scan_results.json")
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _stage1_signal(acf_summary: Dict, lottery: str) -> Dict:
    node = acf_summary.get("lotteries", {}).get(lottery, {})
    if not node:
        return {"passed": False, "reason": "acf_scan_missing"}
    g = node.get("global", {})
    n_sig = int(g.get("numbers_with_any_sig", 0))
    max_signal = float(g.get("max_signal_strength", 0.0))
    conf = float(node.get("confidence_bound", 1.0))
    passed = n_sig >= 1 and max_signal > conf
    return {
        "passed": passed,
        "numbers_with_any_sig": n_sig,
        "max_signal_strength": round(max_signal, 4),
        "confidence_bound": round(conf, 4),
    }


def run_one(
    lottery: str,
    n_bets: int,
    history: List[dict],
    n_perm: int,
    min_train: int,
    max_oos: int,
    train_window: int,
) -> Dict:
    metric_key = METRIC_KEY[lottery]
    baseline = BASELINES[lottery][n_bets]

    new_hits: List[bool] = []
    base_hits: List[bool] = []

    start_idx = max(min_train, len(history) - max_oos)
    for i in range(start_idx, len(history)):
        train = history[max(0, i - train_window):i]
        actual = history[i]["numbers"]

        try:
            bets_new = predict_markov2_weibull(train, lottery_type=lottery, n_bets=n_bets)
            hit_new = _metric_hit(bets_new, actual, metric_key)
        except Exception:
            hit_new = False

        try:
            bets_base, _ = coordinator_predict(lottery, train, n_bets=n_bets, mode="hybrid")
            hit_base = _metric_hit(bets_base, actual, metric_key)
        except Exception:
            hit_base = False

        new_hits.append(hit_new)
        base_hits.append(hit_base)

    stage2 = _edge_stats(new_hits, baseline=baseline)
    s2_edges = [stage2["150p"]["edge"], stage2["500p"]["edge"], stage2["1500p"]["edge"]]
    stage2_pass = stage2["1500p"]["edge"] > 0 and sum(1 for e in s2_edges if e > 0) >= 2

    threshold = 2 if metric_key == "is_m2plus" else 3

    def _predict_fn(hist: List[dict]) -> List[List[int]]:
        use_hist = hist[-train_window:] if len(hist) > train_window else hist
        return predict_markov2_weibull(use_hist, lottery_type=lottery, n_bets=n_bets)

    def _hit_fn(bet: List[int], actual_set: set) -> bool:
        return len(set(bet) & actual_set) >= threshold

    perm_start = max(0, len(history) - (max_oos + min_train))
    perm_history = history[perm_start:]
    stage3 = perm_test(
        history=perm_history,
        predict_fn=_predict_fn,
        baseline=baseline,
        hit_fn=_hit_fn,
        min_history=min_train,
        n_perm=n_perm,
        seed=42,
        verbose=False,
    )
    stage3_pass = stage3.get("p_emp", 1.0) < 0.05

    mc = _mcnemar(new_hits, base_hits)
    stage4_pass = mc["p"] < 0.05 and mc["new_only"] > mc["base_only"]

    sharpe100 = _rolling_sharpe(new_hits, baseline=baseline, lookback=100)
    stage5_pass = sharpe100 > 0

    return {
        "lottery_type": lottery,
        "num_bets": n_bets,
        "baseline": baseline,
        "oos_n": len(new_hits),
        "stage2": {"passed": stage2_pass, "windows": stage2},
        "stage3": {
            "passed": stage3_pass,
            "p_emp": stage3.get("p_emp"),
            "cohens_d": stage3.get("cohens_d"),
            "verdict": stage3.get("verdict"),
        },
        "stage4": {"passed": stage4_pass, "mcnemar": mc},
        "stage5": {"passed": stage5_pass, "sharpe_100p": round(sharpe100, 4)},
        "final_pass": bool(stage2_pass and stage3_pass and stage4_pass and stage5_pass),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lottery", choices=("all",) + LOTTERIES, default="all")
    parser.add_argument("--bets", nargs="+", type=int, default=list(BETS_TO_TEST))
    parser.add_argument("--n-perm", type=int, default=120)
    parser.add_argument("--min-train", type=int, default=300)
    parser.add_argument("--max-oos", type=int, default=1500)
    parser.add_argument("--train-window", type=int, default=500)
    parser.add_argument(
        "--db-path",
        default=os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db"),
    )
    parser.add_argument(
        "--out-json",
        default=os.path.join(PROJECT_ROOT, "research", "s2_markov_weibull_gates.json"),
    )
    parser.add_argument(
        "--out-md",
        default=os.path.join(PROJECT_ROOT, "research", "s2_markov_weibull_gates.md"),
    )
    args = parser.parse_args()

    lotteries = list(LOTTERIES) if args.lottery == "all" else [args.lottery]
    db = DatabaseManager(db_path=args.db_path)
    acf_summary = _load_acf_summary()

    out = {
        "generated_at": datetime.now().isoformat(),
        "n_perm": args.n_perm,
        "min_train": args.min_train,
        "results": [],
    }

    for lt in lotteries:
        history = sorted(db.get_all_draws(lt), key=lambda x: (x["date"], x["draw"]))
        stage1 = _stage1_signal(acf_summary, lt)
        print(f"\n[{lt}] stage1={stage1.get('passed')} draws={len(history)}")
        for nb in args.bets:
            if nb not in BASELINES[lt]:
                continue
            print(f"  - run {nb} bets ...", flush=True)
            row = run_one(
                lottery=lt,
                n_bets=nb,
                history=history,
                n_perm=args.n_perm,
                min_train=args.min_train,
                max_oos=args.max_oos,
                train_window=args.train_window,
            )
            row["stage1"] = stage1
            row["final_pass"] = bool(stage1.get("passed", False) and row["final_pass"])
            out["results"].append(row)
            print(
                f"    stage2={row['stage2']['passed']} stage3={row['stage3']['passed']} "
                f"stage4={row['stage4']['passed']} stage5={row['stage5']['passed']} "
                f"final={row['final_pass']}"
            )

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # markdown summary
    lines = [
        "# S2 Markov2+Weibull Validation Gates",
        "",
        f"- generated_at: {out['generated_at']}",
        f"- n_perm: {out['n_perm']}",
        f"- min_train: {out['min_train']}",
        "",
        "| Lottery | Bets | Stage1 | Stage2 | Stage3 | Stage4 | Stage5 | Final |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in out["results"]:
        lines.append(
            f"| {r['lottery_type']} | {r['num_bets']} | "
            f"{'✅' if r['stage1']['passed'] else '❌'} | "
            f"{'✅' if r['stage2']['passed'] else '❌'} | "
            f"{'✅' if r['stage3']['passed'] else '❌'} | "
            f"{'✅' if r['stage4']['passed'] else '❌'} | "
            f"{'✅' if r['stage5']['passed'] else '❌'} | "
            f"{'✅' if r['final_pass'] else '❌'} |"
        )
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    print(f"\nsaved: {args.out_json}")
    print(f"saved: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
