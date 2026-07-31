#!/usr/bin/env python3
"""
獨立驗證 Gemini Phase 2 聲稱的 14% Match-3+ 率
完全不使用 Gemini 的代碼，從頭實現驗證
"""
import sqlite3
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict, Set
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_all_draws(db_path: str, lottery_type: str = 'BIG_LOTTO') -> List[Dict]:
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


# ============== 複製 Gemini 聲稱使用的方法 ==============

def markov_predict(history: List[Dict], rules: Dict) -> List[int]:
    """馬可夫預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 建立轉移矩陣
    transitions = defaultdict(Counter)
    for i in range(len(history) - 1):
        curr_nums = set(history[i]['numbers'])
        next_nums = set(history[i + 1]['numbers'])
        for num in curr_nums:
            for next_num in next_nums:
                transitions[num][next_num] += 1

    # 計算號碼分數
    last_draw = set(history[-1]['numbers'])
    scores = Counter()
    for num in last_draw:
        for next_num, count in transitions[num].items():
            scores[next_num] += count

    # 選擇最高分
    selected = [n for n, _ in scores.most_common(pick_count)]

    # 補足
    if len(selected) < pick_count:
        for n in range(1, max_num + 1):
            if n not in selected:
                selected.append(n)
            if len(selected) >= pick_count:
                break

    return sorted(selected[:pick_count])


def statistical_predict(history: List[Dict], rules: Dict) -> List[int]:
    """統計預測（頻率 + 遺漏）"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 計算頻率
    freq = Counter()
    for draw in history[-100:]:
        for num in draw['numbers']:
            freq[num] += 1

    # 計算遺漏
    gap = {}
    for num in range(1, max_num + 1):
        gap[num] = 0
        for i, draw in enumerate(reversed(history)):
            if num in draw['numbers']:
                gap[num] = i
                break

    # 綜合分數
    scores = Counter()
    for num in range(1, max_num + 1):
        scores[num] = freq.get(num, 0) * 0.6 + gap.get(num, 0) * 0.4

    selected = [n for n, _ in scores.most_common(pick_count)]
    return sorted(selected[:pick_count])


def deviation_predict(history: List[Dict], rules: Dict) -> List[int]:
    """偏差預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 計算期望頻率
    total_picks = sum(len(d['numbers']) for d in history)
    expected = total_picks / max_num

    # 實際頻率
    freq = Counter()
    for draw in history:
        for num in draw['numbers']:
            freq[num] += 1

    # 偏差分數（選擇低於期望的號碼 - 回歸均值）
    scores = Counter()
    for num in range(1, max_num + 1):
        actual = freq.get(num, 0)
        deviation = expected - actual  # 正偏差表示出現少
        scores[num] = deviation

    selected = [n for n, _ in scores.most_common(pick_count)]
    return sorted(selected[:pick_count])


def frequency_predict(history: List[Dict], rules: Dict) -> List[int]:
    """純頻率預測"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 49)
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

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 比較近期 vs 中期頻率
    recent = Counter()
    for draw in history[-20:]:
        for num in draw['numbers']:
            recent[num] += 1

    medium = Counter()
    for draw in history[-50:-20]:
        for num in draw['numbers']:
            medium[num] += 1

    # 趨勢分數 = 近期增長
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

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 先驗：均勻分佈
    prior = 1.0 / max_num

    # 計算後驗
    freq = Counter()
    for draw in history:
        for num in draw['numbers']:
            freq[num] += 1

    total = sum(freq.values())
    posterior = {}
    for num in range(1, max_num + 1):
        likelihood = freq.get(num, 0) / total if total > 0 else prior
        posterior[num] = likelihood * prior

    # 歸一化
    total_post = sum(posterior.values())
    if total_post > 0:
        posterior = {k: v / total_post for k, v in posterior.items()}

    selected = sorted(posterior.keys(), key=lambda x: -posterior[x])[:pick_count]
    return sorted(selected)


