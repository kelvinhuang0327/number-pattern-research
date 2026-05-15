"""
優化預測路由
使用自動學習優化的參數進行預測
"""
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List
import logging

logger = logging.getLogger(__name__)

class PredictFromBackendRequest(BaseModel):
    lotteryType: str
    modelType: str = "prophet"

async def predict_optimized(request: PredictFromBackendRequest, scheduler, PredictResponse):
    """
    使用自動學習優化的參數進行預測
    """
    try:
        logger.info(f"收到優化預測請求: 彩券={request.lotteryType}")
        
        # 1. 獲取最佳配置（優先使用彩種專屬配置）
        best_config = scheduler.get_best_config(request.lotteryType)
        if not best_config:
            best_config = scheduler.get_best_config()
        
        if not best_config:
            raise HTTPException(
                status_code=400,
                detail="沒有可用的優化配置，請先執行自動優化"
            )
        
        logger.info(f"使用優化配置，共 {len([k for k in best_config.keys() if '_weight' in k])} 個權重參數")
        
        # 2. 從後端加載數據
        if not scheduler.latest_data or not scheduler.lottery_rules:
            scheduler.load_data()
            
            if not scheduler.latest_data or not scheduler.lottery_rules:
                raise HTTPException(
                    status_code=400,
                    detail="後端沒有數據，請先同步數據到後端"
                )
        
        # 3. 篩選指定彩券類型的數據
        history = [
            draw for draw in scheduler.latest_data 
            if draw.get('lotteryType') == request.lotteryType
        ]
        
        if len(history) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"彩券類型 {request.lotteryType} 的數據不足"
            )
        
        lottery_rules = scheduler.lottery_rules
        pick_count = lottery_rules.get('pickCount', 6)
        min_number = lottery_rules.get('minNumber', 1)
        max_number = lottery_rules.get('maxNumber', 49)
        
        # 4. 使用 AdvancedAutoLearningEngine 進行預測（包含高級策略）
        from models.advanced_auto_learning import AdvancedAutoLearningEngine
        engine = AdvancedAutoLearningEngine()
        
        predicted_numbers = engine._predict_with_config(
            best_config,
            history,
            pick_count,
            min_number,
            max_number
        )
        
        # 5. 計算信心度（基於配置中的權重總和）
        weight_keys = [k for k in best_config.keys() if '_weight' in k]
        total_weight = sum(best_config.get(k, 0) for k in weight_keys)
        
        # 高級策略權重佔比加成
        advanced_keys = ['entropy_weight', 'clustering_weight', 'temporal_weight', 'feature_eng_weight']
        advanced_weight = sum(best_config.get(k, 0) for k in advanced_keys)
        advanced_bonus = advanced_weight * 0.1  # 高級策略每10%權重加1%信心
        
        base_confidence = 0.08 + advanced_bonus
        confidence = min(0.15, base_confidence)  # 最高 15%
        
        logger.info(f"優化預測成功: {predicted_numbers}, 信心度: {confidence:.2%}, 高級策略權重: {advanced_weight:.2%}")
        
        return {
            "numbers": predicted_numbers,
            "confidence": confidence,
            "method": "優化混合策略 (Advanced Optimized)",
            "notes": f"使用自動學習優化的參數進行預測，包含 {len(weight_keys)} 個策略權重"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"優化預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")

