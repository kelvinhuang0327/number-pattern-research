#!/usr/bin/env python3
"""
S2.1 Grid + Full Gates
======================
1) Stage2 pre-screen with parameter grid
2) Full Stage1~Stage5 on top candidates
"""
from __future__ import annotations

import argparse
import itertools
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
BETS = (2, 3)


def _metric_hit(bets: List[List[int]], actual: List[int], metric_key: str) -> bool:
    if not bets:
        return False
    s = set(actual)
    m = max(len(set(b) & s) for b in bets)
    return m >= 2 if metric_key == "is_m2plus" else m >= 3


def _edge_stats(hits: List[bool], baseline: float) -> Dict[str, Dict]:
    out = {}
    for w in (150, 500, 1500):
        h = hits[-w:] if len(hits) >= w else hits
        n = len(h)
        rate = sum(h) / n if n else 0.0
        out[f"{w}p"] = {"n": n, "rate": round(rate, 5), "edge": round(rate - baseline, 5)}
    return out


def _mcnemar(a_hits: List[bool], b_hits: List[bool]) -> Dict:
    b = sum(1 for a, c in zip(a_hits, b_hits) if a and not c)
    c = sum(1 for a, c in zip(a_hits, b_hits) if c and not a)
    n = b + c
    if n == 0:
        return {"new_only": 0, "base_only": 0, "chi2": 0.0, "p": 1.0}
    chi2 = (abs(b - c) - 1.0) ** 2 / n
    p = math.erfc(math.sqrt(max(chi2, 0.0) / 2.0))
    return {"new_only": b, "base_only": c, "chi2": round(chi2, 4), "p": round(p, 4)}


def _sharpe_100(hits: List[bool], baseline: float) -> float:
    h = hits[-100:] if len(hits) >= 100 else hits
    if not h:
        return 0.0
    r = [(1.0 if x else 0.0) - baseline for x in h]
    mu = sum(r) / len(r)
    var = sum((x - mu) ** 2 for x in r) / max(len(r) - 1, 1)
    return mu / math.sqrt(max(var, 1e-9))


def _stage1_pass(acf_data: Dict, lottery: str) -> bool:
    node = acf_data.get("lotteries", {}).get(lottery, {})
    if not node:
        return False
    g = node.get("global", {})
    return float(g.get("max_signal_strength", 0.0)) > float(node.get("confidence_bound", 1.0))


def _predict(train: List[dict], lottery: str, n_bets: int, cfg: Dict) -> List[List[int]]:
    return predict_markov2_weibull(
        train,
        lottery_type=lottery,
        n_bets=n_bets,
        w_markov2=cfg["w_markov2"],
        w_weibull=1.0 - cfg["w_markov2"],
        pair_min_count=cfg["pair_min_count"],
        diversity_penalty=cfg["diversity_penalty"],
        pressure_boost=cfg["pressure_boost"],
    )


def _run_hits(
    history: List[dict],
    lottery: str,
    n_bets: int,
    cfg: Dict,
    min_train: int,
    max_oos: int,
    train_window: int,
    base_hits_cached: List[bool] = None,
) -> Dict:
    metric = METRIC_KEY[lottery]
    base = BASELINES[lottery][n_bets]
    start = max(min_train, len(history) - max_oos)
    new_hits: List[bool] = []
    base_hits: List[bool] = list(base_hits_cached) if base_hits_cached is not None else []
    for i in range(start, len(history)):
        train = history[max(0, i - train_window):i]
        actual = history[i]["numbers"]
        try:
            p = _predict(train, lottery, n_bets, cfg)
            nh = _metric_hit(p, actual, metric)
        except Exception:
            nh = False
        if base_hits_cached is None:
            try:
                b, _ = coordinator_predict(lottery, train, n_bets=n_bets, mode="hybrid")
                bh = _metric_hit(b, actual, metric)
            except Exception:
                bh = False
            base_hits.append(bh)
        new_hits.append(nh)
    return {"new_hits": new_hits, "base_hits": base_hits, "baseline": base}


