#!/usr/bin/env python3
"""
大樂透/威力彩 優化 3 注預測工具
基於 115000008 期分析成果，提供具備「位置分佈」、「區域集群」、「穩定集成」三種特性的注單。
"""
import os
import sys
import argparse
import json
from datetime import datetime

# 確保可以導入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottery_api.database import DatabaseManager
from lottery_api.engine.multi_bet_optimizer import MultiBetOptimizer

def main():
    parser = argparse.ArgumentParser(description='生成優化 3 注預測')
    parser.add_argument('--lottery', type=str, default='big_lotto', choices=['big_lotto', 'power_lotto'], help='彩種 (big_lotto, power_lotto)')
    args = parser.parse_args()

    lottery_type = 'BIG_LOTTO' if args.lottery == 'big_lotto' else 'POWER_LOTTO'
    lottery_name = '大樂透' if args.lottery == 'big_lotto' else '威力彩'

    print("=" * 60)
    print(f"🚀 {lottery_name} 優化 3 注預測生成器")
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 載入數據
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    res = db.get_draws(lottery_type, page_size=250)
    history = res['draws']
    
    if not history:
        print(f"❌ 錯誤: 資料庫中未找到 {lottery_name} 的數據。")
        return

    if history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]
    
    print(f"✅ 載入 {len(history)} 期歷史數據")
    print(f"📊 最新一期: {history[-1]['draw']} | 號碼: {history[-1]['numbers']}")
    print("-" * 60)

    # 2. 執行優化器
    print("正在訓練 AI 模型並分析集群特徵...")
    optimizer = MultiBetOptimizer(lottery_type=lottery_type)
    bets = optimizer.generate_3bets(history)

    # 3. 輸出結果
    for i, b in enumerate(bets):
        nums_str = " ".join([f"{n:02d}" for n in b['numbers']])
        print(f"\n[{i+1}] {b['style']}")
        print(f"👉 號碼: {nums_str}")
        print(f"📝 依據: {b['description']}")

    print("\n" + "=" * 60)
    print("💡 建議: 三注代表不同的分佈邏輯，建議組合使用以提高覆蓋率。")
    print("=" * 60)

if __name__ == "__main__":
    main()
