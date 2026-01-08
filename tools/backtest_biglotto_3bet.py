#!/usr/bin/env python3
"""
大樂透三注組合150期回測
驗證 Deviation + Markov + Statistical 三注策略效果
"""
import sys
import os
import io
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backtest_3bet_strategy():
    """回測三注策略"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    test_periods = min(150, len(all_draws) - 50)
    
    optimizer = BigLotto3BetOptimizer()
    
    print("=" * 80)
    print("🔬 大樂透三注智能組合回測 (最近 150 期)")
    print("=" * 80)
    print(f"測試期數: {test_periods} 期")
    print(f"組合策略: Deviation + Markov + Statistical (低重疊)")
    print("-" * 80)
    
    # 統計數據
    wins = 0
    match_3_plus = 0
    match_4_plus = 0
    match_5_plus = 0
    match_6 = 0
    total = 0
    
    match_distribution = Counter()
    hit_details = []
    
    # 逐期測試
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        
        if len(hist) < 10:
            continue
        
        actual = set(target_draw['numbers'])
        draw_num = target_draw['draw']
        draw_date = target_draw['date']
        
        try:
            # 生成三注預測
            result = optimizer.predict_3bets_diversified(hist, rules)
            
            # 檢查每注的命中數
            matches = []
            for bet in result['bets']:
                predicted = set(bet['numbers'])
                match_count = len(predicted & actual)
                matches.append(match_count)
            
            best_match = max(matches)
            match_distribution[best_match] += 1
            
            # 判斷中獎
            if best_match >= 6:
                match_6 += 1
                match_5_plus += 1
                match_4_plus += 1
                match_3_plus += 1
                wins += 1
            elif best_match >= 5:
                match_5_plus += 1
                match_4_plus += 1
                match_3_plus += 1
                wins += 1
            elif best_match >= 4:
                match_4_plus += 1
                match_3_plus += 1
                wins += 1
            elif best_match >= 3:
                match_3_plus += 1
                wins += 1
            elif best_match >= 1:
                wins += 1
            
            # 記錄命中詳情
            if best_match >= 3:
                best_bet_idx = matches.index(best_match)
                hit_details.append({
                    'draw': draw_num,
                    'date': draw_date,
                    'actual': sorted(actual),
                    'best_match': best_match,
                    'best_bet': best_bet_idx + 1,
                    'all_matches': matches
                })
            
            total += 1
            
        except Exception as e:
            print(f"⚠️ 期數 {i}: {e}")
            continue
    
    if total == 0:
        print("❌ 測試失敗：無有效數據")
        return
    
    # 顯示統計結果
    print("\n" + "=" * 80)
    print("📊 回測統計結果")
    print("=" * 80)
    
    match_3_rate = match_3_plus / total * 100
    
    print(f"\n總期數: {total}")
    print(f"總勝率: {wins / total * 100:.2f}%")
    print(f"\n命中統計:")
    print(f"  Match-6 (頭獎): {match_6:3d} 次 ({match_6 / total * 100:5.2f}%)")
    print(f"  Match-5+ (貳獎): {match_5_plus:3d} 次 ({match_5_plus / total * 100:5.2f}%)")
    print(f"  Match-4+ (參獎): {match_4_plus:3d} 次 ({match_4_plus / total * 100:5.2f}%)")
    print(f"  Match-3+ (肆獎): {match_3_plus:3d} 次 ({match_3_rate:5.2f}%)")
    
    print(f"\n命中分布:")
    for match_count in sorted(match_distribution.keys(), reverse=True):
        count = match_distribution[match_count]
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{match_count}: {count:3d} 次 ({pct:5.1f}%) {bar}")
    
    # 顯示命中詳情
    if hit_details:
        print("\n" + "=" * 80)
        print(f"🎯 Match-3+ 命中詳情 (共 {len(hit_details)} 次)")
        print("=" * 80)
        
        print(f"\n{'期號':<12} {'日期':<12} {'實際號碼':<30} {'最佳命中':<15}")
        print("-" * 80)
        
        for detail in hit_details[:20]:
            actual_str = ','.join([f"{n:02d}" for n in detail['actual']])
            match_str = f"{detail['best_match']}號(注{detail['best_bet']})"
            print(f"{detail['draw']:<12} {detail['date']:<12} {actual_str:<30} {match_str:<15}")
        
        if len(hit_details) > 20:
            print(f"\n... 還有 {len(hit_details) - 20} 次命中未顯示")
    
    # 與其他方案對比
    print("\n" + "=" * 80)
    print("📊 方案對比分析")
    print("=" * 80)
    
    baseline = 2.67
    two_bet = 5.33
    improvement = match_3_rate - baseline
    vs_two_bet = match_3_rate - two_bet
    
    print(f"\n{'方案':<35} {'Match-3+':<12} {'成本':<8} {'效益':<12}")
    print("-" * 80)
    print(f"{'單注偏差分析 (基準)':<35} {f'{baseline:.2f}%':<12} {'1注':<8} {f'{baseline:.2f}%':<12}")
    print(f"{'雙注組合 (Deviation+Markov)':<35} {f'{two_bet:.2f}%':<12} {'2注':<8} {f'{two_bet/2:.2f}%':<12}")
    print(f"{'🎯 三注智能組合 (新方案)':<35} {f'{match_3_rate:.2f}%':<12} {'3注':<8} {f'{match_3_rate/3:.2f}%':<12}")
    
    # 最終總結
    print("\n" + "=" * 80)
    print("🎯 最終評估")
    print("=" * 80)
    
    print(f"\n✅ Match-3+ 率: {match_3_rate:.2f}%")
    print(f"📈 vs 單注基準: +{improvement:.2f}%")
    print(f"📈 vs 雙注方案: +{vs_two_bet:.2f}%")
    print(f"💰 性價比: {match_3_rate/3:.2f}% per 注")
    print(f"🎰 成本: 3 注")
    
    target = 7.67  # 基準2.67% + 目標提升5%
    
    if match_3_rate >= target:
        gap = match_3_rate - target
        print(f"\n🎉 達成目標！")
        print(f"   目標: {target:.2f}% (基準+5%)")
        print(f"   實際: {match_3_rate:.2f}%")
        print(f"   超越: +{gap:.2f}%")
    else:
        gap = target - match_3_rate
        print(f"\n⚠️ 未達目標")
        print(f"   目標: {target:.2f}% (基準+5%)")
        print(f"   實際: {match_3_rate:.2f}%")
        print(f"   差距: -{gap:.2f}%")
        
        if gap <= 1.0:
            print(f"   💡 非常接近！建議微調參數或增加至4注")
        elif gap <= 2.0:
            print(f"   💡 有明顯進步，可考慮4注組合或輕量級機器學習")
        else:
            print(f"   💡 建議接受當前成果或轉向威力彩")
    
    # 使用建議
    print("\n💡 使用建議:")
    if match_3_rate >= 6.5:
        print("  ✅ 三注方案表現優異，強烈建議作為大樂透主要策略")
    elif match_3_rate >= 5.5:
        print("  ✅ 三注方案效果良好，可作為大樂透策略使用")
        print("  💡 如預算充足，可考慮增加至4注以接近目標")
    else:
        print("  ⚠️ 建議評估是否值得3注成本")
        print("  💡 或可考慮轉向威力彩（已驗證11.33%四注方案）")

if __name__ == '__main__':
    backtest_3bet_strategy()
