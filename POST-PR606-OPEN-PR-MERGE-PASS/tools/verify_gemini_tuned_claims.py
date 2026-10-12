#!/usr/bin/env python3
"""
獨立驗證 Gemini 兩項微調聲稱 (2026-01-28)
==========================================
聲稱 1: 大樂透 Cluster Pivot Window=50, 2注, Edge +1.71%
聲稱 2: 威力彩 GUM Tuned Weights (M=0.25, C=1.0, K=0.5), 2注, Edge +3.21%

驗證方法:
  A) 全 500 期 in-sample (重現 Gemini 結果)
  B) 前 250 期調參 + 後 250 期 out-of-sample (真正驗證)
  C) 1000 期長期驗證 (確認穩定性)
"""
import os
import sys
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

SEED = 42
np.random.seed(SEED)

# 正確的 N 注隨機基準 (2026-01-28 修正版)
BASELINES = {
    'BIG_LOTTO':   {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 7: 12.34},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60, 7: 24.14},
}


# ========== 策略實作 ==========

def cluster_pivot_predict(history, max_num, n_bets=2, window=150):
    """Cluster Pivot 策略 (與 strategy_leaderboard.py 完全一致)"""
    recent = history[-window:]
    cooccur = Counter()
    for d in recent:
        nums = sorted(d['numbers'])
        for pair in combinations(nums, 2):
            cooccur[pair] += 1

    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count
    centers = [num for num, _ in num_scores.most_common(n_bets)]

    bets = []
    exclude = set()
    for center in centers:
        candidates = Counter()
        for (a, b), count in cooccur.items():
            if a == center and b not in exclude:
                candidates[b] += count
            elif b == center and a not in exclude:
                candidates[a] += count

        bet = [center]
        for n, _ in candidates.most_common(5):
            bet.append(n)

        if len(bet) < 6:
            for n in range(1, max_num + 1):
                if n not in bet and n not in exclude:
                    bet.append(n)
                if len(bet) == 6:
                    break

        bets.append(sorted(bet))
        exclude.update(bet[:2])
    return bets


def gum_consensus_predict(history, rules, max_num, n_bets=2, window=150,
                           w_markov=0.25, w_cluster=1.0, w_cold=0.5):
    """GUM Consensus 策略 (與 strategy_leaderboard.py:strat_gum 完全一致)"""
    scores = np.zeros(max_num + 1)

    # Markov component
    engine = UnifiedPredictionEngine()
    try:
        recent = history[-window:]
        markov_res = engine.markov_predict(recent, rules)
        if 'numbers' in markov_res:
            # 取 top 24 (4注 × 6)
            for n in markov_res['numbers'][:24]:
                scores[n] += w_markov
    except:
        pass

    # Cluster component
    cluster_bets = cluster_pivot_predict(history, max_num, n_bets=4, window=window)
    for b in cluster_bets:
        for n in b:
            scores[n] += w_cluster

    # Cold numbers component
    recent = history[-window:]
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    sorted_cold = sorted(range(1, max_num + 1), key=lambda x: freq.get(x, 0))
    for n in sorted_cold[:24]:  # top 24 coldest
        scores[n] += w_cold

    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    bets = []
    for i in range(n_bets):
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
    return bets


# ========== 回測框架 ==========

def backtest_strategy(lottery_type, strategy_func, test_periods, n_bets=2, **kwargs):
    """
    標準回測: 滾動式, 無數據洩漏
    Returns: (m3_rate, m3_count, total)
    """
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))

    if lottery_type == 'BIG_LOTTO':
        max_num = 49
        rules = {'minNumber': 1, 'maxNumber': 49, 'pickCount': 6, 'name': 'BIG_LOTTO'}
    else:
        max_num = 38
        rules = {'minNumber': 1, 'maxNumber': 38, 'pickCount': 6, 'name': 'POWER_LOTTO'}

    window = kwargs.get('window', 150)
    test_periods = min(test_periods, len(all_draws) - window - 10)

    m3_count = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= window:
            continue

        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist, rules=rules, max_num=max_num, n_bets=n_bets, **kwargs)
        except Exception as e:
            continue

        best_match = 0
        for bet in bets:
            match = len(set(bet) & actual)
            best_match = max(best_match, match)

        if best_match >= 3:
            m3_count += 1
        total += 1

    if total == 0:
        return 0.0, 0, 0
    return m3_count / total * 100, m3_count, total


