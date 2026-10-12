
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import logging
from typing import List, Dict

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.anomaly_predictor import AnomalyPredictor

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ExtremeCaseVerification')

def verify_extreme_case():
    """
    驗證 AnomalyPredictor 是否能捕捉極端案例 (如 44-45-46 連號)
    """
    logger.info("🧪 Verifying Extreme Case Detection (44-45-46)...")
    
    predictor = AnomalyPredictor()
    
    # 模擬訓練數據 (正常隨機分佈)
    # 創建一些看起來正常的歷史數據
    history = []
    for i in range(100):
        # 生成正常隨機號碼
        history.append({
            'numbers': sorted([x for x in range(1, 7)]), # 1-6 (Normal-ish)
             # Wait, randomly generate to be robust
             'numbers': sorted(list(set([x % 49 + 1 for x in range(i, i+6)])))
        })
    
    # 手動訓練 (雖然 predict 會自動訓練，但這裡顯式調用)
    predictor.fit(history)
    
    # 定義極端案例
    # Case 1: 44-45-46 三連號 (極端)
    extreme_case_1 = [1, 2, 44, 45, 46, 49]
    # Case 2: 均勻分佈 (正常)
    normal_case = [5, 12, 18, 25, 33, 41]
    # Case 3: 全連號 (極極端)
    extreme_case_2 = [1, 2, 3, 4, 5, 6]
    
    cases = [
        ('Extreme (44-45-46)', extreme_case_1),
        ('Normal', normal_case),
        ('Extreme (1-2-3-4-5-6)', extreme_case_2)
    ]
    
    results = []
    
    if hasattr(predictor, '_calculate_anomaly_score_sklearn') and predictor.model:
        logger.info("Using Isolation Forest (Sklearn)")
        method = 'sklearn'
    else:
        logger.info("Using Simple Distance (Fallback)")
        method = 'simple'
        
    for name, numbers in cases:
        if method == 'sklearn':
            # Score is negative, lower is more anomalous in raw sklearn
            # But our wrapper returns negative? 
            # predict_anomaly implementation: anomaly_score = -score (so higher is more anomalous)
            # Let's check _calculate_anomaly_score_sklearn direct return.
            # It returns score_samples (higher = normal, lower = abnormal)
            raw_score = predictor._calculate_anomaly_score_sklearn(numbers)
            anomaly_score = -raw_score # Higher means more anomalous
        else:
            anomaly_score = predictor._calculate_anomaly_score_simple(numbers)
            
        logger.info(f"Case: {name:<25} | Numbers: {numbers} | Anomaly Score: {anomaly_score:.4f}")
        results.append((name, anomaly_score))
        
    # Check if Extreme cases have higher anomaly scores than Normal
    normal_score = next(s for n, s in results if n == 'Normal')
    extreme_1_score = next(s for n, s in results if n == 'Extreme (44-45-46)')
    
    if extreme_1_score > normal_score:
        logger.info("✅ SUCCESS: Extreme case (44-45-46) has higher anomaly score than Normal.")
    else:
        logger.warning(f"❌ FAILURE: Extreme case (44-45-46) score ({extreme_1_score:.4f}) <= Normal ({normal_score:.4f})")
        # Depending on Isolation Forest training, this might fluctuate if history is random.
        # But logically it should be anomalous.

if __name__ == "__main__":
    verify_extreme_case()
