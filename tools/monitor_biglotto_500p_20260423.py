#!/usr/bin/env python3
"""
BIG_LOTTO 500p monitor and downgrade-trigger diagnostics (2026-04-23).

Monitors active BIG_LOTTO maintenance-mode strategies:
  - p1_deviation_4bet
  - p1_dev_sum5bet

Shadow-only comparison:
  - regime_2bet
"""

from __future__ import annotations

import ast
import json
import math
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Sequence

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

SEED = 42
N_PERM = 200
MAX_NUM = 49
PICK = 6
MATCH_TH = 3
MIN_HISTORY = 150
DB_PATH = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
STAGE0_PATH = os.path.join(PROJECT_ROOT, "analysis", "results", "stage0_baseline.json")
LEAKAGE_TOOL = os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")
RESULT_JSON_PATH = os.path.join(
    PROJECT_ROOT, "analysis", "results", "biglotto_monitor_500p_20260423.json"
)
RESULT_MD_PATH = os.path.join(
    PROJECT_ROOT, "analysis", "results", "biglotto_monitor_500p_20260423.md"
)
DB_QUERY = (
    "SELECT draw, date, numbers, special, lottery_type "
    "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC"
)

P_SINGLE = sum(
    math.comb(PICK, m) * math.comb(MAX_NUM - PICK, PICK - m)
    for m in range(MATCH_TH, PICK + 1)
) / math.comb(MAX_NUM, PICK)
BASELINES = {n: 1.0 - (1.0 - P_SINGLE) ** n for n in range(1, 6)}

WINDOW_SPECS = [
    ("recent_150", 150),
    ("recent_500", 500),
    ("recent_1500", 1500),
]


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
        rows = conn.execute(DB_QUERY, ("BIG_LOTTO",)).fetchall()
    finally:
        conn.close()
    draws = [
        {
            "draw": row["draw"],
            "date": row["date"],
            "numbers": parse_numbers(row["numbers"]),
            "special": row["special"],
            "lottery_type": row["lottery_type"],
        }
        for row in rows
    ]
    return sorted(draws, key=lambda d: (d["date"], d["draw"]))


