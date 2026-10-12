#!/usr/bin/env python3
"""
冷號事件預警模組 (Cold Cluster Alert)
======================================
用途: 偵測當前是否處於冷號集群高機率期
整合: 供 quick_predict.py 顯示冷號預警資訊

驗證結果 (2026-02-24):
  - 冷號事件(>=4冷號)歷史佔比: 0.7%
  - 分類器 Recall@0.4: 50%
  - 自適應策略 Edge: +2.43% vs PP3 +2.23%
  - McNemar p=0.606 (不顯著，不採納為策略替換)
  - 用途: 僅作為預警資訊顯示，不改變選號策略
"""
import numpy as np
from collections import Counter, defaultdict


MAX_NUM = 38
PICK = 6


def compute_cold_features(draws, idx, window=100):
    """
    計算冷號相關特徵
    
    Args:
        draws: 已排序(ASC)的開獎列表
        idx: 目標期的 index (計算 idx 之前的特徵)
        window: 頻率統計的回看窗口
    
    Returns:
        dict with feature values, or None if insufficient data
    """
    if idx < window + 5:
        return None
    
    hist = draws[idx - window:idx]
    
    freq = Counter()
    for d in hist:
        for n in d['numbers']:
            freq[n] += 1
    
    expected = window * PICK / MAX_NUM
    std_freq = np.std([freq.get(n, 0) for n in range(1, MAX_NUM + 1)])
    cold_threshold = expected - std_freq
    
    # F1: 冷號池大小
    cold_pool = [n for n in range(1, MAX_NUM + 1) if freq.get(n, 0) < cold_threshold]
    n_cold_pool = len(cold_pool)
    
    # F2: 冷號平均偏差
    cold_deviations = [freq.get(n, 0) - expected for n in cold_pool]
    avg_cold_dev = np.mean(cold_deviations) if cold_deviations else 0
    
    # F3: 近5期冷號比率
    recent5 = draws[idx-5:idx]
    cold_in_recent = sum(1 for d in recent5 for n in d['numbers'] if freq.get(n, 0) < cold_threshold)
    cold_ratio_recent = cold_in_recent / (5 * PICK)
    
    # F4: 最大 gap
    max_gap = 0
    for n in range(1, MAX_NUM + 1):
        for j in range(idx-1, max(0, idx-100), -1):
            if n in draws[j]['numbers']:
                gap = idx - j
                if gap > max_gap:
                    max_gap = gap
                break
    
    return {
        'n_cold_pool': n_cold_pool,
        'cold_pool': cold_pool,
        'avg_cold_dev': avg_cold_dev,
        'cold_ratio_recent': cold_ratio_recent,
        'max_gap': max_gap,
        'cold_threshold': cold_threshold,
        'expected_freq': expected,
    }


def cold_alert_score(draws, idx=None, window=100):
    """
    計算冷號預警分數 (0.0 ~ 1.0)
    
    Args:
        draws: 已排序(ASC)的開獎列表
        idx: 目標期 index (默認 = len(draws), 即預測下一期)
        window: 頻率統計窗口
    
    Returns:
        float: 預警分數 (>= 0.4 為預警)
    """
    if idx is None:
        idx = len(draws)
    
    feats = compute_cold_features(draws, idx, window)
    if feats is None:
        return 0.0
    
    score = 0.0
    
    # Rule 1: 冷號池 >= 12
    if feats['n_cold_pool'] >= 12:
        score += 0.3
    elif feats['n_cold_pool'] >= 10:
        score += 0.15
    
    # Rule 2: 冷號偏差很深
    if feats['avg_cold_dev'] < -5:
        score += 0.25
    elif feats['avg_cold_dev'] < -4:
        score += 0.1
    
    # Rule 3: 近期已有冷號出現
    if feats['cold_ratio_recent'] > 0.3:
        score += 0.2
    elif feats['cold_ratio_recent'] > 0.2:
        score += 0.1
    
    # Rule 4: 最大 gap 很大
    if feats['max_gap'] > 30:
        score += 0.15
    
    return min(score, 1.0)


def get_cold_alert_info(history, window=100):
    """
    取得完整冷號預警資訊 (供 quick_predict.py 使用)
    
    Args:
        history: 已排序(ASC)的開獎列表
        window: 頻率統計窗口
    
    Returns:
        dict: {
            'alert_score': float,
            'is_alert': bool,
            'cold_pool': list,
            'top_cold': list (最冷6個號碼),
            'max_gap': int,
            'message': str
        }
    """
    idx = len(history)
    score = cold_alert_score(history, idx, window)
    feats = compute_cold_features(history, idx, window)
    
    if feats is None:
        return {
            'alert_score': 0.0,
            'is_alert': False,
            'cold_pool': [],
            'top_cold': [],
            'max_gap': 0,
            'message': '數據不足，無法計算',
        }
    
    # Rank cold pool by deviation (most cold first)
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1
    
    cold_ranked = sorted(feats['cold_pool'], key=lambda n: freq.get(n, 0))
    top_cold = cold_ranked[:6]
    
    if score >= 0.6:
        msg = "⚠️ 高度冷號預警 — 冷號集群機率偏高"
    elif score >= 0.4:
        msg = "⚠️ 中度冷號預警 — 冷號累積中"
    elif score >= 0.2:
        msg = "ℹ️ 輕度冷號累積"
    else:
        msg = "✅ 正常 — 無冷號預警"
    
    return {
        'alert_score': score,
        'is_alert': score >= 0.4,
        'cold_pool': feats['cold_pool'],
        'top_cold': top_cold,
        'max_gap': feats['max_gap'],
        'n_cold_pool': feats['n_cold_pool'],
        'message': msg,
    }


if __name__ == '__main__':
    """獨立執行: 顯示當前冷號預警狀態"""
    import sys, os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
    from database import DatabaseManager
    
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    info = get_cold_alert_info(draws)
    
    print("=" * 50)
    print("  威力彩冷號預警")
    print("=" * 50)
    print(f"  最新期: {draws[-1]['draw']} ({draws[-1]['date']})")
    print(f"  預警分數: {info['alert_score']:.2f}")
    print(f"  狀態: {info['message']}")
    print(f"  冷號池: {info['n_cold_pool']}個")
    print(f"  最冷6號: {info['top_cold']}")
    print(f"  最大gap: {info['max_gap']}")
    print("=" * 50)
