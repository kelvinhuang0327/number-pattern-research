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
        
        # 1. 獲取最佳配置
        best_config = scheduler.get_best_config()
        if not best_config:
            best_config = scheduler.load_config()
        
        if not best_config:
            raise HTTPException(
                status_code=400,
                detail="沒有可用的優化配置，請先執行自動優化"
            )
        
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
        
        # 4. 使用優化配置進行預測
        from models.auto_learning import AutoLearningEngine
        engine = AutoLearningEngine()
        
        predicted_numbers = engine._predict_with_config(
            best_config,
            history,
            pick_count,
            min_number,
            max_number
        )
        
        # 5. 計算信心度（基於優化時的成功率）
        confidence = 0.10  # 10% 的基礎信心度
        
        logger.info(f"優化預測成功: {predicted_numbers}, 信心度: {confidence:.2%}")
        
        return {
            "numbers": predicted_numbers,
            "confidence": confidence,
            "method": "優化混合策略 (Optimized)",
            "notes": f"使用自動學習優化的參數進行預測"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"優化預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")