def _full_gate_eval(
    history: List[dict],
    lottery: str,
    n_bets: int,
    cfg: Dict,
    stage1_pass: bool,
    min_train: int,
    max_oos: int,
    train_window: int,
    n_perm: int,
    base_hits_cached: List[bool],
) -> Dict:
    r = _run_hits(
        history,
        lottery,
        n_bets,
        cfg,
        min_train,
        max_oos,
        train_window,
        base_hits_cached=base_hits_cached,
    )
    stage2w = _edge_stats(r["new_hits"], r["baseline"])
    s2_pass = stage2w["1500p"]["edge"] > 0 and sum(1 for x in stage2w.values() if x["edge"] > 0) >= 2

    threshold = 2 if METRIC_KEY[lottery] == "is_m2plus" else 3

    def _predict_fn(hist: List[dict]) -> List[List[int]]:
        use = hist[-train_window:] if len(hist) > train_window else hist
        return _predict(use, lottery, n_bets, cfg)

    def _hit_fn(bet: List[int], actual_set: set) -> bool:
        return len(set(bet) & actual_set) >= threshold

    perm_start = max(0, len(history) - (max_oos + min_train))
    perm_hist = history[perm_start:]
    p = perm_test(
        history=perm_hist,
        predict_fn=_predict_fn,
        baseline=r["baseline"],
        hit_fn=_hit_fn,
        min_history=min_train,
        n_perm=n_perm,
        seed=42,
        verbose=False,
    )
    s3_pass = p.get("p_emp", 1.0) < 0.05

    mc = _mcnemar(r["new_hits"], r["base_hits"])
    s4_pass = mc["p"] < 0.05 and mc["new_only"] > mc["base_only"]

    sh = _sharpe_100(r["new_hits"], r["baseline"])
    s5_pass = sh > 0

    final = bool(stage1_pass and s2_pass and s3_pass and s4_pass and s5_pass)
    return {
        "config": cfg,
        "stage1": {"passed": stage1_pass},
        "stage2": {"passed": s2_pass, "windows": stage2w},
        "stage3": {"passed": s3_pass, "p_emp": p.get("p_emp"), "cohens_d": p.get("cohens_d"), "verdict": p.get("verdict")},
        "stage4": {"passed": s4_pass, "mcnemar": mc},
        "stage5": {"passed": s5_pass, "sharpe_100p": round(sh, 4)},
        "final_pass": final,
        "score": round(stage2w["1500p"]["edge"] + 0.2 * max(sh, 0.0), 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lottery", choices=("all",) + LOTTERIES, default="all")
    parser.add_argument("--bets", nargs="+", type=int, default=list(BETS))
    parser.add_argument("--min-train", type=int, default=300)
    parser.add_argument("--max-oos", type=int, default=500)
    parser.add_argument("--train-window", type=int, default=500)
    parser.add_argument("--n-perm", type=int, default=30)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--db-path", default=os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db"))
    parser.add_argument("--out-json", default=os.path.join(PROJECT_ROOT, "research", "s2_1_grid_gates.json"))
    parser.add_argument("--out-md", default=os.path.join(PROJECT_ROOT, "research", "s2_1_grid_gates.md"))
    args = parser.parse_args()

    lotteries = list(LOTTERIES) if args.lottery == "all" else [args.lottery]
    db = DatabaseManager(db_path=args.db_path)
    acf_path = os.path.join(PROJECT_ROOT, "research", "acf_pacf_scan_results.json")
    acf_data = json.load(open(acf_path, "r", encoding="utf-8")) if os.path.exists(acf_path) else {}

    grid = []
    for w, pair_min, div_pen, pboost in itertools.product(
        (0.55, 0.65, 0.75),
        (2, 3, 4),
        (0.12, 0.17),
        (0.20, 0.30),
    ):
        grid.append(
            {
                "w_markov2": w,
                "pair_min_count": pair_min,
                "diversity_penalty": div_pen,
                "pressure_boost": pboost,
            }
        )

    result = {
        "generated_at": datetime.now().isoformat(),
        "params": {
            "min_train": args.min_train,
            "max_oos": args.max_oos,
            "train_window": args.train_window,
            "n_perm": args.n_perm,
            "grid_size": len(grid),
            "topk": args.topk,
        },
        "runs": [],
    }

    for lt in lotteries:
        history = sorted(db.get_all_draws(lt), key=lambda x: (x["date"], x["draw"]))
        s1 = _stage1_pass(acf_data, lt)
        print(f"\n[{lt}] stage1={s1} draws={len(history)}")
        for nb in args.bets:
            if nb not in BASELINES[lt]:
                continue
            print(f"  - prescreen {nb} bets over {len(grid)} configs ...", flush=True)
            base_seed_cfg = {
                "w_markov2": 0.65,
                "pair_min_count": 3,
                "diversity_penalty": 0.17,
                "pressure_boost": 0.25,
            }
            base_ref = _run_hits(
                history,
                lt,
                nb,
                base_seed_cfg,
                args.min_train,
                args.max_oos,
                args.train_window,
                base_hits_cached=None,
            )
            cached_base_hits = base_ref["base_hits"]
            pres = []
            for cfg in grid:
                h = _run_hits(
                    history,
                    lt,
                    nb,
                    cfg,
                    args.min_train,
                    args.max_oos,
                    args.train_window,
                    base_hits_cached=cached_base_hits,
                )["new_hits"]
                ew = _edge_stats(h, BASELINES[lt][nb])
                pres.append((ew["500p"]["edge"], ew["1500p"]["edge"], cfg))
            pres.sort(key=lambda x: (x[0], x[1]), reverse=True)
            top_cfg = [x[2] for x in pres[: args.topk]]

            gate_rows = []
            for i, cfg in enumerate(top_cfg, 1):
                print(f"    top{i}: {cfg}", flush=True)
                gate = _full_gate_eval(
                    history,
                    lt,
                    nb,
                    cfg,
                    s1,
                    args.min_train,
                    args.max_oos,
                    args.train_window,
                    args.n_perm,
                    cached_base_hits,
                )
                gate_rows.append(gate)
                print(
                    f"      s2={gate['stage2']['passed']} s3={gate['stage3']['passed']} "
                    f"s4={gate['stage4']['passed']} s5={gate['stage5']['passed']} final={gate['final_pass']}"
                )

            gate_rows.sort(key=lambda x: (x["final_pass"], x["score"]), reverse=True)
            best = gate_rows[0] if gate_rows else {}
            result["runs"].append(
                {
                    "lottery_type": lt,
                    "num_bets": nb,
                    "stage1_pass": s1,
                    "best": best,
                    "top_candidates": gate_rows,
                }
            )

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    lines = [
        "# S2.1 Grid Gates Summary",
        "",
        f"- generated_at: {result['generated_at']}",
        f"- grid_size: {result['params']['grid_size']}",
        f"- topk: {result['params']['topk']}",
        "",
        "| Lottery | Bets | Stage1 | Stage2 | Stage3 | Stage4 | Stage5 | Final | Config |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in result["runs"]:
        b = run.get("best", {})
        cfg = b.get("config", {})
        cfg_s = (
            f"w={cfg.get('w_markov2')},pair={cfg.get('pair_min_count')},"
            f"div={cfg.get('diversity_penalty')},pb={cfg.get('pressure_boost')}"
        )
        lines.append(
            f"| {run['lottery_type']} | {run['num_bets']} | "
            f"{'✅' if run['stage1_pass'] else '❌'} | "
            f"{'✅' if b.get('stage2',{}).get('passed') else '❌'} | "
            f"{'✅' if b.get('stage3',{}).get('passed') else '❌'} | "
            f"{'✅' if b.get('stage4',{}).get('passed') else '❌'} | "
            f"{'✅' if b.get('stage5',{}).get('passed') else '❌'} | "
            f"{'✅' if b.get('final_pass') else '❌'} | {cfg_s} |"
        )
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    print(f"\nsaved: {args.out_json}")
    print(f"saved: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
