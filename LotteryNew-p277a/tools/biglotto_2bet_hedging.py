#!/usr/bin/env python3
"""
大樂透 2注對沖策略 (Big Lotto 2-Bet Hedging Strategy)

移植自威力彩 Fourier30 + Markov30 策略
需要回測驗證在大樂透的有效性

策略組合:
- 注1 (Fourier30): 加權頻率法，偏重近期趨勢
- 注2 (Markov30): 轉移機率法，自動多樣化處理

使用方式:
    python3 tools/biglotto_2bet_hedging.py
    python3 tools/biglotto_2bet_hedging.py --backtest  # 執行回測驗證
"""

import sqlite3
import json
import sys
import argparse
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

# 大樂透參數
MAX_NUMBER = 49
NUMBERS_PER_BET = 6


def get_zone(num):
    """獲取號碼所在區間 (1-5) for 大樂透"""
    if 1 <= num <= 10:
        return 1
    elif 11 <= num <= 20:
        return 2
    elif 21 <= num <= 30:
        return 3
    elif 31 <= num <= 40:
        return 4
    else:
        return 5


def bet1_fourier30(history):
    """
    注1: Fourier Rhythm W30
    使用加權頻率，近期號碼權重更高
    """
    recent = history[-30:] if len(history) >= 30 else history
    weighted_freq = Counter()
    n = len(recent)

    for i, h in enumerate(recent):
        weight = 1 + 2 * (i / n)  # 線性遞增權重 (1.0 ~ 3.0)
        for num in h['numbers']:
            weighted_freq[num] += weight

    return sorted([n for n, _ in weighted_freq.most_common(NUMBERS_PER_BET)])


def bet2_markov30(history):
    """
    注2: Markov W30
    基於號碼轉移機率預測
    """
    recent = history[-30:] if len(history) >= 30 else history

    # 建立轉移矩陣
    transitions = Counter()
    for i in range(len(recent) - 1):
        prev = set(recent[i]['numbers'])
        curr = recent[i + 1]['numbers']
        for p in prev:
            for c in curr:
                transitions[(p, c)] += 1

    if not recent:
        return list(range(1, NUMBERS_PER_BET + 1))

    # 根據上一期計算下一期機率
    last = recent[-1]['numbers']
    scores = Counter()
    for num in last:
        for (p, c), count in transitions.items():
            if p == num:
                scores[c] += count

    result = [n for n, _ in scores.most_common(NUMBERS_PER_BET)]

    # 補足6個 (用頻率補充)
    if len(result) < NUMBERS_PER_BET:
        all_nums = []
        for h in recent:
            all_nums.extend(h['numbers'])
        freq = Counter(all_nums)
        for n, _ in freq.most_common():
            if n not in result and len(result) < NUMBERS_PER_BET:
                result.append(n)

    return sorted(result[:NUMBERS_PER_BET])


def diversify_bets(bet1, bet2, history, max_overlap=3):
    """
    多樣化處理：確保兩注重疊不超過 max_overlap 個
    """
    overlap = set(bet1) & set(bet2)

    if len(overlap) <= max_overlap:
        return bet1, bet2

    recent = history[-50:] if len(history) >= 50 else history

    # 計算冷度 (距離上次出現的期數)
    last_seen = {i: len(recent) for i in range(1, MAX_NUMBER + 1)}
    for idx, h in enumerate(recent):
        for num in h['numbers']:
            gap = len(recent) - 1 - idx
            if gap < last_seen[num]:
                last_seen[num] = gap

    # 保留部分非重疊的 Markov 結果
    new_bet2 = [n for n in bet2 if n not in overlap][:max_overlap]

    # 用適度冷號補充，確保區間分散
    cold = sorted(last_seen.items(), key=lambda x: -x[1])
    zones_used = Counter(get_zone(n) for n in new_bet2)

    for n, gap in cold:
        if n not in bet1 and n not in new_bet2 and len(new_bet2) < NUMBERS_PER_BET:
            z = get_zone(n)
            if zones_used[z] < 2:  # 每區最多2個
                new_bet2.append(n)
                zones_used[z] += 1

    # 補足至6個
    for n, gap in cold:
        if n not in bet1 and n not in new_bet2 and len(new_bet2) < NUMBERS_PER_BET:
            new_bet2.append(n)

    return bet1, sorted(new_bet2[:NUMBERS_PER_BET])


def load_history():
    """從數據庫載入歷史數據"""
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute('''
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC
    ''')

    rows = cursor.fetchall()
    history = []
    for row in rows:
        history.append({
            'draw': row[0],
            'date': row[1],
            'numbers': json.loads(row[2]),
            'special': row[3]
        })

    conn.close()
    return history


def analyze_bet(bet, name):
    """分析預測號碼特徵"""
    odd = sum(1 for n in bet if n % 2 == 1)
    small = sum(1 for n in bet if n <= 24)
    total = sum(bet)

    zones = Counter()
    for n in bet:
        zones[get_zone(n)] += 1

    return {
        'name': name,
        'numbers': bet,
        'odd_even': f"{odd}:{6-odd}",
        'big_small': f"{small}:{6-small}",
        'sum': total,
        'zones': dict(zones)
    }


