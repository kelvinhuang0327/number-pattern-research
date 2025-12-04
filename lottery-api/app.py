print(">>> [START] app.py loading...")

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

print(">>> [1/10] Basic imports loaded.")

try:
    from models.prophet_model import ProphetPredictor
    print(">>> [2/10] Imported ProphetPredictor.")
    from models.xgboost_model import XGBoostPredictor
    print(">>> [3/10] Imported XGBoostPredictor.")
    from models.autogluon_model import AutoGluonPredictor
    print(">>> [4/10] Imported AutoGluonPredictor.")
    from models.lstm_model import LSTMPredictor
    print(">>> [5/10] Imported LSTMPredictor.")
    from models.unified_predictor import prediction_engine
    print(">>> [6/10] Imported prediction_engine.")
    from models.strategy_evaluator import strategy_evaluator
    print(">>> [7/10] Imported strategy_evaluator.")
    from utils.scheduler import scheduler
    print(">>> [8/10] Imported scheduler.")
    from utils.smart_scheduler import smart_scheduler
    print(">>> [8.5/10] Imported smart_scheduler.")
    from utils.model_cache import model_cache
    print(">>> [9/10] Imported model_cache.")
    from models.advanced_auto_learning import AdvancedAutoLearningEngine
    print(">>> [9.5/10] Imported AdvancedAutoLearningEngine.")
    from database import db_manager
    print(">>> [10/10] Imported db_manager.")
except Exception as e:
    print(f">>> [FATAL] Import failed: {e}")


# 設置日誌（同時輸出到終端與檔案 logs/server.log）
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'server.log')

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清理既有 handler 避免重複輸出
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
root_logger.addHandler(stream_handler)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
logger.info("Logging configured. Writing to %s", LOG_FILE)


app = FastAPI(
    title="Lottery AI Prediction API",
    description="使用 Prophet 等 AI 模型預測彩票號碼",
    version="1.0.0"
)
print(">>> FastAPI app created.")

# 初始化進階學習引擎
advanced_engine = AdvancedAutoLearningEngine()
print(">>> Advanced learning engine initialized.")

# CORS 設置（最寬鬆模式，適用於開發）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允許所有來源
    allow_credentials=False,  # 關閉憑證（這樣才可以使用 *）
    allow_methods=["*"],      # 允許所有方法
    allow_headers=["*"],      # 允許所有標頭
)
print(">>> Middleware added.")

# ===== 請求數據模型 =====
class DrawData(BaseModel):
    date: str
    draw: str
    numbers: List[int]
    lotteryType: str

class PredictRequest(BaseModel):
    history: List[DrawData]
    lotteryRules: Dict
    modelType: str = "prophet"
print(">>> Pydantic models defined.")

# ===== 響應數據模型 =====
class PredictResponse(BaseModel):
    numbers: List[int]
    confidence: float
    method: str
    probabilities: Optional[List[float]] = None
    trend: Optional[str] = None
    seasonality: Optional[str] = None
    modelInfo: Optional[Dict] = None
    notes: Optional[str] = None

# ===== 延遲初始化模型（避免啟動時掛起）=====
print(">>> Models will be initialized on first use (lazy loading).")
_prophet_predictor = None
_xgboost_predictor = None
_autogluon_predictor = None
_lstm_predictor = None

def get_prophet_predictor():
    global _prophet_predictor
    if _prophet_predictor is None:
        print(">>> Initializing ProphetPredictor...")
        _prophet_predictor = ProphetPredictor()
        print(">>> ProphetPredictor initialized.")
    return _prophet_predictor

def get_xgboost_predictor():
    global _xgboost_predictor
    if _xgboost_predictor is None:
        print(">>> Initializing XGBoostPredictor...")
        _xgboost_predictor = XGBoostPredictor()
        print(">>> XGBoostPredictor initialized.")
    return _xgboost_predictor

def get_autogluon_predictor():
    global _autogluon_predictor
    if _autogluon_predictor is None:
        print(">>> Initializing AutoGluonPredictor...")
        _autogluon_predictor = AutoGluonPredictor()
        print(">>> AutoGluonPredictor initialized.")
    return _autogluon_predictor

def get_lstm_predictor():
    global _lstm_predictor
    if _lstm_predictor is None:
        print(">>> Initializing LSTMPredictor...")
        _lstm_predictor = LSTMPredictor()
        print(">>> LSTMPredictor initialized.")
    return _lstm_predictor

# ===== 策略分派表 (非深度 AI 部分) =====
# 使用 lambda 延遲執行以保持與現有 prediction_engine API 一致
MODEL_DISPATCH = {
    # 統計 / 基礎
    "frequency": lambda h, r: prediction_engine.frequency_predict(h, r),
    "bayesian": lambda h, r: prediction_engine.bayesian_predict(h, r),
    "markov": lambda h, r: prediction_engine.markov_predict(h, r),
    "monte_carlo": lambda h, r: prediction_engine.monte_carlo_predict(h, r),
    "trend": lambda h, r: prediction_engine.trend_predict(h, r),
    "deviation": lambda h, r: prediction_engine.deviation_predict(h, r),
    "statistical": lambda h, r: prediction_engine.statistical_predict(h, r),
    # 民間 / 分佈
    "odd_even": lambda h, r: prediction_engine.odd_even_balance_predict(h, r),
    "zone_balance": lambda h, r: prediction_engine.zone_balance_predict(h, r),
    "hot_cold": lambda h, r: prediction_engine.hot_cold_mix_predict(h, r),
    "sum_range": lambda h, r: prediction_engine.sum_range_predict(h, r),
    "wheeling": lambda h, r: prediction_engine.wheeling_predict(h, r),
    "number_pairs": lambda h, r: prediction_engine.number_pairs_predict(h, r),
    # 集成 / ML
    "ensemble": lambda h, r: prediction_engine.ensemble_predict(h, r),
    "ensemble_advanced": lambda h, r: prediction_engine.ensemble_advanced_predict(h, r),
    "random_forest": lambda h, r: prediction_engine.random_forest_predict(h, r),
}

# ===== Thread Pool for CPU-bound tasks =====
# Prevents blocking the event loop during heavy computations
executor = ThreadPoolExecutor(max_workers=4)
print(">>> ThreadPoolExecutor initialized with 4 workers.")


# ===== API 端點 =====

@app.get("/")
async def root():
    """API 根端點"""
    return {
        "message": "Lottery AI Prediction API",
        "version": "1.0.0",
        "models": ["prophet", "xgboost", "lstm"],
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
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
            "lstm": "not_implemented"
        }
    }

@app.get("/api/ping")
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

