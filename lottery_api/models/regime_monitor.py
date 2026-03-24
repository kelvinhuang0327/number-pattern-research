import numpy as np
import pandas as pd
from typing import Dict, List, Any
import os
import json

class RegimeMonitor:
    """
    Level 3: Dynamic Waterline & Performance Regime Tracking.
    Monitors historical hit rates to detect 'Hot' and 'Cold' clusters.
    """
    
    def __init__(self, history_path: str = "data/performance_history.json", window: int = 20):
        self.history_path = history_path
        self.window = window
        self.ensure_history_exists()

    def ensure_history_exists(self):
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        if not os.path.exists(self.history_path):
            # Seed with neutral history if empty
            initial_data = [0] * self.window
            with open(self.history_path, 'w') as f:
                json.dump(initial_data, f)

    def record_result(self, hit_count: int):
        """Records a 0 (miss) or 1 (win M3+) for the latest period."""
        val = 1 if hit_count >= 1 else 0
        try:
            with open(self.history_path, 'r') as f:
                data = json.load(f)
            data.append(val)
            # Keep only sliding window
            data = data[-100:] 
            with open(self.history_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error recording result: {e}")

    def get_current_regime(self) -> Dict[str, Any]:
        """Calculates the current regime based on Moving Average."""
        try:
            with open(self.history_path, 'r') as f:
                data = json.load(f)
        except:
            data = []

        if len(data) < self.window:
            return {
                "regime": "資料累積中",
                "ma_hit_rate": 0,
                "recommendation": "尚無足夠資料，請繼續記錄",
                "color": "#6c757d"
            }

        # Calculate MA for the last `window` periods
        ma_hit_rate = np.mean(data[-self.window:])
        
        # Performance Thresholds for Level 3
        # Baseline M3+ (3-bet) usually around 6%
        baseline = 0.06
        
        if ma_hit_rate < baseline * 0.5:
            regime = "低潮期（命中率異常偏低）"
            recommendation = "防守模式：建議降低投注"
            color = "#dc3545" # Red
        elif ma_hit_rate > baseline * 1.5:
            regime = "高峰期（命中率異常偏高）"
            recommendation = "留意均值回歸：近期表現優於預期"
            color = "#28a745" # Green
        else:
            regime = "穩定期（正常波動範圍）"
            recommendation = "維持標準投注策略"
            color = "#ffc107" # Yellow or Amber

        return {
            "regime": regime,
            "ma_hit_rate": float(ma_hit_rate),
            "recommendation": recommendation,
            "color": color,
            "window": self.window,
            "sample_size": len(data)
        }

def get_regime_monitor():
    return RegimeMonitor()
