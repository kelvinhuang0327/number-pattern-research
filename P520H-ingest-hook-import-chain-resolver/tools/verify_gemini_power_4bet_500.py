#!/usr/bin/env python3
"""
Gemini 威力彩 4-Bet 策略獨立驗證 (500 期)
==========================================
驗證 Gemini 聲稱的策略:
- 4-Bet Optimized Ensemble with Fourier Rhythm
- Overall Hit Rate: 53.33% (Gemini 聲稱)
- Special Number: 40.00% (Gemini 聲稱)
- Match 3+: 13.33% (Gemini 聲稱)

Claude 獨立驗證，使用正確的 N 注 baseline 計算
"""
import os
import sys
import random
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

# 固定隨機種子
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ==================== 正確的 N 注 Baseline ====================
# 威力彩 (1-38 選 6) 單注 M3+ 理論機率
SINGLE_BET_M3_PLUS = 0.0387  # 3.87%

def correct_n_bet_baseline(n_bets):
    """
    正確的 N 注隨機基準
    P(N注至少一注 M3+) = 1 - (1 - P(1注))^N
    """
    return 1 - (1 - SINGLE_BET_M3_PLUS) ** n_bets

# 威力彩特別號 (1-8 選 1) 隨機基準
SPECIAL_BASELINE = 1 / 8  # 12.5%

# ==================== Fourier Rhythm 預測 ====================
def detect_dominant_period(ball_history):
    n = len(ball_history)
    if sum(ball_history) < 2:
        return None
    yf = fft(ball_history - np.mean(ball_history))
    xf = fftfreq(n, 1)
    idx = np.where(xf > 0)
    pos_xf = xf[idx]
    pos_yf = np.abs(yf[idx])
    if len(pos_yf) == 0:
        return None
    peak_idx = np.argmax(pos_yf)
    freq = pos_xf[peak_idx]
    if freq == 0:
        return None
    return 1 / freq

def fourier_rhythm_predict(history, n_bets=4, window=500):
    """Gemini 的 Fourier Rhythm 策略"""
    h_slice = history[-window:] if len(history) >= window else history
    max_num = 38  # 威力彩

    bitstreams = {i: np.zeros(len(h_slice)) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if 1 <= n <= max_num:
                bitstreams[n][idx] = 1

    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        period = detect_dominant_period(bitstreams[n])
        if period and 2 < period < len(h_slice)/2:
            last_hits = np.where(bitstreams[n] == 1)[0]
            if len(last_hits) > 0:
                last_hit = last_hits[-1]
                gap = (len(h_slice) - 1) - last_hit
                dist_to_peak = abs(gap - period)
                scores[n] = 1.0 / (dist_to_peak + 1.0)

    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]

    bets = []
    used = set()
    for i in range(n_bets):
        bet = []
        for idx in sorted_indices:
            if idx not in used and len(bet) < 6:
                bet.append(int(idx))
                used.add(idx)
        if len(bet) < 6:
            remaining = [x for x in range(1, 39) if x not in used]
            random.shuffle(remaining)
            bet.extend(remaining[:6-len(bet)])
            used.update(bet)
        bets.append(sorted(bet[:6]))

    return bets

# ==================== 特別號預測 (V3 Markov) ====================
def predict_special(history):
    """V3 特別號預測 (Markov)"""
    if len(history) < 10:
        return 2

    specials = [d.get('special') for d in history if d.get('special')]
    if len(specials) < 2:
        return 2

    # 一階 Markov
    transitions = {}
    for i in range(len(specials) - 1):
        key = specials[i]
        if key not in transitions:
            transitions[key] = Counter()
        transitions[key][specials[i+1]] += 1

    last = specials[0]  # history 是 新→舊 排序
    if last in transitions:
        return transitions[last].most_common(1)[0][0]

    # Fallback: 最頻繁的
    return Counter(specials).most_common(1)[0][0]

