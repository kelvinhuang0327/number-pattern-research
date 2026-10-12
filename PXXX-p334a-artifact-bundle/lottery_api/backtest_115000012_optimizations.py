#!/usr/bin/env python3
"""
大樂透 115000012 檢討優化回測

根據 failure_analysis_115000012.md 的三大優化方向，逐段實作並回測：
  Phase A: Baseline (Orthogonal 3-Bet 原始版)
  Phase B: + Median Zone Sampler (中間態取樣器)
  Phase C: + Zone Absence Predictor (區間缺席預警)
  Phase D: + Repeat/Consecutive Force Include (重號/連號強制納入)

回測方法: Rolling Backtest (無資料洩漏)
  - 以每期開獎為目標，使用該期之前的歷史數據進行預測
  - 測試 2025 年 (114 年) + 2026 年 (115 年) 的所有大樂透資料
"""
import sys
import os
import logging
import numpy as np
from typing import List, Dict, Tuple, Set
from collections import Counter
from datetime import datetime

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

# Suppress verbose logs
logging.getLogger().setLevel(logging.ERROR)

from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.unified_predictor import UnifiedPredictionEngine
from models.multi_bet_optimizer import MultiBetOptimizer
from common import get_lottery_rules


# ============================================================
# Optimization Module 1: Median Zone Sampler (中間態取樣器)
# ============================================================
class MedianZoneSampler:
    """
    專門從 freq 10-20%, gap 3-8 的「被忽略」號碼中取樣。
    這些號碼處於「中間態」— 不冷不熱、不長不短遺漏 —
    是所有極端策略的盲區。
    """
    def predict(self, draws: List[Dict], lottery_rules: Dict) -> List[int]:
        max_num = lottery_rules.get('maxNumber', 49)
        pick_count = lottery_rules.get('pickCount', 6)
        
        window_30 = draws[:30]
        window_50 = draws[:50]
        total_30 = len(window_30)
        total_50 = len(window_50)
        
        # 計算近30期頻率
        nums_30 = [n for d in window_30 for n in d['numbers']]
        freq_30 = Counter(nums_30)
        
        # 計算遺漏期數 (Gap)
        gaps = {}
        for n in range(1, max_num + 1):
            for i, d in enumerate(draws):
                if n in d['numbers']:
                    gaps[n] = i
                    break
            else:
                gaps[n] = len(draws)
        
        # 篩選「中間態」號碼: freq 10-20%, gap 3-8
        candidates = []
        for n in range(1, max_num + 1):
            freq_pct = freq_30.get(n, 0) / total_30 * 100
            gap = gaps.get(n, 0)
            
            # 中間態定義: 頻率 8-22%, Gap 2-10 (略放寬以確保足夠候選)
            if 8 <= freq_pct <= 22 and 2 <= gap <= 10:
                # 評分: 越接近「中心」的越優先
                freq_score = 1 - abs(freq_pct - 15) / 15  # 以 15% 為中心
                gap_score = 1 - abs(gap - 5) / 5  # 以 5 為中心
                score = freq_score * 0.5 + gap_score * 0.5
                candidates.append((n, score))
        
        # 按分數排序取 Top
        candidates.sort(key=lambda x: x[1], reverse=True)
        result = [c[0] for c in candidates[:pick_count]]
        
        # 若候選不足，用近50期 freq 15% 附近的號碼補充
        if len(result) < pick_count:
            nums_50 = [n for d in window_50 for n in d['numbers']]
            freq_50 = Counter(nums_50)
            fallback = sorted(
                range(1, max_num + 1),
                key=lambda n: abs(freq_50.get(n, 0) / total_50 * 100 - 12.2)
            )
            for f in fallback:
                if f not in result:
                    result.append(f)
                    if len(result) >= pick_count:
                        break
        
        return sorted(result[:pick_count])


