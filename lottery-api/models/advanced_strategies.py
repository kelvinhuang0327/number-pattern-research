"""
高級預測策略模塊
新增 5 種利用 Python 強大計算能力的高級預測方法

策略列表：
1. entropy_analysis - 信息熵分析
2. clustering - 號碼聚類
3. dynamic_ensemble - 動態權重集成
4. temporal_enhanced - 增強時間序列
5. feature_engineering - 多維特徵工程
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import logging
from scipy import stats
from scipy.fft import fft, fftfreq
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class AdvancedStrategies:
    """
    高級預測策略集合
    利用 Python 強大的數據科學庫實現更複雜的預測算法
    """

    def __init__(self, prediction_engine=None):
        """
        初始化高級策略

        Args:
            prediction_engine: 統一預測引擎實例（用於存取共享狀態）
        """
        self.prediction_engine = prediction_engine
        self.scaler = StandardScaler()
        self.strategy_weights = {}  # 動態權重緩存
        logger.info("AdvancedStrategies 初始化完成")

    # ===========================================================================
    # 策略 1: 信息熵分析
    # ===========================================================================
    def entropy_analysis_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        信息熵分析策略

        原理：
        1. 計算每個號碼的出現概率分佈
        2. 計算系統的信息熵 H(X) = -Σ p(x) log p(x)
        3. 計算條件熵 H(X|Y) 發現號碼間的依賴關係
        4. 選擇「熵貢獻」最高的號碼（最具不確定性但有規律的號碼）

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        try:
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            if len(history) < 30:
                raise ValueError("數據不足，至少需要 30 期")

            # 1. 計算基礎頻率分佈
            all_numbers = []
            for draw in history:
                all_numbers.extend(draw['numbers'])

            freq = Counter(all_numbers)
            total = len(all_numbers)

            # 計算每個號碼的概率
            prob_dist = {}
            for num in range(min_num, max_num + 1):
                prob_dist[num] = freq.get(num, 0) / total if total > 0 else 0

            # 2. 計算系統熵
            system_entropy = self._calculate_entropy(list(prob_dist.values()))

            # 3. 計算每個號碼的「熵貢獻」
            entropy_scores = {}
            for num in range(min_num, max_num + 1):
                # 條件熵：計算該號碼出現後，下一期其他號碼的不確定性
                conditional_entropy = self._calculate_conditional_entropy(
                    history, num, min_num, max_num
                )

                # 互信息：系統熵 - 條件熵（越高表示該號碼越有「規律性」）
                mutual_info = system_entropy - conditional_entropy

                # 綜合評分：頻率 + 互信息貢獻
                freq_score = prob_dist[num]
                entropy_scores[num] = 0.6 * freq_score + 0.4 * (mutual_info / (system_entropy + 1e-10))

            # 4. 近期熵趨勢分析（近 20 期 vs 全局）
            recent_history = history[-20:]
            recent_numbers = [n for d in recent_history for n in d['numbers']]
            recent_freq = Counter(recent_numbers)
            recent_total = len(recent_numbers)

            for num in range(min_num, max_num + 1):
                recent_prob = recent_freq.get(num, 0) / recent_total if recent_total > 0 else 0

                # 熵變化率：近期概率變化
                change_rate = recent_prob - prob_dist[num]

                # 上升趨勢的號碼加分
                if change_rate > 0:
                    entropy_scores[num] *= (1 + change_rate * 2)

            # 5. 選擇得分最高的號碼
            sorted_numbers = sorted(entropy_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = sorted([num for num, _ in sorted_numbers[:pick_count]])

            # 計算信心度
            top_scores = [score for _, score in sorted_numbers[:pick_count]]
            confidence = float(np.mean(top_scores)) if top_scores else 0.5

            return {
                'numbers': predicted,
                'confidence': min(0.95, max(0.3, confidence * 1.5)),
                'method': '信息熵分析',
                'report': f'系統熵: {system_entropy:.4f}，選擇熵貢獻最高的號碼',
                'details': {
                    'system_entropy': float(system_entropy),
                    'top_entropy_scores': dict(sorted_numbers[:10])
                }
            }

        except Exception as e:
            logger.error(f"信息熵分析失敗: {str(e)}", exc_info=True)
            raise

    def _calculate_entropy(self, probabilities: List[float]) -> float:
        """計算信息熵 H(X) = -Σ p(x) log2 p(x)"""
        entropy = 0.0
        for p in probabilities:
            if p > 0:
                entropy -= p * np.log2(p)
        return entropy

    def _calculate_conditional_entropy(
        self,
        history: List[Dict],
        target_num: int,
        min_num: int,
        max_num: int
    ) -> float:
        """計算條件熵 H(X|target_num)"""
        # 找出目標號碼出現後的下一期分佈
        next_draw_numbers = []
        for i, draw in enumerate(history[:-1]):
            if target_num in draw['numbers']:
                next_draw_numbers.extend(history[i + 1]['numbers'])

        if not next_draw_numbers:
            return 0.0

        freq = Counter(next_draw_numbers)
        total = len(next_draw_numbers)
        probs = [freq.get(n, 0) / total for n in range(min_num, max_num + 1)]
        return self._calculate_entropy(probs)

    # ===========================================================================
    # 策略 2: 號碼聚類
    # ===========================================================================
    def clustering_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        號碼聚類策略

        原理：
        1. 將歷史開獎轉換為特徵向量
        2. 使用 K-Means 聚類發現號碼組合模式
        3. 從每個「活躍聚類」中選擇代表性號碼
        4. 結合頻率和聚類權重選擇最終號碼

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        try:
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            if len(history) < 50:
                raise ValueError("數據不足，至少需要 50 期進行聚類分析")

            # 1. 為每個號碼創建特徵向量
            number_features = self._create_number_features(history, min_num, max_num)

            # 2. 標準化特徵
            feature_matrix = np.array([number_features[n] for n in range(min_num, max_num + 1)])
            feature_matrix_scaled = self.scaler.fit_transform(feature_matrix)

            # 3. 使用 K-Means 聚類
            n_clusters = min(8, len(history) // 10)  # 動態決定聚類數
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(feature_matrix_scaled)

            # 4. 計算每個聚類的「活躍度」
            cluster_activity = self._calculate_cluster_activity(
                history[-30:], cluster_labels, min_num, max_num
            )

            # 5. 從每個活躍聚類選擇號碼
            cluster_scores = {}
            for num in range(min_num, max_num + 1):
                cluster = cluster_labels[num - min_num]
                activity = cluster_activity.get(cluster, 0)

                # 計算該號碼的聚類內得分
                # 距離聚類中心越近 + 聚類越活躍 = 得分越高
                distance_to_center = np.linalg.norm(
                    feature_matrix_scaled[num - min_num] - kmeans.cluster_centers_[cluster]
                )
                proximity_score = 1 / (1 + distance_to_center)

                cluster_scores[num] = activity * proximity_score

            # 6. 結合頻率分數
            all_numbers = [n for d in history[-50:] for n in d['numbers']]
            freq = Counter(all_numbers)
            max_freq = max(freq.values()) if freq else 1

            final_scores = {}
            for num in range(min_num, max_num + 1):
                freq_score = freq.get(num, 0) / max_freq
                final_scores[num] = 0.5 * cluster_scores[num] + 0.5 * freq_score

            # 7. 選擇得分最高的號碼
            sorted_numbers = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = sorted([num for num, _ in sorted_numbers[:pick_count]])

            # 計算信心度
            top_scores = [score for _, score in sorted_numbers[:pick_count]]
            confidence = float(np.mean(top_scores)) if top_scores else 0.5

            return {
                'numbers': predicted,
                'confidence': min(0.95, max(0.3, confidence * 1.2)),
                'method': '號碼聚類分析',
                'report': f'識別 {n_clusters} 個號碼聚類，從活躍聚類中選擇高頻號碼',
                'details': {
                    'n_clusters': n_clusters,
                    'cluster_activity': cluster_activity
                }
            }

        except Exception as e:
            logger.error(f"聚類分析失敗: {str(e)}", exc_info=True)
            raise

    def _create_number_features(
        self,
        history: List[Dict],
        min_num: int,
        max_num: int
    ) -> Dict[int, List[float]]:
        """為每個號碼創建特徵向量"""
        features = {}
        all_numbers = [n for d in history for n in d['numbers']]
        freq = Counter(all_numbers)
        total_draws = len(history)

        for num in range(min_num, max_num + 1):
            # 特徵 1: 頻率
            freq_feature = freq.get(num, 0) / (total_draws * 6)

            # 特徵 2: 遺漏值
            gap = 0
            for d in reversed(history):
                if num in d['numbers']:
                    break
                gap += 1
            gap_feature = gap / total_draws

            # 特徵 3: 尾數分佈
            last_digit = num % 10
            digit_freq = sum(1 for n in all_numbers if n % 10 == last_digit)
            digit_feature = digit_freq / len(all_numbers) if all_numbers else 0

            # 特徵 4: 區間位置（0-1 標準化）
            zone_feature = (num - min_num) / (max_num - min_num)

            # 特徵 5: 奇偶屬性
            parity_feature = num % 2

            # 特徵 6: 近期頻率（近 20 期）
            recent = [n for d in history[-20:] for n in d['numbers']]
            recent_freq = Counter(recent)
            recent_feature = recent_freq.get(num, 0) / len(recent) if recent else 0

            features[num] = [
                freq_feature, gap_feature, digit_feature,
                zone_feature, parity_feature, recent_feature
            ]

        return features

    def _calculate_cluster_activity(
        self,
        recent_history: List[Dict],
        cluster_labels: np.ndarray,
        min_num: int,
        max_num: int
    ) -> Dict[int, float]:
        """計算每個聚類的活躍度"""
        cluster_activity = Counter()
        total = 0

        for draw in recent_history:
            for num in draw['numbers']:
                if min_num <= num <= max_num:
                    cluster = cluster_labels[num - min_num]
                    cluster_activity[cluster] += 1
                    total += 1

        # 標準化為概率
        if total > 0:
            for cluster in cluster_activity:
                cluster_activity[cluster] /= total

        return dict(cluster_activity)

    # ===========================================================================
    # 策略 3: 動態權重集成
    # ===========================================================================
    def dynamic_ensemble_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        動態權重集成策略

        原理：
        1. 使用滑動窗口評估各基礎策略的近期表現
        2. 根據表現動態分配權重（表現好的策略權重增加）
        3. 加權融合所有策略的預測結果
        4. 使用 Softmax 平滑權重分佈

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        try:
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            if len(history) < 50:
                raise ValueError("數據不足，至少需要 50 期")

            # 1. 定義基礎策略及其預測函數
            base_strategies = {
                'frequency': self._frequency_scores,
                'gap': self._gap_scores,
                'hot_cold': self._hot_cold_scores,
                'trend': self._trend_scores,
                'zone': self._zone_scores,
            }

            # 2. 評估每個策略在近期的表現
            eval_window = min(30, len(history) - 20)
            strategy_performance = {}

            for name, score_func in base_strategies.items():
                hits = 0
                for i in range(eval_window):
                    # 使用 i 之前的數據預測第 i 期
                    train_data = history[:-(eval_window - i)]
                    target = history[len(history) - eval_window + i]['numbers']

                    scores = score_func(train_data, min_num, max_num)
                    predicted = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:pick_count]
                    predicted_nums = [num for num, _ in predicted]

                    hits += len(set(predicted_nums) & set(target))

                strategy_performance[name] = hits / (eval_window * pick_count)

            # 3. 使用 Softmax 計算動態權重
            performances = list(strategy_performance.values())
            temperature = 0.5  # 控制權重分佈的銳度
            weights = self._softmax(performances, temperature)
            strategy_weights = dict(zip(strategy_performance.keys(), weights))

            # 4. 計算每個號碼的加權得分
            final_scores = {num: 0.0 for num in range(min_num, max_num + 1)}

            for name, score_func in base_strategies.items():
                scores = score_func(history, min_num, max_num)
                weight = strategy_weights[name]

                for num, score in scores.items():
                    final_scores[num] += weight * score

            # 5. 選擇得分最高的號碼
            sorted_numbers = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = sorted([num for num, _ in sorted_numbers[:pick_count]])

            # 計算信心度
            top_scores = [score for _, score in sorted_numbers[:pick_count]]
            confidence = float(np.mean(top_scores)) if top_scores else 0.5

            return {
                'numbers': predicted,
                'confidence': min(0.95, max(0.3, confidence * 1.3)),
                'method': '動態權重集成',
                'report': '根據近期表現自適應調整策略權重',
                'details': {
                    'strategy_weights': strategy_weights,
                    'strategy_performance': strategy_performance
                }
            }

        except Exception as e:
            logger.error(f"動態集成失敗: {str(e)}", exc_info=True)
            raise

    def _softmax(self, values: List[float], temperature: float = 1.0) -> List[float]:
        """計算 Softmax 權重"""
        values = np.array(values)
        exp_values = np.exp(values / temperature)
        return (exp_values / exp_values.sum()).tolist()

    def _frequency_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """頻率分數"""
        all_numbers = [n for d in history[-50:] for n in d['numbers']]
        freq = Counter(all_numbers)
        max_freq = max(freq.values()) if freq else 1
        return {num: freq.get(num, 0) / max_freq for num in range(min_num, max_num + 1)}

    def _gap_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """遺漏值分數"""
        gaps = {}
        for num in range(min_num, max_num + 1):
            gap = 0
            for d in reversed(history):
                if num in d['numbers']:
                    break
                gap += 1
            gaps[num] = gap

        max_gap = max(gaps.values()) if gaps else 1
        return {num: np.sqrt(gap / max_gap) for num, gap in gaps.items()}

    def _hot_cold_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """冷熱號分數"""
        recent = [n for d in history[-20:] for n in d['numbers']]
        long_term = [n for d in history for n in d['numbers']]

        recent_freq = Counter(recent)
        long_freq = Counter(long_term)

        max_recent = max(recent_freq.values()) if recent_freq else 1
        max_long = max(long_freq.values()) if long_freq else 1

        scores = {}
        for num in range(min_num, max_num + 1):
            r = recent_freq.get(num, 0) / max_recent
            l = long_freq.get(num, 0) / max_long
            scores[num] = 0.6 * r + 0.4 * l

        return scores

    def _trend_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """趨勢分數"""
        if len(history) < 40:
            return {num: 0.5 for num in range(min_num, max_num + 1)}

        mid = len(history) - 20
        early = [n for d in history[:mid] for n in d['numbers']]
        late = [n for d in history[mid:] for n in d['numbers']]

        early_freq = Counter(early)
        late_freq = Counter(late)

        scores = {}
        for num in range(min_num, max_num + 1):
            e = early_freq.get(num, 0) / len(early) if early else 0
            l = late_freq.get(num, 0) / len(late) if late else 0

            if l > e:
                scores[num] = 0.7 + (l - e) * 5
            elif l < e:
                scores[num] = 0.3 - (e - l) * 5
            else:
                scores[num] = 0.5

            scores[num] = max(0, min(1, scores[num]))

        return scores

    def _zone_scores(self, history: List[Dict], min_num: int, max_num: int) -> Dict[int, float]:
        """區間分數"""
        recent = [n for d in history[-20:] for n in d['numbers']]
        zone_size = (max_num - min_num + 1) // 5

        zone_freq = Counter()
        for n in recent:
            zone = (n - min_num) // zone_size
            zone_freq[zone] += 1

        max_zone = max(zone_freq.values()) if zone_freq else 1

        scores = {}
        for num in range(min_num, max_num + 1):
            zone = (num - min_num) // zone_size
            scores[num] = zone_freq.get(zone, 0) / max_zone

        return scores

    # ===========================================================================
    # 策略 4: 增強時間序列
    # ===========================================================================
    def temporal_enhanced_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        增強時間序列策略

        原理：
        1. FFT 傅里葉變換：識別週期性模式
        2. 多尺度趨勢分析：短期 + 中期 + 長期
        3. 季節性分解：提取趨勢、季節性、殘差
        4. 結合週期和趨勢預測下一期

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        try:
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            if len(history) < 60:
                raise ValueError("數據不足，至少需要 60 期進行時間序列分析")

            # 1. 為每個號碼創建時間序列
            time_series = self._create_number_time_series(history, min_num, max_num)

            temporal_scores = {}

            for num in range(min_num, max_num + 1):
                series = time_series[num]

                # 2. FFT 週期分析
                periodicity_score = self._fft_periodicity_score(series)

                # 3. 多尺度趨勢分析
                trend_score = self._multi_scale_trend_score(series)

                # 4. 近期動量
                momentum_score = self._momentum_score(series)

                # 5. 綜合評分
                temporal_scores[num] = (
                    0.3 * periodicity_score +
                    0.4 * trend_score +
                    0.3 * momentum_score
                )

            # 6. 選擇得分最高的號碼
            sorted_numbers = sorted(temporal_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = sorted([num for num, _ in sorted_numbers[:pick_count]])

            # 計算信心度
            top_scores = [score for _, score in sorted_numbers[:pick_count]]
            confidence = float(np.mean(top_scores)) if top_scores else 0.5

            return {
                'numbers': predicted,
                'confidence': min(0.95, max(0.3, confidence * 1.2)),
                'method': '時間序列增強分析',
                'report': 'FFT 週期分析 + 多尺度趨勢 + 動量指標',
                'details': {
                    'top_temporal_scores': dict(sorted_numbers[:10])
                }
            }

        except Exception as e:
            logger.error(f"時間序列分析失敗: {str(e)}", exc_info=True)
            raise

    def _create_number_time_series(
        self,
        history: List[Dict],
        min_num: int,
        max_num: int
    ) -> Dict[int, List[int]]:
        """創建每個號碼的時間序列（0/1 表示是否出現）"""
        time_series = {num: [] for num in range(min_num, max_num + 1)}

        for draw in history:
            for num in range(min_num, max_num + 1):
                time_series[num].append(1 if num in draw['numbers'] else 0)

        return time_series

    def _fft_periodicity_score(self, series: List[int]) -> float:
        """使用 FFT 計算週期性得分"""
        if len(series) < 16:
            return 0.5

        # 執行 FFT
        signal = np.array(series, dtype=float)
        signal = signal - np.mean(signal)  # 去均值

        n = len(signal)
        yf = fft(signal)
        xf = fftfreq(n)

        # 找出主要頻率成分
        power = np.abs(yf[:n // 2]) ** 2
        power[0] = 0  # 忽略 DC 分量

        if power.sum() == 0:
            return 0.5

        # 計算週期性強度（主頻能量佔比）
        top_k = min(3, len(power))
        top_power = np.sort(power)[-top_k:]
        periodicity = top_power.sum() / (power.sum() + 1e-10)

        # 檢查是否處於上升週期
        if len(yf) > 0:
            # 簡化：使用最後幾期的趨勢
            recent_trend = np.mean(series[-5:]) > np.mean(series[-10:-5])
            if recent_trend:
                periodicity *= 1.2

        return min(1.0, periodicity)

    def _multi_scale_trend_score(self, series: List[int]) -> float:
        """多尺度趨勢分析"""
        if len(series) < 30:
            return 0.5

        # 短期（10 期）
        short_term = np.mean(series[-10:]) if len(series) >= 10 else 0.5

        # 中期（30 期）
        mid_term = np.mean(series[-30:]) if len(series) >= 30 else 0.5

        # 長期（100 期）
        long_term = np.mean(series[-100:]) if len(series) >= 100 else np.mean(series)

        # 計算趨勢方向
        # 如果短期 > 長期，說明上升趨勢
        trend_score = 0.5

        if short_term > long_term * 1.2:
            trend_score = 0.8
        elif short_term > mid_term > long_term:
            trend_score = 0.75
        elif short_term > mid_term:
            trend_score = 0.65
        elif short_term < long_term * 0.8:
            trend_score = 0.3

        return trend_score

    def _momentum_score(self, series: List[int]) -> float:
        """計算動量指標"""
        if len(series) < 10:
            return 0.5

        # 使用移動平均計算動量
        short_ma = np.mean(series[-5:])
        long_ma = np.mean(series[-20:]) if len(series) >= 20 else np.mean(series)

        # 動量 = 短期均值 / 長期均值
        if long_ma > 0:
            momentum = short_ma / long_ma
        else:
            momentum = 1.0

        # 標準化到 0-1
        return min(1.0, max(0.0, momentum * 0.5))

    # ===========================================================================
    # 策略 5: 多維特徵工程
    # ===========================================================================
    def feature_engineering_predict(
        self,
        history: List[Dict],
        lottery_rules: Dict
    ) -> Dict:
        """
        多維特徵工程策略

        整合 12 維特徵：
        1. 頻率特徵：近期頻率、長期頻率、頻率變化率
        2. 遺漏特徵：遺漏值、平均遺漏、最大遺漏
        3. 形態特徵：尾數分佈、奇偶比、區間分佈
        4. 關聯特徵：共現頻率、轉移概率
        5. 統計特徵：AC值貢獻、和值貢獻

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則

        Returns:
            預測結果字典
        """
        try:
            pick_count = lottery_rules.get('pickCount', 6)
            min_num = lottery_rules.get('minNumber', 1)
            max_num = lottery_rules.get('maxNumber', 49)

            if len(history) < 50:
                raise ValueError("數據不足，至少需要 50 期")

            # 收集所有特徵
            all_features = {}

            for num in range(min_num, max_num + 1):
                features = []

                # 1. 頻率特徵 (3維)
                freq_features = self._extract_frequency_features(history, num)
                features.extend(freq_features)

                # 2. 遺漏特徵 (3維)
                gap_features = self._extract_gap_features(history, num)
                features.extend(gap_features)

                # 3. 形態特徵 (3維)
                pattern_features = self._extract_pattern_features(history, num, min_num, max_num)
                features.extend(pattern_features)

                # 4. 關聯特徵 (2維)
                correlation_features = self._extract_correlation_features(history, num, min_num, max_num)
                features.extend(correlation_features)

                # 5. 統計特徵 (1維)
                stat_features = self._extract_statistical_features(history, num)
                features.extend(stat_features)

                all_features[num] = features

            # 標準化特徵
            feature_matrix = np.array([all_features[n] for n in range(min_num, max_num + 1)])
            feature_matrix_scaled = self.scaler.fit_transform(feature_matrix)

            # 計算綜合得分（加權平均所有維度）
            # 權重可以根據歷史驗證調整
            weights = np.array([
                # 頻率特徵權重
                0.12, 0.08, 0.10,
                # 遺漏特徵權重
                0.10, 0.05, 0.08,
                # 形態特徵權重
                0.08, 0.07, 0.07,
                # 關聯特徵權重
                0.10, 0.08,
                # 統計特徵權重
                0.07
            ])

            final_scores = {}
            for i, num in enumerate(range(min_num, max_num + 1)):
                # 加權得分（確保權重總和為 1）
                score = np.dot(feature_matrix_scaled[i], weights / weights.sum())
                # 轉換為正數分數
                final_scores[num] = (score + 3) / 6  # 假設 z-score 範圍 -3 到 3

            # 選擇得分最高的號碼
            sorted_numbers = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
            predicted = sorted([num for num, _ in sorted_numbers[:pick_count]])

            # 計算信心度
            top_scores = [score for _, score in sorted_numbers[:pick_count]]
            confidence = float(np.mean(top_scores)) if top_scores else 0.5

            return {
                'numbers': predicted,
                'confidence': min(0.95, max(0.3, confidence * 1.1)),
                'method': '多維特徵工程',
                'report': f'整合 12 維特徵進行綜合預測',
                'details': {
                    'feature_dimensions': 12,
                    'top_scores': dict(sorted_numbers[:10])
                }
            }

        except Exception as e:
            logger.error(f"特徵工程分析失敗: {str(e)}", exc_info=True)
            raise

    def _extract_frequency_features(self, history: List[Dict], num: int) -> List[float]:
        """提取頻率特徵"""
        # 近期頻率 (20期)
        recent = [d for d in history[-20:]]
        recent_count = sum(1 for d in recent if num in d['numbers'])
        recent_freq = recent_count / len(recent) if recent else 0

        # 長期頻率
        long_count = sum(1 for d in history if num in d['numbers'])
        long_freq = long_count / len(history) if history else 0

        # 頻率變化率
        if len(history) >= 40:
            early_count = sum(1 for d in history[:len(history)//2] if num in d['numbers'])
            late_count = sum(1 for d in history[len(history)//2:] if num in d['numbers'])
            early_freq = early_count / (len(history) // 2)
            late_freq = late_count / (len(history) - len(history) // 2)
            change_rate = late_freq - early_freq
        else:
            change_rate = 0

        return [recent_freq, long_freq, change_rate]

    def _extract_gap_features(self, history: List[Dict], num: int) -> List[float]:
        """提取遺漏特徵"""
        # 當前遺漏值
        current_gap = 0
        for d in reversed(history):
            if num in d['numbers']:
                break
            current_gap += 1

        # 計算歷史遺漏分佈
        gaps = []
        gap = 0
        for d in history:
            if num in d['numbers']:
                if gap > 0:
                    gaps.append(gap)
                gap = 0
            else:
                gap += 1

        avg_gap = np.mean(gaps) if gaps else 0
        max_gap = max(gaps) if gaps else 0

        # 標準化
        return [
            current_gap / (len(history) + 1),
            avg_gap / (len(history) + 1),
            max_gap / (len(history) + 1)
        ]

    def _extract_pattern_features(
        self,
        history: List[Dict],
        num: int,
        min_num: int,
        max_num: int
    ) -> List[float]:
        """提取形態特徵"""
        recent = history[-30:]
        all_numbers = [n for d in recent for n in d['numbers']]

        # 尾數分佈
        last_digit = num % 10
        digit_count = sum(1 for n in all_numbers if n % 10 == last_digit)
        digit_score = digit_count / len(all_numbers) if all_numbers else 0

        # 奇偶比（與當前號碼的匹配度）
        is_odd = num % 2 == 1
        odd_count = sum(1 for n in all_numbers if n % 2 == 1)
        odd_ratio = odd_count / len(all_numbers) if all_numbers else 0.5
        parity_score = odd_ratio if is_odd else (1 - odd_ratio)

        # 區間分佈
        zone_size = (max_num - min_num + 1) // 5
        num_zone = (num - min_num) // zone_size
        zone_count = sum(1 for n in all_numbers if (n - min_num) // zone_size == num_zone)
        zone_score = zone_count / len(all_numbers) if all_numbers else 0

        return [digit_score, parity_score, zone_score]

    def _extract_correlation_features(
        self,
        history: List[Dict],
        num: int,
        min_num: int,
        max_num: int
    ) -> List[float]:
        """提取關聯特徵"""
        recent = history[-50:]

        # 共現頻率（與其他號碼一起出現的頻率）
        co_occurrence = 0
        num_appearances = 0

        for d in recent:
            if num in d['numbers']:
                num_appearances += 1
                co_occurrence += len(d['numbers']) - 1  # 排除自己

        avg_co_occurrence = co_occurrence / num_appearances if num_appearances > 0 else 0

        # 轉移概率（前一期出現後，這期也出現的概率）
        transitions = 0
        transition_count = 0

        for i in range(1, len(recent)):
            prev_nums = recent[i - 1]['numbers']
            curr_nums = recent[i]['numbers']

            # 如果前一期有任何號碼, 這期是否有 num
            if len(prev_nums) > 0:
                if num in curr_nums:
                    transitions += 1
                transition_count += 1

        transition_prob = transitions / transition_count if transition_count > 0 else 0

        return [
            avg_co_occurrence / 6,  # 標準化到約 0-1
            transition_prob
        ]

    def _extract_statistical_features(self, history: List[Dict], num: int) -> List[float]:
        """提取統計特徵"""
        recent = history[-30:]

        # 計算號碼對 AC 值的平均貢獻
        ac_contributions = []

        for d in recent:
            if num in d['numbers']:
                nums = sorted(d['numbers'])
                # 計算 AC 值
                diffs = set()
                for i in range(len(nums)):
                    for j in range(i + 1, len(nums)):
                        diffs.add(nums[j] - nums[i])
                ac = max(0, len(diffs) - (len(nums) - 1))
                ac_contributions.append(ac)

        avg_ac = np.mean(ac_contributions) if ac_contributions else 0

        return [avg_ac / 10]  # 標準化
