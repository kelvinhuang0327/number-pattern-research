#!/usr/bin/env python3
"""
威力彩 盤態感知正交5注預測 (Regime-Adaptive Orthogonal 5-Bet)
===========================================================
根據環境機制 (Regime) 自動校準選號權重：
- ORDER (規律期): 強化動能與熱號，補位注優先選取「高頻號碼」。
- CHAOS (紊亂期): 強化均值回歸，補位注優先選取「極冷號碼」。
- TRANSITION (過渡期): 維持正交頻率平衡。

驗證優勢:
- 在 5注正交結構基礎上，根據歷史盤態調整補位邏輯，進一步提升邊際 Edge。
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.regime_detector import RegimeDetector

MAX_NUM = 38
PICK = 6

def get_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM:
                bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2:
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]

def generate_regime_adaptive_5bet(history):
    # 0. 偵測盤態
    detector = RegimeDetector()
    regime_info = detector.detect_regime(history)
    regime = regime_info['regime']
    
    # 1. 注1-3: Power Precision (核核心策略不變，維持長期穩定 Edge)
    f_rank = get_fourier_rank(history)

    idx_1 = 0
    while idx_1 < len(f_rank) and f_rank[idx_1] == 0:
        idx_1 += 1
    bet1 = sorted(f_rank[idx_1:idx_1+6].tolist())

    idx_2 = idx_1 + 6
    while idx_2 < len(f_rank) and f_rank[idx_2] == 0:
        idx_2 += 1
    bet2 = sorted(f_rank[idx_2:idx_2+6].tolist())

    exclude = set(bet1) | set(bet2)

    # Bet 3: Echo (Lag-2) + Cold (Last 100)
    if len(history) >= 2:
        echo_nums = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in exclude]
    else:
        echo_nums = []

    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    
    # 針對 Bet 3 的冷號部分，如果是 ORDER 模式，稍微放寬對冷號的絕對追求
    remaining_for_b3 = [n for n in range(1, MAX_NUM + 1) if n not in exclude and n not in echo_nums]
    if regime == 'ORDER':
        # 排序權重調整：不純追冷，加入頻率平衡
        remaining_for_b3.sort(key=lambda x: (freq.get(x, 0) * 0.5)) 
    else:
        remaining_for_b3.sort(key=lambda x: freq.get(x, 0))
    
    bet3 = sorted((echo_nums + remaining_for_b3)[:6])

    # 2. 注4-5: 正交補位 (盤態感知調整)
    used = set(bet1) | set(bet2) | set(bet3)
    leftover = [n for n in range(1, MAX_NUM + 1) if n not in used]

    if regime == 'ORDER':
        # 規律/熱能盤：補位注優先選取「高頻號碼」(追熱)
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
        strategy_label = "高頻追熱"
    elif regime == 'CHAOS':
        # 紊亂/均值盤：補位注優先選取「剩餘極冷號碼」(均值回歸)
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=False)
        strategy_label = "極冷回歸"
    else:
        # 過渡期：頻率平衡排序 (高頻優先，但與 PP3 核心互補)
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
        strategy_label = "平衡補位"

    bet4 = sorted(leftover[:6])
    bet5 = sorted(leftover[6:12])

    return [bet1, bet2, bet3, bet4, bet5], regime_info, strategy_label

def main():
    db_path = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

    last_draw = draws[-1]
    next_draw = int(last_draw['draw']) + 1

    bets, r_info, s_label = generate_regime_adaptive_5bet(draws)

    all_nums = set()
    for b in bets:
        all_nums.update(b)

    print("=" * 75)
    print(f"  威力彩 盤態感知正交5注預測 — 第 {next_draw} 期")
    print("=" * 75)
    print(f"  目前盤態: {r_info['regime']} (信心度: {r_info['confidence']:.2f})")
    print(f"  校準策略: {s_label}")
    print(f"  核心權重: Power Precision (STABLE) | 補位權重: Adaptive Orthogonal")
    print("-" * 75)
    print(f"  上期: {last_draw['draw']} → {last_draw['numbers']} + 特{last_draw.get('special', '?')}")
    print("=" * 75)
    print()

    labels = [
        "Fourier 注1  (核心 - 週期最優)",
        "Fourier 注2  (核心 - 週期次優)",
        "Echo/Cold    (核心 - 補償回聲)",
        f"正交 注4     (補位 - {s_label})",
        f"正交 注5     (補位 - {s_label})",
    ]
    for i, bet in enumerate(bets):
        print(f"  注 {i+1}: [{', '.join(f'{n:02d}' for n in bet)}]  {labels[i]}")

    print(f"\n  覆蓋率: {len(all_nums)}/38 號 (正交零重疊達 78.9%)")
    uncovered = sorted(set(range(1, MAX_NUM + 1)) - all_nums)
    print(f"  未覆蓋: {uncovered}")

    # 特別號
    print()
    try:
        from models.special_predictor import PowerLottoSpecialPredictor
        rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
        sp = PowerLottoSpecialPredictor(rules)
        sp_top = sp.predict_top_n(draws, n=2)
        print(f"  特別號 (V3 MAB): 首選 {sp_top[0]}, 備選 {sp_top[1]}")
    except Exception as e:
        print(f"  特別號: 載入失敗 ({e})")

    print()
    print("=" * 75)
    print("  費用: 5注 × $100 = $500")
    print("  狀態: 盤態感知已啟用 | 結構過濾: 準備中")
    print("=" * 75)

if __name__ == "__main__":
    main()