# ============================================================
# Optimization Module 2: Zone Absence Predictor (區間缺席預警)
# ============================================================
class ZoneAbsencePredictor:
    """
    偵測「過熱區間」並預測哪個區間本期可能完全缺席。
    用來調整其他策略的選號分佈。
    """
    ZONES = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]
    
    def predict_absent_zone(self, draws: List[Dict], lottery_rules: Dict) -> Tuple[int, float]:
        """
        Returns: (zone_index, confidence)
        zone_index: 預測最可能缺席的區間 (0-4)
        confidence: 信心分數 (0-1)
        """
        recent = draws[:10]
        
        # 統計近10期每個 zone 的出現次數
        zone_counts = [0] * 5
        total_nums = 0
        for d in recent:
            for n in d['numbers']:
                total_nums += 1
                for zi, (lo, hi) in enumerate(self.ZONES):
                    if lo <= n <= hi:
                        zone_counts[zi] += 1
                        break
        
        # 計算每個 zone 的「過熱度」(近10期佔比 vs 期望佔比)
        expected = [10/49, 10/49, 10/49, 10/49, 9/49]  # Z5 只有 9 個號碼
        overheat_scores = []
        for zi in range(5):
            actual_pct = zone_counts[zi] / total_nums if total_nums > 0 else 0
            overheat = actual_pct / expected[zi] if expected[zi] > 0 else 0
            overheat_scores.append(overheat)
        
        # 過熱最多的區間 → 最可能在本期「缺席」(均值回歸)
        most_overheated = max(range(5), key=lambda i: overheat_scores[i])
        confidence = min((overheat_scores[most_overheated] - 1.0) / 1.0, 1.0)  # 超過 2x 期望 → 高信心
        confidence = max(confidence, 0.0)
        
        return most_overheated, confidence
    
    def filter_numbers(self, numbers: List[int], absent_zone_idx: int, confidence: float) -> List[int]:
        """
        從號碼列表中移除位於「預測缺席區間」的號碼 (高信心時)。
        """
        if confidence < 0.3:
            return numbers  # 信心不夠，不過濾
        
        lo, hi = self.ZONES[absent_zone_idx]
        filtered = [n for n in numbers if not (lo <= n <= hi)]
        
        # 至少保留原來號碼的一半
        if len(filtered) < len(numbers) // 2:
            return numbers
        
        return filtered


# ============================================================
# Optimization Module 3: Repeat/Consecutive Force Include
# ============================================================
class RepeatConsecutiveForcer:
    """
    強制在多注策略中納入重號和連號候選。
    歷史數據顯示大樂透約 40% 的期數含有重號，25-30% 含連號對。
    """
    def get_repeat_candidates(self, draws: List[Dict], lottery_rules: Dict, top_n: int = 3) -> List[int]:
        """返回上期號碼中最可能重現的候選"""
        if not draws:
            return []
        
        prev_numbers = draws[0]['numbers']
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 計算每個上期號碼的「重現可能性」
        # 依據: 近30期的頻率 (頻率越高的號碼越容易重現)
        nums_30 = [n for d in draws[:30] for n in d['numbers']]
        freq_30 = Counter(nums_30)
        
        scored = [(n, freq_30.get(n, 0)) for n in prev_numbers]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [s[0] for s in scored[:top_n]]
    
    def get_consecutive_candidates(self, draws: List[Dict], lottery_rules: Dict) -> List[Tuple[int, int]]:
        """返回最可能的連號對候選"""
        max_num = lottery_rules.get('maxNumber', 49)
        
        # 統計近50期哪些連號對最常出現
        pair_count = Counter()
        for d in draws[:50]:
            nums = sorted(d['numbers'])
            for i in range(len(nums) - 1):
                if nums[i+1] - nums[i] == 1:
                    pair_count[(nums[i], nums[i+1])] += 1
        
        # 加上近期頻率較高號碼形成的連號  
        nums_30 = [n for d in draws[:30] for n in d['numbers']]
        freq_30 = Counter(nums_30)
        
        # 找頻率最高的號碼，檢查其 ±1 是否也有合理頻率
        hot_nums = sorted(freq_30.keys(), key=lambda x: freq_30[x], reverse=True)[:15]
        for n in hot_nums:
            if n + 1 <= max_num and freq_30.get(n + 1, 0) >= 2:
                pair_count[(n, n+1)] += 1
        
        return pair_count.most_common(3)
    
    def force_include(self, bet_numbers: List[int], repeat_candidates: List[int], 
                      consecutive_candidates: List[Tuple[int, int]], pick_count: int = 6) -> List[int]:
        """
        強制在注組中加入至少 1 個重號候選。
        如果有高頻連號對，嘗試納入。
        """
        result = list(bet_numbers)
        added = set(result)
        
        # 強制加入最佳重號候選 (替換分數最低的)
        for rc in repeat_candidates[:1]:
            if rc not in added:
                result.append(rc)
                added.add(rc)
        
        # 嘗試加入連號 (如果空間允許)
        if consecutive_candidates:
            best_pair = consecutive_candidates[0][0]
            n1, n2 = best_pair
            if n1 not in added:
                result.append(n1)
                added.add(n1)
            if n2 not in added:
                result.append(n2)
                added.add(n2)
        
        # 如果超過 pick_count，移除低頻號碼
        if len(result) > pick_count:
            # 保留所有強制加入的，移除原始注中分數最低的
            result = sorted(result)
            while len(result) > pick_count:
                # 移除與其他號碼距離最近的 (減少冗餘)
                min_gap_idx = 0
                min_gap = float('inf')
                for i in range(len(result) - 1):
                    gap = result[i+1] - result[i]
                    if gap < min_gap:
                        min_gap = gap
                        min_gap_idx = i
                # 移除距離最近的一對中，不是強制加入的那個
                if result[min_gap_idx] in repeat_candidates or \
                   any(result[min_gap_idx] in pair for pair, _ in consecutive_candidates):
                    result.pop(min_gap_idx + 1)
                else:
                    result.pop(min_gap_idx)
        
        return sorted(result[:pick_count])