def hot_cold_mix_predict(history: List[Dict], rules: Dict) -> List[int]:
    """冷熱混合"""
    if len(history) < 10:
        return []

    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)

    # 熱號（近期高頻）
    recent_freq = Counter()
    for draw in history[-30:]:
        for num in draw['numbers']:
            recent_freq[num] += 1

    hot = [n for n, _ in recent_freq.most_common(pick_count // 2 + 1)]

    # 冷號（近期低頻）
    cold = [n for n in range(1, max_num + 1) if recent_freq.get(n, 0) == 0]
    if len(cold) < pick_count // 2:
        cold = [n for n, _ in recent_freq.most_common()[-(pick_count // 2):]]

    # 混合
    selected = hot[:3] + cold[:3]

    # 補足
    for n in range(1, max_num + 1):
        if n not in selected and len(selected) < pick_count:
            selected.append(n)

    return sorted(selected[:pick_count])


# ============== 7 注策略 ==============

def generate_7_bets(history: List[Dict], rules: Dict) -> List[List[int]]:
    """
    生成 7 注預測（模擬 Gemini 的 diversified_bets）
    """
    methods = [
        ('markov', markov_predict),
        ('statistical', statistical_predict),
        ('deviation', deviation_predict),
        ('frequency', frequency_predict),
        ('trend', trend_predict),
        ('bayesian', bayesian_predict),
        ('hot_cold_mix', hot_cold_mix_predict),
    ]

    bets = []
    for name, func in methods:
        try:
            bet = func(history, rules)
            if bet and len(bet) == rules.get('pickCount', 6):
                bets.append(bet)
        except Exception as e:
            print(f"  警告: {name} 預測失敗: {e}")

    return bets


def run_verification(test_periods: int = 150):
    """運行獨立驗證"""
    print("=" * 80)
    print("🔬 獨立驗證 Gemini Phase 2 聲稱")
    print("=" * 80)
    print(f"Gemini 聲稱: 7注策略達到 14.00% Match-3+ 率 (150期)")
    print()

    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    all_draws = get_all_draws(db_path, lottery_type='BIG_LOTTO')

    print(f"總數據量: {len(all_draws)} 期")
    print(f"回測期數: {test_periods}")

    rules = {
        'name': 'BIG_LOTTO',
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
    }

    start_idx = len(all_draws) - test_periods

    results = {
        'm3': 0,
        'm4': 0,
        'm5': 0,
        'total': 0,
        'per_bet_m3': 0,
        'total_bets': 0,
        'method_wins': Counter(),
    }

    print(f"\n開始回測 (期 {all_draws[start_idx]['draw']} ~ {all_draws[-1]['draw']})...")

    for target_idx in range(start_idx, len(all_draws)):
        # 嚴格使用過去數據
        history = all_draws[:target_idx]
        target = all_draws[target_idx]

        if len(history) < 100:
            continue

        actual = set(target['numbers'])

        # 生成 7 注
        bets = generate_7_bets(history, rules)

        if not bets:
            continue

        max_match = 0
        period_m3 = False

        for i, bet in enumerate(bets):
            match_count = len(set(bet) & actual)

            if match_count > max_match:
                max_match = match_count

            if match_count >= 3:
                results['per_bet_m3'] += 1
                period_m3 = True

            results['total_bets'] += 1

        results['total'] += 1

        if max_match >= 3:
            results['m3'] += 1
        if max_match >= 4:
            results['m4'] += 1
        if max_match >= 5:
            results['m5'] += 1

    # 輸出結果
    print("\n" + "=" * 80)
    print("📊 獨立驗證結果")
    print("=" * 80)

    total = results['total']
    m3_rate = results['m3'] / total * 100 if total > 0 else 0
    m4_rate = results['m4'] / total * 100 if total > 0 else 0
    per_bet_rate = results['per_bet_m3'] / results['total_bets'] * 100 if results['total_bets'] > 0 else 0

    print(f"\n測試期數: {total}")
    print(f"總注數: {results['total_bets']}")
    print()
    print(f"Match-3+ 期數: {results['m3']}")
    print(f"Match-4+ 期數: {results['m4']}")
    print(f"Match-5+ 期數: {results['m5']}")
    print()
    print(f"📈 每期 Match-3+ 率: {m3_rate:.2f}%")
    print(f"📈 每注 Match-3+ 率: {per_bet_rate:.2f}%")

    # 對比 Gemini 聲稱
    print("\n" + "=" * 80)
    print("📊 vs Gemini 聲稱")
    print("=" * 80)

    gemini_claim = 14.00
    diff = m3_rate - gemini_claim

    print(f"\n| 指標 | Gemini 聲稱 | 獨立驗證 | 差異 |")
    print(f"|------|------------|----------|------|")
    print(f"| Match-3+ 率 | {gemini_claim:.2f}% | {m3_rate:.2f}% | {diff:+.2f}% |")

    if abs(diff) < 2:
        print(f"\n✅ 驗證通過：差異在可接受範圍內 (±2%)")
    elif m3_rate > gemini_claim:
        print(f"\n🔥 實際表現優於聲稱")
    else:
        print(f"\n❌ 無法復現：實際表現低於聲稱 {abs(diff):.2f}%")

    # 計算隨機基準
    print("\n" + "=" * 80)
    print("📊 vs 隨機基準")
    print("=" * 80)

    random.seed(42)
    rand_wins = 0
    rand_total = 0

    for _ in range(50):  # 50 次模擬
        for target_idx in range(start_idx, len(all_draws)):
            actual = set(all_draws[target_idx]['numbers'])
            max_m = 0
            for _ in range(7):  # 7 注
                bet = set(random.sample(range(1, 50), 6))
                max_m = max(max_m, len(bet & actual))
            if max_m >= 3:
                rand_wins += 1
            rand_total += 1

    rand_rate = rand_wins / rand_total * 100 if rand_total > 0 else 0

    print(f"\n隨機 7 注 Match-3+ 率: {rand_rate:.2f}%")
    print(f"實際 vs 隨機: {m3_rate:.2f}% vs {rand_rate:.2f}% ({m3_rate - rand_rate:+.2f}%)")

    if m3_rate > rand_rate:
        print(f"\n✅ 策略優於隨機")
    else:
        print(f"\n❌ 策略不優於隨機")

    return results


if __name__ == '__main__':
    run_verification(test_periods=150)
