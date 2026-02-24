"""
動態集成預測器 - 策略1+2整合

核心改進：
1. 動態權重調整 - 根據近期表現自動調整各策略權重
2. LSTM整合 - 將深度學習模型作為集成成員
3. 元學習 - 識別不同市場狀態並選擇最佳策略組合
4. 信心度校準 - 基於歷史準確度校準預測信心

目標：從基線 4.31% 提升至 10%+ 中獎率
"""

import numpy as np
import os
import json
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# 嘗試導入LSTM模型
try:
    from .lstm_attention_predictor import LSTMAttentionPredictor
    LSTM_AVAILABLE = True
except ImportError:
    LSTM_AVAILABLE = False
    logger.warning("LSTM模型不可用，將跳過深度學習策略")


class MarketStateDetector:
    """市場狀態檢測器 - 識別當前號碼分佈的趨勢狀態"""

    def __init__(self):
        self.state_names = ['hot_trend', 'cold_reversal', 'balanced', 'volatile', 'clustered']

    def detect_state(self, history: List[Dict], window: int = 20) -> Dict:
        """
        檢測市場狀態

        Returns:
            {
                'state': str,  # 主要狀態
                'confidence': float,  # 狀態信心度
                'metrics': dict  # 詳細指標
            }
        """
        if len(history) < window:
            return {'state': 'balanced', 'confidence': 0.5, 'metrics': {}}

        recent = history[:window]

        # 計算各項指標
        metrics = {}

        # 1. 熱號集中度 - 是否少數號碼主導
        all_nums = []
        for h in recent:
            all_nums.extend(h['numbers'])
        freq = Counter(all_nums)
        top_5_freq = sum(c for _, c in freq.most_common(5))
        total_freq = sum(freq.values())
        metrics['hot_concentration'] = top_5_freq / total_freq if total_freq > 0 else 0

        # 2. 冷號回歸率 - 長期未出現的號碼是否開始出現
        cold_nums = [n for n, c in freq.items() if c <= 1]
        metrics['cold_ratio'] = len(cold_nums) / len(freq) if freq else 0

        # 3. 區間波動 - 開獎號碼的分散程度
        zone_volatility = []
        for h in recent:
            nums = h['numbers']
            zone_dist = [0, 0, 0, 0, 0]  # 5個區間
            for n in nums:
                zone_idx = min(4, (n - 1) // 10)
                zone_dist[zone_idx] += 1
            zone_volatility.append(np.std(zone_dist))
        metrics['zone_volatility'] = np.mean(zone_volatility)

        # 4. 連續性 - 相鄰期數之間的號碼重疊
        overlaps = []
        for i in range(len(recent) - 1):
            curr = set(recent[i]['numbers'])
            prev = set(recent[i+1]['numbers'])
            overlaps.append(len(curr & prev))
        metrics['avg_overlap'] = np.mean(overlaps) if overlaps else 0

        # 5. 奇偶平衡
        odd_ratios = []
        for h in recent:
            odd_count = sum(1 for n in h['numbers'] if n % 2 == 1)
            odd_ratios.append(odd_count / len(h['numbers']))
        metrics['odd_balance'] = 1 - abs(np.mean(odd_ratios) - 0.5) * 2

        # 判斷狀態
        state = 'balanced'
        confidence = 0.6

        if metrics['hot_concentration'] > 0.35:
            state = 'hot_trend'
            confidence = 0.7 + (metrics['hot_concentration'] - 0.35)
        elif metrics['cold_ratio'] > 0.4:
            state = 'cold_reversal'
            confidence = 0.65 + metrics['cold_ratio'] * 0.3
        elif metrics['zone_volatility'] > 1.5:
            state = 'volatile'
            confidence = 0.6 + metrics['zone_volatility'] * 0.1
        elif metrics['avg_overlap'] >= 1.5:
            state = 'clustered'
            confidence = 0.65 + metrics['avg_overlap'] * 0.1
        else:
            confidence = 0.5 + metrics['odd_balance'] * 0.2

        return {
            'state': state,
            'confidence': min(0.95, confidence),
            'metrics': metrics
        }


class PerformanceTracker:
    """性能追蹤器 - 追蹤各策略的歷史表現"""

    def __init__(self, strategy_names: List[str], decay_factor: float = 0.95):
        self.strategy_names = strategy_names
        self.decay_factor = decay_factor

        # 初始化權重 (平均分配)
        self.weights = {name: 1.0 for name in strategy_names}

        # 歷史記錄
        self.history = defaultdict(list)  # {strategy: [(predicted, actual, matches), ...]}

        # 累積分數
        self.scores = defaultdict(float)

    def update(self, strategy_name: str, predicted: List[int], actual: List[int]):
        """更新策略表現"""
        matches = len(set(predicted) & set(actual))
        self.history[strategy_name].append({
            'predicted': predicted,
            'actual': actual,
            'matches': matches
        })

        # 更新分數 (匹配3個及以上得分更高)
        score_delta = 0
        if matches >= 3:
            score_delta = 100 + (matches - 3) * 50  # 中獎大幅加分
        elif matches == 2:
            score_delta = 20
        elif matches == 1:
            score_delta = 5
        else:
            score_delta = -10  # 完全未中扣分

        # 應用衰減因子
        for name in self.strategy_names:
            self.scores[name] *= self.decay_factor

        self.scores[strategy_name] += score_delta

        # 重新計算權重
        self._recalculate_weights()

    def _recalculate_weights(self):
        """重新計算各策略權重"""
        min_score = min(self.scores.values()) if self.scores else 0

        # 將分數轉換為正數
        adjusted_scores = {
            name: score - min_score + 10
            for name, score in self.scores.items()
        }

        total = sum(adjusted_scores.values())
        if total > 0:
            self.weights = {
                name: score / total
                for name, score in adjusted_scores.items()
            }

    def get_weights(self) -> Dict[str, float]:
        """獲取當前權重"""
        return dict(self.weights)

    def get_statistics(self, strategy_name: str) -> Dict:
        """獲取策略統計信息"""
        history = self.history.get(strategy_name, [])
        if not history:
            return {'total': 0, 'win_rate': 0, 'avg_matches': 0}

        total = len(history)
        wins = sum(1 for h in history if h['matches'] >= 3)
        avg_matches = np.mean([h['matches'] for h in history])

        return {
            'total': total,
            'wins': wins,
            'win_rate': wins / total if total > 0 else 0,
            'avg_matches': avg_matches
        }


class DynamicEnsemblePredictor:
    """動態集成預測器"""

    def __init__(self, model_path: Optional[str] = None):
        self.name = "DynamicEnsemble"

        # 初始化市場狀態檢測器
        self.state_detector = MarketStateDetector()

        # 定義策略池
        self.strategies = {}
        self._register_strategies()

        # 初始化性能追蹤器
        self.tracker = PerformanceTracker(list(self.strategies.keys()))

        # LSTM模型 (可選)
        self.lstm_model = None
        self.lstm_model_path = model_path
        if LSTM_AVAILABLE and model_path and os.path.exists(model_path):
            self._load_lstm_model(model_path)

        # 各市場狀態下的策略偏好
        self.state_strategy_bias = {
            'hot_trend': {
                'hot_frequency': 1.5,
                'multi_window_fusion': 1.3,
                'consecutive_friendly': 1.2,
            },
            'cold_reversal': {
                'cold_comeback': 1.6,
                'deviation_predict': 1.4,
                'gap_analysis': 1.3,
            },
            'balanced': {
                'zone_balance': 1.3,
                'constrained': 1.3,
                'ensemble_vote': 1.2,
            },
            'volatile': {
                'coverage_optimized': 1.4,
                'monte_carlo': 1.3,
                'enhanced_ensemble': 1.2,
            },
            'clustered': {
                'consecutive_friendly': 1.5,
                'pattern_match': 1.3,
                'multi_window_fusion': 1.2,
            }
        }

        # 保存配置路徑
        self.config_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'dynamic_ensemble_config.json'
        )
        self._load_config()

    def _register_strategies(self):
        """註冊所有可用策略"""
        from .enhanced_predictor import EnhancedPredictor
        from .unified_predictor import prediction_engine

        enhanced = EnhancedPredictor()

        # 註冊增強型預測器的方法
        self.strategies['consecutive_friendly'] = enhanced.consecutive_friendly_predict
        self.strategies['cold_comeback'] = enhanced.cold_number_comeback_predict
        self.strategies['constrained'] = enhanced.constrained_predict
        self.strategies['multi_window_fusion'] = enhanced.multi_window_fusion_predict
        self.strategies['coverage_optimized'] = enhanced.coverage_optimized_predict
        self.strategies['enhanced_ensemble'] = enhanced.enhanced_ensemble_predict

        # 註冊統一預測引擎的方法
        self.strategies['zone_balance'] = prediction_engine.zone_balance_predict
        self.strategies['hot_cold_mix'] = prediction_engine.hot_cold_mix_predict
        self.strategies['sum_range'] = prediction_engine.sum_range_predict
        self.strategies['trend_predict'] = prediction_engine.trend_predict
        self.strategies['bayesian'] = prediction_engine.bayesian_predict
        self.strategies['monte_carlo'] = prediction_engine.monte_carlo_predict
        self.strategies['ensemble_vote'] = prediction_engine.ensemble_predict

        # 嘗試註冊進階方法
        try:
            self.strategies['deviation_predict'] = prediction_engine.deviation_predict
        except:
            pass

    def _load_lstm_model(self, model_path: str):
        """載入LSTM模型"""
        try:
            self.lstm_model = LSTMAttentionPredictor()
            self.lstm_model.load(model_path)
            self.strategies['lstm_attention'] = self._lstm_predict
            logger.info(f"LSTM模型載入成功: {model_path}")
        except Exception as e:
            logger.warning(f"LSTM模型載入失敗: {e}")
            self.lstm_model = None

    def _lstm_predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """LSTM預測包裝器"""
        if self.lstm_model is None:
            raise ValueError("LSTM模型未載入")
        return self.lstm_model.predict(history, lottery_rules)

    def _load_config(self):
        """載入配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.tracker.weights = config.get('weights', self.tracker.weights)
                    self.tracker.scores = defaultdict(float, config.get('scores', {}))
            except:
                pass

    def _save_config(self):
        """保存配置"""
        config = {
            'weights': self.tracker.weights,
            'scores': dict(self.tracker.scores)
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def predict(self, history: List[Dict], lottery_rules: Dict,
                num_bets: int = 1) -> Dict:
        """
        動態集成預測

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則
            num_bets: 生成的注數

        Returns:
            預測結果
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 1. 檢測市場狀態
        market_state = self.state_detector.detect_state(history)
        state = market_state['state']

        # 2. 獲取基礎權重
        base_weights = self.tracker.get_weights()

        # 3. 根據市場狀態調整權重
        state_bias = self.state_strategy_bias.get(state, {})
        adjusted_weights = {}
        for name, weight in base_weights.items():
            bias = state_bias.get(name, 1.0)
            adjusted_weights[name] = weight * bias

        # 標準化權重
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            adjusted_weights = {k: v/total_weight for k, v in adjusted_weights.items()}

        # 4. 執行所有策略
        all_predictions = {}
        strategy_errors = []

        for name, strategy in self.strategies.items():
            try:
                result = strategy(history, lottery_rules)
                all_predictions[name] = result['numbers']
            except Exception as e:
                strategy_errors.append(f"{name}: {e}")
                continue

        if not all_predictions:
            raise ValueError(f"所有策略都失敗: {strategy_errors}")

        # 5. 加權投票
        number_scores = defaultdict(float)
        for name, numbers in all_predictions.items():
            weight = adjusted_weights.get(name, 0.1)
            for num in numbers:
                number_scores[num] += weight

        # 6. 生成預測結果
        if num_bets == 1:
            # 單注: 選擇得分最高的號碼
            sorted_nums = sorted(number_scores.keys(), key=lambda x: -number_scores[x])
            predicted = sorted_nums[:pick_count]

            # 計算信心度
            confidence = self._calculate_confidence(
                predicted, number_scores, len(all_predictions), market_state
            )

            # 特別號預測 (如果需要)
            special = None
            if lottery_rules.get('hasSpecialNumber', False):
                special = self._predict_special(history, lottery_rules)

            return {
                'numbers': sorted(predicted),
                'special': special,
                'confidence': confidence,
                'method': 'dynamic_ensemble',
                'market_state': state,
                'strategies_used': list(all_predictions.keys()),
                'weights': {k: round(v, 3) for k, v in adjusted_weights.items()
                           if k in all_predictions}
            }
        else:
            # 多注: 生成多組不同的預測
            return self._generate_multiple_bets(
                number_scores, all_predictions, adjusted_weights,
                lottery_rules, num_bets, market_state
            )

    def _calculate_confidence(self, predicted: List[int], scores: Dict[int, float],
                             num_strategies: int, market_state: Dict) -> float:
        """計算預測信心度"""
        # 基礎信心度: 基於投票一致性
        selected_scores = [scores[n] for n in predicted]
        avg_score = np.mean(selected_scores)
        max_possible = 1.0  # 如果所有策略都投同一個號碼

        base_confidence = avg_score / max_possible * 0.5

        # 市場狀態修正
        state_confidence = market_state.get('confidence', 0.5)

        # 策略數量修正 (更多策略參與 = 更可靠)
        strategy_factor = min(1.0, num_strategies / 10)

        # 綜合計算
        confidence = base_confidence * 0.5 + state_confidence * 0.3 + strategy_factor * 0.2

        return min(0.85, max(0.3, confidence))

    def _predict_special(self, history: List[Dict], lottery_rules: Dict) -> int:
        """預測特別號"""
        special_min = lottery_rules.get('specialMinNumber', lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber', lottery_rules.get('specialMax', 8))

        # 統計特別號頻率
        special_freq = Counter()
        for h in history[:50]:
            special = h.get('special_number') or h.get('special')
            if special is not None:
                special_freq[special] += 1

        if not special_freq:
            return (special_min + special_max) // 2

        # 混合策略: 熱號 + 冷號回歸
        hot_special = special_freq.most_common(1)[0][0]

        # 找出最近未出現的冷號
        all_specials = set(range(special_min, special_max + 1))
        recent_specials = set(
            h.get('special_number') or h.get('special')
            for h in history[:10]
            if h.get('special_number') or h.get('special')
        )
        cold_specials = all_specials - recent_specials

        if cold_specials:
            # 50% 機率選熱號, 50% 選冷號
            if np.random.random() < 0.5:
                return hot_special
            else:
                return min(cold_specials)

        return hot_special

    def _generate_multiple_bets(self, number_scores: Dict[int, float],
                                all_predictions: Dict[str, List[int]],
                                weights: Dict[str, float],
                                lottery_rules: Dict,
                                num_bets: int,
                                market_state: Dict) -> Dict:
        """生成多組預測"""
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        bets = []
        used_combos = set()

        # 策略1: 投票得分最高的組合
        sorted_by_score = sorted(number_scores.keys(), key=lambda x: -number_scores[x])
        first_bet = sorted(sorted_by_score[:pick_count])
        bets.append(first_bet)
        used_combos.add(tuple(first_bet))

        # 策略2: 各個表現最好的單一策略結果
        sorted_strategies = sorted(weights.keys(), key=lambda x: -weights[x])
        for strategy in sorted_strategies[:num_bets-1]:
            if strategy in all_predictions:
                bet = sorted(all_predictions[strategy])
                if tuple(bet) not in used_combos:
                    bets.append(bet)
                    used_combos.add(tuple(bet))

        # 策略3: 變異組合 (高分號碼的不同組合)
        top_candidates = sorted_by_score[:pick_count + 5]
        attempts = 0
        while len(bets) < num_bets and attempts < 100:
            attempts += 1
            # 加權隨機選擇
            probs = np.array([number_scores[n] for n in top_candidates])
            probs = probs / probs.sum()

            try:
                selected = np.random.choice(
                    top_candidates, size=pick_count, replace=False, p=probs
                )
                bet = sorted(selected.tolist())
                if tuple(bet) not in used_combos:
                    bets.append(bet)
                    used_combos.add(tuple(bet))
            except:
                pass

        # 補足不夠的注數
        while len(bets) < num_bets:
            # 隨機生成
            remaining = list(set(range(min_num, max_num + 1)) -
                           {n for bet in bets for n in bet})
            if len(remaining) >= pick_count:
                bet = sorted(np.random.choice(remaining, pick_count, replace=False).tolist())
            else:
                bet = sorted(np.random.choice(
                    range(min_num, max_num + 1), pick_count, replace=False
                ).tolist())
            if tuple(bet) not in used_combos:
                bets.append(bet)
                used_combos.add(tuple(bet))

        # 計算覆蓋率
        all_numbers = set()
        for bet in bets:
            all_numbers.update(bet)
        coverage = len(all_numbers) / (max_num - min_num + 1)

        return {
            'bets': bets[:num_bets],
            'coverage': coverage,
            'method': 'dynamic_ensemble_multi',
            'market_state': market_state['state'],
            'num_bets': num_bets
        }

    def update_from_result(self, predicted: Dict, actual: List[int]):
        """根據開獎結果更新策略權重"""
        # 如果有多注預測
        if 'bets' in predicted:
            # 找到匹配最好的一注
            best_matches = 0
            for bet in predicted['bets']:
                matches = len(set(bet) & set(actual))
                best_matches = max(best_matches, matches)
            # 對所有使用的策略更新 (簡化處理)
            for strategy in self.strategies.keys():
                self.tracker.update(strategy, predicted['bets'][0], actual)
        else:
            # 單注預測
            for strategy in predicted.get('strategies_used', []):
                self.tracker.update(strategy, predicted['numbers'], actual)

        # 保存配置
        self._save_config()

    def get_strategy_stats(self) -> Dict:
        """獲取所有策略的統計信息"""
        stats = {}
        for name in self.strategies.keys():
            stats[name] = self.tracker.get_statistics(name)
        return stats

    def rolling_backtest(self, draws: List[Dict], lottery_rules: Dict,
                        test_periods: int = 100) -> Dict:
        """
        滾動回測

        Args:
            draws: 所有歷史數據 (新→舊)
            lottery_rules: 彩票規則
            test_periods: 測試期數

        Returns:
            回測結果
        """
        results = []
        win_count = 0
        total_matches = 0

        print(f"\n{'='*60}")
        print(f"動態集成預測器 - 滾動回測 (測試 {test_periods} 期)")
        print(f"{'='*60}")

        for i in range(test_periods):
            target = draws[i]
            target_numbers = set(target['numbers'])

            # 使用之後的數據作為歷史
            history = draws[i + 1:]

            if len(history) < 50:
                continue

            try:
                prediction = self.predict(history, lottery_rules)
                predicted_numbers = set(prediction['numbers'])
                matches = len(predicted_numbers & target_numbers)

                total_matches += matches
                if matches >= 3:
                    win_count += 1
                    status = "WIN"
                else:
                    status = ""

                results.append({
                    'draw': target['draw'],
                    'predicted': sorted(predicted_numbers),
                    'actual': sorted(target_numbers),
                    'matches': matches,
                    'matched_nums': sorted(predicted_numbers & target_numbers),
                    'market_state': prediction.get('market_state'),
                    'confidence': prediction.get('confidence')
                })

                # 更新追蹤器
                self.update_from_result(prediction, list(target_numbers))

                if (i + 1) % 20 == 0:
                    current_win_rate = win_count / (i + 1) * 100
                    current_avg = total_matches / (i + 1)
                    print(f"進度: {i+1}/{test_periods}, "
                          f"中獎率: {current_win_rate:.2f}%, "
                          f"平均匹配: {current_avg:.3f}")

            except Exception as e:
                print(f"預測錯誤 (期號 {target['draw']}): {e}")
                continue

        test_count = len(results)
        win_rate = win_count / test_count if test_count > 0 else 0
        avg_matches = total_matches / test_count if test_count > 0 else 0

        # 按市場狀態分組統計
        state_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'matches': 0})
        for r in results:
            state = r.get('market_state', 'unknown')
            state_stats[state]['count'] += 1
            state_stats[state]['matches'] += r['matches']
            if r['matches'] >= 3:
                state_stats[state]['wins'] += 1

        return {
            'test_count': test_count,
            'win_count': win_count,
            'win_rate': win_rate,
            'avg_matches': avg_matches,
            'state_stats': dict(state_stats),
            'strategy_weights': self.tracker.get_weights(),
            'details': results
        }


