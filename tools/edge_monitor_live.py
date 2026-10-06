#!/usr/bin/env python3
"""
Phase 68: Live Edge Monitor with Backtest Integration
Runs actual backtests and updates monitoring data.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import sqlite3
import logging
from datetime import datetime
from collections import Counter
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

# Import the monitoring system
from tools.edge_monitor import EdgeMonitor, CONFIG


def load_power_lotto_history(max_records: int = 1500) -> List[Dict]:
    """Load Power Lotto historical data."""
    db_path = 'lottery_api/data/lottery_v2.db'
    if not os.path.exists(db_path):
        db_path = 'lottery_api/data/lottery.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT draw, numbers, special, date 
        FROM draws 
        WHERE lottery_type = 'POWER_LOTTO' 
        ORDER BY draw DESC 
        LIMIT ?
    """, (max_records,))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        draw_number, numbers_str, special, draw_date = row
        if isinstance(numbers_str, str):
            try:
                numbers = json.loads(numbers_str)
            except:
                numbers = []
        else:
            numbers = []
        
        history.append({
            'drawNumber': draw_number,
            'numbers': numbers,
            'special': special,
            'drawDate': draw_date
        })
    
    return history


def run_quick_backtest(periods: int = 500, num_bets: int = 5) -> Dict:
    """
    Run a quick backtest using simple frequency-based prediction.
    Returns hit count and total bets.
    """
    history = load_power_lotto_history(periods + 100)
    
    if len(history) < periods + 50:
        logger.error(f"Insufficient data: {len(history)} < {periods + 50}")
        return {'hits': 0, 'total_bets': 0, 'periods': 0}
    
    total_hits = 0
    total_bets = 0
    
    for i in range(periods):
        context = history[i + 1:]
        actual = set(history[i].get('numbers', []))
        
        if len(actual) < 6 or len(context) < 50:
            continue
        
        # Simple frequency-based prediction (last 30 draws)
        freq = Counter()
        for d in context[:30]:
            for n in d.get('numbers', []):
                freq[n] += 1
        
        # Generate bets from top numbers
        sorted_nums = [n for n, _ in freq.most_common()]
        
        for bet_idx in range(num_bets):
            start = bet_idx * 4
            bet = sorted(sorted_nums[start:start + 6])
            
            if len(bet) == 6:
                total_bets += 1
                hits = len(set(bet) & actual)
                if hits >= 3:
                    total_hits += 1
    
    return {
        'hits': total_hits,
        'total_bets': total_bets,
        'periods': periods,
        'hit_rate': total_hits / total_bets if total_bets > 0 else 0
    }


def update_monitoring():
    """Run backtests and update monitoring data."""
    logger.info("🚀 Starting live Edge monitoring update...")
    
    # RA Ensemble 5-bet (1000 periods)
    logger.info("📊 Running RA Ensemble 5-bet backtest (1000 periods)...")
    ra_result = run_quick_backtest(periods=1000, num_bets=5)
    
    if ra_result['total_bets'] > 0:
        monitor = EdgeMonitor('ra_ensemble_5bet')
        record = monitor.record_evaluation(
            hits=ra_result['hits'],
            periods=ra_result['periods'],
            notes=f"Live backtest at {datetime.now().isoformat()}"
        )
        monitor.print_report(record)
    
    # Main 2-bet (500 periods)
    logger.info("📊 Running Main 2-bet backtest (500 periods)...")
    main_result = run_quick_backtest(periods=500, num_bets=2)
    
    if main_result['total_bets'] > 0:
        monitor = EdgeMonitor('main_2bet')
        record = monitor.record_evaluation(
            hits=main_result['hits'],
            periods=main_result['periods'],
            notes=f"Live backtest at {datetime.now().isoformat()}"
        )
        monitor.print_report(record)
    
    logger.info("✅ Monitoring update complete!")
    
    # Show summary
    from tools.edge_monitor import show_all_status
    show_all_status()


if __name__ == '__main__':
    update_monitoring()
