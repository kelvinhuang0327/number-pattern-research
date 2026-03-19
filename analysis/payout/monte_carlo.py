"""Monte Carlo comparison of ticket selection layers."""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np


SEED = 42


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = equity_curve[0] if equity_curve else 0.0
    max_dd = 0.0
    for x in equity_curve:
        peak = max(peak, x)
        if peak > 0:
            max_dd = max(max_dd, (peak - x) / peak)
    return max_dd


def _strategy_metrics(profits: np.ndarray, initial_bankroll: float) -> Dict:
    flat = profits.reshape(-1)
    hit_mask = flat > 0
    positive_hits = flat[hit_mask]

    ruin_steps = []
    drawdowns = []
    ruined_count = 0
    for path in profits:
        equity = initial_bankroll + np.cumsum(path)
        ruined_idx = np.where(equity <= 0)[0]
        if len(ruined_idx) > 0:
            ruined_count += 1
            ruin_steps.append(int(ruined_idx[0] + 1))
        drawdowns.append(_max_drawdown(equity.tolist()))

    risk_of_ruin = ruined_count / max(len(profits), 1)
    return {
        'expected_profit_per_draw': round(float(np.mean(flat)), 4),
        'variance': round(float(np.var(flat)), 4),
        'max_drawdown': round(float(np.mean(drawdowns)), 4),
        'time_to_ruin': int(np.median(ruin_steps)) if ruin_steps else None,
        'risk_of_ruin': round(float(risk_of_ruin), 4),
        'survival_probability': round(float(1.0 - risk_of_ruin), 4),
        'payout_per_hit': round(float(np.mean(positive_hits)), 2) if len(positive_hits) else 0.0,
        'hit_rate': round(float(np.mean(hit_mask)), 6),
    }


def run_strategy_simulations(
    strategy_payloads: Dict[str, Dict],
    n_simulations: int = 1_000_000,
    initial_bankroll: float = 100_000.0,
) -> Dict:
    rng = np.random.default_rng(SEED)
    n_paths = min(5000, max(200, int(math.sqrt(n_simulations))))
    horizon = max(100, n_simulations // n_paths)
    results = {}

    for strategy_name, payload in strategy_payloads.items():
        ticket_cost = float(payload['ticket_cost'])
        tickets = payload['tickets']
        total_cost = ticket_cost * len(tickets)
        edge_boost = float(payload.get('edge_boost', 0.0))
        jackpot_prob = float(payload['jackpot_probability'])
        min_hit_prob = float(payload['threshold_hit_probability'])

        draw_profit = np.full((n_paths, horizon), -total_cost, dtype=np.float64)

        for ticket in tickets:
            quality = float(ticket.get('payout_quality_score', 0.0)) / 100.0
            prediction = float(ticket.get('prediction_score', 0.0)) / 100.0
            expected_payout = float(ticket.get('expected_payout', 0.0))
            jackpot_adj_prob = jackpot_prob * (1.0 + 0.50 * quality + edge_boost)
            jackpot_adj_prob = min(max(jackpot_adj_prob, 0.0), 0.25)

            threshold_adj_prob = min_hit_prob * (1.0 + 0.35 * prediction + edge_boost)
            threshold_adj_prob = min(max(threshold_adj_prob, jackpot_adj_prob), 0.40)

            jackpot_hits = rng.random((n_paths, horizon)) < jackpot_adj_prob
            near_hits = (~jackpot_hits) & (
                rng.random((n_paths, horizon)) < max(0.0, threshold_adj_prob - jackpot_adj_prob)
            )

            draw_profit += jackpot_hits * expected_payout
            draw_profit += near_hits * ticket_cost * (2.5 + 1.5 * prediction)

        metrics = _strategy_metrics(draw_profit, initial_bankroll)
        metrics['total_ticket_cost'] = round(total_cost, 2)
        metrics['simulations'] = int(n_paths * horizon)
        metrics['paths'] = int(n_paths)
        metrics['horizon_per_path'] = int(horizon)
        results[strategy_name] = metrics

    best_profit = max(results.items(), key=lambda kv: kv[1]['expected_profit_per_draw'])[0]
    best_survival = max(results.items(), key=lambda kv: kv[1]['survival_probability'])[0]
    best_payout = max(results.items(), key=lambda kv: kv[1]['payout_per_hit'])[0]

    return {
        'assumptions': {
            'n_simulations': int(n_simulations),
            'initial_bankroll': initial_bankroll,
            'seed': SEED,
            'note': 'Edge-adjusted Monte Carlo built on top of current strategy-state hit-rate estimates',
        },
        'strategies': results,
        'winners': {
            'highest_expected_profit_per_draw': best_profit,
            'best_long_term_survival': best_survival,
            'highest_payout_per_hit': best_payout,
        },
    }
