"""
Configuration Loader for Lottery Prediction System
Loads and provides access to prediction configuration
"""
import os
import yaml
from typing import Dict, Any

class PredictionConfig:
    """Singleton configuration manager"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: str = None):
        """Load configuration from YAML file"""
        if config_path is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config', 'prediction_config.yaml')
        
        if not os.path.exists(config_path):
            # Use default configuration
            self._config = self._get_default_config()
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file doesn't exist"""
        return {
            'consecutive_filter': {
                'enabled': True,
                'use_gradual_penalties': True,
                'penalties': {
                    'two_consecutive': 0.7,
                    'three_consecutive': 0.4,
                    'four_plus_consecutive': 0.1
                },
                'hard_penalty_three_consecutive': 300
            },
            'strategy_weights': {
                'frequency': 1.5,
                'trend': 1.5,
                'bayesian': 1.2,
                'markov': 1.0,
                'deviation': 1.0,
                'gap_analysis': 1.2,
                'gap_hunter': 1.2,
                'cold_comeback': 1.1
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_consecutive_penalty(self, consecutive_count: int) -> float:
        """Get penalty multiplier for consecutive numbers"""
        if not self.get('consecutive_filter.use_gradual_penalties', True):
            # Use old hard penalty system
            if consecutive_count >= 3:
                return self.get('consecutive_filter.hard_penalty_three_consecutive', 300)
            return 0
        
        # Use gradual penalty system
        penalties = self.get('consecutive_filter.penalties', {})
        
        if consecutive_count == 2:
            return penalties.get('two_consecutive', 0.7)
        elif consecutive_count == 3:
            return penalties.get('three_consecutive', 0.4)
        elif consecutive_count >= 4:
            return penalties.get('four_plus_consecutive', 0.1)
        
        return 1.0  # No penalty
    
    def get_strategy_weight(self, strategy_name: str) -> float:
        """Get weight for a specific strategy"""
        return self.get(f'strategy_weights.{strategy_name}', 1.0)
    
    def get_all_strategy_weights(self) -> Dict[str, float]:
        """Get all strategy weights"""
        return self.get('strategy_weights', {})


# Global instance
config = PredictionConfig()


# Convenient access functions
def get_consecutive_penalty(consecutive_count: int) -> float:
    """Get penalty multiplier for consecutive numbers"""
    return config.get_consecutive_penalty(consecutive_count)


def get_strategy_weight(strategy_name: str) -> float:
    """Get weight for a specific strategy"""
    return config.get_strategy_weight(strategy_name)


def get_diversity_lambda() -> float:
    """Get diversity lambda for overlap penalty (Phase 3)"""
    return config.get('experimental.mab_config.diversity_lambda', 0.5)


def reload_config(config_path: str = None):
    """Reload configuration from file"""
    config.load_config(config_path)
