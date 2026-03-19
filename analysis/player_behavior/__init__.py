"""
Player Behavior / Split-Risk Analysis Module
==============================================
ADVISORY ONLY — does NOT predict draw outcomes.

Analyzes human number selection bias and prize split risk.
Takes already-predicted tickets as input and produces payout-quality
recommendations. Never feeds back into prediction scoring.

Usage:
    from analysis.player_behavior import analyze_tickets

    result = analyze_tickets(
        bets=[{"numbers": [3, 11, 18, 25, 34, 42]}, ...],
        lottery_type="BIG_LOTTO"
    )
"""
from .popularity_model import compute_popularity
from .split_risk import assess_split_risk
from .anti_crowd import suggest_anti_crowd
from .reporting import format_advisory, format_advisory_cli

# Game-specific configuration
GAME_CONFIG = {
    'BIG_LOTTO': {
        'max_num': 49, 'pick': 6,
        'grid_cols': 7,
        'pari_mutuel_tiers': ['頭獎', '貳獎', '參獎'],
        'fixed_tiers': ['肆獎', '伍獎', '陸獎', '柒獎', '普獎'],
        'birthday_range': 31,
    },
    'POWER_LOTTO': {
        'max_num': 38, 'pick': 6,
        'grid_cols': 7,
        'pari_mutuel_tiers': ['頭獎', '貳獎', '參獎'],
        'fixed_tiers': ['肆獎', '伍獎', '陸獎', '柒獎', '捌獎', '玖獎', '普獎'],
        'birthday_range': 31,
        'special_max': 8,
    },
    'DAILY_539': {
        'max_num': 39, 'pick': 5,
        'grid_cols': 7,
        'pari_mutuel_tiers': ['頭獎'],
        'fixed_tiers': ['貳獎', '參獎', '肆獎'],
        'birthday_range': 31,
    },
}


def analyze_tickets(bets, lottery_type):
    """
    Main entry point: analyze a list of predicted tickets for player behavior risk.

    This is a HEURISTIC model, NOT a predictive model.
    It estimates how popular a ticket pattern might be among other players,
    and therefore how much a pari-mutuel prize would be diluted.

    Args:
        bets: list of dicts, each with 'numbers' key (list of int)
        lottery_type: str, one of 'BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539'

    Returns:
        dict with per-bet analysis and overall summary
    """
    config = GAME_CONFIG.get(lottery_type)
    if not config:
        return {'error': f'Unknown lottery type: {lottery_type}', 'bets': []}

    max_num = config['max_num']
    pick = config['pick']
    analyses = []

    for bet in bets:
        numbers = sorted(bet.get('numbers', []))
        if not numbers:
            continue

        popularity = compute_popularity(numbers, max_num, pick)
        risk = assess_split_risk(popularity['popularity_score'], lottery_type)
        anti = suggest_anti_crowd(numbers, max_num, pick, popularity['popularity_score'])

        analyses.append({
            'numbers': numbers,
            'popularity': popularity,
            'split_risk': risk,
            'anti_crowd': anti,
        })

    # Overall summary
    if analyses:
        avg_score = sum(a['popularity']['popularity_score'] for a in analyses) / len(analyses)
        max_score = max(a['popularity']['popularity_score'] for a in analyses)
        highest_risk = max(
            [a['split_risk']['split_risk_level'] for a in analyses],
            key=lambda x: {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}.get(x, 0)
        )
    else:
        avg_score = 0
        max_score = 0
        highest_risk = 'LOW'

    return {
        'bets': analyses,
        'summary': {
            'avg_popularity': round(avg_score, 1),
            'max_popularity': round(max_score, 1),
            'highest_risk': highest_risk,
            'lottery_type': lottery_type,
            'n_bets': len(analyses),
        },
    }