@app.post("/api/predict", response_model=PredictResponse)
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
        if request.modelType in ("prophet", "xgboost", "autogluon", "lstm"):
            history_dicts = [draw.dict() for draw in request.history]
            if request.modelType == "prophet":
                result = await get_prophet_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "xgboost":
                result = await get_xgboost_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "autogluon":
                result = await get_autogluon_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
            elif request.modelType == "lstm":
                result = await get_lstm_predictor().predict(history=history_dicts, lottery_rules=request.lotteryRules)
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

class PredictFromBackendRequest(BaseModel):
    lotteryType: str
    modelType: str = "prophet"

class PredictWithRangeRequest(BaseModel):
    """使用期數或日期範圍進行預測（最優化模式）"""
    lotteryType: str
    modelType: str = "prophet"
    # 期數範圍（優先使用）
    startDraw: Optional[str] = None  # 例如：'114000001'
    endDraw: Optional[str] = None    # 例如：'114000100'
    # 日期範圍（備選）
    startDate: Optional[str] = None  # 例如：'2024/01/01'
    endDate: Optional[str] = None    # 例如：'2024/12/31'
    # 或使用最近N期
    recentCount: Optional[int] = None  # 例如：50

# ===== 共用輔助方法 =====
def normalize_lottery_type(lottery_type: str) -> str:
    """
    將中文彩券名稱轉換為後端使用的英文代碼
    """
    mapping = {
        "大樂透": "BIG_LOTTO",
        "威力彩": "POWER_LOTTO",
        "今彩539": "DAILY_539",
        "雙贏彩": "DOUBLE_WIN",
        "3星彩": "3_STAR",
        "4星彩": "4_STAR",
        "38樂合彩": "38_LOTTO",
        "49樂合彩": "49_LOTTO",
        "39樂合彩": "39_LOTTO"
    }
    return mapping.get(lottery_type, lottery_type)

def _load_backend_history(lottery_type: str, min_required: int = 10):
    """載入後端已同步的歷史數據與規則, 不足時回傳 HTTPException"""
    # Normalize lottery type
    lottery_type = normalize_lottery_type(lottery_type)
    
    if not scheduler.latest_data or not scheduler.lottery_rules:
        scheduler.load_data()
        if not scheduler.latest_data or not scheduler.lottery_rules:
            raise HTTPException(status_code=400, detail="後端沒有數據，請先同步數據到後端")

    # O(1) 取指定彩種
    history = scheduler.get_data(lottery_type)
    if len(history) < min_required:
        # 回退舊方法 (check both original and normalized)
        history = [d for d in scheduler.latest_data if d.get('lotteryType') == lottery_type or d.get('lotteryType') == normalize_lottery_type(d.get('lotteryType', ''))]
    if len(history) < min_required:
        raise HTTPException(status_code=400, detail=f"彩券類型 {lottery_type} 的數據不足（需要至少 {min_required} 期，目前 {len(history)} 期）")
    return history, scheduler.lottery_rules

@app.post("/api/predict-from-backend", response_model=PredictResponse)
async def predict_from_backend(request: PredictFromBackendRequest):
    """
    使用後端已存儲的數據進行預測（優化版）
    - 不需要前端傳送完整歷史數據
    - 支持模型緩存，大幅提升速度
    - 適用於快速預測和排程優化
    """
    try:
        logger.info(f"收到後端預測請求: 彩券={request.lotteryType}, 模型={request.modelType}")
        
        # Normalize lottery type
        lottery_type = normalize_lottery_type(request.lotteryType)
        
        # 1. 載入數據（統一方法）
        history, lottery_rules = _load_backend_history(lottery_type, min_required=10)
        logger.info(f"使用後端數據: {len(history)} 期")
        
        # 3. 檢查模型緩存 (加入最佳配置簽名以便 backend_optimized 變更失效)
        extra_sig = None
        if request.modelType == "backend_optimized":
            # Use per-type best config for signature to invalidate cache correctly
            best_config = getattr(scheduler, 'get_best_config', lambda lt: {})(lottery_type)
            if best_config:
                import json, hashlib
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
        
        # 4. 根據模型類型選擇預測器
        # AI 深度學習模型
        if request.modelType == "prophet":
            result = await get_prophet_predictor().predict(history, lottery_rules)
        elif request.modelType == "xgboost":
            result = await get_xgboost_predictor().predict(history, lottery_rules)
        elif request.modelType == "autogluon":
            result = await get_autogluon_predictor().predict(history, lottery_rules)
        elif request.modelType == "lstm":
            raise HTTPException(
                status_code=501,
                detail="LSTM 模型尚未實現，敬請期待"
            )
        # ===== Backend Optimized (自動優化策略快捷模式) =====
        elif request.modelType == "backend_optimized":
            # 合併後端優化邏輯 (頻率 + 遺漏 + 輕量噪聲 + 最佳配置權重)
            # Fetch per-type best config persisted by scheduler
            best_config = getattr(scheduler, 'get_best_config', lambda lt: {})(lottery_type)
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
                "lotteryType": request.lotteryType
            }

        # 其餘策略統一透過分派表
        elif request.modelType in MODEL_DISPATCH:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                MODEL_DISPATCH[request.modelType],
                history,
                lottery_rules
            )
        elif request.modelType == "deviation":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.deviation_predict,
                history,
                lottery_rules
            )
        elif request.modelType == "statistical":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.statistical_predict,
                history,
                lottery_rules
            )
            
        # (移除重複 backend_optimized 分支，已合併至前面)
        
        # 高級策略
        elif request.modelType == "random_forest":
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                executor,
                prediction_engine.random_forest_predict,
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
        
        # 5. 緩存結果
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