# ============================================================
# Enhanced Orthogonal 3-Bet Generator with optimizations
# ============================================================
class EnhancedOrthogonal3Bet:
    """
    增強版 Orthogonal 3-Bet，整合三大優化模組。
    """
    def __init__(self, engine: UnifiedPredictionEngine, optimizer: MultiBetOptimizer):
        self.engine = engine
        self.optimizer = optimizer
        self.median_sampler = MedianZoneSampler()
        self.zone_predictor = ZoneAbsencePredictor()
        self.repeat_forcer = RepeatConsecutiveForcer()
    
    def predict_baseline(self, draws: List[Dict], rules: Dict, number_scores: Dict) -> Dict:
        """Phase A: 原始 Orthogonal 3-Bet"""
        return self.optimizer.generate_orthogonal_strategy_3bets(draws, rules, number_scores)
    
    def predict_with_median(self, draws: List[Dict], rules: Dict, number_scores: Dict) -> Dict:
        """Phase B: + Median Zone Sampler 替換 Bet 3"""
        result = self.optimizer.generate_orthogonal_strategy_3bets(draws, rules, number_scores)
        
        # 替換 Bet 3 為 Median Zone Sampler
        median_pred = self.median_sampler.predict(draws, rules)
        
        if result.get('bets') and len(result['bets']) >= 3:
            result['bets'][2] = {
                'numbers': median_pred,
                'source': 'median_zone_sampler',
                'special': result['bets'][2].get('special')
            }
        
        return result
    
    def predict_with_zone_filter(self, draws: List[Dict], rules: Dict, number_scores: Dict) -> Dict:
        """Phase C: + Zone Absence Predictor (過濾過熱區間)"""
        result = self.predict_with_median(draws, rules, number_scores)
        
        absent_zone, confidence = self.zone_predictor.predict_absent_zone(draws, rules)
        
        if confidence >= 0.3 and result.get('bets'):
            max_num = rules.get('maxNumber', 49)
            pick_count = rules.get('pickCount', 6)
            
            for i, bet in enumerate(result['bets']):
                filtered = self.zone_predictor.filter_numbers(
                    bet['numbers'], absent_zone, confidence
                )
                
                if len(filtered) < pick_count:
                    # 需要補充號碼: 從非過熱區間的高頻號碼中補充
                    lo, hi = self.zone_predictor.ZONES[absent_zone]
                    supplement_pool = [
                        n for n in range(1, max_num + 1) 
                        if not (lo <= n <= hi) and n not in filtered
                    ]
                    # 按 number_scores 排序
                    supplement_pool.sort(key=lambda x: number_scores.get(x, 0), reverse=True)
                    
                    for s in supplement_pool:
                        filtered.append(s)
                        if len(filtered) >= pick_count:
                            break
                
                result['bets'][i]['numbers'] = sorted(filtered[:pick_count])
        
        return result
    
    def predict_full_optimization(self, draws: List[Dict], rules: Dict, number_scores: Dict) -> Dict:
        """Phase D: + Repeat/Consecutive Force Include (全部優化)"""
        result = self.predict_with_zone_filter(draws, rules, number_scores)
        
        pick_count = rules.get('pickCount', 6)
        
        # 獲取重號和連號候選
        repeat_cands = self.repeat_forcer.get_repeat_candidates(draws, rules, top_n=2)
        consec_cands = self.repeat_forcer.get_consecutive_candidates(draws, rules)
        
        if result.get('bets') and len(result['bets']) >= 2:
            # 在 Bet 2 (Cluster/Momentum) 中強制納入重號
            bet2_nums = result['bets'][1]['numbers']
            enhanced_bet2 = self.repeat_forcer.force_include(
                bet2_nums, repeat_cands, consec_cands, pick_count
            )
            result['bets'][1]['numbers'] = enhanced_bet2
            result['bets'][1]['source'] += '_repeat_enhanced'
        
        return result


