#!/usr/bin/env python3
"""
根據已購買的 2 注號碼，生成最優第 3 注補強。
邏輯：
1. 分析已購 2 注的覆蓋缺口（區間、尾數、頻率空間）
2. 從預測模型候選池中篩選出正交且補強缺口的號碼
3. 進行結構評分（和值、奇偶、區間分佈）
"""
import sqlite3, json, sys, os
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

MAX_NUM = 49
PICK = 6

def load_history(lottery_type='BIG_LOTTO'):
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        (lottery_type,)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({'draw': row[0], 'date': row[1], 'numbers': nums, 'special': row[3] or 0})
    conn.close()
    return draws

def structural_score(bet):
    s = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        if n <= 16: zones[0] += 1
        elif n <= 33: zones[1] += 1
        else: zones[2] += 1
    consec = sum(1 for i in range(len(bet)-1) if bet[i+1] - bet[i] == 1)
    spread = bet[-1] - bet[0]
    
    score = 0
    if 100 <= s <= 200: score += 2
    if 120 <= s <= 180: score += 2
    if 2 <= odd <= 4: score += 2
    if all(z >= 1 for z in zones): score += 2
    if consec <= 1: score += 1
    if spread >= 25: score += 1
    return score

def analyze_coverage(bet1, bet2):
    """分析已購 2 注的覆蓋情況"""
    all_nums = set(bet1) | set(bet2)
    overlap = set(bet1) & set(bet2)
    
    # 區間分析
    zones = {'低區(1-16)': [], '中區(17-33)': [], '高區(34-49)': []}
    for n in sorted(all_nums):
        if n <= 16: zones['低區(1-16)'].append(n)
        elif n <= 33: zones['中區(17-33)'].append(n)
        else: zones['高區(34-49)'].append(n)
    
    # 尾數分析
    tails_covered = set(n % 10 for n in all_nums)
    tails_missing = set(range(10)) - tails_covered
    
    # 5區間分析 (用於 Zone Gap Detection)
    zone5 = [0]*5
    zone5_ranges = [(1,10),(11,20),(21,30),(31,40),(41,49)]
    for n in all_nums:
        for i,(lo,hi) in enumerate(zone5_ranges):
            if lo <= n <= hi:
                zone5[i] += 1
                break
    
    return {
        'all_nums': all_nums,
        'overlap': overlap,
        'zones': zones,
        'tails_covered': tails_covered,
        'tails_missing': tails_missing,
        'zone5': zone5,
        'zone5_ranges': zone5_ranges
    }

