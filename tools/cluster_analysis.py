#!/usr/bin/env python3
"""
Power Lotto Cluster Omission Analysis (區塊遺漏分析)
目標：找出尚未規劃的有效預測方法 —— 「區塊能量平衡」。
"""
import os
import sys
from collections import Counter
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class ClusterAnalyzer:
    def __init__(self):
        self.db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.draws = self.db.get_all_draws('POWER_LOTTO')
        
    def analyze_clusters(self, window=50):
        print(f"\n🧩 Cluster Omission Analysis (Window={window})")
        print("-" * 50)
        
        # Define 4 clusters: 1-10, 11-20, 21-30, 31-38
        clusters = {
            "C1 (01-10)": range(1, 11),
            "C2 (11-20)": range(11, 21),
            "C3 (21-30)": range(21, 31),
            "C4 (31-38)": range(31, 39)
        }
        
        recent = self.draws[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        
        cluster_density = {}
        for name, r in clusters.items():
            count = sum(freq.get(n, 0) for n in r)
            # Normalize by expected density (6 balls per draw * window / 38 total balls * balls in cluster)
            expected = (6 * window / 38) * len(r)
            ratio = count / expected
            cluster_density[name] = ratio
            
        for name, ratio in cluster_density.items():
            status = "Normal"
            if ratio < 0.8: status = "❄️ Omitted (Energy Surplus)"
            if ratio > 1.2: status = "🔥 Converged (Energy Deficit)"
            print(f"{name:<12}: {ratio:>6.2%} | {status}")
            
        # Strategy: If a cluster is Omitted, prefer numbers from that cluster.
        return cluster_density

if __name__ == "__main__":
    ca = ClusterAnalyzer()
    ca.analyze_clusters(window=50)
    ca.analyze_clusters(window=20)
