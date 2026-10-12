#!/usr/bin/env python3
"""
威力彩 3 注策略 (Power Triple Strike)
=====================================
策略組成:
  注1: Fourier Rhythm (FFT 週期分析) - Edge +1.81%
  注2: Cold Numbers (冷號逆向) - 捕捉被忽視的號碼
  注3: Tail Balance (尾數平衡) - 確保尾數覆蓋多樣性

設計目標:
  - 最大化覆蓋面，降低單期全軍覆沒風險
  - 每注使用不同邏輯，互補而非重疊

2026-01-30 Created based on 115000009 review meeting
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor

np.random.seed(42)

# ========== 策略實作 ==========

def fourier_rhythm_bet(history, window=500):
    """
    注1: Fourier Rhythm
    原理: FFT 檢測每個號碼的週期性，選擇「即將到期」的號碼
    """
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 38

    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            bitstreams[n][idx] = 1

    scores = np.zeros(max_num + 1)
    for n in range(1, max_num + 1):
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
        if 2 < period < w / 2:
            last_hit = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit
            dist_to_peak = abs(gap - period)
            scores[n] = 1.0 / (dist_to_peak + 1.0)

    all_idx = np.arange(1, max_num + 1)
    sorted_idx = all_idx[np.argsort(scores[1:])[::-1]]
    return sorted(sorted_idx[:6].tolist())


def cold_numbers_bet(history, window=100, exclude=None):
    """
    注2: Cold Numbers
    原理: 選擇近 N 期最少出現的號碼 (逆向思維)
    """
    if exclude is None:
        exclude = set()

    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    # 排除已選號碼
    candidates = [n for n in range(1, 39) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))

    return sorted(sorted_cold[:6])


def tail_balance_bet(history, window=100, exclude=None):
    """
    注3: Tail Balance (尾數平衡)
    原理: 確保選出的 6 個號碼覆蓋至少 5 種不同尾數

    步驟:
    1. 計算每個尾數 (0-9) 的近期頻率
    2. 從每個尾數中選出頻率最高的號碼
    3. 優先選擇覆蓋不同尾數的號碼
    """
    if exclude is None:
        exclude = set()

    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    # 按尾數分組
    tail_groups = {i: [] for i in range(10)}
    for n in range(1, 39):
        if n not in exclude:
            tail = n % 10
            tail_groups[tail].append((n, freq.get(n, 0)))

    # 每組按頻率排序
    for tail in tail_groups:
        tail_groups[tail].sort(key=lambda x: x[1], reverse=True)

    # 策略: 從不同尾數中輪流選取
    selected = []
    # 先從有號碼的尾數組中各選一個最熱門的
    available_tails = [t for t in range(10) if tail_groups[t]]

    # 按組內最高頻率排序尾數組
    available_tails.sort(key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)

    # 輪流從各尾數組選取
    idx_in_group = {t: 0 for t in range(10)}
    round_num = 0

    while len(selected) < 6:
        for tail in available_tails:
            if len(selected) >= 6:
                break
            group = tail_groups[tail]
            idx = idx_in_group[tail]
            if idx < len(group):
                num, _ = group[idx]
                if num not in selected:
                    selected.append(num)
                    idx_in_group[tail] += 1
        round_num += 1
        if round_num > 10:  # 防止無限循環
            break

    # 如果還不夠 6 個，從剩餘號碼中補充
    if len(selected) < 6:
        remaining = [n for n in range(1, 39) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def zone_coverage_check(bets):
    """
    區間覆蓋檢查
    確保 3 注組合覆蓋所有區間
    """
    low = set(range(1, 14))    # 1-13
    mid = set(range(14, 27))   # 14-26
    high = set(range(27, 39))  # 27-38

    all_nums = set()
    for bet in bets:
        all_nums.update(bet)

    coverage = {
        'low': len(all_nums & low),
        'mid': len(all_nums & mid),
        'high': len(all_nums & high),
    }
    return coverage


def generate_triple_strike(history):
    """
    生成 3 注預測
    """
    # 注 1: Fourier Rhythm
    bet1 = fourier_rhythm_bet(history, window=500)
    exclude1 = set(bet1)

    # 注 2: Cold Numbers (排除注1的號碼以增加覆蓋)
    bet2 = cold_numbers_bet(history, window=100, exclude=exclude1)
    exclude2 = exclude1 | set(bet2)

    # 注 3: Tail Balance (排除前兩注以最大化覆蓋)
    bet3 = tail_balance_bet(history, window=100, exclude=exclude2)

    return [bet1, bet2, bet3]


# ========== 主程式 ==========

def main():
    import argparse
    parser = argparse.ArgumentParser(description='威力彩 3 注策略預測')
    parser.add_argument('--backtest', type=int, default=0, help='回測期數 (0=只預測)')
    args = parser.parse_args()

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('POWER_LOTTO'), key=lambda x: (x['date'], x['draw']))

    if args.backtest > 0:
        # 回測模式
        run_backtest(draws, args.backtest)
    else:
        # 預測模式
        run_prediction(draws)


def run_prediction(draws):
    """執行預測"""
    last_draw = draws[-1]
    next_draw = int(last_draw['draw']) + 1

    # 生成預測
    bets = generate_triple_strike(draws)

    # 特別號預測
    rules = {'specialMinNumber': 1, 'specialMaxNumber': 8, 'name': 'POWER_LOTTO',
             'minNumber': 1, 'maxNumber': 38, 'pickCount': 6}
    sp = PowerLottoSpecialPredictor(rules)
    specials = sp.predict_top_n(draws, n=3)

    # 區間覆蓋檢查
    coverage = zone_coverage_check(bets)

    # 計算總覆蓋號碼數
    all_nums = set()
    for bet in bets:
        all_nums.update(bet)

    # 輸出
    print("=" * 70)
    print(f"  威力彩 POWER LOTTO 3注預測 — 第 {next_draw} 期")
    print("=" * 70)
    print(f"  策略: Triple Strike (Fourier + Cold + Tail Balance)")
    print(f"  上期開獎: {last_draw['draw']} → {last_draw['numbers']} 特:{last_draw.get('special')}")
    print("=" * 70)
    print()

    strategy_names = [
        "Fourier Rhythm (FFT 週期分析)",
        "Cold Numbers (冷號逆向思維)",
        "Tail Balance (尾數平衡覆蓋)"
    ]

    for i, (bet, sp_num, name) in enumerate(zip(bets, specials, strategy_names)):
        print(f"  注 {i+1}:  {bet}  |  特別號: {int(sp_num)}")
        print(f"         └─ {name}")
        print()

    print("-" * 70)
    print(f"  覆蓋統計:")
    print(f"    總覆蓋號碼: {len(all_nums)}/38 ({len(all_nums)/38*100:.1f}%)")
    print(f"    低區 (1-13): {coverage['low']} 個")
    print(f"    中區 (14-26): {coverage['mid']} 個")
    print(f"    高區 (27-38): {coverage['high']} 個")

    # 尾數覆蓋
    tails = set(n % 10 for n in all_nums)
    print(f"    尾數覆蓋: {len(tails)}/10 種 ({sorted(tails)})")
    print()
    print("=" * 70)
    print(f"  預測期數: {next_draw}")
    print(f"  基準日期: 最後入庫期 {last_draw['draw']} ({last_draw['date']})")
    print("=" * 70)


def run_backtest(draws, test_periods):
    """執行回測"""
    print("=" * 70)
    print(f"【回測驗證】威力彩 3 注策略 Triple Strike")
    print("=" * 70)
    print(f"測試期數: {test_periods}")
    print()

    # 正確的 N 注基準
    BASELINES = {1: 3.87, 2: 7.59, 3: 11.17}

    results = {
        'bet1_m3': 0, 'bet2_m3': 0, 'bet3_m3': 0,
        'any_m3': 0, 'total': 0,
        'bet1_hits': [], 'bet2_hits': [], 'bet3_hits': []
    }

    for i in range(test_periods):
        target_idx = len(draws) - test_periods + i
        if target_idx <= 500:
            continue

        target_draw = draws[target_idx]
        hist = draws[:target_idx]
        actual = set(target_draw['numbers'])

        # 生成預測
        bets = generate_triple_strike(hist)

        # 計算命中
        hits = [len(set(bet) & actual) for bet in bets]
        results['bet1_hits'].append(hits[0])
        results['bet2_hits'].append(hits[1])
        results['bet3_hits'].append(hits[2])

        if hits[0] >= 3:
            results['bet1_m3'] += 1
        if hits[1] >= 3:
            results['bet2_m3'] += 1
        if hits[2] >= 3:
            results['bet3_m3'] += 1
        if max(hits) >= 3:
            results['any_m3'] += 1

        results['total'] += 1

    total = results['total']

    # 統計
    print(f"{'策略':<30} {'M3+ 次數':<12} {'M3+ 率':<12} {'平均命中':<10}")
    print("-" * 70)

    bet1_rate = results['bet1_m3'] / total * 100
    bet2_rate = results['bet2_m3'] / total * 100
    bet3_rate = results['bet3_m3'] / total * 100
    any_rate = results['any_m3'] / total * 100

    avg1 = np.mean(results['bet1_hits'])
    avg2 = np.mean(results['bet2_hits'])
    avg3 = np.mean(results['bet3_hits'])

    print(f"{'注1 Fourier Rhythm':<30} {results['bet1_m3']:<12} {bet1_rate:.2f}%{'':<6} {avg1:.2f}")
    print(f"{'注2 Cold Numbers':<30} {results['bet2_m3']:<12} {bet2_rate:.2f}%{'':<6} {avg2:.2f}")
    print(f"{'注3 Tail Balance':<30} {results['bet3_m3']:<12} {bet3_rate:.2f}%{'':<6} {avg3:.2f}")
    print("-" * 70)
    print(f"{'3注組合 (任一注 M3+)':<30} {results['any_m3']:<12} {any_rate:.2f}%")
    print()

    # Edge 計算
    print("【Edge 分析】")
    print("-" * 70)
    print(f"  3注組合 M3+: {any_rate:.2f}%")
    print(f"  3注隨機基準: {BASELINES[3]:.2f}%")
    print(f"  Edge: {any_rate - BASELINES[3]:+.2f}%")
    print()

    # 與 2 注比較
    # 計算純 Fourier 2注
    fourier_2bet_m3 = 0
    for i in range(test_periods):
        target_idx = len(draws) - test_periods + i
        if target_idx <= 500:
            continue
        target_draw = draws[target_idx]
        hist = draws[:target_idx]
        actual = set(target_draw['numbers'])

        f1 = fourier_rhythm_bet(hist, window=500)
        # 計算第二注 (Fourier top 7-12)
        h_slice = hist[-500:] if len(hist) >= 500 else hist
        w = len(h_slice)
        scores = np.zeros(39)
        for n in range(1, 39):
            bh = np.zeros(w)
            for idx, d in enumerate(h_slice):
                if n in d['numbers']:
                    bh[idx] = 1
            if sum(bh) >= 2:
                yf = fft(bh - np.mean(bh))
                xf = fftfreq(w, 1)
                idx_pos = np.where(xf > 0)
                if len(idx_pos[0]) > 0:
                    pos_xf = xf[idx_pos]
                    pos_yf = np.abs(yf[idx_pos])
                    peak_idx = np.argmax(pos_yf)
                    freq_val = pos_xf[peak_idx]
                    if freq_val != 0:
                        period = 1 / freq_val
                        if 2 < period < w / 2:
                            last_hit = np.where(bh == 1)[0][-1]
                            gap = (w - 1) - last_hit
                            dist_to_peak = abs(gap - period)
                            scores[n] = 1.0 / (dist_to_peak + 1.0)
        all_idx = np.arange(1, 39)
        sorted_idx = all_idx[np.argsort(scores[1:])[::-1]]
        f2 = sorted(sorted_idx[6:12].tolist())

        f1_hits = len(set(f1) & actual)
        f2_hits = len(set(f2) & actual)
        if max(f1_hits, f2_hits) >= 3:
            fourier_2bet_m3 += 1

    fourier_2bet_rate = fourier_2bet_m3 / total * 100

    print("【與 2 注策略比較】")
    print("-" * 70)
    print(f"  Fourier 2注: {fourier_2bet_rate:.2f}% (Edge {fourier_2bet_rate - BASELINES[2]:+.2f}%)")
    print(f"  Triple Strike 3注: {any_rate:.2f}% (Edge {any_rate - BASELINES[3]:+.2f}%)")
    print()

    if any_rate - BASELINES[3] > fourier_2bet_rate - BASELINES[2]:
        print("  ✅ 3注策略 Edge 優於 2注策略！")
    else:
        print("  ⚠️ 3注策略 Edge 略低於 2注，但覆蓋更廣")

    print("=" * 70)


if __name__ == "__main__":
    main()
