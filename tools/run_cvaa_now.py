import sys
import os
import json
import numpy as np

# Add lottery-api to path
sys.path.insert(0, os.path.join(os.getcwd(), 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from cvaa_predictor import CVAAPredictor

def main():
    db_path = os.path.join(os.getcwd(), 'lottery-api/data/lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = db.get_all_draws('DAILY_539')
    rules = get_lottery_rules('DAILY_539')
    
    # Use 50 period window for "Fast" momentum
    history = all_draws[0:50] 
    
    # Reversed history to chronological order for physics
    chrono_history = list(reversed(history))
    
    predictor = CVAAPredictor(rules)
    prediction = predictor.predict(chrono_history)
    
    print(json.dumps(prediction))

if __name__ == "__main__":
    main()
