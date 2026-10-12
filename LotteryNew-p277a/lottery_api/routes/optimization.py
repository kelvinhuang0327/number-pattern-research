from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Dict, Optional
import logging
import asyncio
import json

from schemas import (
    OptimizationRequest, ScheduleRequest, SyncDataRequest, StrategyEvaluationRequest,
    DrawData, PredictFromBackendRequest
)
from utils.scheduler import scheduler
from utils.smart_scheduler import smart_scheduler
from predictors import executor, advanced_engine # Use Singleton
from database import db_manager
from common import normalize_lottery_type, get_data_range_info, get_lottery_rules
from models.strategy_evaluator import strategy_evaluator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/auto-learning/optimize")
async def run_optimization(request: OptimizationRequest):
    """手動觸發自動優化"""
    try:
        logger.info(f"開始手動優化: {request.generations} 代, 種群 {request.population_size}, 彩券類型: {request.lotteryType or '未指定'}")
        
        lottery_type = normalize_lottery_type(request.lotteryType) if request.lotteryType else None
        
        if not scheduler.latest_data:
            scheduler.load_data()
            
        if not scheduler.latest_data:
            raise HTTPException(status_code=400, detail="後端沒有數據，請先點擊「同步數據到後端」按鈕")
            
        target_data = scheduler.get_data(lottery_type) if lottery_type else scheduler.latest_data
        
        if not target_data:
            target_data = scheduler.latest_data
            if lottery_type and target_data:
                target_data = [d for d in target_data if d.get('lotteryType') == lottery_type or d.get('lotteryType') == request.lotteryType]
                if not target_data:
                    logger.warning(f"找不到類型為 {lottery_type} 的數據，將使用全部數據")
                    target_data = scheduler.latest_data
        
        data_range = get_data_range_info(target_data)
        logger.info(f"📊 優化使用數據: {data_range['total_count']} 期")
        
        # Use dynamic rules
        rules = request.lotteryRules or get_lottery_rules(lottery_type or 'BIG_LOTTO')
        
        result = await scheduler.run_manual_optimization(
            history=target_data,
            lottery_rules=rules,
            generations=request.generations,
            population_size=request.population_size
        )
        
        return result
    except Exception as e:
        logger.error(f"優化失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/schedule/start")
async def start_schedule(request: ScheduleRequest):
    """啟動自動學習排程"""
    try:
        scheduler.start(schedule_time=request.schedule_time)
        return {
            "success": True,
            "message": f"排程已啟動，每天 {request.schedule_time} 執行優化",
            "schedule_time": request.schedule_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/schedule/stop")
async def stop_schedule():
    """停止自動學習排程"""
    try:
        scheduler.stop()
        return {"success": True, "message": "排程已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/schedule/run-now")
async def run_schedule_now(background_tasks: BackgroundTasks):
    """立即執行一次優化任務"""
    try:
        logger.info("🚀 手動觸發立即執行優化任務...")
        all_draws = db_manager.get_all_draws()
        if not all_draws or len(all_draws) < 50:
            return {"success": False, "message": "數據不足"}

        history = [{
            'date': draw['date'], 'draw': draw['draw'], 
            'numbers': draw['numbers'], 'lotteryType': draw['lotteryType']
        } for draw in all_draws]
        
        # Default rules for schedule update (should ideally be per-type)
        lottery_rules = get_lottery_rules('BIG_LOTTO')
        scheduler.update_data(history, lottery_rules)

        async def run_optimization_task():
            try:
                await scheduler._run_optimization()
                logger.info("✅ 後台優化任務執行完成")
            except Exception as e:
                logger.error(f"後台優化任務失敗: {str(e)}", exc_info=True)

        background_tasks.add_task(run_optimization_task)
        return {"success": True, "message": "優化任務已啟動", "status": "running_in_background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/auto-learning/schedule/status")
async def get_schedule_status():
    """獲取排程狀態"""
    status = scheduler.get_schedule_status()
    status['advanced_optimization_history'] = advanced_engine.optimization_history[-10:]
    return status

@router.get("/api/auto-learning/best-config")
async def get_best_config(lottery_type: Optional[str] = Query(None)):
    """獲取最佳配置"""
    config = scheduler.get_best_config(lottery_type)
    if not config:
        config = scheduler.load_config(lottery_type)
    return {"config": config}

@router.post("/api/auto-learning/set-target-fitness")
async def set_target_fitness(request: dict):
    """設定目標適應度"""
    try:
        target = request.get("target_fitness")
        if target is not None:
            target = float(target)
            if not (0 < target <= 1.0):
                raise HTTPException(status_code=400, detail="目標適應度必須在 0 到 1 之間")
        scheduler.set_target_fitness(target)
        return {"success": True, "message": f"已設定目標適應度: {target}" if target else "已禁用"}
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/auto-learning/optimization-history")
async def get_optimization_history(lottery_type: Optional[str] = Query(None)):
    """獲取優化歷史"""
    try:
        history = advanced_engine.optimization_history
        best_config = scheduler.get_best_config(lottery_type)
        config_info = None
        if best_config:
            config_file = f"data/best_config_{lottery_type}.json" if lottery_type else "data/best_config.json"
            import os
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    config_info = {'timestamp': data.get('timestamp'), 'config': best_config}
        return {
            "success": True, 
            "history": history[-20:], 
            "total_count": len(history),
            "best_config_info": config_info,
            "lottery_type": lottery_type
        }
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/sync-data")
async def sync_data(request: OptimizationRequest):
    """同步數據（用於排程）"""
    try:
        history = [draw.dict() for draw in request.history]
        inserted, duplicates = db_manager.insert_draws(history)
        
        # Use dynamic rules if provided or from config
        rules = request.lotteryRules or get_lottery_rules(request.lotteryType)
        scheduler.update_data(history, rules)
        
        return {"success": True, "inserted": inserted, "duplicates": duplicates}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/evaluate-strategies")
async def evaluate_strategies(request: StrategyEvaluationRequest):
    """評估預測策略"""
    try:
        logger.info(f"開始評估策略: {request.lotteryType}")
        if not scheduler.latest_data: scheduler.load_data()
        
        history = [d for d in scheduler.latest_data if d.get('lotteryType') == request.lotteryType]
        if len(history) < request.min_train_size + 10:
            raise HTTPException(status_code=400, detail="數據不足")
            
        base_rules = get_lottery_rules(request.lotteryType)
        lottery_rules = {**base_rules, 'lotteryType': request.lotteryType}
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            strategy_evaluator.evaluate_all_strategies,
            history, lottery_rules, request.test_ratio, request.min_train_size
        )
        return result
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/auto-learning/best-strategy")
async def get_best_strategy(lottery_type: Optional[str] = None):
    """獲取最佳策略"""
    try:
        best = strategy_evaluator.get_best_strategy()
        if not best and lottery_type:
            latest = strategy_evaluator.load_latest_evaluation(lottery_type)
            best = latest.get('best_strategy') if latest else None
        return {"has_best_strategy": bool(best), "best_strategy": best}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/advanced/multi-stage")
