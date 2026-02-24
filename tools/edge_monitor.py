#!/usr/bin/env python3
"""
Phase 68: Automated Edge Monitoring System
Tracks strategy performance with rolling statistical tests.
Alerts when Edge degrades or becomes statistically insignificant.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import sqlite3
from datetime import datetime
from scipy.stats import binomtest
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'strategies': {
        'ra_ensemble_5bet': {
            'name': 'RA Ensemble 5-bet',
            'baseline_rate': 0.1820,  # 18.20% for 5-bet M3+
            'bets_per_period': 5,
            'min_periods': 200,
            'target_periods': 1000,
        },
        'main_2bet': {
            'name': 'Main Number 2-bet',
            'baseline_rate': 0.0759,  # 7.59% for 2-bet M3+
            'bets_per_period': 2,
            'min_periods': 200,
            'target_periods': 500,
        }
    },
    'thresholds': {
        'p_value': 0.05,       # Statistical significance
        'min_edge': 0.02,      # 2% minimum meaningful edge
        'warning_edge': 0.01,  # 1% warning level
    },
    'data_path': 'lottery_api/data/monitor_data/'
}


class EdgeMonitor:
    """Monitors strategy edge over time with statistical validation."""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.config = CONFIG['strategies'].get(strategy_id)
        if not self.config:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        
        self.data_dir = CONFIG['data_path']
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.history_file = os.path.join(self.data_dir, f'{strategy_id}_history.json')
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Load monitoring history from file."""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_history(self):
        """Save monitoring history to file."""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, default=str)
    
    def calculate_stats(self, hits: int, total_bets: int) -> Dict:
        """Calculate statistical metrics for given results."""
        baseline = self.config['baseline_rate']
        observed_rate = hits / total_bets if total_bets > 0 else 0
        edge = observed_rate - baseline
        
        # Binomial test (one-sided, greater)
        if total_bets > 0:
            result = binomtest(hits, total_bets, baseline, alternative='greater')
            p_value = result.pvalue
            ci = result.proportion_ci(confidence_level=0.95, method='wilson')
            ci_low, ci_high = ci.low, ci.high
        else:
            p_value = 1.0
            ci_low, ci_high = 0, 0
        
        return {
            'hits': hits,
            'total_bets': total_bets,
            'observed_rate': observed_rate,
            'baseline_rate': baseline,
            'edge': edge,
            'edge_pct': edge * 100,
            'p_value': p_value,
            'ci_low': ci_low,
            'ci_high': ci_high,
            'significant': p_value < CONFIG['thresholds']['p_value'],
            'meaningful_edge': edge > CONFIG['thresholds']['min_edge'],
        }
    
    def evaluate_status(self, stats: Dict) -> str:
        """Determine strategy status based on statistics."""
        if stats['significant'] and stats['meaningful_edge']:
            return 'VALID'
        elif stats['significant'] and stats['edge'] > CONFIG['thresholds']['warning_edge']:
            return 'MARGINAL'
        elif stats['edge'] > 0:
            return 'INSUFFICIENT_EVIDENCE'
        else:
            return 'NO_EDGE'
    
    def record_evaluation(self, hits: int, periods: int, notes: str = '') -> Dict:
        """Record a new evaluation point."""
        total_bets = periods * self.config['bets_per_period']
        stats = self.calculate_stats(hits, total_bets)
        status = self.evaluate_status(stats)
        
        record = {
            'timestamp': datetime.now().isoformat(),
            'periods': periods,
            **stats,
            'status': status,
            'notes': notes,
        }
        
        self.history.append(record)
        self._save_history()
        
        return record
    
    def get_latest_status(self) -> Optional[Dict]:
        """Get the most recent evaluation."""
        if self.history:
            return self.history[-1]
        return None
    
    def print_report(self, record: Dict):
        """Print a formatted status report."""
        thresholds = CONFIG['thresholds']
        
        print()
        print('=' * 60)
        print(f"📊 {self.config['name']} 監控報告")
        print('=' * 60)
        print(f"⏰ 時間: {record['timestamp']}")
        print(f"📈 期數: {record['periods']}")
        print(f"🎯 命中: {record['hits']}/{record['total_bets']} = {record['observed_rate']*100:.2f}%")
        print(f"📌 基線: {record['baseline_rate']*100:.2f}%")
        print(f"✨ Edge: {record['edge_pct']:+.2f}%")
        print(f"📉 p-value: {record['p_value']:.4f}")
        print(f"📊 95% CI: [{record['ci_low']*100:.2f}%, {record['ci_high']*100:.2f}%]")
        print('-' * 60)
        
        # Status with emoji
        status_emoji = {
            'VALID': '✅',
            'MARGINAL': '⚠️',
            'INSUFFICIENT_EVIDENCE': '❓',
            'NO_EDGE': '❌'
        }
        
        print(f"狀態: {status_emoji.get(record['status'], '?')} {record['status']}")
        
        # Alerts
        if record['p_value'] >= thresholds['p_value']:
            print(f"⚠️ 警告: p-value ({record['p_value']:.4f}) >= {thresholds['p_value']} (不顯著)")
        
        if record['edge'] < thresholds['min_edge']:
            print(f"⚠️ 警告: Edge ({record['edge_pct']:+.2f}%) < {thresholds['min_edge']*100}% (無實用價值)")
        
        if record['edge'] < 0:
            print(f"🚨 嚴重警告: 負 Edge! 策略表現低於隨機基線")
        
        print('=' * 60)
    
    def get_trend(self, last_n: int = 5) -> Dict:
        """Analyze recent trend in Edge."""
        if len(self.history) < 2:
            return {'trend': 'UNKNOWN', 'delta': 0}
        
        recent = self.history[-last_n:]
        if len(recent) < 2:
            return {'trend': 'UNKNOWN', 'delta': 0}
        
        edges = [r['edge'] for r in recent]
        delta = edges[-1] - edges[0]
        
        if delta > 0.005:
            trend = 'IMPROVING'
        elif delta < -0.005:
            trend = 'DECLINING'
        else:
            trend = 'STABLE'
        
        return {'trend': trend, 'delta': delta, 'edges': edges}


