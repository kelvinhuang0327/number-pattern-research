"""
Thompson Sampling MAB單元測試
"""
import unittest
import numpy as np
import tempfile
import os
import sys

# Add project to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.mab_ensemble import ThompsonSamplingEnsemble, MABEnsemblePredictor


class TestThompsonSamplingEnsemble(unittest.TestCase):
    """測試Thompson Sampling MAB核心功能"""
    
    def setUp(self):
        """測試前初始化"""
        self.strategies = ['frequency', 'trend', 'bayesian', 'markov']
        self.mab = ThompsonSamplingEnsemble(self.strategies, window=10)
    
    def test_initialization(self):
        """測試初始化"""
        self.assertEqual(len(self.mab.strategies), 4)
        self.assertEqual(self.mab.window, 10)
        
        # 檢查Beta參數初始化為1.0
        for strategy in self.strategies:
            self.assertEqual(self.mab.alpha[strategy], 1.0)
            self.assertEqual(self.mab.beta[strategy], 1.0)
    
    def test_sample_weights(self):
        """測試權重採樣"""
        weights = self.mab.sample_weights()
        
        # 檢查所有策略都有權重
        self.assertEqual(set(weights.keys()), set(self.strategies))
        
        # 檢查權重總和為1（歸一化）
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        
        # 檢查權重都是正數
        for w in weights.values():
            self.assertGreater(w, 0)
    
    def test_expected_weights(self):
        """測試期望權重計算"""
        # 初始狀態下，期望權重應該均勻
        weights = self.mab.get_expected_weights()
        
        for w in weights.values():
            self.assertAlmostEqual(w, 0.25, places=2)  # 4個策略=25%
    
    def test_update_progressive(self):
        """測試progressive獎勵更新"""
        # 模擬預測
        predictions = {
            'frequency': [1, 2, 3, 4, 5, 6],
            'trend': [7, 8, 9, 10, 11, 12],
            'bayesian': [1, 7, 13, 19, 25, 31],
            'markov': [2, 8, 14, 20, 26, 32]
        }
        actual = [1, 2, 7, 8, 13, 14]  # frequency命中2, trend命中2, bayesian命中2, markov命中2
        
        initial_alpha = dict(self.mab.alpha)
        initial_beta = dict(self.mab.beta)
        
        rewards = self.mab.update(predictions, actual, reward_scheme='progressive')
        
        # 檢查所有策略都被更新
        for strategy in self.strategies:
            self.assertNotEqual(self.mab.alpha[strategy], initial_alpha[strategy])
            self.assertNotEqual(self.mab.beta[strategy], initial_beta[strategy])
        
        # 檢查rewards返回
        self.assertEqual(rewards['frequency'], 2)
        self.assertEqual(rewards['trend'], 2)
    
    def test_update_match3_reward(self):
        """測試Match-3+重賞機制"""
        predictions = {
            'frequency': [1, 2, 3, 19, 25, 31],  # Match-3
            'trend': [7, 8, 9, 10, 11, 12],      # Match-0
        }
        actual = [1, 2, 3, 4, 5, 6]
        
        self.mab.update(predictions, actual, reward_scheme='progressive')
        
        # frequency應該獲得大獎(α增加10)
        self.assertGreater(self.mab.alpha['frequency'], self.mab.alpha['trend'])
        
        # trend應該被懲罰(β增加5)
        self.assertGreater(self.mab.beta['trend'], self.mab.beta['frequency'])
    
    def test_decay(self):
        """測試衰減機制"""
        # 先更新一些數據
        for _ in range(15):  # 超過window=10
            predictions = {s: [1, 2, 3, 4, 5, 6] for s in self.strategies}
            actual = [1, 2, 3, 7, 8, 9]
            self.mab.update(predictions, actual)
        
        # 所有α應該大於1但不會無限增長（因為衰減）
        for strategy in self.strategies:
            alpha = self.mab.alpha[strategy]
            self.assertGreater(alpha, 1.0)
            self.assertLess(alpha, 200.0)  # 調整上限（衰減會限制增長）
    
    def test_save_and_load(self):
        """測試保存和載入狀態"""
        # 更新一些數據
        predictions = {s: [1, 2, 3, 4, 5, 6] for s in self.strategies}
        actual = [1, 2, 3, 7, 8, 9]
        self.mab.update(predictions, actual)
        
        # 保存到臨時檔案
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            self.mab.save(temp_path)
            
            # 載入
            loaded_mab = ThompsonSamplingEnsemble.load(temp_path)
            
            # 檢查狀態一致
            self.assertEqual(loaded_mab.strategies, self.mab.strategies)
            self.assertEqual(loaded_mab.window, self.mab.window)
            
            for strategy in self.strategies:
                self.assertEqual(loaded_mab.alpha[strategy], self.mab.alpha[strategy])
                self.assertEqual(loaded_mab.beta[strategy], self.mab.beta[strategy])
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_statistics(self):
        """測試統計信息"""
        # 更新一些數據
        predictions = {s: [1, 2, 3, 4, 5, 6] for s in self.strategies}
        actual = [1, 2, 3, 7, 8, 9]
        self.mab.update(predictions, actual)
        
        stats = self.mab.get_statistics()
        
        # 檢查統計結構
        self.assertIn('total_predictions', stats)
        self.assertIn('strategies', stats)
        self.assertEqual(stats['total_predictions'], 1)
        
        for strategy in self.strategies:
            self.assertIn(strategy, stats['strategies'])
            self.assertIn('expected_weight', stats['strategies'][strategy])


