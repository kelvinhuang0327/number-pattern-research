from pydantic import BaseModel
from typing import List, Dict, Optional, Any

# ===== 基礎數據模型 =====
class DrawData(BaseModel):
    date: str
    draw: str
    numbers: List[int]
    lotteryType: str
    special: Optional[int] = 0  # 特別號（大樂透、威力彩等）

# ===== 預測相關 =====
class PredictRequest(BaseModel):
    history: List[DrawData]
    lotteryRules: Dict
    modelType: str = "prophet"

class PredictFromBackendRequest(BaseModel):
    lotteryType: str
    startDraw: Optional[str] = None  # 🎯 新增：起始期號
    endDraw: Optional[str] = None    # 🎯 新增：結束期號
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
    # Coordinator 可選參數
    coordMode: Optional[str] = "direct"  # direct | hybrid
    coordBets: Optional[int] = 3          # 1~5

class PredictResponse(BaseModel):
    numbers: List[int]
    confidence: float
    method: str
    probabilities: Optional[List[float]] = None
    trend: Optional[str] = None
    seasonality: Optional[str] = None
    modelInfo: Optional[Dict] = None
    notes: Optional[str] = None
    dataRange: Optional[Dict] = None  # 🔧 添加數據範圍信息
    special: Optional[int] = None  # 🔧 添加特別號碼
    # 🔧 雙注預測支持
    bet1: Optional[Dict] = None
    bet2: Optional[Dict] = None
    strategy_weights: Optional[Dict] = None

# ===== 優化與學習相關 =====
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

class StrategyEvaluationRequest(BaseModel):
    lotteryType: str
    test_ratio: float = 0.2  # 測試集比例
    min_train_size: int = 30  # 最小訓練集大小

# ===== 數據管理相關 =====
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