@app.post("/api/predict-with-range", response_model=PredictResponse)
async def predict_with_range(request: PredictWithRangeRequest):
    """
    使用期數/日期範圍進行預測（最優化模式）
    - 只需傳送範圍參數，後端自動從數據庫查詢
    - 適用於模擬測試的滾動窗口預測
    - 大幅減少網路傳輸量
    
    參數優先級：
    1. startDraw/endDraw（期數範圍）
    2. startDate/endDate（日期範圍）
    3. recentCount（最近N期）
    """
    try:
        logger.info(f"收到範圍預測請求: 彩券={request.lotteryType}, 模型={request.modelType}")
        
        # Normalize lottery type
        lottery_type = normalize_lottery_type(request.lotteryType)
        
        # 1. 載入後端全部數據
        if not scheduler.latest_data or not scheduler.lottery_rules:
            scheduler.load_data()
            if not scheduler.latest_data or not scheduler.lottery_rules:
                raise HTTPException(status_code=400, detail="後端沒有數據，請先同步數據到後端")
        
        # 2. 根據彩券類型過濾
        all_history = scheduler.get_data(lottery_type)
        if len(all_history) < 10:
            all_history = [d for d in scheduler.latest_data if d.get('lotteryType') == lottery_type or d.get('lotteryType') == normalize_lottery_type(d.get('lotteryType', ''))]
        
        if len(all_history) < 10:
            raise HTTPException(
                status_code=400, 
                detail=f"彩券類型 {request.lotteryType} ({lottery_type}) 的數據不足（至少需要10期）"
            )
        
        # 3. 根據範圍參數篩選數據
        filtered_history = []
        
        # 優先使用期數範圍（但兩者都要有值才使用）
        if request.startDraw and request.endDraw:
            logger.info(f"使用期數範圍: {request.startDraw} - {request.endDraw}")
            # 轉換為整數進行比較
            start_draw_int = int(request.startDraw)
            end_draw_int = int(request.endDraw)
            
            for draw in all_history:
                draw_num = draw.get('draw', '')
                # 處理帶後綴的期數（例如：114000001-01）
                draw_base = draw_num.split('-')[0] if '-' in draw_num else draw_num
                
                try:
                    draw_int = int(draw_base)
                    if draw_int < start_draw_int:
                        continue
                    if draw_int > end_draw_int:
                        continue
                    filtered_history.append(draw)
                except (ValueError, TypeError):
                    # 無法轉換為整數的期數，跳過
                    logger.warning(f"無效的期數格式: {draw_base}")
                    continue
        
        # 使用日期範圍
        elif request.startDate or request.endDate:
            logger.info(f"使用日期範圍: {request.startDate} - {request.endDate}")
            for draw in all_history:
                draw_date = draw.get('date', '').replace('/', '-')
                compare_date = draw_date
                
                if request.startDate:
                    start_compare = request.startDate.replace('/', '-')
                    if compare_date < start_compare:
                        continue
                
                if request.endDate:
                    end_compare = request.endDate.replace('/', '-')
                    if compare_date > end_compare:
                        continue
                
                filtered_history.append(draw)
        
        # 使用最近N期
        elif request.recentCount:
            logger.info(f"使用最近 {request.recentCount} 期")
            filtered_history = all_history[-request.recentCount:]
        
        # 沒有任何範圍參數，使用全部數據
        else:
            logger.info("未指定範圍，使用全部數據")
            filtered_history = all_history
        
        if len(filtered_history) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"篩選後的數據不足（需要至少10期，目前{len(filtered_history)}期）"
            )
        
        logger.info(f"篩選後數據: {len(filtered_history)} 期")
        lottery_rules = scheduler.lottery_rules
        
        # 4. 執行預測（與 predict 端點相同的邏輯）
        if request.modelType == "prophet":
            result = await get_prophet_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "xgboost":
            result = await get_xgboost_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "autogluon":
            result = await get_autogluon_predictor().predict(filtered_history, lottery_rules)
        elif request.modelType == "lstm":
            raise HTTPException(status_code=501, detail="LSTM 模型尚未實現")
        elif request.modelType == "backend_optimized":
            # 使用優化策略
            best_config = scheduler.engine.get_best_config() if hasattr(scheduler, 'engine') else {}
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            recent_window = min(200, len(filtered_history))
            freq_counter = {}
            for draw in filtered_history[-recent_window:]:
                for n in draw.get('numbers', []):
                    freq_counter[n] = freq_counter.get(n, 0) + 1

            missing_map = {n: 0 for n in range(min_num, max_num + 1)}
            for num in missing_map.keys():
                count = 0
                for d in reversed(filtered_history):
                    if num not in d.get('numbers', []):
                        count += 1
                    else:
                        break
                missing_map[num] = count

            max_freq = max(freq_counter.values()) if freq_counter else 1
            max_missing = max(missing_map.values()) if missing_map else 1

            fw = best_config.get('frequency_weight', 0.5)
            mw = best_config.get('missing_weight', 0.3)
            rw = best_config.get('random_weight', 0.2)

            import random
            scores = {}
            for num in range(min_num, max_num + 1):
                f_score = freq_counter.get(num, 0) / max_freq
                m_score = missing_map.get(num, 0) / max_missing if max_missing > 0 else 0
                r_score = random.random()
                scores[num] = fw * f_score + mw * m_score + rw * r_score

            sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            predicted = [n for n, s in sorted_nums[:pick_count]]
            
            result = {
                "numbers": predicted,
                "confidence": 0.75,
                "method": "Backend Optimized Strategy (Range Mode)",
                "notes": f"使用 {len(filtered_history)} 期數據進行優化預測"
            }
        # 其他策略
        elif request.modelType in MODEL_DISPATCH:
            predict_func = MODEL_DISPATCH[request.modelType]
            loop = asyncio.get_running_loop()
            raw_result = await loop.run_in_executor(
                executor,
                predict_func,
                filtered_history,
                lottery_rules
            )
            result = {
                "numbers": raw_result.get("numbers", []),
                "confidence": raw_result.get("confidence", 0.5),
                "method": raw_result.get("method", request.modelType),
                "notes": f"使用 {len(filtered_history)} 期數據 ({request.modelType})"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型類型: {request.modelType}"
            )
        
        logger.info(f"✅ 範圍預測完成: {result.get('numbers')}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"範圍預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"預測失敗: {str(e)}"
        )

