#!/usr/bin/env python3
"""
威力彩 (POWER_LOTTO) 方法組合優化分析工具
目標: 找到能達到 20%+ 成功率的 2注 和 4注 策略組合
"""

import sys
import os
import json
import logging
from typing import List, Dict, Tuple
from collections import defaultdict
from itertools import combinations
import numpy as np

# 設置路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from common import get_lottery_rules

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PowerLottoOptimizer:
    """威力彩方法組合優化器"""
    
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        self.lottery_type = 'POWER_LOTTO'
        self.lottery_rules = get_lottery_rules(self.lottery_type)
        
        # 所有可用方法及其最佳窗口配置
        self.available_methods = {
            'zone_balance_400': {'method': 'zone_balance', 'window': 400},
            'zone_balance_500': {'method': 'zone_balance', 'window': 500},
            'bayesian_300': {'method': 'bayesian', 'window': 300},
            'bayesian_400': {'method': 'bayesian', 'window': 400},
            'trend_250': {'method': 'trend', 'window': 250},
            'trend_300': {'method': 'trend', 'window': 300},
            'frequency_100': {'method': 'frequency', 'window': 100},
            'frequency_150': {'method': 'frequency', 'window': 150},
            'hot_cold_100': {'method': 'hot_cold', 'window': 100},
            'hot_cold_150': {'method': 'hot_cold', 'window': 150},
            'monte_carlo_200': {'method': 'monte_carlo', 'window': 200},
            'monte_carlo_300': {'method': 'monte_carlo', 'window': 300},
            'deviation_200': {'method': 'deviation', 'window': 200},
        }
    
    def calculate_matches(self, predicted: List[int], actual: List[int]) -> int:
        """計算匹配數字"""
        return len(set(predicted) & set(actual))
    
    def run_single_method_backtest(self, method_key: str, history: List[Dict], 
                                   test_draws: List[Tuple[int, Dict]], all_draws: List[Dict]) -> Dict:
        """
        對單個方法進行回測
        
        Returns:
            {
                'method': str,
                'window': int,
                'win_count': int,      # 3+ matches
                'avg_matches': float,
                'match_distribution': {0: count, 1: count, ...},
                'special_hits': int,
                'hit_rate': float
            }
        """
        method_info = self.available_methods[method_key]
        method_name = method_info['method']
        window = method_info['window']
        
        match_dist = {i: 0 for i in range(7)}
        special_hits = 0
        win_count = 0  # 3+ matches
        total_matches = 0
        
        for target_idx, target_draw in test_draws:
            # 獲取該期之前的歷史數據
            available_history = all_draws[target_idx + 1:]
            if len(available_history) < window:
                continue
            
            # 取指定窗口大小的數據
            history_window = available_history[:window]
            
            try:
                # 執行預測
                if method_name == 'zone_balance':
                    result = self.engine.zone_balance_predict(history_window, self.lottery_rules)
                elif method_name == 'bayesian':
                    result = self.engine.bayesian_predict(history_window, self.lottery_rules)
                elif method_name == 'trend':
                    result = self.engine.trend_predict(history_window, self.lottery_rules)
                elif method_name == 'frequency':
                    result = self.engine.frequency_predict(history_window, self.lottery_rules)
                elif method_name == 'hot_cold':
                    result = self.engine.hot_cold_mix_predict(history_window, self.lottery_rules)
                elif method_name == 'monte_carlo':
                    result = self.engine.monte_carlo_predict(history_window, self.lottery_rules)
                elif method_name == 'deviation':
                    result = self.engine.deviation_predict(history_window, self.lottery_rules)
                else:
                    continue
                
                # 計算匹配
                predicted = set(result['numbers'])
                actual = set(target_draw['numbers'])
                matches = len(predicted & actual)
                
                # 特別號
                pred_special = result.get('special')
                actual_special = target_draw.get('special')
                if pred_special == actual_special:
                    special_hits += 1
                
                # 統計
                match_dist[matches] += 1
                total_matches += matches
                if matches >= 3:
                    win_count += 1
                    
            except Exception as e:
                logger.warning(f"Error predicting {target_draw['draw']}: {e}")
                continue
        
        total_tests = sum(match_dist.values())
        hit_rate = win_count / total_tests if total_tests > 0 else 0
        avg_matches = total_matches / total_tests if total_tests > 0 else 0
        
        return {
            'method': method_key,
            'base_method': method_name,
            'window': window,
            'win_count': win_count,
            'avg_matches': avg_matches,
            'match_distribution': match_dist,
            'special_hits': special_hits,
            'total_tests': total_tests,
            'hit_rate': hit_rate
        }
    
    def run_dual_bet_backtest(self, method1_key: str, method2_key: str,
                              test_draws: List[Tuple[int, Dict]], all_draws: List[Dict]) -> Dict:
        """
        測試 2注 組合策略
        計算 P(至少一注中3個以上) = 1 - (1-P1) * (1-P2)
        """
        method1_info = self.available_methods[method1_key]
        method2_info = self.available_methods[method2_key]
        
        win_count = 0
        total_matches_dist = defaultdict(int)  # 追蹤最高匹配數
        special_hits = 0
        
        for target_idx, target_draw in test_draws:
            available_history = all_draws[target_idx + 1:]
            
            win_this_draw = False
            best_matches = 0
            best_special = False
            
            for method_info in [method1_info, method2_info]:
                window = method_info['window']
                if len(available_history) < window:
                    continue
                
                history_window = available_history[:window]
                
                try:
                    method_name = method_info['method']
                    
                    if method_name == 'zone_balance':
                        result = self.engine.zone_balance_predict(history_window, self.lottery_rules)
                    elif method_name == 'bayesian':
                        result = self.engine.bayesian_predict(history_window, self.lottery_rules)
                    elif method_name == 'trend':
                        result = self.engine.trend_predict(history_window, self.lottery_rules)
                    elif method_name == 'frequency':
                        result = self.engine.frequency_predict(history_window, self.lottery_rules)
                    elif method_name == 'hot_cold':
                        result = self.engine.hot_cold_mix_predict(history_window, self.lottery_rules)
                    elif method_name == 'monte_carlo':
                        result = self.engine.monte_carlo_predict(history_window, self.lottery_rules)
                    elif method_name == 'deviation':
                        result = self.engine.deviation_predict(history_window, self.lottery_rules)
                    else:
                        continue
                    
                    predicted = set(result['numbers'])
                    actual = set(target_draw['numbers'])
                    matches = len(predicted & actual)
                    
                    # 特別號
                    pred_special = result.get('special')
                    actual_special = target_draw.get('special')
                    
                    if matches > best_matches:
                        best_matches = matches
                    
                    if pred_special == actual_special:
                        best_special = True
                    
                    if matches >= 3:
                        win_this_draw = True
                        
                except Exception as e:
                    continue
            
            if win_this_draw:
                win_count += 1
            total_matches_dist[best_matches] += 1
            if best_special:
                special_hits += 1
        
        total_tests = sum(total_matches_dist.values())
        hit_rate = win_count / total_tests if total_tests > 0 else 0
        avg_matches = sum(k*v for k,v in total_matches_dist.items()) / total_tests if total_tests > 0 else 0
        
        return {
            'method1': method1_key,
            'method2': method2_key,
            'win_count': win_count,
            'avg_matches': avg_matches,
            'match_distribution': dict(total_matches_dist),
            'special_hits': special_hits,
            'total_tests': total_tests,
            'hit_rate': hit_rate
        }
    
    def run_quad_bet_backtest(self, methods: Tuple[str, str, str, str],
                              test_draws: List[Tuple[int, Dict]], all_draws: List[Dict]) -> Dict:
        """
        測試 4注 組合策略
        """
        win_count = 0
        total_matches_dist = defaultdict(int)
        special_hits = 0
        
        for target_idx, target_draw in test_draws:
            available_history = all_draws[target_idx + 1:]
            
            win_this_draw = False
            best_matches = 0
            best_special = False
            
            for method_key in methods:
                method_info = self.available_methods[method_key]
                window = method_info['window']
                
                if len(available_history) < window:
                    continue
                
                history_window = available_history[:window]
                
                try:
                    method_name = method_info['method']
                    
                    if method_name == 'zone_balance':
                        result = self.engine.zone_balance_predict(history_window, self.lottery_rules)
                    elif method_name == 'bayesian':
                        result = self.engine.bayesian_predict(history_window, self.lottery_rules)
                    elif method_name == 'trend':
                        result = self.engine.trend_predict(history_window, self.lottery_rules)
                    elif method_name == 'frequency':
                        result = self.engine.frequency_predict(history_window, self.lottery_rules)
                    elif method_name == 'hot_cold':
                        result = self.engine.hot_cold_mix_predict(history_window, self.lottery_rules)
                    elif method_name == 'monte_carlo':
                        result = self.engine.monte_carlo_predict(history_window, self.lottery_rules)
                    elif method_name == 'deviation':
                        result = self.engine.deviation_predict(history_window, self.lottery_rules)
                    else:
                        continue
                    
                    predicted = set(result['numbers'])
                    actual = set(target_draw['numbers'])
                    matches = len(predicted & actual)
                    
                    pred_special = result.get('special')
                    actual_special = target_draw.get('special')
                    
                    if matches > best_matches:
                        best_matches = matches
                    
                    if pred_special == actual_special:
                        best_special = True
                    
                    if matches >= 3:
                        win_this_draw = True
                        
                except Exception as e:
                    continue
            
            if win_this_draw:
                win_count += 1
            total_matches_dist[best_matches] += 1
            if best_special:
                special_hits += 1
        
        total_tests = sum(total_matches_dist.values())
        hit_rate = win_count / total_tests if total_tests > 0 else 0
        avg_matches = sum(k*v for k,v in total_matches_dist.items()) / total_tests if total_tests > 0 else 0
        
        return {
            'methods': methods,
            'win_count': win_count,
            'avg_matches': avg_matches,
            'match_distribution': dict(total_matches_dist),
            'special_hits': special_hits,
            'total_tests': total_tests,
            'hit_rate': hit_rate
        }
    
    def optimize(self):
        """執行完整優化流程"""
        # 加載數據
        all_draws = db_manager.get_all_draws(self.lottery_type)
        if not all_draws:
            logger.error("❌ 未找到威力彩數據")
            return
        
        logger.info(f"📊 已加載 {len(all_draws)} 期威力彩數據")
        
        # 篩選 2025 年數據
        test_draws = []
        for i, draw in enumerate(all_draws):
            if '2025' in str(draw.get('date', '')):
                test_draws.append((i, draw))
        
        if not test_draws:
            logger.error("❌ 未找到 2025 年數據")
            return
        
        logger.info(f"📊 測試集: {len(test_draws)} 期 (2025年)")
        
        # ========== STEP 1: 評估單個方法 ==========
        logger.info("\n" + "="*80)
        logger.info("STEP 1: 評估單個方法 (Single Method Baseline)")
        logger.info("="*80)
        
        single_results = {}
        for method_key in sorted(self.available_methods.keys()):
            result = self.run_single_method_backtest(method_key, all_draws, test_draws, all_draws)
            single_results[method_key] = result
            
            logger.info(f"\n📌 {method_key}")
            logger.info(f"   命中率 (3+): {result['hit_rate']:.2%}")
            logger.info(f"   平均匹配: {result['avg_matches']:.2f}")
            logger.info(f"   特別號: {result['special_hits']}/{result['total_tests']}")
            logger.info(f"   分佈: {result['match_distribution']}")
        
        # ========== STEP 2: 尋找最佳 2注 組合 ==========
        logger.info("\n" + "="*80)
        logger.info("STEP 2: 優化 2注 組合策略 (目標: 20%+)")
        logger.info("="*80)
        
        top_2bet_strategies = []
        method_keys = list(self.available_methods.keys())
        
        # 只測試相關性低的組合 (加速)
        for i, method1 in enumerate(method_keys):
            for method2 in method_keys[i+1:]:
                # 跳過過於相似的組合
                m1_base = self.available_methods[method1]['method']
                m2_base = self.available_methods[method2]['method']
                if m1_base == m2_base:  # 同方法不同窗口時，只取最大窗口
                    continue
                
                result = self.run_dual_bet_backtest(method1, method2, test_draws, all_draws)
                result['strategy_name'] = f"{method1} + {method2}"
                top_2bet_strategies.append(result)
        
        # 按命中率排序
        top_2bet_strategies.sort(key=lambda x: x['hit_rate'], reverse=True)
        
        logger.info(f"\n✅ 2注 組合 TOP 10 (按命中率排序):")
        for rank, strategy in enumerate(top_2bet_strategies[:10], 1):
            logger.info(f"\n   #{rank} {strategy['strategy_name']}")
            logger.info(f"      命中率: {strategy['hit_rate']:.2%} {'🎯' if strategy['hit_rate'] >= 0.20 else ''}")
            logger.info(f"      平均匹配: {strategy['avg_matches']:.2f}")
            logger.info(f"      特別號: {strategy['special_hits']}/{strategy['total_tests']}")
        
        # ========== STEP 3: 尋找最佳 4注 組合 ==========
        logger.info("\n" + "="*80)
        logger.info("STEP 3: 優化 4注 組合策略 (目標: 20%+)")
        logger.info("="*80)
        
        top_4bet_strategies = []
        
        # 選擇表現最好的方法進行 4注組合
        top_methods = sorted(single_results.items(), 
                            key=lambda x: x[1]['hit_rate'], 
                            reverse=True)[:8]
        top_method_keys = [k for k, v in top_methods]
        
        logger.info(f"   測試 4注組合... (基於 TOP 8 單個方法)")
        
        # 生成 4注組合
        tested_combinations = 0
        for method_tuple in combinations(top_method_keys, 4):
            result = self.run_quad_bet_backtest(method_tuple, test_draws, all_draws)
            result['strategy_name'] = " + ".join(method_tuple)
            top_4bet_strategies.append(result)
            tested_combinations += 1
        
        # 按命中率排序
        top_4bet_strategies.sort(key=lambda x: x['hit_rate'], reverse=True)
        
        logger.info(f"   測試了 {tested_combinations} 個 4注組合\n")
        logger.info(f"✅ 4注 組合 TOP 10 (按命中率排序):")
        for rank, strategy in enumerate(top_4bet_strategies[:10], 1):
            methods_str = " + ".join(strategy['methods'])
            logger.info(f"\n   #{rank} {methods_str}")
            logger.info(f"      命中率: {strategy['hit_rate']:.2%} {'🎯' if strategy['hit_rate'] >= 0.20 else ''}")
            logger.info(f"      平均匹配: {strategy['avg_matches']:.2f}")
            logger.info(f"      特別號: {strategy['special_hits']}/{strategy['total_tests']}")
        
        # ========== STEP 4: 生成報告 ==========
        logger.info("\n" + "="*80)
        logger.info("STEP 4: 最優策略總結")
        logger.info("="*80)
        
        best_2bet = top_2bet_strategies[0] if top_2bet_strategies else None
        best_4bet = top_4bet_strategies[0] if top_4bet_strategies else None
        
        if best_2bet:
            logger.info(f"\n🏆 最佳 2注 策略:")
            logger.info(f"   組合: {best_2bet['strategy_name']}")
            logger.info(f"   命中率: {best_2bet['hit_rate']:.2%}")
            logger.info(f"   成本: $200 (2 × $100)")
            logger.info(f"   期望成本/中獎: ${200 / best_2bet['hit_rate']:.0f}" if best_2bet['hit_rate'] > 0 else "")
        
        if best_4bet:
            logger.info(f"\n🏆 最佳 4注 策略:")
            logger.info(f"   組合: {' + '.join(best_4bet['methods'])}")
            logger.info(f"   命中率: {best_4bet['hit_rate']:.2%}")
            logger.info(f"   成本: $400 (4 × $100)")
            logger.info(f"   期望成本/中獎: ${400 / best_4bet['hit_rate']:.0f}" if best_4bet['hit_rate'] > 0 else "")
        
        # 匯總達到 20%+ 的策略
        goal_achieved_2bet = [s for s in top_2bet_strategies if s['hit_rate'] >= 0.20]
        goal_achieved_4bet = [s for s in top_4bet_strategies if s['hit_rate'] >= 0.20]
        
        logger.info(f"\n📈 目標達成 (20%+):")
        logger.info(f"   2注策略達成: {len(goal_achieved_2bet)} 個")
        logger.info(f"   4注策略達成: {len(goal_achieved_4bet)} 個")
        
        # 保存詳細結果
        results_file = 'power_lotto_optimization_results.json'
        with open(results_file, 'w') as f:
            json.dump({
                'single_methods': {k: {
                    'hit_rate': v['hit_rate'],
                    'avg_matches': v['avg_matches'],
                    'match_distribution': v['match_distribution']
                } for k, v in single_results.items()},
                'best_2bet_strategies': top_2bet_strategies[:10],
                'best_4bet_strategies': top_4bet_strategies[:10],
                'goal_achieved': {
                    'two_bet_count': len(goal_achieved_2bet),
                    'four_bet_count': len(goal_achieved_4bet)
                }
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✅ 詳細結果已保存至: {results_file}")


if __name__ == '__main__':
    optimizer = PowerLottoOptimizer()
    optimizer.optimize()
