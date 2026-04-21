#!/usr/bin/env python3
"""Build bankroll advice from validated OOS hit rates.

This script turns the current strategy edge signals into practical bankroll
recommendations by combining:
- empirical OOS hit rates from data/strategy_oos_refresh_*.jsonl
- current jackpot anchors from lottery_api/data/current_jackpots.json
- prize tiers from the repo's payout assumptions
- Monte Carlo bankroll survival estimates

Outputs:
- data/ev_analysis.json
- data/monte_carlo_simulation.json
- data/kelly_analysis.json
- data/annual_budget_analysis.json
- data/betting_strategy_guide_2026_04_20.json
- research/bankroll_analysis.json (updated)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import numpy as np


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RESEARCH_DIR = os.path.join(ROOT, "research")
LOTTERY_DATA_DIR = os.path.join(ROOT, "lottery_api", "data")


@dataclass(frozen=True)
class LotterySpec:
    name: str
    draw_count: int
    number_space: int
    threshold: int
    ticket_cost: int
    bet_count: int
    strategy_name: str
    metric_key: str
    prize_table: Dict[int, int]


LOTTERIES: Dict[str, LotterySpec] = {
    "DAILY_539": LotterySpec(
        name="DAILY_539",
        draw_count=5,
        number_space=39,
        threshold=2,
        ticket_cost=50,
        bet_count=3,
        strategy_name="acb_markov_midfreq_3bet",
        metric_key="is_m2plus",
        prize_table={2: 80, 3: 1000, 4: 50000, 5: 8000000},
    ),
    "BIG_LOTTO": LotterySpec(
        name="BIG_LOTTO",
        draw_count=6,
        number_space=49,
        threshold=3,
        ticket_cost=50,
        bet_count=5,
        strategy_name="p1_dev_sum5bet",
        metric_key="is_m3plus",
        prize_table={3: 400, 4: 2000, 5: 300000, 6: 650000000},
    ),
    "POWER_LOTTO": LotterySpec(
        name="POWER_LOTTO",
        draw_count=6,
        number_space=38,
        threshold=3,
        ticket_cost=100,
        bet_count=5,
        strategy_name="orthogonal_5bet",
        metric_key="is_m3plus",
        prize_table={3: 100, 4: 800, 5: 40000, 6: 200000000},
    ),
}


SCENARIOS = {
    "conservative": {"monthly_budget": 500, "weights": {"BIG_LOTTO": 0.50, "DAILY_539": 0.30, "POWER_LOTTO": 0.20}},
    "balanced": {"monthly_budget": 1000, "weights": {"BIG_LOTTO": 0.45, "DAILY_539": 0.35, "POWER_LOTTO": 0.20}},
    "all_in": {"monthly_budget": 2000, "weights": {"BIG_LOTTO": 0.40, "DAILY_539": 0.35, "POWER_LOTTO": 0.25}},
}


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def comb(n: int, k: int) -> int:
    return math.comb(n, k)


def hypergeom_prob(total: int, draws: int, matches: int, k: int) -> float:
    if k < 0 or k > draws or k > matches or draws - k > total - matches:
        return 0.0
    return comb(matches, k) * comb(total - matches, draws - k) / comb(total, draws)


def exact_match_distribution(spec: LotterySpec) -> Dict[int, float]:
    return {
        k: hypergeom_prob(spec.number_space, spec.draw_count, spec.draw_count, k)
        for k in range(0, spec.draw_count + 1)
    }


def adjust_distribution(base_dist: Dict[int, float], threshold: int, empirical_hit_rate: float) -> Dict[int, float]:
    threshold_base = sum(prob for k, prob in base_dist.items() if k >= threshold)
    if threshold_base <= 0:
        return dict(base_dist)

    lift = empirical_hit_rate / threshold_base if threshold_base else 1.0
    high = {k: base_dist[k] * lift for k in base_dist if k >= threshold}
    high_sum = sum(high.values())
    if high_sum > 0.995:
        scale = 0.995 / high_sum
        high = {k: v * scale for k, v in high.items()}
        high_sum = sum(high.values())

    low_keys = [k for k in base_dist if k < threshold]
    low_base_sum = sum(base_dist[k] for k in low_keys)
    remaining = max(0.0, 1.0 - high_sum)
    adjusted = dict(high)
    for k in low_keys:
        adjusted[k] = base_dist[k] * remaining / low_base_sum if low_base_sum > 0 else 0.0
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}
    return adjusted


def distribution_expected_value(dist: Dict[int, float], prize_table: Dict[int, int]) -> float:
    return sum(dist.get(k, 0.0) * prize_table.get(k, 0) for k in dist)


def distribution_stats(dist: Dict[int, float], prize_table: Dict[int, int], ticket_cost: int, bet_count: int) -> Dict[str, float]:
    keys = sorted(dist)
    payouts = np.array([prize_table.get(k, 0) for k in keys], dtype=float)
    probs = np.array([dist[k] for k in keys], dtype=float)
    mean_payout = float(np.sum(payouts * probs))
    mean_net = mean_payout - (ticket_cost * bet_count)
    variance = float(np.sum(((payouts - mean_payout) ** 2) * probs))
    return {
        "expected_payout": mean_payout,
        "expected_net": mean_net,
        "expected_roi": mean_net / (ticket_cost * bet_count),
        "variance": variance,
    }


def empirical_hit_rate(rows: List[Dict[str, Any]], metric_key: str) -> float:
    if not rows:
        return 0.0
    hits = sum(1 for row in rows if row.get(metric_key, False))
    return hits / len(rows)


def sample_monthly_path(
    rng: np.random.Generator,
    monthly_budget: int,
    weights: Dict[str, float],
    strategy_distributions: Dict[str, Dict[int, float]],
    spec_map: Dict[str, LotterySpec],
) -> float:
    net = 0.0
    for lottery, weight in weights.items():
        spec = spec_map[lottery]
        allocation = monthly_budget * weight
        draw_cost = spec.ticket_cost * spec.bet_count
        draw_count = int(allocation // draw_cost)
        if draw_count <= 0:
            continue

        dist = strategy_distributions[lottery]
        keys = sorted(dist)
        outcomes = np.array([dist[k] for k in keys], dtype=float)
        payouts = np.array([spec.prize_table.get(k, 0) for k in keys], dtype=float)
        sampled = rng.choice(len(outcomes), size=draw_count, p=outcomes)
        monthly_payout = float(payouts[sampled].sum())
        net += monthly_payout - draw_count * draw_cost
    return net


def simulate_scenario(
    scenario_name: str,
    scenario: Dict[str, Any],
    strategy_distributions: Dict[str, Dict[int, float]],
    spec_map: Dict[str, LotterySpec],
    start_bankroll: int = 12000,
    months: int = 200,
    simulations: int = 10000,
    seed: int = 20260420,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    monthly_budget = int(scenario["monthly_budget"])
    weights = scenario["weights"]

    months_to_ruin: List[int] = []
    ending_bankrolls: List[float] = []
    for _ in range(simulations):
        bankroll = float(start_bankroll)
        month = 0
        while month < months and bankroll > 0:
            month += 1
            bankroll += sample_monthly_path(rng, monthly_budget, weights, strategy_distributions, spec_map)
        months_to_ruin.append(month if bankroll <= 0 else months)
        ending_bankrolls.append(bankroll)

    arr = np.array(ending_bankrolls, dtype=float)
    ruin = np.array(months_to_ruin, dtype=float)
    return {
        "scenario": scenario_name,
        "monthly_budget": monthly_budget,
        "start_bankroll": start_bankroll,
        "simulations": simulations,
        "horizon_months": months,
        "ruin_probability": float(np.mean(arr <= 0)),
        "ruin_probability_12m": float(np.mean(ruin <= 12)),
        "ruin_probability_24m": float(np.mean(ruin <= 24)),
        "median_months_to_ruin": float(np.median(ruin)),
        "mean_months_to_ruin": float(np.mean(ruin)),
        "p10_months_to_ruin": float(np.percentile(ruin, 10)),
        "p90_months_to_ruin": float(np.percentile(ruin, 90)),
        "median_ending_bankroll": float(np.median(arr)),
        "mean_ending_bankroll": float(np.mean(arr)),
        "p05_ending_bankroll": float(np.percentile(arr, 5)),
        "p95_ending_bankroll": float(np.percentile(arr, 95)),
    }


def build_lottery_artifacts(jackpots: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Dict[int, float]], List[tuple[str, float, float, float]]]:
    ev_analysis: Dict[str, Any] = {"generated_at": datetime.now().isoformat(), "lotteries": {}}
    kelly_analysis: Dict[str, Any] = {"generated_at": datetime.now().isoformat(), "lotteries": {}}
    strategy_distributions: Dict[str, Dict[int, float]] = {}

    for lottery, spec in LOTTERIES.items():
        rows = load_jsonl(os.path.join(DATA_DIR, f"strategy_oos_refresh_{lottery}.jsonl"))
        hit_rate = empirical_hit_rate(rows, spec.metric_key)
        base_dist = exact_match_distribution(spec)
        adjusted = adjust_distribution(base_dist, spec.threshold, hit_rate)
        strategy_distributions[lottery] = adjusted

        threshold_base = sum(prob for k, prob in base_dist.items() if k >= spec.threshold)
        expected_payout = distribution_expected_value(adjusted, spec.prize_table)
        expected_net = expected_payout - spec.ticket_cost * spec.bet_count
        expected_roi = expected_net / (spec.ticket_cost * spec.bet_count)

        baseline_expected_payout = distribution_expected_value(base_dist, spec.prize_table)
        baseline_expected_net = baseline_expected_payout - spec.ticket_cost * spec.bet_count
        baseline_expected_roi = baseline_expected_net / (spec.ticket_cost * spec.bet_count)
        stats = distribution_stats(adjusted, spec.prize_table, spec.ticket_cost, spec.bet_count)

        ev_analysis["lotteries"][lottery] = {
            "strategy_name": spec.strategy_name,
            "ticket_cost": spec.ticket_cost,
            "bet_count": spec.bet_count,
            "monthly_budget_reference": 1000,
            "hit_rate": hit_rate,
            "threshold_base_rate": threshold_base,
            "lift_vs_random": (hit_rate / threshold_base) if threshold_base else None,
            "expected_payout": round(expected_payout, 4),
            "expected_net": round(expected_net, 4),
            "expected_roi": round(expected_roi, 6),
            "baseline_expected_payout": round(baseline_expected_payout, 4),
            "baseline_expected_net": round(baseline_expected_net, 4),
            "baseline_expected_roi": round(baseline_expected_roi, 6),
            "prize_table": spec.prize_table,
            "jackpot": jackpots.get(lottery, {}).get("jackpot"),
            "distribution": {str(k): round(v, 8) for k, v in adjusted.items()},
            "baseline_distribution": {str(k): round(v, 8) for k, v in base_dist.items()},
            "stats": {k: round(v, 6) for k, v in stats.items()},
        }

        kelly_raw = 0.0 if expected_net <= 0 else expected_net / max(spec.ticket_cost * spec.bet_count, 1)
        kelly_analysis["lotteries"][lottery] = {
            "strategy_name": spec.strategy_name,
            "expected_net": round(expected_net, 4),
            "kelly_fraction_raw": round(kelly_raw, 6),
            "kelly_fraction_truncated": round(max(0.0, min(1.0, kelly_raw)), 6),
            "recommended_fraction": 0.0 if expected_net <= 0 else round(min(0.25, kelly_raw), 6),
            "current_bet_count": spec.bet_count,
            "kelly_alignment": "overbet" if expected_net <= 0 else "compatible",
        }

    ranking = sorted(
        [
            (
                lottery,
                ev_analysis["lotteries"][lottery]["expected_roi"],
                ev_analysis["lotteries"][lottery]["expected_net"],
                ev_analysis["lotteries"][lottery]["hit_rate"],
            )
            for lottery in LOTTERIES
        ],
        key=lambda item: (item[1], item[2]),
        reverse=True,
    )

    return ev_analysis, kelly_analysis, strategy_distributions, ranking


def build_portfolio_artifacts(strategy_distributions: Dict[str, Dict[int, float]]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    monte_carlo: Dict[str, Any] = {"generated_at": datetime.now().isoformat(), "scenarios": {}}
    for scenario_name, scenario in SCENARIOS.items():
        monte_carlo["scenarios"][scenario_name] = simulate_scenario(
            scenario_name=scenario_name,
            scenario=scenario,
            strategy_distributions=strategy_distributions,
            spec_map=LOTTERIES,
            start_bankroll=12000,
            months=200,
            simulations=10000,
            seed=20260420,
        )

    annual_budget: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "assumptions": {
            "start_bankroll": 12000,
            "reference_monthly_budget": 1000,
            "planning_horizon_months": 12,
        },
        "scenarios": {},
    }
    for scenario_name, scenario in SCENARIOS.items():
        mc = monte_carlo["scenarios"][scenario_name]
        monthly_budget = scenario["monthly_budget"]
        annual_budget["scenarios"][scenario_name] = {
            "monthly_budget": monthly_budget,
            "annual_budget": monthly_budget * 12,
            "expected_survival_months_median": mc["median_months_to_ruin"],
            "expected_survival_months_mean": mc["mean_months_to_ruin"],
            "prob_ruin_within_12m": mc["ruin_probability_12m"],
            "median_ending_bankroll": mc["median_ending_bankroll"],
            "mean_ending_bankroll": mc["mean_ending_bankroll"],
            "recommended_action": "cap_spend" if monthly_budget <= 1000 else "reduce_spend",
        }

    return monte_carlo, annual_budget


def main() -> None:
    today = datetime.now().strftime("%Y_%m_%d")

    jackpots = load_json(os.path.join(LOTTERY_DATA_DIR, "current_jackpots.json"))
    ev_analysis, kelly_analysis, strategy_distributions, ranking = build_lottery_artifacts(jackpots)
    monte_carlo, annual_budget = build_portfolio_artifacts(strategy_distributions)

    guide = {
        "generated_at": datetime.now().isoformat(),
        "date": today.replace("_", "-"),
        "summary": {
            "best_priority": ranking[0][0],
            "recommended_monthly_budget": 1000,
            "starting_bankroll_assumption": 12000,
            "kelly_consistency": False,
        },
        "ranking": [
            {
                "lottery": lottery,
                "expected_roi": roi,
                "expected_net": net,
                "hit_rate": hit_rate,
            }
            for lottery, roi, net, hit_rate in ranking
        ],
        "lotteries": ev_analysis["lotteries"],
        "kelly": kelly_analysis["lotteries"],
        "scenario_survival": monte_carlo["scenarios"],
        "budget_plan": annual_budget,
    }

    bankroll_path = os.path.join(RESEARCH_DIR, "bankroll_analysis.json")
    legacy = load_json(bankroll_path) if os.path.exists(bankroll_path) else {}
    legacy["last_updated"] = guide["generated_at"]
    legacy["ev_analysis"] = ev_analysis["lotteries"]
    legacy["monte_carlo"] = monte_carlo["scenarios"]
    legacy["kelly_analysis"] = kelly_analysis["lotteries"]
    legacy["annual_budget_analysis"] = annual_budget["scenarios"]
    legacy["recommendation"] = {
        "priority_order": [row[0] for row in ranking],
        "recommended_monthly_budget": 1000,
        "starting_bankroll_assumption": 12000,
        "kelly_fraction": 0.0,
    }

    write_json(os.path.join(DATA_DIR, "ev_analysis.json"), ev_analysis)
    write_json(os.path.join(DATA_DIR, "monte_carlo_simulation.json"), monte_carlo)
    write_json(os.path.join(DATA_DIR, "kelly_analysis.json"), kelly_analysis)
    write_json(os.path.join(DATA_DIR, "annual_budget_analysis.json"), annual_budget)
    write_json(os.path.join(DATA_DIR, f"betting_strategy_guide_{today}.json"), guide)
    write_json(bankroll_path, legacy)

    print(json.dumps(guide, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()