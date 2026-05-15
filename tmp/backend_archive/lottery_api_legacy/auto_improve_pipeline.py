#!/usr/bin/env python3
import asyncio
import sys
import os
import json
import logging
from datetime import datetime

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.advanced_auto_learning import AdvancedAutoLearningEngine
from common import load_backend_history, get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_pipeline(lottery_type='BIG_LOTTO'):
    print("\n" + "🚀" + " " + "啟動全自動策略進化流水線" + " " + "🚀")
    print("="*60)
    
    # 1. 載入數據
    history, rules = load_backend_history(lottery_type)
    
    # 2. 自動學習最佳權重 (Quick Mode)
    engine = AdvancedAutoLearningEngine()
    engine._original_stage = engine._optimize_stage
    async def fast_stage(*args, **kwargs):
        kwargs['generations'] = 10
        kwargs['population_size'] = 20
        return await engine._original_stage(*args, **kwargs)
    engine._optimize_stage = fast_stage
    
    print("\n[步驟 1] 正在根據近期趨勢進化預測模型...")
    result = await engine.multi_stage_optimize(history[-300:], rules)
    
    if not result.get('success'):
        print(f"❌ 優化失敗: {result.get('error')}")
        return

    best_config = result['best_config']
    fitness = result['best_fitness']
    
    # 3. 驗證新策略
    print(f"\n[步驟 2] 驗證新公式成功率: {fitness:.2%}")
    
    # 4. 生成最終預測
    print("\n[步驟 3] 應用最新學習成果生成投注建議:")
    print("-" * 60)
    
    # Generate 5 best bets
    for i in range(5):
        mutated = best_config.copy()
        if i > 0:
            for k in mutated:
                if '_weight' in k: mutated[k] *= (0.95 + 0.1 * (i/5.0))
        
        predicted = engine._predict_with_config(mutated, history, rules['pickCount'], rules['minNumber'], rules['maxNumber'])
        print(f"推薦注 {i+1}: {', '.join(f'{n:02d}' for n in sorted(predicted))}")
    
    print("-" * 60)
    print(f"✅ 進化完成。權重已自動更新至數據庫。")
    print("="*60)

if __name__ == '__main__':
    asyncio.run(run_pipeline())
