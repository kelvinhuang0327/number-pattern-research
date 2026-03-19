#!/usr/bin/env python3
"""
Power Lotto Fourier Rhythm Researcher
=====================================
Logic:
1. Treat each ball's appearance history (0/1) as a time-series.
2. Apply Fast Fourier Transform (FFT) to detect dominant frequencies.
3. Predict based on the "Next Strike" phase of the top periodic balls.
"""
import os
import sys
import numpy as np
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

try:
    from tools.strategy_leaderboard import StrategyLeaderboard
except ImportError:
    StrategyLeaderboard = None

def detect_dominant_period(ball_history):
    # ball_history is an array of 0s and 1s
    n = len(ball_history)
    if sum(ball_history) < 2: return None
    
    # FFT
    yf = fft(ball_history - np.mean(ball_history)) # Detrend
    xf = fftfreq(n, 1)
    
    # Only look at positive frequencies (excluding constant term)
    idx = np.where(xf > 0)
    pos_xf = xf[idx]
    pos_yf = np.abs(yf[idx])
    
    # Target peak
    peak_idx = np.argmax(pos_yf)
    freq = pos_xf[peak_idx]
    
    if freq == 0: return None
    period = 1 / freq
    return period

def fourier_rhythm_predict(history, n_bets=2, window=500):
    h_slice = history[-window:]
    # Detect lottery type from max ball in history
    max_num = max([n for d in h_slice for n in d['numbers']])
    if max_num < 38: max_num = 38 # Default to Power Lotto
    if max_num > 38: max_num = 49 # Default to Big Lotto
    
    # 1. Create bitstreams for each ball
    bitstreams = {i: np.zeros(window) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1
            
    # 2. Detect periods and phases
    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
        period = detect_dominant_period(bitstreams[n])
        if period and 2 < period < window/2:
            # Simple scoring: How many draws since last appearance?
            last_hit = np.where(bitstreams[n] == 1)[0][-1]
            gap = (window - 1) - last_hit
            # If gap is approaching the period, high score
            # Score = Gaussian-like peak around the period
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)
            
    all_indices = np.arange(1, max_num + 1)
    sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
    
    bets = []
    for i in range(n_bets):
        start = i * 6
        end = (i + 1) * 6
        bets.append(sorted(sorted_indices[start:end].tolist()))
        
    return bets

def predict_and_print(lottery_type='POWER_LOTTO', n_bets=2):
    """載入數據並輸出預測結果"""
    from collections import Counter

    lb = StrategyLeaderboard(lottery_type=lottery_type)
    draws = lb.draws
    last = draws[-1]
    max_num = 38 if lottery_type == 'POWER_LOTTO' else 49
    name = '威力彩' if lottery_type == 'POWER_LOTTO' else '大樂透'
    next_draw = int(last['draw']) + 1

    bets = fourier_rhythm_predict(draws, n_bets=n_bets, window=500)

    print("=" * 60)
    print(f"  {name} Fourier Rhythm {n_bets}注預測 — 第 {next_draw} 期")
    print("=" * 60)
    print(f"  上期: {last['draw']} → {last['numbers']}"
          + (f" sp={last.get('special','')}" if last.get('special') else ""))
    print()

    for i, bet in enumerate(bets):
        num_str = ", ".join(f"{n:02d}" for n in bet)
        print(f"  注{i+1}: [{num_str}]")

    # 特別號 (僅威力彩)
    if lottery_type == 'POWER_LOTTO':
        try:
            sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
            from models.special_predictor import PowerLottoSpecialPredictor
            rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
            sp = PowerLottoSpecialPredictor(rules)
            combined = list(set(n for b in bets for n in b))
            sp_top = sp.predict_top_n(draws, n=3, main_numbers=combined)
            print(f"\n  特別號 (V3 MAB): {sp_top}")
        except Exception:
            sp_freq = Counter(d.get('special', 0) for d in draws[-50:])
            print(f"\n  特別號 (頻率): {[n for n,_ in sp_freq.most_common(3)]}")

    # 覆蓋分析
    all_nums = set(n for b in bets for n in b)
    print(f"\n  覆蓋: {len(all_nums)} 個不同號碼")
    for i, bet in enumerate(bets):
        odd = sum(1 for n in bet if n % 2 == 1)
        big = sum(1 for n in bet if n >= (20 if max_num == 38 else 25))
        print(f"  注{i+1} 奇偶={odd}:{6-odd}, 大小={big}:{6-big}, 和={sum(bet)}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='威力彩/大樂透 Fourier Rhythm 預測')
    parser.add_argument('--predict', action='store_true', help='輸出預測結果')
    parser.add_argument('--bets', type=int, default=2, help='注數 (2 或 3)')
    parser.add_argument('--type', default='POWER_LOTTO',
                        choices=['POWER_LOTTO', 'BIG_LOTTO'], help='彩種')
    parser.add_argument('--n', type=int, default=500, help='回測期數 (非predict模式)')
    args = parser.parse_args()

    if args.predict:
        predict_and_print(lottery_type=args.type, n_bets=args.bets)
    else:
        from tools.verify_strategy_longterm import UnifiedAuditor
        auditor = UnifiedAuditor(lottery_type=args.type)

        def audit_bridge(history, num_bets=2):
            return fourier_rhythm_predict(history, n_bets=num_bets)

        auditor.audit(audit_bridge, n=args.n, num_bets=args.bets)
