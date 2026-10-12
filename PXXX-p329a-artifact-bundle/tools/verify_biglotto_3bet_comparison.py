#!/usr/bin/env python3
"""
大樂透 3 注策略對比驗證
========================
公平比較 Apriori 與 Triple Strike 在相同期數下的表現

2026-01-30
"""
import os
import sys
import numpy as np
from collections import Counter
from scipy.fft import fft, fftfreq
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from tools.predict_biglotto_apriori import BigLottoAprioriPredictor

np.random.seed(42)
random.seed(42)

# 大樂透正確 baseline
BASELINE_3BET = 5.49  # 1 - (1 - 0.0186)^3 ≈ 5.49%

# ========== Triple Strike for Big Lotto ==========

def fourier_rhythm_bet_biglotto(history, window=500):
    """Fourier Rhythm for Big Lotto (1-49)"""
    h_slice = history[-window:] if len(history) >= window else history
    w = len(h_slice)
    max_num = 49

    bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
    for idx, d in enumerate(h_slice):
        for n in d['numbers']:
            if n <= max_num:
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
        if len(pos_yf) == 0:
            continue
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


def cold_numbers_bet_biglotto(history, window=100, exclude=None):
    """Cold Numbers for Big Lotto (1-49)"""
    if exclude is None:
        exclude = set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)
    candidates = [n for n in range(1, 50) if n not in exclude]
    sorted_cold = sorted(candidates, key=lambda x: freq.get(x, 0))
    return sorted(sorted_cold[:6])


def tail_balance_bet_biglotto(history, window=100, exclude=None):
    """Tail Balance for Big Lotto (1-49)"""
    if exclude is None:
        exclude = set()
    recent = history[-window:] if len(history) >= window else history
    all_nums = [n for d in recent for n in d['numbers']]
    freq = Counter(all_nums)

    tail_groups = {i: [] for i in range(10)}
    for n in range(1, 50):
        if n not in exclude:
            tail = n % 10
            tail_groups[tail].append((n, freq.get(n, 0)))

    for tail in tail_groups:
        tail_groups[tail].sort(key=lambda x: x[1], reverse=True)

    selected = []
    available_tails = [t for t in range(10) if tail_groups[t]]
    available_tails.sort(key=lambda t: tail_groups[t][0][1] if tail_groups[t] else 0, reverse=True)

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
        if round_num > 10:
            break

    if len(selected) < 6:
        remaining = [n for n in range(1, 50) if n not in selected and n not in exclude]
        remaining.sort(key=lambda x: freq.get(x, 0), reverse=True)
        selected.extend(remaining[:6 - len(selected)])

    return sorted(selected[:6])


def triple_strike_biglotto(history):
    """Generate 3 bets using Triple Strike for Big Lotto"""
    bet1 = fourier_rhythm_bet_biglotto(history, window=500)
    exclude1 = set(bet1)
    bet2 = cold_numbers_bet_biglotto(history, window=100, exclude=exclude1)
    exclude2 = exclude1 | set(bet2)
    bet3 = tail_balance_bet_biglotto(history, window=100, exclude=exclude2)
    return [bet1, bet2, bet3]


# ========== Apriori Adapter ==========

class AprioriAdapter(BigLottoAprioriPredictor):
    def predict_3bets(self, history, window=150):
        recent_history = history[-window:]
        frequent = self.mine_frequent_itemsets(recent_history, min_support=3)
        rules = self.generate_rules(frequent, min_confidence=0.4)

        bets = []
        used_rules = set()

        for i in range(3):
            target_rule = None
            for r in rules:
                r_key = r['antecedent']
                if r_key not in used_rules:
                    target_rule = r
                    used_rules.add(r_key)
                    break

            if not target_rule:
                remaining = list(range(1, 50))
                bets.append(sorted(random.sample(remaining, 6)))
                continue

            core = list(target_rule['antecedent']) + [target_rule['consequent']]
            current_nums = sorted(list(set(core)))

            while len(current_nums) < 6:
                best_next = None
                last_num = current_nums[-1]

                candidates = []
                for r in rules:
                    if r['consequent'] not in current_nums:
                        if r['antecedent'] == (last_num,) or (len(r['antecedent']) == 1 and r['antecedent'][0] in current_nums):
                            candidates.append(r)

                if candidates:
                    candidates.sort(key=lambda x: x['confidence'], reverse=True)
                    best_next = candidates[0]['consequent']
                else:
                    remaining = [n for n in range(1, 50) if n not in current_nums]
                    if not remaining:
                        break
                    best_next = remaining[i % len(remaining)]

                current_nums.append(best_next)
                current_nums = sorted(list(set(current_nums)))

            bets.append(sorted(current_nums[:6]))

        return bets


def run_comparison():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    apriori_adapter = AprioriAdapter()

    print("=" * 70)
    print("  大樂透 3 注策略公平對比驗證")
    print("=" * 70)
    print(f"  總期數: {len(draws)}")
    print(f"  3注隨機基準: {BASELINE_3BET:.2f}%")
    print("=" * 70)
    print()

    test_periods_list = [150, 500, 1000, len(draws) - 501]

    print(f"{'測試週期':<12} {'Apriori':<20} {'Triple Strike':<20} {'優勝':<10}")
    print("-" * 70)

    for test_periods in test_periods_list:
        if test_periods > len(draws) - 501:
            test_periods = len(draws) - 501

        apriori_wins = 0
        ts_wins = 0

        for i in range(test_periods):
            target_idx = len(draws) - test_periods + i
            if target_idx <= 500:
                continue

            target_draw = draws[target_idx]
            hist = draws[:target_idx]
            actual = set(target_draw['numbers'])

            # Apriori
            try:
                apriori_bets = apriori_adapter.predict_3bets(hist, window=150)
                apriori_hits = [len(set(b) & actual) for b in apriori_bets]
                if max(apriori_hits) >= 3:
                    apriori_wins += 1
            except:
                pass

            # Triple Strike
            ts_bets = triple_strike_biglotto(hist)
            ts_hits = [len(set(b) & actual) for b in ts_bets]
            if max(ts_hits) >= 3:
                ts_wins += 1

        valid_periods = min(test_periods, len(draws) - 501)
        apriori_rate = apriori_wins / valid_periods * 100
        ts_rate = ts_wins / valid_periods * 100
        apriori_edge = apriori_rate - BASELINE_3BET
        ts_edge = ts_rate - BASELINE_3BET

        winner = "Apriori" if apriori_edge > ts_edge else ("Triple Strike" if ts_edge > apriori_edge else "平手")

        print(f"{test_periods:<12} {apriori_rate:.2f}% (Edge {apriori_edge:+.2f}%){'':<3} {ts_rate:.2f}% (Edge {ts_edge:+.2f}%){'':<3} {winner}")

    print()
    print("=" * 70)
    print("  結論分析")
    print("=" * 70)


if __name__ == '__main__':
    run_comparison()
