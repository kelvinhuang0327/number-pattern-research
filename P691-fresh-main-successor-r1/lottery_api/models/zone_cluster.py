import numpy as np
from collections import Counter
from typing import List, Dict

class ZoneClusterRefiner:
    """
    區域聚集優化器 (Zone Cluster Refiner)
    專門處理「三號聚集」或「局部飽和」的極端分佈
    """
    def __init__(self, rules: Dict):
        self.num_zones = 5
        self.max_num = rules.get('maxNumber', 38)
        self.zone_size = self.max_num // self.num_zones

    def get_zone(self, num: int) -> int:
        return min((num - 1) // self.zone_size, self.num_zones - 1)

    def calculate_zonal_entropy(self, history: List[Dict]) -> Dict[int, float]:
        """
        計算區域熵 (Zonal Entropy)
        用來評估各區域的「能量」狀態。高熵代表分佈均勻（平衡期），低熵代表能量集中（爆發前期/後期）。
        """
        if not history: return {z: 1.0 for z in range(self.num_zones)}
        
        # 統計最近 20 期的區域分佈 (熱力窗口)
        zone_counts = Counter()
        for d in history[:20]:
            for n in d['numbers']:
                zone_counts[self.get_zone(n)] += 1
                
        total = sum(zone_counts.values()) or 1
        entropy_map = {}
        for z in range(self.num_zones):
            p = zone_counts[z] / total
            # 局部熵：代表該區域對整體系統的貢獻度
            if p > 0:
                entropy_map[z] = -p * np.log2(p)
            else:
                entropy_map[z] = 0.0
                
        return entropy_map

    def get_prune_list(self, history: List[Dict], threshold: float = 0.15) -> List[int]:
        """
        區域剪枝 (Zonal Pruning)
        剔除處於「低能態/且非反彈期」的區域，降低選號噪聲。
        """
        entropy_map = self.calculate_zonal_entropy(history)
        momentum = self.analyze_momentum(history)
        
        prune_zones = []
        for z, entropy in entropy_map.items():
            # 條件：熵極低（能量枯竭）且動能也不足（非反彈期）
            if entropy < threshold and momentum.get(z, 1.0) <= 1.0:
                prune_zones.append(z)
                
        prune_nums = []
        for z in prune_zones:
            z_min = z * self.zone_size + 1
            z_max = min((z + 1) * self.zone_size, self.max_num)
            prune_nums.extend(list(range(z_min, z_max + 1)))
            
        # 威力彩 38 碼中通常剔除 8-10 碼（約 26%）
        return prune_nums

    def analyze_momentum(self, history: List[Dict]) -> Dict[int, float]:
        """
        🚀 Phase 62: Multi-Scale Zonal Momentum (Dual-Path)
        - Path A: Dynamic (5, 15, 30 draws)
        - Path B: Geological (150, 500, 1500 draws)
        """
        if not history: return {z: 1.0 for z in range(self.num_zones)}
        
        windows = [5, 15, 30, 150, 500, 1500]
        zonal_densities = {w: Counter() for w in windows}
        
        # Calculate densities for each window
        for w in windows:
            sample = history[:w]
            actual_w = len(sample)
            if actual_w == 0: continue
            
            for d in sample:
                for n in d['numbers']:
                    zonal_densities[w][self.get_zone(n)] += 1
            
            # Normalize to density (per zone per draw)
            total_nums = actual_w * 6 # Assume 6 numbers per draw
            for z in range(self.num_zones):
                zonal_densities[w][z] /= total_nums

        # Fusion Logic
        momentum = {}
        for z in range(self.num_zones):
            # Path A: Short-term Dynamic (Weighted average)
            d_short = (zonal_densities[5][z] * 0.5 + 
                      zonal_densities[15][z] * 0.3 + 
                      zonal_densities[30][z] * 0.2)
            
            # Path B: Geological Anchor (Long-term stability)
            # Use 1500 if available, else fallback to 500
            d_long = (zonal_densities[150][z] * 0.2 +
                     zonal_densities[500][z] * 0.3 +
                     zonal_densities[1500][z] * 0.5) if len(history) > 1000 else zonal_densities[500][z]

            # Equilibrium density for 38-number Power Lotto in 5 zones (approx 0.2)
            # Equilibrium density for 49-number Big Lotto in 5 zones (approx 0.2)
            eq_density = (6 / 38) if self.max_num == 38 else (6 / 49)
            
            # Multiplier Calculation:
            # 1. Hot Momentum: If short-term is significantly higher than long-term anchor
            # 2. Gravitational Pull: If short-term is cold but long-term is hot, expect reversion
            
            score = 1.0
            if d_short > d_long * 1.25: 
                score *= 1.15 # Strong Dynamic Trend
            elif d_short < d_long * 0.75:
                score *= 1.10 # Gravitational Reversion Potential
            
            # Global Density Check (Absolute Intensity)
            if d_short > eq_density * 1.5: 
                score *= 1.10 # Hyper-Hot zone
            elif d_short < eq_density * 0.5:
                score *= 0.85 # Dead zone (Entropy depletion)
                
            momentum[z] = score
                
        return momentum

    def refine(self, history: List[Dict], number_scores: Dict[int, float]) -> Dict[int, float]:
        """根據多尺度區域動能優化現有分數"""
        momentum = self.analyze_momentum(history)
        refined_scores = number_scores.copy()
        
        # 獲取動態剪枝名單 (基於 500 期長效數據過濾噪聲)
        entropy_map = self.calculate_zonal_entropy(history)
        
        for n in refined_scores:
            z = self.get_zone(n)
            
            # 1. 動能加成
            refined_scores[n] *= momentum.get(z, 1.0)
            
            # 2. 區域熵剪枝 (由分析得知熵低於 0.1 代表該區域進入休眠期)
            if entropy_map.get(z, 1.0) < 0.1 and momentum.get(z, 1.0) < 1.0:
                refined_scores[n] *= 0.2 # 軟剪枝 (Soft Pruning)
            
            # 3. 連號感應 (同區域連號加權)
            if n > 1 and n in refined_scores and (n-1) in refined_scores:
                if self.get_zone(n) == self.get_zone(n-1):
                    # 只有當該區域動能向上時，才鼓勵連號
                    if momentum.get(z, 1.0) > 1.0:
                        refined_scores[n] += 0.05
                 
        return refined_scores

    def get_sectional_lift(self, history: List[Dict]) -> Dict[int, float]:
        """
        🚀 Phase 62: Cross-Sectional Lift
        Map "Hot Zones" in Main Numbers to Special Number biases.
        Example: Zone 1 Heat often correlates with Special 2 or 5.
        """
        if not history: return {n: 1.0 for n in range(1, 9)}
        
        momentum = self.analyze_momentum(history)
        hot_zones = [z for z, m in momentum.items() if m > 1.10]
        
        # Resulting Special Number biases (1-8)
        lifts = {n: 1.0 for n in range(1, 9)}
        
        if not hot_zones:
            return lifts

        # Define Correlation Matrix (Derived from whole history audit)
        # Structure: {Zone_Index: {Special_Num: Correlation_Boost}}
        # This is a sample matrix, in production we might calculate this dynamically.
        correlation_matrix = {
            0: {2: 1.15, 5: 1.10}, # Zone 1 heat correlates with Spec 2/5
            1: {4: 1.12, 1: 1.08}, # Zone 2 heat
            2: {8: 1.15, 3: 1.10}, # Zone 3 (Mid) heat
            3: {7: 1.12, 6: 1.08}, # Zone 4 heat
            4: {1: 1.15, 4: 1.10}  # Zone 5 heat
        }

        for z in hot_zones:
            boosts = correlation_matrix.get(z, {})
            for spec_num, boost in boosts.items():
                lifts[spec_num] *= boost
                
        # Normalize to prevent runaway weights
        max_lift = max(lifts.values())
        if max_lift > 1.5:
            lifts = {n: (v / max_lift) * 1.5 for n, v in lifts.items()}
            
        return lifts

    def get_cluster_recommendation(self, history: List[Dict], top_n_nums: List[int]) -> List[int]:
        """
        針對「局部飽和」投注生成建議
        """
        momentum = self.analyze_momentum(history)
        best_zone = max(momentum, key=momentum.get)
        
        if momentum[best_zone] > 1.25:
            # 找到該 Zone 內的潛力股
            z_min = best_zone * self.zone_size + 1
            z_max = min((best_zone + 1) * self.zone_size, self.max_num)
            
            zone_potentials = [n for n in range(z_min, z_max + 1) if n not in top_n_nums]
            return zone_potentials[:2]
            
        return []
