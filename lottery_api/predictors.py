import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional
import logging

# Lazy imports for predictors (to avoid circular deps or slow startup)
from models.unified_predictor import prediction_engine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.advanced_auto_learning import AdvancedAutoLearningEngine # NEW

logger = logging.getLogger(__name__)

# ===== 延遲初始化模型（避免啟動時掛起）=====
print(">>> Models will be initialized on first use (lazy loading).")
_prophet_predictor = None
_xgboost_predictor = None
_autogluon_predictor = None
_lstm_predictor = None
_transformer_predictor = None
_bayesian_ensemble_predictor = None
_maml_predictor = None

# Initialize Advanced Engine (Singleton) - ensuring only one instance exists
advanced_engine = AdvancedAutoLearningEngine()

def get_prophet_predictor():
    global _prophet_predictor
    if _prophet_predictor is None:
        try:
            from models.prophet_model import ProphetPredictor
            print(">>> Initializing ProphetPredictor...")
            _prophet_predictor = ProphetPredictor()
            print(">>> ProphetPredictor initialized.")
        except ImportError:
            print(">>> Failed to import ProphetPredictor")
    return _prophet_predictor

def get_xgboost_predictor():
    global _xgboost_predictor
    if _xgboost_predictor is None:
        try:
            from models.xgboost_model import XGBoostPredictor
            print(">>> Initializing XGBoostPredictor...")
            _xgboost_predictor = XGBoostPredictor()
            print(">>> XGBoostPredictor initialized.")
        except ImportError: pass
    return _xgboost_predictor

def get_autogluon_predictor():
    global _autogluon_predictor
    if _autogluon_predictor is None:
        try:
            from models.autogluon_model import AutoGluonPredictor
            print(">>> Initializing AutoGluonPredictor...")
            _autogluon_predictor = AutoGluonPredictor()
            print(">>> AutoGluonPredictor initialized.")
        except ImportError: pass
    return _autogluon_predictor

def get_lstm_predictor():
    global _lstm_predictor
    if _lstm_predictor is None:
        try:
            from models.lstm_model import LSTMPredictor
            print(">>> Initializing LSTMPredictor...")
            _lstm_predictor = LSTMPredictor()
            print(">>> LSTMPredictor initialized.")
        except ImportError: pass
    return _lstm_predictor

def get_transformer_predictor():
    global _transformer_predictor
    if _transformer_predictor is None:
        try:
            from models.transformer_model import TransformerPredictor
            print(">>> Initializing TransformerPredictor...")
            _transformer_predictor = TransformerPredictor()
            print(">>> TransformerPredictor initialized.")
        except ImportError: pass
    return _transformer_predictor

def get_bayesian_ensemble_predictor():
    global _bayesian_ensemble_predictor
    if _bayesian_ensemble_predictor is None:
        try:
            from models.bayesian_ensemble import BayesianEnsemblePredictor
            print(">>> Initializing BayesianEnsemblePredictor...")
            _bayesian_ensemble_predictor = BayesianEnsemblePredictor(prediction_engine)
            print(">>> BayesianEnsemblePredictor initialized.")
        except ImportError: pass
    return _bayesian_ensemble_predictor

def get_maml_predictor():
    global _maml_predictor
    if _maml_predictor is None:
        try:
            from models.meta_learning import MAMLPredictor
            print(">>> Initializing MAMLPredictor...")
            _maml_predictor = MAMLPredictor()
            print(">>> MAMLPredictor initialized.")
        except ImportError: pass
    return _maml_predictor

# ===== 策略分派表 (非深度 AI 部分) =====
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
    "optimized_ensemble": lambda h, r: get_optimized_ensemble_predictor().predict_single(h, r),
    # ===== 高級分析策略 (新增) =====
    "entropy": lambda h, r: prediction_engine.entropy_predict(h, r),
    "entropy_transformer": lambda h, r: prediction_engine.entropy_transformer_predict(h, r),  # 熵驅動 Transformer
    "clustering": lambda h, r: prediction_engine.clustering_predict(h, r),
    "dynamic_ensemble": lambda h, r: prediction_engine.dynamic_ensemble_predict(h, r),
    "temporal": lambda h, r: prediction_engine.temporal_predict(h, r),
    "feature_engineering": lambda h, r: prediction_engine.feature_engineering_predict(h, r),
}

_optimized_ensemble_predictor = None
def get_optimized_ensemble_predictor():
    global _optimized_ensemble_predictor
    if _optimized_ensemble_predictor is None:
        try:
            from models.optimized_ensemble import OptimizedEnsemblePredictor
            print(">>> Initializing OptimizedEnsemblePredictor...")
            _optimized_ensemble_predictor = OptimizedEnsemblePredictor(prediction_engine)
            print(">>> OptimizedEnsemblePredictor initialized.")
        except ImportError: pass
    return _optimized_ensemble_predictor

# ===== 异步深度学习模型（需要特殊处理）=====
ASYNC_MODEL_DISPATCH = {
    "transformer": lambda h, r: get_transformer_predictor().predict(h, r),
    "bayesian_ensemble": lambda h, r: get_bayesian_ensemble_predictor().predict(h, r),
    "maml": lambda h, r: get_maml_predictor().predict(h, r),
}

# ===== Thread Pool for CPU-bound tasks =====
executor = ThreadPoolExecutor(max_workers=4)
print(">>> ThreadPoolExecutor initialized with 4 workers.")
