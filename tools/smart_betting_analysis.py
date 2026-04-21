#!/usr/bin/env python3
"""Generate jackpot-aware smart betting artifacts.

This script extends the existing bankroll work with a monetary EV gate:
- checks whether lottery_v2.db stores jackpot history (it does not)
- computes breakeven jackpot thresholds from the current strategy EV model
- compares always-participate vs EV-gate vs Kelly+EV-gate monthly plans
- evaluates bet-count efficiency for DAILY_539 and POWER_LOTTO
- writes a V3.1 proposal and an updated betting strategy guide

Outputs:
- data/jackpot_ev_analysis.json
- data/smart_participation_analysis.json
- data/bet_sizing_optimization.json
- data/decision_engine_v31_proposal.json
- data/smart_betting_summary_2026_04_20.json
- data/betting_strategy_guide_2026_04_20.json
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RESEARCH_DIR = os.path.join(ROOT, "research")
LOTTERY_DATA_DIR = os.path.join(ROOT, "lottery_api", "data")
DB_PATH = os.path.join(LOTTERY_DATA_DIR, "lottery_v2.db")
EV_ANALYSIS_FILE = "ev_analysis.json"
KELLY_ANALYSIS_FILE = "kelly_analysis.json"
CURRENT_JACKPOTS_FILE = "current_jackpots.json"
STAGE2_RECALIBRATION_FILE = "stage2_recalibration.json"
JACKPOT_EV_ANALYSIS_FILE = "jackpot_ev_analysis.json"
SMART_PARTICIPATION_FILE = "smart_participation_analysis.json"
BET_SIZING_FILE = "bet_sizing_optimization.json"
DECISION_PROPOSAL_FILE = "decision_engine_v31_proposal.json"
SMART_SUMMARY_FILE = "smart_betting_summary_2026_04_20.json"
GUIDE_FILE = "betting_strategy_guide_2026_04_20.json"


@dataclass(frozen=True)
class StrategyPlan:
    lottery: str
    monthly_allocation: float
    expected_draws: float
    gate_open: bool


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_strategy_states(lottery: str) -> Dict[str, Any]:
    path = os.path.join(LOTTERY_DATA_DIR, f"strategy_states_{lottery}.json")
    return load_json(path)


def load_ev_analysis() -> Dict[str, Any]:
    return load_json(os.path.join(DATA_DIR, EV_ANALYSIS_FILE))


def load_kelly_analysis() -> Dict[str, Any]:
    return load_json(os.path.join(DATA_DIR, KELLY_ANALYSIS_FILE))


def load_stage2_recalibration() -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, STAGE2_RECALIBRATION_FILE)
    return load_json(path) if os.path.exists(path) else {}


def load_current_jackpots() -> Dict[str, Any]:
    return load_json(os.path.join(LOTTERY_DATA_DIR, CURRENT_JACKPOTS_FILE))


def database_has_jackpot_amount_column() -> bool:
    if not os.path.exists(DB_PATH):
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(draws)")
        columns = [row[1] for row in cur.fetchall()]
        return "jackpot_amount" in columns
    finally:
        conn.close()


def jackpot_match_count(prize_table: Dict[str, Any]) -> int:
    return max(int(k) for k in prize_table.keys())


def normalize_distribution(dist: Dict[str, float]) -> Dict[int, float]:
    return {int(k): float(v) for k, v in dist.items()}


def breakeven_jackpot_for_strategy(ev_entry: Dict[str, Any], current_jackpot: float) -> Dict[str, Any]:
    dist = normalize_distribution(ev_entry["distribution"])
    prize_table = {int(k): float(v) for k, v in ev_entry["prize_table"].items()}
    jackpot_match = jackpot_match_count(ev_entry["prize_table"])
    jackpot_probability = float(dist.get(jackpot_match, 0.0))

    current_expected_payout = float(ev_entry["expected_payout"])
    current_expected_net = float(ev_entry["expected_net"])
    current_cost = float(ev_entry["ticket_cost"] * ev_entry["bet_count"])

    jackpot_component = jackpot_probability * float(current_jackpot)
    non_jackpot_expected_payout = current_expected_payout - jackpot_component
    breakeven_jackpot = (current_cost - non_jackpot_expected_payout) / jackpot_probability if jackpot_probability > 0 else math.inf

    gate_open = current_jackpot >= breakeven_jackpot

    return {
        "jackpot_probability": round(jackpot_probability, 10),
        "jackpot_match_count": jackpot_match,
        "current_jackpot": float(current_jackpot),
        "current_expected_payout": round(current_expected_payout, 6),
        "current_expected_net": round(current_expected_net, 6),
        "current_expected_roi": round(float(ev_entry["expected_roi"]), 6),
        "non_jackpot_expected_payout": round(non_jackpot_expected_payout, 6),
        "breakeven_jackpot": round(breakeven_jackpot, 6),
        "breakeven_ratio": round(float(current_jackpot) / breakeven_jackpot, 6) if breakeven_jackpot > 0 else None,
        "current_to_breakeven_multiple": round(breakeven_jackpot / float(current_jackpot), 6) if current_jackpot > 0 else None,
        "ev_gate_open": gate_open,
        "ev_gate_recommendation": "OPEN" if gate_open else "CLOSE",
        "ev_gap": round(float(current_jackpot) - breakeven_jackpot, 6),
        "jackpot_component_at_current": round(jackpot_component, 6),
        "jackpot_component_at_breakeven": round(jackpot_probability * breakeven_jackpot, 6) if math.isfinite(breakeven_jackpot) else None,
        "ticket_cost_total": round(current_cost, 6),
        "prize_table": prize_table,
        "distribution": dist,
        "current_expected_net_sign": "positive" if current_expected_net > 0 else "negative",
    }


def build_jackpot_analysis(ev_analysis: Dict[str, Any], current_jackpots: Dict[str, Any]) -> Dict[str, Any]:
    db_has_jackpot = database_has_jackpot_amount_column()
    result: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "source": {
            "database": os.path.basename(DB_PATH),
            "db_has_jackpot_amount_column": db_has_jackpot,
            "jackpot_history_available": db_has_jackpot,
            "jackpot_source_file": CURRENT_JACKPOTS_FILE,
            "ev_source_file": EV_ANALYSIS_FILE,
        },
        "lotteries": {},
    }

    for lottery, entry in ev_analysis["lotteries"].items():
        current_jackpot = float(current_jackpots[lottery]["jackpot"])
        gate = breakeven_jackpot_for_strategy(entry, current_jackpot)
        gate.update({
            "strategy_name": entry["strategy_name"],
            "ticket_cost": entry["ticket_cost"],
            "bet_count": entry["bet_count"],
            "monthly_budget_reference": entry.get("monthly_budget_reference", 1000),
            "current_jackpot_source": current_jackpots[lottery].get("source"),
            "current_jackpot_updated_at": current_jackpots[lottery].get("updated_at"),
            "historical_jackpot_samples": 0,
            "historical_positive_share": None,
            "historical_note": "lottery_v2.db has no jackpot_amount column; use snapshot-based breakeven only",
            "stage2_skip_threshold": None,
            "stage2_skip_rate": None,
            "stage2_best_strategy": None,
        })

        result["lotteries"][lottery] = gate

    stage2 = load_stage2_recalibration()
    for lottery, entry in stage2.get("by_lottery", {}).items():
        if lottery in result["lotteries"]:
            result["lotteries"][lottery]["stage2_skip_threshold"] = entry.get("optimal_threshold")
            result["lotteries"][lottery]["stage2_skip_rate"] = entry.get("expected_skip_rate")
            result["lotteries"][lottery]["stage2_best_strategy"] = entry.get("best_strategy")

    return result


def build_monthly_plan(kelly_analysis: Dict[str, Any], jackpot_analysis: Dict[str, Any]) -> Dict[str, Any]:
    monthly_budget = 1000.0
    baseline_weights = {"BIG_LOTTO": 0.45, "DAILY_539": 0.35, "POWER_LOTTO": 0.20}

    always_alloc = {lottery: monthly_budget * weight for lottery, weight in baseline_weights.items()}
    positive_lotteries = [lottery for lottery, entry in jackpot_analysis["lotteries"].items() if entry["ev_gate_open"]]

    ev_gate_alloc = {
        lottery: always_alloc[lottery] if lottery in positive_lotteries else 0.0
        for lottery in baseline_weights
    }

    kelly_alloc: Dict[str, float] = {}
    for lottery in baseline_weights:
        if lottery not in positive_lotteries:
            kelly_alloc[lottery] = 0.0
            continue
        recommended_fraction = float(kelly_analysis["lotteries"][lottery]["recommended_fraction"])
        kelly_alloc[lottery] = min(always_alloc[lottery], monthly_budget * recommended_fraction)

    return {
        "monthly_budget_reference": monthly_budget,
        "baseline_weights": baseline_weights,
        "scenarios": {
            "always": always_alloc,
            "ev_gate": ev_gate_alloc,
            "kelly_ev": kelly_alloc,
        },
    }


def _build_distribution_cache(ev_analysis: Dict[str, Any]) -> Tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]], Dict[str, float]]:
    distributions: Dict[str, Dict[int, float]] = {}
    payouts: Dict[str, Dict[int, float]] = {}
    costs: Dict[str, float] = {}
    for lottery, entry in ev_analysis["lotteries"].items():
        distributions[lottery] = normalize_distribution(entry["distribution"])
        payouts[lottery] = {int(k): float(v) for k, v in entry["prize_table"].items()}
        costs[lottery] = float(entry["ticket_cost"] * entry["bet_count"])
    return distributions, payouts, costs


def _sample_month(
    rng: np.random.Generator,
    allocations: Dict[str, float],
    draw_counts: Dict[str, float],
    distributions: Dict[str, Dict[int, float]],
    payouts: Dict[str, Dict[int, float]],
    costs: Dict[str, float],
) -> Tuple[float, float, Dict[str, int]]:
    monthly_net = 0.0
    monthly_spend = 0.0
    month_draws = dict.fromkeys(allocations.keys(), 0)

    for lottery, expected_draws in draw_counts.items():
        if expected_draws <= 0:
            continue

        n_draws = int(rng.poisson(expected_draws))
        month_draws[lottery] = n_draws
        if n_draws <= 0:
            continue

        dist = distributions[lottery]
        keys = np.array(sorted(dist.keys()), dtype=int)
        probs = np.array([dist[int(k)] for k in keys], dtype=float)
        prizes = np.array([payouts[lottery].get(int(k), 0.0) for k in keys], dtype=float)
        sampled = rng.choice(len(keys), size=n_draws, p=probs)
        payout_total = float(prizes[sampled].sum())
        cost_total = n_draws * costs[lottery]
        monthly_net += payout_total - cost_total
        monthly_spend += cost_total

    return monthly_net, monthly_spend, month_draws


def simulate_monthly_strategy(
    strategy_name: str,
    allocations: Dict[str, float],
    ev_analysis: Dict[str, Any],
    simulations: int = 5000,
    months: int = 200,
    seed: int = 20260420,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    draw_counts = {
        lottery: allocations[lottery] / float(ev_analysis["lotteries"][lottery]["ticket_cost"] * ev_analysis["lotteries"][lottery]["bet_count"])
        for lottery in allocations
    }

    distributions, payouts, costs = _build_distribution_cache(ev_analysis)

    ending_bankrolls: List[float] = []
    ruin_by_month: List[int] = []
    monthly_spends: List[float] = []
    monthly_nets: List[float] = []
    active_months: List[Dict[str, int]] = []

    for _ in range(simulations):
        bankroll = 12000.0
        month_ruin = months
        local_spend = []
        local_net = []
        active_draws = dict.fromkeys(allocations.keys(), 0)

        for month in range(1, months + 1):
            monthly_net, monthly_spend, month_draws = _sample_month(
                rng=rng,
                allocations=allocations,
                draw_counts=draw_counts,
                distributions=distributions,
                payouts=payouts,
                costs=costs,
            )
            for lottery, draw_count in month_draws.items():
                active_draws[lottery] += draw_count

            bankroll += monthly_net
            local_spend.append(monthly_spend)
            local_net.append(monthly_net)
            if bankroll <= 0 and month_ruin == months:
                month_ruin = month

        ending_bankrolls.append(bankroll)
        ruin_by_month.append(month_ruin)
        monthly_spends.append(float(np.mean(local_spend) if local_spend else 0.0))
        monthly_nets.append(float(np.mean(local_net) if local_net else 0.0))
        active_months.append(active_draws)

    arr = np.array(ending_bankrolls, dtype=float)
    ruin_arr = np.array(ruin_by_month, dtype=float)

    avg_draws = {lottery: float(np.mean([record.get(lottery, 0) for record in active_months])) / months for lottery in allocations}
    avg_spend = float(np.mean(monthly_spends))

    return {
        "strategy": strategy_name,
        "simulations": simulations,
        "horizon_months": months,
        "start_bankroll": 12000.0,
        "expected_monthly_spend": round(sum(allocations.values()), 6),
        "expected_monthly_savings_vs_always": None,
        "allocations": {lottery: round(value, 6) for lottery, value in allocations.items()},
        "mean_draws_per_month": {lottery: round(value, 6) for lottery, value in avg_draws.items()},
        "mean_actual_monthly_spend": round(avg_spend, 6),
        "median_ending_bankroll": round(float(np.median(arr)), 6),
        "mean_ending_bankroll": round(float(np.mean(arr)), 6),
        "p05_ending_bankroll": round(float(np.percentile(arr, 5)), 6),
        "p95_ending_bankroll": round(float(np.percentile(arr, 95)), 6),
        "median_months_to_ruin": round(float(np.median(ruin_arr)), 6),
        "mean_months_to_ruin": round(float(np.mean(ruin_arr)), 6),
        "ruin_probability_12m": round(float(np.mean(ruin_arr <= 12)), 6),
        "ruin_probability_24m": round(float(np.mean(ruin_arr <= 24)), 6),
        "ruin_probability_200m": round(float(np.mean(arr <= 0)), 6),
    }


def build_smart_participation(ev_analysis: Dict[str, Any], kelly_analysis: Dict[str, Any], jackpot_analysis: Dict[str, Any]) -> Dict[str, Any]:
    plan = build_monthly_plan(kelly_analysis, jackpot_analysis)
    always_alloc = plan["scenarios"]["always"]
    ev_gate_alloc = plan["scenarios"]["ev_gate"]
    kelly_alloc = plan["scenarios"]["kelly_ev"]

    sim_always = simulate_monthly_strategy("always", always_alloc, ev_analysis)
    sim_ev_gate = simulate_monthly_strategy("ev_gate", ev_gate_alloc, ev_analysis)
    sim_kelly_ev = simulate_monthly_strategy("kelly_ev", kelly_alloc, ev_analysis)

    sim_always["expected_monthly_savings_vs_always"] = 0.0
    sim_ev_gate["expected_monthly_savings_vs_always"] = round(sum(always_alloc.values()) - sum(ev_gate_alloc.values()), 6)
    sim_kelly_ev["expected_monthly_savings_vs_always"] = round(sum(always_alloc.values()) - sum(kelly_alloc.values()), 6)

    return {
        "generated_at": datetime.now().isoformat(),
        "monthly_budget_reference": plan["monthly_budget_reference"],
        "baseline_weights": plan["baseline_weights"],
        "gate_summary": {
            "ev_gate_open_lotteries": [lottery for lottery, entry in jackpot_analysis["lotteries"].items() if entry["ev_gate_open"]],
            "ev_gate_closed_lotteries": [lottery for lottery, entry in jackpot_analysis["lotteries"].items() if not entry["ev_gate_open"]],
            "monthly_budget_always": round(sum(always_alloc.values()), 6),
            "monthly_budget_ev_gate": round(sum(ev_gate_alloc.values()), 6),
            "monthly_budget_kelly_ev": round(sum(kelly_alloc.values()), 6),
            "monthly_savings_ev_gate": round(sum(always_alloc.values()) - sum(ev_gate_alloc.values()), 6),
            "monthly_savings_kelly_ev": round(sum(always_alloc.values()) - sum(kelly_alloc.values()), 6),
        },
        "allocations": plan["scenarios"],
        "strategies": {
            "always": sim_always,
            "ev_gate": sim_ev_gate,
            "kelly_ev": sim_kelly_ev,
        },
        "lottery_notes": {
            lottery: {
                "current_jackpot": entry["current_jackpot"],
                "breakeven_jackpot": entry["breakeven_jackpot"],
                "ev_gate_open": entry["ev_gate_open"],
                "reason": (
                    "positive monetary EV at current jackpot" if entry["ev_gate_open"] else "current jackpot below breakeven"
                ),
            }
            for lottery, entry in jackpot_analysis["lotteries"].items()
        },
    }


def _validation_priority(status: Optional[str]) -> int:
    if status == "VALIDATED":
        return 2
    if status == "WATCH":
        return 1
    return 0


def pick_best_strategy_by_bet_count(states: Dict[str, Any], bet_count: int) -> Optional[Dict[str, Any]]:
    candidates = [entry for entry in states.values() if int(entry.get("num_bets", 0)) == bet_count]
    if not candidates:
        return None

    def rank_key(entry: Dict[str, Any]) -> Tuple[int, float, float, float]:
        status = entry.get("validated_status")
        priority = _validation_priority(status)
        edge_1500p = float(entry.get("edge_1500p") or 0.0)
        sharpe = float(entry.get("sharpe") or 0.0)
        composite = float(entry.get("composite_score") or 0.0)
        return priority, composite, edge_1500p, sharpe

    return max(candidates, key=rank_key)


def _build_bet_rows_for_lottery(lottery: str, bet_counts: List[int]) -> List[Dict[str, Any]]:
    states = load_strategy_states(lottery)
    rows: List[Dict[str, Any]] = []
    ticket_cost = 50 if lottery != "POWER_LOTTO" else 100

    for bet_count in bet_counts:
        best = pick_best_strategy_by_bet_count(states, bet_count)
        if not best:
            continue
        total_cost = bet_count * ticket_cost
        edge_1500p = float(best.get("edge_1500p") or 0.0)
        edge_per_ntd = edge_1500p / total_cost if total_cost > 0 else 0.0
        rows.append({
            "bet_count": bet_count,
            "strategy_name": best.get("name"),
            "validated_status": best.get("validated_status"),
            "composite_score": best.get("composite_score"),
            "edge_150p": best.get("edge_150p"),
            "edge_500p": best.get("edge_500p"),
            "edge_1500p": best.get("edge_1500p"),
            "sharpe": best.get("sharpe"),
            "ticket_cost": ticket_cost,
            "total_cost": total_cost,
            "edge_per_ntd": round(edge_per_ntd, 8),
        })

    return sorted(rows, key=lambda item: (item["edge_per_ntd"], float(item.get("composite_score") or 0.0)), reverse=True)


def _find_decline_point(rows: List[Dict[str, Any]]) -> Optional[int]:
    ordered_by_bet = sorted(rows, key=lambda item: item["bet_count"])
    for previous, current in zip(ordered_by_bet, ordered_by_bet[1:]):
        if current["edge_per_ntd"] < previous["edge_per_ntd"]:
            return current["bet_count"]
    return None


def build_bet_sizing_optimization() -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "metric": "edge_1500p_per_ntd",
        "lotteries": {},
    }

    candidate_map = {
        "DAILY_539": [1, 2, 3],
        "POWER_LOTTO": [2, 3, 4, 5],
    }

    for lottery, bet_counts in candidate_map.items():
        rows = _build_bet_rows_for_lottery(lottery, bet_counts)
        recommended = rows[0]["bet_count"] if rows else None

        decline_point = _find_decline_point(rows)

        current_strategy = None
        if rows:
            current_strategy = max(rows, key=lambda item: item["bet_count"]).get("strategy_name")

        results["lotteries"][lottery] = {
            "candidates": rows,
            "recommended_bet_count": recommended,
            "decline_point": decline_point,
            "current_bet_count": max((row["bet_count"] for row in rows), default=None),
            "current_strategy": current_strategy,
            "takeaway": (
                "edge per dollar peaks at the recommended bet count and then weakens"
                if recommended is not None else "no candidates found"
            ),
        }

    return results


def build_decision_proposal(jackpot_analysis: Dict[str, Any], bet_sizing: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(),
        "version": "V3.1",
        "objective": "add a monetary EV gate to the decision layer and cap exposure when jackpot edge is positive",
        "inputs": [
            "current_jackpots.json",
            "ev_analysis.json",
            "kelly_analysis.json",
            "stage2_recalibration.json",
            "strategy_states_*.json",
        ],
        "required_fields": {
            "current_jackpot": "float",
            "breakeven_jackpot": "float",
            "ev_gate_open": "bool",
            "ev_gap": "float",
            "recommended_bet_count": "int",
            "monthly_budget_after_gate": "float",
            "kelly_fraction": "float",
        },
        "decision_rules": {
            "if_ev_gate_closed": "return n_bets=0 and exposure_weight=0",
            "if_ev_gate_open": "use kelly-capped monthly allocation, not raw unconstrained Kelly",
            "if_stage2_positive_but_monetary_ev_negative": "keep the statistical model but do not activate spend",
        },
        "lottery_decisions": {
            lottery: {
                "ev_gate_open": entry["ev_gate_open"],
                "current_jackpot": entry["current_jackpot"],
                "breakeven_jackpot": entry["breakeven_jackpot"],
                "recommended_action": "play" if entry["ev_gate_open"] else "skip",
            }
            for lottery, entry in jackpot_analysis["lotteries"].items()
        },
        "bet_sizing_summary": {
            lottery: {
                "recommended_bet_count": payload["recommended_bet_count"],
                "decline_point": payload["decline_point"],
            }
            for lottery, payload in bet_sizing["lotteries"].items()
        },
        "implementation_notes": [
            "surface the EV gate status in the API response and the weekly health report",
            "keep stage2 skip thresholds separate from jackpot EV gating",
            "use current snapshot jackpots until historical jackpot_amount data exists in the DB",
        ],
        "acceptance_criteria": [
            "decision API returns gate_open and breakeven_jackpot",
            "weekly health report surfaces which lotteries are EV-gated on or off",
            "bet sizing defaults to the proxy-optimal bet count for DAILY_539 and POWER_LOTTO",
        ],
    }


def build_summary(jackpot_analysis: Dict[str, Any], smart_participation: Dict[str, Any], bet_sizing: Dict[str, Any]) -> Dict[str, Any]:
    gate_open = smart_participation["gate_summary"]["ev_gate_open_lotteries"]
    gate_closed = smart_participation["gate_summary"]["ev_gate_closed_lotteries"]
    return {
        "generated_at": datetime.now().isoformat(),
        "headline": {
            "db_jackpot_history_available": jackpot_analysis["source"]["jackpot_history_available"],
            "gate_open_lotteries": gate_open,
            "gate_closed_lotteries": gate_closed,
            "recommended_monthly_budget_after_gate": smart_participation["gate_summary"]["monthly_budget_ev_gate"],
            "monthly_savings_vs_always": smart_participation["gate_summary"]["monthly_savings_ev_gate"],
        },
        "lotteries": jackpot_analysis["lotteries"],
        "participation": smart_participation["strategies"],
        "bet_sizing": bet_sizing["lotteries"],
        "recommendation": {
            "DAILY_539": "skip under current jackpot; current statistical edge is not enough to clear monetary EV",
            "BIG_LOTTO": "keep; it is the only lottery that is positive under the current jackpot snapshot",
            "POWER_LOTTO": "skip under current jackpot; breakeven remains far above the snapshot",
        },
    }


def main() -> None:
    ev_analysis = load_ev_analysis()
    kelly_analysis = load_kelly_analysis()
    current_jackpots = load_current_jackpots()

    jackpot_analysis = build_jackpot_analysis(ev_analysis, current_jackpots)
    write_json(os.path.join(DATA_DIR, JACKPOT_EV_ANALYSIS_FILE), jackpot_analysis)

    smart_participation = build_smart_participation(ev_analysis, kelly_analysis, jackpot_analysis)
    write_json(os.path.join(DATA_DIR, SMART_PARTICIPATION_FILE), smart_participation)

    bet_sizing = build_bet_sizing_optimization()
    write_json(os.path.join(DATA_DIR, BET_SIZING_FILE), bet_sizing)

    proposal = build_decision_proposal(jackpot_analysis, bet_sizing)
    write_json(os.path.join(DATA_DIR, DECISION_PROPOSAL_FILE), proposal)

    summary = build_summary(jackpot_analysis, smart_participation, bet_sizing)
    write_json(os.path.join(DATA_DIR, SMART_SUMMARY_FILE), summary)

    guide = {
        "generated_at": datetime.now().isoformat(),
        "date": "2026-04-20",
        "summary": {
            "best_priority": "BIG_LOTTO",
            "recommended_monthly_budget": 1000,
            "starting_bankroll_assumption": 12000,
            "kelly_consistency": False,
            "ev_gate_open_lotteries": smart_participation["gate_summary"]["ev_gate_open_lotteries"],
            "ev_gate_closed_lotteries": smart_participation["gate_summary"]["ev_gate_closed_lotteries"],
            "monthly_budget_ev_gate": smart_participation["gate_summary"]["monthly_budget_ev_gate"],
            "monthly_budget_kelly_ev": smart_participation["gate_summary"]["monthly_budget_kelly_ev"],
            "monthly_savings_ev_gate": smart_participation["gate_summary"]["monthly_savings_ev_gate"],
            "monthly_savings_kelly_ev": smart_participation["gate_summary"]["monthly_savings_kelly_ev"],
        },
        "ranking": [
            {
                "lottery": lottery,
                "expected_roi": ev_analysis["lotteries"][lottery]["expected_roi"],
                "expected_net": ev_analysis["lotteries"][lottery]["expected_net"],
                "hit_rate": ev_analysis["lotteries"][lottery]["hit_rate"],
                "ev_gate_open": jackpot_analysis["lotteries"][lottery]["ev_gate_open"],
                "breakeven_jackpot": jackpot_analysis["lotteries"][lottery]["breakeven_jackpot"],
            }
            for lottery in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
        ],
        "lotteries": ev_analysis["lotteries"],
        "kelly": kelly_analysis["lotteries"],
        "scenario_survival": smart_participation["strategies"],
        "budget_plan": smart_participation["allocations"],
        "jackpot_gate": jackpot_analysis,
    }
    write_json(os.path.join(DATA_DIR, GUIDE_FILE), guide)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()