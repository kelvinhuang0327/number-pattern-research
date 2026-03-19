import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StabilityProfile:
    """
    Manages and retrieves the stability profiles of various prediction strategies.
    Profiles are derived from long-term vs short-term backtest benchmarks.
    """
    
    def __init__(self, data_path: str = "tools/"):
        self.data_path = data_path
        self.profiles = {
            "POWER_LOTTO": self._load_profile("POWER_LOTTO"),
            "BIG_LOTTO": self._load_profile("BIG_LOTTO")
        }

    def _load_profile(self, lottery_type: str) -> Dict[str, Any]:
        """Loads and parses the stability audit report if it exists."""
        # Note: Since the report is a markdown/text file, we might prefer a JSON version 
        # but for now we look for the benchmark files directly to compute.
        profile = {}
        windows = [150, 500, 1500]
        
        for w in windows:
            filename = os.path.join(self.data_path, f"benchmark_{lottery_type}_{w}.json")
            if os.path.exists(filename):
                try:
                    with open(filename, "r") as f:
                        data = json.load(f)
                        for strat, stats in data['methods'].items():
                            if strat not in profile:
                                profile[strat] = {}
                            profile[strat][w] = (stats['hits'] / w) * 100
                except Exception as e:
                    logger.warning(f"Failed to load {filename}: {e}")
        
        # Analyze stability
        final_profiles = {}
        for strat, results in profile.items():
            if 150 in results and 1500 in results:
                decay = results[150] - results[1500]
                if decay > 2.0:
                    status = "SHORT_MOMENTUM"
                    desc = "高性能但具備顯著長線衰減，建議僅用於短期觀察。"
                elif abs(decay) < 0.5:
                    status = "ROBUST"
                    desc = "長短期表現一致，具備高系統穩定性。"
                elif decay < -1.0:
                    status = "LATE_BLOOMER"
                    desc = "長線表現優於短期，可能捕捉的是大樣本規律。"
                else:
                    status = "STABLE"
                    desc = "表現穩定，符合預期波動範圍。"
            else:
                status = "UNCERTAIN"
                desc = "回測數據不足，無法評估穩定性。"
            
            final_profiles[strat] = {
                "status": status,
                "description": desc,
                "data": results
            }
        return final_profiles

    def get_strategy_stability(self, lottery_type: str, strategy_name: str) -> Dict[str, Any]:
        """Returns the stability profile for a given strategy."""
        l_type = "POWER_LOTTO" if "POWER" in lottery_type.upper() else "BIG_LOTTO"
        lottery_profile = self.profiles.get(l_type, {})
        
        # Exact match or fuzzy match
        if strategy_name in lottery_profile:
            return lottery_profile[strategy_name]
            
        # Try fuzzy match (e.g., lowercase, or substrings)
        for k, v in lottery_profile.items():
            if strategy_name.lower() in k.lower() or k.lower() in strategy_name.lower():
                return v
                
        return {
            "status": "UNKNOWN",
            "description": "無此策略的回測穩定性數據。",
            "data": {}
        }

_global_stability_profile = None

def get_stability_profile():
    global _global_stability_profile
    if _global_stability_profile is None:
        # Check root, tools/, and ../tools/
        paths_to_check = [".", "tools", "../tools", "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"]
        data_path = "."
        for p in paths_to_check:
            if os.path.exists(os.path.join(p, "benchmark_POWER_LOTTO_500.json")):
                data_path = p
                break
        _global_stability_profile = StabilityProfile(data_path=data_path)
    return _global_stability_profile
