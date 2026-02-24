import logging
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def validate_chronological_order(history: List[Dict], lottery_type: str = "Unknown") -> List[Dict]:
    """
    Ensures history is sorted Oldest to Newest.
    Fixes the common DESC/ASC confusion.
    """
    if not history:
        return []
    
    first_date = history[0].get('date', '')
    last_date = history[-1].get('date', '')
    
    if first_date > last_date:
        logger.warning(f"⚠️ [Backtest Safety] {lottery_type} history detected in REVERSE order. Automatically fixing to Chronological (ASC).")
        return history[::-1]
    
    return history

def get_safe_backtest_slice(all_draws: List[Dict], target_index: int) -> List[Dict]:
    """
    Returns a slice of history strictly BEFORE the target index.
    CRITICAL: target_index is the draw currently being predicted.
    """
    if target_index <= 0:
        return []
    
    # Strictly limit to data BEFORE target_index
    safe_history = all_draws[:target_index]
    
    # Integrity Check
    if len(safe_history) >= (target_index + 1):
        raise ValueError("[Backtest Safety] LEAKAGE DETECTED: History slice includes target or future data!")
    
    return safe_history

def isolate_mab_state(engine, lottery_type: str):
    """
    Forces MAB reset and uses a temporary/isolated state path for backtesting.
    Prevention for State Persistence Leakage.
    """
    if not hasattr(engine, 'mab_predictor') or not engine.mab_predictor:
        return
    
    # 1. Reset Internal State
    engine.mab_predictor.mab.reset()
    
    # 2. Assign Temporary Paths to prevent reading/writing to production state
    temp_path = f"data/temp_mab_backtest_{lottery_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    engine.mab_predictor.state_path = temp_path
    
    logger.info(f"🛡️ [Backtest Safety] MAB Isolated. Temp State: {temp_path}")
    return temp_path

def cleanup_backtest_state(temp_path: str):
    """Removes temporary backtest state files."""
    if temp_path and os.path.exists(temp_path):
        try:
            os.remove(temp_path)
            logger.info(f"🧹 [Backtest Safety] Cleaned up temp state: {temp_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup {temp_path}: {e}")
