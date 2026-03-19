#!/usr/bin/env python3
"""
大樂透「最佳策略」綜合預測器 (Master Hybrid Predictor)

根據回測數據與專家評審團建議：
┌──────┬───────────────┬──────────────────────────────┐
│ 注數 │   推薦策略    │     說明                     │
├──────┼───────────────┼──────────────────────────────┤
│ 1注  │ Cluster Pivot │ 單注王 (+1.60%)              │
│ 2注  │ Apriori       │ 雙注王 (+1.93%)              │
│ 3注  │ Apriori       │ 三注王 (+3.20%)              │
│ 4-6注│ Cluster Pivot │ 多注覆蓋                     │
│ 7注+ │ Cluster + Skew│ 前N-1注聚類 + 最後一注黑天鵝 │
└──────┴───────────────┴──────────────────────────────┘
"""
import sys
import os
import argparse
import logging
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.predict_biglotto_6bets_cluster import BigLottoClusterPivotPredictor
from tools.predict_biglotto_apriori import BigLottoAprioriPredictor

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_best_strategy(num_bets):
    if num_bets == 1:
        return 'cluster', "Cluster Pivot (單注王 +1.60%)"
    elif num_bets in [2, 3]:
        return 'apriori', f"Apriori 關聯規則 ({num_bets}注王 +{1.93 if num_bets==2 else 3.20}%)"
    else:
        suffix = " + 黑天鵝防守" if num_bets >= 7 else ""
        return 'cluster', f"Cluster Pivot (多注覆蓋王){suffix}"

def generate_skew_bet():
    """生成一注「黑天鵝」極端盤 (防守斷層)"""
    skew_type = random.choice(['ALL_BIG', 'ALL_SMALL', 'ALL_ODD', 'ALL_EVEN', 'ZONE_FOCUS'])
    numbers = []
    
    if skew_type == 'ALL_BIG':
        # 25-49
        pool = list(range(25, 50))
        numbers = sorted(random.sample(pool, 6))
        desc = "全大 (25-49)"
    elif skew_type == 'ALL_SMALL':
        # 01-24
        pool = list(range(1, 25))
        numbers = sorted(random.sample(pool, 6))
        desc = "全小 (01-24)"
    elif skew_type == 'ALL_ODD':
        pool = [n for n in range(1, 50) if n % 2 != 0]
        numbers = sorted(random.sample(pool, 6))
        desc = "全奇數"
    elif skew_type == 'ALL_EVEN':
        pool = [n for n in range(1, 50) if n % 2 == 0]
        numbers = sorted(random.sample(pool, 6))
        desc = "全偶數"
    else: # ZONE_FOCUS
        # Random zone focus
        start = random.choice([1, 11, 21, 31])
        end = start + 9
        zone_pool = [n for n in range(start, min(end+1, 50))]
        others = [n for n in range(1, 50) if n not in zone_pool]
        
        # Pick 4 from zone, 2 from others
        if len(zone_pool) >= 4:
            part1 = random.sample(zone_pool, 4)
            part2 = random.sample(others, 2)
            numbers = sorted(part1 + part2)
            desc = f"強攻區間 ({start}-{end})"
        else:
            numbers = sorted(random.sample(range(1, 50), 6))
            desc = "隨機偏態"
            
    return {
        'numbers': numbers,
        'strategy': f'🛡️ 黑天鵝防守: {desc}',
        'anchor': 99 # Special ID
    }

def main():
    parser = argparse.ArgumentParser(description='大樂透最佳策略預測器')
    parser.add_argument('-n', '--num', type=int, default=7, help='預測注數 (預設: 7)')
    args = parser.parse_args()
    
    num_bets = args.num
    strategy_type, desc = get_best_strategy(num_bets)
    
    print("="*60)
    print(f"🏆 大樂透智能預測 (注數: {num_bets})")
    print(f"🤖 選用策略: {desc}")
    print("="*60)
    
    bets = []
    
    if strategy_type == 'cluster':
        predictor = BigLottoClusterPivotPredictor()
        
        # Logic for 7+ bets: N-1 Cluster + 1 Skew
        target_cluster_bets = num_bets
        needs_skew = False
        
        if num_bets >= 7:
            target_cluster_bets = num_bets - 1
            needs_skew = True
            
        bets = predictor.generate_bets(num_bets=target_cluster_bets, window=150)
        
        if needs_skew:
            skew_bet = generate_skew_bet()
            bets.append(skew_bet)
            
    elif strategy_type == 'apriori':
        predictor = BigLottoAprioriPredictor()
        bets = predictor.predict_next_draw(num_bets=num_bets, window=150)
    
    # Output
    next_draw = "115000008" # Hardcoded or fetch
    print(f"\n📅 預測期號: {next_draw}")
    print("-" * 30)
    
    for i, bet in enumerate(bets, 1):
        nums = ", ".join(f"{n:02d}" for n in bet['numbers'])
        detail = bet.get('strategy', '')
        
        if strategy_type == 'cluster':
            anchor = bet.get('anchor', 'N/A')
            if anchor == 99:
                 print(f"注 {i} [{detail}]: {nums}")
            else:
                 print(f"注 {i} [錨點 {anchor:02d}]: {nums}")
        else:
            print(f"注 {i} [規則]: {nums}")
            if detail: print(f"   └─ {detail}")
            
    print("-" * 60)
    if num_bets >= 7:
        print("💡 策略提示: 已啟用「黑天鵝防守」，最後一注專門防禦極端盤")
    print("祝您中獎！")

if __name__ == '__main__':
    main()
