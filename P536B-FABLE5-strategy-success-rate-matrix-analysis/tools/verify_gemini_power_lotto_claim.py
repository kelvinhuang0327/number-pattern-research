#!/usr/bin/env python3
"""
獨立驗證 Gemini 威力彩策略聲稱
"""
import sqlite3
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws(db_path: str, lottery_type: str = 'POWER_LOTTO') -> List[Dict]:
    """讀取開獎數據"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = ? ORDER BY date ASC
    """, (lottery_type,))
    draws = []
    for row in cursor.fetchall():
        numbers = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0],
            'date': row[1],
            'numbers': numbers
        })
    conn.close()
    return draws


# ============== 預測方法 (威力彩版本 max=38) ==============

def markov_predict(history: List[Dict], rules: Dict) -> List[int]:
    """馬可夫預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    transitions = defaultdict(Counter)
    for i in range(len(history) - 1):
        curr_nums = set(history[i]['numbers'])
        next_nums = set(history[i + 1]['numbers'])
        for num in curr_nums:
            for next_num in next_nums:
                transitions[num][next_num] += 1

    last_draw = set(history[-1]['numbers'])
    scores = Counter()
    for num in last_draw:
        for next_num, count in transitions[num].items():
            scores[next_num] += count

    selected = [n for n, _ in scores.most_common(pick_count)]

    if len(selected) < pick_count:
        for n in range(1, max_num + 1):
            if n not in selected:
                selected.append(n)
            if len(selected) >= pick_count:
                break

    return sorted(selected[:pick_count])


def statistical_predict(history: List[Dict], rules: Dict) -> List[int]:
    """統計預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    freq = Counter()
    for draw in history[-100:]:
        for num in draw['numbers']:
            freq[num] += 1

    gap = {}
    for num in range(1, max_num + 1):
        gap[num] = 0
        for i, draw in enumerate(reversed(history)):
            if num in draw['numbers']:
                gap[num] = i
                break

    scores = Counter()
    for num in range(1, max_num + 1):
        scores[num] = freq.get(num, 0) * 0.6 + gap.get(num, 0) * 0.4

    selected = [n for n, _ in scores.most_common(pick_count)]
    return sorted(selected[:pick_count])


def deviation_predict(history: List[Dict], rules: Dict) -> List[int]:
    """偏差預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    total_picks = sum(len(d['numbers']) for d in history)
    expected = total_picks / max_num

    freq = Counter()
    for draw in history:
        for num in draw['numbers']:
            freq[num] += 1

    scores = Counter()
    for num in range(1, max_num + 1):
        actual = freq.get(num, 0)
        deviation = expected - actual
        scores[num] = deviation

    selected = [n for n, _ in scores.most_common(pick_count)]
    return sorted(selected[:pick_count])


def frequency_predict(history: List[Dict], rules: Dict) -> List[int]:
    """頻率預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    freq = Counter()
    for draw in history[-50:]:
        for num in draw['numbers']:
            freq[num] += 1

    selected = [n for n, _ in freq.most_common(pick_count)]
    return sorted(selected[:pick_count])


def trend_predict(history: List[Dict], rules: Dict) -> List[int]:
    """趨勢預測"""
    if len(history) < 20:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    recent = Counter()
    for draw in history[-20:]:
        for num in draw['numbers']:
            recent[num] += 1

    medium = Counter()
    for draw in history[-50:-20]:
        for num in draw['numbers']:
            medium[num] += 1

    scores = Counter()
    for num in range(1, max_num + 1):
        r = recent.get(num, 0) / 20
        m = medium.get(num, 0) / 30 if medium.get(num, 0) else 0.01
        scores[num] = r / max(m, 0.01)

    selected = [n for n, _ in scores.most_common(pick_count)]
    return sorted(selected[:pick_count])


