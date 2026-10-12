import sqlite3
import json
import random
import numpy as np
from collections import Counter, defaultdict
import os

def check_db_path():
    paths = ["lottery_api/data/lottery_v2.db", "lottery_api/data/lottery.db", "data/lottery_v2.db"]
    for p in paths:
        if os.path.exists(p):
            try:
                conn = sqlite3.connect(p)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM draws WHERE lottery_type IN ('POWER_LOTTO')")
                cnt = cursor.fetchone()[0]
                conn.close()
                if cnt > 100:
                    return p
            except Exception as e:
                pass
    return None

def load_data():
    db_path = check_db_path()
    if not db_path:
        raise Exception("Cannot find populated DB")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT draw, date, numbers FROM draws WHERE lottery_type = 'POWER_LOTTO' ORDER BY CAST(draw AS INTEGER) ASC")
    rows = cursor.fetchall()
    conn.close()
    
    draws = []
    for row in rows:
        try:
            nums = json.loads(row[2])
            draws.append({
                'draw': row[0],
                'date': row[1],
                'numbers': set(nums)
            })
        except:
            pass
    return draws

def get_signal_pool(draws, currentIndex, signal_type, pool_size):
    pool = set()
    history_len = 50
    history = draws[max(0, currentIndex-history_len):currentIndex]
    
    if signal_type == 'Fourier':
        # Periodic/Hot emulation
        all_nums = []
        for h in history[max(0, len(history)-20):]: all_nums.extend(list(h['numbers']))
        c = Counter(all_nums)
        pool = set([x[0] for x in c.most_common(int(pool_size))])
        
    elif signal_type == 'Cold':
        all_nums = []
        for h in history: all_nums.extend(list(h['numbers']))
        c = Counter(all_nums)
        for i in range(1, 38+1):
            if i not in c:
                c[i] = 0
        pool = set([x[0] for x in c.most_common()][:-pool_size-1:-1])
        
    elif signal_type == 'FreqOrt':
        all_nums = []
        for h in history: all_nums.extend(list(h['numbers']))
        c = Counter(all_nums)
        hot = [x[0] for x in c.most_common(12)]
        if len(hot) > pool_size:
            pool = set(random.sample(hot, pool_size))
        else:
            pool = set(hot)
            
    elif signal_type == 'TailBalance':
        tails = defaultdict(list)
        for i in range(1, 39):
            tails[i % 10].append(i)
        while len(pool) < pool_size:
            t = random.randint(0, 9)
            if tails[t]:
                pool.add(random.choice(tails[t]))

    # Fill remaining
    while len(pool) < pool_size:
        pool.add(random.randint(1, 38))
        
    return list(pool)[:pool_size]

def generate_covering(pool, num_lines):
    pool = list(pool)
    lines = []
    random.shuffle(pool)
    for i in range(num_lines):
        line = pool[i*6:i*6+6]
        while len(line) < 6:
            rem = set(range(1, 39)) - set(line)
            line.append(random.choice(list(rem)))
        lines.append(set(line))
    return lines

def mcnemar_test(b, c):
    """
    McNemar test statistic: (|b - c| - 1)^2 / (b + c)
    b: TS3 hit, FCF miss
    c: TS3 miss, FCF hit
    """
    if b + c == 0:
        return 1.0, 1.0 # p-value ~ 1
    chi2 = (abs(b - c) - 1)**2 / (b + c)
    
    # Approx p-value from chi2 (1 df)
    from scipy.stats import chi2 as chi2_dist
    p = 1 - chi2_dist.cdf(chi2, 1)
    return chi2, p / 2 # One-sided

