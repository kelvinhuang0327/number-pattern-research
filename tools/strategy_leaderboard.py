#!/usr/bin/env python3
"""
Strategy leaderboard from strategy_states_*.json.

Usage:
  python3 tools/strategy_leaderboard.py
  python3 tools/strategy_leaderboard.py --lottery BIG_LOTTO --bets 2 3
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Tuple


LOTTERIES = ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539")


def _load_states(repo_root: str, lottery: str) -> Dict[str, dict]:
    candidates = [
        os.path.join(repo_root, "lottery_api", "data", f"strategy_states_{lottery}.json"),
        os.path.join(repo_root, "data", f"strategy_states_{lottery}.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    return {}


def _trend_penalty(trend: str) -> float:
    t = (trend or "STABLE").upper()
    if t == "REGIME_SHIFT":
        return 0.25
    if t == "DECELERATING":
        return 0.10
    return 0.0


def _score(s: dict) -> float:
    edge_300 = float(s.get("edge_300p", 0.0))
    edge_30 = float(s.get("edge_30p", 0.0))
    sharpe = max(float(s.get("sharpe_300p", 0.0)), 0.0)
    neg = int(s.get("consecutive_neg_30p", 0))
    alert = 1.0 if s.get("alert", False) else 0.0

    # Stability proxy: short/long consistency.
    denom = max(abs(edge_300), 0.01)
    stability = max(0.0, 1.0 - min(abs(edge_30 - edge_300) / denom, 1.0))

    raw = (edge_300 * 100.0) * 0.55 + sharpe * 100.0 * 0.25 + stability * 0.20
    penalty = _trend_penalty(str(s.get("trend", "STABLE"))) + min(neg / 20.0, 0.2) + alert * 0.2
    return raw - penalty


def _rank(states: Dict[str, dict], bet_sizes: List[int]) -> Dict[int, List[Tuple[str, dict, float]]]:
    out: Dict[int, List[Tuple[str, dict, float]]] = {}
    for b in bet_sizes:
        rows = []
        for name, s in states.items():
            if int(s.get("num_bets", -1)) != b:
                continue
            rows.append((name, s, _score(s)))
        rows.sort(key=lambda x: x[2], reverse=True)
        out[b] = rows
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lottery", choices=LOTTERIES, default=None)
    parser.add_argument("--bets", nargs="+", type=int, default=[2, 3])
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lotteries = [args.lottery] if args.lottery else list(LOTTERIES)

    for lottery in lotteries:
        states = _load_states(repo_root, lottery)
        print(f"\n=== {lottery} ===")
        if not states:
            print("No strategy states found.")
            continue

        ranked = _rank(states, args.bets)
        for b in args.bets:
            rows = ranked.get(b, [])
            print(f"  -- {b} bets --")
            if not rows:
                print("     (none)")
                continue
            for i, (name, s, score) in enumerate(rows[: args.top], 1):
                e30 = float(s.get("edge_30p", 0.0)) * 100
                e300 = float(s.get("edge_300p", 0.0)) * 100
                sharpe = float(s.get("sharpe_300p", 0.0))
                trend = s.get("trend", "STABLE")
                print(
                    f"    {i}. {name:<28} score={score:+.2f}  30p={e30:+.2f}%  "
                    f"300p={e300:+.2f}%  sharpe={sharpe:+.3f}  {trend}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