# ============================================================
# Rolling Backtest Engine
# ============================================================
def run_rolling_backtest(test_draws: List[Dict], all_draws: List[Dict], 
                         predict_func, rules: Dict, label: str) -> Dict:
    """
    執行滾動回測 (無資料洩漏)
    
    Args:
        test_draws: 要測試的目標期數列表 (ASC order)
        all_draws: 全部歷史數據 (ASC order)
        predict_func: 接受 (history, rules, number_scores) 的預測函數
        rules: 彩票規則
        label: 標籤名稱
    
    Returns: 統計結果 dict
    """
    pick_count = rules.get('pickCount', 6)
    max_num = rules.get('maxNumber', 49)
    
    stats = {
        'label': label,
        'total': 0,
        'bet_hits': [[], [], []],  # 每注的命中數列表
        'best_hit_per_draw': [],    # 每期最佳注的命中數
        'union_hits': [],           # 3注聯合覆蓋的命中數
        'any_3plus': 0,             # 任一注 3+ 命中的次數
        'any_2plus': 0,             # 任一注 2+ 命中的次數
        'union_3plus': 0,           # 聯合覆蓋 3+ 的次數
        'details': [],
    }
    
    for target in test_draws:
        target_id = target['draw']
        
        # 找到 target 在 all_draws 中的 index
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == target_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx < 200:
            continue
        
        # 歷史數據: target 之前的所有數據 (DESC order for models)
        history = all_draws[:target_idx]
        history_desc = list(reversed(history))  # newest first
        
        if len(history_desc) < 100:
            continue
        
        # 計算 number_scores
        recent_nums = [n for d in history_desc[:200] for n in d['numbers']]
        freq_counter = Counter(recent_nums)
        number_scores = {n: freq_counter.get(n, 0) for n in range(1, max_num + 1)}
        
        actual = set(target['numbers'])
        
        try:
            result = predict_func(history_desc, rules, number_scores)
            bets = result.get('bets', [])
            
            if len(bets) < 3:
                continue
            
            # 計算每注的命中數
            bet_hits_this = []
            all_predicted = set()
            for bi, bet in enumerate(bets[:3]):
                nums = set(bet['numbers'])
                all_predicted |= nums
                hits = len(nums & actual)
                bet_hits_this.append(hits)
                stats['bet_hits'][bi].append(hits)
            
            best_hit = max(bet_hits_this)
            union_hit = len(all_predicted & actual)
            
            stats['best_hit_per_draw'].append(best_hit)
            stats['union_hits'].append(union_hit)
            
            if best_hit >= 3:
                stats['any_3plus'] += 1
            if best_hit >= 2:
                stats['any_2plus'] += 1
            if union_hit >= 3:
                stats['union_3plus'] += 1
            
            stats['total'] += 1
            
            stats['details'].append({
                'draw_id': target_id, 
                'actual': sorted(actual),
                'bets': [sorted(b['numbers']) for b in bets[:3]],
                'hits': bet_hits_this,
                'best': best_hit,
                'union': union_hit
            })
            
        except Exception as e:
            # Silently skip failures
            pass
    
    return stats


