#!/usr/bin/env python3
"""
Fourier Main 策略獨立 500 期驗證
================================
驗證 Gemini 聲稱的 Fourier Main 5.60% M3+ 命中率

正確基準 (威力彩 1-38 選 6): 3.87%
Gemini 聲稱: 5.60% M3+ (+1.73% Edge)

執行方式：
  python3 tools/verify_fourier_main_500.py
"""
import sys
import os
import numpy as np
from collections import Counter
from scipy.fft import fft

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

# 固定隨機種子
SEED = 42
np.random.seed(SEED)

# 正確基準
BASELINE_1BET = 3.87


def fourier_main_predict(history, max_num=38, window_sizes=[64, 128, 256]):
    """
    Fourier Main 主號預測 (複製自 lottery_api/models/fourier_rhythm.py)
    """
    if len(history) < 32:
        return list(range(1, 7))

    scores = {n: 0.0 for n in range(1, max_num + 1)}

    for w in window_sizes:
        if len(history) < w:
            continue

        h_slice = history[-w:]  # 取最近 w 期 (history 是舊→新排序)

        # 建立位元流
        bitstreams = np.zeros((max_num + 1, w), dtype=float)
        for idx, d in enumerate(h_slice):
            for num in d.get('numbers', []):
                if 1 <= num <= max_num:
                    bitstreams[num][idx] = 1.0

        for n in range(1, max_num + 1):
            seq = bitstreams[n]
            mean_val = np.mean(seq)
            if mean_val == 0:
                continue

            centered = seq - mean_val
            xf = fft(centered)
            mags = np.abs(xf)

            half = len(mags) // 2
            if half <= 1:
                continue

            # 尋找最強頻率
            dominants = np.argsort(mags[1:half])[-2:] + 1

            t_next = w
            recon_val = 0.0
            for k in dominants:
                phase = np.angle(xf[k])
                amplitude = mags[k] / w
                recon_val += 2.0 * amplitude * np.cos(2.0 * np.pi * k * t_next / w + phase)

            score = recon_val + mean_val
            if score > 0:
                scores[n] += score * np.log(w)

    # 取得分最高的 6 個號碼
    top_6 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:6]
    return sorted([n for n, s in top_6])


def run_backtest(test_periods=500):
    """執行 Fourier Main 回測"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    test_periods = min(test_periods, len(all_draws) - 300)  # 需要至少 256 期歷史

    print("=" * 70)
    print(f"🔬 Fourier Main 策略獨立驗證 ({test_periods} 期)")
    print("=" * 70)
    print(f"隨機種子: {SEED}")
    print(f"正確基準 (1 注 M3+): {BASELINE_1BET}%")
    print(f"Gemini 聲稱: 5.60% M3+ (+1.73% Edge)")
    print("-" * 70)

    match_dist = Counter()
    m3_plus = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 300:  # 確保有足夠歷史數據
            continue

        # 數據切片防止洩漏
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]

        actual = set(target_draw['numbers'])

        try:
            predicted = set(fourier_main_predict(hist))
            match_count = len(predicted & actual)
            match_dist[match_count] += 1

            if match_count >= 3:
                m3_plus += 1

            total += 1

            if total % 100 == 0:
                current_rate = m3_plus / total * 100
                print(f"  進度: {total}/{test_periods} | 當前 M3+: {current_rate:.2f}%")

        except Exception as e:
            print(f"  Error at {i}: {e}")
            continue

    if total == 0:
        print("❌ 無有效數據")
        return None

    m3_rate = m3_plus / total * 100
    edge = m3_rate - BASELINE_1BET

    print("\n" + "=" * 70)
    print("📊 回測結果")
    print("=" * 70)
    print(f"\n測試期數: {total}")

    print(f"\n主號命中分布:")
    for mc in sorted(match_dist.keys(), reverse=True):
        cnt = match_dist[mc]
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{mc}: {cnt:3d} ({pct:5.1f}%) {bar}")

    print("\n" + "=" * 70)
    print("📈 核心指標 (M3+)")
    print("=" * 70)
    print(f"\n實測 M3+ 命中率: {m3_rate:.2f}%")
    print(f"正確基準 (1 注): {BASELINE_1BET}%")
    print(f"Edge: {'+' if edge >= 0 else ''}{edge:.2f}%")

    print("\n" + "-" * 70)
    print("Gemini 聲稱 vs Claude 實測:")
    print("-" * 70)
    print(f"Gemini 聲稱: 5.60% M3+ (+1.73% Edge)")
    print(f"Claude 實測: {m3_rate:.2f}% M3+ ({'+' if edge >= 0 else ''}{edge:.2f}% Edge)")

    diff = m3_rate - 5.60
    if abs(diff) < 0.5:
        print(f"\n✅ 結果一致 (差異 {diff:+.2f}%)")
        verdict = "CONFIRMED"
    elif diff > 0:
        print(f"\n✅ 結果更好 (高於聲稱 {diff:+.2f}%)")
        verdict = "CONFIRMED_BETTER"
    else:
        print(f"\n⚠️ 結果有差異 (低於聲稱 {diff:.2f}%)")
        verdict = "DISCREPANCY"

    if edge >= 1.0:
        print(f"\n✅ 顯著優於基準 (Edge >= 1%)")
    elif edge >= 0:
        print(f"\n⚠️ 微弱優勢 (0 <= Edge < 1%)")
    else:
        print(f"\n❌ 低於基準 (Edge < 0)")

    return {
        'test_periods': total,
        'm3_rate': m3_rate,
        'baseline': BASELINE_1BET,
        'edge': edge,
        'gemini_claim': 5.60,
        'verdict': verdict
    }


if __name__ == '__main__':
    result = run_backtest(test_periods=500)
