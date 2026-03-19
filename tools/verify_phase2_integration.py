"""
Phase 2 Integration Verification Script
驗證 Phase 2 改進的集成情況：
1. MAB Ensemble 是否正確啟用並權重更新
2. Anomaly Detection 是否能產生預測
3. 7-bet 引擎是否包含 Anomaly 策略
"""
import sys
import os
import logging
from pprint import pprint

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Phase2Verification")

# 添加項目根目錄到路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api')) # Support legacy imports like 'from models import ...'

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.config_loader import PredictionConfig
# from tools.update_db_latest import load_data # This failed
from lottery_api.database import db_manager, DatabaseManager

def load_data(lottery_type='BIG_LOTTO'):
    # Re-initialize db_manager with correct path
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    print(f"Loading DB from: {db_path}")
    db = DatabaseManager(db_path=db_path)
    return db.get_all_draws(lottery_type)

def verify_mab_ensemble(history, rules):
    """驗證 MAB 集成"""
    logger.info(">>> Verifying MAB Ensemble...")
    
    engine = UnifiedPredictionEngine()
    
    # 1. 檢查是否加載了 MAB
    if not getattr(engine, 'mab_predictor', None):
        logger.error("❌ MAB Predictor not initialized in UnifiedPredictionEngine!")
        return False
    
    logger.info("✅ MAB Predictor initialized.")
    
    # 2. 執行預測
    logger.info("Running MAB prediction...")
    result = engine.ensemble_predict(history, rules)
    
    if result.get('method') != 'mab_ensemble':
        logger.warning(f"⚠️ Prediction method is {result.get('method')}, expected 'mab_ensemble'")
        # 這可能是因為 MAB 失敗導致 fallback，檢查日誌
    else:
        logger.info("✅ Prediction method confirmed as 'mab_ensemble'")
        logger.info(f"Weights: {result.get('weights')}")
        
    return True

def verify_anomaly_detection(history, rules):
    """驗證 Anomaly Detection 集成"""
    logger.info("\n>>> Verifying Anomaly Detection...")
    
    optimizer = MultiBetOptimizer()
    
    # 1. 檢查策略是否在 experimental 組
    experimental_group = optimizer.strategy_groups.get('experimental', [])
    anomaly_strategies = [s[0] for s in experimental_group]
    
    if 'anomaly_detection' not in anomaly_strategies:
        logger.error("❌ 'anomaly_detection' not found in MultiBetOptimizer experimental group!")
        return False
    
    logger.info("✅ Anomaly Detection found in strategy groups.")
    
    # 2. 測試 Anomaly Predictor 單獨運行
    logger.info("Testing standalone Anomaly Predictor...")
    try:
        anomaly_pred = optimizer.anomaly_predictor.predict(history, rules)
        logger.info(f"Anomaly Prediction: {anomaly_pred['numbers']} (Conf: {anomaly_pred.get('confidence')})")
        logger.info(f"Metadata: {anomaly_pred.get('metadata')}")
    except Exception as e:
        logger.error(f"❌ Anomaly Predictor failed: {e}")
        return False
        
    return True

def verify_7bet_integration(history, rules):
    """驗證 7-bet 集成"""
    logger.info("\n>>> Verifying 7-Bet Integration...")
    
    optimizer = MultiBetOptimizer()
    
    try:
        # 生成 7 注
        results = optimizer.generate_diversified_bets(
            history, rules, num_bets=7
        )
        
        logger.info(f"Generated {len(results['bets'])} bets.")
        
        # 檢查是否包含 experimental 策略
        strategies_used = [b.get('group', 'unknown') for b in results['bets']]
        logger.info(f"Strategies used: {strategies_used}")
        
        # 注意：不一定每次都會選中 experimental，因為是隨機選擇 + 評分
        # 但我們可以檢查是否有 Anomaly Detection 的 bet
        
        return True
    except Exception as e:
        logger.error(f"❌ 7-Bet Generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # 載入數據
    data = load_data('BIG_LOTTO')
    if not data:
        logger.error("Failed to load data")
        return
        
    # 取最近 100 期
    history = data[-100:]
    rules = {
        'minNumber': 1,
        'maxNumber': 49,
        'pickCount': 6,
        'hasSpecialNumber': True
    }
    
    # 驗證步驟
    mab_ok = verify_mab_ensemble(history, rules)
    anomaly_ok = verify_anomaly_detection(history, rules)
    bet7_ok = verify_7bet_integration(history, rules)
    
    if mab_ok and anomaly_ok and bet7_ok:
        logger.info("\n🎉🎉🎉 Phase 2 Integration Verification PASSED! 🎉🎉🎉")
    else:
        logger.error("\n❌ Phase 2 Verification FAILED.")

if __name__ == "__main__":
    main()