def print_stats(stats: Dict):
    """格式化輸出回測統計"""
    n = stats['total']
    if n == 0:
        print(f"   ❌ {stats['label']}: 無有效測試")
        return
    
    avg_best = np.mean(stats['best_hit_per_draw'])
    avg_union = np.mean(stats['union_hits'])
    rate_3plus = stats['any_3plus'] / n * 100
    rate_2plus = stats['any_2plus'] / n * 100
    union_3plus = stats['union_3plus'] / n * 100
    
    # 各注平均
    avg_bets = [np.mean(h) if h else 0 for h in stats['bet_hits']]
    
    # 命中分佈
    best_dist = Counter(stats['best_hit_per_draw'])
    
    print(f"\n   📊 {stats['label']}")
    print(f"   {'─' * 60}")
    print(f"   測試期數: {n}")
    print(f"   各注平均命中: Bet1={avg_bets[0]:.2f}  Bet2={avg_bets[1]:.2f}  Bet3={avg_bets[2]:.2f}")
    print(f"   最佳注平均命中: {avg_best:.3f}")
    print(f"   聯合覆蓋平均: {avg_union:.3f}")
    print(f"   任一注 3+ 命中率: {rate_3plus:.1f}% ({stats['any_3plus']}/{n})")
    print(f"   任一注 2+ 命中率: {rate_2plus:.1f}% ({stats['any_2plus']}/{n})")
    print(f"   聯合覆蓋 3+ 率: {union_3plus:.1f}% ({stats['union_3plus']}/{n})")
    print(f"   最佳注命中分佈: ", end="")
    for h in sorted(best_dist.keys(), reverse=True):
        print(f"{h}命中={best_dist[h]}({best_dist[h]/n*100:.1f}%) ", end="")
    print()


def compare_phases(all_stats: List[Dict]):
    """輸出各 Phase 對比表"""
    print("\n" + "=" * 90)
    print("📈 各 Phase 回測對比表")
    print("=" * 90)
    
    headers = ["Phase", "最佳注Avg", "聯合Avg", "3+率", "2+率", "聯合3+率", "Δ3+率"]
    print(f"{'Phase':<40} | {'Best Avg':>9} | {'UnionAvg':>9} | {'3+%':>7} | {'2+%':>7} | {'U3+%':>7} | {'Δ3+%':>7}")
    print("-" * 90)
    
    baseline_3plus = None
    
    for s in all_stats:
        n = s['total']
        if n == 0:
            continue
        avg_best = np.mean(s['best_hit_per_draw'])
        avg_union = np.mean(s['union_hits'])
        rate_3 = s['any_3plus'] / n * 100
        rate_2 = s['any_2plus'] / n * 100
        union_3 = s['union_3plus'] / n * 100
        
        if baseline_3plus is None:
            baseline_3plus = rate_3
            delta = "---"
        else:
            delta = f"{rate_3 - baseline_3plus:+.1f}%"
        
        print(f"{s['label']:<40} | {avg_best:>9.3f} | {avg_union:>9.3f} | {rate_3:>6.1f}% | {rate_2:>6.1f}% | {union_3:>6.1f}% | {delta:>7}")


