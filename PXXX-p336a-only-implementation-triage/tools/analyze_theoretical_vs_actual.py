#!/usr/bin/env python3
"""
理論與實證對比：智能5注 vs. 隨機5注
"""
import math
from itertools import combinations

def comb(n, r):
    """組合數計算"""
    return math.factorial(n) // (math.factorial(r) * math.factorial(n - r))

def calculate_single_bet_win_prob():
    """計算單注中獎機率 (至少中3個號碼)"""
    total_combinations = comb(49, 6)
    
    # 中3個號碼
    ways_3 = comb(6, 3) * comb(43, 3)
    # 中4個號碼
    ways_4 = comb(6, 4) * comb(43, 2)
    # 中5個號碼
    ways_5 = comb(6, 5) * comb(43, 1)
    # 中6個號碼
    ways_6 = comb(6, 6) * comb(43, 0)
    
    total_winning_ways = ways_3 + ways_4 + ways_5 + ways_6
    
    single_prob = total_winning_ways / total_combinations
    
    return single_prob

def calculate_5bets_win_prob_independent():
    """計算5注完全獨立時的組合中獎機率"""
    single_prob = calculate_single_bet_win_prob()
    
    # 至少一注中獎 = 1 - (全部不中)
    combined_prob = 1 - (1 - single_prob) ** 5
    
    return combined_prob

def main():
    print("=" * 70)
    print("大樂透 5注策略 - 理論分析")
    print("=" * 70)
    
    single_prob = calculate_single_bet_win_prob()
    random_5_prob = calculate_5bets_win_prob_independent()
    
    print(f"\n📊 理論機率:")
    print(f"   單注中獎機率 (3+):        {single_prob*100:.4f}%")
    print(f"   隨機5注組合中獎機率:      {random_5_prob*100:.2f}%")
    
    print(f"\n📊 我們的實測結果:")
    print(f"   智能5注組合中獎率:        10.17%")
    print(f"   各單注中獎率:")
    print(f"      Bet 1 (穩健): 4.24%")
    print(f"      Bet 2 (平衡): 3.39%")
    print(f"      Bet 3 (趨勢): 3.39%")
    print(f"      Bet 4 (回補): 2.54%")
    print(f"      Bet 5 (共識): 0.00%")
    
    # 計算平均單注中獎率
    avg_single = (4.24 + 3.39 + 3.39 + 2.54 + 0.00) / 5
    
    print(f"\n   平均單注中獎率:          {avg_single:.2f}%")
    
    diff = 10.17 - random_5_prob * 100
    
    print(f"\n📊 比較分析:")
    print(f"   智能5注 vs 隨機5注差距:  {diff:+.2f}%")
    
    print(f"\n💡 結論:")
    if abs(diff) < 1:
        print(f"   ⚠️  差距小於1%，智能策略「無顯著優勢」")
        print(f"   ⚠️  驗證了用戶的質疑：系統未能超越隨機水平")
    elif diff > 0:
        print(f"   ✅ 智能策略優於隨機選號 {diff:.2f}%")
    else:
        print(f"   ❌ 智能策略劣於隨機選號 {abs(diff):.2f}%")
    
    print("\n" + "=" * 70)
    
    # 檢驗號碼重疊問題
    print("\n🔍 進階分析：為何組合勝率低於預期？")
    print()
    
    # 如果5注完全獨立，理論組合勝率
    expected_if_independent = 1 - (1 - 0.0424) * (1 - 0.0339) * (1 - 0.0339) * (1 - 0.0254) * (1 - 0.0000)
    
    print(f"   若5注完全獨立，理論組合勝率: {expected_if_independent*100:.2f}%")
    print(f"   實際組合勝率:                10.17%")
    print(f"   差距:                        {(expected_if_independent*100 - 10.17):.2f}%")
    print()
    print(f"   📌 結論：5注之間存在「號碼重疊」或「相同偏好」")
    print(f"      - 可能都避開了 Kill-5 的號碼")
    print(f"      - 可能都偏愛相同的熱門號碼")
    print(f"      → 導致分散性不足，降低了整體覆蓋率")
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    main()