# 便捷訪問
dynamic_ensemble = DynamicEnsemblePredictor()


def test_dynamic_ensemble():
    """測試動態集成預測器"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("動態集成預測器測試")
    print("=" * 80)

    # 載入數據
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據概況:")
    print(f"  總期數: {len(draws)}")
    print(f"  最新期號: {draws[0]['draw']}")

    # 創建預測器
    predictor = DynamicEnsemblePredictor()

    # 單次預測測試
    print(f"\n{'='*60}")
    print("單次預測測試")
    print(f"{'='*60}")

    history = draws[1:301]  # 使用300期歷史
    result = predictor.predict(history, rules)

    print(f"預測號碼: {result['numbers']}")
    print(f"市場狀態: {result['market_state']}")
    print(f"信心度: {result['confidence']:.2%}")
    print(f"使用策略: {len(result['strategies_used'])} 個")

    # 回測
    print(f"\n{'='*60}")
    print("開始2025年回測")
    print(f"{'='*60}")

    draws_2025 = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]

    backtest_results = predictor.rolling_backtest(
        draws=draws,
        lottery_rules=rules,
        test_periods=min(100, len(draws_2025))
    )

    print(f"\n{'='*60}")
    print("回測結果")
    print(f"{'='*60}")
    print(f"  測試期數: {backtest_results['test_count']}")
    print(f"  中獎次數: {backtest_results['win_count']}")
    print(f"  中獎率: {backtest_results['win_rate']*100:.2f}%")
    print(f"  平均匹配: {backtest_results['avg_matches']:.3f}")

    print(f"\n各市場狀態表現:")
    for state, stats in backtest_results['state_stats'].items():
        if stats['count'] > 0:
            state_win_rate = stats['wins'] / stats['count'] * 100
            state_avg = stats['matches'] / stats['count']
            print(f"  {state}: {stats['count']}期, "
                  f"中獎率 {state_win_rate:.1f}%, 平均匹配 {state_avg:.2f}")

    print(f"\n最終策略權重:")
    weights = backtest_results['strategy_weights']
    for name, weight in sorted(weights.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {weight:.3f}")

    return backtest_results


if __name__ == '__main__':
    test_dynamic_ensemble()
