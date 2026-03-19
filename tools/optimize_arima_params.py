#!/usr/bin/env python3
"""
ARIMA 參數優化工具 (Grid Search)
==============================
通過網格搜索尋找大樂透與威力彩的最佳 (p, d, q) 組合。
"""
import os
import sys
import itertools
import pandas as pd
import numpy as np
import logging
import warnings
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error

# 忽略 ARIMA 收斂警告
warnings.filterwarnings("ignore")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_params_for_type(lottery_type, p_range, d_range, q_range, test_size=50):
    """
    對特定彩種進行參數優化
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type=lottery_type)))
    
    if not history:
        logger.error(f"No data found for {lottery_type}")
        return None

    # 提取第一個球的序列作為優化目標 (通常各球趨勢相似)
    series = pd.Series([draw['numbers'][0] for draw in history]).astype(float)
    
    # 切分訓練與測試集 (使用最近的 test_size 期進行驗證)
    train_data = series.iloc[:-test_size]
    test_data = series.iloc[-test_size:]
    
    best_aic = float("inf")
    best_mse = float("inf")
    best_cfg = None
    
    # 建立網格
    grid = list(itertools.product(p_range, d_range, q_range))
    logger.info(f"Searching {len(grid)} combinations for {lottery_type}...")

    results = []

    for cfg in grid:
        try:
            # 建立模型
            model = ARIMA(train_data, order=cfg)
            model_fit = model.fit()
            
            # 計算 AIC
            aic = model_fit.aic
            
            # 進行簡單的 1-step 預測驗證 MSE
            forecast = model_fit.forecast(steps=test_size)
            mse = mean_squared_error(test_data, forecast)
            
            results.append({
                'cfg': cfg,
                'aic': aic,
                'mse': mse
            })
            
            # 我們主要以 AIC 作為標準，因為它是對模型複雜度與擬合度的綜合評價
            if aic < best_aic:
                best_aic = aic
                best_mse = mse
                best_cfg = cfg
                
        except Exception as e:
            continue

    logger.info(f"Best Config for {lottery_type}: {best_cfg} (AIC: {best_aic:.2f}, MSE: {best_mse:.2f})")
    return {
        'type': lottery_type,
        'best_cfg': best_cfg,
        'best_aic': best_aic,
        'best_mse': best_mse,
        'all_results': results
    }

def run_optimization():
    p_range = [1, 3, 5, 7]
    d_range = [0, 1, 2]
    q_range = [0, 1, 2]
    
    types = ['BIG_LOTTO', 'POWER_LOTTO']
    final_best = {}

    for l_type in types:
        res = optimize_params_for_type(l_type, p_range, d_range, q_range)
        if res:
            final_best[l_type] = res
            
    # 打印報告
    print("\n" + "="*50)
    print("🏆 ARIMA Parameter Optimization Report")
    print("="*50)
    for l_type, data in final_best.items():
        print(f"{l_type}: Best Order = {data['best_cfg']} | AIC = {data['best_aic']:.2f}")
    
    # 保存結果
    output_path = os.path.join(project_root, 'tools', 'data', 'arima_optimized_params.json')
    import json
    with open(output_path, 'w') as f:
        # 轉換 tuple 為 list 以便 JSON 序列化
        serializable = {k: {**v, 'best_cfg': list(v['best_cfg']), 'all_results': []} for k, v in final_best.items()}
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved to: {output_path}")

if __name__ == "__main__":
    run_optimization()
