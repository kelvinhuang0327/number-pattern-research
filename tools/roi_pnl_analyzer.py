import json
import logging
from typing import List, Dict
import numpy as np

logger = logging.getLogger(__name__)

class ROIPnLAnalyzer:
    def __init__(self, lottery_type: str = 'POWER_LOTTO'):
        self.lottery_type = lottery_type
        # Standard prize amounts for Power Lotto (Manual approximation for analysis)
        self.prizes = {
            'M6': 100000000, # Variable, using floor for analysis
            'M5+1': 1000000,
            'M5': 20000,
            'M4+1': 4000,
            'M4': 800,
            'M3+1': 400,
            'M2+1': 200,
            'M3': 100,
            'M1+1': 100
        }

    def analyze_results(self, backtest_results: List[Dict]) -> Dict:
        """
        Decomposes backtest profit into prize tiers.
        """
        tier_counts = {k: 0 for k in self.prizes.keys()}
        tier_winnings = {k: 0 for k in self.prizes.keys()}
        total_bets = len(backtest_results) * 2 # Assuming 2-bet
        total_cost = total_bets * 100
        total_winnings = 0

        for res in backtest_results:
            actual = set(res.get('actual_numbers', []))
            actual_special = res.get('actual_special')
            
            for bet in res.get('bets', []):
                predicted = set(bet.get('numbers', []))
                intercept = len(predicted.intersection(actual))
                special_hit = (bet.get('special') == actual_special)
                
                tier = None
                if intercept == 6: tier = 'M6'
                elif intercept == 5 and special_hit: tier = 'M5+1'
                elif intercept == 5: tier = 'M5'
                elif intercept == 4 and special_hit: tier = 'M4+1'
                elif intercept == 4: tier = 'M4'
                elif intercept == 3 and special_hit: tier = 'M3+1'
                elif intercept == 3: tier = 'M3'
                elif intercept == 2 and special_hit: tier = 'M2+1'
                elif intercept == 1 and special_hit: tier = 'M1+1'
                
                if tier:
                    tier_counts[tier] += 1
                    amount = self.prizes.get(tier, 0)
                    tier_winnings[tier] += amount
                    total_winnings += amount

        roi = (total_winnings / total_cost) if total_cost > 0 else 0
        
        # Attribution percentages
        attribution = {k: (v / total_winnings if total_winnings > 0 else 0) for k, v in tier_winnings.items()}
        
        return {
            'total_cost': total_cost,
            'total_winnings': total_winnings,
            'overall_roi': roi,
            'tier_counts': tier_counts,
            'tier_winnings': tier_winnings,
            'attribution': attribution
        }

    def print_report(self, stats: Dict):
        print("\n" + "="*50)
        print("💰 ROI PnL ATTRIBUTION REPORT")
        print("="*50)
        print(f"Total Cost: {stats['total_cost']:,} TWD")
        print(f"Total Winnings: {stats['total_winnings']:,} TWD")
        print(f"Overall ROI: {stats['overall_roi']:.2%}")
        print("-" * 50)
        print(f"{'Tier':<10} | {'Count':<8} | {'Winnings':<12} | {'Contribution'}")
        print("-" * 50)
        sorted_tiers = sorted(stats['attribution'].items(), key=lambda x: x[1], reverse=True)
        for tier, contrib in sorted_tiers:
            if stats['tier_counts'][tier] > 0:
                print(f"{tier:<10} | {stats['tier_counts'][tier]:<8} | {stats['tier_winnings'][tier]:<12,} | {contrib:.2%}")
        print("="*50)
