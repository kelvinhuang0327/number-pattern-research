"""Expected payout engine built on top of popularity and split-risk analysis."""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List

from analysis.player_behavior.popularity_model import compute_popularity
from analysis.player_behavior.split_risk import assess_split_risk


GAME_CONFIG = {
    'BIG_LOTTO': {
        'max_num': 49,
        'pick': 6,
        'ticket_cost': 50,
        'reference_jackpot': 100_000_000,
        'estimated_active_tickets': 3_200_000,
        'crowd_scale': 2.8,
        'grid_cols': 7,
    },
    'POWER_LOTTO': {
        'max_num': 38,
        'pick': 6,
        'ticket_cost': 100,
        'reference_jackpot': 200_000_000,
        'estimated_active_tickets': 2_100_000,
        'crowd_scale': 2.5,
        'grid_cols': 7,
    },
    'DAILY_539': {
        'max_num': 39,
        'pick': 5,
        'ticket_cost': 50,
        'reference_jackpot': 8_000_000,
        'estimated_active_tickets': 900_000,
        'crowd_scale': 3.2,
        'grid_cols': 7,
    },
}

ASSUMPTION_PATH = os.path.join(os.path.dirname(__file__), 'game_assumptions.json')
GAME_ASSUMPTIONS = json.load(open(ASSUMPTION_PATH, 'r', encoding='utf-8'))
JACKPOT_OVERRIDE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'lottery_api',
    'data',
    'current_jackpots.json',
)