async def run_multi_stage_optimization_api(background_tasks: BackgroundTasks, request: dict):
    """多階段優化"""
    try:
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        history = db_manager.get_all_draws(lottery_type)
        if len(history) < 30: raise HTTPException(status_code=400, detail="數據不足")
        
        lottery_rules = get_lottery_rules(lottery_type)
        
        def run_optimization():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(advanced_engine.multi_stage_optimize(history, lottery_rules))
            loop.close()
            if result['success']:
                scheduler._save_config(result['best_config'], lottery_type)
        
        background_tasks.add_task(run_optimization)
        return {"success": True, "message": "多階段優化已啟動"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto-learning/advanced/adaptive-window")
async def run_adaptive_window_optimization_api(background_tasks: BackgroundTasks, request: dict):
    """自適應窗口優化"""
    try:
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        history = db_manager.get_all_draws(lottery_type)
        if len(history) < 30: raise HTTPException(status_code=400, detail="數據不足")
        
        lottery_rules = get_lottery_rules(lottery_type)

        def run_optimization():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(advanced_engine.adaptive_window_optimize(history, lottery_rules))
            loop.close()
            if result['success']:
                scheduler._save_config(result['best_config'], lottery_type)

        background_tasks.add_task(run_optimization)
        return {"success": True, "message": "自適應窗口優化已啟動"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/auto-learning/advanced/status")
async def get_advanced_optimization_status():
    """查詢進階優化狀態"""
    history = advanced_engine.optimization_history
    latest = history[-1] if history else None
    is_optimizing = False
    if latest:
        pass # Simplified Check
    return {"is_optimizing": is_optimizing, "latest_result": latest, "history_count": len(history)}

# ===== 智能排程 API =====
@router.post("/api/smart-learning/start")
async def start_smart_learning(request: dict):
    """啟動智能排程"""
    try:
        smart_scheduler.set_success_threshold(request.get('success_threshold', 0.30))
        smart_scheduler.start(request.get('evaluation_schedule', '02:00'), request.get('learning_schedule', '03:00'))
        return {"success": True, "message": "智能排程已啟動"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/smart-learning/stop")
async def stop_smart_learning():
    smart_scheduler.stop()
    return {"success": True, "message": "已停止"}

@router.get("/api/smart-learning/status")
async def get_smart_learning_status():
    return smart_scheduler.get_schedule_status()

@router.post("/api/smart-learning/sync-data")
async def sync_data_to_smart_scheduler(data: SyncDataRequest):
    rules = data.lottery_rules or get_lottery_rules(data.lotteryType)
    smart_scheduler.update_data(data.lotteryType, data.history, rules)
    return {"success": True, "message": "已同步"}

@router.post("/api/smart-learning/manual-evaluation")
async def manual_strategy_evaluation(request: dict):
    lottery_type = request.get('lotteryType')
    if not lottery_type: raise HTTPException(status_code=400, detail="Missing lotteryType")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: asyncio.run(smart_scheduler.manual_evaluation(lottery_type)))

@router.get("/api/smart-learning/best-strategy/{lottery_type}")
async def get_best_strategy_for_type(lottery_type: str):
    strategy = smart_scheduler.get_best_strategy(lottery_type)
    return {"success": True, "lottery_type": lottery_type, "strategy": strategy} if strategy else {"success": False, "message": "Not found"}

@router.get("/api/smart-learning/all-best-strategies")
async def get_all_best_strategies():
    strategies = smart_scheduler.get_all_best_strategies()
    return {"success": True, "strategies": strategies}