def main():
    print("=" * 90)
    print("🎰 大樂透 115000012 期檢討 - 三段式優化回測")
    print(f"📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    
    # 載入規則 & 數據
    rules = get_lottery_rules('BIG_LOTTO')
    all_draws = db_manager.get_all_draws('BIG_LOTTO')
    all_draws.sort(key=lambda x: x['date'])  # ASC order
    
    print(f"\n📦 載入 {len(all_draws)} 期大樂透歷史數據")
    
    # 篩選測試期: 2025 年 (114) + 2026 年 (115) 全部
    test_draws = [d for d in all_draws 
                  if str(d.get('draw', '')).startswith('114') or 
                     str(d.get('draw', '')).startswith('115')]
    
    print(f"🎯 測試期數: {len(test_draws)} 期 (2025-2026)")
    
    if not test_draws:
        print("❌ 未找到 2025-2026 年數據")
        return
    
    # 初始化
    engine = UnifiedPredictionEngine()
    optimizer = MultiBetOptimizer()
    enhanced = EnhancedOrthogonal3Bet(engine, optimizer)
    
    all_phase_stats = []
    
    # =========================================
    # Phase A: Baseline (原始 Orthogonal 3-Bet)
    # =========================================
    print("\n" + "=" * 90)
    print("🅰️  Phase A: Baseline (原始 Orthogonal 3-Bet)")
    print("=" * 90)
    
    stats_a = run_rolling_backtest(
        test_draws, all_draws,
        enhanced.predict_baseline,
        rules, "Phase A: Baseline Orthogonal 3-Bet"
    )
    print_stats(stats_a)
    all_phase_stats.append(stats_a)
    
    # =========================================
    # Phase B: + Median Zone Sampler
    # =========================================
    print("\n" + "=" * 90)
    print("🅱️  Phase B: + Median Zone Sampler (中間態取樣器)")
    print("    → Bet 3 替換為 Median Zone Sampler")
    print("=" * 90)
    
    stats_b = run_rolling_backtest(
        test_draws, all_draws,
        enhanced.predict_with_median,
        rules, "Phase B: + Median Zone Sampler"
    )
    print_stats(stats_b)
    all_phase_stats.append(stats_b)
    
    # =========================================
    # Phase C: + Zone Absence Predictor
    # =========================================
    print("\n" + "=" * 90)
    print("🅲  Phase C: + Zone Absence Predictor (區間缺席預警)")
    print("    → 偵測過熱區間，過濾該區間的號碼")
    print("=" * 90)
    
    stats_c = run_rolling_backtest(
        test_draws, all_draws,
        enhanced.predict_with_zone_filter,
        rules, "Phase C: + Zone Absence Predictor"
    )
    print_stats(stats_c)
    all_phase_stats.append(stats_c)
    
    # =========================================
    # Phase D: + Repeat/Consecutive Force Include
    # =========================================
    print("\n" + "=" * 90)
    print("🅳  Phase D: + Repeat/Consecutive Force (重號/連號強制納入)")
    print("    → 在 Bet 2 中強制納入重號和連號候選")
    print("=" * 90)
    
    stats_d = run_rolling_backtest(
        test_draws, all_draws,
        enhanced.predict_full_optimization,
        rules, "Phase D: + Repeat/Consecutive Force"
    )
    print_stats(stats_d)
    all_phase_stats.append(stats_d)
    
    # =========================================
    # 對比表
    # =========================================
    compare_phases(all_phase_stats)
    
    # =========================================
    # 最近 10 期詳情 (Phase D)
    # =========================================
    print("\n" + "=" * 90)
    print("📋 Phase D 最近 10 期預測詳情")
    print("=" * 90)
    
    if stats_d['details']:
        for detail in stats_d['details'][-10:]:
            actual_str = ", ".join(f"{n:02d}" for n in detail['actual'])
            print(f"\n期號: {detail['draw_id']} | 開獎: [{actual_str}]")
            for bi, (bet, hit) in enumerate(zip(detail['bets'], detail['hits'])):
                bet_str = ", ".join(f"{n:02d}" for n in bet)
                marker = "🎯" if hit >= 3 else "✅" if hit >= 2 else "  "
                print(f"  Bet{bi+1}: [{bet_str}] → {hit} 命中 {marker}")
            print(f"  Union→ {detail['union']} 命中 | 最佳→ {detail['best']} 命中")
    
    # =========================================
    # Summary
    # =========================================
    print("\n" + "=" * 90)
    print("🏁 最終總結")
    print("=" * 90)
    
    if len(all_phase_stats) == 4 and all(s['total'] > 0 for s in all_phase_stats):
        base_rate = all_phase_stats[0]['any_3plus'] / all_phase_stats[0]['total'] * 100
        final_rate = all_phase_stats[3]['any_3plus'] / all_phase_stats[3]['total'] * 100
        improvement = final_rate - base_rate
        
        print(f"Baseline 3+ 命中率: {base_rate:.1f}%")
        print(f"Full Optimization 3+ 命中率: {final_rate:.1f}%")
        print(f"總提升: {improvement:+.1f} 百分點")
        
        if improvement > 0:
            print(f"✅ 優化有效！3+ 命中率提升 {improvement:.1f} 百分點")
        elif improvement == 0:
            print(f"⚠️ 優化無顯著效果，需要進一步調整參數")
        else:
            print(f"❌ 優化反向，需要檢視模組設計")


if __name__ == '__main__':
    main()
