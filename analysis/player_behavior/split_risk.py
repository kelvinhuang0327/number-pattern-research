"""
Split Risk Assessment — Prize Dilution Analysis
=================================================
HEURISTIC model — NOT a predictive model.

Maps popularity scores to split-risk levels, considering which prize
tiers are pari-mutuel (shared among winners) vs fixed payout.
"""
from typing import Dict

# Prize structure per game
PRIZE_STRUCTURE = {
    'BIG_LOTTO': {
        'pari_mutuel': ['頭獎 (6中6)', '貳獎 (5中+特)', '參獎 (5中5)'],
        'fixed': ['肆獎 (4中+特) ~5K', '伍獎 (4中4) ~1K', '陸獎 (3中+特) ~400',
                  '柒獎 (3中3) ~400', '普獎 (2中+特) ~200'],
    },
    'POWER_LOTTO': {
        'pari_mutuel': ['頭獎 (6中6+特)', '貳獎 (6中6)', '參獎 (5中+特)'],
        'fixed': ['肆獎 (5中5) ~20K', '伍獎 (4中+特) ~4K', '陸獎 (4中4) ~800',
                  '柒獎 (3中+特) ~400', '捌獎 (2中+特) ~200',
                  '玖獎 (3中3) ~100', '普獎 (1中+特) ~100'],
    },
    'DAILY_539': {
        'pari_mutuel': ['頭獎 (5中5) ~8M'],
        'fixed': ['貳獎 (4中4) 20K', '參獎 (3中3) 300', '肆獎 (2中2) 50'],
    },
}

# Thresholds for risk levels
RISK_THRESHOLDS = {
    'LOW': (0, 30),
    'MEDIUM': (30, 60),
    'HIGH': (60, 100),
}


def assess_split_risk(popularity_score: float, lottery_type: str) -> Dict:
    """
    Assess prize split risk based on popularity score.

    This is ADVISORY ONLY. It estimates how many other winners might
    share a pari-mutuel prize if this ticket hits.

    Args:
        popularity_score: 0-100 from compute_popularity()
        lottery_type: game identifier

    Returns:
        dict with split_risk_level, affected tiers, and qualitative description
    """
    # Determine risk level
    if popularity_score < RISK_THRESHOLDS['MEDIUM'][0]:
        level = 'LOW'
    elif popularity_score < RISK_THRESHOLDS['HIGH'][0]:
        level = 'MEDIUM'
    else:
        level = 'HIGH'

    prize_info = PRIZE_STRUCTURE.get(lottery_type, {})
    pari_tiers = prize_info.get('pari_mutuel', [])
    fixed_tiers = prize_info.get('fixed', [])

    # Qualitative dilution description
    descriptions = {
        'LOW': '低分裂風險 — 此組合較不常見，中獎獎金稀釋機率較低',
        'MEDIUM': '中等分裂風險 — 此組合有部分常見特徵，頭獎可能需與他人分享',
        'HIGH': '高分裂風險 — 此組合符合多項常見選號模式，頭獎大幅稀釋機率高',
    }

    return {
        'split_risk_level': level,
        'pari_mutuel_tiers': pari_tiers,
        'fixed_tiers': fixed_tiers,
        'expected_dilution': descriptions[level],
        'popularity_score': round(popularity_score, 1),
    }
