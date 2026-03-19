"""Portfolio selection layer for candidate tickets."""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List


def _overlap_ratio(a: List[int], b: List[int]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa | sb), 1)


def _portfolio_diversity(tickets: List[List[int]]) -> Dict:
    if len(tickets) <= 1:
        return {'avg_overlap': 0.0, 'diversity_bonus': 100.0}
    overlaps = [_overlap_ratio(a, b) for a, b in combinations(tickets, 2)]
    avg_overlap = sum(overlaps) / len(overlaps)
    return {
        'avg_overlap': round(avg_overlap, 4),
        'diversity_bonus': round(max(0.0, (1.0 - avg_overlap)) * 100.0, 2),
    }


def _candidate_score(candidate: Dict, rank_penalty: float = 0.05) -> float:
    return (
        float(candidate.get('prediction_score', 0.0))
        + float(candidate.get('payout_quality_score', 0.0))
        - float(candidate.get('rank', 1)) * rank_penalty
    )


def optimize_ticket_portfolio(
    candidates: List[Dict],
    k: int,
    max_pair_overlap: float = 0.35,
    budget_limit: float | None = None,
    min_expected_value: float | None = None,
) -> Dict:
    def _no_bet(reason: str, selected_tickets: List[Dict] | None = None) -> Dict:
        chosen = selected_tickets or []
        diversity = _portfolio_diversity([c['ticket'] for c in chosen]) if chosen else {'avg_overlap': 0.0, 'diversity_bonus': 0.0}
        return {
            'selected_tickets': chosen,
            'portfolio_score': 0.0,
            'expected_value_sum': round(sum(float(c.get('expected_value', 0.0)) for c in chosen), 4) if chosen else 0.0,
            'total_cost': round(sum(float(c.get('ticket_cost', 0.0)) for c in chosen), 2) if chosen else 0.0,
            'decision': 'NO_BET',
            'reason': reason,
            **diversity,
        }

    if not candidates:
        return _no_bet('No candidates provided')

    if len(candidates) <= k:
        selected = list(candidates)
        total_ev = sum(float(c.get('expected_value', 0.0)) for c in selected)
        if min_expected_value is not None and total_ev < min_expected_value:
            return _no_bet('Candidate set below EV floor', selected_tickets=selected)
        diversity = _portfolio_diversity([c['ticket'] for c in selected])
        score = sum(_candidate_score(c) for c in selected) + diversity['diversity_bonus']
        return {
            'selected_tickets': selected,
            'portfolio_score': round(score, 2),
            'expected_value_sum': round(total_ev, 4),
            'total_cost': round(sum(float(c.get('ticket_cost', 0.0)) for c in selected), 2),
            'decision': 'BET',
            **diversity,
            'reason': 'Candidate count already <= target size',
        }

    best = None
    best_score = float('-inf')

    for combo in combinations(candidates, k):
        tickets = [c['ticket'] for c in combo]
        pair_overlaps = [_overlap_ratio(a, b) for a, b in combinations(tickets, 2)]
        if pair_overlaps and max(pair_overlaps) > max_pair_overlap:
            continue
        total_cost = sum(float(c.get('ticket_cost', 0.0)) for c in combo)
        if budget_limit is not None and total_cost > budget_limit:
            continue
        total_ev = sum(float(c.get('expected_value', 0.0)) for c in combo)
        if min_expected_value is not None and total_ev < min_expected_value:
            continue
        diversity = _portfolio_diversity(tickets)
        prediction_edge = sum(float(c.get('prediction_score', 0.0)) for c in combo)
        payout_quality = sum(float(c.get('payout_quality_score', 0.0)) for c in combo)
        rank_penalty = sum(float(c.get('rank', 1)) * 0.05 for c in combo)
        overlap_penalty = sum(pair_overlaps) * 25.0
        ev_bonus = max(0.0, total_ev) * 0.25
        score = prediction_edge + payout_quality + diversity['diversity_bonus'] + ev_bonus - rank_penalty - overlap_penalty
        if score > best_score:
            best_score = score
            best = {
                'selected_tickets': list(combo),
                'portfolio_score': round(score, 2),
                'prediction_edge_sum': round(prediction_edge, 2),
                'payout_quality_sum': round(payout_quality, 2),
                'expected_value_sum': round(total_ev, 4),
                'total_cost': round(total_cost, 2),
                'decision': 'BET',
                **diversity,
            }

    if best is None:
        return _no_bet('No portfolio satisfies overlap, budget, and EV constraints')

    best['reason'] = 'Optimized under overlap and ranking constraints'
    return best
