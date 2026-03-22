"""
Winning Quality Engine
======================
Track B — 最大化中獎後的實際價值

核心功能:
  1. Popularity Score（號碼人氣估算）
  2. Split Risk（分獎風險 LOW/MED/HIGH）
  3. Payout Quality（中獎預期價值）
  4. 歷史分布基線建立

設計原則:
  - Popularity = proxy（無真實玩家資料，用啟發式模型）
  - 只有可驗證、可量化的指標才入系統
  - 不替代預測，只作為後處理濾網

2026-03-22 Created
"""
import os
import json
import sqlite3
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'lottery_v2.db'
)

# ── 彩種配置 ──────────────────────────────────────────
GAME_CONFIG = {
    'BIG_LOTTO':   {'pool': 49, 'pick': 6, 'birthday_ceil': 31},
    'POWER_LOTTO': {'pool': 38, 'pick': 6, 'birthday_ceil': 31},
    'DAILY_539':   {'pool': 39, 'pick': 5, 'birthday_ceil': 31},
}

# 人氣因子權重（啟發式，基於彩票心理學研究）
POPULARITY_WEIGHTS = {
    'birthday':    8,   # 生日號 (1-31) 加分
    'lucky_8':     5,   # 尾數8相關（台灣文化）
    'lucky_6':     3,   # 尾數6相關
    'round_num':   4,   # 整數（10, 20, 30...）
    'low_10':     10,   # 1-10 超低號（最多人選）
    'very_low_5':  5,   # 1-5 額外加成
    'high_bonus': -3,   # 40+ 高號懲罰（少人選）
    'consecutive': 3,   # 每個連號對加分
}


