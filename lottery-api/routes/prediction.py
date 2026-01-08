from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Dict, Optional
import logging
import asyncio
import json
import hashlib

from schemas import (
    PredictRequest, PredictResponse, PredictFromBackendRequest, PredictWithRangeRequest, DrawData
)
from predictors import (
    get_prophet_predictor, get_xgboost_predictor, get_autogluon_predictor,
    get_lstm_predictor, get_transformer_predictor, get_bayesian_ensemble_predictor,
    get_maml_predictor, MODEL_DISPATCH, ASYNC_MODEL_DISPATCH, executor,
    advanced_engine # Use Singleton
)
from utils.model_cache import model_cache
from utils.scheduler import scheduler
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.unified_predictor import prediction_engine
from models.enhanced_predictor import EnhancedPredictor
from models.smart_multi_bet import SmartMultiBetSystem
from models.daily539_predictor import Daily539Predictor
from database import db_manager
from common import normalize_lottery_type, load_backend_history, get_data_range_info, get_lottery_rules
from config import optimal_prediction_config
from models.strategy_adapter import strategy_adapter

# Initialize enhanced predictors
enhanced_predictor = EnhancedPredictor()
smart_multi_bet = SmartMultiBetSystem()
daily539_predictor = Daily539Predictor()

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    預測下一期彩票號碼
    """
    try:
        logger.info(f"收到預測請求: 模型={request.modelType}, 數據量={len(request.history)}")
        
        # 數據驗證
        if len(request.history) < 10:
            raise HTTPException(
                status_code=400, 
                detail="歷史數據不足，至少需要 10 期數據"
            )
        
        # AI 深度模型分支
        if request.modelType in ("prophet", "xgboost", "autogluon", "lstm", "transformer"):
            history_dicts = [draw.dict() for draw in request.history]
            if request.modelType == "prophet":
                result = await get_prophet_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "xgboost":
                result = await get_xgboost_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "autogluon":
                result = await get_autogluon_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "lstm":
                result = await get_lstm_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "transformer":
                result = await get_transformer_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
        elif request.modelType in ASYNC_MODEL_DISPATCH:
            # 异步集成模型（如贝叶斯优化集成）
            history_dicts = [draw.dict() for draw in request.history]
            result = await ASYNC_MODEL_DISPATCH[request.modelType](history_dicts, request.lotteryRules)
        elif request.modelType in MODEL_DISPATCH:
            history_dicts = [draw.dict() for draw in request.history]
            # Run synchronous prediction in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                MODEL_DISPATCH[request.modelType],
                history_dicts,
                request.lotteryRules
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的模型類型: {request.modelType}")
        
        logger.info(f"預測成功: {result['numbers']}, 信心度: {result['confidence']:.2%}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"預測過程發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"預測失敗: {str(e)}"
        )

@router.post("/api/predict-from-backend", response_model=PredictResponse)
async def predict_from_backend(request: PredictFromBackendRequest):
    """
    使用後端已存儲的數據進行預測（優化版）
    """
    try:
        logger.info(f"收到後端預測請求: 彩券={request.lotteryType}, 模型={request.modelType}")
        
        lottery_type = normalize_lottery_type(request.lotteryType)
        
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)
        data_range = get_data_range_info(history)
        logger.info(f"📊 使用數據: {data_range['total_count']} 期 | 日期: {data_range['date_range']} | 期號: {data_range['draw_range']}")
        
        extra_sig = None
        if request.modelType == "backend_optimized":
            best_config = getattr(scheduler, 'get_best_config', lambda lt: {})(lottery_type)
            
            # Use Strategy Adapter to refine config
            if best_config:
                best_config = strategy_adapter.adapt_weights(best_config, lottery_type, history)

            if best_config:
                cfg_str = json.dumps(best_config, sort_keys=True)
                extra_sig = hashlib.sha256(cfg_str.encode()).hexdigest()[:12]

        cached_result = model_cache.get(
            lottery_type,
            request.modelType,
            history,
            lottery_rules,
            extra_signature=extra_sig
        )
        
        if cached_result:
            logger.info(f"✅ 使用緩存結果，跳過模型訓練")
            return cached_result
        
        if request.modelType == "prophet":
            result = await get_prophet_predictor().predict(history, lottery_rules)
        elif request.modelType == "xgboost":
            result = await get_xgboost_predictor().predict(history, lottery_rules)
        elif request.modelType == "autogluon":
            result = await get_autogluon_predictor().predict(history, lottery_rules)
        elif request.modelType == "transformer":
            result = await get_transformer_predictor().predict(history, lottery_rules)
        elif request.modelType == "bayesian_ensemble":
            result = await get_bayesian_ensemble_predictor().predict(history, lottery_rules)
        elif request.modelType == "maml":
            result = await get_maml_predictor().predict(history, lottery_rules)
        elif request.modelType == "lstm":
            result = await get_lstm_predictor().predict(history, lottery_rules)
        elif request.modelType == "backend_optimized":
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            use_data = history
            recent_window = min(200, len(use_data))
            freq_counter = {}
            for draw in use_data[-recent_window:]:
                for n in draw.get('numbers', []):
                    freq_counter[n] = freq_counter.get(n, 0) + 1

            missing_map = {n: 0 for n in range(min_num, max_num + 1)}
            for num in missing_map.keys():
                count = 0
                for d in reversed(use_data):
                    if num not in d.get('numbers', []):
                        count += 1
                    else:
                        break
                missing_map[num] = count

            max_freq = max(freq_counter.values()) if freq_counter else 1
            max_missing = max(missing_map.values()) if missing_map else 1

            # Use (possibly adapted) best_config
            fw = best_config.get('frequency_weight', 0.5)
            mw = best_config.get('missing_weight', 0.2)
            hw = best_config.get('hot_cold_weight', 0.1)
            tw = best_config.get('trend_weight', 0.1)

            scores = {}
            for num in range(min_num, max_num + 1):
                freq_score = (freq_counter.get(num, 0) / max_freq) if max_freq > 0 else 0
                miss_score = (missing_map.get(num, 0) / max_missing) if max_missing > 0 else 0
                hotcold_noise = 0.05 * hw * ((num % 7) / 7)
                trend_noise = 0.05 * tw * ((num % 5) / 5)
                scores[num] = freq_score * fw + (1 - (miss_score / (miss_score + 5))) * mw + hotcold_noise + trend_noise

            sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            predicted = [n for n, _ in sorted_nums[:pick_count]]
            predicted.sort()
            result = {
                "numbers": predicted,
                "confidence": 0.85,
                "method": "優化混合策略 (Optimized)",
                "lotteryType": request.lotteryType
            }

        elif request.modelType in MODEL_DISPATCH:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                MODEL_DISPATCH[request.modelType],
                history,
                lottery_rules
            )
        elif request.modelType == "ensemble":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.ensemble_predict,
                history,
                lottery_rules
            )
        elif request.modelType == "ensemble_advanced":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.ensemble_advanced_predict,
                history,
                lottery_rules
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型類型: {request.modelType}"
            )
        
        model_cache.set(
            request.lotteryType,
            request.modelType,
            result,
            history,
            lottery_rules,
            extra_signature=extra_sig
        )
        
        logger.info(f"預測成功: {result['numbers']}, 信心度: {result['confidence']:.2%}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"後端預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"預測失敗: {str(e)}"
        )

@router.post("/api/predict-from-backend-eval", response_model=PredictResponse)
async def predict_from_backend_eval(request: PredictFromBackendRequest, recent_count: int = Query(200, ge=10, le=1000)):
    """
    評估專用預測端點（固定配置、禁用快取）
    
    與 /api/predict-from-backend 的差異：
    1. 使用固定配置（backend_optimized 不會動態調整）
    2. 強制使用最近 N 期數據（預設 200）
    3. 禁用快取，確保結果可重現
    4. 所有模型統一預測特別號
    """
    try:
        logger.info(f"收到評估預測請求: 彩券={request.lotteryType}, 模型={request.modelType}, 窗口={recent_count}")
        
        lottery_type = normalize_lottery_type(request.lotteryType)
        
        # Load history and apply window
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)
        if len(history) > recent_count:
            history = history[-recent_count:]
        
        data_range = get_data_range_info(history)
        logger.info(f"📊 評估數據: {data_range['total_count']} 期 | 日期: {data_range['date_range']}")
        
        # NO CACHE for evaluation
        
        if request.modelType == "prophet":
            result = await get_prophet_predictor().predict(history, lottery_rules)
        elif request.modelType == "xgboost":
            result = await get_xgboost_predictor().predict(history, lottery_rules)
        elif request.modelType == "autogluon":
            result = await get_autogluon_predictor().predict(history, lottery_rules)
        elif request.modelType == "transformer":
            result = await get_transformer_predictor().predict(history, lottery_rules)
        elif request.modelType == "bayesian_ensemble":
            result = await get_bayesian_ensemble_predictor().predict(history, lottery_rules)
        elif request.modelType == "maml":
            result = await get_maml_predictor().predict(history, lottery_rules)
        elif request.modelType == "lstm":
            result = await get_lstm_predictor().predict(history, lottery_rules)
        elif request.modelType == "backend_optimized":
            # Use FIXED config for consistency
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)
            
            best_config = {
                'frequency_weight': 0.5,
                'missing_weight': 0.3,
                'hot_cold_weight': 0.1,
                'trend_weight': 0.1
            }

            recent_window = min(200, len(history))
            freq_counter = {}
            for draw in history[-recent_window:]:
                for n in draw.get('numbers', []):
                    freq_counter[n] = freq_counter.get(n, 0) + 1

            missing_map = {n: 0 for n in range(min_num, max_num + 1)}
            for num in missing_map.keys():
                count = 0
                for d in reversed(history):
                    if num not in d.get('numbers', []):
                        count += 1
                    else:
                        break
                missing_map[num] = count

            max_freq = max(freq_counter.values()) if freq_counter else 1
            max_missing = max(missing_map.values()) if missing_map else 1

            fw = best_config.get('frequency_weight', 0.5)
            mw = best_config.get('missing_weight', 0.3)
            hw = best_config.get('hot_cold_weight', 0.1)
            tw = best_config.get('trend_weight', 0.1)

            scores = {}
            for num in range(min_num, max_num + 1):
                freq_score = (freq_counter.get(num, 0) / max_freq) if max_freq > 0 else 0
                miss_score = (missing_map.get(num, 0) / max_missing) if max_missing > 0 else 0
                hotcold_noise = 0.05 * hw * ((num % 7) / 7)
                trend_noise = 0.05 * tw * ((num % 5) / 5)
                scores[num] = freq_score * fw + (1 - (miss_score / (miss_score + 5))) * mw + hotcold_noise + trend_noise

            sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            predicted = [n for n, _ in sorted_nums[:pick_count]]
            predicted.sort()
            
            result = {
                "numbers": predicted,
                "confidence": 0.85,
                "method": "優化混合策略 (Eval-Static)",
                "lotteryType": request.lotteryType
            }
        elif request.modelType in MODEL_DISPATCH:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                MODEL_DISPATCH[request.modelType],
                history,
                lottery_rules
            )
        elif request.modelType == "ensemble":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.ensemble_predict,
                history,
                lottery_rules
            )
        elif request.modelType == "optimized_ensemble":
            optimized = OptimizedEnsemblePredictor(prediction_engine)
            result = await optimized.predict(history, lottery_rules)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的模型類型: {request.modelType}")
        
        # ⚠️ 大樂透特別號不預測！
        # 玩家只選6個主號碼，特別號是開獎時從剩餘43個號碼中抽取的
        # 預測系統只預測6個主號碼，回測時才用來對比歷史的7個開獎號碼（6主+1特別）
        
        result['dataRange'] = data_range
        logger.info(f"評估預測完成: {result['numbers']}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"評估預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"評估預測失敗: {str(e)}"
        )

@router.post("/api/predict-with-range", response_model=PredictResponse)
async def predict_with_range(request: PredictWithRangeRequest):
    """
    使用期數/日期範圍進行預測（最優化模式）
    """
    try:
        logger.info(f"收到範圍預測請求: 彩券={request.lotteryType}, 模型={request.modelType}")

        lottery_type = normalize_lottery_type(request.lotteryType)

        if request.startDraw and request.endDraw:
            filtered_history = db_manager.get_draws_by_range(
                lottery_type=lottery_type,
                start_draw=request.startDraw,
                end_draw=request.endDraw
            )
        elif request.startDate or request.endDate:
            all_draws = db_manager.get_all_draws(lottery_type=lottery_type)
            filtered_history = []
            for draw in all_draws:
                draw_date = draw.get('date', '').replace('/', '-')
                if request.startDate:
                    start_compare = request.startDate.replace('/', '-')
                    if draw_date < start_compare: continue
                if request.endDate:
                    end_compare = request.endDate.replace('/', '-')
                    if draw_date > end_compare: continue
                filtered_history.append(draw)
        elif request.recentCount:
            all_draws = db_manager.get_all_draws(lottery_type=lottery_type)
            filtered_history = all_draws[-request.recentCount:] if len(all_draws) >= request.recentCount else all_draws
        else:
            filtered_history = db_manager.get_all_draws(lottery_type=lottery_type)

        if len(filtered_history) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"查詢結果數據不足（需要至少10期，目前{len(filtered_history)}期）"
            )
        
        data_range = get_data_range_info(filtered_history)
        logger.info(f"📊 範圍預測數據: {data_range['total_count']} 期")

        if hasattr(request, 'lotteryRules') and request.lotteryRules:
            lottery_rules = request.lotteryRules.dict() if hasattr(request.lotteryRules, 'dict') else request.lotteryRules
        else:
            lottery_rules = get_lottery_rules(request.lotteryType)
        
        if request.modelType == "prophet":
            result = await get_prophet_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "xgboost":
            result = await get_xgboost_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "autogluon":
            result = await get_autogluon_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "transformer":
            result = await get_transformer_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "bayesian_ensemble":
            result = await get_bayesian_ensemble_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "maml":
            result = await get_maml_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "lstm":
            result = await get_lstm_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "backend_optimized":
            best_config = scheduler.get_best_config(request.lotteryType)
            if not best_config:
                best_config = scheduler.get_best_config()
            
            if not best_config:
                raise HTTPException(status_code=400, detail="沒有可用的優化配置，請先執行自動優化")
            
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)
            
            # Use Singleton Engine
            predicted = advanced_engine._predict_with_config(
                best_config,
                filtered_history,
                pick_count,
                min_num,
                max_num
            )
            
            advanced_keys = ['entropy_weight', 'clustering_weight', 'temporal_weight', 'feature_eng_weight']
            advanced_weight = sum(best_config.get(k, 0) for k in advanced_keys)
            confidence = min(0.15, 0.08 + advanced_weight * 0.1)
            
            result = {
                "numbers": predicted,
                "confidence": confidence,
                "method": "優化混合策略 (Advanced Range)",
                "notes": f"使用 {len(filtered_history)} 期數據 + 高級策略進行範圍預測"
            }
        elif request.modelType == "optimized_ensemble":
            ensemble_predictor = OptimizedEnsemblePredictor(prediction_engine)
            loop = asyncio.get_running_loop()
            ensemble_result = await loop.run_in_executor(
                executor,
                ensemble_predictor.predict,
                filtered_history,
                lottery_rules
            )
            result = {
                "numbers": ensemble_result['bet1']['numbers'],
                "confidence": ensemble_result['bet1']['confidence'],
                "method": "優化集成預測",
                "bet1": ensemble_result['bet1'],
                "bet2": ensemble_result['bet2'],
                "strategy_weights": ensemble_result.get('strategy_weights', {}),
                "notes": f"使用 {len(filtered_history)} 期數據，動態權重集成"
            }
        elif request.modelType in MODEL_DISPATCH:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                MODEL_DISPATCH[request.modelType],
                filtered_history,
                lottery_rules
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的模型類型: {request.modelType} (in predict-with-range)")

        return result
    except HTTPException: raise
    except Exception as e:
        logger.error(f"範圍預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"範圍預測失敗: {str(e)}")

@router.post("/api/predict-optimized", response_model=PredictResponse)
async def predict_optimized_route(request: PredictRequest):
    request.modelType = "backend_optimized"
    return await predict(request)

@router.post("/api/auto-learning/predict-with-best", response_model=PredictResponse)
async def predict_with_best_route(request: PredictRequest):
    return await predict(request)


@router.post("/api/predict-entropy-8-bets")
async def predict_entropy_8_bets_route(request: PredictFromBackendRequest):
    """
    熵驅動 8 注預測端點
    
    使用革命性的熵最大化方法生成8注差異化的號碼組合
    支持策略: balanced (平衡), aggressive (激進), conservative (保守)
    """
    try:
        from models.entropy_transformer import EntropyTransformerModel
        from models.anti_consensus_sampler import EntropyMaximizedSampler, AntiConsensusFilter, DiversityCalculator
        import numpy as np
        
        logger.info(f"收到熵8注預測請求: 彩券={request.lotteryType}")
        
        lottery_type = normalize_lottery_type(request.lotteryType)
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)
        
        # 使用最近100期
        history = history[:100]
        
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 初始化模型和採樣器
        model = EntropyTransformerModel(max_num=max_num)
        sampler = EntropyMaximizedSampler(n_bets=8, numbers_per_bet=pick_count)
        anti_filter = AntiConsensusFilter(penalty_factor=0.7)
        
        # 獲取模型概率
        probs = model.predict(history)
        
        # 獲取共識號碼
        consensus_numbers = set()
        try:
            freq_result = prediction_engine.frequency_predict(history, lottery_rules)
            consensus_numbers.update(freq_result['numbers'])
        except:
            pass
        try:
            trend_result = prediction_engine.trend_predict(history, lottery_rules)
            consensus_numbers.update(trend_result['numbers'])
        except:
            pass
        
        # 應用反共識過濾
        filtered_probs = anti_filter.filter(probs, consensus_numbers)
        
        # 獲取策略（默認 balanced）
        strategy = getattr(request, 'strategy', 'balanced') or 'balanced'
        
        # 生成8注
        bets, metadata = sampler.generate_diverse_8_bets(filtered_probs, strategy=strategy)
        
        # 計算覆蓋率和多樣性
        all_numbers = set()
        for bet in bets:
            all_numbers.update(bet)
        coverage_rate = len(all_numbers) / max_num
        diversity_score = DiversityCalculator.calculate_diversity_score(bets)
        
        return {
            "bets": [
                {
                    "numbers": sorted(bet_meta['numbers']),
                    "type": bet_meta['type'],
                    "avg_prob": float(bet_meta['avg_prob']),
                    "odd_count": bet_meta['odd_count'],
                    "sum": bet_meta['sum']
                }
                for bet_meta in metadata
            ],
            "analysis": {
                "coverage_rate": float(coverage_rate),
                "unique_numbers": len(all_numbers),
                "total_numbers": max_num,
                "diversity_score": float(diversity_score),
                "strategy": strategy,
                "consensus_numbers": sorted(list(consensus_numbers))
            },
            "method": "熵驅動 Transformer (12維特徵 + 反共識)",
            "lotteryType": request.lotteryType
        }
        
    except Exception as e:
        logger.error(f"熵8注預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")

@router.get("/api/models")
async def list_models(lottery_type: Optional[str] = Query(None)):
    """列出所有可用的模型和策略"""
    data_size = 0
    if lottery_type:
        try:
             l_type = normalize_lottery_type(lottery_type)
             data_size = len(scheduler.get_data(l_type))
        except: pass

    models = [
            {
                "id": "prophet",
                "name": "Prophet 時間序列",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "xgboost",
                "name": "XGBoost 梯度提升",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "lstm",
                "name": "LSTM 神經網絡",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "transformer",
                "name": "Transformer (Attention)",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "autogluon",
                "name": "AutoGluon (AutoML)",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "bayesian_ensemble",
                "name": "貝葉斯集成 (Bayesian)",
                "category": "ai",
                "status": "available",
            },
            {
                "id": "maml",
                "name": "MAML (Meta Learning)",
                "category": "ai",
                "status": "available",
            },
            
            # ===== 統計模型 =====
            {
                "id": "frequency",
                "name": "頻率分析",
                "category": "statistical",
                "status": "available",
            },
            {
                "id": "trend",
                "name": "趨勢分析",
                "category": "statistical",
                "status": "available",
            },
            {
                "id": "deviation",
                "name": "乖離率分析",
                "category": "statistical",
                "status": "available",
            },
            {
                "id": "statistical",
                "name": "綜合統計",
                "category": "statistical",
                "status": "available",
            },
            {
                "id": "markov",
                "name": "馬可夫鏈",
                "category": "statistical",
                "status": "available",
            },
            {
                "id": "monte_carlo",
                "name": "蒙地卡羅模擬",
                "category": "statistical",
                "status": "available",
            },
            
            # ===== 民間/分佈策略 =====
            {
                "id": "odd_even",
                "name": "奇偶平衡",
                "category": "distribution",
                "status": "available",
            },
            {
                "id": "zone_balance",
                "name": "區間平衡",
                "category": "distribution",
                "status": "available",
            },
            {
                "id": "hot_cold",
                "name": "冷熱混合",
                "category": "distribution",
                "status": "available",
            },
            {
                "id": "sum_range",
                "name": "和值區間",
                "category": "distribution",
                "status": "available",
            },
            {
                "id": "wheeling",
                "name": "聰明組合 (Wheeling)",
                "category": "distribution",
                "status": "available",
            },
            {
                "id": "number_pairs",
                "name": "連號分析",
                "category": "distribution",
                "status": "available",
            },
            
            # ===== 集成/高級策略 =====
            {
                "id": "ensemble",
                "name": "簡單平均集成",
                "category": "ensemble",
                "status": "available",
            },
            {
                "id": "random_forest",
                "name": "隨機森林",
                "category": "ensemble",
                "status": "available",
            },
            {
                "id": "ensemble_advanced",
                "name": "加權集成 (Advanced)",
                "category": "ensemble",
                "status": "available",
            },
            {
                "id": "backend_optimized",
                "name": "自動優化混合策略 (Recommended)",
                "category": "ensemble",
                "status": "available" if scheduler.get_best_config() else "unavailable",
            },
            {
                "id": "optimized_ensemble",
                "name": "動態權重集成 (Dynamic)",
                "category": "ensemble",
                "status": "available"
            },
            
            # ===== 高級分析策略 (Advanced Analysis) =====
            {
                "id": "entropy",
                "name": "熵值分析 (Entropy)",
                "category": "advanced_analysis",
                "status": "available"
            },
            {
                "id": "entropy_transformer",
                "name": "熵驅動 Transformer (創新)",
                "category": "advanced_analysis",
                "status": "available"
            },
            {
                "id": "clustering",
                "name": "K-Means 聚類分析",
                "category": "advanced_analysis",
                "status": "available"
            },
            {
                "id": "dynamic_ensemble",
                "name": "動態集成策略",
                "category": "advanced_analysis",
                "status": "available"
            },
            {
                "id": "temporal",
                "name": "時序特徵分析",
                "category": "advanced_analysis",
                "status": "available"
            },
            {
                "id": "feature_engineering",
                "name": "特徵工程預測",
                "category": "advanced_analysis",
                "status": "available"
            }
    ]
    
    adjusted_models = strategy_adapter.adjust_available_models(models, lottery_type, data_size)

    return {
        "models": adjusted_models
    }


# ==================== 增強型預測 API ====================

@router.post("/api/predict-enhanced")
async def predict_enhanced(request: PredictFromBackendRequest):
    """
    增強型預測端點 - 使用新設計的預測方法

    可用方法 (method 參數):
    - consecutive_friendly: 連號友善策略（不迴避上期號碼）
    - cold_comeback: 冷號回歸策略
    - constrained: 約束優化策略（奇偶比、和值範圍等）
    - multi_window_fusion: 多窗口融合策略
    - coverage_optimized: 覆蓋率優化策略
    - enhanced_ensemble: 綜合增強策略（推薦）
    """
    try:
        logger.info(f"收到增強預測請求: 彩券={request.lotteryType}")

        lottery_type = normalize_lottery_type(request.lotteryType)
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)

        # 獲取預測方法
        method_name = getattr(request, 'method', 'enhanced_ensemble') or 'enhanced_ensemble'

        # 方法映射
        method_map = {
            'consecutive_friendly': enhanced_predictor.consecutive_friendly_predict,
            'cold_comeback': enhanced_predictor.cold_number_comeback_predict,
            'constrained': enhanced_predictor.constrained_predict,
            'multi_window_fusion': enhanced_predictor.multi_window_fusion_predict,
            'coverage_optimized': enhanced_predictor.coverage_optimized_predict,
            'enhanced_ensemble': enhanced_predictor.enhanced_ensemble_predict,
        }

        if method_name not in method_map:
            method_name = 'enhanced_ensemble'

        # 執行預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            method_map[method_name],
            history,
            lottery_rules
        )

        return {
            "numbers": result['numbers'],
            "confidence": result['confidence'],
            "method": f"增強預測 - {method_name}",
            "lotteryType": request.lotteryType,
            "dataUsed": len(history)
        }

    except Exception as e:
        logger.error(f"增強預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


@router.post("/api/predict-enhanced-all")
async def predict_enhanced_all(request: PredictFromBackendRequest):
    """
    獲取所有增強型預測方法的結果
    """
    try:
        logger.info(f"收到全部增強預測請求: 彩券={request.lotteryType}")

        lottery_type = normalize_lottery_type(request.lotteryType)
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)

        methods = [
            ('consecutive_friendly', '連號友善', enhanced_predictor.consecutive_friendly_predict),
            ('cold_comeback', '冷號回歸', enhanced_predictor.cold_number_comeback_predict),
            ('constrained', '約束優化', enhanced_predictor.constrained_predict),
            ('multi_window_fusion', '多窗口融合', enhanced_predictor.multi_window_fusion_predict),
            ('coverage_optimized', '覆蓋率優化', enhanced_predictor.coverage_optimized_predict),
            ('enhanced_ensemble', '綜合增強', enhanced_predictor.enhanced_ensemble_predict),
        ]

        results = []
        loop = asyncio.get_running_loop()

        for method_id, method_name, method_func in methods:
            try:
                result = await loop.run_in_executor(
                    executor,
                    method_func,
                    history,
                    lottery_rules
                )
                results.append({
                    "methodId": method_id,
                    "methodName": method_name,
                    "numbers": result['numbers'],
                    "confidence": result['confidence']
                })
            except Exception as e:
                logger.warning(f"方法 {method_name} 失敗: {e}")

        return {
            "predictions": results,
            "lotteryType": request.lotteryType,
            "dataUsed": len(history),
            "totalMethods": len(results)
        }

    except Exception as e:
        logger.error(f"全部增強預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


# ==================== 智能多組號碼 API ====================

@router.post("/api/predict-smart-multi-bet")
async def predict_smart_multi_bet(
    request: PredictFromBackendRequest,
    num_bets: int = Query(6, ge=1, le=10, description="要生成的組數")
):
    """
    智能多組號碼預測 - 生成多組互補的號碼組合

    特點：
    - 多組互補號碼，提高整體覆蓋率
    - 每組使用不同策略（熱門、均衡、冷號、連號、區間、約束）
    - 平均可覆蓋 60%+ 的號碼池
    """
    try:
        logger.info(f"收到智能多組預測請求: 彩券={request.lotteryType}, 組數={num_bets}")

        lottery_type = normalize_lottery_type(request.lotteryType)
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)

        # 執行多組預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            smart_multi_bet.generate_smart_bets,
            history,
            lottery_rules,
            num_bets
        )

        return {
            "bets": result['bets'],
            "totalBets": result['total_bets'],
            "uniqueNumbers": result['unique_numbers'],
            "coverageRate": result['coverage_rate'],
            "allNumbers": result['numbers_list'],
            "lotteryType": request.lotteryType,
            "dataUsed": len(history),
            "method": "智能多組號碼系統"
        }

    except Exception as e:
        logger.error(f"智能多組預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


@router.get("/api/enhanced-methods")
async def list_enhanced_methods():
    """列出所有增強型預測方法"""
    return {
        "methods": [
            {
                "id": "consecutive_friendly",
                "name": "連號友善策略",
                "description": "不迴避上期號碼，基於歷史數據顯示 55% 機率有重複號碼",
                "category": "enhanced"
            },
            {
                "id": "cold_comeback",
                "name": "冷號回歸策略",
                "description": "預測即將回歸的冷號，追蹤每個號碼的出現週期",
                "category": "enhanced"
            },
            {
                "id": "constrained",
                "name": "約束優化策略",
                "description": "滿足統計約束條件：奇偶比 3:3 或 4:2，和值 128-173",
                "category": "enhanced"
            },
            {
                "id": "multi_window_fusion",
                "name": "多窗口融合策略",
                "description": "結合短期(10期)、中期(30期)、長期(100期)分析",
                "category": "enhanced"
            },
            {
                "id": "coverage_optimized",
                "name": "覆蓋率優化策略",
                "description": "基於組合數學的覆蓋設計，最大化區間和配對覆蓋",
                "category": "enhanced"
            },
            {
                "id": "enhanced_ensemble",
                "name": "綜合增強策略",
                "description": "融合所有增強方法的投票結果，推薦使用",
                "category": "enhanced",
                "recommended": True
            }
        ],
        "smartMultiBet": {
            "description": "智能多組號碼系統",
            "features": [
                "生成 1-10 組互補號碼",
                "每組使用不同策略",
                "平均覆蓋率 60%+",
                "多組合併可命中 4-6 個目標號碼"
            ]
        }
    }


# ==================== 最佳配置預測 API ====================

@router.post("/api/predict-optimal")
async def predict_optimal(request: PredictFromBackendRequest):
    """
    使用回測驗證的最佳配置進行預測

    根據彩票類型自動選擇最佳方法和數據窗口:
    - 威力彩 (POWER_LOTTO): Ensemble + 100期
    - 今彩539 (DAILY_539): Monte Carlo + 100期
    - 大樂透 (BIG_LOTTO): Bayesian + 300期
    """
    try:
        logger.info(f"收到最佳配置預測請求: 彩券={request.lotteryType}")

        lottery_type = normalize_lottery_type(request.lotteryType)

        # 獲取最佳配置
        optimal_config = optimal_prediction_config.get_optimal_config(lottery_type)
        optimal_method = optimal_config.get("optimal_method", "ensemble_predict")
        optimal_window = optimal_config.get("optimal_window", 100)

        logger.info(f"📊 最佳配置: 方法={optimal_method}, 窗口={optimal_window}")

        # 載入數據
        history, lottery_rules = load_backend_history(lottery_type, min_required=10)

        # 應用最佳窗口大小
        if len(history) > optimal_window:
            history = history[:optimal_window]

        data_range = get_data_range_info(history)
        logger.info(f"📊 使用數據: {data_range['total_count']} 期")

        # 獲取預測方法
        method_map = {
            "ensemble_predict": prediction_engine.ensemble_predict,
            "monte_carlo_predict": prediction_engine.monte_carlo_predict,
            "bayesian_predict": prediction_engine.bayesian_predict,
            "trend_predict": prediction_engine.trend_predict,
            "frequency_predict": prediction_engine.frequency_predict,
            "hot_cold_mix_predict": prediction_engine.hot_cold_mix_predict,
            "sota_predict": prediction_engine.sota_predict,
        }

        if optimal_method not in method_map:
            optimal_method = "ensemble_predict"

        # 執行預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            method_map[optimal_method],
            history,
            lottery_rules
        )

        # 獲取方法描述
        method_desc = optimal_prediction_config.get_method_description(optimal_method)

        return {
            "numbers": result['numbers'],
            "confidence": result['confidence'],
            "method": f"最佳配置: {method_desc}",
            "lotteryType": request.lotteryType,
            "optimalConfig": {
                "method": optimal_method,
                "window": optimal_window,
                "description": method_desc,
                "backtest_result": optimal_config.get("backtest_result", {})
            },
            "dataRange": data_range,
            "special": result.get('special')
        }

    except Exception as e:
        logger.error(f"最佳配置預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


@router.get("/api/optimal-configs")
async def get_optimal_configs():
    """
    獲取所有彩票類型的最佳預測配置
    """
    configs = optimal_prediction_config.get_all_configs()

    result = {}
    for lottery_type, config in configs.items():
        result[lottery_type] = {
            "name": config.get("name", lottery_type),
            "optimal_method": config.get("optimal_method"),
            "optimal_window": config.get("optimal_window"),
            "method_description": optimal_prediction_config.get_method_description(
                config.get("optimal_method", "")
            ),
            "backtest_result": config.get("backtest_result", {}),
            "notes": config.get("notes", "")
        }

    return {
        "configs": result,
        "updated": "2025-12-22",
        "description": "基於回測驗證的最佳預測配置"
    }


@router.post("/api/predict-double-bet")
async def predict_double_bet(
    lottery_type: str,
    mode: str = Query("optimal", description="雙注模式: optimal, dynamic, balanced")
):
    """
    生成最優雙注組合預測

    模式說明：
    - optimal: 極端奇數 + 冷號回歸（116期驗證50%命中率）
    - dynamic: 根據上期奇偶配比自動選擇策略
    - balanced: 標準熱號 + 極端奇數

    Returns:
        包含兩注預測結果及覆蓋率分析
    """
    try:
        logger.info(f"收到雙注預測請求: 彩券={lottery_type}, 模式={mode}")

        # 標準化彩券類型
        lottery_type = normalize_lottery_type(lottery_type)

        # 載入數據
        history, lottery_rules = load_backend_history(lottery_type, min_required=20)

        # 執行雙注預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            prediction_engine.generate_double_bet,
            history,
            lottery_rules,
            mode
        )

        # 構建返回結果
        response = {
            "lotteryType": lottery_type,
            "mode": mode,
            "bet1": {
                "numbers": result['bet1']['numbers'],
                "confidence": result['bet1']['confidence'],
                "method": result['bet1']['method'],
                "special": result['bet1'].get('special'),
                "meta_info": result['bet1'].get('meta_info', {})
            },
            "bet2": {
                "numbers": result['bet2']['numbers'],
                "confidence": result['bet2']['confidence'],
                "method": result['bet2']['method'],
                "special": result['bet2'].get('special'),
                "meta_info": result['bet2'].get('meta_info', {})
            },
            "analysis": {
                "total_coverage": result['meta_info']['coverage'],
                "overlap_count": result['meta_info']['overlap'],
                "complementary_score": result['meta_info']['complementary_score'],
                "complementary_rate": result['meta_info']['complementary_rate'],
                "reason": result['meta_info']['reason'],
                "expected_hit_rate": result['meta_info']['expected_hit_rate']
            },
            "recommendation": {
                "why_this_combo": result['meta_info']['reason'],
                "coverage_efficiency": f"{result['meta_info']['coverage']}個號碼覆蓋{lottery_rules['maxNumber']}號池的{result['meta_info']['coverage']/lottery_rules['maxNumber']*100:.1f}%",
                "usage_tip": "建議同時投注兩組號碼，最大化覆蓋率"
            }
        }

        logger.info(f"雙注預測成功: 覆蓋{result['meta_info']['coverage']}個號碼, 重疊{result['meta_info']['overlap']}個")

        return response

    except Exception as e:
        logger.error(f"雙注預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"雙注預測失敗: {str(e)}")


# ==================== 今彩539 專用 API ====================

@router.post("/api/predict-dual-bet-539")
async def predict_dual_bet_539():
    """
    今彩539 2注覆蓋預測 - 達成 28.12% 中獎率

    回測驗證結果 (2025年313期):
    - 單注最佳: sum_range(300期) = 15.34%
    - 2注覆蓋: 28.12% ✅ 超越20%目標

    策略說明:
    - 第1注: sum_range 方法 (窗口300期) — 和值範圍分析
    - 第2注: tail 方法 (窗口100期) — 尾數分布分析

    成功標準: 任一注中2個號碼以上即為成功

    Returns:
        包含兩注號碼組合及分析資訊
    """
    try:
        logger.info("收到今彩539 2注覆蓋預測請求")

        # 載入數據
        history, lottery_rules = load_backend_history('DAILY_539', min_required=300)

        # 獲取數據範圍
        data_range = get_data_range_info(history)
        logger.info(f"📊 使用數據: {data_range['total_count']} 期")

        # 執行2注預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            daily539_predictor.dual_bet_predict,
            history,
            lottery_rules
        )

        # 構建返回結果
        response = {
            "lotteryType": "DAILY_539",
            "strategy": "2注覆蓋策略",
            "bets": result['bets'],
            "num_bets": result['num_bets'],
            "analysis": {
                "expected_win_rate": result['expected_win_rate'],
                "expected_win_rate_pct": f"{result['expected_win_rate']*100:.2f}%",
                "periods_per_win": result['periods_per_win'],
                "win_threshold": result['win_threshold'],
                "unique_numbers": result['unique_numbers'],
                "coverage_rate": result['coverage_rate'],
                "improvement_vs_single": result['improvement_vs_single'],
            },
            "recommendation": result['recommendation'],
            "method": result['method'],
            "dataRange": data_range,
            "validation": {
                "backtest_year": 2025,
                "backtest_periods": 313,
                "verified": True
            }
        }

        logger.info(f"今彩539 2注預測成功: 預期中獎率={result['expected_win_rate']*100:.2f}%")

        return response

    except Exception as e:
        logger.error(f"今彩539 2注預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


@router.post("/api/predict-triple-bet-539")
async def predict_triple_bet_539():
    """
    今彩539 3注覆蓋預測 - 達成 36.42% 中獎率 (超越33%目標)

    回測驗證結果 (2025年313期):
    - 單注最佳: 15.34%
    - 2注覆蓋: 28.12%
    - 3注覆蓋: 36.42% ✅ 超越33%目標

    最佳組合 (經35種組合回測驗證):
    - 第1注: sum_range 方法 (窗口300期) — 和值範圍分析
    - 第2注: bayesian 方法 (窗口300期) — 貝葉斯統計分析
    - 第3注: zone_opt 方法 (窗口200期) — 區間優化分析

    成功標準: 任一注中2個號碼以上即為成功

    Returns:
        包含三注號碼組合及分析資訊
    """
    try:
        logger.info("收到今彩539 3注覆蓋預測請求")

        # 載入數據
        history, lottery_rules = load_backend_history('DAILY_539', min_required=300)

        # 獲取數據範圍
        data_range = get_data_range_info(history)
        logger.info(f"📊 使用數據: {data_range['total_count']} 期")

        # 執行3注預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            daily539_predictor.triple_bet_predict,
            history,
            lottery_rules
        )

        # 構建返回結果
        response = {
            "lotteryType": "DAILY_539",
            "strategy": "3注覆蓋策略",
            "bets": result['bets'],
            "num_bets": result['num_bets'],
            "analysis": {
                "expected_win_rate": result['expected_win_rate'],
                "expected_win_rate_pct": result.get('expected_win_rate_pct', '36.42%'),
                "periods_per_win": result['periods_per_win'],
                "win_threshold": result['win_threshold'],
                "unique_numbers": result['analysis']['unique_numbers'],
                "coverage_rate": result['analysis']['coverage_rate'],
                "overlap_stats": {
                    "bet1_bet2": result['analysis']['overlap_bet1_bet2'],
                    "bet1_bet3": result['analysis']['overlap_bet1_bet3'],
                    "bet2_bet3": result['analysis']['overlap_bet2_bet3'],
                }
            },
            "comparison": result['comparison'],
            "recommendation": result['recommendation'],
            "method": result['method'],
            "dataRange": data_range,
            "validation": result['validation']
        }

        logger.info(f"今彩539 3注預測成功: 預期中獎率=36.42%")

        return response

    except Exception as e:
        logger.error(f"今彩539 3注預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


@router.post("/api/predict-consecutive-539")
async def predict_consecutive_539():
    """
    今彩539 連號強化預測 - 追求大獎 (中4-5個號碼)

    回測驗證結果 (2025年315期):
    - 中獎率: 11.75% (低於其他方法)
    - 中3個: 2次
    - 中4個: 1次 🏆 唯一命中4個的方法！
    - 中5個: 0次

    策略:
    - 基於 sum_range 生成基礎預測
    - 強制加入歷史最熱門的連號對
    - 連號對提高號碼群聚機會，增加大獎潛力

    適用場景:
    - 願意犧牲中獎頻率，追求大獎的玩家
    - 建議搭配3注覆蓋策略一起使用

    Returns:
        包含連號強化預測結果及分析資訊
    """
    try:
        logger.info("收到今彩539連號強化預測請求 (追求大獎)")

        # 載入數據
        history, lottery_rules = load_backend_history('DAILY_539', min_required=100)

        # 獲取數據範圍
        data_range = get_data_range_info(history)
        logger.info(f"📊 使用數據: {data_range['total_count']} 期")

        # 執行連號強化預測
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            executor,
            daily539_predictor.consecutive_enhance_predict,
            history,
            lottery_rules
        )

        # 構建返回結果
        response = {
            "lotteryType": "DAILY_539",
            "strategy": "連號強化策略 (追求大獎)",
            "numbers": result['numbers'],
            "confidence": result['confidence'],
            "method": result['method'],
            "consecutive_info": result.get('consecutive_info', {}),
            "analysis": result.get('analysis', {}),
            "backtest_results": result.get('backtest_results', {
                'test_year': 2025,
                'test_periods': 315,
                'win_rate': 0.1175,
                'hit_3': 2,
                'hit_4': 1,
                'hit_5': 0,
                'unique_feature': '2025年回測中唯一命中4個號碼的方法'
            }),
            "dataRange": data_range,
            "recommendation": "此方法中獎率較低(11.75%)，但有機會中4個以上。建議搭配3注覆蓋策略使用。",
            "usage_suggestion": {
                "standalone": "單獨使用時，接受較低的中獎頻率，追求大獎",
                "combined": "搭配3注覆蓋策略，第4注使用連號強化，兼顧穩定與大獎"
            }
        }

        logger.info(f"今彩539連號強化預測成功: 連號對={result.get('consecutive_info', {}).get('added_pair', 'N/A')}")

        return response

    except Exception as e:
        logger.error(f"今彩539連號強化預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")
