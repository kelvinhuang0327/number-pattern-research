"""
增強型雙注預測器 (Enhanced Dual Bet Predictor)

整合負向排除機制的完整預測方案：
1. 計算並輸出廢號（負向排除）
2. 驗證歷史排除成功率
3. 生成兩組預測號碼
4. 識別膽碼

使用方式：
    from models.enhanced_dual_bet_predictor import EnhancedDualBetPredictor

    predictor = EnhancedDualBetPredictor()
    result = predictor.predict('BIG_LOTTO')

    print(result['excluded_numbers'])  # 廢號
    print(result['bet1'])              # 第一注
    print(result['bet2'])              # 第二注
    print(result['core_numbers'])      # 膽碼
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from collections import Counter
import json
from datetime import datetime

from database import DatabaseManager
from common import get_lottery_rules
from models.negative_selector import NegativeSelector
from models.unified_predictor import prediction_engine


class EnhancedDualBetPredictor:
    """增強型雙注預測器"""

    # 各彩種的最佳雙注策略配置
    DUAL_BET_CONFIGS = {
        'BIG_LOTTO': {
            'bet1': {
                'name': 'zone_balance',
                'window': 500,
                'method': 'zone_balance_predict',
                'description': '穩定型 (區間平衡)',
            },
            'bet2': {
                'name': 'bayesian',
                'window': 300,
                'method': 'bayesian_predict',
                'description': '大獎型 (貝葉斯分析)',
            },
            'backtest_win_rate': 6.78,
            'backtest_big_win_rate': 0.85,
        },
        'POWER_LOTTO': {
            'bet1': {
                'name': 'ensemble',
                'window': 100,
                'method': 'ensemble_predict',
                'description': '穩定型 (集成預測)',
            },
            'bet2': {
                'name': 'zone_balance',
                'window': 200,
                'method': 'zone_balance_predict',
                'description': '平衡型 (區間平衡)',
            },
            'backtest_win_rate': 8.42,
            'backtest_big_win_rate': 1.05,
        },
        'DAILY_539': {
            'bet1': {
                'name': 'sum_range',
                'window': 300,
                'method': 'sum_range_predict',
                'description': '穩定型 (和值範圍)',
            },
            'bet2': {
                'name': 'bayesian',
                'window': 300,
                'method': 'bayesian_predict',
                'description': '統計型 (貝葉斯分析)',
            },
            'backtest_win_rate': 27.62,
            'backtest_big_win_rate': 0.64,
        },
    }

    def __init__(self, db_path: Optional[str] = None):
        """初始化預測器"""
        self.db = DatabaseManager(db_path=db_path) if db_path else DatabaseManager()
        self.negative_selector = NegativeSelector()

    def predict(self, lottery_type: str, apply_exclusion: bool = True) -> Dict:
        """
        執行完整的雙注預測

        Args:
            lottery_type: 彩種類型 (BIG_LOTTO, POWER_LOTTO, DAILY_539)
            apply_exclusion: 是否應用負向排除過濾

        Returns:
            完整預測結果，包含:
            - excluded_numbers: 廢號列表
            - exclusion_validation: 排除機制驗證結果
            - bet1: 第一注號碼
            - bet2: 第二注號碼
            - core_numbers: 膽碼（兩注都有的號碼）
            - coverage: 覆蓋分析
            - metadata: 元數據
        """
        # 獲取歷史數據
        history = self.db.get_all_draws(lottery_type)
        rules = get_lottery_rules(lottery_type)

        if len(history) < 100:
            raise ValueError(f"數據不足: {lottery_type} 只有 {len(history)} 期")

        # 獲取配置
        config = self.DUAL_BET_CONFIGS.get(lottery_type)
        if not config:
            raise ValueError(f"不支援的彩種: {lottery_type}")

        latest = history[0]

        # === 負向排除分析 ===
        exclusion_result = self.negative_selector.analyze(history, lottery_type)
        excluded_set = set(exclusion_result['excluded_numbers'])

        # 驗證排除準確率
        validation = self.negative_selector.validate_exclusion(
            history, lottery_type, test_periods=min(100, len(history) // 2)
        )

        # === 生成預測 ===
        bet1_config = config['bet1']
        bet2_config = config['bet2']

        # 第一注
        method1 = getattr(prediction_engine, bet1_config['method'])
        result1 = method1(history[:bet1_config['window']], rules)
        bet1_raw = list(result1['numbers'])

        # 第二注
        method2 = getattr(prediction_engine, bet2_config['method'])
        result2 = method2(history[:bet2_config['window']], rules)
        bet2_raw = list(result2['numbers'])

        # === 應用負向排除 ===
        if apply_exclusion and excluded_set:
            bet1 = self.negative_selector.filter_prediction(
                bet1_raw, excluded_set, history, rules['maxNumber']
            )
            bet2 = self.negative_selector.filter_prediction(
                bet2_raw, excluded_set, history, rules['maxNumber']
            )
        else:
            bet1 = sorted(bet1_raw)
            bet2 = sorted(bet2_raw)

        # === 分析 ===
        core_numbers = sorted(set(bet1) & set(bet2))
        all_numbers = set(bet1) | set(bet2)
        coverage = len(all_numbers) / rules['maxNumber'] * 100

        # 計算下一期期號
        current_draw = latest['draw']
        year = int(current_draw[:3])
        seq = int(current_draw[3:])
        next_draw = f"{year}{seq + 1:06d}"

        return {
            'lottery_type': lottery_type,
            'lottery_name': self._get_lottery_name(lottery_type),
            'next_draw': next_draw,
            'prediction_time': datetime.now().isoformat(),

            # 負向排除
            'negative_selection': {
                'excluded_numbers': exclusion_result['excluded_numbers'],
                'excluded_count': len(exclusion_result['excluded_numbers']),
                'cold_numbers': exclusion_result['cold_numbers'],
                'overdue_numbers': exclusion_result['overdue_numbers'],
                'validation': {
                    'test_periods': validation['test_periods'],
                    'accuracy': validation['accuracy_pct'],
                    'avg_excluded_per_draw': round(validation['avg_excluded_per_draw'], 1),
                    'correct_excluded': validation['correct_excluded'],
                    'false_excluded': validation['false_excluded'],
                },
            },

            # 預測結果
            'bet1': {
                'numbers': bet1,
                'method': bet1_config['name'],
                'window': bet1_config['window'],
                'description': bet1_config['description'],
                'raw_numbers': bet1_raw,
                'filtered': bet1 != sorted(bet1_raw),
            },
            'bet2': {
                'numbers': bet2,
                'method': bet2_config['name'],
                'window': bet2_config['window'],
                'description': bet2_config['description'],
                'raw_numbers': bet2_raw,
                'filtered': bet2 != sorted(bet2_raw),
            },

            # 分析
            'analysis': {
                'core_numbers': core_numbers,
                'core_count': len(core_numbers),
                'total_coverage': len(all_numbers),
                'coverage_pct': round(coverage, 1),
            },

            # 回測數據
            'backtest': {
                'win_rate': config['backtest_win_rate'],
                'big_win_rate': config['backtest_big_win_rate'],
                'periods_per_win': round(100 / config['backtest_win_rate'], 1),
            },

            # 數據來源
            'data_source': {
                'latest_draw': latest['draw'],
                'latest_date': latest['date'],
                'total_history': len(history),
            },
        }

    def _get_lottery_name(self, lottery_type: str) -> str:
        """獲取彩種中文名稱"""
        names = {
            'BIG_LOTTO': '大樂透',
            'POWER_LOTTO': '威力彩',
            'DAILY_539': '今彩539',
        }
        return names.get(lottery_type, lottery_type)

    def format_prediction(self, result: Dict) -> str:
        """格式化預測結果為易讀字串"""
        ns = result['negative_selection']
        b1 = result['bet1']
        b2 = result['bet2']
        analysis = result['analysis']
        bt = result['backtest']

        output = f"""
{'=' * 65}
🎱 {result['lottery_name']} 雙注預測 - 第 {result['next_draw']} 期
{'=' * 65}

