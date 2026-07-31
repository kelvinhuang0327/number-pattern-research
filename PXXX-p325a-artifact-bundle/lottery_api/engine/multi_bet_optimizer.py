#!/usr/bin/env python3
"""
多策略多注優化器 (Multi-Strategy Multi-Bet Optimizer)
基於 115000008 期檢討結果實作：
1. Strategy A: 位置最優 (Per-Ball LSTM)
2. Strategy B: 區域集群 (Zonal Cluster Anomaly)
3. Strategy C: 穩定集成 (Ensemble 7ME)
"""
import numpy as np
import os
import json
import logging
import random
from typing import List, Dict, Tuple

from ..models.perball_lstm import PerBallLSTMPredictor
from ..models.attention_lstm import AttentionLSTMPredictor
from ..models.unified_predictor import prediction_engine

logger = logging.getLogger(__name__)

class ZonalDensityDetector:
    """區域密度檢測器: 用於識別號碼集群跡象"""
    
    @staticmethod
    def detect_anomalies(proba_vector: np.ndarray, zone_size: int = 10) -> List[Dict]:
        """
        偵測號碼區間中的異常高機率區
        proba_vector: [num_balls] 的機率分佈
        """
        num_balls = len(proba_vector)
        anomalies = []
        
        # 滑動窗口檢測區間密度
        for start in range(num_balls - zone_size + 1):
            zone_proba = np.sum(proba_vector[start:start+zone_size])
            avg_proba = zone_size / num_balls
            
            # 如果區間機率超過平均值的 1.5 倍，視為異常集群
            if zone_proba > avg_proba * 1.5:
                anomalies.append({
                    'range': (start + 1, start + zone_size),
                    'density': float(zone_proba),
                    'score': float(zone_proba / avg_proba)
                })
        
        # 按密度排序
        return sorted(anomalies, key=lambda x: x['density'], reverse=True)

class MultiBetOptimizer:
    """多注優化引擎"""
    
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        if 'BIG_LOTTO' in lottery_type:
            self.num_balls = 49
            self.n_picks = 6
            self.rules = {'minNumber': 1, 'maxNumber': 49, 'pickCount': 6, 'name': 'BIG_LOTTO'}
        else:
            self.num_balls = 38
            self.n_picks = 6
            self.rules = {'minNumber': 1, 'maxNumber': 38, 'pickCount': 6, 'name': 'POWER_LOTTO'}
            
    def generate_3bets(self, history: List[Dict]) -> List[Dict]:
        """生成三種不同風格的預測注單"""
        results = []
        
        # 預加載模型數據
        train_data = history[-300:] if len(history) > 300 else history
        
        # --- 準備 Per-Ball LSTM 模型 ---
        pb_predictor = PerBallLSTMPredictor(
            num_balls=self.num_balls, 
            n_picks=self.n_picks,
            window_size=5
        )
        pb_predictor.train(train_data, epochs=35, verbose=0)
        pb_proba = pb_predictor.predict_proba(history)
        
        # --- 注單 1: 位置最優 (Strategy A) ---
        bet1_nums = pb_predictor._greedy_dedup_sample(pb_proba, self.n_picks)
        results.append({
            'numbers': sorted(bet1_nums),
            'style': '位置最優 (Per-Ball LSTM)',
            'description': '捕捉每個球位的精確機率分佈，最契合近期線性規律。'
        })
        
        # --- 注單 2: 區域集群 (Strategy B) ---
        # 合併所有球位的機率分佈以檢測集群
        combined_proba = np.mean(pb_proba, axis=0)
        anomalies = ZonalDensityDetector.detect_anomalies(combined_proba)
        
        if anomalies:
            top_zone = anomalies[0]['range']
            # 在異常區間強行選取一半的號碼
            zone_nums = []
            zone_start, zone_end = top_zone
            # 取區間內機率最高的 3 個號碼
            zone_indices = np.argsort(combined_proba[zone_start-1:zone_end])[::-1][:3]
            zone_nums = [idx + zone_start for idx in zone_indices]
            
            # 從全局機率中補齊剩餘號碼 (避開已選)
            rem_count = self.n_picks - len(zone_nums)
            all_indices = np.argsort(combined_proba)[::-1]
            for idx in all_indices:
                num = idx + 1
                if num not in zone_nums and len(zone_nums) < self.n_picks:
                    zone_nums.append(num)
            bet2_nums = sorted(zone_nums)
            desc = f"偵測到區間 {top_zone[0]}-{top_zone[1]} 存在集群跡象，強化該區塊覆蓋。"
        else:
            # 隨機擾動 Sampling
            bet2_nums = pb_predictor.predict_with_temperature(history, n_numbers=self.n_picks, temperature=1.2, n_samples=1)[0]
            desc = "未發現明顯集群，採用高熵隨機擾動策略擴展覆蓋範圍。"
            
        results.append({
            'numbers': bet2_nums,
            'style': '區域集群 (Anomaly Detection)',
            'description': desc
        })
        
        # --- 注單 3: 穩定集成 (Strategy C) ---
        # 調用現有的 Ensemble 7ME 引擎
        ensemble_res = prediction_engine.ensemble_predict(history, self.rules)
        results.append({
            'numbers': sorted(ensemble_res['numbers']),
            'style': '穩定集成 (7-Method Ensemble)',
            'description': '融合統計、趨勢、馬可夫等多種經典算法，追求長期穩定命中。'
        })
        
        return results

if __name__ == "__main__":
    # 快速測試
    from ..database import DatabaseManager
    db = DatabaseManager()
    history = db.get_draws('BIG_LOTTO', page_size=100)['draws'][::-1]
    
    optimizer = MultiBetOptimizer(lottery_type='BIG_LOTTO')
    bets = optimizer.generate_3bets(history)
    for i, b in enumerate(bets):
        print(f"注單 {i+1} [{b['style']}]: {b['numbers']}")
        print(f"依據: {b['description']}\n")