def _load_recent_draws(lottery_type: str, n: int = 100) -> List[List[int]]:
    """載入最近 N 期開獎號碼"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'SELECT numbers FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT ?',
        (lottery_type, n)
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for (nums_str,) in rows:
        try:
            nums = json.loads(nums_str) if isinstance(nums_str, str) else nums_str
            result.append([int(n) for n in nums])
        except Exception:
            continue
    return result


def popularity_score(numbers: List[int], lottery_type: str = 'BIG_LOTTO') -> float:
    """
    計算號碼組合的人氣分數（越高 = 越多人選 = 分獎風險越高）

    Returns: float（可為負值，代表極冷門組合）
    """
    cfg = GAME_CONFIG.get(lottery_type, GAME_CONFIG['BIG_LOTTO'])
    w = POPULARITY_WEIGHTS
    score = 0.0
    sorted_nums = sorted(numbers)

    for n in sorted_nums:
        # 低號效應（最強因子）
        if n <= 10:
            score += w['low_10']
            if n <= 5:
                score += w['very_low_5']

        # 生日號
        if n <= cfg['birthday_ceil']:
            score += w['birthday']

        # 尾數文化加成
        if n % 10 == 8:
            score += w['lucky_8']
        elif n % 10 == 6:
            score += w['lucky_6']

        # 整數偏好
        if n % 10 == 0:
            score += w['round_num']

        # 高號懲罰（大樂透 40+）
        if lottery_type == 'BIG_LOTTO' and n >= 40:
            score += w['high_bonus']

    # 連號效應（玩家喜歡連號）
    consec_pairs = sum(
        1 for i in range(len(sorted_nums) - 1)
        if sorted_nums[i + 1] - sorted_nums[i] == 1
    )
    score += consec_pairs * w['consecutive']

    return score


def split_risk_label(pop_score: float, baseline_mean: float, baseline_std: float) -> str:
    """
    根據 popularity score 相對基線判定分獎風險

    Returns: 'LOW' | 'MED' | 'HIGH'
    """
    z = (pop_score - baseline_mean) / (baseline_std + 1e-9)
    if z < -0.5:
        return 'LOW'
    elif z < 0.5:
        return 'MED'
    else:
        return 'HIGH'


def payout_quality_label(split_risk: str) -> str:
    """分獎風險 → 中獎價值等級"""
    return {'LOW': '高', 'MED': '中', 'HIGH': '低'}.get(split_risk, '中')


def compute_baseline(lottery_type: str, n: int = 300) -> Tuple[float, float]:
    """
    計算歷史 popularity score 的均值/標準差（作為比較基線）

    Returns: (mean, std)
    """
    draws = _load_recent_draws(lottery_type, n)
    if not draws:
        return (0.0, 1.0)
    scores = [popularity_score(d, lottery_type) for d in draws]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)
    return (mean, std)


def analyze(
    numbers: List[int],
    lottery_type: str = 'BIG_LOTTO',
    recent_n: int = 300,
) -> Dict:
    """
    完整 Winning Quality 分析

    Args:
        numbers: 預測號碼列表
        lottery_type: 彩種
        recent_n: 基線計算用期數

    Returns:
        dict with keys:
            pop_score, baseline_mean, baseline_std, percentile,
            split_risk, payout_quality, factors, z_score
    """
    baseline_mean, baseline_std = compute_baseline(lottery_type, recent_n)
    pop = popularity_score(numbers, lottery_type)
    z = (pop - baseline_mean) / (baseline_std + 1e-9)

    # 計算百分位
    draws = _load_recent_draws(lottery_type, recent_n)
    all_scores = [popularity_score(d, lottery_type) for d in draws]
    percentile = sum(1 for s in all_scores if s < pop) / len(all_scores) * 100 if all_scores else 50.0

    split_risk = split_risk_label(pop, baseline_mean, baseline_std)
    payout_quality = payout_quality_label(split_risk)

    # 因子拆解
    cfg = GAME_CONFIG.get(lottery_type, GAME_CONFIG['BIG_LOTTO'])
    sorted_nums = sorted(numbers)
    factors = {
        'low_nums_1_10': [n for n in sorted_nums if n <= 10],
        'birthday_nums': [n for n in sorted_nums if n <= cfg['birthday_ceil']],
        'lucky_tail_8_6': [n for n in sorted_nums if n % 10 in (6, 8)],
        'high_nums_40plus': [n for n in sorted_nums if n >= 40] if lottery_type == 'BIG_LOTTO' else [],
        'consecutive_pairs': [
            (sorted_nums[i], sorted_nums[i + 1])
            for i in range(len(sorted_nums) - 1)
            if sorted_nums[i + 1] - sorted_nums[i] == 1
        ],
    }

    return {
        'numbers': sorted_nums,
        'lottery_type': lottery_type,
        'pop_score': round(pop, 2),
        'baseline_mean': round(baseline_mean, 2),
        'baseline_std': round(baseline_std, 2),
        'z_score': round(z, 2),
        'percentile': round(percentile, 1),
        'split_risk': split_risk,
        'payout_quality': payout_quality,
        'factors': factors,
        'interpretation': _interpret(pop, baseline_mean, baseline_std, split_risk),
    }


def _interpret(pop: float, mean: float, std: float, split_risk: str) -> str:
    if split_risk == 'LOW':
        return '冷門組合：若命中頭獎，預期分獎人數少於平均，獨得或少數人分享機率高'
    elif split_risk == 'HIGH':
        return '熱門組合：此類號碼廣受歡迎，頭獎分獎風險高，獨得機率低'
    else:
        return '中性組合：分獎風險接近平均水平'


def backtest_payout_correlation(
    lottery_type: str = 'BIG_LOTTO',
    n: int = 300,
) -> Dict:
    """
    回測分析：低 popularity 期數的分獎人數分布特徵
    （使用和值/奇偶/區間分布作為 proxy）

    注意：無真實分獎注數資料，此為統計特性分析
    """
    draws = _load_recent_draws(lottery_type, n)
    if not draws:
        return {'error': 'insufficient data'}

    scores = [popularity_score(d, lottery_type) for d in draws]
    mean_score = sum(scores) / len(scores)

    low_pop = [draws[i] for i, s in enumerate(scores) if s < mean_score - 0.5 * (sum((s-mean_score)**2 for s in scores)/len(scores))**0.5]
    high_pop = [draws[i] for i, s in enumerate(scores) if s > mean_score + 0.5 * (sum((s-mean_score)**2 for s in scores)/len(scores))**0.5]

    def stats(group):
        if not group:
            return {}
        sums = [sum(d) for d in group]
        odd_counts = [sum(1 for x in d if x % 2 == 1) for d in group]
        return {
            'count': len(group),
            'sum_mean': round(sum(sums) / len(sums), 1),
            'odd_mean': round(sum(odd_counts) / len(odd_counts), 2),
        }

    return {
        'low_popularity': stats(low_pop),
        'high_popularity': stats(high_pop),
        'total_analyzed': len(draws),
        'mean_pop_score': round(mean_score, 2),
        'note': 'proxy analysis — no real split prize data available',
    }


# ── CLI 入口 ──────────────────────────────────────────
if __name__ == '__main__':
    import sys
    lottery_type = sys.argv[1] if len(sys.argv) > 1 else 'BIG_LOTTO'

    print(f'\n=== Winning Quality Baseline Analysis: {lottery_type} ===\n')
    mean, std = compute_baseline(lottery_type)
    print(f'Population Stability Index (300p):')
    print(f'  Popularity mean={mean:.2f}, std={std:.2f}')
    print()

    # 分析本期（115000037）大樂透
    if lottery_type == 'BIG_LOTTO':
        result = analyze([11, 15, 33, 38, 41, 43], lottery_type)
        print(f'115000037 [11,15,33,38,41,43]:')
        print(f'  pop_score={result["pop_score"]}')
        print(f'  z={result["z_score"]} (percentile P{result["percentile"]:.0f})')
        print(f'  split_risk={result["split_risk"]}')
        print(f'  payout_quality={result["payout_quality"]}')
        print(f'  {result["interpretation"]}')
        print(f'  factors: {result["factors"]}')
        print()

    corr = backtest_payout_correlation(lottery_type)
    print('Proxy correlation (low vs high popularity draws):')
    print(f'  Low pop:  {corr["low_popularity"]}')
    print(f'  High pop: {corr["high_popularity"]}')
    print(f'  Note: {corr["note"]}')
