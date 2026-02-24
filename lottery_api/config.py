import json
import os
import logging
from typing import Dict, Optional, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PlayMode(BaseModel):
    pickCount: int
    matchRequired: int

class LotteryRule(BaseModel):
    name: str
    minNumber: int
    maxNumber: int
    pickCount: int
    hasSpecialNumber: bool = False
    specialMinNumber: Optional[int] = None
    specialMaxNumber: Optional[int] = None
    # 新增欄位
    dependsOn: Optional[str] = None  # 依附的主遊戲ID
    isSubGame: bool = False  # 是否為子遊戲
    playModes: Optional[Dict[str, PlayMode]] = None  # 多玩法配置
    repeatsAllowed: bool = False  # 是否允許重複號碼
    isPermutation: bool = False  # 是否為排列型遊戲
    note: Optional[str] = None  # 備註

class LotteryConfig:
    _instance = None
    _rules: Dict[str, LotteryRule] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LotteryConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "data", "lottery_types.json")
            
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self._rules[key] = LotteryRule(**value)
                logger.info(f"Loaded {len(self._rules)} lottery rules from config.")
            else:
                logger.warning(f"Config file not found at {config_path}")
        except Exception as e:
            logger.error(f"Failed to load lottery config: {e}")
    
    def get_rules(self, lottery_type: str) -> Optional[LotteryRule]:
        return self._rules.get(lottery_type)

    def get_all_types(self) -> Dict[str, LotteryRule]:
        return self._rules
        
    def get_rules_dict(self, lottery_type: str) -> Optional[Dict]:
        rule = self.get_rules(lottery_type)
        return rule.dict() if rule else None

class OptimalPredictionConfig:
    """最佳預測配置管理器"""
    _instance = None
    _configs: Dict[str, Dict] = {}
    _method_mapping: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OptimalPredictionConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """載入最佳預測配置"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "data", "optimal_prediction_config.json")

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._configs = data.get("configs", {})
                    self._method_mapping = data.get("method_mapping", {})
                logger.info(f"Loaded optimal prediction config for {len(self._configs)} lottery types.")
            else:
                logger.warning(f"Optimal prediction config not found at {config_path}")
                self._set_defaults()
        except Exception as e:
            logger.error(f"Failed to load optimal prediction config: {e}")
            self._set_defaults()

    def _set_defaults(self):
        """設置默認配置"""
        self._configs = {
            "POWER_LOTTO": {"optimal_method": "ensemble_predict", "optimal_window": 100},
            "DAILY_539": {"optimal_method": "monte_carlo_predict", "optimal_window": 100},
            "BIG_LOTTO": {"optimal_method": "bayesian_predict", "optimal_window": 300},
        }

    def get_optimal_config(self, lottery_type: str) -> Dict:
        """獲取指定彩票類型的最佳配置"""
        default = {"optimal_method": "ensemble_predict", "optimal_window": 100}
        return self._configs.get(lottery_type, default)

    def get_optimal_method(self, lottery_type: str) -> str:
        """獲取最佳預測方法名稱"""
        config = self.get_optimal_config(lottery_type)
        return config.get("optimal_method", "ensemble_predict")

    def get_optimal_window(self, lottery_type: str) -> int:
        """獲取最佳數據窗口大小"""
        config = self.get_optimal_config(lottery_type)
        return config.get("optimal_window", 100)

    def get_method_description(self, method_name: str) -> str:
        """獲取方法的中文描述"""
        return self._method_mapping.get(method_name, method_name)

    def get_all_configs(self) -> Dict[str, Dict]:
        """獲取所有彩票類型的配置"""
        return self._configs


# Singleton Instances
lottery_config = LotteryConfig()
optimal_prediction_config = OptimalPredictionConfig()