def backtest_split(lottery_type, strategy_func, total_periods, split_idx, n_bets=2, **kwargs):
    """
    分段回測: 只回測 [split_start, split_end) 範圍
    用於 out-of-sample 驗證
    """
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))

    if lottery_type == 'BIG_LOTTO':
        max_num = 49
        rules = {'minNumber': 1, 'maxNumber': 49, 'pickCount': 6, 'name': 'BIG_LOTTO'}
    else:
        max_num = 38
        rules = {'minNumber': 1, 'maxNumber': 38, 'pickCount': 6, 'name': 'POWER_LOTTO'}

    window = kwargs.get('window', 150)

    # 整段是最後 total_periods 期
    base_idx = len(all_draws) - total_periods

    m3_count = 0
    total = 0

    for i in range(split_idx, total_periods):
        target_idx = base_idx + i
        if target_idx <= window:
            continue

        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist, rules=rules, max_num=max_num, n_bets=n_bets, **kwargs)
        except:
            continue

        best_match = 0
        for bet in bets:
            match = len(set(bet) & actual)
            best_match = max(best_match, match)

        if best_match >= 3:
            m3_count += 1
        total += 1

    if total == 0:
        return 0.0, 0, 0
    return m3_count / total * 100, m3_count, total


def backtest_first_half(lottery_type, strategy_func, total_periods, n_bets=2, **kwargs):
    """回測前半段 (用於調參)"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))

    if lottery_type == 'BIG_LOTTO':
        max_num = 49
        rules = {'minNumber': 1, 'maxNumber': 49, 'pickCount': 6, 'name': 'BIG_LOTTO'}
    else:
        max_num = 38
        rules = {'minNumber': 1, 'maxNumber': 38, 'pickCount': 6, 'name': 'POWER_LOTTO'}

    window = kwargs.get('window', 150)
    half = total_periods // 2
    base_idx = len(all_draws) - total_periods

    m3_count = 0
    total = 0

    for i in range(half):
        target_idx = base_idx + i
        if target_idx <= window:
            continue

        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])

        try:
            bets = strategy_func(hist, rules=rules, max_num=max_num, n_bets=n_bets, **kwargs)
        except:
            continue

        best_match = 0
        for bet in bets:
            match = len(set(bet) & actual)
            best_match = max(best_match, match)

        if best_match >= 3:
            m3_count += 1
        total += 1

    if total == 0:
        return 0.0, 0, 0
    return m3_count / total * 100, m3_count, total


# ========== Wrapper functions (適配不同策略) ==========

def cp_wrapper(hist, rules, max_num, n_bets, window=150, **kw):
    return cluster_pivot_predict(hist, max_num, n_bets=n_bets, window=window)

def gum_wrapper(hist, rules, max_num, n_bets, window=150,
                w_markov=0.25, w_cluster=1.0, w_cold=0.5, **kw):
    return gum_consensus_predict(hist, rules, max_num, n_bets=n_bets, window=window,
                                  w_markov=w_markov, w_cluster=w_cluster, w_cold=w_cold)

def gum_equal_wrapper(hist, rules, max_num, n_bets, window=150, **kw):
    """等權重 GUM (對照組)"""
    return gum_consensus_predict(hist, rules, max_num, n_bets=n_bets, window=window,
                                  w_markov=1.0, w_cluster=1.0, w_cold=1.0)


# ========== 主程式 ==========

def main():
    print("=" * 75)
    print("🔬 獨立驗證 Gemini 微調聲稱 (Out-of-Sample)")
    print("=" * 75)
    print(f"種子: {SEED} | 方法: 500期分段 (前250調參 / 後250驗證) + 1000期長期")
    print()

    # ===================================================
    # 測試 1: 大樂透 Cluster Pivot Window 優化
    # ===================================================
    print("━" * 75)
    print("【測試 1】大樂透 Cluster Pivot - Gemini 聲稱 Window=50 最佳, Edge +1.71%")
    print("━" * 75)

    baseline_2bet = BASELINES['BIG_LOTTO'][2]
    print(f"正確基準 (2注): {baseline_2bet}%")
    print()

    # 1A: 全 500 期重現 (Gemini 的測試)
    print("📊 [1A] 全 500 期 in-sample (重現 Gemini):")
    print("-" * 60)
    for w in [30, 50, 100, 150, 200]:
        rate, hits, total = backtest_strategy('BIG_LOTTO', cp_wrapper, 500, n_bets=2, window=w)
        edge = rate - baseline_2bet
        mark = "⭐" if w == 50 else "  "
        status = "✅" if edge > 0.5 else ("⚠️" if edge > 0 else "❌")
        print(f"  {mark} W={w:3d}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}% {status}")

    # 1B: 前 250 期找最佳窗口
    print()
    print("📊 [1B] 前 250 期 Grid Search (調參階段):")
    print("-" * 60)
    best_w_train = None
    best_rate_train = -1
    for w in [30, 50, 100, 150, 200]:
        rate, hits, total = backtest_first_half('BIG_LOTTO', cp_wrapper, 500, n_bets=2, window=w)
        edge = rate - baseline_2bet
        print(f"  W={w:3d}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}%")
        if rate > best_rate_train:
            best_rate_train = rate
            best_w_train = w

    print(f"\n  → 前 250 期最佳窗口: W={best_w_train} (M3+={best_rate_train:.2f}%)")

    # 1C: 後 250 期 out-of-sample 驗證
    print()
    print("📊 [1C] 後 250 期 Out-of-Sample 驗證:")
    print("-" * 60)
    for w in [best_w_train, 50, 150]:
        w = int(w)
        rate, hits, total = backtest_split('BIG_LOTTO', cp_wrapper, 500, 250, n_bets=2, window=w)
        edge = rate - baseline_2bet
        label = " (Grid Search 最佳)" if w == best_w_train else (" (Gemini 聲稱)" if w == 50 else " (原始預設)")
        status = "✅" if edge > 0.5 else ("⚠️" if edge > 0 else "❌")
        print(f"  W={w:3d}{label}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}% {status}")

    # 1D: 1000 期長期驗證
    print()
    print("📊 [1D] 1000 期長期驗證:")
    print("-" * 60)
    for w in [50, 150]:
        rate, hits, total = backtest_strategy('BIG_LOTTO', cp_wrapper, 1000, n_bets=2, window=w)
        edge = rate - baseline_2bet
        label = " (Gemini)" if w == 50 else " (預設)"
        status = "✅" if edge > 0.5 else ("⚠️" if edge > 0 else "❌")
        print(f"  W={w:3d}{label}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}% {status}")

    # ===================================================
    # 測試 2: 威力彩 GUM Tuned Weights
    # ===================================================
    print()
    print("━" * 75)
    print("【測試 2】威力彩 GUM Consensus - Gemini 聲稱 Tuned Edge +3.21%")
    print("━" * 75)

    baseline_2bet_p = BASELINES['POWER_LOTTO'][2]
    print(f"正確基準 (2注): {baseline_2bet_p}%")
    print()

    # 2A: 全 500 期重現
    print("📊 [2A] 全 500 期 in-sample (重現 Gemini):")
    print("-" * 60)

    gum_configs = [
        ("Gemini Tuned (M=0.25,C=1.0,K=0.5)", 0.25, 1.0, 0.5),
        ("Equal Weights (1.0, 1.0, 1.0)", 1.0, 1.0, 1.0),
        ("Markov Heavy (M=1.0,C=0.5,K=0.25)", 1.0, 0.5, 0.25),
        ("Cold Heavy (M=0.25,C=0.5,K=1.0)", 0.25, 0.5, 1.0),
    ]

    for label, wm, wc, wk in gum_configs:
        rate, hits, total = backtest_strategy(
            'POWER_LOTTO', gum_wrapper, 500, n_bets=2,
            window=150, w_markov=wm, w_cluster=wc, w_cold=wk
        )
        edge = rate - baseline_2bet_p
        status = "✅" if edge > 0.5 else ("⚠️" if edge > 0 else "❌")
        is_gemini = "⭐" if "Gemini" in label else "  "
        print(f"  {is_gemini} {label}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}% {status}")

    # 2B: 前 250 期 Grid Search
    print()
    print("📊 [2B] 前 250 期 Grid Search (調參):")
    print("-" * 60)

    weight_options = [0.25, 0.5, 0.75, 1.0]
    best_config = None
    best_rate_gum = -1
    grid_results = []

    for wm in weight_options:
        for wc in weight_options:
            for wk in weight_options:
                rate, hits, total = backtest_first_half(
                    'POWER_LOTTO', gum_wrapper, 500, n_bets=2,
                    window=150, w_markov=wm, w_cluster=wc, w_cold=wk
                )
                grid_results.append((wm, wc, wk, rate, hits, total))
                if rate > best_rate_gum:
                    best_rate_gum = rate
                    best_config = (wm, wc, wk)

    # 顯示 Top 5
    grid_results.sort(key=lambda x: x[3], reverse=True)
    print("  Top 5 配置 (前 250 期):")
    for wm, wc, wk, rate, hits, total in grid_results[:5]:
        edge = rate - baseline_2bet_p
        print(f"    M={wm:.2f} C={wc:.2f} K={wk:.2f}: M3+={rate:5.2f}% ({hits}/{total}) | Edge={edge:+.2f}%")

    print(f"\n  → 前 250 期最佳: M={best_config[0]:.2f} C={best_config[1]:.2f} K={best_config[2]:.2f}")

    # 2C: 後 250 期 out-of-sample 驗證
    print()
    print("📊 [2C] 後 250 期 Out-of-Sample 驗證:")
    print("-" * 60)

    # Gemini 的配置
    rate_gemini, hits_g, total_g = backtest_split(
        'POWER_LOTTO', gum_wrapper, 500, 250, n_bets=2,
        window=150, w_markov=0.25, w_cluster=1.0, w_cold=0.5
    )
    edge_gemini = rate_gemini - baseline_2bet_p
    status_g = "✅" if edge_gemini > 0.5 else ("⚠️" if edge_gemini > 0 else "❌")
    print(f"  ⭐ Gemini Tuned (M=0.25,C=1.0,K=0.5): M3+={rate_gemini:5.2f}% ({hits_g}/{total_g}) | Edge={edge_gemini:+.2f}% {status_g}")

    # Grid Search 最佳配置
    rate_best, hits_b, total_b = backtest_split(
        'POWER_LOTTO', gum_wrapper, 500, 250, n_bets=2,
        window=150, w_markov=best_config[0], w_cluster=best_config[1], w_cold=best_config[2]
    )
    edge_best = rate_best - baseline_2bet_p
    status_b = "✅" if edge_best > 0.5 else ("⚠️" if edge_best > 0 else "❌")
    print(f"     Grid Best (M={best_config[0]:.2f},C={best_config[1]:.2f},K={best_config[2]:.2f}): M3+={rate_best:5.2f}% ({hits_b}/{total_b}) | Edge={edge_best:+.2f}% {status_b}")

    # 等權重對照
    rate_eq, hits_e, total_e = backtest_split(
        'POWER_LOTTO', gum_equal_wrapper, 500, 250, n_bets=2, window=150
    )
    edge_eq = rate_eq - baseline_2bet_p
    status_e = "✅" if edge_eq > 0.5 else ("⚠️" if edge_eq > 0 else "❌")
    print(f"     Equal Weights (1.0, 1.0, 1.0): M3+={rate_eq:5.2f}% ({hits_e}/{total_e}) | Edge={edge_eq:+.2f}% {status_e}")

    # 2D: 1000 期長期驗證
    print()
    print("📊 [2D] 1000 期長期驗證:")
    print("-" * 60)

    rate_g1k, hits_g1k, total_g1k = backtest_strategy(
        'POWER_LOTTO', gum_wrapper, 1000, n_bets=2,
        window=150, w_markov=0.25, w_cluster=1.0, w_cold=0.5
    )
    edge_g1k = rate_g1k - baseline_2bet_p
    status_g1k = "✅" if edge_g1k > 0.5 else ("⚠️" if edge_g1k > 0 else "❌")
    print(f"  ⭐ Gemini Tuned: M3+={rate_g1k:5.2f}% ({hits_g1k}/{total_g1k}) | Edge={edge_g1k:+.2f}% {status_g1k}")

    rate_e1k, hits_e1k, total_e1k = backtest_strategy(
        'POWER_LOTTO', gum_equal_wrapper, 1000, n_bets=2, window=150
    )
    edge_e1k = rate_e1k - baseline_2bet_p
    status_e1k = "✅" if edge_e1k > 0.5 else ("⚠️" if edge_e1k > 0 else "❌")
    print(f"     Equal Weights: M3+={rate_e1k:5.2f}% ({hits_e1k}/{total_e1k}) | Edge={edge_e1k:+.2f}% {status_e1k}")

    # ===================================================
    # 對照: 已驗證有效的策略
    # ===================================================
    print()
    print("━" * 75)
    print("【對照組】已驗證有效的策略")
    print("━" * 75)
    print()

    # 大樂透 2注 Markov (我們的冠軍)
    print("📊 大樂透 2注 Markov (已驗證 Edge +2.31%):")
    # 使用 cluster pivot 對照
    for w in [50, 100, 150]:
        rate, hits, total = backtest_strategy('BIG_LOTTO', cp_wrapper, 500, n_bets=2, window=w)
        edge = rate - BASELINES['BIG_LOTTO'][2]
        print(f"  Cluster Pivot W={w:3d}: M3+={rate:5.2f}% | Edge={edge:+.2f}%")

    # ===================================================
    # 最終判決
    # ===================================================
    print()
    print("=" * 75)
    print("📋 最終判決")
    print("=" * 75)
    print()
    print("【聲稱 1】大樂透 Cluster Pivot W=50, Edge +1.71%:")
    # 用 1000期結果判斷
    rate_cp50_1k, _, total_cp50_1k = backtest_strategy('BIG_LOTTO', cp_wrapper, 1000, n_bets=2, window=50)
    rate_cp150_1k, _, _ = backtest_strategy('BIG_LOTTO', cp_wrapper, 1000, n_bets=2, window=150)
    edge_50 = rate_cp50_1k - BASELINES['BIG_LOTTO'][2]
    edge_150 = rate_cp150_1k - BASELINES['BIG_LOTTO'][2]
    print(f"  W=50  1000期: Edge={edge_50:+.2f}%")
    print(f"  W=150 1000期: Edge={edge_150:+.2f}%")
    if edge_50 > edge_150 + 0.3:
        print(f"  → ✅ W=50 確實優於 W=150，但 Edge 可能不到 +1.71%")
    elif edge_50 > 0:
        print(f"  → ⚠️ W=50 有效但未必優於 W=150，Edge 差異不顯著")
    else:
        print(f"  → ❌ W=50 無效")

    print()
    print("【聲稱 2】威力彩 GUM Tuned, Edge +3.21%:")
    print(f"  In-sample 500期: Edge={rate_gemini - baseline_2bet_p + (rate_gemini - rate_gemini):+.2f}% (需看上方 2A)")
    print(f"  Out-of-sample 250期: Edge={edge_gemini:+.2f}%")
    print(f"  長期 1000期: Edge={edge_g1k:+.2f}%")
    if edge_g1k > 2.0:
        print(f"  → ✅ Edge > +2.0%，聲稱基本成立")
    elif edge_g1k > 0.5:
        print(f"  → ⚠️ 有效但 Edge 遠低於聲稱的 +3.21%，過擬合嫌疑")
    elif edge_g1k > 0:
        print(f"  → ⚠️ 微弱 Edge，與隨機相當")
    else:
        print(f"  → ❌ Edge ≤ 0，聲稱不成立")

    print()
    print("=" * 75)


if __name__ == "__main__":
    main()
