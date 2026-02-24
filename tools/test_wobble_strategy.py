#!/usr/bin/env python3
import sys
import os
import json

# Add project root and lottery_api to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.wobble_optimizer import WobbleOptimizer
from database import DatabaseManager
from common import get_lottery_rules

def main():
    print("=" * 80)
    print("Wobble Strategy 驗證工具")
    print("=" * 80)

    # 1. 載入當期實際號碼 (115000001)
    actual = [3, 7, 16, 19, 40, 42]
    
    # 2. 載入之前的「接近」預測 (例如 Bayesian 模型產出的)
    # Bayesian 預測: [8, 10, 12, 15, 18, 24] -> 命中 0
    # 但 8(←7), 15(→16), 18(→19) 都是 ±1
    base_prediction = [8, 10, 12, 15, 18, 24]
    
    print(f"實際號碼: {actual}")
    print(f"原始預測: {base_prediction}")
    print(f"原始命中: {len(set(base_prediction) & set(actual))}")
    print("-" * 40)

    optimizer = WobbleOptimizer()
    
    # 測試系統化擾動生成 10 注
    wobble_bets = optimizer.systematic_wobble(base_prediction, num_bets=10)
    
    print(f"生成的 Wobble 注項 (共 {len(wobble_bets)} 注):")
    best_match = 0
    for i, bet in enumerate(wobble_bets):
        matches = len(set(bet) & set(actual))
        hit_nums = sorted(list(set(bet) & set(actual)))
        print(f"注 {i+1:2}: {bet} | 命中: {matches} {hit_nums if matches > 0 else ''}")
        if matches > best_match:
            best_match = matches

    print("-" * 40)
    print(f"最佳命中提升: {len(set(base_prediction) & set(actual))} -> {best_match}")
    
    if best_match > len(set(base_prediction) & set(actual)):
        print("✅ Wobble 策略成功捕捉到更多號碼！")
    else:
        print("❌ Wobble 策略對此預測無顯著提升（可能基礎注偏移過大）。")

if __name__ == "__main__":
    main()