📋 負向排除分析 (Negative Selection)
{'-' * 65}
  🚫 廢號 ({ns['excluded_count']}個): {ns['excluded_numbers']}
  📊 歷史驗證: {ns['validation']['accuracy']} 準確率
     (測試 {ns['validation']['test_periods']} 期, 每期平均排除 {ns['validation']['avg_excluded_per_draw']} 個)

🎯 預測號碼
{'-' * 65}
  第 1 注 [{b1['description']}]
    號碼: {b1['numbers']}
    方法: {b1['method']} ({b1['window']}期)
    {'⚡ 已過濾廢號' if b1['filtered'] else ''}

  第 2 注 [{b2['description']}]
    號碼: {b2['numbers']}
    方法: {b2['method']} ({b2['window']}期)
    {'⚡ 已過濾廢號' if b2['filtered'] else ''}

📊 分析
{'-' * 65}
  💎 膽碼: {analysis['core_numbers'] if analysis['core_numbers'] else '無'}
  📈 覆蓋: {analysis['total_coverage']} 個號碼 ({analysis['coverage_pct']}%)

📉 回測數據
{'-' * 65}
  中獎率: {bt['win_rate']}% (每 {bt['periods_per_win']} 期中 1 次)
  大獎率: {bt['big_win_rate']}% (中4個以上)

📅 數據來源: {result['data_source']['latest_draw']} ({result['data_source']['latest_date']})
{'=' * 65}
"""
        return output


# 便捷函數
def predict_dual_bet(lottery_type: str = 'BIG_LOTTO') -> Dict:
    """快速執行雙注預測"""
    predictor = EnhancedDualBetPredictor()
    return predictor.predict(lottery_type)


def print_prediction(lottery_type: str = 'BIG_LOTTO'):
    """打印預測結果"""
    predictor = EnhancedDualBetPredictor()
    result = predictor.predict(lottery_type)
    print(predictor.format_prediction(result))
    return result


if __name__ == '__main__':
    # 測試
    for lt in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
        try:
            print_prediction(lt)
        except Exception as e:
            print(f"{lt} 預測失敗: {e}")