def run_backtest(history, test_periods=500):
    """執行回測驗證"""
    print(f"\n{'='*70}")
    print(f"回測驗證 (最近 {test_periods} 期)")
    print(f"{'='*70}")

    if len(history) < test_periods + 50:
        print(f"數據不足，需要至少 {test_periods + 50} 期")
        return

    m3_hits = 0
    m4_hits = 0
    m5_hits = 0

    for i in range(test_periods):
        # 目標期數索引
        target_idx = len(history) - test_periods + i
        target = history[target_idx]
        actual = set(target['numbers'])

        # 使用該期之前的數據預測
        train_history = history[:target_idx]

        # 生成預測
        bet1 = bet1_fourier30(train_history)
        bet2 = bet2_markov30(train_history)
        bet1, bet2 = diversify_bets(bet1, bet2, train_history, max_overlap=3)

        # 計算命中
        match1 = len(set(bet1) & actual)
        match2 = len(set(bet2) & actual)
        best_match = max(match1, match2)

        if best_match >= 3:
            m3_hits += 1
        if best_match >= 4:
            m4_hits += 1
        if best_match >= 5:
            m5_hits += 1

    # 計算結果
    m3_rate = m3_hits / test_periods * 100
    random_baseline = 3.69  # 大樂透 2注隨機基準
    edge = m3_rate - random_baseline

    print(f"\n測試期數: {test_periods}")
    print(f"M3+ 命中: {m3_hits} 次")
    print(f"M4+ 命中: {m4_hits} 次")
    print(f"M5+ 命中: {m5_hits} 次")
    print(f"\n實測 M3+ 勝率: {m3_rate:.2f}%")
    print(f"隨機基準 (2注): {random_baseline:.2f}%")
    print(f"Edge: {edge:+.2f}%")

    if edge > 0.5:
        print(f"\n✅ 策略有效 (Edge > +0.5%)")
    elif edge > 0:
        print(f"\n⚠️ 微弱優勢 (0 < Edge < +0.5%)")
    else:
        print(f"\n❌ 策略無效 (Edge ≤ 0)")

    return {
        'test_periods': test_periods,
        'm3_rate': m3_rate,
        'baseline': random_baseline,
        'edge': edge
    }


def main():
    parser = argparse.ArgumentParser(description='大樂透 2注對沖策略')
    parser.add_argument('--diversified', action='store_true',
                        help='強制多樣化模式 (最大重疊=0，覆蓋12號碼)')
    parser.add_argument('--backtest', action='store_true',
                        help='執行回測驗證')
    parser.add_argument('--periods', type=int, default=500,
                        help='回測期數 (默認 500)')
    args = parser.parse_args()

    print("=" * 70)
    print("大樂透 2注對沖策略 (Fourier30 + Markov30)")
    print("=" * 70)

    # 載入數據
    history = load_history()
    print(f"\n數據總期數: {len(history)}")
    print(f"最近一期: {history[-1]['draw']} ({history[-1]['date']})")
    print(f"開獎號碼: {history[-1]['numbers']} + 特{history[-1]['special']}")

    # 如果執行回測
    if args.backtest:
        run_backtest(history, args.periods)
        return

    # 生成預測
    bet1 = bet1_fourier30(history)
    bet2 = bet2_markov30(history)

    # 多樣化處理
    if args.diversified:
        bet1, bet2 = diversify_bets(bet1, bet2, history, max_overlap=0)
        mode = "多樣化模式 (覆蓋最大化)"
    else:
        bet1, bet2 = diversify_bets(bet1, bet2, history, max_overlap=3)
        mode = "標準模式"

    # 輸出結果
    print(f"\n模式: {mode}")
    print("\n" + "=" * 70)
    print("【下期預測】")
    print("=" * 70)

    overlap = set(bet1) & set(bet2)
    coverage = set(bet1) | set(bet2)

    print(f"\n注1 (Fourier30 熱號): {bet1}")
    print(f"注2 (Markov30 轉移):  {bet2}")

    print(f"\n號碼覆蓋: {len(coverage)} 個不同號碼")
    if overlap:
        print(f"重疊號碼: {sorted(overlap)} ({len(overlap)}個)")
    else:
        print("重疊號碼: 無 (完全分散)")

    # 特徵分析
    print("\n【號碼特徵】")
    for bet, name in [(bet1, "注1"), (bet2, "注2")]:
        info = analyze_bet(bet, name)
        print(f"\n{name}: {bet}")
        print(f"  奇偶: {info['odd_even']}, 大小: {info['big_small']}, 和: {info['sum']}")
        z = info['zones']
        print(f"  區間: Z1={z.get(1,0)}, Z2={z.get(2,0)}, Z3={z.get(3,0)}, Z4={z.get(4,0)}, Z5={z.get(5,0)}")

    # 提示
    print("\n" + "=" * 70)
    print("【注意事項】")
    print("=" * 70)
    print("  ⚠️ 此策略尚未經過大樂透回測驗證")
    print("  → 執行 'python3 tools/biglotto_2bet_hedging.py --backtest' 驗證")


if __name__ == '__main__':
    main()
