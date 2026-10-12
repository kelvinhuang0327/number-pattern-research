#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from typing import List, Dict

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.advanced_auto_learning import AdvancedAutoLearningEngine
from common import load_backend_history, get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_self_optimization():
    lottery_type = 'BIG_LOTTO'  # 大樂透
    logger.info(f"🚀 開始針對 {lottery_type} 進行自動學習優化...")
    
    # 1. 載入數據
    history, rules = load_backend_history(lottery_type)
    
    if len(history) < 100:
        logger.error("數據量不足以進行深度學習優化（需要至少 100 期）")
        return

    # 2. 初始化自動學習引擎
    engine = AdvancedAutoLearningEngine()
    
    # 3. 執行多階段優化 (快速演示版)
    # 我們手動覆蓋引擎參數以加快速度
    engine._original_stage = engine._optimize_stage
    async def fast_stage(*args, **kwargs):
        # 將代數縮減至 5, 10, 5 代，群體縮減至 20
        kwargs['generations'] = min(kwargs.get('generations', 10), 10)
        kwargs['population_size'] = 20
        return await engine._original_stage(*args, **kwargs)
    
    engine._optimize_stage = fast_stage
    
    logger.info("⏳ 正在運行快速學習優化 (縮減規模以供快速確認)...")
    
    async def progress(p):
        print(f"   優化進度: {p:.1f}%")

    # 執行優化 (僅使用最近 300 期以加快評估速度)
    result = await engine.multi_stage_optimize(history[-300:], rules, progress_callback=progress)
    
    if result.get('success'):
        print("\n" + "="*50)
        print("🏆 自動學習優化完成！")
        print("="*50)
        print(f"最佳適應度 (Win Rate 3+): {result['best_fitness']:.2%}")
        print("\n學習到的最佳權重配置 (Top 5):")
        
        config = result['best_config']
        # 排序權重
        weights = {k: v for k, v in config.items() if '_weight' in k}
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        for name, val in sorted_weights[:5]:
            print(f"   - {name:<20}: {val:.4f}")
            
        print(f"\n最佳數據窗口大小: {config.get('recent_window', 'Default')} 期")
        print("="*50)
        print("💡 系統已將此配置保存至 data/advanced_optimization_history.json")
        print("集成預測器在下次運行時將優先參考此優化結果。")
    else:
        logger.error(f"優化過程出錯: {result.get('error')}")

if __name__ == '__main__':
    asyncio.run(run_self_optimization())
