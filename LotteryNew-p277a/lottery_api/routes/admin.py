from fastapi import APIRouter
from utils.scheduler import scheduler
from utils.model_cache import model_cache
from typing import Optional

router = APIRouter()

@router.get("/")
async def root():
    """API 根端點"""
    return {
        "message": "Lottery AI Prediction API",
        "version": "1.0.0",
        "models": ["prophet", "xgboost", "lstm"],
        "status": "running",
        "docs": "/docs"
    }

@router.get("/health")
async def health_check():
    """健康檢查端點"""
    # 加入排程優化狀態，供前端判斷是『忙碌』而非離線
    return {
        "status": "healthy",
        "busy": scheduler.is_optimizing,
        "progress": getattr(scheduler, 'current_progress', 0),
        "currentGeneration": getattr(scheduler, 'current_generation', 0),
        "totalGenerations": getattr(scheduler, 'total_generations', 0),
        "message": getattr(scheduler, 'optimization_message', ''),
        "lastOptimizationAt": getattr(scheduler, 'last_optimization_at', None),
        "models": {
            "prophet": "available",
            "xgboost": "available",
            "autogluon": "available",
            "lstm": "available"
        }
    }

@router.get("/api/ping")
async def ping():
    """極速回應端點：用於前端快速判斷後端是否存活及是否忙碌"""
    return {
        "status": "ok",
        "busy": scheduler.is_optimizing,
        "progress": getattr(scheduler, 'current_progress', 0),
        "currentGeneration": getattr(scheduler, 'current_generation', 0),
        "totalGenerations": getattr(scheduler, 'total_generations', 0),
        "message": getattr(scheduler, 'optimization_message', ''),
        "lastOptimizationAt": getattr(scheduler, 'last_optimization_at', None)
    }

@router.get("/api/cache/stats")
async def get_cache_stats():
    """獲取緩存統計信息"""
    return model_cache.get_stats()

@router.post("/api/cache/clear")
async def clear_cache(lottery_type: Optional[str] = None, model_type: Optional[str] = None):
    """
    清除模型緩存
    
    Query Parameters:
        lottery_type: 指定清除的彩種 (可選)
        model_type: 指定清除的模型 (可選)
    """
    count = model_cache.clear(lottery_type, model_type)
    return {
        "success": True,
        "cleared_count": count,
        "message": f"已清除 {count} 筆緩存"
    }