class TestMABEnsemblePredictor(unittest.TestCase):
    """測試MAB Ensemble預測器"""
    
    def setUp(self):
        """測試前初始化"""
        def mock_predictor(name, numbers):
            """模擬預測函數"""
            def predict(history, rules):
                return {'numbers': numbers, 'method': name}
            return predict
        
        self.predictors = {
            'freq': mock_predictor('freq', [1, 2, 3, 4, 5, 6]),
            'trend': mock_predictor('trend', [7, 8, 9, 10, 11, 12]),
            'bayes': mock_predictor('bayes', [1, 7, 13, 19, 25, 31])
        }
        
        # 使用臨時路徑
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            self.temp_state_path = f.name
        
        self.ensemble = MABEnsemblePredictor(
            predictors=self.predictors,
            mab_config={
                'window': 10,
                'state_path': self.temp_state_path
            }
        )
    
    def tearDown(self):
        """清理臨時檔案"""
        if os.path.exists(self.temp_state_path):
            os.remove(self.temp_state_path)
    
    def test_predict(self):
        """測試預測"""
        history = []
        rules = {'pickCount': 6}
        
        result = self.ensemble.predict(history, rules, use_expected=True)
        
        # 檢查結果結構
        self.assertIn('numbers', result)
        self.assertIn('method', result)
        self.assertIn('weights', result)
        self.assertEqual(result['method'], 'mab_ensemble')
        self.assertEqual(len(result['numbers']), 6)
    
    def test_update_with_result(self):
        """測試結果更新"""
        strategy_predictions = {
            'freq': [1, 2, 3, 4, 5, 6],
            'trend': [7, 8, 9, 10, 11, 12],
            'bayes': [1, 7, 13, 19, 25, 31]
        }
        actual = [1, 2, 3, 7, 8, 13]
        
        rewards = self.ensemble.update_with_result(strategy_predictions, actual)
        
        # 檢查rewards
        self.assertEqual(rewards['freq'], 3)   # Match-3
        self.assertEqual(rewards['trend'], 2)  # Match-2
        self.assertEqual(rewards['bayes'], 3)  # Match-3


if __name__ == '__main__':
    # 設定隨機種子確保可重複性
    np.random.seed(42)
    unittest.main()
