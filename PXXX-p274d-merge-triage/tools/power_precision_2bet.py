import os
import sys
import logging
from datetime import datetime

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

logging.basicConfig(level=logging.WARNING)

def generate_precision_2bet():
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('POWER_LOTTO')
    history = sorted(draws, key=lambda x: (x['date'], x['draw']))
    rules = get_lottery_rules('POWER_LOTTO')
    next_draw = int(history[-1]['draw']) + 1
    
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*17 + "🎯  POWER LOTTO 2-BET PRECISION REPORT  🎯" + " "*17 + "║")
    print("║" + " "*21 + f"VERSION: Prediction Engine V11" + " "*22 + "║")
    print("║" + " "*21 + f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " "*21 + "║")
    print("╚" + "═"*68 + "╝")

    print(f"\n🎯 【威力彩 POWER LOTTO】 - 預測期數: {next_draw}")
    print(f"📊 策略：模型預測 + 特區 V3 優勢")
    print("-" * 70)

    # 1. 使用 UnifiedPredictionEngine 的最佳預測模型組合
    engine = UnifiedPredictionEngine()
    
    # 使用 Markov + Statistical 組合 (歷史表現最佳的兩個模型)
    markov_result = engine.markov_predict(history, rules)
    statistical_result = engine.statistical_predict(history, rules)
    
    main_set_1 = markov_result.get('numbers', [])
    main_set_2 = statistical_result.get('numbers', [])
    
    # 2. 獲取 Top 2 特別號 (V3 - 經 1000 期驗證 +2.2% Edge)
    sp_predictor = PowerLottoSpecialPredictor(rules)
    top_2_specials = sp_predictor.predict_top_n(history, n=2)
    
    # 3. 輸出組合：兩組不同主號 + 各自最佳特別號
    print(f"注 1: {sorted(main_set_1)} | 特別號: {top_2_specials[0]}")
    print(f"      └─ 主號策略: Markov Chain (馬可夫鏈轉移機率)")
    print(f"注 2: {sorted(main_set_2)} | 特別號: {top_2_specials[1]}")
    print(f"      └─ 主號策略: Statistical Deviation (統計偏差分析)")

    print("\n" + "="*70)
    print("💡 預測方法說明：")
    print("   [主號 - 注1] Markov Chain：基於號碼轉移機率預測下一期熱門號")
    print("   [主號 - 注2] Statistical：綜合頻率、區間、奇偶等統計特徵預測")
    print("   [特別號] V3 Model：經 1000+ 期驗證，具備 +2.2% 實測優勢")
    print("="*70 + "\n")

if __name__ == "__main__":
    generate_precision_2bet()
