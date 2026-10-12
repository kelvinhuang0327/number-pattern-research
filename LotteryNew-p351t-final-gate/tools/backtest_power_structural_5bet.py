
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.regime_detector import RegimeDetector

MAX_NUM = 38
PICK = 6

def is_structurally_valid(numbers):
    """
    威力彩結構過濾器 (Structural Integrity Filter)
    過濾掉統計學上的極端低概率組合
    """
    if len(numbers) != 6: return False
    
    # 1. 和值過濾 (核心區間: 80-155)
    s = sum(numbers)
    if not (75 <= s <= 165): return False
    
    # 2. 奇偶比過濾 (禁止 0:6 或 6:0)
    odds = len([n for n in numbers if n % 2 != 0])
    if odds == 0 or odds == 6: return False
    
    # 3. 大小比過濾 (禁止 0:6 或 6:0, 大數定義為 20-38)
    highs = len([n for n in numbers if n >= 20])
    if highs == 0 or highs == 6: return False
    
    # 4. 連號過濾 (禁止 3 連號及以上)
    sorted_nums = sorted(numbers)
    consecutive_count = 1
    max_consecutive = 1
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i+1] - sorted_nums[i] == 1:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 1
    if max_consecutive >= 3: return False
    
    return True

def get_fourier_rank(history, window=500):
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    bitstreams = {i: np.zeros(w) for i in range(1, MAX_NUM + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= MAX_NUM: bitstreams[n][idx] = 1
    scores = np.zeros(MAX_NUM + 1)
    for n in range(1, MAX_NUM + 1):
        bh = bitstreams[n]
        if sum(bh) < 2: continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_xf = xf[idx_pos]
        pos_yf = np.abs(yf[idx_pos])
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0: continue
        period = 1 / freq_val
        last_hit = np.where(bh == 1)[0][-1]
        gap = (w - 1) - last_hit
        scores[n] = 1.0 / (abs(gap - period) + 1.0)
    return np.argsort(scores)[::-1]

def generate_structural_adaptive_5bet(history):
    # 偵測盤態
    detector = RegimeDetector()
    regime = detector.detect_regime(history)['regime']
    
    # 獲取基礎權重排位
    f_rank = get_fourier_rank(history)
    idx_ptr = 0
    while idx_ptr < len(f_rank) and f_rank[idx_ptr] == 0: idx_ptr += 1
    f_rank_clean = f_rank[idx_ptr:].tolist()
    
    recent = history[-100:]
    freq = Counter([n for d in recent for n in d['numbers']])
    
    final_bets = []
    used_total = set()
    
    # 核心邏輯：逐注生成並過濾
    # 如果最優組合不過濾，則微調最後一個號碼為備選號
    def get_valid_bet(candidate_pool, count=6):
        if len(candidate_pool) < count: return candidate_pool[:count]
        
        # 嘗試前 N 個號碼的組合，尋找符合結構的最佳注
        # 這裡簡化為：如果首選 6 個不過，嘗試更換第 6 個號碼為池中後續的號碼
        best_6 = candidate_pool[:6]
        if is_structurally_valid(best_6):
            return best_6
            
        # 簡單微調：嘗試更換最後一、二個號碼
        for i in range(count, min(len(candidate_pool), count + 10)):
            # 嘗試換掉倒數第一個
            test_bet = candidate_pool[:count-1] + [candidate_pool[i]]
            if is_structurally_valid(test_bet): return test_bet
            
        # 如果微調後仍不符合，返回原首選（避免信號損失過大），但在補位注會更嚴格
        return best_6

    # Bet 1 & 2: Fourier
    bet1 = get_valid_bet(f_rank_clean)
    used_total.update(bet1)
    
    rem_f = [n for n in f_rank_clean if n not in used_total]
    bet2 = get_valid_bet(rem_f)
    used_total.update(bet2)
    
    # Bet 3: Echo/Cold
    if len(history) >= 2:
        echo = [n for n in history[-2]['numbers'] if n <= MAX_NUM and n not in used_total]
    else: echo = []
    
    rem_for_b3 = [n for n in range(1, 39) if n not in used_total and n not in echo]
    rem_for_b3.sort(key=lambda x: freq.get(x, 0))
    b3_pool = echo + rem_for_b3
    bet3 = get_valid_bet(b3_pool)
    used_total.update(bet3)
    
    # Bet 4 & 5: Regime Adaptive Orthogonal
    leftover = [n for n in range(1, 39) if n not in used_total]
    if regime == 'ORDER':
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    elif regime == 'CHAOS':
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=False)
    else:
        leftover.sort(key=lambda x: freq.get(x, 0), reverse=True)
    
    bet4 = get_valid_bet(leftover)
    used_total.update(bet4)
    
    rem_last = [n for n in range(1, 39) if n not in used_total]
    bet5 = get_valid_bet(rem_last)
    
    return [sorted(b) for b in [bet1, bet2, bet3, bet4, bet5]]

def run_backtest_structural(periods_list=[150, 500, 1500]):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))
    
    print("=" * 70)
    print("📊 STRUCTURAL FILTER + REGIME ADAPTIVE 5-BET BACKTEST")
    print("=" * 70)
    
    baseline = 18.20
    
    for periods in periods_list:
        hits = 0
        total = 0
        test_draws = all_draws[-periods:]
        
        for i in range(len(all_draws) - periods, len(all_draws)):
            history = all_draws[:i]
            if len(history) < 500: continue
            
            target = all_draws[i]
            actual = set(target['numbers'])
            bets = generate_structural_adaptive_5bet(history)
            
            win = False
            for b in bets:
                if len(set(b) & actual) >= 3:
                    win = True
                    break
            if win: hits += 1
            total += 1
            
        rate = (hits / total) * 100 if total > 0 else 0
        edge = rate - baseline
        print(f"[{periods:4d}期] 勝率: {rate:5.2f}% | 基準: {baseline:5.2f}% | Edge: {edge:+5.2f}%")

if __name__ == "__main__":
    run_backtest_structural()