# ==================== 主回測函數 ====================
def backtest_4bet(test_periods=500):
    """4 注策略回測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))

    test_periods = min(test_periods, len(all_draws) - 100)

    print("=" * 70)
    print("🔬 Gemini 威力彩 4-Bet 策略獨立驗證")
    print("=" * 70)
    print(f"驗證配置: 4-Bet Optimized Ensemble with Fourier Rhythm")
    print(f"測試期數: {test_periods}")
    print(f"隨機種子: {SEED}")
    print("-" * 70)

    # 統計
    m3_hits = 0          # 任一注 M3+ 的期數
    m4_hits = 0          # 任一注 M4+ 的期數
    special_hits = 0     # 特別號命中次數
    total = 0

    # 詳細命中分布
    best_match_dist = Counter()
    per_bet_m3 = [0, 0, 0, 0]  # 每注的 M3+ 次數

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 50:
            continue

        # ===== 數據切片 (防洩漏) =====
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        # =============================

        actual_numbers = set(target_draw['numbers'])
        actual_special = target_draw.get('special')

        # 生成 4 注預測
        try:
            bets = fourier_rhythm_predict(hist, n_bets=4, window=500)
            pred_special = predict_special(hist)
        except Exception as e:
            continue

        # 評估每注
        best_match = 0
        for j, bet in enumerate(bets):
            match = len(set(bet) & actual_numbers)
            best_match = max(best_match, match)
            if match >= 3:
                per_bet_m3[j] += 1

        best_match_dist[best_match] += 1

        if best_match >= 3:
            m3_hits += 1
        if best_match >= 4:
            m4_hits += 1

        # 特別號
        if pred_special == actual_special:
            special_hits += 1

        total += 1

    # ==================== 結果計算 ====================
    m3_rate = m3_hits / total * 100
    m4_rate = m4_hits / total * 100
    special_rate = special_hits / total * 100

    # 正確的 4 注 baseline
    baseline_4bet = correct_n_bet_baseline(4) * 100
    special_baseline_pct = SPECIAL_BASELINE * 100

    # Edge 計算
    edge_m3 = m3_rate - baseline_4bet
    edge_special = special_rate - special_baseline_pct

    # ==================== 輸出報告 ====================
    print("\n" + "=" * 70)
    print("📊 驗證結果")
    print("=" * 70)

    print(f"\n測試期數: {total}")
    print(f"策略: 4-Bet Fourier Rhythm Ensemble")

    print(f"\n最佳主號命中分布:")
    for mc in sorted(best_match_dist.keys(), reverse=True):
        cnt = best_match_dist[mc]
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{mc}: {cnt:3d} ({pct:5.2f}%) {bar}")

    print(f"\n各注 M3+ 次數:")
    for j in range(4):
        print(f"  注{j+1}: {per_bet_m3[j]} 次 ({per_bet_m3[j]/total*100:.2f}%)")

    print("\n" + "=" * 70)
    print("📈 關鍵指標對比")
    print("=" * 70)

    print(f"\n{'指標':<25} {'Gemini 聲稱':<15} {'Claude 驗證':<15} {'正確基準':<15} {'Edge':<10}")
    print("-" * 70)

    # Overall Hit Rate - Gemini 聲稱 53.33%，但這個定義不清
    # 我們用 M3+ 作為 "Hit"
    print(f"{'M3+ 命中率 (4注)':<25} {'13.33%':<15} {f'{m3_rate:.2f}%':<15} {f'{baseline_4bet:.2f}%':<15} {f'{edge_m3:+.2f}%':<10}")
    print(f"{'M4+ 命中率 (4注)':<25} {'-':<15} {f'{m4_rate:.2f}%':<15} {'-':<15} {'-':<10}")
    print(f"{'特別號命中率':<25} {'40.00%':<15} {f'{special_rate:.2f}%':<15} {f'{special_baseline_pct:.2f}%':<15} {f'{edge_special:+.2f}%':<10}")

    print("\n" + "=" * 70)
    print("🔍 驗證結論")
    print("=" * 70)

    # M3+ 判定
    if edge_m3 >= 2.0:
        m3_status = "✅ 顯著有效"
    elif edge_m3 >= 0.5:
        m3_status = "⚠️ 微弱優勢"
    elif edge_m3 >= -0.5:
        m3_status = "❌ 與隨機相當"
    else:
        m3_status = "❌ 比隨機差"

    # 特別號判定
    if edge_special >= 2.0:
        special_status = "✅ 顯著有效"
    elif edge_special >= 0.5:
        special_status = "⚠️ 微弱優勢"
    elif edge_special >= -0.5:
        special_status = "❌ 與隨機相當"
    else:
        special_status = "❌ 比隨機差"

    print(f"\n主號 M3+ (4注): {m3_status}")
    print(f"  實測: {m3_rate:.2f}% | 基準: {baseline_4bet:.2f}% | Edge: {edge_m3:+.2f}%")

    print(f"\n特別號: {special_status}")
    print(f"  實測: {special_rate:.2f}% | 基準: {special_baseline_pct:.2f}% | Edge: {edge_special:+.2f}%")

    print("\n" + "=" * 70)
    print("⚠️ Gemini 聲稱 vs 現實")
    print("=" * 70)

    print(f"""
Gemini 報告問題：

1. 「Overall Hit Rate 53.33%」
   - 定義不清：什麼算 "Hit"？
   - 4 注 M3+ 隨機基準是 {baseline_4bet:.2f}%，不可能達到 53%
   - Claude 驗證結果：{m3_rate:.2f}%

2. 「Special Number 40.00%」
   - 物理上不可能：隨機基準 12.5%，Edge +27.5%?
   - 我們最好的 V3 策略也只有 ~14.7%
   - Claude 驗證結果：{special_rate:.2f}%

3. 「Match 3+ 13.33%」
   - 這是 Gemini 唯一可能接近的數字
   - 但需要澄清：是單注還是 4 注組合？
   - 單注 M3+ 基準 3.87%，4 注組合基準 {baseline_4bet:.2f}%
   - Claude 驗證 (4注組合): {m3_rate:.2f}%

4. 樣本量問題
   - Gemini: 20 期 × 3 seeds = 60 個樣本
   - Claude: {total} 期獨立驗證
   - 統計意義：N≥500 才可靠
""")

    return {
        'm3_rate': m3_rate,
        'special_rate': special_rate,
        'edge_m3': edge_m3,
        'edge_special': edge_special,
        'total': total
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--periods', type=int, default=500, help='測試期數')
    args = parser.parse_args()

    result = backtest_4bet(args.periods)

    print("\n" + "=" * 70)
    print("📋 最終判定")
    print("=" * 70)

    if result['edge_m3'] >= 1.0 and result['edge_special'] >= 1.0:
        print("\n✅ 策略整體有效 (但 Gemini 數據仍然嚴重誇大)")
    elif result['edge_m3'] >= 0.5 or result['edge_special'] >= 0.5:
        print("\n⚠️ 策略有微弱優勢，但 Gemini 數據不實")
    else:
        print("\n❌ 策略無效，Gemini 數據完全虛假")
