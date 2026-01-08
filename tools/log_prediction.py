#!/usr/bin/env python3
"""
威力彩預測記錄器 (Prediction Logger)
每次生成預測時自動記錄，建立完整的預測歷史。
"""
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from database import DatabaseManager
from common import get_lottery_rules

# 預測記錄檔案路徑
PREDICTIONS_LOG = os.path.join(project_root, 'data', 'predictions_log.json')

def load_predictions_log():
    """載入預測記錄"""
    if os.path.exists(PREDICTIONS_LOG):
        with open(PREDICTIONS_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"predictions": []}

def save_predictions_log(log_data):
    """儲存預測記錄"""
    os.makedirs(os.path.dirname(PREDICTIONS_LOG), exist_ok=True)
    with open(PREDICTIONS_LOG, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def log_prediction(target_draw, bets, meta_info):
    """
    記錄一次預測
    
    Args:
        target_draw: 目標期數
        bets: 預測的注數列表
        meta_info: 額外資訊（策略、錨點等）
    """
    log_data = load_predictions_log()
    
    prediction_entry = {
        "target_draw": target_draw,
        "prediction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bets": [
            {
                "numbers": bet["numbers"],
                "special": bet["special"]
            }
            for bet in bets
        ],
        "meta": meta_info,
        "validated": False,
        "result": None
    }
    
    log_data["predictions"].append(prediction_entry)
    save_predictions_log(log_data)
    
    print(f"✅ 已記錄預測：期數 {target_draw}")
    return prediction_entry

def generate_and_log_prediction():
    """生成預測並自動記錄"""
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not history:
        print("❌ 無歷史數據")
        return
    
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    # 計算下一期期數
    latest_draw = history[0]
    current_draw_num = int(latest_draw['draw'])
    next_draw_num = current_draw_num + 1
    
    print(f"📍 最新開獎期數: {current_draw_num} ({latest_draw['date']})")
    print(f"🎯 預測目標期數: {next_draw_num}")
    print("-" * 60)
    
    # 生成預測（使用 V3 Resilience 配置）
    meta_config = {
        'method': 'cluster_pivot',
        'anchor_count': 2,
        'resilience': True,
        'strategy_whitelist': ['frequency', 'bayesian', 'markov', 'trend', 'hot_cold']
    }
    
    res = optimizer.generate_diversified_bets(history, rules, num_bets=4, meta_config=meta_config)
    bets = res['bets']
    summary = res.get('summary', {})
    
    # 顯示預測
    print(f"🔗 核心錨點: {summary.get('anchors', [])}")
    print(f"🎯 特別號分佈: {summary.get('specials', [])}")
    print("-" * 60)
    
    for i, bet in enumerate(bets):
        nums = ",".join([f"{n:02d}" for n in bet['numbers']])
        print(f"注 {i+1}: {nums} | 特別號: {bet['special']:02d}")
    
    # 記錄到日誌
    meta_info = {
        "anchors": summary.get('anchors', []),
        "specials": summary.get('specials', []),
        "config": meta_config,
        "data_version": latest_draw['draw']
    }
    
    log_prediction(next_draw_num, bets, meta_info)
    print("-" * 60)
    print(f"📝 預測已記錄至: {PREDICTIONS_LOG}")

if __name__ == '__main__':
    generate_and_log_prediction()
