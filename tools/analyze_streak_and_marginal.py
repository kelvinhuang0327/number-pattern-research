#!/usr/bin/env python3
"""
Task 2: Consecutive Streak Conditional Lift (539)
Task 3: P3 Marginal Efficiency for lag-3 as 4th bet
"""
import json
import sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')


def load_539_history():
    import os
    os.chdir('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
    sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')
    from database import DatabaseManager
    db = DatabaseManager()
    raw = db.get_all_draws('DAILY_539')
    draws = []
    for d in raw:
        nums = d.get('numbers', [])
        if isinstance(nums, str):
            nums = json.loads(nums)
        draws.append({'period': d['draw'], 'date': d.get('date', ''), 'numbers': sorted(nums)})
    draws.sort(key=lambda x: x['period'])
    print(f"DB loaded: 539 count={len(draws)}, first={draws[0]['period']}, last={draws[-1]['period']}")
    return draws


# =====================
# TASK 2: Consecutive Streak
# =====================

def consecutive_streak_analysis(draws):
    MAX_NUM = 39
    n = len(draws)

    appear = np.zeros((n, MAX_NUM + 1), dtype=int)
    for i, d in enumerate(draws):
        for num in d['numbers']:
            appear[i][num] = 1

    baseline_arr = appear.sum(axis=0) / n
    avg_baseline = float(baseline_arr[1:].mean())

    s1_n = np.zeros(MAX_NUM + 1, dtype=int)
    s1_match = np.zeros(MAX_NUM + 1, dtype=int)
    s2_n = np.zeros(MAX_NUM + 1, dtype=int)
    s2_match = np.zeros(MAX_NUM + 1, dtype=int)

    for t in range(2, n):
        for num in range(1, MAX_NUM + 1):
            if appear[t-1][num] == 1:
                s1_n[num] += 1
                if appear[t][num] == 1:
                    s1_match[num] += 1
            if appear[t-1][num] == 1 and appear[t-2][num] == 1:
                s2_n[num] += 1
                if appear[t][num] == 1:
                    s2_match[num] += 1

    from scipy.stats import binomtest

    all_s1_n = int(s1_n[1:].sum())
    all_s1_match = int(s1_match[1:].sum())
    all_s2_n = int(s2_n[1:].sum())
    all_s2_match = int(s2_match[1:].sum())

    s1_p_cond = all_s1_match / all_s1_n if all_s1_n > 0 else 0.0
    s2_p_cond = all_s2_match / all_s2_n if all_s2_n > 0 else 0.0
    s1_lift = s1_p_cond / avg_baseline if avg_baseline > 0 else 0.0
    s2_lift = s2_p_cond / avg_baseline if avg_baseline > 0 else 0.0

    s1_bt = binomtest(all_s1_match, all_s1_n, avg_baseline, alternative='two-sided')
    s2_bt = binomtest(all_s2_match, all_s2_n, avg_baseline, alternative='two-sided')

    print("\n=== Task 2: Consecutive Streak Analysis ===")
    print(f"總期數: {n}")
    print(f"全域 baseline P(appear): {avg_baseline:.4f} (理論 5/39 = {5/39:.4f})")
    print()
    print(f"Streak=1 (前1期出現):")
    print(f"  n={all_s1_n}, match={all_s1_match}")
    print(f"  P(appear|streak=1)={s1_p_cond:.4f}")
    print(f"  Lift={s1_lift:.4f} | p={s1_bt.pvalue:.6f} {'✓ SIGNIFICANT' if s1_bt.pvalue < 0.05 else '✗ not sig'}")
    print()
    print(f"Streak=2 (前2期連續出現):")
    print(f"  n={all_s2_n}, match={all_s2_match}")
    print(f"  P(appear|streak=2)={s2_p_cond:.4f}")
    print(f"  Lift={s2_lift:.4f} | p={s2_bt.pvalue:.6f} {'✓ SIGNIFICANT' if s2_bt.pvalue < 0.05 else '✗ not sig'}")

    # Per-number top streakers
    print("\n=== Top 10 Streak=1 Lift 號碼 ===")
    num_results = []
    for num in range(1, MAX_NUM + 1):
        if s1_n[num] >= 30:
            b = float(baseline_arr[num])
            p_c = float(s1_match[num]) / float(s1_n[num]) if s1_n[num] > 0 else 0
            lift = p_c / b if b > 0 else 0
            num_results.append((num, int(s1_n[num]), int(s1_match[num]), round(p_c, 4), round(lift, 4)))
    num_results.sort(key=lambda x: x[4], reverse=True)
    for num, nv, match, pc, lift in num_results[:10]:
        print(f"  #{num:02d}: n={nv} match={match} p_cond={pc} lift={lift}")

    print("\n=== 可操作性判斷 ===")
    if s1_lift > 1.2 and s1_bt.pvalue < 0.05:
        print(f"✅ Streak=1 Lift={s1_lift:.3f} > 1.2x + p<0.05 → 可研究")
    else:
        print(f"❌ Streak=1 Lift={s1_lift:.3f} — {'不足 1.2x' if s1_lift <= 1.2 else '不顯著'} → REJECT")
    if s2_lift > 1.2 and s2_bt.pvalue < 0.05:
        print(f"✅ Streak=2 Lift={s2_lift:.3f} > 1.2x + p<0.05 → 可研究")
    else:
        print(f"❌ Streak=2 Lift={s2_lift:.3f} — {'不足 1.2x' if s2_lift <= 1.2 else '不顯著'} → REJECT")

    return {
        'baseline': round(avg_baseline, 4),
        'streak1': {
            'n': all_s1_n, 'match': all_s1_match,
            'p_conditional': round(s1_p_cond, 4),
            'lift': round(s1_lift, 4),
            'p_value': round(float(s1_bt.pvalue), 6),
            'actionable': bool(s1_lift > 1.2 and s1_bt.pvalue < 0.05)
        },
        'streak2': {
            'n': all_s2_n, 'match': all_s2_match,
            'p_conditional': round(s2_p_cond, 4),
            'lift': round(s2_lift, 4),
            'p_value': round(float(s2_bt.pvalue), 6),
            'actionable': bool(s2_lift > 1.2 and s2_bt.pvalue < 0.05)
        }
    }


# =====================
# TASK 3: P3 Marginal Efficiency
# =====================

def marginal_efficiency_analysis(draws):
    MAX_NUM = 39
    WINDOW_ACB = 100
    WINDOW_MID = 200

    n = len(draws)
    start = max(WINDOW_MID + 3, 300)

    def acb_scores(hist):
        freq = defaultdict(int)
        for d in hist[-WINDOW_ACB:]:
            for num in d['numbers']:
                freq[num] += 1
        last_seen = {}
        for i, d in enumerate(hist):
            for num in d['numbers']:
                last_seen[num] = i
        cur_pos = len(hist) - 1
        expected_freq = WINDOW_ACB * 5 / MAX_NUM
        scores = {}
        for num in range(1, MAX_NUM + 1):
            gap = cur_pos - last_seen.get(num, -50)
            freq_deficit = max(0, expected_freq - freq.get(num, 0)) / expected_freq
            gap_score = min(gap / 20, 1.0)
            boundary = 1.2 if (num <= 5 or num >= 35) else 1.0
            scores[num] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary
        return scores

    def midfreq_scores(hist):
        freq = defaultdict(int)
        for d in hist[-WINDOW_MID:]:
            for num in d['numbers']:
                freq[num] += 1
        expected = WINDOW_MID * 5 / MAX_NUM
        scores = {}
        for num in range(1, MAX_NUM + 1):
            f = freq.get(num, 0)
            ratio = f / expected if expected > 0 else 0
            scores[num] = (1.0 - abs(ratio - 1.0)) if 0.5 <= ratio <= 1.5 else 0.0
        return scores

    def make_bet(scores, exclude, top_n=5):
        candidates = [(s, num) for num, s in scores.items() if num not in exclude]
        candidates.sort(reverse=True)
        return [num for _, num in candidates[:top_n]]

    def count_match(bet, actual):
        return sum(1 for num in bet if num in actual)

    m3_3bet = 0
    m3_4bet = 0
    total = 0

    for t in range(start, n):
        hist = draws[:t]
        actual = set(draws[t]['numbers'])

        acb = acb_scores(hist)
        mid = midfreq_scores(hist)

        bet1 = make_bet(acb, set())
        bet2 = make_bet(mid, set(bet1))
        combined = {num: acb.get(num, 0) * 0.5 + mid.get(num, 0) * 0.5
                    for num in range(1, MAX_NUM + 1)}
        bet3 = make_bet(combined, set(bet1) | set(bet2))

        # lag-3 bet
        if t >= 3:
            lag3_nums = draws[t-3]['numbers']
            lag3_scores = {num: acb.get(num, 0) for num in lag3_nums}
            bet4 = sorted(lag3_scores, key=lambda x: lag3_scores[x], reverse=True)[:5]
        else:
            bet4 = []

        matches = [count_match(b, actual) for b in [bet1, bet2, bet3]]
        best3 = max(matches)
        best4 = max(best3, count_match(bet4, actual)) if bet4 else best3

        if best3 >= 3:
            m3_3bet += 1
        if best4 >= 3:
            m3_4bet += 1
        total += 1

    # Edge approximation
    RANDOM_SINGLE = 5 / 39
    edge_3bet = (m3_3bet / total - 3 * RANDOM_SINGLE) / (3 * RANDOM_SINGLE)
    edge_4bet = (m3_4bet / total - 4 * RANDOM_SINGLE) / (4 * RANDOM_SINGLE)
    marginal_gain = m3_4bet - m3_3bet
    marginal_eff = (edge_4bet - edge_3bet) / abs(edge_3bet) if edge_3bet != 0 else 0

    print(f"\n=== Task 3: P3 邊際效率分析（lag-3 作第4注）===")
    print(f"模擬期數: {total} (從第 {start} 期起)")
    print()
    print(f"3注:")
    print(f"  M3+ 次數: {m3_3bet}/{total} = {m3_3bet/total:.4f}")
    print(f"  近似 Edge: {edge_3bet*100:.2f}%")
    print()
    print(f"4注 (3注 + lag-3):")
    print(f"  M3+ 次數: {m3_4bet}/{total} = {m3_4bet/total:.4f}")
    print(f"  近似 Edge: {edge_4bet*100:.2f}%")
    print(f"  新增命中: {marginal_gain} 期")
    print(f"  邊際效率: {marginal_eff*100:.1f}%")
    print()
    threshold = 0.80
    if marginal_eff >= threshold:
        decision = f"✅ 邊際效率 {marginal_eff*100:.1f}% >= 80% → 通過門檻，可進行完整回測"
    else:
        decision = f"❌ 邊際效率 {marginal_eff*100:.1f}% < 80% → REJECT (不需完整回測)"
    print(f"決定: {decision}")

    return {
        'total_periods': total,
        'edge_3bet_approx': round(edge_3bet, 4),
        'edge_4bet_approx': round(edge_4bet, 4),
        'marginal_gain_periods': int(marginal_gain),
        'marginal_efficiency': round(marginal_eff, 4),
        'threshold': threshold,
        'pass': bool(marginal_eff >= threshold),
        'decision': decision
    }


if __name__ == '__main__':
    print("=== 載入 539 歷史數據 ===")
    draws = load_539_history()
    print(f"總期數: {len(draws)}")

    streak_results = consecutive_streak_analysis(draws)
    marginal_results = marginal_efficiency_analysis(draws)

    results = {
        'streak_analysis': streak_results,
        'marginal_efficiency': marginal_results
    }
    out_path = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/tools/streak_marginal_results.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 結果已存至 {out_path}")
    print(json.dumps(results, indent=2, ensure_ascii=False))
