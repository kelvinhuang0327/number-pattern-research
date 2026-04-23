#!/usr/bin/env python3
"""
POWER_LOTTO PP3 Sum Regime / Sum Reversal validation (2026-04-23)
==================================================================

Scope:
1. Evaluate `PP3 Sum Regime` and `PP3 Sum Reversal` on:
   - 200p monitoring
   - 150 / 500 / 1500 walk-forward validation
2. Enforce leakage-first validation, permutation / Cohen's d gates,
   per-bet efficiency vs `pp3_freqort_4bet`, and conditional McNemar
   vs `fourier_rhythm_3bet`.
3. Output orchestrator-ready JSON artifacts.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import chi2

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.engine.perm_test import perm_test
from lottery_api.utils.benchmark_framework import StrategyBenchmark
from tools.backtest_power_sum_regime import get_sum_target, predict_pp3_sum_regime
from tools.backtest_power_sum_reversal_pp3 import (
    SUM_TARGET_MAX,
    SUM_TRIGGER,
    predict_pp3_sum_reversal,
)
from tools.power_fourier_rhythm import fourier_rhythm_predict
from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet

SEED = 42
N_PERM = 200
MAX_NUM = 38
PICK = 6
MATCH_TH = 3
MIN_HISTORY = 100

DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
RESULT_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_pp3_sum_regime_validation_20260423.json",
)
DIAG_PATH = os.path.join(
    PROJECT_ROOT,
    "analysis",
    "results",
    "power_pp3_sum_regime_diagnostics_20260423.json",
)
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINE_1BET = P_SINGLE
BASELINE_3BET = 1 - (1 - P_SINGLE) ** 3
BASELINE_4BET = 1 - (1 - P_SINGLE) ** 4


def now_iso_taipei() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="milliseconds")


def parse_numbers(raw) -> List[int]:
    if isinstance(raw, list):
        return [int(n) for n in raw]
    if isinstance(raw, str):
        return [int(n) for n in ast.literal_eval(raw)]
    raise TypeError(f"Unsupported numbers payload: {type(raw)!r}")


def load_draws() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(DB_QUERY, ("POWER_LOTTO",)).fetchall()
    finally:
        conn.close()

    desc_draws = [
        {
            "draw": row["draw"],
            "date": row["date"],
            "numbers": parse_numbers(row["numbers"]),
            "special": row["special"],
            "lottery_type": row["lottery_type"],
        }
        for row in rows
    ]
    return sorted(desc_draws, key=lambda d: (d["date"], d["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["POWER_LOTTO"]["strategies"]


def bernoulli_sharpe(hit_rate: float, edge: float) -> float:
    variance = max(hit_rate * (1.0 - hit_rate), 1e-9)
    return edge / math.sqrt(variance)


def validate_no_leakage(target_draw: Dict, history: Sequence[Dict]) -> None:
    if not history:
        return
    last = history[-1]
    if (last["date"], last["draw"]) >= (target_draw["date"], target_draw["draw"]):
        raise ValueError(
            f"Data leakage: history tail {last['draw']} >= target {target_draw['draw']}"
        )


def fourier_3bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return fourier_rhythm_predict(list(history), n_bets=3, window=500)


def pp3_freqort_4bet_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return generate_orthogonal_5bet(list(history))[:4]


def sum_regime_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return predict_pp3_sum_regime(list(history))


def sum_reversal_predictor(history: Sequence[Dict]) -> List[List[int]]:
    return predict_pp3_sum_reversal(list(history))


def sum_regime_meta(history: Sequence[Dict]) -> Dict:
    lo, hi, regime, mu, sigma = get_sum_target(list(history))
    recent_sums = [sum(d["numbers"][:PICK]) for d in history[-30:]] if history else []
    return {
        "regime": regime,
        "target_lo": round(float(lo), 3),
        "target_hi": round(float(hi), 3),
        "global_mean_sum": round(float(mu), 3),
        "global_sum_std": round(float(sigma), 3),
        "recent_mean_sum": round(float(np.mean(recent_sums)), 3) if recent_sums else None,
    }


def sum_reversal_meta(history: Sequence[Dict]) -> Dict:
    prev_sum = int(sum(history[-1]["numbers"][:PICK])) if history else None
    return {
        "prev_sum": prev_sum,
        "triggered": bool(prev_sum is not None and prev_sum >= SUM_TRIGGER),
        "sum_trigger": SUM_TRIGGER,
        "sum_target_max": SUM_TARGET_MAX,
    }


def evaluate_targets(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
    meta_builder: Optional[Callable[[Sequence[Dict]], Dict]] = None,
) -> Dict:
    records = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        bets = predictor(history)
        actual = set(target["numbers"])
        per_bet_hits = [len(set(bet) & actual) >= MATCH_TH for bet in bets]
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "actual": target["numbers"],
                "actual_sum": int(sum(target["numbers"][:PICK])),
                "bets": bets,
                "per_bet_hits": per_bet_hits,
                "hit": any(per_bet_hits),
                "meta": meta_builder(history) if meta_builder else None,
            }
        )
    return {
        "records": records,
        "hits": sum(1 for row in records if row["hit"]),
        "periods": len(records),
    }


def summarize_window(evaluation: Dict, baseline: float, n_bets: int) -> Dict:
    periods = evaluation["periods"]
    hits = evaluation["hits"]
    hit_rate = hits / periods if periods else 0.0
    edge = hit_rate - baseline

    per_bet_hit_rates = []
    per_bet_edges = []
    if periods:
        for bet_idx in range(n_bets):
            rate = sum(row["per_bet_hits"][bet_idx] for row in evaluation["records"]) / periods
            per_bet_hit_rates.append(rate)
            per_bet_edges.append(rate - BASELINE_1BET)

    strongest = max(per_bet_hit_rates) if per_bet_hit_rates else 0.0
    weakest = min(per_bet_hit_rates) if per_bet_hit_rates else 0.0
    efficiency_pct = (weakest / strongest * 100.0) if strongest > 0 else 0.0

    return {
        "periods": periods,
        "hits": hits,
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "per_bet_hit_rates": [round(rate, 6) for rate in per_bet_hit_rates],
        "per_bet_hit_rate_pct": [round(rate * 100.0, 2) for rate in per_bet_hit_rates],
        "per_bet_edges": [round(edge_i, 6) for edge_i in per_bet_edges],
        "per_bet_edge_pct": [round(edge_i * 100.0, 2) for edge_i in per_bet_edges],
        "within_candidate_efficiency_pct": round(efficiency_pct, 2),
        "start_draw": evaluation["records"][0]["draw"],
        "end_draw": evaluation["records"][-1]["draw"],
    }


def compare_windows(candidate: Dict, baseline: Dict) -> Dict:
    return {
        "candidate_edge_pct": candidate["edge_pct"],
        "baseline_edge_pct": baseline["edge_pct"],
        "delta_edge_pct": round(candidate["edge_pct"] - baseline["edge_pct"], 2),
        "candidate_sharpe": candidate["sharpe_bernoulli"],
        "baseline_sharpe": baseline["sharpe_bernoulli"],
        "delta_sharpe": round(candidate["sharpe_bernoulli"] - baseline["sharpe_bernoulli"], 4),
    }


def marginal_efficiency(candidate_edge: float, reference_edge: float) -> Dict:
    edge_retention_pct = (candidate_edge / reference_edge * 100.0) if reference_edge > 0 else 0.0
    per_bet_efficiency_pct = (
        (candidate_edge / 3.0) / (reference_edge / 4.0) * 100.0 if reference_edge > 0 else 0.0
    )
    return {
        "edge_retention_pct": round(edge_retention_pct, 2),
        "per_bet_efficiency_pct": round(per_bet_efficiency_pct, 2),
        "pass": per_bet_efficiency_pct > 80.0,
    }


def run_perm_window(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predict_fn: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    subset = list(draws[: target_indices[-1] + 1])
    min_history = target_indices[0]
    result = perm_test(
        history=subset,
        predict_fn=predict_fn,
        baseline=BASELINE_3BET,
        min_history=min_history,
        n_perm=N_PERM,
        seed=SEED,
        verbose=False,
    )
    if result["n_oos"] != len(target_indices):
        raise ValueError(
            f"Permutation OOS mismatch: expected {len(target_indices)}, got {result['n_oos']}"
        )
    result["real_rate_pct"] = round(result["real_rate"] * 100.0, 2)
    result["real_edge_pct"] = round(result["real_edge"] * 100.0, 2)
    result["shuffle_mean_pct"] = round(result["shuffle_mean"] * 100.0, 2)
    result["shuffle_std_pct"] = round(result["shuffle_std"] * 100.0, 2)
    return result


def mcnemar_against_fourier(
    draws: Sequence[Dict],
    target_indices: Sequence[int],
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
) -> Dict:
    candidate_hits = []
    fourier_hits = []
    for target_idx in target_indices:
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        actual = set(target["numbers"])
        candidate_bets = predictor(history)
        fourier_bets = fourier_3bet_predictor(history)
        candidate_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in candidate_bets))
        fourier_hits.append(any(len(set(bet) & actual) >= MATCH_TH for bet in fourier_bets))

    a = sum(1 for c, f in zip(candidate_hits, fourier_hits) if c and f)
    b = sum(1 for c, f in zip(candidate_hits, fourier_hits) if c and not f)
    c = sum(1 for c, f in zip(candidate_hits, fourier_hits) if not c and f)
    d = sum(1 for c, f in zip(candidate_hits, fourier_hits) if not c and not f)
    discordant = b + c
    if discordant == 0:
        return {
            "status": "IDENTICAL",
            "a": a,
            "b": b,
            "c": c,
            "d": d,
            "discordant": 0,
            "chi2": 0.0,
            "p_value": 1.0,
            "net": 0,
            "pass": False,
        }

    chi2_val = (abs(b - c) - 1) ** 2 / discordant
    p_value = float(1.0 - chi2.cdf(chi2_val, df=1))
    return {
        "status": "COMPUTED",
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "discordant": discordant,
        "chi2": round(float(chi2_val), 4),
        "p_value": round(p_value, 4),
        "net": b - c,
        "pass": p_value < 0.05,
    }


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = "PASS" if proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout else "FAIL"
    return {
        "status": status,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def benchmark_reference(
    predictor: Callable[[Sequence[Dict]], List[List[int]]],
    strategy_name: str,
    test_periods: int,
) -> Dict:
    def wrapper(history, rules):
        del rules
        return predictor(history)

    benchmark = StrategyBenchmark(lottery_type="POWER_LOTTO", test_periods=test_periods)
    result = benchmark.evaluate(
        strategy_fn=wrapper,
        strategy_name=strategy_name,
        num_bets=3,
        use_multi_seed=False,
    )
    return {
        "strategy_name": result.strategy_name,
        "test_periods": result.test_periods,
        "random_baseline_pct": round(result.random_baseline, 2),
        "win_rate_pct": round(result.win_rate, 2),
        "edge_vs_random_pct": round(result.edge_vs_random, 2),
        "roi_pct": round(result.roi, 2),
        "z_score": round(result.z_score, 3),
        "p_value": round(result.p_value, 4),
    }


def build_sum_regime_diagnostics(
    candidate_eval: Dict,
    fourier_eval: Dict,
) -> Dict:
    buckets = defaultdict(lambda: {"count": 0, "candidate_hits": 0, "fourier_hits": 0})
    for cand_row, fourier_row in zip(candidate_eval["records"], fourier_eval["records"]):
        regime = (cand_row["meta"] or {}).get("regime", "UNKNOWN")
        buckets[regime]["count"] += 1
        buckets[regime]["candidate_hits"] += int(cand_row["hit"])
        buckets[regime]["fourier_hits"] += int(fourier_row["hit"])

    rows = []
    for regime, row in buckets.items():
        count = row["count"]
        rows.append(
            {
                "regime": regime,
                "count": count,
                "candidate_hit_rate_pct": round(row["candidate_hits"] / count * 100.0, 2),
                "fourier_hit_rate_pct": round(row["fourier_hits"] / count * 100.0, 2),
                "candidate_minus_fourier_edge_pct": round(
                    (row["candidate_hits"] - row["fourier_hits"]) / count * 100.0,
                    2,
                ),
            }
        )
    rows.sort(key=lambda row: row["count"], reverse=True)
    return {"regime_buckets": rows}


def build_sum_reversal_diagnostics(
    candidate_eval: Dict,
    fourier_eval: Dict,
) -> Dict:
    buckets = defaultdict(
        lambda: {
            "count": 0,
            "candidate_hits": 0,
            "fourier_hits": 0,
            "actual_low_sum": 0,
        }
    )
    for cand_row, fourier_row in zip(candidate_eval["records"], fourier_eval["records"]):
        triggered = bool((cand_row["meta"] or {}).get("triggered"))
        key = "triggered" if triggered else "not_triggered"
        buckets[key]["count"] += 1
        buckets[key]["candidate_hits"] += int(cand_row["hit"])
        buckets[key]["fourier_hits"] += int(fourier_row["hit"])
        buckets[key]["actual_low_sum"] += int(cand_row["actual_sum"] <= SUM_TARGET_MAX)

    rows = []
    for key, row in buckets.items():
        count = row["count"]
        rows.append(
            {
                "bucket": key,
                "count": count,
                "candidate_hit_rate_pct": round(row["candidate_hits"] / count * 100.0, 2),
                "fourier_hit_rate_pct": round(row["fourier_hits"] / count * 100.0, 2),
                "candidate_minus_fourier_edge_pct": round(
                    (row["candidate_hits"] - row["fourier_hits"]) / count * 100.0,
                    2,
                ),
                "actual_sum_leq_target_pct": round(row["actual_low_sum"] / count * 100.0, 2),
            }
        )
    rows.sort(key=lambda row: row["bucket"])
    return {"trigger_buckets": rows}


def build_candidate_blockers(candidate_payload: Dict) -> List[str]:
    blockers = []
    for window_name in ("recent_150", "recent_500", "recent_1500"):
        summary = candidate_payload["formal_windows"][window_name]
        perm = candidate_payload["permutation_tests"][window_name]
        eff = candidate_payload["efficiency_vs_pp3_freqort_4bet"][window_name]
        if summary["edge"] <= 0:
            blockers.append(f"{window_name}: edge={summary['edge_pct']:+.2f}% <= 0")
        if perm["p_emp"] >= 0.05:
            blockers.append(f"{window_name}: permutation p={perm['p_emp']:.4f} >= 0.05")
        if perm["cohens_d"] <= 1.0:
            blockers.append(f"{window_name}: Cohen's d={perm['cohens_d']:.3f} <= 1.0")
        if not eff["pass"]:
            blockers.append(
                f"{window_name}: per-bet efficiency={eff['per_bet_efficiency_pct']:.1f}% <= 80%"
            )
    if candidate_payload["leakage_check"] != "PASS":
        blockers.append("leakage_check: FAIL")
    if candidate_payload["mcnemar_vs_fourier"]["status"] == "SKIPPED":
        blockers.append(
            f"mcnemar_vs_fourier: skipped ({candidate_payload['mcnemar_vs_fourier']['reason']})"
        )
    elif not candidate_payload["mcnemar_vs_fourier"].get("pass", False):
        blockers.append(
            f"mcnemar_vs_fourier: p={candidate_payload['mcnemar_vs_fourier']['p_value']:.4f} >= 0.05 "
            f"(net={candidate_payload['mcnemar_vs_fourier']['net']:+d})"
        )

    deduped = []
    for blocker in blockers:
        if blocker not in deduped:
            deduped.append(blocker)
    return deduped


def decide_candidate(
    formal_windows: Dict[str, Dict],
    permutation_tests: Dict[str, Dict],
    efficiency: Dict[str, Dict],
    monitoring_200: Dict,
    leakage_status: str,
    mcnemar_vs_fourier: Dict,
) -> Tuple[str, List[str], str]:
    edge_pass = all(formal_windows[name]["edge"] > 0 for name in formal_windows)
    perm_pass = all(permutation_tests[name]["p_emp"] < 0.05 for name in permutation_tests)
    d_pass = all(permutation_tests[name]["cohens_d"] > 1.0 for name in permutation_tests)
    efficiency_pass = all(efficiency[name]["pass"] for name in efficiency)
    leakage_pass = leakage_status == "PASS"

    reject_reasons = []
    if not leakage_pass:
        reject_reasons.append("leakage check failed")
    for window_name, summary in formal_windows.items():
        if summary["edge"] <= 0:
            reject_reasons.append(f"{window_name} edge <= 0")
    for window_name, perm in permutation_tests.items():
        if perm["p_emp"] >= 0.05:
            reject_reasons.append(f"{window_name} permutation p >= 0.05")
        if perm["cohens_d"] <= 1.0:
            reject_reasons.append(f"{window_name} Cohen's d <= 1.0")
    for window_name, eff in efficiency.items():
        if not eff["pass"]:
            reject_reasons.append(f"{window_name} per-bet efficiency <= 80%")

    if edge_pass and perm_pass and d_pass and efficiency_pass and leakage_pass:
        if mcnemar_vs_fourier.get("pass"):
            return "PASS", [], "eligible_for_replacement_review"
        reject_reasons.append("McNemar vs fourier_rhythm_3bet not significant")
        return "WATCH", reject_reasons, "keep_shadow_monitoring_only"

    watch_signal = (
        edge_pass
        and monitoring_200["edge"] > 0
        and leakage_pass
        and any(perm["p_emp"] < 0.10 for perm in permutation_tests.values())
    )
    if watch_signal:
        return "WATCH", reject_reasons, "continue monitoring; not eligible for McNemar replacement"
    return "REJECT", reject_reasons, "stop PP3 Sum family promotion and move to new Layer-1 signals"


def build_completed_markdown(payload: Dict) -> str:
    lines = [
        "# POWER_LOTTO PP3 Sum Regime / Sum Reversal validation (2026-04-23)",
        "",
        f"- Final decision: **{payload['final_decision']}**",
        f"- Leakage check: {payload['leakage_check']['status']}",
        (
            "- Repro command: "
            "`python3 tools/validate_power_pp3_sum_regime_20260423.py`"
        ),
        (
            f"- Outputs: `{os.path.relpath(RESULT_PATH, PROJECT_ROOT)}`, "
            f"`{os.path.relpath(DIAG_PATH, PROJECT_ROOT)}`"
        ),
    ]

    for candidate_name, candidate in payload["candidates"].items():
        lines.extend(
            [
                "",
                f"## {candidate_name}",
                f"- Decision: **{candidate['final_decision']}**",
                (
                    f"- 200p monitoring Edge: {candidate['monitoring_200']['edge_pct']:+.2f}% "
                    f"(vs fourier {candidate['monitoring_vs_fourier']['delta_edge_pct']:+.2f}pp)"
                ),
                (
                    f"- 150/500/1500 Edge: "
                    f"{candidate['formal_windows']['recent_150']['edge_pct']:+.2f}% / "
                    f"{candidate['formal_windows']['recent_500']['edge_pct']:+.2f}% / "
                    f"{candidate['formal_windows']['recent_1500']['edge_pct']:+.2f}%"
                ),
                (
                    f"- 150/500/1500 permutation p: "
                    f"{candidate['permutation_tests']['recent_150']['p_emp']:.4f} / "
                    f"{candidate['permutation_tests']['recent_500']['p_emp']:.4f} / "
                    f"{candidate['permutation_tests']['recent_1500']['p_emp']:.4f}"
                ),
                (
                    f"- 150/500/1500 Cohen's d: "
                    f"{candidate['permutation_tests']['recent_150']['cohens_d']:.3f} / "
                    f"{candidate['permutation_tests']['recent_500']['cohens_d']:.3f} / "
                    f"{candidate['permutation_tests']['recent_1500']['cohens_d']:.3f}"
                ),
                (
                    f"- 150/500/1500 per-bet efficiency vs pp3_freqort_4bet: "
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_150']['per_bet_efficiency_pct']:.1f}% / "
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_500']['per_bet_efficiency_pct']:.1f}% / "
                    f"{candidate['efficiency_vs_pp3_freqort_4bet']['recent_1500']['per_bet_efficiency_pct']:.1f}%"
                ),
                (
                    "- McNemar vs fourier_rhythm_3bet: "
                    + (
                        f"p={candidate['mcnemar_vs_fourier']['p_value']:.4f}, "
                        f"net={candidate['mcnemar_vs_fourier']['net']:+d}"
                        if candidate["mcnemar_vs_fourier"]["status"] == "COMPUTED"
                        else f"skipped ({candidate['mcnemar_vs_fourier']['reason']})"
                    )
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Scope decisions",
            "- WQ P2-1 was not retried because that direction is explicitly blocked after repeated environment/quota failures.",
            "- Special V3/V4 family was not retried because trusted wiki lessons already mark the family as REJECT/WATCH with persistent short-window permutation failure.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    stage0 = load_stage0_metrics()
    total_draws = len(draws)

    windows = {
        "monitoring_200": list(range(max(MIN_HISTORY, total_draws - 200), total_draws)),
        "recent_150": list(range(max(MIN_HISTORY, total_draws - 150), total_draws)),
        "recent_500": list(range(max(MIN_HISTORY, total_draws - 500), total_draws)),
        "recent_1500": list(range(max(MIN_HISTORY, total_draws - 1500), total_draws)),
    }

    leakage_check = run_leakage_check()

    candidate_specs = {
        "pp3_sum_regime_detector": {
            "predictor": sum_regime_predictor,
            "meta_builder": sum_regime_meta,
            "description": "Dynamic bet3 sum target based on rolling high/low/neutral sum regime.",
        },
        "pp3_sum_reversal_filter": {
            "predictor": sum_reversal_predictor,
            "meta_builder": sum_reversal_meta,
            "description": (
                "When previous draw sum >= 145, force bet3 toward low-sum combinations "
                f"(sum <= {SUM_TARGET_MAX})."
            ),
        },
    }

    diagnostics = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy_family": "PP3 Sum Regime / Sum Reversal",
        "seed": SEED,
        "n_perm": N_PERM,
        "windows": {
            name: {
                "draw_count": len(indices),
                "start_draw": draws[indices[0]]["draw"],
                "end_draw": draws[indices[-1]]["draw"],
            }
            for name, indices in windows.items()
        },
        "candidates": {},
    }

    candidates_payload = {}
    overall_decisions = []

    for candidate_name, spec in candidate_specs.items():
        predictor = spec["predictor"]
        meta_builder = spec["meta_builder"]

        candidate_eval = {
            name: evaluate_targets(draws, indices, predictor, meta_builder)
            for name, indices in windows.items()
        }
        fourier_eval = {
            name: evaluate_targets(draws, indices, fourier_3bet_predictor)
            for name, indices in windows.items()
        }
        pp3_ref_eval = {
            name: evaluate_targets(draws, indices, pp3_freqort_4bet_predictor)
            for name, indices in windows.items()
        }

        candidate_windows = {
            name: summarize_window(candidate_eval[name], BASELINE_3BET, 3) for name in windows
        }
        fourier_windows = {
            name: summarize_window(fourier_eval[name], BASELINE_3BET, 3) for name in windows
        }
        pp3_ref_windows = {
            name: summarize_window(pp3_ref_eval[name], BASELINE_4BET, 4) for name in windows
        }

        efficiency_vs_pp3 = {
            name: marginal_efficiency(candidate_windows[name]["edge"], pp3_ref_windows[name]["edge"])
            for name in windows
        }
        monitoring_vs_fourier = compare_windows(
            candidate_windows["monitoring_200"],
            fourier_windows["monitoring_200"],
        )
        monitoring_vs_pp3 = compare_windows(
            candidate_windows["monitoring_200"],
            pp3_ref_windows["monitoring_200"],
        )

        permutation_tests = {
            name: run_perm_window(draws, windows[name], predictor)
            for name in ("recent_150", "recent_500", "recent_1500")
        }

        gate_pass = (
            all(candidate_windows[name]["edge"] > 0 for name in ("recent_150", "recent_500", "recent_1500"))
            and all(permutation_tests[name]["p_emp"] < 0.05 for name in permutation_tests)
            and all(permutation_tests[name]["cohens_d"] > 1.0 for name in permutation_tests)
            and all(efficiency_vs_pp3[name]["pass"] for name in ("recent_150", "recent_500", "recent_1500"))
            and leakage_check["status"] == "PASS"
        )
        if gate_pass:
            mcnemar_vs_fourier = mcnemar_against_fourier(draws, windows["recent_500"], predictor)
        else:
            skip_reasons = []
            if not all(
                candidate_windows[name]["edge"] > 0 for name in ("recent_150", "recent_500", "recent_1500")
            ):
                skip_reasons.append("edge gate not fully passed")
            if not all(permutation_tests[name]["p_emp"] < 0.05 for name in permutation_tests):
                skip_reasons.append("permutation p gate not fully passed")
            if not all(permutation_tests[name]["cohens_d"] > 1.0 for name in permutation_tests):
                skip_reasons.append("Cohen's d gate not fully passed")
            if not all(
                efficiency_vs_pp3[name]["pass"] for name in ("recent_150", "recent_500", "recent_1500")
            ):
                skip_reasons.append("per-bet efficiency gate not fully passed")
            if leakage_check["status"] != "PASS":
                skip_reasons.append("leakage gate failed")
            mcnemar_vs_fourier = {
                "status": "SKIPPED",
                "reason": ", ".join(skip_reasons),
                "pass": False,
            }

        final_decision, reject_reasons, next_action = decide_candidate(
            {
                name: candidate_windows[name]
                for name in ("recent_150", "recent_500", "recent_1500")
            },
            permutation_tests,
            {name: efficiency_vs_pp3[name] for name in ("recent_150", "recent_500", "recent_1500")},
            candidate_windows["monitoring_200"],
            leakage_check["status"],
            mcnemar_vs_fourier,
        )

        benchmark_refs = {
            "candidate": benchmark_reference(predictor, candidate_name, 500),
            "fourier_rhythm_3bet": benchmark_reference(fourier_3bet_predictor, "fourier_rhythm_3bet", 500),
        }

        candidate_payload = {
            "description": spec["description"],
            "monitoring_200": candidate_windows["monitoring_200"],
            "monitoring_vs_fourier": monitoring_vs_fourier,
            "monitoring_vs_pp3_freqort_4bet": monitoring_vs_pp3,
            "formal_windows": {
                name: candidate_windows[name] for name in ("recent_150", "recent_500", "recent_1500")
            },
            "fourier_reference_windows": {
                name: fourier_windows[name] for name in windows
            },
            "pp3_freqort_4bet_reference_windows": {
                name: pp3_ref_windows[name] for name in windows
            },
            "efficiency_vs_pp3_freqort_4bet": {
                name: efficiency_vs_pp3[name] for name in windows
            },
            "permutation_tests": permutation_tests,
            "mcnemar_vs_fourier": mcnemar_vs_fourier,
            "benchmark_framework_reference_500p": benchmark_refs,
            "leakage_check": leakage_check["status"],
            "final_decision": final_decision,
            "reject_reasons": reject_reasons,
            "next_action": next_action,
        }
        candidate_payload["top_blockers"] = build_candidate_blockers(candidate_payload)

        if candidate_name == "pp3_sum_regime_detector":
            diagnostics["candidates"][candidate_name] = {
                "description": spec["description"],
                "monitoring_200": build_sum_regime_diagnostics(
                    candidate_eval["monitoring_200"],
                    fourier_eval["monitoring_200"],
                ),
                "recent_1500": build_sum_regime_diagnostics(
                    candidate_eval["recent_1500"],
                    fourier_eval["recent_1500"],
                ),
            }
        else:
            diagnostics["candidates"][candidate_name] = {
                "description": spec["description"],
                "monitoring_200": build_sum_reversal_diagnostics(
                    candidate_eval["monitoring_200"],
                    fourier_eval["monitoring_200"],
                ),
                "recent_1500": build_sum_reversal_diagnostics(
                    candidate_eval["recent_1500"],
                    fourier_eval["recent_1500"],
                ),
            }

        candidates_payload[candidate_name] = candidate_payload
        overall_decisions.append(final_decision)

    final_decision = (
        "PASS"
        if "PASS" in overall_decisions
        else ("WATCH" if "WATCH" in overall_decisions else "REJECT")
    )

    reject_reasons = []
    for candidate_name, candidate in candidates_payload.items():
        if candidate["final_decision"] != "PASS":
            reject_reasons.extend([f"{candidate_name}: {reason}" for reason in candidate["reject_reasons"]])

    if final_decision == "PASS":
        next_action = "run replacement proposal review; no production swap in this task"
    elif final_decision == "WATCH":
        next_action = "keep only as WATCH/monitoring; no replacement or family retry"
    else:
        next_action = "mark PP3 Sum family as REJECT and redirect research to non-sum, non-WQ, non-special-V3/V4 paths"

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "POWER_LOTTO",
        "strategy_family": "PP3 Sum Regime / Sum Reversal",
        "seed": SEED,
        "n_perm": N_PERM,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "benchmark_framework": "lottery_api/utils/benchmark_framework.py",
            "permutation_test": "lottery_api/engine/perm_test.py",
            "leakage_check": "tools/verify_no_data_leakage.py",
            "sum_regime_source": "tools/backtest_power_sum_regime.py",
            "sum_reversal_source": "tools/backtest_power_sum_reversal_pp3.py",
            "fourier_reference": "tools/power_fourier_rhythm.py",
            "pp3_freqort_4bet_reference": "tools/predict_power_orthogonal_5bet.py",
            "baseline_reference": "analysis/results/stage0_baseline.json",
        },
        "db_query": DB_QUERY,
        "draw_count_total": total_draws,
        "windows": {
            name: {
                "periods": len(indices),
                "start_draw": draws[indices[0]]["draw"],
                "end_draw": draws[indices[-1]]["draw"],
            }
            for name, indices in windows.items()
        },
        "baseline_reference": {
            "m3_plus_baseline_pct": round(BASELINE_3BET * 100.0, 2),
            "pp3_freqort_4bet_baseline_pct": round(BASELINE_4BET * 100.0, 2),
            "stage0_fourier_rhythm_3bet_edge_pct": stage0["fourier_rhythm_3bet"]["edge_pct"],
            "stage0_pp3_freqort_4bet_edge_pct": stage0["pp3_freqort_4bet"]["edge_pct"],
        },
        "leakage_check": leakage_check,
        "candidates": candidates_payload,
        "scope_notes": {
            "why_not_wq_p2_1": (
                "Task contract blocks Winning Quality P2-1 because that direction has already failed "
                "repeatedly from environment/quota blockage."
            ),
            "why_not_special_v3_v4_family": (
                "Trusted wiki lessons L121/L123 already mark special V3/V4 retries and adjacent family "
                "micro-tuning as non-priority after repeated REJECT/WATCH outcomes."
            ),
        },
        "final_decision": final_decision,
        "reject_reasons": reject_reasons,
        "next_action": next_action,
        "changed_files_list": [
            "tools/validate_power_pp3_sum_regime_20260423.py",
            "analysis/results/power_pp3_sum_regime_validation_20260423.json",
            "analysis/results/power_pp3_sum_regime_diagnostics_20260423.json",
        ],
    }
    payload["completed_markdown"] = build_completed_markdown(payload)
    payload["task_result_json"] = {
        "final_decision": payload["final_decision"],
        "reject_reasons": payload["reject_reasons"],
        "next_action": payload["next_action"],
        "candidates": {
            name: {
                "final_decision": row["final_decision"],
                "monitoring_200_edge_pct": row["monitoring_200"]["edge_pct"],
                "formal_edge_pct": {
                    window: row["formal_windows"][window]["edge_pct"] for window in row["formal_windows"]
                },
                "perm_p": {
                    window: row["permutation_tests"][window]["p_emp"] for window in row["permutation_tests"]
                },
                "cohens_d": {
                    window: row["permutation_tests"][window]["cohens_d"] for window in row["permutation_tests"]
                },
                "per_bet_efficiency_pct": {
                    window: row["efficiency_vs_pp3_freqort_4bet"][window]["per_bet_efficiency_pct"]
                    for window in ("recent_150", "recent_500", "recent_1500")
                },
                "mcnemar_vs_fourier": row["mcnemar_vs_fourier"],
                "reject_reasons": row["reject_reasons"],
                "next_action": row["next_action"],
            }
            for name, row in candidates_payload.items()
        },
    }

    os.makedirs(os.path.dirname(DIAG_PATH), exist_ok=True)
    with open(DIAG_PATH, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(DIAG_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
