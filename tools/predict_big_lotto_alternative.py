#!/usr/bin/env python3
import sys
import os
import io

# Add project root and lottery-api to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("================================================================================")
    print("大樂透雙注預測 - 備選方案")
    print("策略組合: zone_balance(500) + bayesian(300)")
    print("================================================================================")

    # 1. Load Data
    db_path = os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    lottery_type = 'BIG_LOTTO'
    
    # Get all draws (Returns DESC: Newest -> Oldest)
    draws_desc = db.get_all_draws(lottery_type=lottery_type)
    
    if not draws_desc:
        print(f"Error: No data found for {lottery_type}")
        return

    # Convert to ASC (Oldest -> Newest)
    draws_asc = list(reversed(draws_desc))
    rules = get_lottery_rules(lottery_type)
    engine = UnifiedPredictionEngine()

    # 3. Predict Bet 1: Zone Balance (Window 500)
    print("\n[第一注] 策略: zone_balance_500")
    window_1 = 500
    history_1 = draws_asc[-window_1:] if len(draws_asc) > window_1 else draws_asc
    
    try:
        result_1 = engine.zone_balance_predict(history_1, rules)
        nums_1 = sorted(result_1['numbers'])
        print(f"號碼: {nums_1}")
    except Exception as e:
        print(f"Error generating Bet 1: {e}")
        nums_1 = []

    # 4. Predict Bet 2: Bayesian (Window 300)
    print("\n[第二注 - 備選] 策略: bayesian_300")
    print("說明: 貝葉斯統計，結合長期先驗概率與近期似然概率")
    window_2 = 300
    history_2 = draws_asc[-window_2:] if len(draws_asc) > window_2 else draws_asc
    
    try:
        result_2 = engine.bayesian_predict(history_2, rules)
        nums_2 = sorted(result_2['numbers'])
        special_2 = result_2.get('special')
        print(f"號碼: {nums_2}")
        if special_2:
            print(f"特別號: {special_2}")
    except Exception as e:
        print(f"Error generating Bet 2: {e}")
        nums_2 = []

    # 5. Analysis
    if nums_1 and nums_2:
        overlap = set(nums_1) & set(nums_2)
        print("\n" + "=" * 80)
        print("備選分析結果:")
        print(f"重疊號碼: {sorted(list(overlap))}")
        print("=" * 80)

if __name__ == '__main__':
    main()
