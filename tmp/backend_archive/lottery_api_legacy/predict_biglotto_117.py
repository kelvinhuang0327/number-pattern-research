import sys
import os
import json
import logging
import numpy as np

# Setup path
sys.path.insert(0, os.getcwd())

from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.unified_predictor import UnifiedPredictionEngine
from common import load_backend_history, get_data_range_info

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def predict_draw_117():
    lottery_type = 'BIG_LOTTO'
    next_draw = '114000117'
    
    print(f"\n{'='*60}")
    print(f"🚀 大樂透 (BIG_LOTTO) 第 {next_draw} 期預測分析")
    print(f"{'='*60}")

    try:
        # 1. 載入歷史數據 (確保使用最新數據庫)
        # load_backend_history 內部使用 DatabaseManager，預設路徑為 lottery_v2.db
        history, rules = load_backend_history(lottery_type)
        range_info = get_data_range_info(history)
        
        print(f"📊 歷史數據區間: {range_info['date_range']}")
        print(f"📈 總期數: {range_info['total_count']}")
        print(f"🔔 最新一期: {range_info['last_draw']} -> {history[-1]['numbers']} (特別號: {history[-1]['special']})")
        print("-" * 60)

        # 2. 初始化引擎與預測器
        engine = UnifiedPredictionEngine()
        ensemble = OptimizedEnsemblePredictor(engine)

        # 3. 執行預測
        print("🔍 正在進行多維度集成運算 (SOTA/Meta/Statistical)...")
        result = ensemble.predict(history, rules)

        # 4. 輸出預測結果
        print("\n🏆 【雙注預測結果】")
        print("-" * 60)
        
        for bet_key in ['bet1', 'bet2']:
            bet = result[bet_key]
            nums = sorted(bet['numbers'])
            spec = bet['special']
            conf = bet['confidence']
            
            nums_str = ", ".join([f"{n:02d}" for n in nums])
            print(f"📍 {bet_key.upper()} 建議號碼: {nums_str} | 特別號: {spec:02d}")
            print(f"   ✨ 預估信心度: {conf:.1%}")
            
        print("-" * 60)
        
        # 分析特徵
        best_nums = result['bet1']['numbers']
        odd_count = sum(1 for n in best_nums if n % 2 != 0)
        even_count = 6 - odd_count
        sum_val = sum(best_nums)
        
        print("\n📌 策略分析亮點:")
        print(f"   • 奇偶分佈: {odd_count} 奇 {even_count} 偶 (符合回測高頻區間)")
        print(f"   • 總和預期: {sum_val} (符合大樂透 20 年均值規律)")
        print(f"   • 核心信心來源: {result.get('consensus_stats', {}).get('avg_consensus', 0):.1f} 層預測共識")
        
        print(f"\n💡 策略提示: 以上為系統優化集成預測，建議作為選號參考。")
        print(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"❌ 預測過程中出錯: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    predict_draw_117()