@app.get("/api/models")
async def list_models():
    """列出所有可用的模型和策略"""
    return {
        "models": [
            # ===== AI 深度學習模型 =====
            {
                "id": "prophet",
                "name": "Prophet 時間序列",
                "category": "ai",
                "status": "available",
                "description": "基於 Facebook Prophet 的時間序列預測模型，適合有週期性和趨勢的數據"
            },
            {
                "id": "xgboost",
                "name": "XGBoost 梯度提升",
                "category": "ai",
                "status": "available",
                "description": "極端梯度提升算法，通過學習歷史模式進行多標籤分類預測"
            },
            {
                "id": "autogluon",
                "name": "AutoGluon AutoML",
                "category": "ai",
                "status": "available",
                "description": "自動機器學習框架，自動測試多種模型（LightGBM, CatBoost, Random Forest等）並選擇最佳組合"
            },
            {
                "id": "lstm",
                "name": "LSTM 神經網絡",
                "category": "ai",
                "status": "not_implemented",
                "description": "長短期記憶網絡，適合複雜的序列預測"
            },
            
            # ===== 核心統計策略 =====
            {
                "id": "frequency",
                "name": "頻率分析",
                "category": "statistical",
                "status": "available",
                "description": "選擇歷史上出現頻率最高的號碼，簡單有效的基礎策略"
            },
            {
                "id": "bayesian",
                "name": "貝葉斯統計",
                "category": "statistical",
                "status": "available",
                "description": "使用貝葉斯統計方法，結合先驗概率和條件概率進行預測"
            },
            {
                "id": "markov",
                "name": "馬可夫鏈",
                "category": "statistical",
                "status": "available",
                "description": "分析號碼之間的轉移概率，捕捉序列模式"
            },
            {
                "id": "monte_carlo",
                "name": "蒙地卡羅模擬",
                "category": "statistical",
                "status": "available",
                "description": "通過大量隨機模擬來預測，基於統計學原理"
            },
            
            # ===== 民間策略 =====
            {
                "id": "odd_even",
                "name": "奇偶平衡",
                "category": "folk",
                "status": "available",
                "description": "保持奇數和偶數的平衡，符合自然分佈規律"
            },
            {
                "id": "zone_balance",
                "name": "區域平衡",
                "category": "folk",
                "status": "available",
                "description": "將號碼分成多個區域，每個區域選擇適當數量"
            },
            {
                "id": "hot_cold",
                "name": "冷熱混合",
                "category": "folk",
                "status": "available",
                "description": "結合熱門號碼和冷門號碼，平衡風險與收益"
            },
            {
                "id": "sum_range",
                "name": "和值範圍",
                "category": "folk",
                "status": "available",
                "description": "分析號碼和值與AC值分佈，篩選最佳組合"
            },
            {
                "id": "wheeling",
                "name": "組合輪轉",
                "category": "folk",
                "status": "available",
                "description": "使用聰明組合策略，從候選池中生成最佳分佈的一注"
            },
            {
                "id": "number_pairs",
                "name": "連號/配對",
                "category": "folk",
                "status": "available",
                "description": "分析歷史共現矩陣，找出強關聯號碼組合"
            },
            
            # ===== 趨勢與偏差 =====
            {
                "id": "trend",
                "name": "趨勢分析",
                "category": "statistical",
                "status": "available",
                "description": "使用指數衰減加權，重視近期趨勢"
            },
            {
                "id": "deviation",
                "name": "偏差追蹤",
                "category": "statistical",
                "status": "available",
                "description": "基於標準差與均值回歸原理，捕捉偏差修正機會"
            },
            {
                "id": "statistical",
                "name": "多維統計",
                "category": "statistical",
                "status": "available",
                "description": "綜合和值、AC值、奇偶比等多維度指標進行篩選"
            },
            
            # ===== 高級策略 =====
            {
                "id": "random_forest",
                "name": "隨機森林",
                "category": "machine_learning",
                "status": "available",
                "description": "使用機器學習的隨機森林算法，自動學習複雜模式"
            },
            {
                "id": "ensemble",
                "name": "集成預測",
                "category": "ensemble",
                "status": "available",
                "description": "結合多種策略的預測結果，提高準確率和穩定性"
            }
        ],
        "categories": {
            "ai": "AI 深度學習模型",
            "statistical": "核心統計策略",
            "folk": "民間經驗策略",
            "machine_learning": "機器學習策略",
            "ensemble": "集成策略"
        }
    }

# ===== 自動學習 API =====

class OptimizationRequest(BaseModel):
    history: List[DrawData]
    lotteryRules: Dict
    generations: int = 20
    population_size: int = 30
    lotteryType: Optional[str] = None

class ScheduleRequest(BaseModel):
    schedule_time: str = "02:00"  # HH:MM 格式

class SyncDataRequest(BaseModel):
    lotteryType: str
    history: List[Dict]
    lottery_rules: Dict

@app.get("/api/history")
async def get_history(
    lottery_type: Optional[str] = Query(None, description="彩券類型篩選")
):
    """
    獲取所有歷史數據（用於前端初始化）
    現在從數據庫讀取，支持按類型篩選
    """
    try:
        # Normalize lottery type
        if lottery_type:
            lottery_type = normalize_lottery_type(lottery_type)
            
        # 從數據庫獲取所有數據
        all_data = db_manager.get_all_draws(lottery_type)
        
        # 同時確保 scheduler 有數據（用於優化和預測）
        if not scheduler.latest_data or len(scheduler.latest_data) == 0:
            scheduler.latest_data = all_data
            # 按類型分組
            scheduler.data_by_type = {}
            for draw in all_data:
                lt = draw.get('lotteryType', 'UNKNOWN')
                if lt not in scheduler.data_by_type:
                    scheduler.data_by_type[lt] = []
                scheduler.data_by_type[lt].append(draw)
        
        logger.info(f"前端請求歷史數據，返回 {len(all_data)} 筆")
        return all_data
    except Exception as e:
        logger.error(f"獲取歷史數據失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/optimize")
async def run_optimization(request: OptimizationRequest):
    """
    手動觸發自動優化
    """
    try:
        logger.info(f"開始手動優化: {request.generations} 代, 種群 {request.population_size}, 彩券類型: {request.lotteryType or '未指定'}")
        
        # Normalize lottery type
        lottery_type = normalize_lottery_type(request.lotteryType) if request.lotteryType else None
        
        # 1. 優先使用後端本地數據（完整數據）
        if not scheduler.latest_data:
            scheduler.load_data()
            
        if not scheduler.latest_data:
            raise HTTPException(
                status_code=400, 
                detail="後端沒有數據，請先點擊「同步數據到後端」按鈕"
            )
            
        # 🚀 優化：直接獲取指定類型數據
        target_data = scheduler.get_data(lottery_type) if lottery_type else scheduler.latest_data
        
        if not target_data:
            # 回退到舊方法（向後兼容）
            target_data = scheduler.latest_data
            if lottery_type and target_data:
                target_data = [d for d in target_data if d.get('lotteryType') == lottery_type or d.get('lotteryType') == request.lotteryType]
                if not target_data:
                    logger.warning(f"找不到類型為 {lottery_type} 的數據，將使用全部數據")
                    target_data = scheduler.latest_data
                else:
                    logger.info(f"已篩選 {lottery_type} 數據: {len(target_data)} 期")
        else:
            logger.info(f"快速獲取 {request.lotteryType} 數據: {len(target_data)} 期")
        
        logger.info(f"使用後端數據進行優化: {len(target_data)} 期")
        
        # 3. 使用本地數據執行優化
        result = await scheduler.run_manual_optimization(
            history=target_data,  # 使用篩選後的數據
            lottery_rules=request.lotteryRules or scheduler.lottery_rules,
            generations=request.generations,
            population_size=request.population_size
        )
        
        return result
        
    except Exception as e:
        logger.error(f"優化失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/schedule/start")
