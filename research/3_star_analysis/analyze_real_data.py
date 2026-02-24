import sqlite3
import pandas as pd
import numpy as np
import json
import os
import sys

# 將研究目錄加入 path
sys.path.append('/Users/kelvin/Kelvin-WorkSpace/LotteryNew/research/3_star_analysis')
from system_core import ThreeStarAnalyzer
from inference_engine import ThreeStarInferenceEngine

def load_real_data(db_path):
    print(f"Loading 3_STAR data from {db_path}...")
    conn = sqlite3.connect(db_path)
    query = """
    SELECT draw, date, numbers 
    FROM draws 
    WHERE lottery_type = '3_STAR' 
    ORDER BY date ASC, draw ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 解析號碼字串 [n1, n2, n3] -> Num1, Num2, Num3
    df['parsed_nums'] = df['numbers'].apply(lambda x: json.loads(x))
    df['Num1'] = df['parsed_nums'].apply(lambda x: x[0])
    df['Num2'] = df['parsed_nums'].apply(lambda x: x[1])
    df['Num3'] = df['parsed_nums'].apply(lambda x: x[2])
    
    # 移除中間轉換列
    return df.drop(columns=['parsed_nums'])

def main():
    db_path = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
    df = load_real_data(db_path)
    print(f"Loaded {len(df)} real draws.")
    
    # 1. 執行隨機性檢定 (Step 5)
    analyzer = ThreeStarAnalyzer()
    analyzer.history = df
    analyzer.draw_count = len(df)
    results = analyzer.run_randomness_tests()
    
    # 2. 執行回測策略 (Step 4)
    print("\n--- [STEP 4] 真實數據回測：頻率模型 ---")
    def frequentist_strategy(df):
        res = []
        for col in ['Num1', 'Num2', 'Num3']:
            res.append(df[col].mode()[0])
        return np.array(res)
    
    analyzer.backtest_strategy(frequentist_strategy, train_size=2000)
    
    # 3. 獲取當前推薦 (Step 9)
    print("\n--- [STEP 9] 最新數據預測推薦 ---")
    inference_engine = ThreeStarInferenceEngine(df)
    inference_engine.generate_recommendation()

if __name__ == "__main__":
    main()