def _common_pattern_score(numbers: List[int], max_num: int) -> float:
    sorted_nums = sorted(numbers)
    decade_clusters = len(set((n - 1) // 10 for n in sorted_nums))
    low_ratio = sum(1 for n in sorted_nums if n <= min(31, max_num)) / max(len(sorted_nums), 1)
    tail_counts = {}
    for n in sorted_nums:
        tail = n % 10
        tail_counts[tail] = tail_counts.get(tail, 0) + 1
    max_same_tail = max(tail_counts.values()) if tail_counts else 1
    consecutive_pairs = sum(
        1 for i in range(1, len(sorted_nums)) if sorted_nums[i] == sorted_nums[i - 1] + 1
    )

    score = 0.0
    if decade_clusters <= 2:
        score += 0.30
    if low_ratio >= 0.8:
        score += 0.25
    if max_same_tail >= 2:
        score += min(0.20, 0.10 * (max_same_tail - 1))
    if consecutive_pairs >= 1:
        score += min(0.25, 0.12 * consecutive_pairs)
    return min(1.0, score)


def _jackpot_probability(max_num: int, pick: int) -> float:
    return 1.0 / math.comb(max_num, pick)


def get_game_assumptions(lottery_type: str) -> Dict:
    merged = dict(GAME_CONFIG[lottery_type])
    merged.update(GAME_ASSUMPTIONS.get(lottery_type, {}))
    return merged


def get_current_jackpot(lottery_type: str) -> Dict:
    assumptions = get_game_assumptions(lottery_type)
    payload = {
        'jackpot': assumptions['jackpot_assumption'],
        'source': 'assumption_default',
        'updated_at': None,
    }
    if os.path.exists(JACKPOT_OVERRIDE_PATH):
        try:
            overrides = json.load(open(JACKPOT_OVERRIDE_PATH, 'r', encoding='utf-8'))
            override = overrides.get(lottery_type, {})
            if 'jackpot' in override:
                payload['jackpot'] = int(override['jackpot'])
                payload['source'] = override.get('source', 'manual_override')
                payload['updated_at'] = override.get('updated_at')
        except Exception:
            pass
    return payload


def _fixed_prize_ev(lottery_type: str) -> float:
    assumptions = GAME_ASSUMPTIONS.get(lottery_type, {})
    official_prizes = assumptions.get('official_prizes')
    if not official_prizes:
        return 0.0

    max_num = GAME_CONFIG[lottery_type]['max_num']
    pick = GAME_CONFIG[lottery_type]['pick']
    total = math.comb(max_num, pick)
    non_drawn = max_num - pick
    ev = 0.0
    for match_str, prize in official_prizes.items():
        m = int(match_str)
        ways = math.comb(pick, m) * math.comb(non_drawn, pick - m)
        ev += ways / total * prize
    return ev


def expected_winners(ticket: List[int], lottery_type: str) -> Dict:
    config = get_game_assumptions(lottery_type)
    popularity = compute_popularity(
        ticket,
        max_num=config['max_num'],
        pick=config['pick'],
        grid_cols=config['grid_cols'],
    )
    split_risk = assess_split_risk(popularity['popularity_score'], lottery_type)
    pattern_score = _common_pattern_score(ticket, config['max_num'])
    jackpot_prob = _jackpot_probability(config['max_num'], config['pick'])

    # The base term estimates how many other tickets might match the same combination
    # if it wins. It stays near 1 for uncommon tickets and rises quickly for popular ones.
    popularity_factor = 1.0 + (popularity['popularity_score'] / 100.0) * config['crowd_scale']
    pattern_factor = 1.0 + pattern_score
    market_density = config['estimated_active_tickets'] * jackpot_prob
    additional_winners = market_density * popularity_factor * pattern_factor

    winners = 1.0 + additional_winners
    return {
        'expected_winners': round(winners, 4),
        'market_density': round(market_density, 6),
        'pattern_commonness': round(pattern_score, 4),
        'popularity': popularity,
        'split_risk': split_risk,
    }


def analyze_ticket_payout(ticket: List[int], lottery_type: str, jackpot: int | None = None) -> Dict:
    config = get_game_assumptions(lottery_type)
    jackpot_meta = get_current_jackpot(lottery_type)
    payout_pool = jackpot or jackpot_meta['jackpot']
    winner_info = expected_winners(ticket, lottery_type)
    exp_winners = max(winner_info['expected_winners'], 1.0)
    post_tax_pool = payout_pool * (1.0 - float(config.get('jackpot_tax_rate', 0.0)))
    exp_payout = post_tax_pool / exp_winners
    fixed_ev = _fixed_prize_ev(lottery_type)
    jackpot_prob = _jackpot_probability(config['max_num'], config['pick'])
    expected_value = fixed_ev + jackpot_prob * exp_payout - config['ticket_cost']
    breakeven_ratio = payout_pool / max(float(config.get('breakeven_jackpot', payout_pool)), 1.0)

    payout_quality = (
        0.55 * (1.0 - min(1.0, winner_info['popularity']['popularity_score'] / 100.0))
        + 0.25 * (1.0 - min(1.0, winner_info['pattern_commonness']))
        + 0.20 * min(1.0, exp_payout / max(post_tax_pool, 1.0))
    )

    return {
        'ticket': sorted(ticket),
        'expected_winners': winner_info['expected_winners'],
        'expected_payout': round(exp_payout, 2),
        'expected_value': round(expected_value, 4),
        'payout_quality_score': round(payout_quality * 100.0, 2),
        'jackpot_assumption': payout_pool,
        'jackpot_source': jackpot_meta['source'],
        'jackpot_updated_at': jackpot_meta['updated_at'],
        'breakeven_jackpot': config.get('breakeven_jackpot'),
        'breakeven_ratio': round(breakeven_ratio, 4),
        'ticket_cost': config['ticket_cost'],
        'popularity_score': winner_info['popularity']['popularity_score'],
        'split_risk_level': winner_info['split_risk']['split_risk_level'],
        'pattern_commonness': winner_info['pattern_commonness'],
        'bias_flags': winner_info['popularity']['bias_flags'],
        'is_ev_positive': expected_value >= 0.0,
    }


def analyze_ticket_set(
    tickets: List[List[int]],
    lottery_type: str,
    jackpot: int | None = None,
) -> List[Dict]:
    return [analyze_ticket_payout(ticket, lottery_type, jackpot=jackpot) for ticket in tickets]