def bayesian_predict(history: List[Dict], rules: Dict) -> List[int]:
    """貝葉斯預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    prior = 1.0 / max_num

    freq = Counter()
    for draw in history:
        for num in draw['numbers']:
            freq[num] += 1

    total = sum(freq.values())
    posterior = {}
    for num in range(1, max_num + 1):
        likelihood = freq.get(num, 0) / total if total > 0 else prior
        posterior[num] = likelihood * prior

    total_post = sum(posterior.values())
    if total_post > 0:
        posterior = {k: v / total_post for k, v in posterior.items()}

    selected = sorted(posterior.keys(), key=lambda x: -posterior[x])[:pick_count]
    return sorted(selected)


def hot_cold_mix_predict(history: List[Dict], rules: Dict) -> List[int]:
    """冷熱混合"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 38)
    pick_count = rules.get('pickCount', 6)

    recent_freq = Counter()
    for draw in history[-30:]:
        for num in draw['numbers']:
            recent_freq[num] += 1

    hot = [n for n, _ in recent_freq.most_common(pick_count // 2 + 1)]

    cold = [n for n in range(1, max_num + 1) if recent_freq.get(n, 0) == 0]
    if len(cold) < pick_count // 2:
        cold = [n for n, _ in recent_freq.most_common()[-(pick_count // 2):]]

    selected = hot[:3] + cold[:3]

    for n in range(1, max_num + 1):
        if n not in selected and len(selected) < pick_count:
            selected.append(n)

    return sorted(selected[:pick_count])


# ============== 回測邏輯 ==============

def run_backtest_single(history_full: List[Dict], rules: Dict,
                        predict_fn, test_periods: int = 150) -> Dict:
    """單一方法回測"""
    start_idx = len(history_full) - test_periods

    m3 = 0
    m4 = 0
    total = 0

    for target_idx in range(start_idx, len(history_full)):
        history = history_full[:target_idx]
        target = history_full[target_idx]

        if len(history) < 100:
            continue

        actual = set(target['numbers'])
        predicted = predict_fn(history, rules)

        if not predicted:
            continue

        match = len(set(predicted) & actual)
        total += 1

        if match >= 3:
            m3 += 1
        if match >= 4:
            m4 += 1

    return {
        'm3': m3,
        'm4': m4,
        'total': total,
        'rate': m3 / total * 100 if total > 0 else 0
    }


def run_backtest_multi(history_full: List[Dict], rules: Dict,
                       predict_fns: List, test_periods: int = 150) -> Dict:
    """多注方法回測"""
    start_idx = len(history_full) - test_periods

    m3_periods = 0
    m4_periods = 0
    total = 0
    per_bet_m3 = 0
    total_bets = 0

    for target_idx in range(start_idx, len(history_full)):
        history = history_full[:target_idx]
        target = history_full[target_idx]

        if len(history) < 100:
            continue

        actual = set(target['numbers'])
        max_match = 0

        for predict_fn in predict_fns:
            predicted = predict_fn(history, rules)
            if not predicted:
                continue

            match = len(set(predicted) & actual)
            total_bets += 1

            if match > max_match:
                max_match = match
            if match >= 3:
                per_bet_m3 += 1

        total += 1
        if max_match >= 3:
            m3_periods += 1
        if max_match >= 4:
            m4_periods += 1

    return {
        'm3_periods': m3_periods,
        'm4_periods': m4_periods,
        'total': total,
        'rate': m3_periods / total * 100 if total > 0 else 0,
        'per_bet_m3': per_bet_m3,
        'total_bets': total_bets,
        'per_bet_rate': per_bet_m3 / total_bets * 100 if total_bets > 0 else 0
    }


def run_verification(test_periods: int = 150):
    """運行完整驗證"""
    print("=" * 80)
    print("🔬 獨立驗證 Gemini 威力彩策略聲稱")
    print("=" * 80)

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='POWER_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")

    rules = {
        'name': 'POWER_LOTTO',
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 38,
    }

    # ============== 1. 單注 Markov 驗證 ==============
    print("\n" + "=" * 80)
    print("📊 1. 單注 Markov 驗證 (Gemini 聲稱: 3.50%)")
    print("=" * 80)

    markov_result = run_backtest_single(all_draws, rules, markov_predict, test_periods)
    print(f"Match-3+: {markov_result['m3']}/{markov_result['total']}")
    print(f"Match-3+ 率: {markov_result['rate']:.2f}%")
    print(f"Gemini 聲稱: 3.50%")
    diff = markov_result['rate'] - 3.50
    print(f"差異: {diff:+.2f}%")

    # ============== 2. 2注 Statistical+Frequency 驗證 ==============
    print("\n" + "=" * 80)
    print("📊 2. 2注 Statistical+Frequency 驗證 (Gemini 聲稱: 10.00%)")
    print("=" * 80)

    two_bet_result = run_backtest_multi(
        all_draws, rules,
        [statistical_predict, frequency_predict],
        test_periods
    )
    print(f"Match-3+ 期數: {two_bet_result['m3_periods']}/{two_bet_result['total']}")
    print(f"每期 Match-3+ 率: {two_bet_result['rate']:.2f}%")
    print(f"每注 Match-3+ 率: {two_bet_result['per_bet_rate']:.2f}%")
    print(f"Gemini 聲稱: 10.00%")
    diff = two_bet_result['rate'] - 10.00
    print(f"差異: {diff:+.2f}%")

    # ============== 3. 4注 Top4 Methods 驗證 ==============
    print("\n" + "=" * 80)
    print("📊 3. 4注 Top4 Methods 驗證 (Gemini 聲稱: 18.00%)")
    print("=" * 80)

    four_bet_result = run_backtest_multi(
        all_draws, rules,
        [statistical_predict, frequency_predict, deviation_predict, markov_predict],
        test_periods
    )
    print(f"Match-3+ 期數: {four_bet_result['m3_periods']}/{four_bet_result['total']}")
    print(f"Match-4+ 期數: {four_bet_result['m4_periods']}")
    print(f"每期 Match-3+ 率: {four_bet_result['rate']:.2f}%")
    print(f"每注 Match-3+ 率: {four_bet_result['per_bet_rate']:.2f}%")
    print(f"Gemini 聲稱: 18.00%")
    diff = four_bet_result['rate'] - 18.00
    print(f"差異: {diff:+.2f}%")

    # ============== 隨機基準 ==============
    print("\n" + "=" * 80)
    print("📊 隨機基準對比")
    print("=" * 80)

    random.seed(42)
    start_idx = len(all_draws) - test_periods

    def test_random(num_bets, trials=50):
        total = 0
        for _ in range(trials):
            count = 0
            for target_idx in range(start_idx, len(all_draws)):
                actual = set(all_draws[target_idx]['numbers'])
                max_m = 0
                for _ in range(num_bets):
                    bet = set(random.sample(range(1, 39), 6))
                    max_m = max(max_m, len(bet & actual))
                if max_m >= 3:
                    count += 1
            total += count
        return total / trials / test_periods * 100

    rand1 = test_random(1)
    rand2 = test_random(2)
    rand4 = test_random(4)

    print(f"\n隨機 1 注: {rand1:.2f}%")
    print(f"隨機 2 注: {rand2:.2f}%")
    print(f"隨機 4 注: {rand4:.2f}%")

    # ============== 總結 ==============
    print("\n" + "=" * 80)
    print("📊 驗證總結")
    print("=" * 80)

    print(f"\n| 策略 | Gemini 聲稱 | 獨立驗證 | 隨機基準 | vs 聲稱 | vs 隨機 |")
    print(f"|------|------------|----------|----------|---------|---------|")

    m1_diff = markov_result['rate'] - 3.50
    m1_rand_diff = markov_result['rate'] - rand1
    status1 = "✅" if abs(m1_diff) < 1.5 and m1_rand_diff > 0 else "❌"
    print(f"| 1注 Markov | 3.50% | {markov_result['rate']:.2f}% | {rand1:.2f}% | {m1_diff:+.2f}% | {m1_rand_diff:+.2f}% | {status1}")

    m2_diff = two_bet_result['rate'] - 10.00
    m2_rand_diff = two_bet_result['rate'] - rand2
    status2 = "✅" if abs(m2_diff) < 2 and m2_rand_diff > 0 else "❌"
    print(f"| 2注 Stat+Freq | 10.00% | {two_bet_result['rate']:.2f}% | {rand2:.2f}% | {m2_diff:+.2f}% | {m2_rand_diff:+.2f}% | {status2}")

    m4_diff = four_bet_result['rate'] - 18.00
    m4_rand_diff = four_bet_result['rate'] - rand4
    status4 = "✅" if abs(m4_diff) < 3 and m4_rand_diff > 0 else "❌"
    print(f"| 4注 Top4 | 18.00% | {four_bet_result['rate']:.2f}% | {rand4:.2f}% | {m4_diff:+.2f}% | {m4_rand_diff:+.2f}% | {status4}")

    return {
        'markov_1bet': markov_result,
        'stat_freq_2bet': two_bet_result,
        'top4_4bet': four_bet_result,
        'random': {'1bet': rand1, '2bet': rand2, '4bet': rand4}
    }


if __name__ == '__main__':
    run_verification(test_periods=150)
