#!/usr/bin/env python3
import sys
import os
import logging
import json
from datetime import datetime, timedelta

# Disable basic logging to keep output clean, we will configure our own logger
logging.basicConfig(level=logging.ERROR)

sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

logger = logging.getLogger('Predictor')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def get_next_draw_date(last_date_str):
    """
    Calculate next draw date for Power Lotto (Monday and Thursday)
    """
    try:
        last_date = datetime.strptime(str(last_date_str), "%Y-%m-%d")
    except ValueError:
        # Fallback if format is weird
        logger.warning(f"⚠️ Could not parse date {last_date_str}, using today")
        last_date = datetime.now()

    # Power Lotto draws on Mon (0) and Thu (3)
    next_date = last_date + timedelta(days=1)
    while next_date.weekday() not in [0, 3]:
        next_date += timedelta(days=1)
    
    return next_date.strftime("%Y-%m-%d")

def main():
    try:
        lottery_type = 'POWER_LOTTO'
        rules = get_lottery_rules(lottery_type)
        
        # 1. Load Data
        logger.info("📂 Loading Power Lotto history...")
        all_draws = db_manager.get_all_draws(lottery_type)
        if not all_draws:
            logger.error("❌ No data found for Power Lotto")
            return

        # Sort by date descending (newest first)
        # Using date is safer than draw ID string comparison across different ROC years (e.g. "99..." > "114...")
        all_draws.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        last_draw = all_draws[0]
        logger.info(f"📅 Last Draw: {last_draw['draw']} ({last_draw['date']}) - Numbers: {last_draw['numbers']} Special: {last_draw['special']}")
        
        next_date = get_next_draw_date(last_draw.get('date'))
        logger.info(f"🔮 Predicting for Next Draw Date: {next_date}")
        print("-" * 60)
        
        # 2. Initialize Engine
        logger.info("🚀 Initializing SOTA Prediction Engine...")
        engine = UnifiedPredictionEngine()
        ensemble = OptimizedEnsemblePredictor(engine)
        
        # 3. Run Prediction
        logger.info("🧠 Running Optimized Ensemble Analysis...")
        logger.info("   (Including: Transformer SOTA, Pattern Recognition, Statistical Models)")
        
        # predict_single includes post-processing optimizations (Gap constraints, Special number optimization, etc.)
        prediction = ensemble.predict_single(all_draws, rules)
        
        # 4. Output Results
        print("\n" + "="*60)
        print(f"✨ POWER LOTTO PREDICTION FOR {next_date} ✨")
        print("="*60)
        
        numbers = prediction['numbers']
        special = prediction['special']
        confidence = prediction.get('confidence', 0)
        
        # Format numbers
        nums_str = ", ".join(f"{n:02d}" for n in numbers)
        special_str = f"{int(special):02d}" if special is not None else "??"
        
        print(f"\n🎯 Recommended Numbers (Zone 1):")
        print(f"   [{nums_str}]")
        
        print(f"\n⭐ Special Number (Zone 2):")
        print(f"   [{special_str}]")
        
        print(f"\n📊 Confidence Level: {confidence:.1%}")
        
        print("\n🔍 Strategy Details:")
        print(f"   Method: {prediction.get('method')}")
        
        if 'optimizations' in prediction:
            print(f"   Optimizations Applied: {', '.join(prediction['optimizations'])}")
            
        print("\n⚖️  Top Strategy Weights:")
        weights = prediction.get('strategy_weights', {})
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        for name, w in sorted_weights[:5]:
            print(f"   - {name:<15}: {w:.1%}")
            
        print("="*60 + "\n")
        
    except Exception as e:
        logger.error(f"❌ Prediction failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