def load_stage0_metrics() -> Dict:
    with open(STAGE0_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["BIG_LOTTO"]["strategies"]


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


def p1_deviation_4bet_predict(history: Sequence[Dict]) -> List[List[int]]:
    from tools.backtest_p1_deviation_4bet import p1_deviation_4bet

    return p1_deviation_4bet(list(history))


def p1_dev_sum5bet_predict(history: Sequence[Dict]) -> List[List[int]]:
    from tools.quick_predict import biglotto_p1_deviation_5bet

    return [bet["numbers"] for bet in biglotto_p1_deviation_5bet(list(history))]


def regime_2bet_predict(history: Sequence[Dict]) -> List[List[int]]:
    from tools.predict_biglotto_regime import generate_regime_2bet

    return generate_regime_2bet(list(history))


def build_strategy_configs() -> Dict[str, Dict]:
    return {
        "p1_deviation_4bet": {
            "num_bets": 4,
            "predict_fn": p1_deviation_4bet_predict,
            "active": True,
            "shadow_only": False,
        },
        "p1_dev_sum5bet": {
            "num_bets": 5,
            "predict_fn": p1_dev_sum5bet_predict,
            "active": True,
            "shadow_only": False,
        },
        "regime_2bet": {
            "num_bets": 2,
            "predict_fn": regime_2bet_predict,
            "active": False,
            "shadow_only": True,
        },
    }


def evaluate_strategy(draws: Sequence[Dict], predict_fn: Callable[[Sequence[Dict]], List[List[int]]]) -> List[Dict]:
    records = []
    for target_idx in range(MIN_HISTORY, len(draws)):
        target = draws[target_idx]
        history = draws[:target_idx]
        validate_no_leakage(target, history)
        bets = predict_fn(history)
        actual = set(target["numbers"])
        per_bet_matches = [len(set(bet) & actual) for bet in bets]
        per_bet_hits = [match >= MATCH_TH for match in per_bet_matches]
        records.append(
            {
                "target_idx": target_idx,
                "draw": target["draw"],
                "date": target["date"],
                "actual": target["numbers"],
                "bets": bets,
                "per_bet_matches": per_bet_matches,
                "per_bet_hits": per_bet_hits,
                "hit": any(per_bet_hits),
            }
        )
    return records


def select_window_records(records: Sequence[Dict], periods: int) -> List[Dict]:
    if not records:
        return []
    return list(records[-periods:]) if len(records) >= periods else list(records)


def summarize_window(records: Sequence[Dict], num_bets: int, stage0: Dict) -> Dict:
    periods = len(records)
    hits = sum(1 for row in records if row["hit"])
    hit_rate = hits / periods if periods else 0.0
    baseline = BASELINES[num_bets]
    edge = hit_rate - baseline

    per_bet_hit_rates = []
    per_bet_edges = []
    for bet_idx in range(num_bets):
        bet_rate = sum(row["per_bet_hits"][bet_idx] for row in records) / periods if periods else 0.0
        per_bet_hit_rates.append(bet_rate)
        per_bet_edges.append(bet_rate - BASELINES[1])

    stage0_edge = float(stage0["edge"])
    stage0_sharpe = float(stage0["sharpe_bernoulli"])
    efficiency_ratio = (edge / stage0_edge) if stage0_edge > 0 else 0.0
    return {
        "periods": periods,
        "hits": hits,
        "hit_rate": round(hit_rate, 6),
        "hit_rate_pct": round(hit_rate * 100.0, 2),
        "baseline": round(baseline, 6),
        "baseline_pct": round(baseline * 100.0, 2),
        "edge": round(edge, 6),
        "edge_pct": round(edge * 100.0, 2),
        "sharpe_bernoulli": round(bernoulli_sharpe(hit_rate, edge), 4),
        "per_bet_hit_rates": [round(rate, 6) for rate in per_bet_hit_rates],
        "per_bet_hit_rate_pct": [round(rate * 100.0, 2) for rate in per_bet_hit_rates],
        "per_bet_edges": [round(val, 6) for val in per_bet_edges],
        "per_bet_edge_pct": [round(val * 100.0, 2) for val in per_bet_edges],
        "per_bet_efficiency": round(efficiency_ratio, 4),
        "per_bet_efficiency_pct": round(efficiency_ratio * 100.0, 2),
        "per_bet_efficiency_pass": efficiency_ratio > 0.8,
        "stage0_edge_pct": round(float(stage0["edge_pct"]), 2),
        "stage0_sharpe": round(stage0_sharpe, 4),
        "delta_vs_stage0_edge_pct": round(edge * 100.0 - float(stage0["edge_pct"]), 2),
        "delta_vs_stage0_sharpe": round(bernoulli_sharpe(hit_rate, edge) - stage0_sharpe, 4),
        "start_draw": records[0]["draw"] if records else None,
        "end_draw": records[-1]["draw"] if records else None,
    }


def run_perm_window(
    records: Sequence[Dict],
    baseline: float,
) -> Dict:
    if not records:
        raise ValueError("Cannot run permutation without records")
    actuals = np.zeros((len(records), MAX_NUM), dtype=bool)
    indexed_bets = []
    real_hits = 0
    for row_idx, rec in enumerate(records):
        for n in rec["actual"]:
            actuals[row_idx, n - 1] = True
        row_bets = [np.array([num - 1 for num in bet], dtype=int) for bet in rec["bets"]]
        indexed_bets.append(row_bets)
        if rec["hit"]:
            real_hits += 1

    def eval_edge(actual_matrix: np.ndarray) -> float:
        hits = 0
        for row_idx, row_bets in enumerate(indexed_bets):
            if any(int(np.sum(actual_matrix[row_idx, bet])) >= MATCH_TH for bet in row_bets):
                hits += 1
        return hits / len(records) - baseline

    rng = np.random.RandomState(SEED)
    real_rate = real_hits / len(records)
    real_edge = real_rate - baseline
    shuffle_edges = [eval_edge(actuals[rng.permutation(len(records))]) for _ in range(N_PERM)]
    shuffle_mean = float(np.mean(shuffle_edges))
    shuffle_std = float(np.std(shuffle_edges)) if np.std(shuffle_edges) > 0 else 1e-6
    n_greater = sum(1 for edge in shuffle_edges if edge >= real_edge)
    p_emp = (n_greater + 1) / (N_PERM + 1)
    cohens_d = (real_edge - shuffle_mean) / shuffle_std
    verdict = "SIGNAL_DETECTED" if p_emp < 0.05 else ("MARGINAL" if p_emp < 0.10 else "NO_SIGNAL")

    return {
        "n_oos": len(records),
        "real_rate": round(real_rate, 6),
        "real_rate_pct": round(real_rate * 100.0, 2),
        "real_edge": round(real_edge, 6),
        "real_edge_pct": round(real_edge * 100.0, 2),
        "shuffle_mean": round(shuffle_mean, 6),
        "shuffle_mean_pct": round(shuffle_mean * 100.0, 2),
        "shuffle_std": round(shuffle_std, 6),
        "shuffle_std_pct": round(shuffle_std * 100.0, 2),
        "p_emp": round(p_emp, 4),
        "cohens_d": round(float(cohens_d), 3),
        "z_score": round(float(cohens_d), 3),
        "verdict": verdict,
        "n_perm": N_PERM,
        "window_start_draw": records[0]["draw"],
        "window_end_draw": records[-1]["draw"],
        "shuffle_edges": [round(val * 100.0, 4) for val in shuffle_edges],
        "method": "fixed_prediction_temporal_reassignment",
    }


def lifecycle_pattern(windows: Dict[str, Dict]) -> str:
    names = [name for name, _ in WINDOW_SPECS if name in windows]
    edges = [windows[name]["edge_pct"] for name in names]
    if edges and all(edge > 0 for edge in edges):
        return "STABLE"
    if len(edges) == 3 and edges[0] > 0 and edges[1] > 0 and edges[2] <= 0:
        return "SHORT_MOMENTUM"
    if len(edges) == 3 and edges[0] <= 0 and edges[2] > 0:
        return "LATE_BLOOMER"
    return "UNSTABLE"


def build_downgrade_triggers(windows: Dict[str, Dict], permutation_tests: Dict[str, Dict]) -> List[str]:
    triggers = []
    for name, _ in WINDOW_SPECS:
        if name not in windows:
            continue
        summary = windows[name]
        perm = permutation_tests[name]
        if summary["edge"] <= 0:
            triggers.append(f"{name}: edge={summary['edge_pct']:+.2f}% <= 0")
        if perm["p_emp"] >= 0.05:
            triggers.append(f"{name}: permutation p={perm['p_emp']:.4f} >= 0.05")
        if summary["per_bet_efficiency"] <= 0.8:
            triggers.append(
                f"{name}: per-bet efficiency={summary['per_bet_efficiency_pct']:.1f}% <= 80%"
            )
    seen = []
    for trigger in triggers:
        if trigger not in seen:
            seen.append(trigger)
    return seen


def classify_final_decision(
    windows: Dict[str, Dict],
    permutation_tests: Dict[str, Dict],
    leakage_status: str,
) -> str:
    if leakage_status != "PASS":
        return "WATCH"
    triggers = build_downgrade_triggers(windows, permutation_tests)
    if triggers:
        return "DOWNGRADE_CANDIDATE"
    return "KEEP"


def run_leakage_check() -> Dict:
    proc = subprocess.run(
        [sys.executable, LEAKAGE_TOOL],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    tool_pass = proc.returncode == 0 and "✅ 所有測試案例通過" in proc.stdout
    return {
        "status": "PASS" if tool_pass else "FAIL",
        "tool": "tools/verify_no_data_leakage.py",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def internal_leakage_summary(records_by_strategy: Dict[str, List[Dict]]) -> Dict:
    try:
        for records in records_by_strategy.values():
            for row in records:
                if row["target_idx"] < MIN_HISTORY:
                    raise ValueError("target_idx below MIN_HISTORY")
        return {
            "status": "PASS",
            "checked_strategies": sorted(records_by_strategy.keys()),
            "rule": "All predictions used history[:target_idx] with target strictly after history tail.",
        }
    except Exception as exc:
        return {
            "status": "FAIL",
            "error": str(exc),
        }


def build_shadow_candidate(strategy_name: str, strategy_payload: Dict) -> Dict:
    window500 = strategy_payload["windows"]["recent_500"]
    perm500 = strategy_payload["permutation_tests"]["recent_500"]
    names = [name for name, _ in WINDOW_SPECS if name in strategy_payload["windows"]]
    edge_pass_count = sum(strategy_payload["windows"][name]["edge"] > 0 for name in names)
    perm_pass_count = sum(strategy_payload["permutation_tests"][name]["p_emp"] < 0.05 for name in names)
    efficiency_pass_count = sum(
        strategy_payload["windows"][name]["per_bet_efficiency"] > 0.8 for name in names
    )
    return {
        "rank": 1,
        "strategy": strategy_name,
        "status": "SHADOW_ONLY",
        "bet_count": strategy_payload["num_bets"],
        "score_components": {
            "positive_edge_windows": edge_pass_count,
            "permutation_pass_windows": perm_pass_count,
            "efficiency_pass_windows": efficiency_pass_count,
        },
        "recent_500": {
            "edge_pct": window500["edge_pct"],
            "sharpe": window500["sharpe_bernoulli"],
            "hit_rate_pct": window500["hit_rate_pct"],
            "permutation_p": perm500["p_emp"],
            "cohens_d": perm500["cohens_d"],
            "per_bet_efficiency_pct": window500["per_bet_efficiency_pct"],
        },
        "reason": (
            "Best available shadow comparator inside scope; still advisory only because "
            "bet count is not like-for-like with current 4/5-bet active strategies."
        ),
    }


def build_mcnemar_gate_result(active_payloads: Dict[str, Dict], shadow_payload: Dict) -> Dict:
    if any(payload["final_decision"] == "DOWNGRADE_CANDIDATE" for payload in active_payloads.values()):
        return {
            "status": "NO",
            "reason": (
                "No candidate enters next McNemar replacement validation. "
                "Only shadow `regime_2bet` was evaluated, and it is not a like-for-like "
                "replacement for 4/5-bet active slots."
            ),
            "candidate": None,
        }
    return {
        "status": "NO",
        "reason": "No downgrade trigger fired on active strategies; replacement validation is unnecessary this round.",
        "candidate": None,
    }


def build_strategy_markdown(strategy_name: str, payload: Dict) -> List[str]:
    lines = [
        f"## {strategy_name}",
        "",
        f"- Decision: **{payload['final_decision']}**",
        f"- Lifecycle pattern: **{payload['lifecycle_pattern']}**",
        f"- Downgrade triggers: {'; '.join(payload['downgrade_triggers']) if payload['downgrade_triggers'] else 'none'}",
        "",
        "| Window | Hit Rate | Edge | Sharpe | Perm p | Cohen's d | Efficiency | vs Stage0 Edge |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, periods in WINDOW_SPECS:
        if name not in payload["windows"]:
            continue
        summary = payload["windows"][name]
        perm = payload["permutation_tests"][name]
        lines.append(
            f"| {periods} | {summary['hit_rate_pct']:.2f}% | {summary['edge_pct']:+.2f}% | "
            f"{summary['sharpe_bernoulli']:+.4f} | {perm['p_emp']:.4f} | {perm['cohens_d']:+.3f} | "
            f"{summary['per_bet_efficiency_pct']:.1f}% | {summary['delta_vs_stage0_edge_pct']:+.2f}pp |"
        )
    lines.extend([""])
    return lines


def build_markdown(payload: Dict) -> str:
    active_names = [name for name, cfg in build_strategy_configs().items() if cfg["active"]]
    lines = [
        "# BIG_LOTTO 500p monitoring report (2026-04-23)",
        "",
        f"- overall_status: **{payload['overall_status']}**",
        f"- recommended_action: **{payload['recommended_action']}**",
        f"- leakage_check: **{payload['leakage_check']['status']}**",
        f"- next McNemar replacement candidate: **{payload['next_round_mcnemar_candidate']['status']}**",
        f"- rationale: {payload['next_round_mcnemar_candidate']['reason']}",
        "",
    ]
    for strategy_name in active_names:
        lines.extend(build_strategy_markdown(strategy_name, payload["strategies"][strategy_name]))
    if payload["fallback_ranking"]:
        lines.extend(
            [
                "## Shadow fallback ranking",
                "",
                "| Rank | Strategy | 500p Edge | 500p Perm p | 500p Cohen's d | Action | Reason |",
                "|---:|---|---:|---:|---:|---|---|",
            ]
        )
        for row in payload["fallback_ranking"]:
            lines.append(
                f"| {row['rank']} | {row['strategy']} | {row['recent_500']['edge_pct']:+.2f}% | "
                f"{row['recent_500']['permutation_p']:.4f} | {row['recent_500']['cohens_d']:+.3f} | "
                f"{row['status']} | {row['reason']} |"
            )
        lines.append("")
    else:
        lines.extend(["## Shadow fallback ranking", "", "- Not needed this round; both active strategies stayed above downgrade gates.", ""])

    lines.extend(
        [
            "## Handoff notes",
            "",
            f"- {payload['handoff_notes']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_completed_markdown(payload: Dict) -> str:
    active_4 = payload["strategies"]["p1_deviation_4bet"]
    active_5 = payload["strategies"]["p1_dev_sum5bet"]
    lines = [
        "# BIG_LOTTO 500p monitoring complete (2026-04-23)",
        "",
        f"- overall_status: **{payload['overall_status']}**",
        f"- recommended_action: **{payload['recommended_action']}**",
        (
            f"- p1_deviation_4bet 150/500/1500 Edge: "
            f"{active_4['windows']['recent_150']['edge_pct']:+.2f}% / "
            f"{active_4['windows']['recent_500']['edge_pct']:+.2f}% / "
            f"{active_4['windows']['recent_1500']['edge_pct']:+.2f}%"
        ),
        (
            f"- p1_dev_sum5bet 150/500/1500 Edge: "
            f"{active_5['windows']['recent_150']['edge_pct']:+.2f}% / "
            f"{active_5['windows']['recent_500']['edge_pct']:+.2f}% / "
            f"{active_5['windows']['recent_1500']['edge_pct']:+.2f}%"
        ),
        (
            f"- p1_deviation_4bet perm p: "
            f"{active_4['permutation_tests']['recent_150']['p_emp']:.4f} / "
            f"{active_4['permutation_tests']['recent_500']['p_emp']:.4f} / "
            f"{active_4['permutation_tests']['recent_1500']['p_emp']:.4f}"
        ),
        (
            f"- p1_dev_sum5bet perm p: "
            f"{active_5['permutation_tests']['recent_150']['p_emp']:.4f} / "
            f"{active_5['permutation_tests']['recent_500']['p_emp']:.4f} / "
            f"{active_5['permutation_tests']['recent_1500']['p_emp']:.4f}"
        ),
        f"- leakage_check: {payload['leakage_check']['status']}",
        f"- next McNemar replacement candidate: {payload['next_round_mcnemar_candidate']['status']} ({payload['next_round_mcnemar_candidate']['reason']})",
    ]
    if payload["fallback_ranking"]:
        row = payload["fallback_ranking"][0]
        lines.append(
            f"- shadow fallback rank #1: {row['strategy']} @ 500p edge {row['recent_500']['edge_pct']:+.2f}%, "
            f"perm p={row['recent_500']['permutation_p']:.4f}, action={row['status']}"
        )
    return "\n".join(lines)


def main() -> None:
    draws = load_draws()
    stage0 = load_stage0_metrics()
    configs = build_strategy_configs()

    formal_leakage = run_leakage_check()

    records_by_strategy = {
        name: evaluate_strategy(draws, config["predict_fn"]) for name, config in configs.items()
    }
    internal_leakage = internal_leakage_summary(records_by_strategy)
    leakage_status = (
        "PASS" if formal_leakage["status"] == "PASS" and internal_leakage["status"] == "PASS" else "FAIL"
    )

    windows_available = {}
    max_periods_available = len(next(iter(records_by_strategy.values()))) if records_by_strategy else 0
    for name, periods in WINDOW_SPECS:
        if max_periods_available >= periods:
            windows_available[name] = periods

    strategies_payload = {}
    for strategy_name, config in configs.items():
        stage0_ref = stage0[strategy_name]
        strategy_windows = {}
        strategy_permutation = {}
        for window_name, periods in windows_available.items():
            records = select_window_records(records_by_strategy[strategy_name], periods)
            strategy_windows[window_name] = summarize_window(records, config["num_bets"], stage0_ref)
            strategy_permutation[window_name] = run_perm_window(records, BASELINES[config["num_bets"]])

        final_decision = classify_final_decision(strategy_windows, strategy_permutation, leakage_status)
        strategies_payload[strategy_name] = {
            "num_bets": config["num_bets"],
            "active": config["active"],
            "shadow_only": config["shadow_only"],
            "stage0_reference": {
                "n_records": stage0_ref["n_records"],
                "edge_pct": round(float(stage0_ref["edge_pct"]), 2),
                "sharpe_bernoulli": round(float(stage0_ref["sharpe_bernoulli"]), 4),
                "hit_rate_pct": round(float(stage0_ref["hit_rate"]) * 100.0, 2),
            },
            "windows": strategy_windows,
            "permutation_tests": strategy_permutation,
            "lifecycle_pattern": lifecycle_pattern(strategy_windows),
            "downgrade_triggers": build_downgrade_triggers(strategy_windows, strategy_permutation),
            "final_decision": final_decision,
        }

    active_payloads = {
        name: payload for name, payload in strategies_payload.items() if payload["active"]
    }
    any_downgrade = any(
        payload["final_decision"] == "DOWNGRADE_CANDIDATE" for payload in active_payloads.values()
    )
    overall_status = "STABLE" if not any_downgrade else "DOWNGRADE_TRIGGERED"
    recommended_action = "MONITOR_ONLY" if not any_downgrade else "SHADOW_ONLY"

    fallback_ranking = []
    if any_downgrade:
        fallback_ranking.append(build_shadow_candidate("regime_2bet", strategies_payload["regime_2bet"]))

    next_round_mcnemar_candidate = build_mcnemar_gate_result(
        active_payloads, strategies_payload["regime_2bet"]
    )

    payload = {
        "generated_at": now_iso_taipei(),
        "lottery_type": "BIG_LOTTO",
        "monitor_type": "maintenance_mode_500p",
        "seed": SEED,
        "n_perm": N_PERM,
        "draw_count_total": len(draws),
        "windows_evaluated": windows_available,
        "source_files": {
            "db": "lottery_api/data/lottery_v2.db",
            "baseline_reference": "analysis/results/stage0_baseline.json",
            "formal_leakage_check": "tools/verify_no_data_leakage.py",
            "strategy_impl": {
                "p1_deviation_4bet": "tools/backtest_p1_deviation_4bet.py",
                "p1_dev_sum5bet": "tools/quick_predict.py",
                "regime_2bet": "tools/predict_biglotto_regime.py",
            },
        },
        "db_query": DB_QUERY,
        "baselines": {str(n): round(BASELINES[n] * 100.0, 4) for n in range(1, 6)},
        "leakage_check": {
            "status": leakage_status,
            "formal_tool": formal_leakage,
            "internal_walkforward": internal_leakage,
        },
        "strategies": strategies_payload,
        "overall_status": overall_status,
        "recommended_action": recommended_action,
        "fallback_ranking": fallback_ranking,
        "next_round_mcnemar_candidate": next_round_mcnemar_candidate,
        "handoff_notes": "wiki 無需更新",
        "changed_files_list": [
            "tools/monitor_biglotto_500p_20260423.py",
            "analysis/results/biglotto_monitor_500p_20260423.json",
            "analysis/results/biglotto_monitor_500p_20260423.md",
        ],
    }

    payload["completed_markdown"] = build_completed_markdown(payload)
    payload["task_result_json"] = {
        "overall_status": overall_status,
        "recommended_action": recommended_action,
        "leakage_check": payload["leakage_check"]["status"],
        "final_decision": {
            name: row["final_decision"] for name, row in active_payloads.items()
        },
        "edge_pct": {
            name: {window: row["edge_pct"] for window, row in payload["strategies"][name]["windows"].items()}
            for name in active_payloads
        },
        "perm_p": {
            name: {window: row["p_emp"] for window, row in payload["strategies"][name]["permutation_tests"].items()}
            for name in active_payloads
        },
        "cohens_d": {
            name: {window: row["cohens_d"] for window, row in payload["strategies"][name]["permutation_tests"].items()}
            for name in active_payloads
        },
        "per_bet_efficiency_pct": {
            name: {window: row["per_bet_efficiency_pct"] for window, row in payload["strategies"][name]["windows"].items()}
            for name in active_payloads
        },
        "fallback_ranking": fallback_ranking,
        "next_round_mcnemar_candidate": next_round_mcnemar_candidate,
    }

    markdown = build_markdown(payload)
    os.makedirs(os.path.dirname(RESULT_JSON_PATH), exist_ok=True)
    with open(RESULT_JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(RESULT_MD_PATH, "w", encoding="utf-8") as handle:
        handle.write(markdown)
        handle.write("\n")

    print(payload["completed_markdown"])
    print(f"\nSaved: {os.path.relpath(RESULT_JSON_PATH, PROJECT_ROOT)}")
    print(f"Saved: {os.path.relpath(RESULT_MD_PATH, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