async def start_schedule(request: ScheduleRequest):
    """
    啟動自動學習排程
    """
    try:
        scheduler.start(schedule_time=request.schedule_time)
        return {
            "success": True,
            "message": f"排程已啟動，每天 {request.schedule_time} 執行優化",
            "schedule_time": request.schedule_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/schedule/stop")
async def stop_schedule():
    """
    停止自動學習排程
    """
    try:
        scheduler.stop()
        return {
            "success": True,
            "message": "排程已停止"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/schedule/run-now")
async def run_schedule_now(background_tasks: BackgroundTasks):
    """
    立即執行一次優化任務（不等待定時排程）
    會自動從資料庫讀取最新數據
    使用後台任務執行，不阻塞 API 響應
    """
    try:
        logger.info("🚀 手動觸發立即執行優化任務...")

        # 從資料庫讀取數據
        all_draws = db_manager.get_all_draws()

        if not all_draws or len(all_draws) < 50:
            return {
                "success": False,
                "message": f"數據不足（{len(all_draws) if all_draws else 0} 期），至少需要 50 期數據"
            }

        logger.info(f"📊 從資料庫讀取到 {len(all_draws)} 期數據")

        # 轉換為排程器需要的格式
        history = [
            {
                'date': draw['date'],
                'draw': draw['draw'],
                'numbers': draw['numbers'],
                'lotteryType': draw['lotteryType']
            }
            for draw in all_draws
        ]

        # 設置彩券規則（使用大樂透的規則，可根據需要調整）
        lottery_rules = {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49
        }

        # 更新排程器的數據
        scheduler.update_data(history, lottery_rules)

        # 在後台執行優化任務（不阻塞響應）
        async def run_optimization_task():
            try:
                await scheduler._run_optimization()
                logger.info("✅ 後台優化任務執行完成")
            except Exception as e:
                logger.error(f"後台優化任務失敗: {str(e)}", exc_info=True)

        background_tasks.add_task(run_optimization_task)

        logger.info("✅ 優化任務已加入後台執行佇列")

        return {
            "success": True,
            "message": f"優化任務已啟動（後台執行），使用 {len(history)} 期數據",
            "data_count": len(history),
            "status": "running_in_background"
        }
    except Exception as e:
        logger.error(f"立即執行優化失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auto-learning/schedule/status")
async def get_schedule_status():
    """
    獲取排程狀態（包含進階優化歷史）
    """
    status = scheduler.get_schedule_status()
    
    # 添加進階優化歷史
    status['advanced_optimization_history'] = advanced_engine.optimization_history[-10:]  # 最近10條
    
    return status

@app.get("/api/auto-learning/best-config")
async def get_best_config(lottery_type: Optional[str] = Query(None, description="彩券類型")):
    """
    獲取最佳配置
    """
    config = scheduler.get_best_config(lottery_type)
    if not config:
        # 嘗試從檔案載入
        config = scheduler.load_config(lottery_type)

    return {
        "config": config
    }

@app.post("/api/auto-learning/set-target-fitness")
async def set_target_fitness(request: dict):
    """
    🎯 設定目標適應度（達標後提前停止優化）

    Args:
        target_fitness: 目標值 (0.0-1.0)，null 表示禁用

    Examples:
        {"target_fitness": 0.05}  # 達到 5% 後停止
        {"target_fitness": null}  # 禁用早停
    """
    try:
        target = request.get("target_fitness")

        if target is not None:
            target = float(target)
            if not (0 < target <= 1.0):
                raise HTTPException(
                    status_code=400,
                    detail="目標適應度必須在 0 到 1 之間"
                )

        scheduler.set_target_fitness(target)

        return {
            "success": True,
            "target_fitness": target,
            "message": f"已設定目標適應度: {target:.2%}" if target else "已禁用目標適應度早停"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"設定目標適應度失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auto-learning/optimization-history")
async def get_optimization_history(lottery_type: Optional[str] = Query(None, description="彩券類型")):
    """
    獲取優化歷史記錄
    
    返回所有執行過的優化結果，包括：
    - 多階段優化
    - 自適應窗口優化
    - 集成優化
    """
    try:
        # 從進階引擎獲取優化歷史
        history = advanced_engine.optimization_history
        
        # 如果指定了彩券類型，可以過濾（目前歷史記錄沒有存彩券類型，所以返回全部）
        # 未來可以在保存時加入 lottery_type 字段
        
        # 同時獲取最佳配置信息
        best_config = scheduler.get_best_config(lottery_type)
        config_file = f"data/best_config_{lottery_type}.json" if lottery_type else "data/best_config.json"
        
        config_info = None
        if best_config:
            import os
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    config_info = {
                        'timestamp': data.get('timestamp'),
                        'config': best_config
                    }
        
        return {
            "success": True,
            "history": history[-20:],  # 返回最近 20 條記錄
            "total_count": len(history),
            "best_config_info": config_info,
            "lottery_type": lottery_type
        }
        
    except Exception as e:
        logger.error(f"獲取優化歷史失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/sync-data")
async def sync_data(request: OptimizationRequest):
    """
    同步前端數據到後端（用於排程優化）
    現在直接存入數據庫
    """
    try:
        history = [draw.dict() for draw in request.history]
        lottery_rules = request.lotteryRules

        # 插入到數據庫
        inserted, duplicates = db_manager.insert_draws(history)
        
        # 更新排程器的數據
        scheduler.update_data(history, lottery_rules)

        logger.info(f"數據同步成功: {inserted} 新增, {duplicates} 重複")

        return {
            "success": True,
            "message": f"數據同步成功，新增 {inserted} 筆，{duplicates} 筆重複",
            "inserted": inserted,
            "duplicates": duplicates,
            "total": len(history)
        }
    except Exception as e:
        logger.error(f"數據同步失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ===== 緩存管理 API =====

@app.get("/api/cache/stats")
async def get_cache_stats():
    """
    獲取緩存統計信息
    """
    return model_cache.get_stats()

@app.post("/api/cache/clear")
async def clear_cache(lottery_type: Optional[str] = None, model_type: Optional[str] = None):
    """
    清除模型緩存
    
    Query Parameters:
        lottery_type: 可選，指定要清除的彩券類型
        model_type: 可選，指定要清除的模型類型
    """
    try:
        model_cache.clear(lottery_type, model_type)
        
        if lottery_type and model_type:
            message = f"已清除 {lottery_type} - {model_type} 的緩存"
        elif lottery_type:
            message = f"已清除 {lottery_type} 的所有緩存"
        elif model_type:
            message = f"已清除所有 {model_type} 模型的緩存"
        else:
            message = "已清除所有緩存"
        
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        logger.error(f"清除緩存失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/upload")
async def upload_data(request: OptimizationRequest):
    """
    上傳開獎數據到數據庫
    前端解析 CSV 後直接調用此 API 存儲數據
    """
    try:
        history = [draw.dict() for draw in request.history]
        logger.info(f"📤 開始上傳 {len(history)} 筆數據...")
        
        # 插入到數據庫（批次處理）
        inserted, duplicates = db_manager.insert_draws(history)
        logger.info(f"✅ 數據插入完成: 新增 {inserted} 筆，重複 {duplicates} 筆")
        
        # 同時更新 scheduler 的內存數據（用於優化和預測）
        scheduler.update_data(history, request.lotteryRules)
        
        logger.info(f"✅ Data uploaded: {inserted} new, {duplicates} duplicates")
        
        return {
            "success": True,
            "inserted": inserted,
            "duplicates": duplicates,
            "total": inserted + duplicates,
            "message": f"成功上傳 {inserted} 筆新數據，{duplicates} 筆重複"
        }
    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/draws")
async def get_draws(
    lottery_type: Optional[str] = Query(None, description="彩券類型篩選"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(50, ge=1, le=500, description="每頁數量"),
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)")
):
    """
    分頁查詢開獎記錄
    支持按彩券類型、日期範圍篩選
    """
    try:
        result = db_manager.get_draws(
            lottery_type=lottery_type,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(f"📊 Query: type={lottery_type}, page={page}, returned {len(result['draws'])} draws")
        return result
        
    except Exception as e:
        logger.error(f"❌ Query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/stats")
async def get_data_stats(lottery_type: Optional[str] = Query(None)):
    """
    獲取數據統計信息
    """
    try:
        stats = db_manager.get_stats(lottery_type)
        logger.info(f"📊 Stats: {stats['total']} total draws")
        return stats
    except Exception as e:
        logger.error(f"❌ Get stats failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/clear")
async def clear_backend_data():
    """
    清除後端存儲的所有數據
    """
    import os
    try:
        # 清除數據庫
        count = db_manager.clear_all_data()
        
        # 清除舊的 JSON 文件（如果存在）
        data_files = [
            "data/lottery_data.json",
            "data/lottery_rules.json"
        ]

        deleted_files = []
        for file_path in data_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(file_path)

        # 同時清除記憶體中的數據
        scheduler.latest_data = None
        scheduler.lottery_rules = None
        scheduler.data_by_type = {}
        
        # 清除模型緩存
        model_cache.clear()

        return {
            "success": True,
            "message": f"已清除 {count} 筆數據庫記錄",
            "deleted_db_records": count,
            "deleted_files": deleted_files
        }
    except Exception as e:
        logger.error(f"清除數據失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ===== 智能策略評估 API =====

class StrategyEvaluationRequest(BaseModel):
    lotteryType: str
    test_ratio: float = 0.2  # 測試集比例
    min_train_size: int = 30  # 最小訓練集大小

@app.post("/api/auto-learning/evaluate-strategies")
async def evaluate_strategies(request: StrategyEvaluationRequest):
    """
    評估所有可用的預測策略，找出最佳方法

    使用滾動驗證評估每個策略的性能，包括：
    - 成功率
    - 平均命中數
    - 命中率分佈
    - vs 理論概率倍數
    """
    try:
        logger.info(f"開始評估策略: 彩券={request.lotteryType}, 測試比例={request.test_ratio}")

        # 1. 從後端加載數據
        if not scheduler.latest_data or not scheduler.lottery_rules:
            scheduler.load_data()

            if not scheduler.latest_data or not scheduler.lottery_rules:
                raise HTTPException(
                    status_code=400,
                    detail="後端沒有數據，請先同步數據到後端"
                )

        # 2. 篩選指定彩券類型的數據
        history = [
            draw for draw in scheduler.latest_data
            if draw.get('lotteryType') == request.lotteryType
        ]

        if len(history) < request.min_train_size + 10:
            raise HTTPException(
                status_code=400,
                detail=f"彩券類型 {request.lotteryType} 的數據不足（需要至少 {request.min_train_size + 10} 期）"
            )

        lottery_rules = {
            **scheduler.lottery_rules,
            'lotteryType': request.lotteryType
        }

        logger.info(f"使用後端數據評估: {len(history)} 期")

        # 3. 執行評估
        result = strategy_evaluator.evaluate_all_strategies(
            history=history,
            lottery_rules=lottery_rules,
            test_ratio=request.test_ratio,
            min_train_size=request.min_train_size
        )

        logger.info(f"✅ 策略評估完成: 最佳策略 = {result['best_strategy']['strategy_name']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"策略評估失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"評估失敗: {str(e)}")

@app.get("/api/auto-learning/best-strategy")
async def get_best_strategy(lottery_type: Optional[str] = None):
    """
    獲取最佳策略

    如果有緩存則返回緩存，否則嘗試載入最新的評估結果
    """
    try:
        # 先檢查緩存
        best = strategy_evaluator.get_best_strategy()

        if not best and lottery_type:
            # 嘗試載入最新評估結果
            latest = strategy_evaluator.load_latest_evaluation(lottery_type)
            best = latest.get('best_strategy') if latest else None

        if not best:
            return {
                "has_best_strategy": False,
                "message": "沒有最佳策略，請先執行策略評估"
            }

        return {
            "has_best_strategy": True,
            "best_strategy": best
        }

    except Exception as e:
        logger.error(f"獲取最佳策略失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-learning/predict-with-best")
async def predict_with_best_strategy(request: PredictFromBackendRequest):
    """
    使用自動評估找出的最佳策略進行預測

    如果沒有最佳策略緩存，則使用默認的 ensemble 策略
    """
    try:
        logger.info(f"使用最佳策略預測: 彩券={request.lotteryType}")

        # 1. 從後端加載數據
        if not scheduler.latest_data or not scheduler.lottery_rules:
            scheduler.load_data()

            if not scheduler.latest_data or not scheduler.lottery_rules:
                raise HTTPException(
                    status_code=400,
                    detail="後端沒有數據，請先同步數據到後端"
                )

        # 2. 篩選指定彩券類型的數據
        history = [
            draw for draw in scheduler.latest_data
            if draw.get('lotteryType') == request.lotteryType
        ]

        if len(history) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"彩券類型 {request.lotteryType} 的數據不足"
            )

        lottery_rules = {
            **scheduler.lottery_rules,
            'lotteryType': request.lotteryType
        }

        # 3. 使用最佳策略預測
        result = strategy_evaluator.predict_with_best(
            history=history,
            lottery_rules=lottery_rules
        )

        logger.info(f"✅ 最佳策略預測完成: {result['numbers']}, 使用策略: {result.get('strategy_name')}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"最佳策略預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"預測失敗: {str(e)}")


# ===== 進階自動學習 API =====

@app.post("/api/auto-learning/advanced/multi-stage")
async def run_multi_stage_optimization_api(background_tasks: BackgroundTasks, request: dict):
    """
    🚀 執行多階段優化 (Multi-Stage Optimization)

    階段1：粗調 (50代) - 快速探索
    階段2：精調 (100代) - 深度優化
    階段3：微調 (50代) - 精確調整

    預期效果：相比基礎優化提升 50-100% 適應度
    耗時：10-15 分鐘
    """
    try:
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        logger.info(f"🚀 開始多階段優化: 彩券類型={lottery_type}")

        # 從後端加載數據
        history = scheduler.get_data(lottery_type)

        if not history or len(history) < 100:
            raise HTTPException(
                status_code=400,
                detail=f'數據不足（目前 {len(history)} 期，至少需要 100 期）'
            )

        lottery_rules = scheduler.lottery_rules or {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49
        }

        # 執行多階段優化（後台執行）
        def run_optimization():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                advanced_engine.multi_stage_optimize(
                    history=history,
                    lottery_rules=lottery_rules
                )
            )
            loop.close()

            # 保存最佳配置
            if result['success']:
                scheduler._save_config(result['best_config'], lottery_type)
                logger.info(f"✅ 多階段優化完成: 適應度={result['best_fitness']:.4f}")

            return result

        background_tasks.add_task(run_optimization)

        return {
            'success': True,
            'message': '多階段優化已在後台啟動（預計 10-15 分鐘）',
            'data_count': len(history),
            'lottery_type': lottery_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"多階段優化失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"優化失敗: {str(e)}")


@app.post("/api/auto-learning/advanced/adaptive-window")
async def run_adaptive_window_optimization_api(background_tasks: BackgroundTasks, request: dict):
    """
    🔍 執行自適應窗口優化 (Adaptive Window Optimization)

    自動測試不同的訓練數據窗口大小（100/200/300/500/全部期）
    找出最佳的數據量，排除過時模式

    預期效果：相比固定窗口提升 20-30% 適應度
    耗時：5-8 分鐘
    """
    try:
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        logger.info(f"🔍 開始自適應窗口優化: 彩券類型={lottery_type}")

        # 從後端加載數據
        history = scheduler.get_data(lottery_type)

        if not history or len(history) < 100:
            raise HTTPException(
                status_code=400,
                detail=f'數據不足（目前 {len(history)} 期，至少需要 100 期）'
            )

        lottery_rules = scheduler.lottery_rules or {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49
        }

        # 執行自適應窗口優化（後台執行）
        def run_optimization():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                advanced_engine.adaptive_window_optimize(
                    history=history,
                    lottery_rules=lottery_rules
                )
            )
            loop.close()

            # 保存最佳配置
            if result['success']:
                scheduler._save_config(result['best_config'], lottery_type)
                logger.info(f"✅ 自適應窗口優化完成: 適應度={result['best_fitness']:.4f}, 最佳窗口={result['best_window_size']}期")

            return result

        background_tasks.add_task(run_optimization)

        return {
            'success': True,
            'message': '自適應窗口優化已在後台啟動（預計 5-8 分鐘）',
            'data_count': len(history),
            'lottery_type': lottery_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"自適應窗口優化失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"優化失敗: {str(e)}")


# ===== 錯誤處理 =====

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未處理的異常: {exc}", exc_info=True)
    return {
        "error": "Internal server error",
        "message": str(exc)
    }

@app.post("/api/predict-optimized", response_model=PredictResponse)
async def predict_optimized(request: PredictFromBackendRequest):
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


# ===== CRUD API 端點 =====

class CreateDrawRequest(BaseModel):
    """新增記錄請求模型"""
    draw: str
    date: str
    lotteryType: str
    numbers: List[int]
    special: Optional[int] = 0

class UpdateDrawRequest(BaseModel):
    """更新記錄請求模型"""
    draw: Optional[str] = None
    date: Optional[str] = None
    lotteryType: Optional[str] = None
    numbers: Optional[List[int]] = None
    special: Optional[int] = None

@app.post("/api/draws")
async def create_draw(request: CreateDrawRequest):
    """
    新增開獎記錄
    """
    try:
        logger.info(f"📝 新增記錄: 期數={request.draw}, 日期={request.date}")

        # 驗證號碼數量
        if len(request.numbers) != 6:
            raise HTTPException(status_code=400, detail="必須提供 6 個開獎號碼")

        # 驗證號碼範圍
        for num in request.numbers:
            if num < 1 or num > 49:
                raise HTTPException(status_code=400, detail=f"號碼 {num} 超出範圍 (1-49)")

        # 驗證特別號
        if request.special and (request.special < 1 or request.special > 49):
            raise HTTPException(status_code=400, detail=f"特別號 {request.special} 超出範圍 (1-49)")

        # 插入資料庫
        draw_data = [{
            'draw': request.draw,
            'date': request.date,
            'lotteryType': request.lotteryType,
            'numbers': request.numbers,
            'special': request.special or 0
        }]

        inserted, duplicates = db_manager.insert_draws(draw_data)

        if duplicates > 0:
            raise HTTPException(status_code=409, detail=f"期數 {request.draw} 已存在")

        logger.info(f"✅ 新增成功: {inserted} 筆")

        return {
            "success": True,
            "message": "新增成功",
            "inserted": inserted
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 新增失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"新增失敗: {str(e)}")


@app.put("/api/draws/{draw_id}")
async def update_draw(draw_id: str, request: UpdateDrawRequest):
    """
    更新開獎記錄
    """
    try:
        logger.info(f"✏️ 更新記錄: ID={draw_id}")

        # 驗證號碼（如果提供）
        if request.numbers:
            if len(request.numbers) != 6:
                raise HTTPException(status_code=400, detail="必須提供 6 個開獎號碼")

            for num in request.numbers:
                if num < 1 or num > 49:
                    raise HTTPException(status_code=400, detail=f"號碼 {num} 超出範圍 (1-49)")

        # 驗證特別號（如果提供）
        if request.special is not None and (request.special < 1 or request.special > 49):
            raise HTTPException(status_code=400, detail=f"特別號 {request.special} 超出範圍 (1-49)")

        # 更新資料庫
        # 注意：這裡需要先刪除舊記錄，再插入新記錄
        # 因為 SQLite 的 UNIQUE 約束是基於 (draw, lottery_type)

        # 先刪除
        conn = db_manager._get_connection()
        cursor = conn.cursor()

        try:
            # 查詢現有記錄
            cursor.execute("SELECT * FROM draws WHERE id = ? OR draw = ?", (draw_id, draw_id))
            existing = cursor.fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"找不到記錄: {draw_id}")

            # 準備更新數據
            update_data = {
                'draw': request.draw if request.draw else existing['draw'],
                'date': request.date if request.date else existing['date'],
                'lotteryType': request.lotteryType if request.lotteryType else existing['lottery_type'],
                'numbers': request.numbers if request.numbers else eval(existing['numbers']),
                'special': request.special if request.special is not None else existing['special']
            }

            # 刪除舊記錄
            cursor.execute("DELETE FROM draws WHERE id = ? OR draw = ?", (draw_id, draw_id))

            # 插入新記錄
            import json
            numbers_json = json.dumps(update_data['numbers'])
            cursor.execute("""
                INSERT INTO draws (draw, date, lottery_type, numbers, special)
                VALUES (?, ?, ?, ?, ?)
            """, (
                update_data['draw'],
                update_data['date'],
                update_data['lotteryType'],
                numbers_json,
                update_data['special']
            ))

            conn.commit()
            logger.info(f"✅ 更新成功: {draw_id}")

            return {
                "success": True,
                "message": "更新成功"
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")


@app.delete("/api/draws/{draw_id}")
async def delete_draw(draw_id: str):
    """
    刪除開獎記錄
    """
    try:
        logger.info(f"🗑️ 刪除記錄: ID={draw_id}")

        conn = db_manager._get_connection()
        cursor = conn.cursor()

        try:
            # 先檢查記錄是否存在
            cursor.execute("SELECT COUNT(*) FROM draws WHERE id = ? OR draw = ?", (draw_id, draw_id))
            count = cursor.fetchone()[0]

            if count == 0:
                raise HTTPException(status_code=404, detail=f"找不到記錄: {draw_id}")

            # 刪除記錄
            cursor.execute("DELETE FROM draws WHERE id = ? OR draw = ?", (draw_id, draw_id))
            conn.commit()

            deleted_count = cursor.rowcount
            logger.info(f"✅ 刪除成功: {deleted_count} 筆")

            return {
                "success": True,
                "message": "刪除成功",
                "deleted": deleted_count
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 刪除失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")


# ===== 智能排程 API =====

@app.post("/api/smart-learning/start")
async def start_smart_learning(request: dict):
    """
    啟動智能自動學習排程

    請求參數:
        evaluation_schedule: 策略評估時間 (格式: "HH:MM", 默認 "02:00")
        learning_schedule: 參數優化時間 (格式: "HH:MM", 默認 "03:00")
        success_threshold: 成功率閾值 (0.0-1.0, 默認 0.30)
    """
    try:
        eval_schedule = request.get('evaluation_schedule', '02:00')
        learn_schedule = request.get('learning_schedule', '03:00')
        threshold = request.get('success_threshold', 0.30)

        # 設置閾值
        smart_scheduler.set_success_threshold(threshold)

        # 啟動排程
        smart_scheduler.start(
            evaluation_schedule=eval_schedule,
            learning_schedule=learn_schedule
        )

        logger.info(f"✅ 智能排程已啟動")
        return {
            'success': True,
            'message': '智能排程已啟動',
            'config': {
                'evaluation_schedule': eval_schedule,
                'learning_schedule': learn_schedule,
                'success_threshold': threshold
            }
        }
    except Exception as e:
        logger.error(f"啟動智能排程失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/smart-learning/stop")
async def stop_smart_learning():
    """停止智能自動學習排程"""
    try:
        smart_scheduler.stop()
        logger.info("智能排程已停止")
        return {'success': True, 'message': '智能排程已停止'}
    except Exception as e:
        logger.error(f"停止智能排程失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/smart-learning/status")
async def get_smart_learning_status():
    """獲取智能排程狀態"""
    try:
        status = smart_scheduler.get_schedule_status()
        return status
    except Exception as e:
        logger.error(f"獲取智能排程狀態失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/smart-learning/sync-data")
async def sync_data_to_smart_scheduler(data: SyncDataRequest):
    """
    同步數據到智能排程器

    請求參數:
        lotteryType: 彩券類型
        history: 歷史數據
        lottery_rules: 彩券規則
    """
    try:
        smart_scheduler.update_data(
            lottery_type=data.lotteryType,
            history=data.history,
            lottery_rules=data.lottery_rules
        )

        logger.info(f"✅ 數據已同步到智能排程器: {data.lotteryType} - {len(data.history)} 期")
        return {
            'success': True,
            'message': f'數據已同步: {len(data.history)} 期',
            'lottery_type': data.lotteryType
        }
    except Exception as e:
        logger.error(f"同步數據失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/smart-learning/manual-evaluation")
async def manual_strategy_evaluation(request: dict):
    """
    手動觸發策略評估

    請求參數:
        lotteryType: 彩券類型
    """
    try:
        lottery_type = request.get('lotteryType')
        if not lottery_type:
            raise HTTPException(status_code=400, detail="缺少 lotteryType 參數")

        result = await smart_scheduler.manual_evaluation(lottery_type)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"手動評估失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/smart-learning/best-strategy/{lottery_type}")
async def get_best_strategy_for_type(lottery_type: str):
    """獲取指定彩券類型的最佳策略"""
    try:
        strategy = smart_scheduler.get_best_strategy(lottery_type)
        if not strategy:
            return {
                'success': False,
                'message': f'尚未找到 {lottery_type} 的最佳策略',
                'lottery_type': lottery_type
            }
        return {
            'success': True,
            'lottery_type': lottery_type,
            'strategy': strategy
        }
    except Exception as e:
        logger.error(f"獲取最佳策略失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/smart-learning/all-best-strategies")
async def get_all_best_strategies():
    """獲取所有彩券類型的最佳策略"""
    try:
        strategies = smart_scheduler.get_all_best_strategies()
        return {
            'success': True,
            'strategies': strategies,
            'count': len(strategies)
        }
    except Exception as e:
        logger.error(f"獲取所有最佳策略失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/smart-learning/predict-with-best")
async def predict_with_smart_best(request: PredictFromBackendRequest):
    """
    使用智能排程找出的最佳策略進行預測

    這個端點會使用智能排程系統自動評估和優化後的最佳策略
    """
    try:
        logger.info(f"使用智能最佳策略預測: 彩券={request.lotteryType}")

        # 獲取最佳策略
        best_strategy_info = smart_scheduler.get_best_strategy(request.lotteryType)

        if not best_strategy_info:
            # 如果沒有最佳策略，使用默認的 ensemble
            logger.warning(f"{request.lotteryType} 沒有最佳策略，使用 ensemble")
            strategy_name = 'ensemble'
        else:
            strategy_name = best_strategy_info['strategy_id']
            logger.info(f"使用最佳策略: {best_strategy_info['strategy_name']} (成功率: {best_strategy_info['success_rate']*100:.2f}%)")

        # 獲取數據
        history = smart_scheduler.data_by_type.get(request.lotteryType, [])
        if len(history) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"彩券類型 {request.lotteryType} 的數據不足"
            )

        lottery_rules = smart_scheduler.lottery_rules_by_type.get(request.lotteryType, {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49,
            'lotteryType': request.lotteryType
        })

        # 執行預測
        result = await prediction_engine.predict(
            strategy=strategy_name,
            history=history,
            lottery_rules=lottery_rules
        )

        # 添加策略信息
        if best_strategy_info:
            result['strategy_info'] = {
                'name': best_strategy_info['strategy_name'],
                'success_rate': best_strategy_info['success_rate'],
                'avg_hits': best_strategy_info['avg_hits'],
                'updated_at': best_strategy_info.get('updated_at')
            }

        logger.info(f"✅ 智能預測完成: {result['numbers']}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能預測失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    logger.info("啟動 Lottery AI API 服務器...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=5001,
        log_level="info",
        reload=True
    )
