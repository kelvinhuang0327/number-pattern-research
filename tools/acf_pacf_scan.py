#!/usr/bin/env python3
"""
S1: ACF/PACF full scan for lottery number time series.

For each lottery type and each number:
  - Build binary series (1 if number appears in draw, else 0)
  - Compute ACF/PACF up to max_lag
  - Flag significant lags by |corr| > z / sqrt(N)

Outputs:
  - research/acf_pacf_scan_results.json
  - research/acf_pacf_scan_summary.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Dict, List

import numpy as np


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager  # noqa: E402


LOTTERY_CFG = {
    "BIG_LOTTO": {"max_num": 49},
    "POWER_LOTTO": {"max_num": 38},
    "DAILY_539": {"max_num": 39},
}


def _acf(series: np.ndarray, max_lag: int) -> List[float]:
    x = series.astype(float)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom <= 0:
        return [0.0] * max_lag
    out = []
    for lag in range(1, max_lag + 1):
        if lag >= len(x):
            out.append(0.0)
            continue
        out.append(float(np.dot(x[lag:], x[:-lag]) / denom))
    return out


def _toeplitz_from_acf(acf0_to_kminus1: np.ndarray) -> np.ndarray:
    k = len(acf0_to_kminus1)
    idx = np.abs(np.subtract.outer(np.arange(k), np.arange(k)))
    return acf0_to_kminus1[idx]


def _pacf_from_acf(acf_vals: List[float]) -> List[float]:
    """
    Compute PACF(1..k) from ACF(1..k) using Yule-Walker solve per lag.
    """
    if not acf_vals:
        return []
    r = np.array([1.0] + acf_vals, dtype=float)  # r[0..k]
    max_lag = len(acf_vals)
    out = []
    for k in range(1, max_lag + 1):
        r_toeplitz = _toeplitz_from_acf(r[:k])      # r[0..k-1]
        rhs = r[1 : k + 1]                           # r[1..k]
        try:
            phi = np.linalg.solve(r_toeplitz, rhs)
            out.append(float(phi[-1]))
        except np.linalg.LinAlgError:
            out.append(0.0)
    return out


def _binary_series(draws: List[Dict], max_num: int) -> Dict[int, np.ndarray]:
    arr = {n: np.zeros(len(draws), dtype=float) for n in range(1, max_num + 1)}
    for i, d in enumerate(draws):
        nums = set(int(x) for x in d.get("numbers", []))
        for n in nums:
            if 1 <= n <= max_num:
                arr[n][i] = 1.0
    return arr


def _scan_one_lottery(draws: List[Dict], max_num: int, max_lag: int, z_alpha: float) -> Dict:
    ser = _binary_series(draws, max_num=max_num)
    n = len(draws)
    conf = z_alpha / math.sqrt(max(n, 1))
    by_number = {}

    for num in range(1, max_num + 1):
        a = _acf(ser[num], max_lag=max_lag)
        p = _pacf_from_acf(a)
        sig_a = [{"lag": i + 1, "acf": round(v, 4)} for i, v in enumerate(a) if abs(v) > conf]
        sig_p = [{"lag": i + 1, "pacf": round(v, 4)} for i, v in enumerate(p) if abs(v) > conf]
        by_number[str(num)] = {
            "acf_values": [round(v, 4) for v in a],
            "pacf_values": [round(v, 4) for v in p],
            "significant_acf": sig_a,
            "significant_pacf": sig_p,
            "n_sig_acf": len(sig_a),
            "n_sig_pacf": len(sig_p),
            "max_abs_acf": round(max((abs(v) for v in a), default=0.0), 4),
            "max_abs_pacf": round(max((abs(v) for v in p), default=0.0), 4),
        }

    # Lottery-level summary
    ranked = []
    for k, v in by_number.items():
        score = max(v["max_abs_acf"], v["max_abs_pacf"])
        ranked.append((int(k), score, v["n_sig_acf"] + v["n_sig_pacf"]))
    ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)

    return {
        "n_draws": n,
        "max_lag": max_lag,
        "confidence_bound": round(conf, 4),
        "numbers": by_number,
        "top_signal_numbers": [
            {"number": n, "signal_strength": round(s, 4), "sig_count": c}
            for n, s, c in ranked[:10]
        ],
        "global": {
            "numbers_with_any_sig": sum(
                1 for _, v in by_number.items() if (v["n_sig_acf"] + v["n_sig_pacf"]) > 0
            ),
            "max_signal_strength": round(ranked[0][1], 4) if ranked else 0.0,
        },
    }


def _write_summary_md(path: str, results: Dict):
    lines = []
    lines.append("# ACF/PACF 全掃描摘要")
    lines.append("")
    lines.append(f"- generated_at: {results.get('generated_at')}")
    lines.append(f"- max_lag: {results.get('max_lag')}")
    lines.append(f"- z_alpha: {results.get('z_alpha')}")
    lines.append("")
    for lottery in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
        r = results.get("lotteries", {}).get(lottery, {})
        if not r:
            continue
        g = r.get("global", {})
        lines.append(f"## {lottery}")
        lines.append(f"- n_draws: {r.get('n_draws', 0)}")
        lines.append(f"- confidence_bound: {r.get('confidence_bound', 0)}")
        lines.append(
            f"- numbers_with_any_sig: {g.get('numbers_with_any_sig', 0)} / {LOTTERY_CFG[lottery]['max_num']}"
        )
        lines.append(f"- max_signal_strength: {g.get('max_signal_strength', 0)}")
        lines.append("- top_signal_numbers:")
        for x in r.get("top_signal_numbers", [])[:5]:
            lines.append(
                f"  - #{x['number']:02d} strength={x['signal_strength']:.4f} sig_count={x['sig_count']}"
            )
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-lag", type=int, default=24)
    parser.add_argument("--z-alpha", type=float, default=1.96, help="Normal critical value")
    parser.add_argument(
        "--db-path",
        default=os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db"),
    )
    parser.add_argument(
        "--out-json",
        default=os.path.join(PROJECT_ROOT, "research", "acf_pacf_scan_results.json"),
    )
    parser.add_argument(
        "--out-md",
        default=os.path.join(PROJECT_ROOT, "research", "acf_pacf_scan_summary.md"),
    )
    args = parser.parse_args()

    db = DatabaseManager(db_path=args.db_path)
    results = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "max_lag": args.max_lag,
        "z_alpha": args.z_alpha,
        "lotteries": {},
    }

    for lottery, cfg in LOTTERY_CFG.items():
        draws = db.get_all_draws(lottery)
        draws = sorted(draws, key=lambda x: (x.get("date", ""), x.get("draw", "")))
        results["lotteries"][lottery] = _scan_one_lottery(
            draws=draws,
            max_num=cfg["max_num"],
            max_lag=args.max_lag,
            z_alpha=args.z_alpha,
        )
        g = results["lotteries"][lottery]["global"]
        print(
            f"{lottery}: draws={results['lotteries'][lottery]['n_draws']} "
            f"sig_numbers={g['numbers_with_any_sig']} "
            f"max_signal={g['max_signal_strength']:.4f}"
        )

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    _write_summary_md(args.out_md, results)

    print(f"saved: {args.out_json}")
    print(f"saved: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