def run_live_evaluation(strategy_id: str = 'ra_ensemble_5bet'):
    """Run evaluation using latest backtest data."""
    monitor = EdgeMonitor(strategy_id)
    
    logger.info(f"🔍 Evaluating {monitor.config['name']}...")
    
    # Load the latest backtest results
    # In production, this would query actual prediction vs result data
    # WARNING: Phase 67 results (20.70%) are currently flagged as LEGACY/INVALID
    
    if strategy_id == 'ra_ensemble_5bet':
        # From Phase 67: 1035/5000 = 20.70% (DEBUNKED)
        record = monitor.record_evaluation(
            hits=1035,
            periods=1000,
            notes='[LEGACY/INVALID] Initial baseline from Phase 67 validation (DEBUNKED)'
        )
    elif strategy_id == 'main_2bet':
        # From Phase 67: 76/1000 = 7.60% (LEGACY)
        record = monitor.record_evaluation(
            hits=76,
            periods=500,
            notes='[LEGACY] Initial baseline from Phase 67 validation'
        )
    else:
        logger.error(f"Unknown strategy: {strategy_id}")
        return
    
    monitor.print_report(record)
    
    # Check trend
    trend = monitor.get_trend()
    if trend['trend'] != 'UNKNOWN':
        print(f"\n📈 趨勢: {trend['trend']} (Δ = {trend['delta']*100:+.2f}%)")


def show_all_status():
    """Show status of all monitored strategies."""
    print('\n' + '=' * 70)
    print('📊 所有策略監控狀態總覽')
    print('=' * 70 + '\n')
    
    for strategy_id in CONFIG['strategies'].keys():
        try:
            monitor = EdgeMonitor(strategy_id)
            latest = monitor.get_latest_status()
            
            if latest:
                status_emoji = {'VALID': '✅', 'MARGINAL': '⚠️', 'INSUFFICIENT_EVIDENCE': '❓', 'NO_EDGE': '❌'}
                emoji = status_emoji.get(latest['status'], '?')
                print(f"{emoji} {monitor.config['name']}: Edge {latest['edge_pct']:+.2f}% | p={latest['p_value']:.4f} | {latest['status']}")
            else:
                print(f"❓ {monitor.config['name']}: 尚無評估記錄")
        except Exception as e:
            print(f"❌ {strategy_id}: Error - {e}")
    
    print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Edge Monitoring System')
    parser.add_argument('--strategy', '-s', default='all', help='Strategy ID or "all"')
    parser.add_argument('--evaluate', '-e', action='store_true', help='Run new evaluation')
    args = parser.parse_args()
    
    if args.strategy == 'all':
        if args.evaluate:
            for sid in CONFIG['strategies'].keys():
                run_live_evaluation(sid)
        else:
            show_all_status()
    else:
        if args.evaluate:
            run_live_evaluation(args.strategy)
        else:
            monitor = EdgeMonitor(args.strategy)
            latest = monitor.get_latest_status()
            if latest:
                monitor.print_report(latest)
            else:
                print(f"No evaluation history for {args.strategy}")