def generate_optimal_3rd_bet(bet1, bet2, history):
    """生成最優第 3 注"""
    cov = analyze_coverage(bet1, bet2)
    used = cov['all_nums']
    
    # === 打印覆蓋分析 ===
    print(f"\n{'='*65}")
    print(f"  已購注分析")
    print(f"{'='*65}")
    print(f"  注 1: {sorted(bet1)}  和值={sum(bet1)} 奇偶={sum(1 for n in bet1 if n%2==1)}:{sum(1 for n in bet1 if n%2==0)}")
    print(f"  注 2: {sorted(bet2)}  和值={sum(bet2)} 奇偶={sum(1 for n in bet2 if n%2==1)}:{sum(1 for n in bet2 if n%2==0)}")
    print(f"  重疊: {sorted(cov['overlap'])} ({len(cov['overlap'])} 個)")
    print(f"  已覆蓋: {len(used)} 個號碼")
    print()
    
    # 區間分析
    print(f"  區間覆蓋:")
    for zone_name, nums in cov['zones'].items():
        bar = '█' * len(nums) + '░' * (6 - len(nums))
        print(f"    {zone_name}: {bar} {len(nums)} 個 {nums}")
    
    # 找出最弱區間
    weakest_zone_idx = cov['zone5'].index(min(cov['zone5']))
    wz_lo, wz_hi = cov['zone5_ranges'][weakest_zone_idx]
    print(f"\n  ⚠️  最弱區間: {wz_lo}-{wz_hi} (僅 {cov['zone5'][weakest_zone_idx]} 個號碼)")
    
    # 尾數分析
    print(f"\n  尾數覆蓋: {sorted(cov['tails_covered'])} ({len(cov['tails_covered'])}/10)")
    print(f"  尾數缺口: {sorted(cov['tails_missing'])}")
    
    # === 候選號碼評分 ===
    # 頻率分析
    recent_50 = history[-50:]
    freq = Counter()
    for d in recent_50:
        for n in d['numbers']:
            freq[n] += 1
    expected = 50 * PICK / MAX_NUM
    
    # 遺漏值分析
    gap = {}
    for n in range(1, MAX_NUM+1):
        for i, d in enumerate(reversed(history)):
            if n in d['numbers']:
                gap[n] = i
                break
        else:
            gap[n] = len(history)
    
    # 候選池 = 所有未使用的號碼
    candidates = [n for n in range(1, MAX_NUM+1) if n not in used]
    
    # 為每個候選號碼打分
    scores = {}
    for n in candidates:
        s = 0
        # 1. 尾數補強 (+3): 補充缺失尾數
        if n % 10 in cov['tails_missing']:
            s += 3
        # 2. 區間補強 (+3): 補充最弱區間
        if wz_lo <= n <= wz_hi:
            s += 3
        # 3. 頻率偏差 (±1): 熱號或冷號均可
        dev = freq.get(n, 0) - expected
        if abs(dev) > 2:
            s += 1  # 有明確信號的號碼
        # 4. 遺漏回歸 (+1): 遺漏值 > 平均的號碼
        avg_gap = MAX_NUM / PICK  # ~8.2
        if gap.get(n, 0) > avg_gap * 1.5:
            s += 1
        scores[n] = s
    
    # === 組合搜索 ===
    # 從候選中窮舉找最佳組合
    from itertools import combinations
    
    best_combo = None
    best_total = -1
    
    # 優先確保最弱區間有覆蓋
    must_include = []
    weak_zone_candidates = [n for n in candidates if wz_lo <= n <= wz_hi]
    
    # 按分數排序候選
    ranked = sorted(candidates, key=lambda n: scores[n], reverse=True)
    
    # 取前 20 個高分候選進行組合搜索
    top_candidates = ranked[:20]
    
    # 確保最弱區間候選在搜索池中
    for n in weak_zone_candidates[:3]:
        if n not in top_candidates:
            top_candidates.append(n)
    
    for combo in combinations(top_candidates, PICK):
        bet = sorted(combo)
        
        # 結構分
        ss = structural_score(bet)
        
        # 候選分加總
        cs = sum(scores[n] for n in combo)
        
        # 尾數補強分
        new_tails = set(n % 10 for n in combo)
        tail_fill = len(new_tails & cov['tails_missing'])
        
        # 區間補強分
        zone_fill = sum(1 for n in combo if wz_lo <= n <= wz_hi)
        
        total = ss * 2 + cs + tail_fill * 2 + min(zone_fill, 2) * 2
        
        if total > best_total:
            best_total = total
            best_combo = bet
    
    return best_combo, scores, cov

def main():
    bet1 = [1, 18, 23, 40, 43, 46]
    bet2 = [16, 21, 22, 31, 40, 48]
    
    history = load_history('BIG_LOTTO')
    latest = history[-1]
    
    print(f"  大樂透第 3 注補強分析")
    print(f"  數據: {len(history)} 期 (最新: {latest['draw']} {latest['date']})")
    
    best_bet, scores, cov = generate_optimal_3rd_bet(bet1, bet2, history)
    
    # 最終結果
    print(f"\n{'='*65}")
    print(f"  🎯 最優第 3 注補強號碼")
    print(f"{'='*65}")
    print(f"\n  注 3: {best_bet}")
    
    s = sum(best_bet)
    odd = sum(1 for n in best_bet if n % 2 == 1)
    zones = [0,0,0]
    for n in best_bet:
        if n <= 16: zones[0] += 1
        elif n <= 33: zones[1] += 1
        else: zones[2] += 1
    ss = structural_score(best_bet)
    
    print(f"    和值: {s} | 奇偶: {odd}:{PICK-odd} | 區間: {zones} | 結構分: {ss}/10")
    
    # 新尾數
    new_tails = set(n % 10 for n in best_bet) - cov['tails_covered']
    print(f"    新增尾數: {sorted(new_tails)}")
    
    # 總覆蓋
    all3 = cov['all_nums'] | set(best_bet)
    overlap_with_existing = set(best_bet) & cov['all_nums']
    print(f"    與已購重疊: {sorted(overlap_with_existing)} ({len(overlap_with_existing)} 個)")
    print(f"\n  三注總覆蓋: {len(all3)}/49 ({len(all3)/49*100:.1f}%)")
    
    tails_final = set(n % 10 for n in all3)
    print(f"  尾數覆蓋: {len(tails_final)}/10 種")
    print(f"{'='*65}")

if __name__ == '__main__':
    main()
