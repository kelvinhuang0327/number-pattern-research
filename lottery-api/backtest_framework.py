"""
回測驗證框架 - 量化預測方法的實際表現
用於測試和比較各種預測策略的準確性
"""
import json
import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import numpy as np
from datetime import datetime

from database import DatabaseManager
from models.unified_predictor import UnifiedPredictionEngine

logger = logging.getLogger(__name__)


class BacktestFramework:
    """回測框架 - 用於驗證預測方法的實際表現"""

    def __init__(self, db_path: str = "data/lottery_v2.db"):
        """
        初始化回測框架

        Args:
            db_path: 數據庫路徑
        """
        self.db = DatabaseManager(db_path)
        self.predictor = UnifiedPredictionEngine()

        # 可用的預測方法列表
        self.available_methods = [
            'frequency',
            'trend',
            'statistical',
            'deviation',
            'hot_cold_mix',
            'entropy_transformer',
            'social_wisdom',
            'anomaly_detection',
            'quantum_random',
            'meta_learning'
        ]

        logger.info("✅ BacktestFramework initialized")

    def backtest_single_method(
        self,
        method_name: str,
        lottery_type: str,
        test_size: int = 100,
        min_history: int = 50
    ) -> Dict:
        """
        回測單一預測方法

        Args:
            method_name: 預測方法名稱
            lottery_type: 彩票類型
            test_size: 測試期數（最多測試多少期）
            min_history: 最小歷史數據期數

        Returns:
            回測結果字典
        """
        logger.info(f"🔍 開始回測方法: {method_name} (彩票: {lottery_type})")

        # 獲取所有歷史數據
        all_history = self.db.get_all_draws(lottery_type)

        if len(all_history) < min_history + test_size:
            logger.warning(
                f"⚠️ 歷史數據不足: 需要 {min_history + test_size} 期，"
                f"實際只有 {len(all_history)} 期"
            )
            test_size = max(0, len(all_history) - min_history)

        if test_size <= 0:
            return {
                'method': method_name,
                'error': '數據不足',
                'total_tests': 0
            }

        # 獲取彩票規則
        lottery_rules = self._get_lottery_rules(lottery_type)

        # 回測結果統計
        results = {
            'method': method_name,
            'lottery_type': lottery_type,
            'total_tests': test_size,
            'match_distribution': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0},
            'special_matches': 0,
            'test_details': [],
            'predictions': []
        }

        # 開始滾動回測
        for i in range(test_size):
            # 使用前 N-i 期作為訓練數據
            train_end_idx = len(all_history) - test_size + i
            train_history = all_history[train_end_idx:]

            # 實際開獎結果（第 train_end_idx 期）
            actual_draw = all_history[train_end_idx - 1]
            actual_numbers = set(actual_draw['numbers'])
            actual_special = actual_draw.get('special', 0)

            try:
                # 執行預測
                prediction = self._predict_by_method(
                    method_name,
                    train_history,
                    lottery_rules
                )

                if not prediction or 'numbers' not in prediction:
                    logger.warning(f"⚠️ 方法 {method_name} 預測失敗")
                    continue

                predicted_numbers = set(prediction['numbers'])
                predicted_special = prediction.get('special', 0)

                # 計算匹配數
                main_matches = len(actual_numbers & predicted_numbers)
                special_match = 1 if actual_special and actual_special == predicted_special else 0

                # 更新統計
                results['match_distribution'][main_matches] += 1
                results['special_matches'] += special_match

                # 記錄測試詳情（只記錄前20期，避免數據過大）
                if i < 20:
                    results['test_details'].append({
                        'draw': actual_draw['draw'],
                        'date': actual_draw['date'],
                        'actual': list(actual_numbers),
                        'predicted': list(predicted_numbers),
                        'matches': main_matches,
                        'confidence': prediction.get('confidence', 0)
                    })

                # 記錄所有預測（簡化版）
                results['predictions'].append({
                    'matches': main_matches,
                    'special_match': special_match
                })

            except Exception as e:
                logger.error(f"❌ 回測第 {i} 期時發生錯誤: {e}")
                continue

        # 計算統計指標
        results = self._calculate_statistics(results)

        logger.info(
            f"✅ {method_name} 回測完成: "
            f"勝率={results.get('win_rate', 0):.2%}, "
            f"平均匹配={results.get('avg_matches', 0):.2f}"
        )

        return results

    def _predict_by_method(
        self,
        method_name: str,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Optional[Dict]:
        """
        根據方法名稱執行預測

        Args:
            method_name: 方法名稱
            history: 歷史數據
            lottery_rules: 彩票規則

        Returns:
            預測結果
        """
        method_map = {
            'frequency': self.predictor.frequency_predict,
            'trend': self.predictor.trend_predict,
            'statistical': self.predictor.statistical_predict,
            'deviation': self.predictor.deviation_predict,
            'hot_cold_mix': self.predictor.hot_cold_mix_predict,
            'entropy_transformer': self.predictor.entropy_transformer_predict,
            'social_wisdom': self.predictor.social_wisdom_predict,
            'anomaly_detection': self.predictor.anomaly_detection_predict,
            'quantum_random': self.predictor.quantum_random_predict,
            'meta_learning': self.predictor.meta_learning_predict
        }

        predict_func = method_map.get(method_name)
        if not predict_func:
            logger.error(f"❌ 未知的預測方法: {method_name}")
            return None

        try:
            return predict_func(history, lottery_rules)
        except Exception as e:
            logger.error(f"❌ 方法 {method_name} 預測失敗: {e}")
            return None

    def _calculate_statistics(self, results: Dict) -> Dict:
        """
        計算統計指標

        Args:
            results: 原始結果

        Returns:
            添加統計指標後的結果
        """
        total_tests = results['total_tests']
        match_dist = results['match_distribution']

        if total_tests == 0:
            results['win_rate'] = 0
            results['avg_matches'] = 0
            results['expected_value'] = 0
            return results

        # 平均匹配數
        total_matches = sum(k * v for k, v in match_dist.items())
        avg_matches = total_matches / total_tests

        # 勝率（至少3個匹配）
        wins = sum(v for k, v in match_dist.items() if k >= 3)
        win_rate = wins / total_tests

        # 各匹配數的機率
        match_probabilities = {
            k: v / total_tests for k, v in match_dist.items()
        }

        # 期望值（簡化計算 - 實際需要獎金表）
        # 假設：3個=200, 4個=2000, 5個=100000, 6個=10000000
        prize_table = {
            3: 200,
            4: 2000,
            5: 100000,
            6: 10000000
        }

        expected_value = sum(
            match_probabilities.get(k, 0) * v
            for k, v in prize_table.items()
        )

        results['avg_matches'] = avg_matches
        results['win_rate'] = win_rate
        results['match_probabilities'] = match_probabilities
        results['expected_value'] = expected_value

        return results

    def compare_all_methods(
        self,
        lottery_type: str,
        test_size: int = 100,
        methods: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        對比所有預測方法

        Args:
            lottery_type: 彩票類型
            test_size: 測試期數
            methods: 要測試的方法列表（None則測試所有方法）

        Returns:
            排序後的對比結果列表
        """
        logger.info(f"🚀 開始對比所有方法 (彩票: {lottery_type})")

        methods_to_test = methods or self.available_methods
        comparison = []

        for method in methods_to_test:
            result = self.backtest_single_method(
                method,
                lottery_type,
                test_size=test_size
            )
            comparison.append(result)

        # 按勝率排序
        comparison.sort(key=lambda x: x.get('win_rate', 0), reverse=True)

        logger.info("✅ 所有方法對比完成")

        return comparison

    def generate_report(
        self,
        comparison: List[Dict],
        output_file: str = "backtest_report.md"
    ):
        """
        生成回測報告

        Args:
            comparison: 對比結果
            output_file: 輸出文件路徑
        """
        logger.info(f"📝 生成回測報告: {output_file}")

        report = []
        report.append("# 預測方法回測報告\n")
        report.append(f"**生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        if comparison:
            lottery_type = comparison[0].get('lottery_type', 'Unknown')
            test_size = comparison[0].get('total_tests', 0)
            report.append(f"**彩票類型**: {lottery_type}\n")
            report.append(f"**測試期數**: {test_size}\n\n")

        report.append("## 📊 方法對比總覽\n\n")
        report.append("| 排名 | 方法 | 勝率 | 平均匹配 | 期望值 | 0中 | 1中 | 2中 | 3中 | 4中 | 5中 | 6中 |\n")
        report.append("|------|------|------|---------|--------|-----|-----|-----|-----|-----|-----|-----|\n")

        for rank, result in enumerate(comparison, 1):
            method = result.get('method', 'Unknown')
            win_rate = result.get('win_rate', 0)
            avg_matches = result.get('avg_matches', 0)
            expected_value = result.get('expected_value', 0)
            match_dist = result.get('match_distribution', {})

            report.append(
                f"| {rank} | {method} | {win_rate:.2%} | {avg_matches:.2f} | "
                f"${expected_value:.0f} | "
                f"{match_dist.get(0, 0)} | {match_dist.get(1, 0)} | "
                f"{match_dist.get(2, 0)} | {match_dist.get(3, 0)} | "
                f"{match_dist.get(4, 0)} | {match_dist.get(5, 0)} | "
                f"{match_dist.get(6, 0)} |\n"
            )

        report.append("\n## 📈 詳細分析\n\n")

        for rank, result in enumerate(comparison, 1):
            method = result.get('method', 'Unknown')
            report.append(f"### {rank}. {method}\n\n")

            # 性能指標
            report.append("**性能指標**:\n")
            report.append(f"- 勝率（≥3中）: {result.get('win_rate', 0):.2%}\n")
            report.append(f"- 平均匹配數: {result.get('avg_matches', 0):.2f}\n")
            report.append(f"- 期望值: ${result.get('expected_value', 0):.2f}\n\n")

            # 匹配分布
            match_probs = result.get('match_probabilities', {})
            if match_probs:
                report.append("**匹配機率分布**:\n")
                for k in sorted(match_probs.keys()):
                    report.append(f"- {k}個匹配: {match_probs[k]:.2%}\n")
                report.append("\n")

            # 測試樣本（前5期）
            test_details = result.get('test_details', [])
            if test_details:
                report.append("**測試樣本** (前5期):\n\n")
                report.append("| 期號 | 日期 | 實際 | 預測 | 匹配 | 信心度 |\n")
                report.append("|------|------|------|------|------|--------|\n")

                for detail in test_details[:5]:
                    actual = ', '.join(map(str, sorted(detail.get('actual', []))))
                    predicted = ', '.join(map(str, sorted(detail.get('predicted', []))))
                    matches = detail.get('matches', 0)
                    confidence = detail.get('confidence', 0)

                    report.append(
                        f"| {detail.get('draw', '')} | {detail.get('date', '')} | "
                        f"{actual} | {predicted} | {matches} | {confidence:.2%} |\n"
                    )
                report.append("\n")

            report.append("---\n\n")

        # 寫入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(report)

        logger.info(f"✅ 回測報告已生成: {output_file}")

    def _get_lottery_rules(self, lottery_type: str) -> Dict:
        """
        獲取彩票規則

        Args:
            lottery_type: 彩票類型

        Returns:
            彩票規則字典
        """
        # 從 data/lottery_types.json 讀取規則
        try:
            with open('data/lottery_types.json', 'r', encoding='utf-8') as f:
                lottery_types = json.load(f)

            # lottery_types 是一個字典，鍵是彩票類型 ID
            if lottery_type in lottery_types:
                rules = lottery_types[lottery_type].copy()
                rules['id'] = lottery_type
                return rules

            # 如果找不到，返回預設規則
            logger.warning(f"⚠️ 找不到 {lottery_type} 的規則，使用預設規則")
            return self._get_default_rules()

        except Exception as e:
            logger.error(f"❌ 讀取彩票規則失敗: {e}")
            return self._get_default_rules()

    def _get_default_rules(self) -> Dict:
        """返回預設彩票規則"""
        return {
            'id': 'BIG_LOTTO',
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49,
            'hasSpecialNumber': True,
            'specialNumberRange': {'min': 1, 'max': 49}
        }


def main():
    """主函數 - 執行回測"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 創建回測框架
    framework = BacktestFramework()

    # 對比所有方法（大樂透）
    comparison = framework.compare_all_methods(
        lottery_type='BIG_LOTTO',
        test_size=100
    )

    # 生成報告
    framework.generate_report(
        comparison,
        output_file='lottery-api/backtest_report_all_methods.md'
    )

    print("\n✅ 回測完成！請查看 backtest_report_all_methods.md")


if __name__ == '__main__':
    main()
