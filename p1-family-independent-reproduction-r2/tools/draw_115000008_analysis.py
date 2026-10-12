#!/usr/bin/env python3
"""
大樂透 115000008 期 (2026-01-27) 專項特徵分析
號碼: 04, 11, 24, 25, 29, 30 | 特別號: 08
"""
import os
import sys
import numpy as np
from collections import Counter
import json

# 確保可以導入專案模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottery_api.database import DatabaseManager
from lottery_api.models.attention_lstm import AttentionLSTMPredictor
from lottery_api.models.perball_lstm import PerBallLSTMPredictor

def analyze_features(numbers, sp):
    sorted_nums = sorted(numbers)
    # 1. 連號分析
    consecutive_pairs = []
    for i in range(len(sorted_nums) - 1):
        if sorted_nums[i+1] - sorted_nums[i] == 1:
            consecutive_pairs.append((sorted_nums[i], sorted_nums[i+1]))
    
    # 2. 奇偶比
    odds = [n for n in sorted_nums if n % 2 != 0]
    evens = [n for n in sorted_nums if n % 2 == 0]
    
    # 3. 區域分佈 (1-10, 11-20, 21-30, 31-40, 41-49)
    zones = {
        '1-10': len([n for n in sorted_nums if 1 <= n <= 10]),
        '11-20': len([n for n in sorted_nums if 11 <= n <= 20]),
        '21-30': len([n for n in sorted_nums if 21 <= n <= 30]),
        '31-40': len([n for n in sorted_nums if 31 <= n <= 40]),
        '41-49': len([n for n in sorted_nums if 41 <= n <= 49]),
    }
    
    # 4. 和值與均值
    total_sum = sum(sorted_nums)
    avg = total_sum / len(sorted_nums)
    
    return {
        'numbers': sorted_nums,
        'sp': sp,
        'consecutive_count': len(consecutive_pairs),
        'consecutive_pairs': consecutive_pairs,
        'odd_even': f"{len(odds)}:{len(evens)}",
        'zones': zones,
        'sum': total_sum,
        'avg': avg
    }

def run_model_backtrack(history, target_nums):
    # 使用 115000008 之前的 200 期數據進行訓練
    train_data = history[-201:-1] # 假設 history 最後一期是 115000008
    
    # 1. Attention LSTM
    attn_predictor = AttentionLSTMPredictor(num_balls=49, window_size=5)
    attn_predictor.train(train_data, epochs=30, verbose=0)
    attn_proba = attn_predictor.predict_proba(train_data)
    
    # 2. Per-Ball LSTM
    pb_predictor = PerBallLSTMPredictor(num_balls=49, n_picks=6, window_size=5)
    pb_predictor.train(train_data, epochs=30, verbose=0)
    pb_proba = pb_predictor.predict_proba(train_data) # [6, 49]
    
    # 分析目標號碼在模型中的機率排名
    report = {}
    
    print(f"DEBUG: attn_proba shape: {attn_proba.shape}")
    
    # Attention LSTM 排名
    attn_ranks = np.argsort(attn_proba)[::-1]
    attn_hits = []
    for n in target_nums:
        idx = int(n - 1)
        if idx < len(attn_proba):
            rank = list(attn_ranks).index(idx) + 1
            attn_hits.append({'num': n, 'rank': rank, 'prob': float(attn_proba[idx])})
        else:
            print(f"DEBUG: index {idx} out of range for attn_proba")
    report['attention_lstm'] = attn_hits
    
    print(f"DEBUG: pb_proba shape: {pb_proba.shape}")
    
    # Per-Ball LSTM 排名 (取 6 個位置中最優排名)
    pb_hits = []
    for n in target_nums:
        idx = int(n - 1)
        best_rank = 100
        best_prob = 0
        for pos in range(pb_proba.shape[0]):
            ranks = np.argsort(pb_proba[pos])[::-1]
            if idx < len(pb_proba[pos]):
                rank = list(ranks).index(idx) + 1
                if rank < best_rank:
                    best_rank = rank
                    best_prob = float(pb_proba[pos][idx])
        pb_hits.append({'num': n, 'best_rank': best_rank, 'best_prob': best_prob})
    report['perball_lstm'] = pb_hits
    
    return report

if __name__ == "__main__":
    target_nums = [4, 11, 24, 25, 29, 30]
    sp = 8
    
    # 1. 基礎分析
    features = analyze_features(target_nums, sp)
    print("=== 115000008 期特徵分析 ===")
    print(json.dumps(features, indent=2))
    
    # 2. 資料庫讀取與模型回溯
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    res = db.get_draws('BIG_LOTTO', page_size=250)
    history = res['draws']
    if history and history[0]['draw'] > history[-1]['draw']:
        history = history[::-1]
    
    print(f"DEBUG: history total: {len(history)}")
    if history:
        print(f"DEBUG: first history draw: {history[0]['draw']}, nums: {history[0]['numbers']}")
        print(f"DEBUG: last history draw: {history[-1]['draw']}, nums: {history[-1]['numbers']}")

    train_data = history[-201:-1]
    print(f"DEBUG: train_data total: {len(train_data)}")
    
    print("\n=== 模型回溯預測分析 (對比目標號碼) ===")
    try:
        model_report = run_model_backtrack(history, target_nums)
        print(json.dumps(model_report, indent=2, ensure_ascii=False))
        
        # 保存結果供專家報告使用
        with open('tools/data/draw_115000008_analysis_results.json', 'w') as f:
            json.dump({'features': features, 'model_report': model_report}, f, indent=2)
    except Exception as e:
        print(f"模型運行失敗: {e}")