def main():
    draws = load_data()
    test_draws = draws[-1500:] if len(draws) > 1500 else draws[-1000:]
    start_idx = len(draws) - len(test_draws)
    
    num_lines = 3
    pool_size = num_lines * 6
    
    # Strategy 1: TS3 (Fourier + Cold + TailBalance)
    # Strategy 2: FCF (Fourier + Cold + FreqOrt)
    
    ts3_hits = 0
    fcf_hits = 0
    
    # Confusion matrix for McNemar
    both_hit = 0
    ts3_only = 0
    fcf_only = 0
    neither = 0
    
    # 3-bet combinations emulation
    # TS3: Bet1=Fourier, Bet2=Cold, Bet3=TailBalance
    # FCF: Bet1=Fourier, Bet2=Cold, Bet3=FreqOrt
    
    # Power Lotto 1st zone is 1-38, drawn 6 
    
    for i in range(start_idx, len(draws)):
        target = draws[i]['numbers']
        
        # Bets
        b1_f = generate_covering(get_signal_pool(draws, i, 'Fourier', 6), 1)[0]
        b2_c = generate_covering(get_signal_pool(draws, i, 'Cold', 6), 1)[0]
        
        b3_tail = generate_covering(get_signal_pool(draws, i, 'TailBalance', 6), 1)[0]
        b3_freq = generate_covering(get_signal_pool(draws, i, 'FreqOrt', 6), 1)[0]
        
        ts3_m3 = False
        fcf_m3 = False
        
        for line in [b1_f, b2_c, b3_tail]:
            if len(line.intersection(target)) >= 3:
                ts3_m3 = True
                
        for line in [b1_f, b2_c, b3_freq]:
            if len(line.intersection(target)) >= 3:
                fcf_m3 = True
                
        if ts3_m3: ts3_hits += 1
        if fcf_m3: fcf_hits += 1
        
        if ts3_m3 and fcf_m3: both_hit += 1
        elif ts3_m3 and not fcf_m3: ts3_only += 1
        elif not ts3_m3 and fcf_m3: fcf_only += 1
        else: neither += 1

    # Theoretical baseline for 3-bets Power Lotto M3+
    # p_m3 = C(6,3)*C(32,3) / C(38,6) = 20 * 4960 / 2760681 = 0.0359
    # p_m4 = C(6,4)*C(32,2) / C(38,6) = 15 * 496 / 2760681 = 0.0027
    # per bet P(>=3) = 0.0386 
    # for 3 bets, theoretical expected M3+ rate approx 1 - (1-0.0386)^3 = 0.1114 (11.14%)
    p_3bets_m3 = 1 - (1-0.0386)**3
    base_hits = len(test_draws) * p_3bets_m3

    ts3_rate = ts3_hits / len(test_draws)
    fcf_rate = fcf_hits / len(test_draws)
    
    ts3_edge = ((ts3_hits - base_hits) / base_hits) * 100 if base_hits > 0 else 0
    fcf_edge = ((fcf_hits - base_hits) / base_hits) * 100 if base_hits > 0 else 0
    
    chi2, p_val = mcnemar_test(ts3_only, fcf_only)
    
    print("\n# 威力彩 FCF vs TS3 1v1 Walk-Forward 驗證")
    print(f"期數: {len(test_draws)}")
    print(f"理論 3 注基準 M3+ 率: {p_3bets_m3:.4f} ({base_hits:.1f}次)")
    print()
    print("| 指標 | TS3 | FCF |")
    print("|------|:---:|:---:|")
    print(f"| {len(test_draws)}p M3+ | {ts3_hits}次 ({ts3_rate*100:.2f}%) | {fcf_hits}次 ({fcf_rate*100:.2f}%) |")
    print(f"| Edge | {ts3_edge:+.2f}% | {fcf_edge:+.2f}% |")
    print(f"| 勝負 | {'✅ 領先' if ts3_hits > fcf_hits else '❌'} | {'✅ 領先' if fcf_hits > ts3_hits else '❌'} |")
    print()
    print("### McNemar 配對檢定")
    print(f"- 兩者皆中: {both_hit} 期")
    print(f"- FCF 獨贏: {fcf_only} 期")
    print(f"- TS3 獨贏: {ts3_only} 期")
    print(f"- 兩者皆未中: {neither} 期")
    print(f"- χ²={chi2:.2f}, p(單側)={p_val:.4f} → 差異{'顯著' if p_val < 0.05 else '不顯著'}")
    
    if ts3_hits >= fcf_hits:
        print("\n**裁定：FCF 未優於 TS3，維持現狀 (TS3 較優或旗鼓相當)。**")
    else:
        print("\n**裁定：FCF 優於 TS3，建議更新策略。**")

if __name__ == "__main__":
    main()
