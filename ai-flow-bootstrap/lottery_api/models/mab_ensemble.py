"""
Multi-Armed Bandit Ensemble System
使用Thompson Sampling動態調整策略權重

核心理念：
- 每個預測策略視為一個「臂」(arm)
- 根據近期表現自動調整權重
- Beta分佈採樣實現探索-利用平衡
"""
import numpy as np
import json
import os
from collections import deque, defaultdict
from typing import List, Dict, Tuple, Optional
import logging
from .stability_profile import get_stability_profile

logger = logging.getLogger(__name__)


class ThompsonSamplingEnsemble:
    """Thompson Sampling 多臂老虎機集成器"""
    
    def __init__(self, strategy_names: List[str], window: int = 30):
        """
        初始化MAB集成器
        """
        self.strategies = strategy_names
        self.window = window
        self.regimes = ['ORDER', 'CHAOS', 'TRANSITION', 'GLOBAL']
        
        # 嵌套字典: regime -> strategy -> value
        self.alpha = {r: {s: 1.0 for s in strategy_names} for r in self.regimes}
        self.beta = {r: {s: 1.0 for s in strategy_names} for r in self.regimes}
        
        self.history = deque(maxlen=window)
        self.total_predictions = 0
        self.total_hits = {r: defaultdict(int) for r in self.regimes}
        self.total_misses = {r: defaultdict(int) for r in self.regimes}
        
        logger.info(f"初始化Thompson Sampling MAB (Regime-Aware): {len(strategy_names)}個策略, 窗口={window}期")
    
    def sample_weights(self, temperature: float = 1.0, regime: str = 'GLOBAL') -> Dict[str, float]:
        """
        從指定 Regime 的 Beta分佈採樣客率權重
        """
        if regime not in self.regimes: regime = 'GLOBAL'
        
        weights = {}
        for strategy in self.strategies:
            alpha_adj = self.alpha[regime][strategy] ** (1.0 / temperature)
            beta_adj = self.beta[regime][strategy] ** (1.0 / temperature)
            sampled_value = np.random.beta(alpha_adj, beta_adj)
            weights[strategy] = sampled_value
        
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        else:
            weights = {k: 1.0 / len(self.strategies) for k in self.strategies}
        
        return weights
    
    def get_expected_weights(self, regime: str = 'GLOBAL') -> Dict[str, float]:
        """獲取指定 Regime 的期望權重"""
        if regime not in self.regimes: regime = 'GLOBAL'
        
        weights = {}
        for strategy in self.strategies:
            alpha = self.alpha[regime][strategy]
            beta = self.beta[regime][strategy]
            weights[strategy] = alpha / (alpha + beta)
        
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def update(self, strategy_predictions: Dict[str, List[int]], 
               actual_numbers: List[int],
               regime: str = 'GLOBAL',
               reward_scheme: str = 'progressive') -> Dict[str, float]:
        """
        根據預測結果更新策略表現
        同時更新 GLOBAL 和特定 Regime 的分佈
        """
        if regime not in self.regimes: regime = 'GLOBAL'
        
        actual_set = set(actual_numbers)
        rewards = {}
        
        for strategy, predicted in strategy_predictions.items():
            if strategy not in self.strategies:
                continue
            
            predicted_set = set(predicted)
            hits = len(predicted_set & actual_set)
            misses = len(predicted_set) - hits
            
            uniqueness_bonus = 1.0
            if hits >= 3:
                other_winners = 0
                for s_name in self.strategies:
                    if s_name == strategy: continue
                    s_pred = set(strategy_predictions.get(s_name, []))
                    if len(s_pred & actual_set) >= 3:
                        other_winners += 1
                
                if other_winners == 0: uniqueness_bonus = 2.5
                elif other_winners == 1: uniqueness_bonus = 1.5
                elif other_winners <= 3: uniqueness_bonus = 1.2

            if reward_scheme == 'progressive':
                if hits >= 3:
                    alpha_reward = 20.0 * uniqueness_bonus
                    beta_penalty = 0.0
                elif hits == 2:
                    alpha_reward = 5.0
                    beta_penalty = 1.0
                elif hits == 1:
                    alpha_reward = 1.0
                    beta_penalty = 2.0
                else:
                    alpha_reward = 0.0
                    beta_penalty = 1.0
            
            elif reward_scheme == 'linear':
                alpha_reward = hits * 2.0
                beta_penalty = misses * 0.5
            
            elif reward_scheme == 'binary':
                if hits >= 3:
                    alpha_reward = 10.0
                    beta_penalty = 0.0
                else:
                    alpha_reward = 0.0
                    beta_penalty = 5.0
            else:
                raise ValueError(f"Unknown reward_scheme: {reward_scheme}")
            
            # 更新特定 Regime 的參數
            self.alpha[regime][strategy] += alpha_reward
            self.beta[regime][strategy] += beta_penalty
            
            # 同時更新 GLOBAL 參數（作為基準）
            if regime != 'GLOBAL':
                self.alpha['GLOBAL'][strategy] += alpha_reward * 0.5 # Global 更新權重減半，更穩定
                self.beta['GLOBAL'][strategy] += beta_penalty * 0.5
            
            # 記錄統計
            self.total_hits[regime][strategy] += hits
            self.total_misses[regime][strategy] += misses
            rewards[strategy] = hits
        
        # 記錄到歷史
        self.history.append({
            'predictions': strategy_predictions,
            'actual': actual_numbers,
            'rewards': rewards,
            'regime': regime
        })
        
        self.total_predictions += 1
        
        # Sliding window衰減 (✨ Phase Stability Audit: 傳遞 lottery_type 以支持動態衰減)
        if len(self.history) >= self.window:
            # 嘗試從歷史中獲取最近的 lottery_type 標籤，或默認使用 GLOBAL
            self._apply_decay(lottery_type=strategy_predictions.get('_lottery_type', 'POWER_LOTTO'))
        
        return rewards
    
    def _apply_decay(self, decay_factor: float = 0.95, lottery_type: str = "POWER_LOTTO"):
        """
        對所有分佈施加衰減。
        ✨ Phase Stability Audit: 基於策略穩定性檔案實施動態衰減因子。
        """
        profile_mgr = get_stability_profile()
        
        for regime in self.regimes:
            for strategy in self.strategies:
                # 獲取策略穩定性
                stability = profile_mgr.get_strategy_stability(lottery_type, strategy)
                status = stability.get('status', 'UNKNOWN')
                
                # 動態調整衰減因子
                # SHORT_MOMENTUM: 衰減快 (Factor 小)，快速忘記過期表現
                # ROBUST / STABLE: 衰減慢 (Factor 大)，保留長期表現
                current_decay = decay_factor
                if status == 'SHORT_MOMENTUM':
                    current_decay = 0.85 # 快速衰減，對近期表現更敏感
                elif status == 'ROBUST':
                    current_decay = 0.98 # 緩慢衰減，保留長線學分
                elif status == 'LATE_BLOOMER':
                    current_decay = 0.99 # 極慢衰減，適合大樣本
                
                self.alpha[regime][strategy] = 1.0 + (self.alpha[regime][strategy] - 1.0) * current_decay
                self.beta[regime][strategy] = 1.0 + (self.beta[regime][strategy] - 1.0) * current_decay
    
    def get_statistics(self) -> Dict:
        """獲取MAB分佈統計信息"""
        stats = {
            'total_predictions': self.total_predictions,
            'window_size': self.window,
            'regimes': {}
        }
        
        for regime in self.regimes:
            regime_stats = {}
            for strategy in self.strategies:
                alpha = self.alpha[regime][strategy]
                beta = self.beta[regime][strategy]
                regime_stats[strategy] = {
                    'alpha': float(alpha),
                    'beta': float(beta),
                    'expected_weight': float(alpha / (alpha + beta)),
                    'success_rate': self.total_hits[regime][strategy] / max(1, self.total_hits[regime][strategy] + self.total_misses[regime][strategy])
                }
            stats['regimes'][regime] = regime_stats
        
        return stats
    
    def save(self, filepath: str):
        """保存MAB狀態到檔案"""
        state = {
            'strategies': self.strategies,
            'window': self.window,
            'alpha': self.alpha,
            'beta': self.beta,
            'total_predictions': self.total_predictions,
            'total_hits': dict(self.total_hits),
            'total_misses': dict(self.total_misses),
            'history': list(self.history)
        }
        
        class NpEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super(NpEncoder, self).default(obj)

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, cls=NpEncoder)
        
        logger.info(f"MAB狀態已保存: {filepath}")
    
    @classmethod
    def load(cls, filepath: str, expected_strategies: List[str] = None) -> 'ThompsonSamplingEnsemble':
        """從檔案載入MAB狀態 (含平滑遷移與新策略探索邏輯)"""
        with open(filepath, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        # 決定最終使用的策略列表
        file_strategies = state.get('strategies', [])
        final_strategies = expected_strategies if expected_strategies else file_strategies
        
        mab = cls(
            strategy_names=final_strategies,
            window=state.get('window', 30)
        )
        
        # 遷移邏輯：檢查是否為舊版格式 (非嵌套字典)
        alpha_data = state['alpha']
        beta_data = state['beta']
        
        if alpha_data and not isinstance(alpha_data[next(iter(alpha_data))], dict):
            # 舊版格式: strategy -> value
            logger.info("檢測到舊版 MAB 格式，正在遷移至 GLOBAL Regime...")
            for s, v in alpha_data.items():
                if s in mab.alpha['GLOBAL']:
                    mab.alpha['GLOBAL'][s] = v
            for s, v in beta_data.items():
                if s in mab.beta['GLOBAL']:
                    mab.beta['GLOBAL'][s] = v
        else:
            # 新版格式: regime -> strategy -> value
            # 遍歷 Regimes 與策略，合併現有數據
            for r in mab.regimes:
                if r in alpha_data:
                    for s, v in alpha_data[r].items():
                        if s in mab.alpha[r]:
                            mab.alpha[r][s] = v
                    for s, v in beta_data[r].items():
                        if s in mab.beta[r]:
                            mab.beta[r][s] = v
            
        mab.total_predictions = state.get('total_predictions', 0)
        mab.history = deque(state.get('history', []), maxlen=state['window'])
        
        # 統計數據遷移
        hits = state.get('total_hits', {})
        misses = state.get('total_misses', {})
        if hits and not isinstance(list(hits.values())[0], dict):
             mab.total_hits['GLOBAL'] = defaultdict(int, hits)
             mab.total_misses['GLOBAL'] = defaultdict(int, misses)
        else:
             mab.total_hits = {r: defaultdict(int, hits.get(r, {})) for r in mab.regimes}
             mab.total_misses = {r: defaultdict(int, misses.get(r, {})) for r in mab.regimes}
        
        logger.info(f"MAB狀態已載入並完成遷移: {filepath}")
        return mab
    
    def reset(self):
        """重置MAB到初始狀態"""
        self.alpha = {s: 1.0 for s in self.strategies}
        self.beta = {s: 1.0 for s in self.strategies}
        self.history.clear()
        self.total_predictions = 0
        self.total_hits = defaultdict(int)
        self.total_misses = defaultdict(int)
        logger.info("MAB已重置到初始狀態")


class MABEnsemblePredictor:
    """
    MAB Ensemble預測器
    整合Thompson Sampling到預測流程中
    """
    
    def __init__(self, predictors: Dict, mab_config: Optional[Dict] = None):
        """
        Args:
            predictors: 策略名稱 -> 預測函數的字典
            mab_config: MAB配置
                - window: 窗口大小
                - reward_scheme: 獎勵方案
                - temperature: 採樣溫度
                - state_path: 狀態保存路徑
        """
        self.predictors = predictors
        config = mab_config or {}
        
        self.window = config.get('window', 30)
        self.reward_scheme = config.get('reward_scheme', 'progressive')
        self.temperature = config.get('temperature', 1.0)
        self.state_path = config.get('state_path', 'data/mab_state.json')
        
        # 初始化或載入MAB
        if os.path.exists(self.state_path):
            try:
                # ✨ Phase 49: 傳遞 expected_strategies 以支持動態新策略發現
                self.mab = ThompsonSamplingEnsemble.load(
                    self.state_path, 
                    expected_strategies=list(predictors.keys())
                )
                logger.info(f"載入已存在的MAB狀態，偵測到 {len(self.mab.strategies)} 個策略")
            except Exception as e:
                logger.warning(f"載入MAB狀態失敗: {e}，創建新實例")
                self.mab = ThompsonSamplingEnsemble(
                    strategy_names=list(predictors.keys()),
                    window=self.window
                )
        else:
            self.mab = ThompsonSamplingEnsemble(
                strategy_names=list(predictors.keys()),
                window=self.window
            )
    
    def predict(self, history: List[Dict], lottery_rules: Dict, 
                regime: str = 'GLOBAL',
                use_expected: bool = False) -> Dict:
        """
        使用MAB權重進行ensemble預測
        """
        # 獲取權重
        if use_expected:
            weights = self.mab.get_expected_weights(regime=regime)
        else:
            weights = self.mab.sample_weights(temperature=self.temperature, regime=regime)
        
        # 執行各策略預測
        strategy_predictions = {}
        number_scores = defaultdict(float)
        
        for strategy_name, predictor_func in self.predictors.items():
            try:
                result = predictor_func(history, lottery_rules)
                predicted_nums = result.get('numbers', [])
                strategy_predictions[strategy_name] = predicted_nums
                
                # 加權投票
                weight = weights.get(strategy_name, 0.0)
                for num in predicted_nums:
                    number_scores[num] += weight
                
            except Exception as e:
                logger.warning(f"策略 {strategy_name} 預測失敗: {e}")
                continue
        
        # 選擇top-K號碼
        pick_count = lottery_rules.get('pickCount', 6)
        sorted_numbers = sorted(number_scores.keys(), 
                               key=lambda x: -number_scores[x])
        final_numbers = sorted(sorted_numbers[:pick_count])
        
        return {
            'numbers': final_numbers,
            'method': 'mab_ensemble',
            'regime': regime,
            'weights': weights,
            'confidence': np.mean(list(weights.values())),
            'metadata': {
                'strategy_predictions': strategy_predictions,
                'mab_statistics': self.mab.get_statistics()
            }
        }
    
    def update_with_result(self, strategy_predictions: Dict[str, List[int]], 
                          actual_numbers: List[int],
                          regime: str = 'GLOBAL',
                          lottery_type: str = 'POWER_LOTTO'):
        """
        用實際結果更新MAB
        """
        # ✨ Phase Stability Audit: 注入 lottery_type 標籤供內部 decay 使用
        strategy_predictions_meta = strategy_predictions.copy()
        strategy_predictions_meta['_lottery_type'] = lottery_type

        rewards = self.mab.update(
            strategy_predictions=strategy_predictions_meta,
            actual_numbers=actual_numbers,
            regime=regime,
            reward_scheme=self.reward_scheme
        )
        
        # 保存狀態
        try:
            self.mab.save(self.state_path)
        except Exception as e:
            logger.error(f"保存MAB狀態失敗: {e}")
        
        return rewards
